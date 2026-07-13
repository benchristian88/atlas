import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.database import get_db
from app.models import Asset, Customer, Site
from app.routes.crud_helpers import apply_changes, commit, not_found
from app.routes.manual_assets import customer_and_site
from app.schemas import ManualAssetCreate, ManualAssetResponse, ManualAssetUpdate

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[ManualAssetResponse])
def list_assets(
    _: CurrentUser,
    customer_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(Asset).order_by(Asset.name).limit(limit).offset(offset)
    if customer_id is not None:
        query = query.where(Asset.customer_id == customer_id)
    if site_id is not None:
        query = query.where(Asset.site_id == site_id)
    return list(db.scalars(query))


@router.post("", response_model=ManualAssetResponse, status_code=status.HTTP_201_CREATED)
def create_asset(payload: ManualAssetCreate, _: CurrentUser, db: Session = Depends(get_db)):
    customer, _ = customer_and_site(db, payload.customer_id, payload.site_id)
    values = payload.model_dump()
    values["metadata_"] = values.pop("metadata")
    asset = Asset(
        **values,
        workspace_id=customer.workspace_id,
        source_integration_id=None,
        external_id=None,
        source="manual",
    )
    db.add(asset)
    commit(db, "Asset")
    db.refresh(asset)
    return asset


@router.get("/{asset_id}", response_model=ManualAssetResponse)
def get_asset(asset_id: uuid.UUID, _: CurrentUser, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise not_found("Asset")
    return asset


@router.patch("/{asset_id}", response_model=ManualAssetResponse)
def update_asset(
    asset_id: uuid.UUID,
    payload: ManualAssetUpdate,
    _: CurrentUser,
    db: Session = Depends(get_db),
):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise not_found("Asset")
    changes = payload.model_dump(exclude_unset=True)
    customer_id = changes.get("customer_id", asset.customer_id)
    site_id = changes.get("site_id", asset.site_id)
    customer, _ = customer_and_site(db, customer_id, site_id)
    if "metadata" in changes:
        changes["metadata_"] = changes.pop("metadata")
    changes["workspace_id"] = customer.workspace_id
    apply_changes(asset, changes)
    commit(db, "Asset")
    db.refresh(asset)
    return asset


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: uuid.UUID, _: CurrentUser, db: Session = Depends(get_db)
) -> Response:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise not_found("Asset")
    db.delete(asset)
    commit(db, "Asset")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
