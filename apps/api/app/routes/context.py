from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.authorization import (
    CurrentPrincipal,
    Principal,
    RequestContext,
    require_any_permission,
    scope_condition,
)
from app.database import get_db
from app.models import Asset, AssetRelationship, Customer, Network, Site
from app.schemas import ContextResponse, DashboardSummaryResponse

router = APIRouter(tags=["context"])


def _context_scope(principal: Principal):
    grants = principal.context_grants
    if principal.has_global_context_access:
        return None, None
    customer_ids = {
        grant.customer_id for grant in grants if grant.customer_id is not None
    }
    customer_wide = {
        grant.customer_id
        for grant in grants
        if grant.scope_type == "customer" and grant.customer_id is not None
    }
    site_ids = {
        grant.site_id
        for grant in grants
        if grant.scope_type == "site" and grant.site_id is not None
    }
    return customer_ids, (customer_wide, site_ids)


@router.get("/context", response_model=ContextResponse)
def accessible_context(principal: CurrentPrincipal, db: Session = Depends(get_db)):
    customer_scope, site_scope = _context_scope(principal)
    customer_query = select(Customer).order_by(Customer.name)
    site_query = select(Site).order_by(Site.name)
    if customer_scope is not None:
        customer_query = customer_query.where(Customer.id.in_(customer_scope))
        customer_wide, site_ids = site_scope
        site_conditions = []
        if customer_wide:
            site_conditions.append(Site.customer_id.in_(customer_wide))
        if site_ids:
            site_conditions.append(Site.id.in_(site_ids))
        site_query = site_query.where(or_(*site_conditions) if site_conditions else False)
    return {
        "customers": list(db.scalars(customer_query)),
        "sites": list(db.scalars(site_query)),
        "global_access": principal.has_global_context_access,
    }


@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
def dashboard_summary(
    context: RequestContext,
    principal: Principal = Depends(
        require_any_permission(
            "customers.view",
            "sites.view",
            "assets.view",
            "relationships.view",
            "networks.view",
        )
    ),
    db: Session = Depends(get_db),
):
    customer_predicate = scope_condition(
        principal, "customers.view", Customer.id
    )
    customer_query = select(func.count()).select_from(Customer).where(customer_predicate)
    site_predicate = scope_condition(principal, "sites.view", Site.customer_id, Site.id)
    site_query = select(func.count()).select_from(Site).where(site_predicate)
    asset_predicate = scope_condition(
        principal, "assets.view", Asset.customer_id, Asset.site_id
    )
    asset_query = select(func.count()).select_from(Asset).where(asset_predicate)
    network_predicate = scope_condition(
        principal, "networks.view", Network.customer_id, Network.site_id
    )
    network_query = select(func.count()).select_from(Network).where(network_predicate)

    source = aliased(Asset)
    target = aliased(Asset)
    source_scope = scope_condition(
        principal, "relationships.view", source.customer_id, source.site_id
    )
    target_scope = scope_condition(
        principal, "relationships.view", target.customer_id, target.site_id
    )
    relationship_query = (
        select(func.count())
        .select_from(AssetRelationship)
        .join(source, source.id == AssetRelationship.source_asset_id)
        .join(target, target.id == AssetRelationship.target_asset_id)
        .where(source_scope, target_scope)
    )
    if context.customer_id is not None:
        customer_query = customer_query.where(Customer.id == context.customer_id)
        site_query = site_query.where(Site.customer_id == context.customer_id)
        asset_query = asset_query.where(Asset.customer_id == context.customer_id)
        network_query = network_query.where(Network.customer_id == context.customer_id)
        relationship_query = relationship_query.where(
            source.customer_id == context.customer_id,
            target.customer_id == context.customer_id,
        )
    if context.site_id is not None:
        site_query = site_query.where(Site.id == context.site_id)
        asset_query = asset_query.where(Asset.site_id == context.site_id)
        network_query = network_query.where(
            or_(Network.site_id == context.site_id, Network.site_id.is_(None))
        )
        relationship_query = relationship_query.where(
            source.site_id == context.site_id,
            target.site_id == context.site_id,
        )
    return {
        "customers": int(db.scalar(customer_query) or 0),
        "sites": int(db.scalar(site_query) or 0),
        "assets": int(db.scalar(asset_query) or 0),
        "networks": int(db.scalar(network_query) or 0),
        "relationships": int(db.scalar(relationship_query) or 0),
    }
