"""Site-scoped Link Services reads and adapters for canonical dependency writes."""

import hashlib
import json
from datetime import timezone

from fastapi import HTTPException
from sqlalchemy import case, false, func, or_, select

from app.authorization import forbidden, require_scope, scope_condition
from app.models import Asset, AssetType, RelationshipType, Service, ServiceAssetDependency, ServiceType, Site
from app.routes import services
from app.routes.crud_helpers import commit
from app.schemas import ServiceAssetDependencyCreate
from app.services import onboarding
from app.services.asset_icons import icon_fields
from app.services.service_relationship_scope import current_relationship

STAGE = "link_services"
VIEW = "service_dependencies.view"
MANAGE = "service_dependencies.manage"
Dependency = ServiceAssetDependency


def context(db, principal, customer_id, site_id, *, write=False):
    site, customer, principal = onboarding.scoped_site(
        db, principal, customer_id, site_id, lock=write, manage=write,
    )
    state = onboarding.progress(db, site)
    if state is None or not state.environment_profile or not (
        state.current_stage == STAGE or STAGE in state.stage_decisions
    ):
        raise HTTPException(404, "Record not found")
    if write and state.status != "in_progress":
        raise HTTPException(409, onboarding.CONFLICT)
    return site, customer, principal


def _eligible_services(principal, site):
    return (
        Service.customer_id == site.customer_id,
        or_(Service.site_id.is_(None), Service.site_id == site.id),
        Service.deleted_at.is_(None),
        Service.archived_at.is_(None),
        scope_condition(principal, "services.view", Service.customer_id, Service.site_id),
    )


def _site_counts(principal, site):
    counts = select(Dependency.service_id, func.count().label("total")).join(
        Asset, Asset.id == Dependency.asset_id,
    ).where(
        Asset.customer_id == site.customer_id, Asset.site_id == site.id,
        current_relationship(Dependency, principal),
    ).group_by(Dependency.service_id).subquery()
    visible = (scope_condition(principal, VIEW, Service.customer_id, Service.site_id)
               if principal.can("assets.view", site.customer_id, site.id) else false())
    count = case((visible, func.coalesce(counts.c.total, 0)))
    return counts, count


def summary(db, principal, site):
    if not principal.can("services.view", site.customer_id, site.id):
        return None
    counts, count = _site_counts(principal, site)
    return dict(db.execute(select(
        func.count().filter(count > 0).label("linked"),
        func.count().filter(count == 0).label("unlinked"),
        func.coalesce(func.sum(count), 0).label("mappings"),
        func.count().filter(count.is_(None)).label("unavailable"),
    ).select_from(Service).outerjoin(counts, counts.c.service_id == Service.id).where(
        *_eligible_services(principal, site),
    )).one()._mapping)


def service_page(db, principal, site, *, search, mapping, offset, limit):
    totals = summary(db, principal, site)
    if totals is None:
        return {"summary": None, "services": [], "has_more": False}
    counts, count = _site_counts(principal, site)
    query = select(
        Service.id, Service.name, Service.site_id, Service.service_type_id,
        ServiceType.icon_key.label("service_type_icon_key"),
        ServiceType.accent_key.label("service_type_accent_key"),
        count.label("mapping_count"),
    ).outerjoin(counts, counts.c.service_id == Service.id).join(
        ServiceType, ServiceType.id == Service.service_type_id,
    ).where(*_eligible_services(principal, site))
    if search.strip():
        query = query.where(Service.name.icontains(search.strip(), autoescape=True))
    if mapping == "linked":
        query = query.where(count > 0)
    elif mapping == "unlinked":
        query = query.where(count == 0)
    rows = db.execute(query.order_by(func.lower(Service.name), Service.id).offset(offset).limit(limit + 1)).mappings().all()
    return {"summary": totals, "services": rows[:limit], "has_more": len(rows) > limit}


def _service(db, principal, site, service_id, *, write=False):
    service = db.get(Service, service_id, populate_existing=True)
    if service is None or service.deleted_at is not None or service.customer_id != site.customer_id:
        raise HTTPException(404, "Service not found")
    require_scope(principal, "services.view", service.customer_id, service.site_id, hide_existence=True)
    if service.site_id not in (None, site.id) or service.archived_at is not None:
        if write and principal.can("sites.view", service.customer_id, service.site_id or site.id):
            raise HTTPException(409, "This Service is no longer available in the selected Site setup.")
        raise HTTPException(404, "Service not found")
    return service


