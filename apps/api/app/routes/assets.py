import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import (
    Principal,
    RequestContext,
    require_permission,
    require_scope,
    scope_condition,
)
from app.database import get_db
from app.models import (
    Asset,
    AssetInterface,
    AssetRelationship,
    AssetType,
    Customer,
    Site,
)
from app.presenters import asset_response_data
from app.routes.crud_helpers import apply_changes, commit, flush, not_found
from app.schemas import ManualAssetCreate, ManualAssetResponse, ManualAssetUpdate
from app.services.custom_fields import applicable_definitions, custom_field_values, set_asset_custom_fields
from app.services.manual_knowledge import (
    MANUAL_ASSET_KNOWLEDGE_FIELDS,
    declare_asset_changes,
)

router = APIRouter(prefix="/assets", tags=["assets"])


def customer_and_site(
    db: Session, customer_id: uuid.UUID, site_id: uuid.UUID
) -> tuple[Customer, Site]:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise not_found("Customer")
    site = db.get(Site, site_id)
    if site is None or site.customer_id != customer.id:
        raise not_found("Site for customer")
    return customer, site


def _available_asset_type(
    db: Session, key: str, *, allow_inactive_key: str | None = None
) -> AssetType:
    asset_type = db.scalar(select(AssetType).where(AssetType.key == key))
    if asset_type is None or (not asset_type.active and key != allow_inactive_key):
        raise HTTPException(status_code=422, detail="Asset type is not active or does not exist")
    return asset_type


def _explicit_scope(
    db: Session,
    principal: Principal,
    customer_id: uuid.UUID | None,
    site_id: uuid.UUID | None,
) -> None:
    if site_id is not None:
        site = db.get(Site, site_id)
        if site is None or (customer_id is not None and site.customer_id != customer_id):
            raise HTTPException(status_code=403, detail="The requested site is not available")
        customer_id = site.customer_id
    if customer_id is not None:
        if site_id is None:
            if not principal.can_within_customer("assets.view", customer_id):
                raise HTTPException(status_code=403, detail="The requested customer is not available")
        else:
            require_scope(principal, "assets.view", customer_id, site_id)


