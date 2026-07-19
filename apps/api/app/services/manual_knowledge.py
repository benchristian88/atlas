"""Turn manual asset declarations into accepted, auditable knowledge."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, KnowledgeAssertion
from app.services.data_sources import manual_inventory_source
from app.services.knowledge_assertions import accept_assertion, record_assertion
from app.services.knowledge_changes import record_assertion_change
from app.services.reconciliation import create_item
from app.utils.json_values import to_json_value

MANUAL_ASSET_KNOWLEDGE_FIELDS = (
    "name",
    "asset_type",
    "hostname",
    "status",
    "vendor",
    "model",
    "ip_address",
    "description",
)


def _active_observations(
    db: Session, *, asset: Asset, predicate: str, manual_source_id: uuid.UUID
) -> list[KnowledgeAssertion]:
    rows = db.scalars(
        select(KnowledgeAssertion).where(
            KnowledgeAssertion.subject_type == "asset",
            KnowledgeAssertion.subject_id == asset.id,
            KnowledgeAssertion.predicate == predicate,
            KnowledgeAssertion.data_source_id != manual_source_id,
            KnowledgeAssertion.is_source_current.is_(True),
            KnowledgeAssertion.retracted_at.is_(None),
        )
    )
    return [
        row
        for row in rows
        if row.truth_classification != "declared"
        and row.confirmation_status not in {"rejected", "superseded"}
    ]


def declare_asset_changes(
    db: Session,
    *,
    asset: Asset,
    previous_values: dict[str, Any],
    actor_user_id: uuid.UUID | None,
    occurred_at: datetime | None = None,
) -> list[KnowledgeAssertion]:
    """Persist changed manual fields as accepted declared assertions.

    The caller owns the transaction. Unchanged values are ignored, preventing
    duplicate assertions and timeline noise.
    """

    occurred_at = occurred_at or datetime.now(timezone.utc)
    source = manual_inventory_source(db, asset.customer_id, asset.site_id)
    declared: list[KnowledgeAssertion] = []
    for predicate in MANUAL_ASSET_KNOWLEDGE_FIELDS:
        if predicate not in previous_values:
            continue
        previous = to_json_value(previous_values[predicate])
        value = to_json_value(getattr(asset, predicate))
        if previous == value:
            continue
        assertion, _ = record_assertion(
            db,
            customer_id=asset.customer_id,
            site_id=asset.site_id,
            subject_type="asset",
            subject_id=asset.id,
            predicate=predicate,
            value=value,
            truth_classification="declared",
            data_source_id=source.id,
            observed_at=occurred_at,
        )
        accept_assertion(
            db,
            assertion,
            user_id=actor_user_id,
            accepted_at=occurred_at,
        )
        record_assertion_change(
            db,
            assertion=assertion,
            change_type="fact_changed",
            entity_name=asset.name,
            summary=f"Declared {predicate.replace('_', ' ')} for {asset.name}",
            actor_user_id=actor_user_id,
            previous_value=previous,
            new_value=value,
            occurred_at=occurred_at,
            metadata={"origin": "manual_asset_edit", "accepted": True},
        )
        for observed in _active_observations(
            db,
            asset=asset,
            predicate=predicate,
            manual_source_id=source.id,
        ):
            if to_json_value(observed.value_json) == value:
                continue
            create_item(
                db,
                assertion=observed,
                category="contradiction",
                entity_type="asset",
                entity_id=asset.id,
                current_value={"field": predicate, "value": value},
                observed_value={
                    "field": predicate,
                    "value": to_json_value(observed.value_json),
                },
                recommended_action="Review discovered value",
                candidate_external_id=observed.subject_external_id,
            )
        declared.append(assertion)
    return declared