def _can_manage(principal, site, service):
    return (
        principal.can(onboarding.MANAGE, site.customer_id, site.id)
        and all(principal.can(permission, service.customer_id, service.site_id) for permission in (VIEW, MANAGE))
        and all(principal.can(permission, site.customer_id, site.id) for permission in ("assets.view", MANAGE))
    )


def _asset_record(asset, asset_type):
    return {
        "id": asset.id, "name": asset.name, "status": asset.status,
        "asset_type": asset.asset_type, "type_name": asset_type.name if asset_type else asset.asset_type,
        "hostname": (asset.hostname or "").strip() or None,
        **icon_fields(asset, asset_type),
    }


def _removal_version(dependency, service, asset, relationship_name):
    fields = (
        dependency.id, dependency.relationship_type_id, relationship_name,
        dependency.updated_at.astimezone(timezone.utc).isoformat(),
        dependency.customer_id, dependency.site_id, dependency.service_id, service.name,
        dependency.asset_id, asset.site_id, asset.name, asset.asset_type, asset.hostname,
    )
    return hashlib.sha256(json.dumps(fields, default=str, ensure_ascii=False).encode()).hexdigest()


def mapping_page(db, principal, site, service_id, *, search, asset_type, offset, limit):
    service = _service(db, principal, site, service_id)
    can_view = principal.can(VIEW, service.customer_id, service.site_id)
    site_rows = [] if can_view and principal.can("assets.view", site.customer_id, site.id) else None
    other_rows = [] if can_view else None
    can_manage = _can_manage(principal, site, service)
    if can_view:
        rows = db.execute(select(Asset, AssetType, Dependency, Site.name, RelationshipType.name).join(
            Dependency, Dependency.asset_id == Asset.id,
        ).join(Site, Site.id == Asset.site_id).join(
            RelationshipType, RelationshipType.id == Dependency.relationship_type_id,
        ).outerjoin(AssetType, AssetType.key == Asset.asset_type).where(
            Dependency.service_id == service.id,
            Dependency.customer_id == site.customer_id,
            or_(Dependency.site_id == site.id, Dependency.site_id.is_(None)),
            current_relationship(Dependency, principal),
            scope_condition(principal, "sites.view", Site.customer_id, Site.id),
        ).order_by(func.lower(Site.name), func.lower(Asset.name), Asset.id, Dependency.id))
        for asset, type_record, dependency, site_name, relationship_name in rows:
            target = site_rows if asset.site_id == site.id else other_rows
            version = (_removal_version(dependency, service, asset, relationship_name)
                       if target is site_rows and can_manage else None)
            target.append({
                "asset": _asset_record(asset, type_record), "id": dependency.id,
                "site_name": site_name, "relationship_name": relationship_name,
                "removal_version": version,
            })

    result = {
        "service_name": service.name, "can_manage": can_manage, "site_mappings": site_rows,
        "other_mappings": other_rows, "available": None, "asset_types": [],
        "has_more": False, "has_eligible_assets": False, "has_unlinked_assets": False,
    }
    if not can_manage:
        return result

    inventory = (
        Asset.customer_id == site.customer_id, Asset.site_id == site.id, Asset.status != "retired",
    )
    types = db.execute(select(Asset.asset_type, AssetType.name).outerjoin(
        AssetType, AssetType.key == Asset.asset_type,
    ).where(*inventory).distinct().order_by(AssetType.name, Asset.asset_type)).all()
    linked = select(1).where(
        Dependency.service_id == service.id, Dependency.asset_id == Asset.id,
        Dependency.valid_to.is_(None), Dependency.customer_id == service.customer_id,
        Dependency.site_id.is_not_distinct_from(service.site_id),
    ).correlate(Asset).exists()
    available = select(Asset, AssetType).outerjoin(
        AssetType, AssetType.key == Asset.asset_type,
    ).where(*inventory, ~linked)
    has_unlinked = db.scalar(select(select(1).select_from(Asset).where(*inventory, ~linked).exists()))
    if search.strip():
        available = available.where(Asset.name.icontains(search.strip(), autoescape=True))
    if asset_type:
        available = available.where(Asset.asset_type == asset_type)
    rows = db.execute(available.order_by(func.lower(Asset.name), Asset.id).offset(offset).limit(limit + 1)).all()
    result.update(
        available=[_asset_record(*row) for row in rows[:limit]],
        asset_types=[{"key": key, "name": name or key} for key, name in types],
        has_more=len(rows) > limit, has_eligible_assets=bool(types), has_unlinked_assets=has_unlinked,
    )
    return result


