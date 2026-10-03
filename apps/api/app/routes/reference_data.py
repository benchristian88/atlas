from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.audit import add_audit_event
from app.authorization import (
    Principal,
    require_global,
    require_permission,
    scope_condition,
)
from app.database import get_db
from app.models import (
    Asset,
    AssetCategory,
    AssetRelationship,
    AssetType,
    TopologyPosition,
    CustomFieldAssetType,
    RelationshipType,
    RelationshipTypeApplicability,
    ServiceAssetDependency,
    ServiceBusinessFunction,
    ServiceDependency,
)
from app.schemas import (
    AssetTypeCreate,
    AssetTypeResponse,
    AssetTypeUpdate,
    RelationshipTypeCreate,
    RelationshipTypeResponse,
    RelationshipTypeUpdate,
)
from app.routes.crud_helpers import commit, flush
from app.services.knowledge_requirement_references import (
    invalidate_referencing_requirements,
    requirements_referencing,
)

asset_types_router = APIRouter(prefix="/asset-types", tags=["asset types"])
relationship_types_router = APIRouter(
    prefix="/relationship-types", tags=["relationship types"]
)


def _validated_asset_type_keys(db: Session, keys: list[str]) -> list[str]:
    normalized = sorted(set(keys))
    if not normalized:
        return []
    existing = set(
        db.scalars(select(AssetType.key).where(AssetType.key.in_(normalized)))
    )
    missing = sorted(set(normalized) - existing)
    if missing:
        raise HTTPException(
            status_code=422,
            detail="Unknown allowed asset types: " + ", ".join(missing),
        )
    return normalized


