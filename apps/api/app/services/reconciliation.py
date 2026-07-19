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
from app.services.knowledge_assertions import confirm, reject


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


def find_asset(
    db: Session,
    *,
    customer_id: uuid.UUID,
    site_id: uuid.UUID | None,
    external_id: str | None,
    name: str | None = None,
    asset_type: str | None = None,
) -> Asset | None:
    if site_id is None:
        return None
    if external_id:
        asset = db.scalar(
            select(Asset).where(
                Asset.customer_id == customer_id,
                Asset.site_id == site_id,
                Asset.external_id == external_id,
            )
        )
        if asset is not None:
            return asset
        inferred_name = external_id.rsplit(":", 1)[-1]
        matches = list(
            db.scalars(
                select(Asset).where(
                    Asset.customer_id == customer_id,
                    Asset.site_id == site_id,
                    Asset.name == inferred_name,
                )
            )
        )
        if len(matches) == 1:
            return matches[0]
    if name and asset_type:
        return db.scalar(
            select(Asset).where(
                Asset.customer_id == customer_id,
                Asset.site_id == site_id,
                Asset.name == name,
                Asset.asset_type == asset_type,
            )
        )
    return None


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
        current_value_json=current_value,
        observed_value_json=observed_value,
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


def _accept_new_asset(db: Session, item: ReconciliationItem) -> Asset:
    value = dict(item.observed_value_json or {})
    site = db.get(Site, item.site_id) if item.site_id else None
    customer = db.get(Customer, item.customer_id)
    if customer is None or site is None or site.customer_id != customer.id:
        raise HTTPException(status_code=409, detail="A valid customer and site are required")
    existing = find_asset(
        db,
        customer_id=item.customer_id,
        site_id=item.site_id,
        external_id=item.candidate_external_id,
        name=value.get("name"),
        asset_type=value.get("asset_type"),
    )
    if existing is not None:
        item.entity_id = existing.id
        return existing
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
    item.entity_id = asset.id
    for assertion in db.scalars(
        select(KnowledgeAssertion).where(
            KnowledgeAssertion.customer_id == item.customer_id,
            KnowledgeAssertion.site_id == item.site_id,
            KnowledgeAssertion.subject_type == "asset",
            KnowledgeAssertion.subject_external_id == item.candidate_external_id,
            KnowledgeAssertion.is_current.is_(True),
        )
    ):
        assertion.subject_id = asset.id
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


def _resolve_relationship_asset(
    db: Session, item: ReconciliationItem, external_id: str | None
) -> Asset | None:
    return find_asset(
        db,
        customer_id=item.customer_id,
        site_id=item.site_id,
        external_id=external_id,
    )


def _accept_relationship(db: Session, item: ReconciliationItem) -> AssetRelationship:
    value = dict(item.observed_value_json or {})
    source = _resolve_relationship_asset(db, item, value.get("source_external_id"))
    target = _resolve_relationship_asset(db, item, value.get("target_external_id"))
    if source is None or target is None:
        raise HTTPException(
            status_code=409,
            detail="Accept the source and target assets before this relationship",
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


def accept_item(db: Session, item: ReconciliationItem, user: User) -> object:
    if item.status not in {"open", "deferred"}:
        raise HTTPException(status_code=409, detail="This item has already been decided")
    assertion = db.get(KnowledgeAssertion, item.assertion_id)
    if assertion is None:
        raise HTTPException(status_code=409, detail="The source assertion no longer exists")
    if item.entity_type == "asset" and item.category == "newly_discovered":
        result = _accept_new_asset(db, item)
    elif item.entity_type == "asset" and item.category in {"changed", "contradiction"}:
        result = _accept_changed_fact(db, item)
    elif item.entity_type == "asset_relationship":
        result = _accept_relationship(db, item)
    else:
        raise HTTPException(status_code=422, detail="This item cannot be applied automatically")
    item.status = "accepted"
    item.decided_by_user_id = user.id
    item.decided_at = datetime.now(timezone.utc)
    confirm(assertion)
    return result


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


def defer_item(db: Session, item: ReconciliationItem, user: User, reason: str | None) -> None:
    if item.status != "open":
        raise HTTPException(status_code=409, detail="Only open items can be deferred")
    item.status = "deferred"
    item.decision_reason = reason
    item.decided_by_user_id = user.id
    item.decided_at = datetime.now(timezone.utc)
