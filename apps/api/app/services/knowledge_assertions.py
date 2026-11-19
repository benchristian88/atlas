"""Immutable, evidence-backed knowledge assertion helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KnowledgeAssertion
from app.services.predicate_definitions import predicate_cardinality
from app.services.knowledge_locks import lock_subject
from app.services.proxmox_guest_bindings import GuestBindings
from app.utils.json_values import to_json_value


def _same_claim(left: KnowledgeAssertion, value: Any, object_external_id: str | None) -> bool:
    return left.value_json == value and left.object_external_id == object_external_id


def current_assertions(
    db: Session,
    *,
    subject_type: str,
    subject_id: uuid.UUID | None = None,
    subject_external_id: str | None = None,
) -> list[KnowledgeAssertion]:
    query = select(KnowledgeAssertion).where(
        KnowledgeAssertion.subject_type == subject_type,
        KnowledgeAssertion.is_source_current.is_(True),
    )
    if subject_id is not None:
        query = query.where(KnowledgeAssertion.subject_id == subject_id)
    if subject_external_id is not None:
        query = query.where(
            KnowledgeAssertion.subject_external_id == subject_external_id
        )
    return list(db.scalars(query.order_by(KnowledgeAssertion.predicate)))


def mark_superseded(
    previous: KnowledgeAssertion,
    replacement: KnowledgeAssertion,
    at: datetime,
) -> None:
    previous.is_current = False
    previous.is_source_current = False
    previous.confirmation_status = "superseded"
    previous.valid_to = at
    previous.superseded_by_id = replacement.id


def detect_simple_conflicts(
    db: Session, assertion: KnowledgeAssertion
) -> list[KnowledgeAssertion]:
    candidates = db.scalars(
        select(KnowledgeAssertion).where(
            KnowledgeAssertion.customer_id == assertion.customer_id,
            KnowledgeAssertion.site_id == assertion.site_id,
            KnowledgeAssertion.subject_type == assertion.subject_type,
            KnowledgeAssertion.subject_id == assertion.subject_id,
            KnowledgeAssertion.subject_external_id == assertion.subject_external_id,
            KnowledgeAssertion.predicate == assertion.predicate,
            KnowledgeAssertion.id != assertion.id,
            KnowledgeAssertion.is_source_current.is_(True),
        )
    )
    return [
        candidate
        for candidate in candidates
        if not _same_claim(
            candidate, assertion.value_json, assertion.object_external_id
        )
    ]


def record_assertion(
    db: Session,
    *,
    customer_id: uuid.UUID,
    site_id: uuid.UUID | None,
    subject_type: str,
    predicate: str,
    value: Any = None,
    subject_id: uuid.UUID | None = None,
    subject_external_id: str | None = None,
    object_type: str | None = None,
    object_id: uuid.UUID | None = None,
    object_external_id: str | None = None,
    truth_classification: str = "observed",
    data_source_id: uuid.UUID | None = None,
    discovery_run_id: uuid.UUID | None = None,
    evidence_record_id: uuid.UUID | None = None,
    confidence: float = 1.0,
    observed_at: datetime | None = None,
    fact_metadata: dict | None = None,
    guest_bindings: GuestBindings | None = None,
    identity_epoch: int = 0,
    owner_external_id: str | None = None,
    reviewed_release: bool = False,
    coalesce: bool = True,
) -> tuple[KnowledgeAssertion, bool]:
    """Record a current assertion, coalescing identical observations from one source."""

    observed_at = observed_at or datetime.now(timezone.utc)
    value = to_json_value(value)
    cardinality = predicate_cardinality(predicate, object_type=object_type)
    aliases = guest_bindings.aliases(subject_type=subject_type, subject_external_id=subject_external_id,
        object_type=object_type, object_external_id=object_external_id,
        owner_external_id=owner_external_id, epoch=identity_epoch) if guest_bindings else set()
    current = [] if reviewed_release else list(
        db.scalars(
            select(KnowledgeAssertion).where(
                KnowledgeAssertion.customer_id == customer_id,
                KnowledgeAssertion.site_id == site_id,
                KnowledgeAssertion.subject_type == subject_type,
                KnowledgeAssertion.subject_id == subject_id,
                KnowledgeAssertion.subject_external_id == subject_external_id,
                KnowledgeAssertion.predicate == predicate,
                KnowledgeAssertion.data_source_id == data_source_id,
                KnowledgeAssertion.is_source_current.is_(True),
            )
        )
    )
    if aliases and object_type is not None:
        current = [claim for claim in current if (claim.object_type, claim.object_id, claim.object_external_id) ==
                   (object_type, object_id, object_external_id)]
    if aliases:
        current = [claim for claim in current if not guest_bindings.crossed(
            aliases | guest_bindings.claim_aliases(claim, claim.identity_epoch or 0), claim.identity_epoch or 0, identity_epoch)]
    for assertion in current if coalesce else ():
        if (_same_claim(assertion, value, object_external_id) and assertion.fact_metadata == fact_metadata
                and assertion.retracted_at is None and assertion.superseded_by_id is None
                and assertion.confirmation_status != "superseded"):
            assertion.last_observed_at = observed_at
            assertion.discovery_run_id = discovery_run_id
            assertion.evidence_record_id = evidence_record_id
            assertion.confidence = Decimal(str(confidence))
            if aliases:
                assertion.identity_epoch = identity_epoch
            return assertion, False

    assertion = KnowledgeAssertion(
        customer_id=customer_id,
        site_id=site_id,
        subject_type=subject_type,
        subject_id=subject_id,
        subject_external_id=subject_external_id,
        predicate=predicate,
        value_json=value,
        fact_metadata=fact_metadata,
        object_type=object_type,
        object_id=object_id,
        object_external_id=object_external_id,
        truth_classification=truth_classification,
        confirmation_status="unreviewed",
        data_source_id=data_source_id,
        discovery_run_id=discovery_run_id,
        evidence_record_id=evidence_record_id,
        identity_epoch=identity_epoch if aliases else None,
        confidence=Decimal(str(confidence)),
        first_observed_at=observed_at,
        last_observed_at=observed_at,
        is_current=True,
        is_source_current=True,
        is_accepted=False,
    )
    db.add(assertion)
    db.flush()

    if cardinality == "single":
        for previous in current:
            mark_superseded(previous, assertion, observed_at)

    conflicting = None
    if cardinality == "single" and not reviewed_release:
        candidates = db.scalars(select(KnowledgeAssertion).where(
            KnowledgeAssertion.customer_id == customer_id,
            KnowledgeAssertion.site_id == site_id,
            KnowledgeAssertion.subject_type == subject_type,
            KnowledgeAssertion.subject_id == subject_id,
            KnowledgeAssertion.subject_external_id == subject_external_id,
            KnowledgeAssertion.predicate == predicate,
            KnowledgeAssertion.data_source_id != data_source_id,
            KnowledgeAssertion.is_source_current.is_(True),
        ))
        for candidate in candidates:
            bindings = GuestBindings.for_scope(db, candidate, candidate.data_source_id)
            if not bindings or not bindings.stale(candidate):
                conflicting = candidate
                break
    if (
        cardinality == "single"
        and conflicting is not None
        and not _same_claim(conflicting, value, object_external_id)
    ):
        assertion.confirmation_status = "conflicted"
        if conflicting.confirmation_status == "unreviewed":
            conflicting.confirmation_status = "conflicted"
    return assertion, True


def create_fact_assertion(db: Session, **values) -> tuple[KnowledgeAssertion, bool]:
    return record_assertion(db, **values)


def create_relationship_assertion(
    db: Session, **values
) -> tuple[KnowledgeAssertion, bool]:
    if not values.get("object_type") or not (
        values.get("object_id") or values.get("object_external_id")
    ):
        raise ValueError("Relationship assertions require an object identity")
    return record_assertion(db, value=None, **values)


def confirm(assertion: KnowledgeAssertion) -> None:
    assertion.confirmation_status = "confirmed"


def reject(assertion: KnowledgeAssertion) -> None:
    assertion.confirmation_status = "rejected"
    assertion.is_accepted = False
    assertion.accepted_at = None
    assertion.accepted_by_user_id = None


def accept_assertion(
    db: Session,
    assertion: KnowledgeAssertion,
    *,
    user_id: uuid.UUID | None = None,
    accepted_at: datetime | None = None,
) -> list[KnowledgeAssertion]:
    """Choose an assertion as canonical Atlas knowledge.

    Source freshness and acceptance are intentionally independent. For a
    single-valued predicate, prior accepted assertions are cleared before the
    selected assertion is marked accepted. Multi-valued predicates can have
    more than one accepted assertion.
    """

    if assertion.retracted_at is not None:
        raise ValueError("A retracted assertion cannot be accepted")
    # A common canonical row serializes competing sources, including when
    # neither has an accepted claim yet. Routes acquire this before claim locks.
    lock_subject(db, assertion.subject_type, assertion.subject_id)
    # record_assertion may have pending source-supersession updates. With
    # autoflush disabled, populate_existing below would discard those changes
    # while refreshing accepted flags. Persist them under the canonical lock
    # before reloading the selected set; the outer transaction still owns commit.
    db.flush()
    replaced: list[KnowledgeAssertion] = []
    if predicate_cardinality(
        assertion.predicate, object_type=assertion.object_type
    ) == "single":
        query = select(KnowledgeAssertion).where(
            KnowledgeAssertion.customer_id == assertion.customer_id,
            KnowledgeAssertion.site_id.is_not_distinct_from(assertion.site_id),
            KnowledgeAssertion.subject_type == assertion.subject_type,
            KnowledgeAssertion.predicate == assertion.predicate,
            KnowledgeAssertion.id != assertion.id,
            KnowledgeAssertion.is_accepted.is_(True),
        )
        if assertion.subject_id is not None:
            query = query.where(KnowledgeAssertion.subject_id == assertion.subject_id)
        else:
            query = query.where(
                KnowledgeAssertion.subject_id.is_(None),
                KnowledgeAssertion.data_source_id == assertion.data_source_id,
                KnowledgeAssertion.subject_external_id
                == assertion.subject_external_id,
            )
        # A bulk review may have loaded other sources before waiting for the
        # canonical lock. Refresh accepted flags so clearing them emits UPDATEs.
        replaced = list(db.scalars(query.execution_options(populate_existing=True)))
        for previous in replaced:
            previous.is_accepted = False
            previous.accepted_at = None
            previous.accepted_by_user_id = None
            # Acceptance replacement is not supersession of another source's
            # observation. Its freshness and source lineage remain independent.
            previous.acceptance_replaced_by_id = assertion.id
            if previous.truth_classification == "declared":
                previous.confirmation_status = "superseded"
        # Avoid a transient partial-unique-index violation when SQLAlchemy
        # batches the old and new rows in an unexpected order.
        if replaced:
            db.flush()
    assertion.is_accepted = True
    assertion.accepted_at = accepted_at or datetime.now(timezone.utc)
    assertion.accepted_by_user_id = user_id
    assertion.confirmation_status = "confirmed"
    return replaced