@router.get("", response_model=list[ManualAssetResponse])
def list_assets(
    context: RequestContext,
    principal: Principal = Depends(require_permission("assets.view")),
    customer_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    if (
        context.customer_id is not None
        and customer_id is not None
        and customer_id != context.customer_id
    ):
        raise HTTPException(
            status_code=403,
            detail="The requested customer does not match the active context",
        )
    if (
        context.site_id is not None
        and site_id is not None
        and site_id != context.site_id
    ):
        raise HTTPException(
            status_code=403,
            detail="The requested site does not match the active context",
        )
    customer_id = context.customer_id or customer_id
    site_id = context.site_id or site_id
    _explicit_scope(db, principal, customer_id, site_id)
    query = (
        select(Asset)
        .where(scope_condition(principal, "assets.view", Asset.customer_id, Asset.site_id))
        .order_by(Asset.name)
        .limit(limit)
        .offset(offset)
    )
    if customer_id is not None:
        query = query.where(Asset.customer_id == customer_id)
    if site_id is not None:
        query = query.where(Asset.site_id == site_id)
    return [asset_response_data(db, asset) for asset in db.scalars(query)]


@router.post("", response_model=ManualAssetResponse, status_code=status.HTTP_201_CREATED)
def create_asset(
    payload: ManualAssetCreate,
    request: Request,
    context: RequestContext,
    principal: Principal = Depends(require_permission("assets.create")),
    db: Session = Depends(get_db),
):
    if context.customer_id is not None and payload.customer_id != context.customer_id:
        raise HTTPException(status_code=403, detail="Asset customer must match the active context")
    if context.site_id is not None and payload.site_id != context.site_id:
        raise HTTPException(status_code=403, detail="Asset site must match the active context")
    require_scope(principal, "assets.create", payload.customer_id, payload.site_id)
    customer, site = customer_and_site(db, payload.customer_id, payload.site_id)
    if customer.status != "active" or site.status != "active":
        raise HTTPException(status_code=409, detail="Assets cannot be created in an inactive context")
    _available_asset_type(db, payload.asset_type)
    values = payload.model_dump(exclude={"custom_fields"})
    values["metadata_"] = values.pop("metadata")
    asset = Asset(
        **values,
        workspace_id=customer.workspace_id,
        source_integration_id=None,
        external_id=None,
        source="manual",
    )
    db.add(asset)
    flush(db, "Asset")
    declare_asset_changes(
        db,
        asset=asset,
        previous_values={field: None for field in MANUAL_ASSET_KNOWLEDGE_FIELDS},
        actor_user_id=principal.user.id,
    )
    set_asset_custom_fields(
        db, asset, payload.custom_fields, replace_active=True
    )
    add_audit_event(
        db,
        action="asset.created",
        target_type="asset",
        target_id=asset.id,
        actor=principal.user,
        workspace_id=asset.workspace_id,
        customer_id=asset.customer_id,
        site_id=asset.site_id,
        summary="Asset created",
        metadata={"name": asset.name, "asset_type": asset.asset_type},
        request=request,
    )
    commit(db, "Asset")
    db.refresh(asset)
    return asset_response_data(db, asset)


@router.get("/{asset_id}", response_model=ManualAssetResponse)
def get_asset(
    asset_id: uuid.UUID,
    principal: Principal = Depends(require_permission("assets.view")),
    db: Session = Depends(get_db),
):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise not_found("Asset")
    require_scope(
        principal,
        "assets.view",
        asset.customer_id,
        asset.site_id,
        hide_existence=True,
    )
    return asset_response_data(db, asset)


@router.patch("/{asset_id}", response_model=ManualAssetResponse)
def update_asset(
    asset_id: uuid.UUID,
    payload: ManualAssetUpdate,
    request: Request,
    context: RequestContext,
    principal: Principal = Depends(require_permission("assets.edit")),
    db: Session = Depends(get_db),
):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise not_found("Asset")
    require_scope(
        principal, "assets.edit", asset.customer_id, asset.site_id, hide_existence=True
    )
    changes = payload.model_dump(exclude_unset=True, exclude={"custom_fields"})
    customer_id = changes.get("customer_id", asset.customer_id)
    site_id = changes.get("site_id", asset.site_id)
    if site_id is None:
        raise HTTPException(status_code=422, detail="Every asset must belong to a site")
    if context.customer_id is not None and customer_id != context.customer_id:
        raise HTTPException(status_code=403, detail="Asset customer must match the active context")
    if context.site_id is not None and site_id != context.site_id:
        raise HTTPException(status_code=403, detail="Asset site must match the active context")
    require_scope(principal, "assets.edit", customer_id, site_id)
    customer, site = customer_and_site(db, customer_id, site_id)
    moving = customer_id != asset.customer_id or site_id != asset.site_id
    if moving:
        dependency_count = int(
            db.scalar(
                select(func.count())
                .select_from(AssetRelationship)
                .where(
                    or_(
                        AssetRelationship.source_asset_id == asset.id,
                        AssetRelationship.target_asset_id == asset.id,
                    )
                )
            )
            or 0
        ) + int(
            db.scalar(
                select(func.count())
                .select_from(AssetInterface)
                .where(AssetInterface.asset_id == asset.id)
            )
            or 0
        )
        if dependency_count:
            raise HTTPException(
                status_code=409,
                detail="An asset with relationships or interfaces cannot be moved to another site",
            )
        if customer.status != "active" or site.status != "active":
            raise HTTPException(status_code=409, detail="Assets cannot be moved to an inactive context")
    new_type = changes.get("asset_type", asset.asset_type)
    _available_asset_type(db, new_type, allow_inactive_key=asset.asset_type)
    if "metadata" in changes:
        changes["metadata_"] = changes.pop("metadata")
    changes["workspace_id"] = customer.workspace_id
    previous_knowledge_values = {
        field: getattr(asset, field)
        for field in MANUAL_ASSET_KNOWLEDGE_FIELDS
        if field in changes
    }
    apply_changes(asset, changes)
    flush(db, "Asset")
    declare_asset_changes(
        db,
        asset=asset,
        previous_values=previous_knowledge_values,
        actor_user_id=principal.user.id,
    )
    if payload.custom_fields is not None:
        set_asset_custom_fields(
            db, asset, payload.custom_fields, replace_active=True
        )
    else:
        # A type change can make a different required field set applicable.
        stored_values = custom_field_values(db, asset)
        active_keys = {
            item.key for item in applicable_definitions(db, asset.asset_type, active_only=True)
        }
        set_asset_custom_fields(
            db,
            asset,
            {key: value for key, value in stored_values.items() if key in active_keys},
            replace_active=False,
        )
    add_audit_event(
        db,
        action="asset.updated",
        target_type="asset",
        target_id=asset.id,
        actor=principal.user,
        workspace_id=asset.workspace_id,
        customer_id=asset.customer_id,
        site_id=asset.site_id,
        summary="Asset updated",
        metadata={"changed_fields": sorted(payload.model_fields_set)},
        request=request,
    )
    commit(db, "Asset")
    db.refresh(asset)
    return asset_response_data(db, asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_permission("assets.delete")),
    db: Session = Depends(get_db),
) -> Response:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise not_found("Asset")
    require_scope(
        principal, "assets.delete", asset.customer_id, asset.site_id, hide_existence=True
    )
    relationship_count = db.scalar(
        select(func.count())
        .select_from(AssetRelationship)
        .where(
            or_(
                AssetRelationship.source_asset_id == asset.id,
                AssetRelationship.target_asset_id == asset.id,
            )
        )
    )
    if relationship_count:
        raise HTTPException(
            status_code=409,
            detail="Delete this asset's relationships before deleting the asset",
        )
    add_audit_event(
        db,
        action="asset.deleted",
        target_type="asset",
        target_id=asset.id,
        actor=principal.user,
        workspace_id=asset.workspace_id,
        customer_id=asset.customer_id,
        site_id=asset.site_id,
        summary="Asset deleted",
        metadata={"name": asset.name, "asset_type": asset.asset_type},
        request=request,
    )
    db.delete(asset)
    commit(db, "Asset")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