def _authorize_write(db, principal, site, service_id):
    principal = onboarding.refreshed_access(db, principal, site, manage=True)
    service = _service(db, principal, site, service_id, write=True)
    if not _can_manage(principal, site, service):
        raise forbidden("Service dependency management and view access are required at both endpoints.")
    return principal, service


def _scoped_asset(db, principal, site, asset_id):
    asset = db.get(Asset, asset_id, populate_existing=True)
    if asset is None or asset.customer_id != site.customer_id:
        raise HTTPException(404, "Asset not found")
    require_scope(principal, "assets.view", asset.customer_id, asset.site_id, hide_existence=True)
    require_scope(principal, "sites.view", asset.customer_id, asset.site_id, hide_existence=True)
    if asset.site_id != site.id:
        raise HTTPException(409, "This Asset is outside the selected Site. Refresh the mappings before retrying.")
    return asset


def add_mapping(db, principal, site, service_id, asset_id, request):
    principal, _ = _authorize_write(db, principal, site, service_id)
    _scoped_asset(db, principal, site, asset_id)
    # This write changes no Asset identity. The canonical ordered endpoint
    # locks serialize it with retirement, transfer, deletion and other links.
    services._lock_relationship_endpoints(db, service_id, asset_ids=(asset_id,))
    principal, service = _authorize_write(db, principal, site, service_id)
    asset = _scoped_asset(db, principal, site, asset_id)
    if asset.status == "retired":
        raise HTTPException(409, "This Asset is retired. Refresh the mappings before retrying.")
    if db.scalar(select(Dependency.id).where(
        Dependency.service_id == service.id, Dependency.asset_id == asset.id,
        current_relationship(Dependency, principal),
    ).limit(1)) is not None:
        return {"outcome": "already_exists"}
    relationship_id = db.scalar(select(RelationshipType.id).where(RelationshipType.key == "depends_on"))
    if relationship_id is None:
        raise HTTPException(422, "The Depends on relationship type is unavailable.")
    payload = ServiceAssetDependencyCreate(asset_id=asset.id, relationship_type_id=relationship_id)
    services.add_asset_dependency(db, service, asset, payload, principal, request)
    _authorize_write(db, principal, site, service.id)
    commit(db, "Service asset dependency")
    return {"outcome": "added"}


def remove_mapping(db, principal, site, service_id, dependency_id, removal_version, request):
    principal, _ = _authorize_write(db, principal, site, service_id)
    candidate = db.get(Dependency, dependency_id)
    if candidate is None or candidate.service_id != service_id or candidate.valid_to is not None:
        raise HTTPException(404, "Service asset dependency not found")
    _scoped_asset(db, principal, site, candidate.asset_id)
    item, _, asset = services._locked_relationship(
        db, principal, Dependency, dependency_id, MANAGE, "Service asset dependency",
    )
    principal, service = _authorize_write(db, principal, site, service_id)
    asset = _scoped_asset(db, principal, site, asset.id)
    relationship_name = db.scalar(select(RelationshipType.name).where(RelationshipType.id == item.relationship_type_id))
    if _removal_version(item, service, asset, relationship_name) != removal_version:
        raise HTTPException(409, {
            "code": "link_mapping_changed",
            "message": "This relationship changed since confirmation. Review the current mapping and confirm removal again.",
        })
    services.end_asset_dependency(db, item, service, asset, principal, request)
    _authorize_write(db, principal, site, service.id)
    commit(db, "Service asset dependency")


def decide(db, customer, site, principal, request, *, version, action, acknowledge_attention):
    state = onboarding.progress(db, site, lock=True)
    principal = onboarding.refreshed_access(db, principal, site, manage=True)
    if state is None or state.version != version or state.status != "in_progress" or state.current_stage != STAGE:
        raise HTTPException(409, onboarding.CONFLICT)
    if action == "skip":
        decision = "skipped"
    else:
        totals = summary(db, principal, site)
        attention = totals is None or totals["unlinked"] > 0 or totals["unavailable"] > 0
        if attention and not acknowledge_attention:
            raise HTTPException(409, {
                "code": "link_services_attention",
                "message": "Review the current mapping status and acknowledge the outstanding or unavailable mappings.",
            })
        decision = "attention" if attention else "completed"
    state.stage_decisions = {**state.stage_decisions, STAGE: decision}
    state.current_stage = "review_ready"
    onboarding.record_progress(db, customer, site, principal, request, state, f"link_services_{decision}")
    commit(db, "Onboarding progress")
    return state
