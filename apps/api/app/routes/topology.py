import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased

from app.authorization import Principal, RequestContext, require_permission, scope_condition
from app.database import get_db
from app.models import Asset, AssetInterface, AssetRelationship, Customer, Network, Site, AssetCategory, AssetType, RelationshipType
from app.presenters import topology_asset_responses
from app.routes.asset_relationships import relationship_response
from app.schemas import TopologyResponse, AssetCategoryResponse, AssetTypeResponse, AssetInterfaceResponse, NetworkResponse, RelationshipTypeResponse, ConnectivityResponse
from app.services.infrastructure_topology import connectivity, platform_links

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
    # Every indirect record must also have visible endpoints under Asset/Network
    # permissions. Permission to view relationships alone is insufficient.
    visible_assets = asset_query.with_only_columns(Asset.id).order_by(None)
    relationship_query = relationship_query.where(
        source.id.in_(visible_assets), target.id.in_(visible_assets),
    )
    interface_query = interface_query.where(Asset.id.in_(visible_assets))
    customers = list(db.scalars(customer_query.order_by(Customer.name, Customer.id)))
    sites = list(db.scalars(site_query.order_by(Site.name, Site.id)))
    assets = list(db.scalars(asset_query.order_by(Asset.name, Asset.id)))
    relationships = [
        relationship_response(db, item)
        for item in db.scalars(
            relationship_query.order_by(AssetRelationship.created_at, AssetRelationship.id)
        )
    ]
    networks = list(db.scalars(network_query.order_by(Network.name, Network.id)))
    asset_interfaces = list(
        db.scalars(interface_query.order_by(AssetInterface.name, AssetInterface.id))
    )
    network_ids = {item.id for item in networks}
    interfaces = []
    for item in asset_interfaces:
        values = AssetInterfaceResponse.model_validate(item).model_dump()
        # Retain the visible interface, but never disclose an inaccessible ID.
        if item.network_id not in network_ids:
            values["network_id"] = None
        interfaces.append(values)
    types = {t.key: t for t in db.scalars(select(AssetType).where(AssetType.key.in_({a.asset_type for a in assets})).order_by(AssetType.sort_order, AssetType.name, AssetType.id))}
    definitions = list(db.scalars(select(RelationshipType).where(RelationshipType.key.in_({r["relationship_type"] for r in relationships})).order_by(RelationshipType.sort_order, RelationshipType.key)))
    categories = list(db.scalars(select(AssetCategory).order_by(AssetCategory.sort_order, AssetCategory.name, AssetCategory.id)))
    return {
        "categories": [AssetCategoryResponse.model_validate(c).model_dump() for c in categories],
        "asset_types": [{**AssetTypeResponse.model_validate(t).model_dump(), "category": t.category_record.name, "category_id": t.category_id, "category_key": t.category_record.key} for t in types.values()],
        "relationship_types": [RelationshipTypeResponse.model_validate(t).model_dump() for t in definitions],
        "platform_links": platform_links(relationships),
        "customers": customers,
        "sites": sites,
        "assets": topology_asset_responses(db, assets, types),
        "relationships": relationships,
        "networks": [NetworkResponse.model_validate(n).model_dump() for n in networks],
        "asset_interfaces": interfaces,
    }


@router.get("/connectivity", response_model=ConnectivityResponse)
def get_connectivity(
    context: RequestContext,
    focus_asset_id: uuid.UUID,
    hops: int = Query(1, ge=1, le=2),
    category_ids: list[uuid.UUID] | None = Query(None),
    show_networks: bool = True,
    limit: int = Query(25, ge=1, le=60),
    principal: Principal = Depends(require_permission("assets.view")),
    db: Session = Depends(get_db),
):
    topology = get_topology(context, principal, db)
    return connectivity(topology, focus_asset_id, hops, category_ids, show_networks, limit)
