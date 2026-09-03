from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
from app.models import Asset, AssetRelationship, BusinessFunction, CriticalityLevel, Customer, KnowledgeChange, KnowledgeCompletenessSummary, KnowledgeGap, Network, ReconciliationItem, Service, ServiceAssetDependency, Site
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
            "services.view",
            "business_functions.view",
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
    service_query = select(func.count()).select_from(Service).where(
        scope_condition(principal, "services.view", Service.customer_id, Service.site_id),
        Service.archived_at.is_(None),
    )
    service_records_query = select(Service).where(
        scope_condition(principal, "services.view", Service.customer_id, Service.site_id),
        Service.archived_at.is_(None),
    )
    business_function_query = select(func.count()).select_from(BusinessFunction).where(
        scope_condition(principal, "business_functions.view", BusinessFunction.customer_id, BusinessFunction.site_id),
        BusinessFunction.active.is_(True),
    )
    reconciliation_base = select(func.count()).select_from(ReconciliationItem).where(
        scope_condition(
            principal,
            "reconciliation.view",
            ReconciliationItem.customer_id,
            ReconciliationItem.site_id,
        )
    )
    open_items_query = select(ReconciliationItem).where(
        scope_condition(
            principal,
            "reconciliation.view",
            ReconciliationItem.customer_id,
            ReconciliationItem.site_id,
        ),
        ReconciliationItem.status == "open",
    )
    changes_query = select(func.count()).select_from(KnowledgeChange).where(
        scope_condition(
            principal,
            "changes.view",
            KnowledgeChange.customer_id,
            KnowledgeChange.site_id,
        ),
        KnowledgeChange.occurred_at >= datetime.now(timezone.utc) - timedelta(days=7),
    )

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
    gap_query = select(KnowledgeGap).where(
        scope_condition(principal, "knowledge_gaps.view", KnowledgeGap.customer_id, KnowledgeGap.site_id)
    )
    completeness_query = select(KnowledgeCompletenessSummary).where(
        scope_condition(principal, "knowledge_gaps.view", KnowledgeCompletenessSummary.customer_id, KnowledgeCompletenessSummary.site_id)
    )
    if context.customer_id is not None:
        customer_query = customer_query.where(Customer.id == context.customer_id)
        site_query = site_query.where(Site.customer_id == context.customer_id)
        asset_query = asset_query.where(Asset.customer_id == context.customer_id)
        network_query = network_query.where(Network.customer_id == context.customer_id)
        service_query = service_query.where(Service.customer_id == context.customer_id)
        service_records_query = service_records_query.where(Service.customer_id == context.customer_id)
        business_function_query = business_function_query.where(BusinessFunction.customer_id == context.customer_id)
        reconciliation_base = reconciliation_base.where(
            ReconciliationItem.customer_id == context.customer_id
        )
        open_items_query = open_items_query.where(
            ReconciliationItem.customer_id == context.customer_id
        )
        changes_query = changes_query.where(KnowledgeChange.customer_id == context.customer_id)
        relationship_query = relationship_query.where(
            source.customer_id == context.customer_id,
            target.customer_id == context.customer_id,
        )
        gap_query = gap_query.where(KnowledgeGap.customer_id == context.customer_id)
        completeness_query = completeness_query.where(KnowledgeCompletenessSummary.customer_id == context.customer_id)
    if context.site_id is not None:
        site_query = site_query.where(Site.id == context.site_id)
        asset_query = asset_query.where(Asset.site_id == context.site_id)
        network_query = network_query.where(
            or_(Network.site_id == context.site_id, Network.site_id.is_(None))
        )
        service_query = service_query.where(or_(Service.site_id == context.site_id, Service.site_id.is_(None)))
        service_records_query = service_records_query.where(or_(Service.site_id == context.site_id, Service.site_id.is_(None)))
        business_function_query = business_function_query.where(or_(BusinessFunction.site_id == context.site_id, BusinessFunction.site_id.is_(None)))
        reconciliation_base = reconciliation_base.where(
            ReconciliationItem.site_id == context.site_id
        )
        open_items_query = open_items_query.where(ReconciliationItem.site_id == context.site_id)
        changes_query = changes_query.where(KnowledgeChange.site_id == context.site_id)
        relationship_query = relationship_query.where(
            source.site_id == context.site_id,
            target.site_id == context.site_id,
        )
        gap_query = gap_query.where(KnowledgeGap.site_id == context.site_id)
        completeness_query = completeness_query.where(KnowledgeCompletenessSummary.site_id == context.site_id)
    open_items = list(db.scalars(open_items_query))
    category_counts = {
        category: sum(item.category == category for item in open_items)
        for category in (
            "newly_discovered",
            "changed",
            "no_longer_observed",
            "contradiction",
            "possible_duplicate",
        )
    }
    gaps = list(db.scalars(gap_query)) if principal.can_anywhere("knowledge_gaps.view") else []
    completeness = list(db.scalars(completeness_query)) if principal.can_anywhere("knowledge_gaps.view") else []
    active_gaps = [item for item in gaps if item.status in {"open", "deferred"}]
    active_asset_gaps = [item for item in active_gaps if item.entity_type == "asset"]
    asset_completeness = [item for item in completeness if item.entity_type == "asset"]
    now = datetime.now(timezone.utc)
    asset_count_value = int(db.scalar(asset_query) or 0)
    service_rows = list(db.scalars(service_records_query)) if principal.can_anywhere("services.view") else []
    service_ids = [item.id for item in service_rows]
    service_asset_dependency_ids = set(db.scalars(select(ServiceAssetDependency.service_id).where(ServiceAssetDependency.service_id.in_(service_ids), ServiceAssetDependency.valid_to.is_(None)))) if service_ids else set()
    criticality_by_id = {item.id: item for item in db.scalars(select(CriticalityLevel))} if service_rows else {}
    required_gap_service_ids = {item.entity_id for item in active_gaps if item.entity_type == "service" and item.requirement_level in {"required", "conditional"}}
    return {
        "customers": int(db.scalar(customer_query) or 0),
        "sites": int(db.scalar(site_query) or 0),
        "assets": asset_count_value,
        "networks": int(db.scalar(network_query) or 0),
        "relationships": int(db.scalar(relationship_query) or 0),
        "reconciliation": int(
            db.scalar(reconciliation_base.where(ReconciliationItem.status == "open")) or 0
        ),
        "open_reconciliation_count": len(open_items),
        "newly_discovered_count": category_counts["newly_discovered"],
        "changed_count": category_counts["changed"],
        "no_longer_observed_count": category_counts["no_longer_observed"],
        "contradiction_count": category_counts["contradiction"],
        "possible_duplicate_count": category_counts["possible_duplicate"],
        "oldest_open_item_at": min((item.created_at for item in open_items), default=None),
        "knowledge_changes_last_7_days": int(db.scalar(changes_query) or 0),
        "open_knowledge_gap_count": sum(item.requirement_level in {"required", "conditional"} for item in active_gaps),
        "critical_knowledge_gap_count": sum(item.severity == "critical" for item in active_gaps),
        "high_knowledge_gap_count": sum(item.severity == "high" for item in active_gaps),
        "assets_with_critical_gaps": len({item.entity_id for item in active_asset_gaps if item.severity == "critical"}),
        "assets_not_evaluated": max(0, asset_count_value - sum(item.completeness_status != "not_evaluated" for item in asset_completeness)),
        "assets_operationally_complete": sum(item.completeness_status in {"complete", "operationally_complete", "exception_accepted"} for item in asset_completeness),
        "expired_exception_count": sum(item.status == "exception" and item.exception_expires_at and item.exception_expires_at <= now for item in gaps),
        "services": int(db.scalar(service_query) or 0),
        "business_functions": int(db.scalar(business_function_query) or 0),
        "services_with_critical_gaps": len({item.entity_id for item in active_gaps if item.entity_type == "service" and item.severity == "critical"}),
        "critical_services": sum(criticality_by_id.get(item.criticality_level_id) and criticality_by_id[item.criticality_level_id].key == "critical" for item in service_rows),
        "services_with_required_gaps": len(required_gap_service_ids),
        "services_missing_recovery_targets": sum(item.rto_minutes is None or item.rpo_minutes is None for item in service_rows),
        "services_missing_dependencies": sum(item.id not in service_asset_dependency_ids for item in service_rows),
    }
