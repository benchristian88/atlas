"""Safety checks and lifecycle mutations for discovery provenance."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    DataSource,
    DiscoveryRun,
    EntitySourceLink,
    EvidenceRecord,
    KnowledgeAssertion,
    ReconciliationItem,
    User,
)
from app.utils.json_values import to_json_value

ACCEPTED_RECONCILIATION_STATUSES = ("accepted", "merged", "exception")
DELETABLE_ASSERTION_STATUSES = ("unreviewed", "rejected", "superseded")
DELETABLE_RUN_SOURCE_TYPES = ("simulated_discovery", "manual")
ARCHIVABLE_RUN_STATUSES = ("completed", "failed", "cancelled")


@dataclass(frozen=True)
class DeletionSafety:
    allowed: bool
    blocking_reasons: tuple[str, ...] = ()
    counts: dict[str, int] = field(default_factory=dict)
    identifiers: dict[str, uuid.UUID | str | None] = field(default_factory=dict)
    recommended_alternative: str | None = None

    def as_dict(self) -> dict:
        return to_json_value({
            "allowed": self.allowed,
            "reasons": list(self.blocking_reasons),
            "blocking_reasons": list(self.blocking_reasons),
            "counts": self.counts,
            "identifiers": self.identifiers,
            "recommended_alternative": self.recommended_alternative,
        })

    def conflict_payload(self, detail: str) -> dict:
        return to_json_value({
            "detail": detail,
            **self.counts,
            "reasons": list(self.blocking_reasons),
            "blocking_reasons": list(self.blocking_reasons),
            "identifiers": self.identifiers,
            "recommended_action": self.recommended_alternative,
        })


class UnsafeDeletionError(Exception):
    def __init__(self, safety: DeletionSafety, detail: str):
        super().__init__(detail)
        self.safety = safety
        self.detail = detail


class ProvenanceGapConfirmationRequired(Exception):
    def __init__(self):
        super().__init__("Retraction would leave accepted operational knowledge without current provenance")


def _count(db: Session, statement) -> int:
    return int(db.scalar(statement) or 0)


def can_delete_discovery_run(db: Session, run: DiscoveryRun) -> DeletionSafety:
    assertion_ids = select(KnowledgeAssertion.id).where(
        KnowledgeAssertion.discovery_run_id == run.id
    )
    evidence_ids = select(EvidenceRecord.id).where(
        EvidenceRecord.discovery_run_id == run.id
    )
    confirmed_assertions = _count(
        db,
        select(func.count()).select_from(KnowledgeAssertion).where(
            KnowledgeAssertion.discovery_run_id == run.id,
            KnowledgeAssertion.confirmation_status == "confirmed",
        ),
    )
    accepted_items = _count(
        db,
        select(func.count()).select_from(ReconciliationItem).where(
            ReconciliationItem.assertion_id.in_(assertion_ids),
            ReconciliationItem.status.in_(ACCEPTED_RECONCILIATION_STATUSES),
        ),
    )
    later_evidence_dependencies = _count(
        db,
        select(func.count()).select_from(KnowledgeAssertion).where(
            KnowledgeAssertion.evidence_record_id.in_(evidence_ids),
            or_(
                KnowledgeAssertion.discovery_run_id.is_(None),
                KnowledgeAssertion.discovery_run_id != run.id,
            ),
        ),
    )
    assertion_history_dependencies = _count(
        db,
        select(func.count()).select_from(KnowledgeAssertion).where(
            KnowledgeAssertion.discovery_run_id != run.id,
            KnowledgeAssertion.superseded_by_id.in_(assertion_ids),
        ),
    )

    linked_entity_ids = set(
        db.scalars(
            select(ReconciliationItem.entity_id).where(
                ReconciliationItem.assertion_id.in_(assertion_ids),
                ReconciliationItem.status.in_(ACCEPTED_RECONCILIATION_STATUSES),
                ReconciliationItem.entity_id.is_not(None),
            )
        )
    )
    linked_entity_ids.update(
        value
        for value in db.scalars(
            select(KnowledgeAssertion.subject_id).where(
                KnowledgeAssertion.discovery_run_id == run.id,
                KnowledgeAssertion.confirmation_status == "confirmed",
                KnowledgeAssertion.subject_id.is_not(None),
            )
        )
        if value is not None
    )
    linked_entity_ids.update(
        value
        for value in db.scalars(
            select(KnowledgeAssertion.object_id).where(
                KnowledgeAssertion.discovery_run_id == run.id,
                KnowledgeAssertion.confirmation_status == "confirmed",
                KnowledgeAssertion.object_id.is_not(None),
            )
        )
        if value is not None
    )
    external_ids = set(
        value
        for value in db.scalars(
            select(KnowledgeAssertion.subject_external_id).where(
                KnowledgeAssertion.discovery_run_id == run.id,
                KnowledgeAssertion.subject_external_id.is_not(None),
            )
        )
        if value
    )
    if run.data_source_id is not None and external_ids:
        linked_entity_ids.update(
            db.scalars(
                select(EntitySourceLink.entity_id).where(
                    EntitySourceLink.data_source_id == run.data_source_id,
                    EntitySourceLink.external_id.in_(external_ids),
                )
            )
        )

    source = db.get(DataSource, run.data_source_id) if run.data_source_id else None
    explicitly_deletable = bool(
        source and source.source_type in DELETABLE_RUN_SOURCE_TYPES
    )
    later_dependencies = later_evidence_dependencies + assertion_history_dependencies
    counts = {
        "confirmed_assertions": confirmed_assertions,
        "accepted_reconciliation_items": accepted_items,
        "linked_entities": len(linked_entity_ids),
        "later_dependencies": later_dependencies,
    }
    reasons = []
    if not explicitly_deletable:
        reasons.append("Only simulated or manual discovery runs can be deleted")
    if confirmed_assertions:
        reasons.append("Confirmed assertions depend on this run")
    if accepted_items:
        reasons.append("Accepted reconciliation decisions depend on this run")
    if linked_entity_ids:
        reasons.append("The run identifies operational Atlas entities")
    if later_dependencies:
        reasons.append("Later provenance history depends on this run")
    return DeletionSafety(
        allowed=not reasons,
        blocking_reasons=tuple(reasons),
        counts=counts,
        identifiers={"discovery_run_id": run.id},
        recommended_alternative="archive" if reasons else None,
    )


def delete_discovery_run(db: Session, run: DiscoveryRun) -> None:
    safety = can_delete_discovery_run(db, run)
    if not safety.allowed:
        raise UnsafeDeletionError(
            safety,
            "Discovery run cannot be deleted because it supports accepted knowledge",
        )
    assertion_ids = select(KnowledgeAssertion.id).where(
        KnowledgeAssertion.discovery_run_id == run.id
    )
    db.execute(
        delete(ReconciliationItem).where(
            ReconciliationItem.assertion_id.in_(assertion_ids)
        )
    )
    db.execute(
        delete(KnowledgeAssertion).where(
            KnowledgeAssertion.discovery_run_id == run.id
        )
    )
    db.execute(
        delete(EvidenceRecord).where(EvidenceRecord.discovery_run_id == run.id)
    )
    db.delete(run)


def archive_discovery_run(
    run: DiscoveryRun, *, user: User, reason: str
) -> None:
    if run.status not in ARCHIVABLE_RUN_STATUSES:
        raise ValueError("Only completed, failed, or cancelled discovery runs can be archived")
    if run.archived_at is not None:
        raise ValueError("Discovery run is already archived")
    run.archived_at = datetime.now(timezone.utc)
    run.archived_by_user_id = user.id
    run.archive_reason = reason


def restore_discovery_run(run: DiscoveryRun) -> None:
    if run.archived_at is None:
        raise ValueError("Discovery run is not archived")
    run.archived_at = None
    run.archived_by_user_id = None
    run.archive_reason = None


def assertion_has_provenance_gap(db: Session, assertion: KnowledgeAssertion) -> bool:
    if assertion.confirmation_status != "confirmed":
        return False
    if assertion.subject_id is None and assertion.object_id is None:
        return False
    candidates = db.scalars(
        select(KnowledgeAssertion).where(
            KnowledgeAssertion.id != assertion.id,
            KnowledgeAssertion.customer_id == assertion.customer_id,
            KnowledgeAssertion.site_id == assertion.site_id,
            KnowledgeAssertion.subject_type == assertion.subject_type,
            KnowledgeAssertion.subject_id == assertion.subject_id,
            KnowledgeAssertion.predicate == assertion.predicate,
            KnowledgeAssertion.confirmation_status == "confirmed",
            KnowledgeAssertion.retracted_at.is_(None),
            KnowledgeAssertion.is_current.is_(True),
        )
    )
    for candidate in candidates:
        if (
            candidate.value_json == assertion.value_json
            and candidate.object_type == assertion.object_type
            and candidate.object_id == assertion.object_id
            and candidate.object_external_id == assertion.object_external_id
        ):
            return False
    return True


def can_delete_assertion(db: Session, assertion: KnowledgeAssertion) -> DeletionSafety:
    accepted_items = _count(
        db,
        select(func.count()).select_from(ReconciliationItem).where(
            ReconciliationItem.assertion_id == assertion.id,
            ReconciliationItem.status.in_(ACCEPTED_RECONCILIATION_STATUSES),
        ),
    )
    history_references = _count(
        db,
        select(func.count()).select_from(KnowledgeAssertion).where(
            KnowledgeAssertion.superseded_by_id == assertion.id
        ),
    )
    linked_entities = 0
    if (
        assertion.data_source_id is not None
        and assertion.subject_external_id
        and assertion.subject_id is not None
    ):
        linked_entities = _count(
            db,
            select(func.count()).select_from(EntitySourceLink).where(
                EntitySourceLink.data_source_id == assertion.data_source_id,
                EntitySourceLink.external_id == assertion.subject_external_id,
                EntitySourceLink.entity_id == assertion.subject_id,
            ),
        )
    counts = {
        "accepted_reconciliation_items": accepted_items,
        "linked_entities": linked_entities,
        "history_references": history_references,
    }
    reasons = []
    if assertion.confirmation_status not in DELETABLE_ASSERTION_STATUSES:
        reasons.append(
            "Only unreviewed, rejected, or superseded assertions can be deleted"
        )
    if accepted_items:
        reasons.append("An accepted reconciliation decision depends on this assertion")
    if linked_entities:
        reasons.append("The assertion identifies an operational Atlas entity")
    if history_references:
        reasons.append("Other assertion history references this assertion")
    return DeletionSafety(
        allowed=not reasons,
        blocking_reasons=tuple(reasons),
        counts=counts,
        identifiers={
            "assertion_id": assertion.id,
            "discovery_run_id": assertion.discovery_run_id,
            "evidence_record_id": assertion.evidence_record_id,
        },
        recommended_alternative="retract" if reasons else None,
    )


def delete_assertion(db: Session, assertion: KnowledgeAssertion) -> None:
    safety = can_delete_assertion(db, assertion)
    if not safety.allowed:
        raise UnsafeDeletionError(
            safety,
            "Assertion cannot be deleted because it supports accepted knowledge",
        )
    db.execute(
        delete(ReconciliationItem).where(
            ReconciliationItem.assertion_id == assertion.id
        )
    )
    db.delete(assertion)


def retract_assertion(
    db: Session,
    assertion: KnowledgeAssertion,
    *,
    user: User,
    reason: str,
    confirm_provenance_gap: bool,
) -> bool:
    if assertion.retracted_at is not None:
        raise ValueError("Assertion is already retracted")
    provenance_gap = assertion_has_provenance_gap(db, assertion)
    if provenance_gap and not confirm_provenance_gap:
        raise ProvenanceGapConfirmationRequired()
    now = datetime.now(timezone.utc)
    assertion.retracted_at = now
    assertion.retracted_by_user_id = user.id
    assertion.retraction_reason = reason
    assertion.is_current = False
    assertion.valid_to = assertion.valid_to or now
    return provenance_gap
