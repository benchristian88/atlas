from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased

from app.authorization import Principal, RequestContext, require_permission, scope_condition
from app.database import get_db
from app.models import Asset, AssetInterface, AssetRelationship, Customer, Network, Site
from app.presenters import asset_response_data
from app.routes.asset_relationships import relationship_response
from app.schemas import TopologyResponse

router = APIRouter(prefix="/topology", tags=["topology"])


@router.get("", response_model=TopologyResponse)
def get_topology(
    context: RequestContext,
    principal: Principal = Depends(require_permission("assets.view")),
    db: Session = Depends(get_db),
):
    customer_query = select(Customer).where(
        scope_condition(principal, "customers.view", Customer.id)
    )
    site_query = select(Site).where(
        scope_condition(principal, "sites.view", Site.customer_id, Site.id)
    )
    asset_query = select(Asset).where(
        scope_condition(principal, "assets.view", Asset.customer_id, Asset.site_id)
    )
    network_query = select(Network).where(
        scope_condition(principal, "networks.view", Network.customer_id, Network.site_id)
    )
    interface_query = (
        select(AssetInterface)
        .join(Asset, Asset.id == AssetInterface.asset_id)
        .where(scope_condition(principal, "networks.view", Asset.customer_id, Asset.site_id))
    )
    source = aliased(Asset)
    target = aliased(Asset)
    relationship_query = (
        select(AssetRelationship)
        .join(source, source.id == AssetRelationship.source_asset_id)
        .join(target, target.id == AssetRelationship.target_asset_id)
        .where(
            scope_condition(
                principal, "relationships.view", source.customer_id, source.site_id
            ),
            scope_condition(
                principal, "relationships.view", target.customer_id, target.site_id
            ),
        )
    )
    if context.customer_id is not None:
        customer_query = customer_query.where(Customer.id == context.customer_id)
        site_query = site_query.where(Site.customer_id == context.customer_id)
        asset_query = asset_query.where(Asset.customer_id == context.customer_id)
        network_query = network_query.where(Network.customer_id == context.customer_id)
        interface_query = interface_query.where(Asset.customer_id == context.customer_id)
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
        interface_query = interface_query.where(Asset.site_id == context.site_id)
        relationship_query = relationship_query.where(
            source.site_id == context.site_id,
            target.site_id == context.site_id,
        )
    customers = list(db.scalars(customer_query.order_by(Customer.name)))
    sites = list(db.scalars(site_query.order_by(Site.name)))
    assets = list(db.scalars(asset_query.order_by(Asset.name)))
    relationships = [
        relationship_response(db, item)
        for item in db.scalars(
            relationship_query.order_by(AssetRelationship.created_at)
        )
    ]
    networks = list(db.scalars(network_query.order_by(Network.name)))
    asset_interfaces = list(
        db.scalars(interface_query.order_by(AssetInterface.name))
    )
    return {
        "customers": customers,
        "sites": sites,
        "assets": [asset_response_data(db, asset) for asset in assets],
        "relationships": relationships,
        "networks": networks,
        "asset_interfaces": asset_interfaces,
    }
