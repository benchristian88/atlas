"""Create and decide reconciliation items without bypassing the operational view."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Asset,
    AssetInterface,
    AssetRelationship,
    AssetType,
    Customer,
    KnowledgeAssertion,
    Network,
    ReconciliationItem,
    RelationshipType,
    Site,
    User,
)
from app.services.entity_resolution import (
    AssetResolution,
    ensure_asset_link,
    resolve_asset_identity,
)
from app.services.knowledge_assertions import confirm, reject
from app.services.knowledge_changes import record_assertion_change
from app.utils.json_values import to_json_value


SAFE_ASSET_FIELDS = {
    "name",
    "asset_type",
    "hostname",
    "status",
    "vendor",
    "model",
    "ip_address",
    "description",
}


class RelationshipResolutionError(Exception):
    def __init__(self, payload: dict[str, Any]):
        super().__init__(payload["detail"])
        self.payload = payload


def _uuid_value(value: Any) -> uuid.UUID | None:
    if value is None or isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def create_item(
    db: Session,
    *,
    assertion: KnowledgeAssertion,
    category: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    current_value: Any,
    observed_value: Any,
    recommended_action: str,
    candidate_external_id: str | None = None,
) -> tuple[ReconciliationItem, bool]:
    existing = db.scalar(
        select(ReconciliationItem).where(
            ReconciliationItem.assertion_id == assertion.id,
            ReconciliationItem.status.in_(("open", "deferred")),
        )
    )
    if existing is not None:
        return existing, False
    item = ReconciliationItem(
        customer_id=assertion.customer_id,
        site_id=assertion.site_id,
        category=category,
        status="open",
        entity_type=entity_type,
        entity_id=entity_id,
        candidate_external_id=candidate_external_id,
        assertion_id=assertion.id,
        current_value_json=to_json_value(current_value),
        observed_value_json=to_json_value(observed_value),
        recommended_action=recommended_action,
    )
    db.add(item)
    db.flush()
    return item, True


def _active_asset_type(db: Session, key: str) -> None:
    asset_type = db.scalar(select(AssetType).where(AssetType.key == key))
    if asset_type is None or not asset_type.active:
        raise HTTPException(status_code=422, detail=f"Asset type '{key}' is not active")


def _create_interfaces(db: Session, asset: Asset, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        network = None
        network_name = row.get("network_name")
        if network_name:
            network = db.scalar(
                select(Network).where(
                    Network.customer_id == asset.customer_id,
                    Network.site_id == asset.site_id,
                    Network.name == network_name,
                )
            )
        db.add(
            AssetInterface(
                asset_id=asset.id,
                network_id=network.id if network else None,
                name=row["name"],
                ip_address=row.get("ip_address"),
                mac_address=row.get("mac_address"),
                is_primary=bool(row.get("is_primary")),
                notes=(None if network or not network_name else f"Observed network: {network_name}"),
            )
        )


def _assertion_for_item(db: Session, item: ReconciliationItem) -> KnowledgeAssertion:
    assertion = db.get(KnowledgeAssertion, item.assertion_id)
    if assertion is None:
        raise HTTPException(status_code=409, detail="The source assertion no longer exists")
    return assertion


def _attach_external_identity(
    db: Session,
    *,
    item: ReconciliationItem,
    assertion: KnowledgeAssertion,
    asset: Asset,
) -> None:
    if assertion.data_source_id is None or not item.candidate_external_id:
        raise HTTPException(status_code=409, detail="The discovered identity is incomplete")
    ensure_asset_link(
        db,
        data_source_id=assertion.data_source_id,
        asset=asset,
        external_id=item.candidate_external_id,
        external_type=(item.observed_value_json or {}).get("asset_type"),
        observed_at=assertion.last_observed_at,
    )
    for related_assertion in db.scalars(
        select(KnowledgeAssertion).where(
            KnowledgeAssertion.customer_id == item.customer_id,
            KnowledgeAssertion.site_id == item.site_id,
            KnowledgeAssertion.data_source_id == assertion.data_source_id,
            KnowledgeAssertion.subject_type == "asset",
            KnowledgeAssertion.subject_external_id == item.candidate_external_id,
            KnowledgeAssertion.is_current.is_(True),
        )
    ):
        related_assertion.subject_id = asset.id
    for object_assertion in db.scalars(
        select(KnowledgeAssertion).where(
            KnowledgeAssertion.customer_id == item.customer_id,
            KnowledgeAssertion.site_id == item.site_id,
            KnowledgeAssertion.data_source_id == assertion.data_source_id,
            KnowledgeAssertion.object_type == "asset",
            KnowledgeAssertion.object_external_id == item.candidate_external_id,
            KnowledgeAssertion.is_current.is_(True),
        )
    ):
        object_assertion.object_id = asset.id
    item.entity_id = asset.id


def _accept_new_asset(db: Session, item: ReconciliationItem) -> Asset:
    value = dict(item.observed_value_json or {})
    site = db.get(Site, item.site_id) if item.site_id else None
    customer = db.get(Customer, item.customer_id)
    if customer is None or site is None or site.customer_id != customer.id:
        raise HTTPException(status_code=409, detail="A valid customer and site are required")
    assertion = _assertion_for_item(db, item)
    if assertion.data_source_id is None or not item.candidate_external_id:
        raise HTTPException(status_code=409, detail="The discovered identity is incomplete")
    resolution = resolve_asset_identity(
        db,
        data_source_id=assertion.data_source_id,
        customer_id=item.customer_id,
        site_id=item.site_id,
        external_id=item.candidate_external_id,
        name=value.get("name"),
        asset_type=value.get("asset_type"),
        hostname=(value.get("facts") or {}).get("hostname"),
        observed_at=assertion.last_observed_at,
    )
    if resolution.asset is not None:
        _attach_external_identity(
            db, item=item, assertion=assertion, asset=resolution.asset
        )
        return resolution.asset
    if resolution.status == "possible_duplicate":
        raise HTTPException(
            status_code=409,
            detail="Multiple existing assets match; link the intended asset explicitly",
        )
    _active_asset_type(db, value["asset_type"])
    facts = value.get("facts") or {}
    asset = Asset(
        workspace_id=customer.workspace_id,
        customer_id=customer.id,
        site_id=site.id,
        source_integration_id=None,
        external_id=item.candidate_external_id,
        name=value["name"],
        asset_type=value["asset_type"],
        hostname=facts.get("hostname"),
        status=facts.get("status") or "active",
        vendor=facts.get("vendor"),
        model=facts.get("model"),
        ip_address=facts.get("ip_address"),
        description=facts.get("description"),
        source="discovery",
        metadata_={"knowledge_source": "reconciliation"},
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(asset)
    db.flush()
    _create_interfaces(db, asset, value.get("interfaces") or [])
    _attach_external_identity(db, item=item, assertion=assertion, asset=asset)
    for related in db.scalars(
        select(ReconciliationItem).where(
            ReconciliationItem.customer_id == item.customer_id,
            ReconciliationItem.site_id == item.site_id,
            ReconciliationItem.entity_type == "asset",
            ReconciliationItem.candidate_external_id == item.candidate_external_id,
            ReconciliationItem.entity_id.is_(None),
        )
    ):
        related.entity_id = asset.id
    return asset


def _accept_changed_fact(db: Session, item: ReconciliationItem) -> Asset:
    asset = db.get(Asset, item.entity_id) if item.entity_id else None
    if asset is None:
        raise HTTPException(status_code=409, detail="The target asset no longer exists")
    value = dict(item.observed_value_json or {})
    field = value.get("field")
    if field not in SAFE_ASSET_FIELDS:
        raise HTTPException(status_code=422, detail="This fact cannot be applied automatically")
    if field == "asset_type":
        _active_asset_type(db, value.get("value"))
    setattr(asset, field, value.get("value"))
    asset.last_seen_at = datetime.now(timezone.utc)
    return asset


def _accept_absence(
    db: Session,
    item: ReconciliationItem,
    *,
    disposition: str | None,
    reason: str | None,
    exception_review_at: datetime | None,
    actor_user_id: uuid.UUID,
) -> Asset:
    asset = db.get(Asset, item.entity_id) if item.entity_id else None
    if asset is None:
        raise HTTPException(status_code=409, detail="The target asset no longer exists")
    disposition = disposition or "mark_missing"
    status_by_disposition = {
        "mark_missing": "missing",
        "mark_inactive": "inactive",
        "mark_retired": "retired",
        "retire": "retired",
        "keep_active": asset.status,
        "exception": asset.status,
    }
    if disposition not in status_by_disposition:
        raise HTTPException(status_code=422, detail="Unsupported absence disposition")
    previous_status = asset.status
    asset.status = status_by_disposition[disposition]
    item.decision_reason = reason or {
        "mark_missing": "Marked missing after complete discovery snapshot",
        "mark_inactive": "Marked inactive after complete discovery snapshot",
        "mark_retired": "Retired after complete discovery snapshot",
        "retire": "Retired after complete discovery snapshot",
        "keep_active": "Kept active despite not being observed",
        "exception": "Exception recorded for the missing observation",
    }[disposition]
    if disposition == "exception":
        item.status = "exception"
        current = dict(item.current_value_json or {})
        current["exception_review_at"] = exception_review_at
        current["disposition"] = disposition
        item.current_value_json = to_json_value(current)
    assertion = _assertion_for_item(db, item)
    record_assertion_change(
        db,
        assertion=assertion,
        item=item,
        change_type=("exception_recorded" if disposition == "exception" else "lifecycle_changed"),
        entity_name=asset.name,
        summary=(
            f"Recorded a no-longer-observed exception for {asset.name}"
            if disposition == "exception"
            else f"Kept {asset.name} active after absence review"
            if disposition == "keep_active"
            else f"{asset.name}: {previous_status} → {asset.status}"
        ),
        actor_user_id=actor_user_id,
        previous_value=previous_status,
        new_value=asset.status,
        metadata={"disposition": disposition, "exception_review_at": exception_review_at},
        occurred_at=datetime.now(timezone.utc),
    )
    return asset


def _pending_resolution_status(
    db: Session,
    *,
    item: ReconciliationItem,
    assertion: KnowledgeAssertion,
    external_id: str,
) -> str:
    pending = db.scalar(
        select(ReconciliationItem)
        .join(KnowledgeAssertion, KnowledgeAssertion.id == ReconciliationItem.assertion_id)
        .where(
            ReconciliationItem.customer_id == item.customer_id,
            ReconciliationItem.site_id == item.site_id,
            ReconciliationItem.entity_type == "asset",
            ReconciliationItem.candidate_external_id == external_id,
            ReconciliationItem.status.in_(("open", "deferred")),
            KnowledgeAssertion.data_source_id == assertion.data_source_id,
        )
    )
    if pending is None:
        return "unresolved"
    if pending.category == "possible_duplicate":
        return "possible_duplicate"
    return "pending_asset_acceptance"


def relationship_resolution(
    db: Session, item: ReconciliationItem, *, persist_links: bool = True
) -> dict[str, Any]:
    assertion = _assertion_for_item(db, item)
    value = dict(item.observed_value_json or {})
    source_external_id = value.get("source_external_id")
    target_external_id = value.get("target_external_id")
    if assertion.data_source_id is None or not source_external_id or not target_external_id:
        return {
            **value,
            "source_external_id": source_external_id,
            "target_external_id": target_external_id,
            "source_resolution_status": "unresolved",
            "target_resolution_status": "unresolved",
            "blocked_reason": "Relationship assertion is missing source identity information",
            "current_relationship_id": None,
        }

    def resolve(external_id: str) -> AssetResolution:
        result = resolve_asset_identity(
            db,
            data_source_id=assertion.data_source_id,
            customer_id=item.customer_id,
            site_id=item.site_id,
            external_id=external_id,
            allow_external_name_hint=True,
            observed_at=assertion.last_observed_at,
            persist_link=persist_links,
        )
        if result.asset is None and result.status == "unresolved":
            result.status = _pending_resolution_status(
                db,
                item=item,
                assertion=assertion,
                external_id=external_id,
            )
        return result

    source = resolve(source_external_id)
    target = resolve(target_external_id)
    current = None
    if source.asset is not None and target.asset is not None:
        current = db.scalar(
            select(AssetRelationship).where(
                AssetRelationship.source_asset_id == source.asset.id,
                AssetRelationship.target_asset_id == target.asset.id,
                AssetRelationship.relationship_type == value.get("relationship_type"),
            )
        )
        if current is None:
            competing = list(
                db.scalars(
                    select(AssetRelationship).where(
                        AssetRelationship.source_asset_id == source.asset.id,
                        AssetRelationship.target_asset_id == target.asset.id,
                    )
                )
            )
            if len(competing) == 1:
                current = competing[0]
        assertion.subject_id = source.asset.id
        assertion.object_id = target.asset.id
    unresolved = []
    if source.asset is None:
        unresolved.append(f"source {source_external_id} ({source.status})")
    if target.asset is None:
        unresolved.append(f"target {target_external_id} ({target.status})")
    result = {
        **value,
        "source_external_id": source_external_id,
        "target_external_id": target_external_id,
        "resolved_source_asset_id": source.asset.id if source.asset else None,
        "resolved_target_asset_id": target.asset.id if target.asset else None,
        "resolved_source_name": source.asset.name if source.asset else None,
        "resolved_target_name": target.asset.name if target.asset else None,
        "source_resolution_status": source.status,
        "target_resolution_status": target.status,
        "blocked_reason": (
            f"Unresolved relationship endpoint: {', '.join(unresolved)}"
            if unresolved
            else None
        ),
        "current_relationship_id": current.id if current else None,
    }
    safe_result = to_json_value(result)
    item.observed_value_json = safe_result
    item.current_value_json = to_json_value(
        {
            "relationship_id": current.id,
            "source_asset_id": source.asset.id,
            "source_name": source.asset.name,
            "relationship_type": current.relationship_type,
            "target_asset_id": target.asset.id,
            "target_name": target.asset.name,
        }
        if current
        else "No current relationship"
    )
    return safe_result


def _accept_relationship(db: Session, item: ReconciliationItem) -> AssetRelationship:
    value = relationship_resolution(db, item)
    source = db.get(Asset, _uuid_value(value.get("resolved_source_asset_id")))
    target = db.get(Asset, _uuid_value(value.get("resolved_target_asset_id")))
    if source is None or target is None:
        raise RelationshipResolutionError(
            {
                "detail": "Relationship endpoints are unresolved",
                "source_status": value.get("source_resolution_status"),
                "target_status": value.get("target_resolution_status"),
                "source_external_id": value.get("source_external_id"),
                "target_external_id": value.get("target_external_id"),
                "blocked_reason": value.get("blocked_reason"),
            }
        )
    key = value.get("relationship_type")
    relationship_type = db.scalar(select(RelationshipType).where(RelationshipType.key == key))
    if relationship_type is None or not relationship_type.active:
        raise HTTPException(status_code=422, detail=f"Relationship type '{key}' is not active")
    allowed_sources = relationship_type.allowed_source_asset_type_keys or []
    allowed_targets = relationship_type.allowed_target_asset_type_keys or []
    if allowed_sources and source.asset_type not in allowed_sources:
        raise HTTPException(status_code=422, detail="Relationship type does not allow the source asset type")
    if allowed_targets and target.asset_type not in allowed_targets:
        raise HTTPException(status_code=422, detail="Relationship type does not allow the target asset type")
    existing = db.scalar(
        select(AssetRelationship).where(
            AssetRelationship.source_asset_id == source.id,
            AssetRelationship.target_asset_id == target.id,
            AssetRelationship.relationship_type == key,
        )
    )
    if existing is not None:
        item.entity_id = existing.id
        return existing
    current_relationship_id = _uuid_value(value.get("current_relationship_id"))
    if item.category == "contradiction" and current_relationship_id:
        current = db.get(AssetRelationship, current_relationship_id)
        if (
            current is not None
            and current.source_asset_id == source.id
            and current.target_asset_id == target.id
        ):
            current.relationship_type = key
            current.notes = "Updated from accepted discovered knowledge"
            item.entity_id = current.id
            return current
    relationship = AssetRelationship(
        source_asset_id=source.id,
        target_asset_id=target.id,
        customer_id=source.customer_id,
        site_id=source.site_id,
        relationship_type=key,
        legacy_cross_context=False,
        notes="Accepted from discovered knowledge",
        metadata_={"knowledge_source": "reconciliation"},
    )
    db.add(relationship)
    db.flush()
    item.entity_id = relationship.id
    return relationship


def accept_item(
    db: Session,
    item: ReconciliationItem,
    user: User,
    *,
    disposition: str | None = None,
    reason: str | None = None,
    exception_review_at: datetime | None = None,
) -> object:
    if item.status not in {"open", "deferred"}:
        raise HTTPException(status_code=409, detail="This item has already been decided")
    assertion = _assertion_for_item(db, item)
    previous_value = item.current_value_json
    if item.entity_type == "asset" and item.category in {"newly_discovered", "possible_duplicate"}:
        result = _accept_new_asset(db, item)
    elif item.entity_type == "asset" and item.category in {"changed", "contradiction"}:
        result = _accept_changed_fact(db, item)
    elif item.entity_type == "asset_relationship":
        result = _accept_relationship(db, item)
    elif item.entity_type == "asset" and item.category == "no_longer_observed":
        result = _accept_absence(
            db,
            item,
            disposition=disposition,
            reason=reason,
            exception_review_at=exception_review_at,
            actor_user_id=user.id,
        )
    else:
        raise HTTPException(status_code=422, detail="This item cannot be applied automatically")
    if item.status != "exception":
        item.status = "accepted"
    item.decision_reason = item.decision_reason or reason
    item.decided_by_user_id = user.id
    item.decided_at = datetime.now(timezone.utc)
    confirm(assertion)
    if item.category != "no_longer_observed":
        name = getattr(result, "name", None) or item.candidate_external_id or item.entity_type
        change_type = (
            "relationship_added"
            if item.entity_type == "asset_relationship"
            else "entity_accepted"
            if item.category in {"newly_discovered", "possible_duplicate"}
            else "fact_changed"
        )
        record_assertion_change(
            db,
            assertion=assertion,
            item=item,
            change_type=change_type,
            entity_name=name,
            summary=f"Accepted {item.category.replace('_', ' ')} for {name}",
            actor_user_id=user.id,
            previous_value=previous_value,
            new_value=item.observed_value_json,
            occurred_at=item.decided_at,
        )
    return result


def link_item_to_asset(
    db: Session,
    *,
    item: ReconciliationItem,
    asset: Asset,
    user: User,
    reason: str | None,
) -> Asset:
    if item.status not in {"open", "deferred"}:
        raise HTTPException(status_code=409, detail="This item has already been decided")
    if item.entity_type != "asset" or item.category not in {
        "newly_discovered",
        "possible_duplicate",
    }:
        raise HTTPException(status_code=422, detail="This item cannot be linked to an asset")
    if asset.customer_id != item.customer_id or asset.site_id != item.site_id:
        raise HTTPException(status_code=422, detail="The asset must be in the same customer and site")
    assertion = _assertion_for_item(db, item)
    _attach_external_identity(db, item=item, assertion=assertion, asset=asset)
    item.status = "accepted"
    item.decision_reason = reason or "Linked discovered identity to existing asset"
    item.decided_by_user_id = user.id
    item.decided_at = datetime.now(timezone.utc)
    confirm(assertion)
    record_assertion_change(
        db,
        assertion=assertion,
        item=item,
        change_type="source_linked",
        entity_name=asset.name,
        summary=f"Linked discovered identity {item.candidate_external_id} to {asset.name}",
        actor_user_id=user.id,
        previous_value=None,
        new_value={"asset_id": asset.id, "external_id": item.candidate_external_id},
        occurred_at=item.decided_at,
    )
    for related in db.scalars(
        select(ReconciliationItem).where(
            ReconciliationItem.customer_id == item.customer_id,
            ReconciliationItem.site_id == item.site_id,
            ReconciliationItem.entity_type == "asset_relationship",
            ReconciliationItem.status.in_(("open", "deferred")),
        )
    ):
        relationship_resolution(db, related)
    return asset


def reject_item(db: Session, item: ReconciliationItem, user: User, reason: str | None) -> None:
    if item.status not in {"open", "deferred"}:
        raise HTTPException(status_code=409, detail="This item has already been decided")
    assertion = db.get(KnowledgeAssertion, item.assertion_id)
    if assertion is not None:
        reject(assertion)
    item.status = "rejected"
    item.decision_reason = reason
    item.decided_by_user_id = user.id
    item.decided_at = datetime.now(timezone.utc)
    if assertion is not None:
        asset = db.get(Asset, item.entity_id) if item.entity_type == "asset" and item.entity_id else None
        record_assertion_change(
            db,
            assertion=assertion,
            item=item,
            change_type="assertion_rejected",
            entity_name=asset.name if asset else item.candidate_external_id or item.entity_type,
            summary=f"Rejected {item.category.replace('_', ' ')}",
            actor_user_id=user.id,
            previous_value=item.observed_value_json,
            new_value=None,
            metadata={"reason": reason},
            occurred_at=item.decided_at,
        )


def defer_item(db: Session, item: ReconciliationItem, user: User, reason: str | None) -> None:
    if item.status != "open":
        raise HTTPException(status_code=409, detail="Only open items can be deferred")
    item.status = "deferred"
    item.decision_reason = reason
    item.decided_by_user_id = user.id
    item.decided_at = datetime.now(timezone.utc)
