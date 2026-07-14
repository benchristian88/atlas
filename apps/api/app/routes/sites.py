import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, require_permission, require_scope, scope_condition
from app.database import get_db
from app.models import AccessAssignment, Asset, Customer, Integration, Network, Site
from app.routes.crud_helpers import apply_changes, commit, flush, not_found
from app.schemas import SiteCreate, SiteResponse, SiteUpdate

router = APIRouter(prefix="/sites", tags=["sites"])


def _dependent_count(db: Session, site_id: uuid.UUID) -> int:
    return sum(
        int(db.scalar(select(func.count()).select_from(model).where(column == site_id)) or 0)
        for model, column in (
            (Asset, Asset.site_id),
            (Network, Network.site_id),
            (Integration, Integration.site_id),
            (AccessAssignment, AccessAssignment.site_id),
        )
    )


@router.get("", response_model=list[SiteResponse])
def list_sites(
    principal: Principal = Depends(require_permission("sites.view")),
    customer_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = (
        select(Site)
        .where(scope_condition(principal, "sites.view", Site.customer_id, Site.id))
        .order_by(Site.name)
        .limit(limit)
        .offset(offset)
    )
    if customer_id is not None:
        query = query.where(Site.customer_id == customer_id)
    return list(db.scalars(query))


@router.post("", response_model=SiteResponse, status_code=status.HTTP_201_CREATED)
def create_site(
    payload: SiteCreate,
    request: Request,
    principal: Principal = Depends(require_permission("sites.manage")),
    db: Session = Depends(get_db),
):
    customer = db.get(Customer, payload.customer_id)
    if customer is None:
        raise not_found("Customer")
    require_scope(principal, "sites.manage", customer.id, hide_existence=True)
    site = Site(**payload.model_dump())
    db.add(site)
    flush(db, "Site")
    add_audit_event(
        db,
        action="site.created",
        target_type="site",
        target_id=site.id,
        actor=principal.user,
        workspace_id=customer.workspace_id,
        customer_id=customer.id,
        site_id=site.id,
        summary="Site created",
        metadata={"name": site.name},
        request=request,
    )
    commit(db, "Site")
    db.refresh(site)
    return site


@router.get("/{site_id}", response_model=SiteResponse)
def get_site(
    site_id: uuid.UUID,
    principal: Principal = Depends(require_permission("sites.view")),
    db: Session = Depends(get_db),
):
    site = db.get(Site, site_id)
    if site is None:
        raise not_found("Site")
    require_scope(principal, "sites.view", site.customer_id, site.id, hide_existence=True)
    return site


@router.patch("/{site_id}", response_model=SiteResponse)
def update_site(
    site_id: uuid.UUID,
    payload: SiteUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("sites.manage")),
    db: Session = Depends(get_db),
):
    site = db.get(Site, site_id)
    if site is None:
        raise not_found("Site")
    require_scope(principal, "sites.manage", site.customer_id, site.id, hide_existence=True)
    changes = payload.model_dump(exclude_unset=True)
    if "customer_id" in changes and changes["customer_id"] != site.customer_id:
        if _dependent_count(db, site.id):
            raise HTTPException(
                status_code=409,
                detail="A used site cannot be moved to another customer",
            )
        customer = db.get(Customer, changes["customer_id"])
        if customer is None:
            raise not_found("Customer")
        require_scope(principal, "sites.manage", customer.id)
    else:
        customer = db.get(Customer, site.customer_id)
    apply_changes(site, changes)
    add_audit_event(
        db,
        action="site.updated",
        target_type="site",
        target_id=site.id,
        actor=principal.user,
        workspace_id=customer.workspace_id if customer else None,
        customer_id=site.customer_id,
        site_id=site.id,
        summary="Site updated",
        metadata={"changed_fields": sorted(changes)},
        request=request,
    )
    commit(db, "Site")
    db.refresh(site)
    return site


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_site(
    site_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_permission("sites.manage")),
    db: Session = Depends(get_db),
) -> Response:
    site = db.get(Site, site_id)
    if site is None:
        raise not_found("Site")
    require_scope(principal, "sites.manage", site.customer_id, site.id, hide_existence=True)
    if _dependent_count(db, site.id):
        raise HTTPException(
            status_code=409,
            detail="Site is in use. Deactivate it instead of deleting it.",
        )
    customer = db.get(Customer, site.customer_id)
    add_audit_event(
        db,
        action="site.deleted",
        target_type="site",
        target_id=site.id,
        actor=principal.user,
        workspace_id=customer.workspace_id if customer else None,
        customer_id=site.customer_id,
        summary="Unused site deleted",
        metadata={"name": site.name},
        request=request,
    )
    db.delete(site)
    commit(db, "Site")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
