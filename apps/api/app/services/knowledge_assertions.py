"""Immutable, evidence-backed knowledge assertion helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KnowledgeAssertion


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
        KnowledgeAssertion.is_current.is_(True),
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
            KnowledgeAssertion.is_current.is_(True),
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
) -> tuple[KnowledgeAssertion, bool]:
    """Record a current assertion, coalescing identical observations from one source."""

    observed_at = observed_at or datetime.now(timezone.utc)
    current = list(
        db.scalars(
            select(KnowledgeAssertion).where(
                KnowledgeAssertion.customer_id == customer_id,
                KnowledgeAssertion.site_id == site_id,
                KnowledgeAssertion.subject_type == subject_type,
                KnowledgeAssertion.subject_id == subject_id,
                KnowledgeAssertion.subject_external_id == subject_external_id,
                KnowledgeAssertion.predicate == predicate,
                KnowledgeAssertion.data_source_id == data_source_id,
                KnowledgeAssertion.is_current.is_(True),
            )
        )
    )
    for assertion in current:
        if _same_claim(assertion, value, object_external_id):
            assertion.last_observed_at = observed_at
            assertion.discovery_run_id = discovery_run_id
            assertion.evidence_record_id = evidence_record_id
            assertion.confidence = Decimal(str(confidence))
            return assertion, False

    assertion = KnowledgeAssertion(
        customer_id=customer_id,
        site_id=site_id,
        subject_type=subject_type,
        subject_id=subject_id,
        subject_external_id=subject_external_id,
        predicate=predicate,
        value_json=value,
        object_type=object_type,
        object_id=object_id,
        object_external_id=object_external_id,
        truth_classification=truth_classification,
        confirmation_status="unreviewed",
        data_source_id=data_source_id,
        discovery_run_id=discovery_run_id,
        evidence_record_id=evidence_record_id,
        confidence=Decimal(str(confidence)),
        first_observed_at=observed_at,
        last_observed_at=observed_at,
        is_current=True,
    )
    db.add(assertion)
    db.flush()

    for previous in current:
        mark_superseded(previous, assertion, observed_at)

    conflicting = db.scalar(
        select(KnowledgeAssertion).where(
            KnowledgeAssertion.customer_id == customer_id,
            KnowledgeAssertion.site_id == site_id,
            KnowledgeAssertion.subject_type == subject_type,
            KnowledgeAssertion.subject_id == subject_id,
            KnowledgeAssertion.subject_external_id == subject_external_id,
            KnowledgeAssertion.predicate == predicate,
            KnowledgeAssertion.data_source_id != data_source_id,
            KnowledgeAssertion.is_current.is_(True),
        )
    )
    if conflicting is not None and not _same_claim(conflicting, value, object_external_id):
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
