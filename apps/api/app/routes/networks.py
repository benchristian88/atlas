import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, RequestContext, require_permission, require_scope, scope_condition
from app.database import get_db
from app.models import AssetInterface, Customer, Network, Site
from app.routes.crud_helpers import apply_changes, commit, flush, not_found
from app.schemas import NetworkCreate, NetworkResponse, NetworkUpdate

router = APIRouter(prefix="/networks", tags=["networks"])


def validate_customer_site(
    db: Session, customer_id: uuid.UUID, site_id: uuid.UUID | None
) -> tuple[Customer, Site | None]:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise not_found("Customer")
    site = None
    if site_id is not None:
        site = db.get(Site, site_id)
        if site is None or site.customer_id != customer_id:
            raise HTTPException(
                status_code=422,
                detail="Site does not belong to the selected customer",
            )
    return customer, site


@router.get("", response_model=list[NetworkResponse])
def list_networks(
    context: RequestContext,
    principal: Principal = Depends(require_permission("networks.view")),
    customer_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    limit: int = Query(default=500, ge=1, le=1000),
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
            if not principal.can_within_customer("networks.view", customer_id):
                raise HTTPException(status_code=403, detail="The requested customer is not available")
        else:
            require_scope(principal, "networks.view", customer_id, site_id)
    query = (
        select(Network)
        .where(scope_condition(principal, "networks.view", Network.customer_id, Network.site_id))
        .order_by(Network.name)
        .limit(limit)
        .offset(offset)
    )
    if customer_id is not None:
        query = query.where(Network.customer_id == customer_id)
    if site_id is not None:
        # Customer-wide networks remain relevant inside a selected site. The
        # scope predicate still hides them from users who hold only a site grant.
        query = query.where(or_(Network.site_id == site_id, Network.site_id.is_(None)))
    return list(db.scalars(query))


@router.post("", response_model=NetworkResponse, status_code=status.HTTP_201_CREATED)
def create_network(
    payload: NetworkCreate,
    request: Request,
    context: RequestContext,
    principal: Principal = Depends(require_permission("networks.create")),
    db: Session = Depends(get_db),
):
    if context.customer_id is not None and payload.customer_id != context.customer_id:
        raise HTTPException(status_code=403, detail="Network must match the active customer")
    if context.site_id is not None and payload.site_id != context.site_id:
        raise HTTPException(status_code=403, detail="Network must match the active site")
    require_scope(principal, "networks.create", payload.customer_id, payload.site_id)
    customer, site = validate_customer_site(db, payload.customer_id, payload.site_id)
    if customer.status != "active" or (site is not None and site.status != "active"):
        raise HTTPException(
            status_code=409,
            detail="Networks cannot be created in an inactive context",
        )
    network = Network(**payload.model_dump())
    db.add(network)
    flush(db, "Network")
    add_audit_event(
        db,
        action="network.created",
        target_type="network",
        target_id=network.id,
        actor=principal.user,
        workspace_id=customer.workspace_id,
        customer_id=network.customer_id,
        site_id=network.site_id,
        summary="Network created",
        metadata={"name": network.name},
        request=request,
    )
    commit(db, "Network")
    db.refresh(network)
    return network


@router.get("/{network_id}", response_model=NetworkResponse)
def get_network(
    network_id: uuid.UUID,
    principal: Principal = Depends(require_permission("networks.view")),
    db: Session = Depends(get_db),
):
    network = db.get(Network, network_id)
    if network is None:
        raise not_found("Network")
    require_scope(
        principal,
        "networks.view",
        network.customer_id,
        network.site_id,
        hide_existence=True,
    )
    return network


@router.patch("/{network_id}", response_model=NetworkResponse)
def update_network(
    network_id: uuid.UUID,
    payload: NetworkUpdate,
    request: Request,
    context: RequestContext,
    principal: Principal = Depends(require_permission("networks.edit")),
    db: Session = Depends(get_db),
):
    network = db.get(Network, network_id)
    if network is None:
        raise not_found("Network")
    require_scope(
        principal,
        "networks.edit",
        network.customer_id,
        network.site_id,
        hide_existence=True,
    )
    changes = payload.model_dump(exclude_unset=True)
    customer_id = changes.get("customer_id", network.customer_id)
    site_id = changes.get("site_id", network.site_id)
    if context.customer_id is not None and customer_id != context.customer_id:
        raise HTTPException(status_code=403, detail="Network must match the active customer")
    if context.site_id is not None and site_id != context.site_id:
        raise HTTPException(status_code=403, detail="Network must match the active site")
    require_scope(principal, "networks.edit", customer_id, site_id)
    customer, site = validate_customer_site(db, customer_id, site_id)
    moving = customer_id != network.customer_id or site_id != network.site_id
    if moving and (
        customer.status != "active" or (site is not None and site.status != "active")
    ):
        raise HTTPException(
            status_code=409,
            detail="Networks cannot be moved to an inactive context",
        )
    if moving and db.scalar(
        select(func.count())
        .select_from(AssetInterface)
        .where(AssetInterface.network_id == network.id)
    ):
        raise HTTPException(
            status_code=409,
            detail="A network assigned to asset interfaces cannot change context",
        )
    apply_changes(network, changes)
    add_audit_event(
        db,
        action="network.updated",
        target_type="network",
        target_id=network.id,
        actor=principal.user,
        workspace_id=customer.workspace_id,
        customer_id=network.customer_id,
        site_id=network.site_id,
        summary="Network updated",
        metadata={"changed_fields": sorted(changes)},
        request=request,
    )
    commit(db, "Network")
    db.refresh(network)
    return network


@router.delete("/{network_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_network(
    network_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_permission("networks.delete")),
    db: Session = Depends(get_db),
) -> Response:
    network = db.get(Network, network_id)
    if network is None:
        raise not_found("Network")
    require_scope(
        principal,
        "networks.delete",
        network.customer_id,
        network.site_id,
        hide_existence=True,
    )
    if db.scalar(
        select(func.count())
        .select_from(AssetInterface)
        .where(AssetInterface.network_id == network.id)
    ):
        raise HTTPException(
            status_code=409,
            detail="Network is assigned to asset interfaces and cannot be deleted",
        )
    customer = db.get(Customer, network.customer_id)
    add_audit_event(
        db,
        action="network.deleted",
        target_type="network",
        target_id=network.id,
        actor=principal.user,
        workspace_id=customer.workspace_id if customer else None,
        customer_id=network.customer_id,
        site_id=network.site_id,
        summary="Network deleted",
        metadata={"name": network.name},
        request=request,
    )
    db.delete(network)
    commit(db, "Network")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
