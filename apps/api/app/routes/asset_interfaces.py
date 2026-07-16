import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, RequestContext, require_permission, require_scope, scope_condition
from app.database import get_db
from app.models import Asset, AssetInterface, Network
from app.routes.crud_helpers import apply_changes, commit, flush, not_found
from app.schemas import AssetInterfaceCreate, AssetInterfaceResponse, AssetInterfaceUpdate

router = APIRouter(prefix="/asset-interfaces", tags=["asset interfaces"])


def _validate_network(
    asset: Asset,
    network: Network | None,
    principal: Principal,
    permission: str,
) -> None:
    if network is None:
        return
    require_scope(
        principal,
        permission,
        network.customer_id,
        network.site_id,
        hide_existence=True,
    )
    if network.customer_id != asset.customer_id or (
        network.site_id is not None and network.site_id != asset.site_id
    ):
        raise HTTPException(
            status_code=422,
            detail="Network must belong to the asset customer and site",
        )


def _scoped_interface_query(principal: Principal, permission: str):
    return (
        select(AssetInterface)
        .join(Asset, Asset.id == AssetInterface.asset_id)
        .where(scope_condition(principal, permission, Asset.customer_id, Asset.site_id))
    )


@router.get("", response_model=list[AssetInterfaceResponse])
def list_asset_interfaces(
    context: RequestContext,
    principal: Principal = Depends(require_permission("networks.view")),
    asset_id: uuid.UUID | None = None,
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = _scoped_interface_query(principal, "networks.view")
    if asset_id is not None:
        asset = db.get(Asset, asset_id)
        if asset is None:
            raise not_found("Asset")
        require_scope(
            principal, "networks.view", asset.customer_id, asset.site_id, hide_existence=True
        )
        query = query.where(AssetInterface.asset_id == asset_id)
    if context.customer_id is not None:
        query = query.where(Asset.customer_id == context.customer_id)
    if context.site_id is not None:
        query = query.where(Asset.site_id == context.site_id)
    return list(
        db.scalars(query.order_by(AssetInterface.name).limit(limit).offset(offset))
    )


@router.post("", response_model=AssetInterfaceResponse, status_code=status.HTTP_201_CREATED)
def create_asset_interface(
    payload: AssetInterfaceCreate,
    request: Request,
    context: RequestContext,
    principal: Principal = Depends(require_permission("networks.create")),
    db: Session = Depends(get_db),
):
    asset = db.get(Asset, payload.asset_id)
    if asset is None:
        raise not_found("Asset")
    require_scope(
        principal, "networks.create", asset.customer_id, asset.site_id, hide_existence=True
    )
    if context.customer_id is not None and asset.customer_id != context.customer_id:
        raise HTTPException(status_code=403, detail="Asset must match the active customer")
    if context.site_id is not None and asset.site_id != context.site_id:
        raise HTTPException(status_code=403, detail="Asset must match the active site")
    network = db.get(Network, payload.network_id) if payload.network_id else None
    if payload.network_id and network is None:
        raise not_found("Network")
    _validate_network(asset, network, principal, "networks.create")
    interface = AssetInterface(**payload.model_dump())
    db.add(interface)
    flush(db, "Asset interface")
    add_audit_event(
        db,
        action="asset_interface.created",
        target_type="asset_interface",
        target_id=interface.id,
        actor=principal.user,
        workspace_id=asset.workspace_id,
        customer_id=asset.customer_id,
        site_id=asset.site_id,
        summary="Asset interface created",
        metadata={"asset_id": asset.id, "name": interface.name},
        request=request,
    )
    commit(db, "Asset interface")
    db.refresh(interface)
    return interface


@router.patch("/{interface_id}", response_model=AssetInterfaceResponse)
def update_asset_interface(
    interface_id: uuid.UUID,
    payload: AssetInterfaceUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("networks.edit")),
    db: Session = Depends(get_db),
):
    interface = db.get(AssetInterface, interface_id)
    if interface is None:
        raise not_found("Asset interface")
    asset = db.get(Asset, interface.asset_id)
    if asset is None:
        raise not_found("Asset")
    require_scope(
        principal, "networks.edit", asset.customer_id, asset.site_id, hide_existence=True
    )
    changes = payload.model_dump(exclude_unset=True)
    network_id = changes.get("network_id", interface.network_id)
    network = db.get(Network, network_id) if network_id else None
    if network_id and network is None:
        raise not_found("Network")
    _validate_network(asset, network, principal, "networks.edit")
    apply_changes(interface, changes)
    add_audit_event(
        db,
        action="asset_interface.updated",
        target_type="asset_interface",
        target_id=interface.id,
        actor=principal.user,
        workspace_id=asset.workspace_id,
        customer_id=asset.customer_id,
        site_id=asset.site_id,
        summary="Asset interface updated",
        metadata={"changed_fields": sorted(changes)},
        request=request,
    )
    commit(db, "Asset interface")
    db.refresh(interface)
    return interface


@router.delete("/{interface_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset_interface(
    interface_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_permission("networks.delete")),
    db: Session = Depends(get_db),
) -> Response:
    interface = db.get(AssetInterface, interface_id)
    if interface is None:
        raise not_found("Asset interface")
    asset = db.get(Asset, interface.asset_id)
    if asset is None:
        raise not_found("Asset")
    require_scope(
        principal, "networks.delete", asset.customer_id, asset.site_id, hide_existence=True
    )
    add_audit_event(
        db,
        action="asset_interface.deleted",
        target_type="asset_interface",
        target_id=interface.id,
        actor=principal.user,
        workspace_id=asset.workspace_id,
        customer_id=asset.customer_id,
        site_id=asset.site_id,
        summary="Asset interface deleted",
        metadata={"name": interface.name},
        request=request,
    )
    db.delete(interface)
    commit(db, "Asset interface")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
