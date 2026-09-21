import uuid

from fastapi import BackgroundTasks, APIRouter, Depends, HTTPException, Query, Request, Response, status
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
    AssetIconCache,
    AssetInterface,
    AssetRelationship,
    AssetType,
    Customer,
    KnowledgeCompletenessSummary,
    KnowledgeGap,
    Site,
)
from app.presenters import asset_response_data
from app.routes.crud_helpers import apply_changes, commit, flush, not_found
from app.schemas import (
    AssetSummaryResponse,
    ManualAssetCreate,
    ManualAssetResponse,
    ManualAssetUpdate,
)
from app.services.custom_fields import applicable_definitions, custom_field_values, set_asset_custom_fields
from app.services.manual_knowledge import (
    MANUAL_ASSET_KNOWLEDGE_FIELDS,
    declare_asset_changes,
)

from app.services import asset_icons

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
    completeness_status: str | None = None,
    has_critical_gaps: bool | None = None,
    has_open_knowledge_gaps: bool | None = None,
    not_evaluated: bool | None = None,
    asset_type_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    search: str | None = None,
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
    if asset_type_id is not None:
        asset_type_key = db.scalar(select(AssetType.key).where(AssetType.id == asset_type_id))
        if asset_type_key is None:
            return []
        query = query.where(Asset.asset_type == asset_type_key)
    if category_id is not None:
        query = query.where(Asset.asset_type.in_(select(AssetType.key).where(AssetType.category_id == category_id)))
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Asset.name.ilike(pattern),
                Asset.hostname.ilike(pattern),
                Asset.ip_address.ilike(pattern),
                Asset.vendor.ilike(pattern),
                Asset.model.ilike(pattern),
            )
        )
    if completeness_status or has_critical_gaps is not None or has_open_knowledge_gaps is not None or not_evaluated is not None:
        query = query.outerjoin(
            KnowledgeCompletenessSummary,
            (KnowledgeCompletenessSummary.entity_type == "asset")
            & (KnowledgeCompletenessSummary.entity_id == Asset.id),
        )
    if completeness_status:
        query = query.where(KnowledgeCompletenessSummary.completeness_status == completeness_status)
    if has_critical_gaps is not None:
        query = query.where((func.coalesce(KnowledgeCompletenessSummary.critical_gap_count, 0) > 0) if has_critical_gaps else (func.coalesce(KnowledgeCompletenessSummary.critical_gap_count, 0) == 0))
    if has_open_knowledge_gaps is not None:
        query = query.where((func.coalesce(KnowledgeCompletenessSummary.open_gap_count, 0) > 0) if has_open_knowledge_gaps else (func.coalesce(KnowledgeCompletenessSummary.open_gap_count, 0) == 0))
    if not_evaluated is not None:
        unevaluated = or_(KnowledgeCompletenessSummary.id.is_(None), KnowledgeCompletenessSummary.completeness_status == "not_evaluated")
        query = query.where(unevaluated if not_evaluated else ~unevaluated)
    return [asset_response_data(db, asset) for asset in db.scalars(query)]


@router.get("/summary", response_model=AssetSummaryResponse)
def asset_summary(
    context: RequestContext,
    principal: Principal = Depends(require_permission("assets.view")),
    db: Session = Depends(get_db),
):
    customer_id = context.customer_id
    site_id = context.site_id
    _explicit_scope(db, principal, customer_id, site_id)
    conditions = [
        scope_condition(principal, "assets.view", Asset.customer_id, Asset.site_id)
    ]
    if customer_id is not None:
        conditions.append(Asset.customer_id == customer_id)
    if site_id is not None:
        conditions.append(Asset.site_id == site_id)

    total = int(
        db.scalar(select(func.count()).select_from(Asset).where(*conditions)) or 0
    )
    rows = db.execute(
        select(
            AssetType.id,
            AssetType.name,
            func.count(Asset.id).label("asset_count"),
        )
        .join(Asset, Asset.asset_type == AssetType.key)
        .where(*conditions)
        .group_by(AssetType.id, AssetType.name)
        .having(func.count(Asset.id) > 0)
        .order_by(func.count(Asset.id).desc(), AssetType.name.asc())
    )
    return {
        "total": total,
        "by_asset_type": [
            {
                "asset_type_id": row.id,
                "asset_type_name": row.name,
                "count": int(row.asset_count),
            }
            for row in rows
        ],
    }


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
    from app.services.knowledge_completeness import evaluate_asset_safely
    evaluate_asset_safely(db, asset, trigger_context="asset_created", actor_user_id=principal.user.id)
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


@router.get("/{asset_id}/icon")
def get_asset_icon(
    asset_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(require_permission("assets.view")),
    db: Session = Depends(get_db),
):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Record not found")
    require_scope(principal, "assets.view", asset.customer_id, asset.site_id, hide_existence=True)
    # Revalidate authenticated access even when the browser already has bytes.
    headers = {"Cache-Control": "private, no-cache", "Vary": "Cookie, Authorization",
               "X-Content-Type-Options": "nosniff"}
    if not asset.icon_url:
        return Response(status_code=204, headers={**headers, "Cache-Control": "no-store"})
    cache = db.get(AssetIconCache, asset_id)
    data = asset_icons.current_bytes(cache, asset.icon_url)
    if data is not None:
        etag = f'"{cache.content_hash}"'
        headers["ETag"] = etag
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return Response(data, media_type="image/png", headers=headers)
    token = asset_icons.claim_attempt(db, asset.id, asset.icon_url)
    if token:
        background_tasks.add_task(asset_icons.refresh_icon, asset.id, asset.icon_url, token)
    return Response(status_code=204, headers={**headers, "Cache-Control": "no-store"})


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
    if "icon_url" in changes and not asset.icon_url:
        # Match background publication lock order: Asset before cache row.
        asset_icons.clear_icon_cache(db, asset.id)
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
    from app.services.knowledge_completeness import evaluate_asset_safely
    evaluate_asset_safely(db, asset, trigger_context="asset_updated", actor_user_id=principal.user.id)
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
    for gap in db.scalars(select(KnowledgeGap).where(
        KnowledgeGap.entity_type == "asset", KnowledgeGap.entity_id == asset.id,
        KnowledgeGap.status.in_(("open", "deferred", "exception")),
    )):
        gap.status = "superseded"
        gap.resolution_reason = "Asset was deleted"
    summary = db.scalar(select(KnowledgeCompletenessSummary).where(
        KnowledgeCompletenessSummary.entity_type == "asset",
        KnowledgeCompletenessSummary.entity_id == asset.id,
    ))
    if summary:
        db.delete(summary)
    db.delete(asset)
    commit(db, "Asset")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
