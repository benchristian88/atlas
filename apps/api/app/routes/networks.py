import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.database import get_db
from app.models import Customer, Network, Site
from app.routes.crud_helpers import apply_changes, commit, not_found
from app.schemas import NetworkCreate, NetworkResponse, NetworkUpdate

router = APIRouter(prefix="/networks", tags=["networks"])


def validate_customer_site(
    db: Session, customer_id: uuid.UUID, site_id: uuid.UUID | None
) -> None:
    if db.get(Customer, customer_id) is None:
        raise not_found("Customer")
    if site_id is not None:
        site = db.get(Site, site_id)
        if site is None:
            raise not_found("Site")
        if site.customer_id != customer_id:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="Site does not belong to the selected customer")


@router.get("", response_model=list[NetworkResponse])
def list_networks(
    _: CurrentUser,
    customer_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(Network).order_by(Network.name).limit(limit).offset(offset)
    if customer_id is not None:
        query = query.where(Network.customer_id == customer_id)
    if site_id is not None:
        query = query.where(Network.site_id == site_id)
    return list(db.scalars(query))


@router.post("", response_model=NetworkResponse, status_code=status.HTTP_201_CREATED)
def create_network(payload: NetworkCreate, _: CurrentUser, db: Session = Depends(get_db)):
    validate_customer_site(db, payload.customer_id, payload.site_id)
    network = Network(**payload.model_dump())
    db.add(network)
    commit(db, "Network")
    db.refresh(network)
    return network


@router.get("/{network_id}", response_model=NetworkResponse)
def get_network(network_id: uuid.UUID, _: CurrentUser, db: Session = Depends(get_db)):
    network = db.get(Network, network_id)
    if network is None:
        raise not_found("Network")
    return network


@router.patch("/{network_id}", response_model=NetworkResponse)
def update_network(
    network_id: uuid.UUID,
    payload: NetworkUpdate,
    _: CurrentUser,
    db: Session = Depends(get_db),
):
    network = db.get(Network, network_id)
    if network is None:
        raise not_found("Network")
    changes = payload.model_dump(exclude_unset=True)
    customer_id = changes.get("customer_id", network.customer_id)
    site_id = changes.get("site_id", network.site_id)
    validate_customer_site(db, customer_id, site_id)
    apply_changes(network, changes)
    commit(db, "Network")
    db.refresh(network)
    return network


@router.delete("/{network_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_network(
    network_id: uuid.UUID, _: CurrentUser, db: Session = Depends(get_db)
) -> Response:
    network = db.get(Network, network_id)
    if network is None:
        raise not_found("Network")
    db.delete(network)
    commit(db, "Network")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
