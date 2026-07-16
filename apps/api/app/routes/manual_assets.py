"""Compatibility routes for clients that still use ``/manual-assets``."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.authorization import Principal, RequestContext, require_permission, require_scope, scope_condition
from app.database import get_db
from app.models import Asset
from app.presenters import asset_response_data
from app.routes.assets import create_asset, delete_asset, update_asset
from app.routes.crud_helpers import not_found
from app.schemas import ManualAssetCreate, ManualAssetResponse, ManualAssetUpdate

router = APIRouter(prefix="/manual-assets", tags=["manual assets"])


def get_manual_asset(db: Session, asset_id: uuid.UUID) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.source_integration_id is not None:
        raise not_found("Manual asset")
    return asset


@router.get("", response_model=list[ManualAssetResponse])
def list_manual_assets(
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
    if customer_id is not None:
        if site_id is None:
            if not principal.can_within_customer("assets.view", customer_id):
                raise HTTPException(status_code=403, detail="The requested customer is not available")
        else:
            require_scope(principal, "assets.view", customer_id, site_id)
    query = (
        select(Asset)
        .where(
            Asset.source_integration_id.is_(None),
            scope_condition(principal, "assets.view", Asset.customer_id, Asset.site_id),
        )
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
def create_manual_asset(
    payload: ManualAssetCreate,
    request: Request,
    context: RequestContext,
    principal: Principal = Depends(require_permission("assets.create")),
    db: Session = Depends(get_db),
):
    return create_asset(payload, request, context, principal, db)


@router.get("/{asset_id}", response_model=ManualAssetResponse)
def get_asset(
    asset_id: uuid.UUID,
    principal: Principal = Depends(require_permission("assets.view")),
    db: Session = Depends(get_db),
):
    asset = get_manual_asset(db, asset_id)
    require_scope(
        principal, "assets.view", asset.customer_id, asset.site_id, hide_existence=True
    )
    return asset_response_data(db, asset)


@router.patch("/{asset_id}", response_model=ManualAssetResponse)
def update_manual_asset(
    asset_id: uuid.UUID,
    payload: ManualAssetUpdate,
    request: Request,
    context: RequestContext,
    principal: Principal = Depends(require_permission("assets.edit")),
    db: Session = Depends(get_db),
):
    get_manual_asset(db, asset_id)
    return update_asset(asset_id, payload, request, context, principal, db)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_manual_asset(
    asset_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_permission("assets.delete")),
    db: Session = Depends(get_db),
) -> Response:
    get_manual_asset(db, asset_id)
    return delete_asset(asset_id, request, principal, db)
