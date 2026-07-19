import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased

from app.audit import add_audit_event
from app.authorization import Principal, RequestContext, require_permission, require_scope, scope_condition
from app.database import get_db
from app.models import Asset, AssetRelationship, Customer, RelationshipType, Site
from app.routes.crud_helpers import apply_changes, commit, flush, not_found
from app.services.knowledge_changes import record_change
from app.schemas import (
    AssetRelationshipCreate,
    AssetRelationshipResponse,
    AssetRelationshipUpdate,
)

router = APIRouter(prefix="/asset-relationships", tags=["asset relationships"])


def relationship_response(db: Session, relationship: AssetRelationship) -> dict:
    source = db.get(Asset, relationship.source_asset_id)
    target = db.get(Asset, relationship.target_asset_id)
    return {
        "id": relationship.id,
        "customer_id": relationship.customer_id,
        "site_id": relationship.site_id,
        "source_asset_id": relationship.source_asset_id,
        "target_asset_id": relationship.target_asset_id,
        "relationship_type": relationship.relationship_type,
        "legacy_cross_context": bool(relationship.legacy_cross_context),
        "notes": relationship.notes,
        "source_asset_name": source.name if source else None,
        "target_asset_name": target.name if target else None,
        "created_at": relationship.created_at,
        "updated_at": relationship.updated_at,
    }


def _scoped_relationship_query(principal: Principal, permission: str):
    source = aliased(Asset)
    target = aliased(Asset)
    query = (
        select(AssetRelationship)
        .join(source, source.id == AssetRelationship.source_asset_id)
        .join(target, target.id == AssetRelationship.target_asset_id)
        .where(
            scope_condition(principal, permission, source.customer_id, source.site_id),
            scope_condition(principal, permission, target.customer_id, target.site_id),
        )
    )
    return query, source, target


def _relationship_type_for_assets(
    db: Session, key: str, source: Asset, target: Asset
) -> RelationshipType:
    relationship_type = db.scalar(
        select(RelationshipType).where(RelationshipType.key == key)
    )
    if relationship_type is None or not relationship_type.active:
        raise HTTPException(status_code=422, detail="Relationship type is not active")
    allowed_sources = relationship_type.allowed_source_asset_type_keys or []
    allowed_targets = relationship_type.allowed_target_asset_type_keys or []
    if allowed_sources and source.asset_type not in allowed_sources:
        raise HTTPException(
            status_code=422,
            detail="Relationship type does not allow this source asset type",
        )
    if allowed_targets and target.asset_type not in allowed_targets:
        raise HTTPException(
            status_code=422,
            detail="Relationship type does not allow this target asset type",
        )
    return relationship_type


