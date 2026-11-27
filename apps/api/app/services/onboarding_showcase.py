"""Bounded presentation of current, authorized records in a confirmed setup."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select

from app.authorization import ActiveContext, scope_condition
from app.models import (
    Asset, AssetInterface, AssetRelationship, BusinessFunction, DiscoveryRun, Integration, Network,
    Service, ServiceBusinessFunction,
)
from app.routes.asset_relationships import _scoped_relationship_query
from app.routes.assets import asset_inventory_conditions, asset_type_distribution
from app.routes.business_functions import scoped_business_functions
from app.routes.networks import scoped_networks
from app.services import onboarding, onboarding_link_services as links
from app.services.discovery_review import active_site_discovery_runs
from app.services.onboarding_review import required_gap_count
from app.services.service_relationship_scope import current_relationship

FUNCTION_LIMIT = 6
SERVICE_EXAMPLE_LIMIT = 4
ASSET_TYPE_LIMIT = 8


def function_associations(principal, functions, service_conditions, as_of):
    association = ServiceBusinessFunction
    return select(
        association.business_function_id.label("function_id"), Service.id, Service.name,
    ).select_from(association).join(Service, Service.id == association.service_id).where(
        association.business_function_id.in_(functions.with_only_columns(BusinessFunction.id)),
        current_relationship(association, principal, as_of=as_of), *service_conditions,
    ).distinct().subquery()


def function_summary(db, query, associations):
    functions = db.execute(query.with_only_columns(
        BusinessFunction.id, BusinessFunction.name, func.count().over().label("total"),
    ).order_by(func.lower(BusinessFunction.name), BusinessFunction.id).limit(FUNCTION_LIMIT)).all()
    items = [{"id": row.id, "name": row.name, "services": None} for row in functions]
    if associations is not None and items:
        order = (func.lower(associations.c.name), associations.c.id)
        partition = associations.c.function_id
        examples = select(
            partition, associations.c.id, associations.c.name,
            func.count().over(partition_by=partition).label("total"),
            func.row_number().over(partition_by=partition, order_by=order).label("position"),
        ).where(partition.in_([row.id for row in functions])).subquery()
        summaries = {item["id"]: {"total": 0, "examples": []} for item in items}
        for row in db.execute(select(examples).where(
            examples.c.position <= SERVICE_EXAMPLE_LIMIT,
        ).order_by(examples.c.position)):
            summary = summaries[row.function_id]
            summary["total"] = row.total
            summary["examples"].append({"id": row.id, "name": row.name})
        for item in items:
            item["services"] = summaries[item["id"]]
    return {"total": functions[0].total if functions else 0, "items": items}


def infrastructure_relationship_count(db, context, principal, asset_ids):
    query, source, target = _scoped_relationship_query(principal, "relationships.view")
    return db.scalar(query.with_only_columns(func.count(AssetRelationship.id)).where(
        AssetRelationship.customer_id == context.customer_id, AssetRelationship.site_id == context.site_id,
        source.id.in_(asset_ids), target.id.in_(asset_ids),
    ))


def integration_summary(db, context, principal):
    total, disabled = db.execute(select(
        func.count(Integration.id), func.count(Integration.id).filter(Integration.enabled.is_(False)),
    ).where(
        Integration.customer_id == context.customer_id, Integration.site_id == context.site_id,
        Integration.retired_at.is_(None),
        scope_condition(principal, "integrations.view", Integration.customer_id, Integration.site_id),
    )).one()
    active_runs = active_site_discovery_runs(context).with_only_columns(func.count(DiscoveryRun.id))
    return {
        "total": total, "enabled": total - disabled, "disabled": disabled,
        "active_runs": db.scalar(active_runs),
    }


def showcase(db, site, customer, principal):
    state = onboarding.progress(db, site)
    if state is None or not state.environment_profile or state.current_stage != "showcase":
        raise HTTPException(404, "Record not found")
    context = ActiveContext(customer.id, site.id)

    def can(permission):
        return principal.can(permission, customer.id, site.id)

    function_query = scoped_business_functions(context, principal, active_only=True) if can("business_functions.view") else None
    associations = functions = services = services_without_functions = mappings = focus = None
    if can("services.view"):
        service_conditions = links.eligible_services(principal, site)
        service_total = func.count(Service.id)
        service_query = select(service_total).where(*service_conditions)
        if function_query is not None:
            associations = function_associations(principal, function_query, service_conditions, datetime.now(timezone.utc))
            associated = select(func.count(func.distinct(associations.c.id))).scalar_subquery()
            services, services_without_functions = db.execute(service_query.add_columns(service_total - associated)).one()
        else:
            services = db.scalar(service_query)
        if can("assets.view") and can(links.VIEW):
            mappings = links.summary(db, principal, site)
        if services:
            identifier = db.scalar(select(Service.id).where(*service_conditions).order_by(Service.id).limit(1))
            if identifier:
                focus = f"service:{identifier}"
    if function_query is not None:
        functions = function_summary(db, function_query, associations)

    networks = network_memberships = assets = relationships = None
    if can("networks.view"):
        network_query = scoped_networks(principal, customer.id, site.id)
        networks = db.scalar(network_query.with_only_columns(func.count(Network.id)))
    if can("assets.view"):
        asset_conditions = asset_inventory_conditions(context, principal)
        asset_ids = select(Asset.id).where(*asset_conditions)
        rows = db.execute(asset_type_distribution(asset_conditions).add_columns(
            func.sum(func.count(Asset.id)).over().label("total"),
        ).limit(ASSET_TYPE_LIMIT)).all()
        total = int(rows[0].total) if rows else 0
        assets = {
            "total": total,
            "by_type": [{"id": row.id, "name": row.name, "count": row.asset_count} for row in rows],
            "other_assets": total - sum(row.asset_count for row in rows),
        }
        if focus is None and total:
            identifier = db.scalar(asset_ids.order_by(Asset.id).limit(1))
            if identifier:
                focus = f"asset:{identifier}"
        if can("relationships.view"):
            relationships = infrastructure_relationship_count(db, context, principal, asset_ids)
        if networks is not None:
            network_memberships = db.scalar(select(func.count(AssetInterface.id)).where(
                AssetInterface.asset_id.in_(asset_ids),
                AssetInterface.network_id.in_(network_query.with_only_columns(Network.id)),
            ))

    return {
        "business_functions": functions,
        "services": services,
        "services_without_functions": services_without_functions,
        "assets": assets,
        "networks": networks,
        "integrations": integration_summary(db, context, principal) if can("integrations.view") else None,
        "mappings": mappings,
        "asset_relationships": relationships,
        "network_memberships": network_memberships,
        "required_gaps": required_gap_count(db, context, principal),
        "analysis_focus": focus,
    }