def _asset_type_response(
    db: Session, item: AssetType, principal: Principal
) -> AssetTypeResponse:
    count = int(
        db.scalar(
            select(func.count())
            .select_from(Asset)
            .where(
                Asset.asset_type == item.key,
                scope_condition(
                    principal,
                    "assets.view",
                    Asset.customer_id,
                    Asset.site_id,
                ),
            )
        )
        or 0
    )
    return AssetTypeResponse.model_validate(
        {
            "id": item.id,
            "key": item.key,
            "name": item.name,
            "description": item.description,
            "category": item.category_record.name if item.category_record else "Uncategorized",
            "category_id": item.category_id,
            "category_key": item.category_record.key if item.category_record else "uncategorized",
            "default_icon_url": item.default_icon_url,
            "topology_position_id": item.topology_position_id,
            "topology_position": item.topology_position,
            "system_defined": item.system_defined,
            "active": item.active,
            "sort_order": item.sort_order,
            "in_use_count": count,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
    )


def _relationship_type_response(
    db: Session, item: RelationshipType, principal: Principal
) -> RelationshipTypeResponse:
    source = aliased(Asset)
    target = aliased(Asset)
    asset_count = int(
        db.scalar(
            select(func.count())
            .select_from(AssetRelationship)
            .join(source, source.id == AssetRelationship.source_asset_id)
            .join(target, target.id == AssetRelationship.target_asset_id)
            .where(
                AssetRelationship.relationship_type == item.key,
                scope_condition(
                    principal,
                    "relationships.view",
                    source.customer_id,
                    source.site_id,
                ),
                scope_condition(
                    principal,
                    "relationships.view",
                    target.customer_id,
                    target.site_id,
                ),
            )
        )
        or 0
    )
    typed_count = int(db.scalar(
        select(func.count()).select_from(ServiceAssetDependency).where(
            ServiceAssetDependency.relationship_type_id == item.id,
            ServiceAssetDependency.valid_to.is_(None),
        )
    ) or 0) + int(db.scalar(
        select(func.count()).select_from(ServiceDependency).where(
            ServiceDependency.relationship_type_id == item.id,
            ServiceDependency.valid_to.is_(None),
        )
    ) or 0) + int(db.scalar(
        select(func.count()).select_from(ServiceBusinessFunction).where(
            ServiceBusinessFunction.relationship_type_id == item.id,
            ServiceBusinessFunction.valid_to.is_(None),
        )
    ) or 0)
    applicability = list(db.scalars(
        select(RelationshipTypeApplicability).where(
            RelationshipTypeApplicability.relationship_type_id == item.id
        ).order_by(
            RelationshipTypeApplicability.source_entity_type,
            RelationshipTypeApplicability.target_entity_type,
        )
    ))
    return RelationshipTypeResponse.model_validate(
        {
            "id": item.id,
            "key": item.key,
            "name": item.name,
            "description": item.description,
            "source_label": item.source_label,
            "target_label": item.target_label,
            "inverse_label": item.inverse_label,
            "directional": item.directional,
            "topology_class": item.topology_class,
            "system_defined": item.system_defined,
            "active": item.active,
            "sort_order": item.sort_order,
            "allowed_source_asset_type_keys": item.allowed_source_asset_type_keys or [],
            "allowed_target_asset_type_keys": item.allowed_target_asset_type_keys or [],
            "applicability": applicability,
            "in_use_count": asset_count + typed_count,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
    )


@asset_types_router.get("", response_model=list[AssetTypeResponse])
def list_asset_types(
    principal: Principal = Depends(require_permission("asset_types.view")),
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    query = select(AssetType).order_by(AssetType.sort_order, AssetType.name)
    if active_only:
        query = query.where(AssetType.active.is_(True))
    return [_asset_type_response(db, item, principal) for item in db.scalars(query)]


@asset_types_router.post(
    "", response_model=AssetTypeResponse, status_code=status.HTTP_201_CREATED
)
def create_asset_type(
    payload: AssetTypeCreate,
    request: Request,
    principal: Principal = Depends(require_permission("asset_types.manage")),
    db: Session = Depends(get_db),
):
    require_global(principal, "asset_types.manage")
    _validate_category(db, payload.category_id)
    _validate_position(db, payload.topology_position_id)
    item = AssetType(**payload.model_dump(), system_defined=False)
    db.add(item)
    flush(db, "Asset type")
    add_audit_event(
        db,
        action="asset_type.created",
        target_type="asset_type",
        target_id=item.id,
        actor=principal.user,
        summary="Asset type created",
        metadata={"key": item.key, "name": item.name},
        request=request,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Asset type key and name must be unique") from exc
    db.refresh(item)
    return _asset_type_response(db, item, principal)


@asset_types_router.patch("/{type_id}", response_model=AssetTypeResponse)
def update_asset_type(
    type_id: uuid.UUID,
    payload: AssetTypeUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("asset_types.manage")),
    db: Session = Depends(get_db),
):
    require_global(principal, "asset_types.manage")
    item = db.get(AssetType, type_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Asset type not found")
    changes = payload.model_dump(exclude_unset=True)
    if "category_id" in changes:
        _validate_category(db, changes["category_id"], current_id=item.category_id)
    if "topology_position_id" in changes:
        _validate_position(db, changes["topology_position_id"], current_id=item.topology_position_id)
    referenced_requirements = requirements_referencing(db, item.id) if changes.get("active") is False else []
    for key, value in changes.items():
        setattr(item, key, value)
    if changes.get("active") is False:
        invalidate_referencing_requirements(db, item.id, "Asset Type")
        from app.services.knowledge_completeness import evaluate_assets_for_asset_type
        for profile_id in {requirement.asset_type_id for requirement in referenced_requirements}:
            evaluate_assets_for_asset_type(db, profile_id, actor_user_id=principal.user.id)
    add_audit_event(
        db,
        action="asset_type.updated",
        target_type="asset_type",
        target_id=item.id,
        actor=principal.user,
        summary="Asset type updated",
        metadata={"key": item.key, "changed_fields": sorted(changes)},
        request=request,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Asset type could not be updated") from exc
    db.refresh(item)
    return _asset_type_response(db, item, principal)


@asset_types_router.delete("/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset_type(
    type_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_permission("asset_types.manage")),
    db: Session = Depends(get_db),
) -> Response:
    require_global(principal, "asset_types.manage")
    item = db.get(AssetType, type_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Asset type not found")
    if item.system_defined:
        raise HTTPException(status_code=409, detail="System asset types cannot be deleted")
    requirement_references = requirements_referencing(db, item.id)
    if requirement_references:
        names = ", ".join(requirement.name for requirement in requirement_references[:5])
        raise HTTPException(status_code=409, detail=f"Asset type is referenced by knowledge requirements: {names}. Deactivate it or update the profile first.")
    asset_count = db.scalar(
        select(func.count()).select_from(Asset).where(Asset.asset_type == item.key)
    )
    field_count = db.scalar(
        select(func.count())
        .select_from(CustomFieldAssetType)
        .where(CustomFieldAssetType.asset_type_key == item.key)
    )
    if asset_count or field_count:
        raise HTTPException(
            status_code=409,
            detail="Asset type is in use. Deactivate it instead of deleting it.",
        )
    relationship_restrictions = db.execute(
        select(
            RelationshipType.allowed_source_asset_type_keys,
            RelationshipType.allowed_target_asset_type_keys,
        )
    )
    if any(
        item.key in (source_keys or []) or item.key in (target_keys or [])
        for source_keys, target_keys in relationship_restrictions
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Asset type is referenced by a relationship-type restriction. "
                "Remove the restriction or deactivate the asset type instead."
            ),
        )
    add_audit_event(
        db,
        action="asset_type.deleted",
        target_type="asset_type",
        target_id=item.id,
        actor=principal.user,
        summary="Unused custom asset type deleted",
        metadata={"key": item.key, "name": item.name},
        request=request,
    )
    db.delete(item)
    commit(db, "Asset type")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@relationship_types_router.get("", response_model=list[RelationshipTypeResponse])
def list_relationship_types(
    principal: Principal = Depends(require_permission("relationship_types.view")),
    active_only: bool = Query(default=False),
    source_entity_type: str | None = Query(default=None),
    target_entity_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = select(RelationshipType).order_by(
        RelationshipType.sort_order, RelationshipType.name
    )
    if active_only:
        query = query.where(RelationshipType.active.is_(True))
    if source_entity_type or target_entity_type:
        applicability_query = select(RelationshipTypeApplicability.relationship_type_id).where(
            RelationshipTypeApplicability.active.is_(True)
        )
        if source_entity_type:
            applicability_query = applicability_query.where(RelationshipTypeApplicability.source_entity_type == source_entity_type)
        if target_entity_type:
            applicability_query = applicability_query.where(RelationshipTypeApplicability.target_entity_type == target_entity_type)
        query = query.where(RelationshipType.id.in_(applicability_query))
    return [
        _relationship_type_response(db, item, principal)
        for item in db.scalars(query)
    ]


@relationship_types_router.post(
    "", response_model=RelationshipTypeResponse, status_code=status.HTTP_201_CREATED
)
def create_relationship_type(
    payload: RelationshipTypeCreate,
    request: Request,
    principal: Principal = Depends(require_permission("relationship_types.manage")),
    db: Session = Depends(get_db),
):
    require_global(principal, "relationship_types.manage")
    values = payload.model_dump(exclude={"applicability"})
    values["allowed_source_asset_type_keys"] = _validated_asset_type_keys(
        db, payload.allowed_source_asset_type_keys
    )
    values["allowed_target_asset_type_keys"] = _validated_asset_type_keys(
        db, payload.allowed_target_asset_type_keys
    )
    item = RelationshipType(**values, system_defined=False)
    db.add(item)
    flush(db, "Relationship type")
    for endpoint in payload.applicability:
        db.add(RelationshipTypeApplicability(
            relationship_type_id=item.id,
            **endpoint.model_dump(),
        ))
    add_audit_event(
        db,
        action="relationship_type.created",
        target_type="relationship_type",
        target_id=item.id,
        actor=principal.user,
        summary="Relationship type created",
        metadata={"key": item.key, "name": item.name},
        request=request,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Relationship type key and name must be unique"
        ) from exc
    db.refresh(item)
    return _relationship_type_response(db, item, principal)


@relationship_types_router.patch(
    "/{type_id}", response_model=RelationshipTypeResponse
)
def update_relationship_type(
    type_id: uuid.UUID,
    payload: RelationshipTypeUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("relationship_types.manage")),
    db: Session = Depends(get_db),
):
    require_global(principal, "relationship_types.manage")
    item = db.get(RelationshipType, type_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Relationship type not found")
    changes = payload.model_dump(exclude_unset=True)
    applicability = changes.pop("applicability", None)
    referenced_requirements = requirements_referencing(db, item.id) if changes.get("active") is False else []
    if "allowed_source_asset_type_keys" in changes:
        changes["allowed_source_asset_type_keys"] = _validated_asset_type_keys(
            db, changes["allowed_source_asset_type_keys"]
        )
    if "allowed_target_asset_type_keys" in changes:
        changes["allowed_target_asset_type_keys"] = _validated_asset_type_keys(
            db, changes["allowed_target_asset_type_keys"]
        )
    for key, value in changes.items():
        setattr(item, key, value)
    if applicability is not None:
        existing = {
            (row.source_entity_type, row.target_entity_type): row
            for row in db.scalars(select(RelationshipTypeApplicability).where(
                RelationshipTypeApplicability.relationship_type_id == item.id
            ))
        }
        requested = {
            (row["source_entity_type"], row["target_entity_type"]): row
            for row in applicability
        }
        for pair, row in existing.items():
            if pair not in requested:
                db.delete(row)
        for pair, values in requested.items():
            if pair in existing:
                existing[pair].active = values.get("active", True)
            else:
                db.add(RelationshipTypeApplicability(relationship_type_id=item.id, **values))
    if changes.get("active") is False:
        invalidate_referencing_requirements(db, item.id, "Relationship Type")
        from app.services.knowledge_completeness import evaluate_assets_for_asset_type
        for profile_id in {requirement.asset_type_id for requirement in referenced_requirements}:
            evaluate_assets_for_asset_type(db, profile_id, actor_user_id=principal.user.id)
    add_audit_event(
        db,
        action="relationship_type.updated",
        target_type="relationship_type",
        target_id=item.id,
        actor=principal.user,
        summary="Relationship type updated",
        metadata={"key": item.key, "changed_fields": sorted(changes) + (["applicability"] if applicability is not None else [])},
        request=request,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Relationship type could not be updated") from exc
    db.refresh(item)
    return _relationship_type_response(db, item, principal)


@relationship_types_router.delete(
    "/{type_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_relationship_type(
    type_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_permission("relationship_types.manage")),
    db: Session = Depends(get_db),
) -> Response:
    require_global(principal, "relationship_types.manage")
    item = db.get(RelationshipType, type_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Relationship type not found")
    if item.system_defined:
        raise HTTPException(status_code=409, detail="System relationship types cannot be deleted")
    requirement_references = requirements_referencing(db, item.id)
    if requirement_references:
        names = ", ".join(requirement.name for requirement in requirement_references[:5])
        raise HTTPException(status_code=409, detail=f"Relationship type is referenced by knowledge requirements: {names}. Deactivate it or update the requirements first.")
    count = db.scalar(
        select(func.count())
        .select_from(AssetRelationship)
        .where(AssetRelationship.relationship_type == item.key)
    )
    if count:
        raise HTTPException(
            status_code=409,
            detail="Relationship type is in use. Deactivate it instead of deleting it.",
        )
    typed_count = sum(int(db.scalar(query) or 0) for query in (
        select(func.count()).select_from(ServiceAssetDependency).where(ServiceAssetDependency.relationship_type_id == item.id),
        select(func.count()).select_from(ServiceDependency).where(ServiceDependency.relationship_type_id == item.id),
        select(func.count()).select_from(ServiceBusinessFunction).where(ServiceBusinessFunction.relationship_type_id == item.id),
    ))
    if typed_count:
        raise HTTPException(status_code=409, detail="Relationship type is used by Service history. Deactivate it instead of deleting it.")
    add_audit_event(
        db,
        action="relationship_type.deleted",
        target_type="relationship_type",
        target_id=item.id,
        actor=principal.user,
        summary="Unused custom relationship type deleted",
        metadata={"key": item.key, "name": item.name},
        request=request,
    )
    db.delete(item)
    commit(db, "Relationship type")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _validate_category(db: Session, category_id, current_id=None):
    category = db.get(AssetCategory, category_id) if category_id else None
    if category is None or (not category.active and category_id != current_id):
        raise HTTPException(status_code=422, detail="Select an active Asset Category")
    return category


def _validate_position(db, position_id, current_id=None):
    if position_id is None:
        return
    position = db.scalar(select(TopologyPosition).where(TopologyPosition.id == position_id).with_for_update(read=True))
    if position is None:
        raise HTTPException(422, "Unknown topology position")
    if not position.active and position_id != current_id:
        raise HTTPException(422, "Choose an active topology position")
