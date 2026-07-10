import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.database import get_db
from app.models import Customer, Site
from app.routes.crud_helpers import apply_changes, commit, not_found
from app.schemas import SiteCreate, SiteResponse, SiteUpdate

router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("", response_model=list[SiteResponse])
def list_sites(
    _: CurrentUser,
    customer_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(Site).order_by(Site.name).limit(limit).offset(offset)
    if customer_id is not None:
        query = query.where(Site.customer_id == customer_id)
    return list(db.scalars(query))


@router.post("", response_model=SiteResponse, status_code=status.HTTP_201_CREATED)
def create_site(payload: SiteCreate, _: CurrentUser, db: Session = Depends(get_db)):
    if db.get(Customer, payload.customer_id) is None:
        raise not_found("Customer")
    site = Site(**payload.model_dump())
    db.add(site)
    commit(db, "Site")
    db.refresh(site)
    return site


@router.get("/{site_id}", response_model=SiteResponse)
def get_site(site_id: uuid.UUID, _: CurrentUser, db: Session = Depends(get_db)):
    site = db.get(Site, site_id)
    if site is None:
        raise not_found("Site")
    return site


@router.patch("/{site_id}", response_model=SiteResponse)
def update_site(
    site_id: uuid.UUID,
    payload: SiteUpdate,
    _: CurrentUser,
    db: Session = Depends(get_db),
):
    site = db.get(Site, site_id)
    if site is None:
        raise not_found("Site")
    changes = payload.model_dump(exclude_unset=True)
    if "customer_id" in changes and db.get(Customer, changes["customer_id"]) is None:
        raise not_found("Customer")
    apply_changes(site, changes)
    commit(db, "Site")
    db.refresh(site)
    return site


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_site(site_id: uuid.UUID, _: CurrentUser, db: Session = Depends(get_db)) -> Response:
    site = db.get(Site, site_id)
    if site is None:
        raise not_found("Site")
    db.delete(site)
    commit(db, "Site")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
