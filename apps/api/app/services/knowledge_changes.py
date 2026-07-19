"""Central persistence boundary for user-meaningful knowledge changes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import KnowledgeAssertion, KnowledgeChange, ReconciliationItem
from app.utils.json_values import to_json_value


def record_change(
    db: Session,
    *,
    customer_id: uuid.UUID,
    site_id: uuid.UUID | None,
    change_type: str,
    entity_type: str,
    entity_name: str,
    summary: str,
    entity_id: uuid.UUID | None = None,
    predicate: str | None = None,
    previous_value: Any = None,
    new_value: Any = None,
    truth_classification: str | None = None,
    data_source_id: uuid.UUID | None = None,
    discovery_run_id: uuid.UUID | None = None,
    assertion_id: uuid.UUID | None = None,
    reconciliation_item_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> KnowledgeChange:
    """Create a ledger entry without committing the surrounding transaction."""

    change = KnowledgeChange(
        customer_id=customer_id,
        site_id=site_id,
        change_type=change_type,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name_snapshot=entity_name,
        predicate=predicate,
        previous_value_json=to_json_value(previous_value),
        new_value_json=to_json_value(new_value),
        truth_classification=truth_classification,
        data_source_id=data_source_id,
        discovery_run_id=discovery_run_id,
        assertion_id=assertion_id,
        reconciliation_item_id=reconciliation_item_id,
        actor_user_id=actor_user_id,
        summary=summary,
        occurred_at=occurred_at or datetime.now(timezone.utc),
        metadata_json=to_json_value(metadata),
    )
    db.add(change)
    return change


def record_assertion_change(
    db: Session,
    *,
    assertion: KnowledgeAssertion,
    change_type: str,
    entity_name: str,
    summary: str,
    item: ReconciliationItem | None = None,
    actor_user_id: uuid.UUID | None = None,
    previous_value: Any = None,
    new_value: Any = None,
    metadata: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> KnowledgeChange:
    return record_change(
        db,
        customer_id=assertion.customer_id,
        site_id=assertion.site_id,
        change_type=change_type,
        entity_type=(item.entity_type if item else assertion.subject_type),
        entity_id=(item.entity_id if item else assertion.subject_id),
        entity_name=entity_name,
        predicate=assertion.predicate,
        previous_value=previous_value,
        new_value=(assertion.value_json if new_value is None else new_value),
        truth_classification=assertion.truth_classification,
        data_source_id=assertion.data_source_id,
        discovery_run_id=assertion.discovery_run_id,
        assertion_id=assertion.id,
        reconciliation_item_id=item.id if item else None,
        actor_user_id=actor_user_id,
        summary=summary,
        occurred_at=occurred_at or assertion.last_observed_at,
        metadata=metadata,
    )