@router.get("", response_model=list[AssetRelationshipResponse])
def list_asset_relationships(
    context: RequestContext,
    principal: Principal = Depends(require_permission("relationships.view")),
    asset_id: uuid.UUID | None = None,
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query, source, target = _scoped_relationship_query(principal, "relationships.view")
    if asset_id is not None:
        asset = db.get(Asset, asset_id)
        if asset is None:
            raise not_found("Asset")
        require_scope(
            principal,
            "relationships.view",
            asset.customer_id,
            asset.site_id,
            hide_existence=True,
        )
        query = query.where(
            or_(
                AssetRelationship.source_asset_id == asset_id,
                AssetRelationship.target_asset_id == asset_id,
            )
        )
    if context.customer_id is not None:
        query = query.where(
            source.customer_id == context.customer_id,
            target.customer_id == context.customer_id,
        )
    if context.site_id is not None:
        query = query.where(
            source.site_id == context.site_id,
            target.site_id == context.site_id,
        )
    query = query.order_by(AssetRelationship.created_at).limit(limit).offset(offset)
    return [relationship_response(db, item) for item in db.scalars(query)]


@router.post("", response_model=AssetRelationshipResponse, status_code=status.HTTP_201_CREATED)
def create_asset_relationship(
    payload: AssetRelationshipCreate,
    request: Request,
    context: RequestContext,
    principal: Principal = Depends(require_permission("relationships.create")),
    db: Session = Depends(get_db),
):
    if payload.source_asset_id == payload.target_asset_id:
        raise HTTPException(status_code=422, detail="Source and target assets must be different")
    source = db.get(Asset, payload.source_asset_id)
    target = db.get(Asset, payload.target_asset_id)
    if source is None or target is None:
        raise not_found("Source or target asset")
    require_scope(
        principal,
        "relationships.create",
        source.customer_id,
        source.site_id,
        hide_existence=True,
    )
    require_scope(
        principal,
        "relationships.create",
        target.customer_id,
        target.site_id,
        hide_existence=True,
    )
    if source.customer_id != target.customer_id or source.site_id != target.site_id:
        raise HTTPException(
            status_code=422,
            detail="Relationships must connect assets in the same customer and site",
        )
    customer = db.get(Customer, source.customer_id)
    site = db.get(Site, source.site_id)
    if customer is None or site is None or customer.status != "active" or site.status != "active":
        raise HTTPException(
            status_code=409,
            detail="Relationships cannot be created in an inactive context",
        )
    if context.customer_id is not None and source.customer_id != context.customer_id:
        raise HTTPException(status_code=403, detail="Assets must match the active customer")
    if context.site_id is not None and source.site_id != context.site_id:
        raise HTTPException(status_code=403, detail="Assets must match the active site")
    _relationship_type_for_assets(db, payload.relationship_type, source, target)
    relationship = AssetRelationship(
        **payload.model_dump(),
        customer_id=source.customer_id,
        site_id=source.site_id,
        legacy_cross_context=False,
        metadata_={},
    )
    db.add(relationship)
    flush(db, "Asset relationship")
    add_audit_event(
        db,
        action="relationship.created",
        target_type="asset_relationship",
        target_id=relationship.id,
        actor=principal.user,
        workspace_id=source.workspace_id,
        customer_id=source.customer_id,
        site_id=source.site_id,
        summary="Asset relationship created",
        metadata={
            "source_asset_id": source.id,
            "target_asset_id": target.id,
            "relationship_type": relationship.relationship_type,
        },
        request=request,
    )
    record_change(
        db,
        customer_id=source.customer_id,
        site_id=source.site_id,
        change_type="relationship_added",
        entity_type="asset_relationship",
        entity_id=relationship.id,
        entity_name=f"{source.name} → {target.name}",
        predicate=relationship.relationship_type,
        previous_value=None,
        new_value={
            "source_asset_id": source.id,
            "target_asset_id": target.id,
            "relationship_type": relationship.relationship_type,
        },
        truth_classification="declared",
        actor_user_id=principal.user.id,
        summary=f"Added {relationship.relationship_type} relationship from {source.name} to {target.name}",
    )
    from app.services.knowledge_completeness import evaluate_asset_safely
    evaluate_asset_safely(db, source, trigger_context="relationship_created", actor_user_id=principal.user.id)
    evaluate_asset_safely(db, target, trigger_context="relationship_created", actor_user_id=principal.user.id)
    commit(db, "Asset relationship")
    db.refresh(relationship)
    return relationship_response(db, relationship)


@router.get("/{relationship_id}", response_model=AssetRelationshipResponse)
def get_asset_relationship(
    relationship_id: uuid.UUID,
    principal: Principal = Depends(require_permission("relationships.view")),
    db: Session = Depends(get_db),
):
    query, _, _ = _scoped_relationship_query(principal, "relationships.view")
    relationship = db.scalar(query.where(AssetRelationship.id == relationship_id))
    if relationship is None:
        raise not_found("Asset relationship")
    return relationship_response(db, relationship)


@router.patch("/{relationship_id}", response_model=AssetRelationshipResponse)
def update_asset_relationship(
    relationship_id: uuid.UUID,
    payload: AssetRelationshipUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("relationships.edit")),
    db: Session = Depends(get_db),
):
    query, _, _ = _scoped_relationship_query(principal, "relationships.edit")
    relationship = db.scalar(query.where(AssetRelationship.id == relationship_id))
    if relationship is None:
        raise not_found("Asset relationship")
    source = db.get(Asset, relationship.source_asset_id)
    target = db.get(Asset, relationship.target_asset_id)
    changes = payload.model_dump(exclude_unset=True)
    previous_relationship = {
        "source_asset_id": relationship.source_asset_id,
        "target_asset_id": relationship.target_asset_id,
        "relationship_type": relationship.relationship_type,
        "notes": relationship.notes,
    }
    if "relationship_type" in changes:
        _relationship_type_for_assets(db, changes["relationship_type"], source, target)
    apply_changes(relationship, changes)
    flush(db, "Asset relationship")
    add_audit_event(
        db,
        action="relationship.updated",
        target_type="asset_relationship",
        target_id=relationship.id,
        actor=principal.user,
        workspace_id=source.workspace_id,
        customer_id=source.customer_id,
        site_id=source.site_id,
        summary="Asset relationship updated",
        metadata={"changed_fields": sorted(changes)},
        request=request,
    )
    record_change(
        db,
        customer_id=source.customer_id,
        site_id=source.site_id,
        change_type="relationship_changed",
        entity_type="asset_relationship",
        entity_id=relationship.id,
        entity_name=f"{source.name} → {target.name if target else relationship.target_asset_id}",
        predicate=relationship.relationship_type,
        previous_value=previous_relationship,
        new_value={
            "source_asset_id": relationship.source_asset_id,
            "target_asset_id": relationship.target_asset_id,
            "relationship_type": relationship.relationship_type,
            "notes": relationship.notes,
        },
        truth_classification="declared",
        actor_user_id=principal.user.id,
        summary=f"Updated {relationship.relationship_type} relationship from {source.name}",
    )
    from app.services.knowledge_completeness import evaluate_asset_safely
    evaluate_asset_safely(db, source, trigger_context="relationship_updated", actor_user_id=principal.user.id)
    if target:
        evaluate_asset_safely(db, target, trigger_context="relationship_updated", actor_user_id=principal.user.id)
    commit(db, "Asset relationship")
    db.refresh(relationship)
    return relationship_response(db, relationship)


@router.delete("/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset_relationship(
    relationship_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_permission("relationships.delete")),
    db: Session = Depends(get_db),
) -> Response:
    query, _, _ = _scoped_relationship_query(principal, "relationships.delete")
    relationship = db.scalar(query.where(AssetRelationship.id == relationship_id))
    if relationship is None:
        raise not_found("Asset relationship")
    source = db.get(Asset, relationship.source_asset_id)
    target = db.get(Asset, relationship.target_asset_id)
    add_audit_event(
        db,
        action="relationship.deleted",
        target_type="asset_relationship",
        target_id=relationship.id,
        actor=principal.user,
        workspace_id=source.workspace_id,
        customer_id=source.customer_id,
        site_id=source.site_id,
        summary="Asset relationship deleted",
        metadata={"relationship_type": relationship.relationship_type},
        request=request,
    )
    db.delete(relationship)
    flush(db, "Asset relationship")
    from app.services.knowledge_completeness import evaluate_asset_safely
    if source:
        evaluate_asset_safely(db, source, trigger_context="relationship_deleted", actor_user_id=principal.user.id)
    if target:
        evaluate_asset_safely(db, target, trigger_context="relationship_deleted", actor_user_id=principal.user.id)
    commit(db, "Asset relationship")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
