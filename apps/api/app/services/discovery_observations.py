"""Coverage-aware discovery observation and absence reconciliation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Asset,
    DiscoveryRun,
    EntitySourceLink,
    KnowledgeAssertion,
    ReconciliationItem,
    RunObservedEntity,
)
from app.services.knowledge_assertions import confirm, record_assertion
from app.services.knowledge_changes import record_assertion_change
from app.services.reconciliation import create_item


@dataclass
class SnapshotReconciliation:
    baseline_run_id: uuid.UUID | None = None
    no_longer_observed_count: int = 0
    reobserved_count: int = 0
    items: list[ReconciliationItem] | None = None

    def __post_init__(self) -> None:
        if self.items is None:
            self.items = []


def default_coverage_key(
    customer_id: uuid.UUID, site_id: uuid.UUID | None
) -> str:
    return f"simulation:{customer_id}:{site_id or 'all-sites'}"


def record_observed_entity(
    db: Session,
    *,
    run: DiscoveryRun,
    entity_type: str,
    external_id: str,
    entity_id: uuid.UUID | None,
    evidence_record_id: uuid.UUID | None,
    observed_at: datetime,
) -> RunObservedEntity:
    row = RunObservedEntity(
        discovery_run_id=run.id,
        data_source_id=run.data_source_id,
        customer_id=run.customer_id,
        site_id=run.site_id,
        coverage_key=run.coverage_key,
        entity_type=entity_type,
        external_id=external_id,
        entity_id=entity_id,
        evidence_record_id=evidence_record_id,
        observed_at=observed_at,
    )
    db.add(row)
    return row


def _previous_complete_run(db: Session, run: DiscoveryRun) -> DiscoveryRun | None:
    return db.scalar(
        select(DiscoveryRun)
        .where(
            DiscoveryRun.id != run.id,
            DiscoveryRun.data_source_id == run.data_source_id,
            DiscoveryRun.customer_id == run.customer_id,
            DiscoveryRun.site_id == run.site_id,
            DiscoveryRun.coverage_key == run.coverage_key,
            DiscoveryRun.status == "completed",
            DiscoveryRun.is_complete_snapshot.is_(True),
            DiscoveryRun.completeness_status == "complete",
        )
        .order_by(DiscoveryRun.finished_at.desc(), DiscoveryRun.started_at.desc())
        .limit(1)
    )


def _current_observation_state(
    db: Session, *, run: DiscoveryRun, external_id: str
) -> KnowledgeAssertion | None:
    candidates = db.scalars(
        select(KnowledgeAssertion).where(
            KnowledgeAssertion.customer_id == run.customer_id,
            KnowledgeAssertion.site_id == run.site_id,
            KnowledgeAssertion.data_source_id == run.data_source_id,
            KnowledgeAssertion.subject_type == "asset",
            KnowledgeAssertion.subject_external_id == external_id,
            KnowledgeAssertion.predicate == "observation_state",
            KnowledgeAssertion.is_current.is_(True),
        )
    )
    return next(iter(candidates), None)


def _asset_link(db: Session, *, run: DiscoveryRun, external_id: str) -> EntitySourceLink | None:
    return db.scalar(
        select(EntitySourceLink).where(
            EntitySourceLink.data_source_id == run.data_source_id,
            EntitySourceLink.customer_id == run.customer_id,
            EntitySourceLink.site_id == run.site_id,
            EntitySourceLink.entity_type == "asset",
            EntitySourceLink.external_id == external_id,
        )
    )


def _resolve_reobservation(
    db: Session,
    *,
    run: DiscoveryRun,
    external_id: str,
    user_id: uuid.UUID,
    observed_at: datetime,
    result: SnapshotReconciliation,
) -> None:
    previous = _current_observation_state(db, run=run, external_id=external_id)
    if previous is None or not isinstance(previous.value_json, dict):
        return
    if previous.value_json.get("state") != "not_observed":
        return
    link = _asset_link(db, run=run, external_id=external_id)
    asset = db.get(Asset, link.entity_id) if link else None
    assertion, _ = record_assertion(
        db,
        customer_id=run.customer_id,
        site_id=run.site_id,
        subject_type="asset",
        subject_id=asset.id if asset else previous.subject_id,
        subject_external_id=external_id,
        predicate="observation_state",
        value={"state": "observed", "reobserved_in_run_id": run.id},
        data_source_id=run.data_source_id,
        discovery_run_id=run.id,
        observed_at=observed_at,
    )
    confirm(assertion)
    for item in db.scalars(
        select(ReconciliationItem)
        .join(KnowledgeAssertion, KnowledgeAssertion.id == ReconciliationItem.assertion_id)
        .where(
            ReconciliationItem.category == "no_longer_observed",
            ReconciliationItem.status.in_(("open", "deferred")),
            KnowledgeAssertion.data_source_id == run.data_source_id,
            KnowledgeAssertion.subject_external_id == external_id,
        )
    ):
        item.status = "accepted"
        item.decision_reason = "Automatically resolved because the entity was observed again"
        item.decided_by_user_id = user_id
        item.decided_at = observed_at
    record_assertion_change(
        db,
        assertion=assertion,
        change_type="entity_reobserved",
        entity_name=asset.name if asset else external_id,
        summary=f"{asset.name if asset else external_id} was observed again",
        actor_user_id=user_id,
        previous_value=previous.value_json,
        new_value=assertion.value_json,
    )
    result.reobserved_count += 1

    if asset is not None and asset.status in {"missing", "inactive"}:
        status_assertion, _ = record_assertion(
            db,
            customer_id=run.customer_id,
            site_id=run.site_id,
            subject_type="asset",
            subject_id=asset.id,
            subject_external_id=external_id,
            predicate="status",
            value="active",
            data_source_id=run.data_source_id,
            discovery_run_id=run.id,
            observed_at=observed_at,
        )
        item, created = create_item(
            db,
            assertion=status_assertion,
            category="changed",
            entity_type="asset",
            entity_id=asset.id,
            candidate_external_id=external_id,
            current_value={"field": "status", "value": asset.status},
            observed_value={"field": "status", "value": "active"},
            recommended_action="Restore asset to active",
        )
        if created:
            result.items.append(item)


def reconcile_complete_snapshot(
    db: Session,
    *,
    run: DiscoveryRun,
    user_id: uuid.UUID,
    observed_at: datetime | None = None,
) -> SnapshotReconciliation:
    """Compare one successful complete run to its matching complete baseline."""

    result = SnapshotReconciliation()
    if (
        run.status != "completed"
        or not run.is_complete_snapshot
        or run.completeness_status != "complete"
    ):
        return result
    observed_at = observed_at or datetime.now(timezone.utc)
    current_rows = list(
        db.scalars(
            select(RunObservedEntity).where(
                RunObservedEntity.discovery_run_id == run.id,
                RunObservedEntity.entity_type == "asset",
            )
        )
    )
    current_ids = {row.external_id for row in current_rows}
    for external_id in current_ids:
        _resolve_reobservation(
            db,
            run=run,
            external_id=external_id,
            user_id=user_id,
            observed_at=observed_at,
            result=result,
        )

    baseline = _previous_complete_run(db, run)
    if baseline is None:
        return result
    result.baseline_run_id = baseline.id
    baseline_rows = list(
        db.scalars(
            select(RunObservedEntity).where(
                RunObservedEntity.discovery_run_id == baseline.id,
                RunObservedEntity.entity_type == "asset",
            )
        )
    )
    for prior in baseline_rows:
        if prior.external_id in current_ids:
            continue
        existing_state = _current_observation_state(
            db, run=run, external_id=prior.external_id
        )
        if (
            existing_state is not None
            and isinstance(existing_state.value_json, dict)
            and existing_state.value_json.get("state") == "not_observed"
        ):
            continue
        link = _asset_link(db, run=run, external_id=prior.external_id)
        asset = db.get(Asset, link.entity_id) if link else None
        assertion, _ = record_assertion(
            db,
            customer_id=run.customer_id,
            site_id=run.site_id,
            subject_type="asset",
            subject_id=asset.id if asset else prior.entity_id,
            subject_external_id=prior.external_id,
            predicate="observation_state",
            value={
                "state": "not_observed",
                "baseline_run_id": baseline.id,
                "missing_since_run_id": run.id,
                "last_observed_at": prior.observed_at,
            },
            data_source_id=run.data_source_id,
            discovery_run_id=run.id,
            observed_at=observed_at,
        )
        item, created = create_item(
            db,
            assertion=assertion,
            category="no_longer_observed",
            entity_type="asset",
            entity_id=asset.id if asset else prior.entity_id,
            candidate_external_id=prior.external_id,
            current_value={
                "status": asset.status if asset else None,
                "last_observed_at": prior.observed_at,
                "baseline_run_id": baseline.id,
            },
            observed_value=assertion.value_json,
            recommended_action="Review whether this asset is missing, inactive, retired, or excepted",
        )
        if not created:
            continue
        result.items.append(item)
        result.no_longer_observed_count += 1
        record_assertion_change(
            db,
            assertion=assertion,
            item=item,
            change_type="entity_no_longer_observed",
            entity_name=asset.name if asset else prior.external_id,
            summary=f"{asset.name if asset else prior.external_id} was not observed in a complete snapshot",
            actor_user_id=user_id,
            previous_value={"state": "observed", "last_observed_at": prior.observed_at},
            new_value=assertion.value_json,
            metadata={"baseline_run_id": baseline.id},
        )
    return result
