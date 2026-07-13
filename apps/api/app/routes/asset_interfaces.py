import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.database import get_db
from app.models import Asset, AssetInterface, Network
from app.routes.crud_helpers import apply_changes, commit, not_found
from app.schemas import AssetInterfaceCreate, AssetInterfaceResponse, AssetInterfaceUpdate

router = APIRouter(prefix="/asset-interfaces", tags=["asset interfaces"])


def validate_network_for_asset(
    db: Session, asset: Asset, network_id: uuid.UUID | None
) -> None:
    if network_id is None:
        return
    network = db.get(Network, network_id)
    if network is None:
        raise not_found("Network")
    if network.customer_id != asset.customer_id:
        raise HTTPException(status_code=422, detail="Network does not belong to the asset customer")
    if network.site_id is not None and asset.site_id != network.site_id:
        raise HTTPException(status_code=422, detail="Network does not belong to the asset site")


@router.get("", response_model=list[AssetInterfaceResponse])
def list_asset_interfaces(
    _: CurrentUser,
    asset_id: uuid.UUID | None = None,
    network_id: uuid.UUID | None = None,
    limit: int = Query(default=1000, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(AssetInterface).order_by(AssetInterface.name).limit(limit).offset(offset)
    if asset_id is not None:
        query = query.where(AssetInterface.asset_id == asset_id)
    if network_id is not None:
        query = query.where(AssetInterface.network_id == network_id)
    return list(db.scalars(query))


@router.post("", response_model=AssetInterfaceResponse, status_code=status.HTTP_201_CREATED)
def create_asset_interface(
    payload: AssetInterfaceCreate, _: CurrentUser, db: Session = Depends(get_db)
):
    asset = db.get(Asset, payload.asset_id)
    if asset is None:
        raise not_found("Asset")
    validate_network_for_asset(db, asset, payload.network_id)
    interface = AssetInterface(**payload.model_dump())
    db.add(interface)
    commit(db, "Asset interface")
    db.refresh(interface)
    return interface


@router.patch("/{interface_id}", response_model=AssetInterfaceResponse)
def update_asset_interface(
    interface_id: uuid.UUID,
    payload: AssetInterfaceUpdate,
    _: CurrentUser,
    db: Session = Depends(get_db),
):
    interface = db.get(AssetInterface, interface_id)
    if interface is None:
        raise not_found("Asset interface")
    asset = db.get(Asset, interface.asset_id)
    if asset is None:
        raise not_found("Asset")
    changes = payload.model_dump(exclude_unset=True)
    validate_network_for_asset(db, asset, changes.get("network_id", interface.network_id))
    apply_changes(interface, changes)
    commit(db, "Asset interface")
    db.refresh(interface)
    return interface


@router.delete("/{interface_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset_interface(
    interface_id: uuid.UUID, _: CurrentUser, db: Session = Depends(get_db)
) -> Response:
    interface = db.get(AssetInterface, interface_id)
    if interface is None:
        raise not_found("Asset interface")
    db.delete(interface)
    commit(db, "Asset interface")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
