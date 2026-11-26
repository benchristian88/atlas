"""First-class Service CRUD, dependency, provenance, and graph APIs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, RequestContext, refresh_principal, require_permission, require_scope, scope_condition
from app.database import get_db
from app.schemas import EntityDeletionEligibilityResponse
from app.models import (
    Asset, AssetType, BusinessFunction, CriticalityLevel, DependencyGroup,
    DependencyGroupMembership, KnowledgeAssertion, KnowledgeChange,
    KnowledgeCompletenessSummary, KnowledgeGap, RelationshipType,
    RelationshipTypeApplicability, Service, ServiceAssetDependency,
    ServiceBusinessFunction, ServiceDependency, ServiceType, Site,
)
from app.routes.changes import _change_response
from app.routes.crud_helpers import commit, flush, not_found
from app.routes.knowledge import assertion_response
from app.schemas import (
    DependencyGroupCreate, DependencyGroupResponse, DependencyGroupUpdate,
    KnowledgeAssertionResponse, KnowledgeChangeResponse, ServiceArchiveRequest,
    ServiceAssetDependencyCreate, ServiceAssetDependencyResponse,
    ServiceAssetDependencyUpdate, ServiceBusinessFunctionCreate,
    ServiceBusinessFunctionResponse, ServiceBusinessFunctionUpdate,
    ServiceCompletenessResponse, ServiceCreate, ServiceDependencyCreate,
    ServiceDependencyResponse, ServiceDependencyUpdate, ServiceGraphResponse,
    ServiceResponse, ServiceSummaryResponse, ServiceUpdate,
)
from app.services.asset_icons import icon_fields
from app.services.data_sources import lock_customer_manual_inventory, manual_inventory_source
from app.services.knowledge_assertions import accept_assertion, record_assertion
from app.services.knowledge_changes import record_assertion_change, record_change
from app.services.knowledge_lifecycle import retract_assertion
from app.services.knowledge_locks import concurrent_decision, lock_subjects
from app.services.manual_knowledge import MANUAL_SERVICE_KNOWLEDGE_FIELDS, declare_service_changes
from app.services.operational_graph import (
    GraphFocusNotFound,
    GraphProjectionRequest,
    OperationalGraphBuilder,
    operational_graph_to_service_graph,
)
from app.services.service_relationship_scope import (
    RELATIONSHIPS,
    compatible_target_scope,
    current_relationship,
    incompatible_incoming_move,
    matches_service_scope,
    valid_relationship_scope,
    visible_relationships,
    visible_service_relationship_assertion,
)
from app.utils.entity_names import service_slug

router = APIRouter(tags=["services"])


def _service(db: Session, principal: Principal, service_id: uuid.UUID, permission: str, *, lock: bool = False) -> Service:
    if lock:
        item = db.get(Service, service_id, with_for_update=True, populate_existing=True)
    else:
        item = db.get(Service, service_id)
    if item is None or item.deleted_at is not None:
        raise not_found("Service")
    require_scope(principal, permission, item.customer_id, item.site_id, hide_existence=True)
    return item


def _visible_related_ids(db: Session, principal: Principal, model, ids, permission: str, customer_id: uuid.UUID) -> set[uuid.UUID]:
    """Authorize related records before serializing names, links or member IDs."""
    ids = set(ids)
    if not ids:
        return set()
    records = db.scalars(select(model).where(model.id.in_(ids), model.customer_id == customer_id))
    return {
        record.id for record in records
        if record.id in ids and record.customer_id == customer_id
        and principal.can(permission, record.customer_id, record.site_id)
    }


def _validate_context(db: Session, principal: Principal, permission: str, customer_id: uuid.UUID, site_id: uuid.UUID | None) -> None:
    if site_id is not None:
        site = db.get(Site, site_id)
        if site is None or site.customer_id != customer_id:
            raise HTTPException(status_code=422, detail="Site does not belong to the selected customer")
    require_scope(principal, permission, customer_id, site_id)


def _active_type(db: Session, model, item_id: uuid.UUID, label: str, *, allow_inactive_id: uuid.UUID | None = None, lock: bool = False):
    item = db.get(model, item_id, with_for_update={"read": True} if lock else None, populate_existing=lock)
    if item is None or (not item.active and item.id != allow_inactive_id):
        raise HTTPException(status_code=422, detail=f"{label} is not active or does not exist")
    return item


def service_response(db: Session, item: Service, principal: Principal) -> dict:
    service_type = db.get(ServiceType, item.service_type_id)
    criticality = db.get(CriticalityLevel, item.criticality_level_id)
    summary = db.scalar(select(KnowledgeCompletenessSummary).where(
        KnowledgeCompletenessSummary.entity_type == "service",
        KnowledgeCompletenessSummary.entity_id == item.id,
        KnowledgeCompletenessSummary.customer_id == item.customer_id,
        KnowledgeCompletenessSummary.site_id == item.site_id,
    )) if principal.can("knowledge_gaps.view", item.customer_id, item.site_id) else None
    open_gaps = list(db.scalars(select(KnowledgeGap).where(
        KnowledgeGap.entity_type == "service",
        KnowledgeGap.entity_id == item.id,
        KnowledgeGap.customer_id == item.customer_id,
        KnowledgeGap.site_id == item.site_id,
        KnowledgeGap.status.in_({"open", "deferred"}),
    ))) if principal.can("knowledge_gaps.view", item.customer_id, item.site_id) else []
    can_dependencies = principal.can("service_dependencies.view", item.customer_id, item.site_id)
    can_functions = principal.can("business_functions.view", item.customer_id, item.site_id)
    result = ServiceResponse.model_validate(item).model_dump()
    result.update(
        service_type_key=service_type.key if service_type else None,
        service_type_name=service_type.name if service_type else None,
        service_type_icon_key=service_type.icon_key if service_type else None,
        service_type_accent_key=service_type.accent_key if service_type else None,
        criticality_key=criticality.key if criticality else None,
        criticality_name=criticality.name if criticality else None,
        criticality_rank=criticality.rank if criticality else None,
        suggested_rto_minutes=criticality.default_rto_minutes if criticality else None,
        suggested_rpo_minutes=criticality.default_rpo_minutes if criticality else None,
        asset_dependency_count=_relationship_count(db, ServiceAssetDependency, ServiceAssetDependency.service_id == item.id, principal) if can_dependencies else 0,
        service_dependency_count=_relationship_count(db, ServiceDependency, or_(ServiceDependency.source_service_id == item.id, ServiceDependency.target_service_id == item.id), principal) if can_dependencies else 0,
        business_function_count=_relationship_count(db, ServiceBusinessFunction, ServiceBusinessFunction.service_id == item.id, principal) if can_functions else 0,
        completeness_status=summary.completeness_status if summary else "not_evaluated",
        open_gap_count=summary.open_gap_count if summary else 0,
        required_gap_count=sum(gap.requirement_level in {"required", "conditional"} for gap in open_gaps),
        recommended_gap_count=sum(gap.requirement_level == "recommended" for gap in open_gaps),
    )
    return result


def _relationship_count(db, model, condition, principal):
    return db.scalar(select(func.count()).select_from(model).where(
        condition, current_relationship(model, principal),
    )) or 0


def _service_query(context: RequestContext, principal: Principal):
    query = select(Service).where(scope_condition(principal, "services.view", Service.customer_id, Service.site_id))
    if context.customer_id:
        query = query.where(Service.customer_id == context.customer_id)
    if context.site_id:
        query = query.where(or_(Service.site_id == context.site_id, Service.site_id.is_(None)))
    return query


@router.get("/services", response_model=list[ServiceResponse])
def list_services(
    context: RequestContext,
    principal: Principal = Depends(require_permission("services.view")),
    search: str | None = None,
    service_type_id: uuid.UUID | None = None,
    criticality_level_id: uuid.UUID | None = None,
    business_function_id: uuid.UUID | None = None,
    lifecycle_status: str | None = None,
    operational_status: str | None = None,
    completeness_status: str | None = None,
    attention: str | None = None,
    archived: bool = False,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = _service_query(context, principal)
    query = query.where(Service.archived_at.is_not(None) if archived else Service.archived_at.is_(None))
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.where(or_(Service.name.ilike(pattern), Service.purpose.ilike(pattern), Service.description.ilike(pattern), Service.owner_name.ilike(pattern)))
    if service_type_id:
        query = query.where(Service.service_type_id == service_type_id)
    if criticality_level_id:
        query = query.where(Service.criticality_level_id == criticality_level_id)
    if business_function_id:
        query = query.join(ServiceBusinessFunction, ServiceBusinessFunction.service_id == Service.id).where(
            ServiceBusinessFunction.business_function_id == business_function_id,
            current_relationship(ServiceBusinessFunction, principal),
        )
    if lifecycle_status:
        query = query.where(Service.lifecycle_status == lifecycle_status)
    if operational_status:
        query = query.where(Service.operational_status == operational_status)
    if completeness_status:
        query = query.join(KnowledgeCompletenessSummary, (KnowledgeCompletenessSummary.entity_type == "service") & (KnowledgeCompletenessSummary.entity_id == Service.id)).where(KnowledgeCompletenessSummary.completeness_status == completeness_status)
    if attention:
        if attention == "missing_owner":
            query = query.where(or_(Service.owner_name.is_(None), func.trim(Service.owner_name) == ""))
        elif attention == "missing_dependencies":
            query = query.where(~select(ServiceAssetDependency.id).where(ServiceAssetDependency.service_id == Service.id, current_relationship(ServiceAssetDependency, principal)).exists())
        elif attention == "missing_recovery_targets":
            query = query.where(or_(Service.rto_minutes.is_(None), Service.rpo_minutes.is_(None)))
        elif attention == "required_gaps":
            query = query.where(select(KnowledgeGap.id).where(KnowledgeGap.entity_type == "service", KnowledgeGap.entity_id == Service.id, KnowledgeGap.requirement_level.in_({"required", "conditional"}), KnowledgeGap.status.in_({"open", "deferred"})).exists())
        elif attention == "incomplete":
            query = query.where(or_(
                ~select(KnowledgeCompletenessSummary.id).where(KnowledgeCompletenessSummary.entity_type == "service", KnowledgeCompletenessSummary.entity_id == Service.id).exists(),
                select(KnowledgeCompletenessSummary.id).where(KnowledgeCompletenessSummary.entity_type == "service", KnowledgeCompletenessSummary.entity_id == Service.id, KnowledgeCompletenessSummary.completeness_status.in_({"incomplete", "critical_gaps", "not_evaluated"})).exists(),
            ))
        else:
            raise HTTPException(status_code=422, detail="Unknown Service attention filter")
    return [service_response(db, item, principal) for item in db.scalars(query.order_by(Service.name).limit(limit))]


@router.get("/services/summary", response_model=ServiceSummaryResponse)
def services_summary(context: RequestContext, principal: Principal = Depends(require_permission("services.view")), db: Session = Depends(get_db)):
    items = list(db.scalars(_service_query(context, principal)))
    service_ids = [item.id for item in items] or [uuid.uuid4()]
    summaries = {row.entity_id: row for row in db.scalars(select(KnowledgeCompletenessSummary).where(KnowledgeCompletenessSummary.entity_type == "service", KnowledgeCompletenessSummary.entity_id.in_(service_ids))) }
    levels = {item.id: item for item in db.scalars(select(CriticalityLevel))}
    current = [item for item in items if item.archived_at is None]
    dependency_service_ids = set(db.scalars(select(ServiceAssetDependency.service_id).where(ServiceAssetDependency.service_id.in_(service_ids), ServiceAssetDependency.valid_to.is_(None))))
    required_gap_service_ids = set(db.scalars(select(KnowledgeGap.entity_id).where(KnowledgeGap.entity_type == "service", KnowledgeGap.entity_id.in_(service_ids), KnowledgeGap.requirement_level.in_({"required", "conditional"}), KnowledgeGap.status.in_({"open", "deferred"}))))
    return {
        "total": len(items), "active": len(current), "archived": len(items) - len(current),
        "critical": sum(levels.get(item.criticality_level_id) and levels[item.criticality_level_id].key == "critical" for item in current),
        "high": sum(levels.get(item.criticality_level_id) and levels[item.criticality_level_id].key == "high" for item in current),
        "incomplete": sum(summaries.get(item.id) is None or summaries[item.id].completeness_status in {"incomplete", "critical_gaps", "not_evaluated"} for item in current),
        "with_required_gaps": sum(item.id in required_gap_service_ids for item in current),
        "missing_owner": sum(not (item.owner_name or "").strip() for item in current),
        "missing_dependencies": sum(item.id not in dependency_service_ids for item in current),
        "missing_recovery_targets": sum(item.rto_minutes is None or item.rpo_minutes is None for item in current),
    }


@router.post("/services", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
def create_service(payload: ServiceCreate, request: Request, context: RequestContext, principal: Principal = Depends(require_permission("services.create")), db: Session = Depends(get_db)):
    if context.customer_id and payload.customer_id != context.customer_id:
        raise HTTPException(status_code=403, detail="Service customer must match the active context")
    if context.site_id and payload.site_id != context.site_id:
        raise HTTPException(status_code=403, detail="Service site must match the active context")
    _validate_context(db, principal, "services.create", payload.customer_id, payload.site_id)
    # Match Apply: Service Type, Criticality, then Customer inventory if needed.
    _active_type(db, ServiceType, payload.service_type_id, "Service type", lock=True)
    _active_type(db, CriticalityLevel, payload.criticality_level_id, "Criticality level", lock=True)
    if payload.site_id is None:
        lock_customer_manual_inventory(db, payload.customer_id)
    principal = refresh_principal(principal, db)
    item = add_service(db, payload, principal, request)
    commit(db, "Service")
    db.refresh(item)
    return service_response(db, item, principal)


def add_service(db: Session, payload: ServiceCreate, principal: Principal, request: Request) -> Service:
    """Create a Service using the caller's locked references and Customer inventory lock, if scoped there."""
    _validate_context(db, principal, "services.create", payload.customer_id, payload.site_id)
    values = payload.model_dump()
    values["slug"] = payload.slug or service_slug(payload.name)
    item = Service(**values, source="manual", created_by_user_id=principal.user.id, updated_by_user_id=principal.user.id)
    db.add(item)
    flush(db, "Service")
    initial_assertions = declare_service_changes(db, service=item, previous_values={field: None for field in MANUAL_SERVICE_KNOWLEDGE_FIELDS}, actor_user_id=principal.user.id, record_changes=False)
    record_change(db, customer_id=item.customer_id, site_id=item.site_id, change_type="service_created", entity_type="service", entity_id=item.id, entity_name=item.name, summary=f"Created Service {item.name}", actor_user_id=principal.user.id)
    from app.services.knowledge_completeness import evaluate_service_safely
    evaluate_service_safely(db, item, trigger_context="service_created", actor_user_id=principal.user.id)
    add_audit_event(db, action="service.created", target_type="service", target_id=item.id, actor=principal.user, customer_id=item.customer_id, site_id=item.site_id, summary="Service created", metadata={"initial_assertion_ids": [str(assertion.id) for assertion in initial_assertions]}, request=request)
    return item


@router.get("/services/{service_id}", response_model=ServiceResponse)
def get_service(service_id: uuid.UUID, principal: Principal = Depends(require_permission("services.view")), db: Session = Depends(get_db)):
    return service_response(db, _service(db, principal, service_id, "services.view"), principal)


@router.patch("/services/{service_id}", response_model=ServiceResponse)
@concurrent_decision
def update_service(service_id: uuid.UUID, payload: ServiceUpdate, request: Request, context: RequestContext, principal: Principal = Depends(require_permission("services.edit")), db: Session = Depends(get_db)):
    item = _service(db, principal, service_id, "services.edit", lock=True)
    principal = refresh_principal(principal, db)
    require_scope(principal, "services.edit", item.customer_id, item.site_id, hide_existence=True)
    changes = payload.model_dump(exclude_unset=True)
    new_site_id = changes.get("site_id", item.site_id)
    if context.site_id and new_site_id != context.site_id:
        raise HTTPException(status_code=403, detail="Service site must match the active context")
    _validate_context(db, principal, "services.edit", item.customer_id, new_site_id)
    moving = new_site_id != item.site_id
    if moving:
        # Outgoing edges and groups retain the owning Service's recorded scope.
        owns_current_relationship = any(
            db.scalar(select(model.id).where(
                getattr(model, owner_column) == item.id, model.valid_to.is_(None),
            ).limit(1)) is not None
            for model, owner_column in (
                (ServiceAssetDependency, "service_id"),
                (ServiceDependency, "source_service_id"),
                (ServiceBusinessFunction, "service_id"),
                (DependencyGroup, "service_id"),
            )
        )
        if owns_current_relationship or incompatible_incoming_move(
            db, ServiceDependency, item.id, item.customer_id, new_site_id,
        ):
            raise HTTPException(409, "A Service with dependencies cannot be moved to another site")
    if "name" in changes and "slug" not in changes and item.slug == service_slug(item.name):
        changes["slug"] = service_slug(changes["name"])
    semantic_changes = {key: value for key, value in changes.items() if getattr(item, key) != value}
    if semantic_changes and new_site_id is None:
        # The existing row lock protects the edit. Take the Customer lock before
        # a rename or move can claim a name or slug needed by an import.
        lock_customer_manual_inventory(db, item.customer_id)
        principal = refresh_principal(principal, db)
        require_scope(principal, "services.edit", item.customer_id, item.site_id, hide_existence=True)
        require_scope(principal, "services.edit", item.customer_id)
    if "service_type_id" in changes:
        _active_type(db, ServiceType, changes["service_type_id"], "Service type", allow_inactive_id=item.service_type_id)
    if "criticality_level_id" in changes:
        _active_type(db, CriticalityLevel, changes["criticality_level_id"], "Criticality level", allow_inactive_id=item.criticality_level_id)
    if not semantic_changes:
        return service_response(db, item, principal)
    previous = {field: getattr(item, field) for field in MANUAL_SERVICE_KNOWLEDGE_FIELDS if field in changes}
    for key, value in semantic_changes.items():
        setattr(item, key, value)
    item.updated_by_user_id = principal.user.id
    flush(db, "Service")
    declare_service_changes(db, service=item, previous_values=previous, actor_user_id=principal.user.id)
    from app.services.knowledge_completeness import evaluate_service_safely
    evaluate_service_safely(db, item, trigger_context="service_updated", actor_user_id=principal.user.id, scope_changed=moving)
    add_audit_event(db, action="service.updated", target_type="service", target_id=item.id, actor=principal.user, customer_id=item.customer_id, site_id=item.site_id, summary="Service updated", metadata={"changed_fields": sorted(semantic_changes)}, request=request)
    commit(db, "Service")
    db.refresh(item)
    return service_response(db, item, principal)


@router.post("/services/{service_id}/archive", response_model=ServiceResponse)
def archive_service(service_id: uuid.UUID, payload: ServiceArchiveRequest, request: Request, principal: Principal = Depends(require_permission("services.archive")), db: Session = Depends(get_db)):
    item = _service(db, principal, service_id, "services.archive", lock=True)
    if item.archived_at is None:
        item.archived_at = datetime.now(timezone.utc); item.archived_by_user_id = principal.user.id; item.archive_reason = payload.reason
        record_change(db, customer_id=item.customer_id, site_id=item.site_id, change_type="service_archived", entity_type="service", entity_id=item.id, entity_name=item.name, summary=f"Archived Service {item.name}", actor_user_id=principal.user.id, metadata={"reason": payload.reason})
        add_audit_event(db, action="service.archived", target_type="service", target_id=item.id, actor=principal.user, customer_id=item.customer_id, site_id=item.site_id, summary="Service archived", request=request)
        commit(db, "Service archive")
    return service_response(db, item, principal)


@router.post("/services/{service_id}/restore", response_model=ServiceResponse)
def restore_service(service_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("services.archive")), db: Session = Depends(get_db)):
    item = _service(db, principal, service_id, "services.archive", lock=True)
    if item.archived_at is not None:
        item.archived_at = None; item.archived_by_user_id = None; item.archive_reason = None
        record_change(db, customer_id=item.customer_id, site_id=item.site_id, change_type="service_updated", entity_type="service", entity_id=item.id, entity_name=item.name, summary=f"Restored Service {item.name}", actor_user_id=principal.user.id)
        add_audit_event(db, action="service.restored", target_type="service", target_id=item.id, actor=principal.user, customer_id=item.customer_id, site_id=item.site_id, summary="Service restored", request=request)
        commit(db, "Service restore")
    return service_response(db, item, principal)


def _applicable_relationship(db: Session, relationship_type_id: uuid.UUID, source_type: str, target_type: str) -> RelationshipType:
    relationship = db.get(RelationshipType, relationship_type_id)
    if relationship is None or not relationship.active:
        raise HTTPException(status_code=422, detail="Relationship type is not active or does not exist")
    allowed = db.scalar(select(RelationshipTypeApplicability.id).where(RelationshipTypeApplicability.relationship_type_id == relationship.id, RelationshipTypeApplicability.source_entity_type == source_type, RelationshipTypeApplicability.target_entity_type == target_type, RelationshipTypeApplicability.active.is_(True)))
    if allowed is None:
        raise HTTPException(status_code=422, detail=f"Relationship type is not valid for {source_type} to {target_type}")
    return relationship


def _asset_dependency_response(db: Session, item: ServiceAssetDependency, service: Service, asset: Asset, semantics: dict | None = None) -> dict:
    relationship = db.get(RelationshipType, item.relationship_type_id)
    result = ServiceAssetDependencyResponse.model_validate(item).model_dump()
    if asset is not None:
        asset_type = db.scalar(select(AssetType).where(AssetType.key == asset.asset_type))
        result.update(icon_fields(asset, asset_type))
    result.update(service_name=service.name if service else None, asset_name=asset.name if asset else None, asset_type=asset.asset_type if asset else None, relationship_type_name=relationship.name if relationship else None, source_label=relationship.source_label if relationship else None, target_label=relationship.target_label if relationship else None, **(semantics or _dependency_semantics(db, item, "asset")))
    return result


def _service_dependency_response(db: Session, item: ServiceDependency, source: Service, target: Service, semantics: dict | None = None) -> dict:
    relationship = db.get(RelationshipType, item.relationship_type_id)
    result = ServiceDependencyResponse.model_validate(item).model_dump()
    result.update(source_service_name=source.name if source else None, target_service_name=target.name if target else None, relationship_type_name=relationship.name if relationship else None, source_label=relationship.source_label if relationship else None, target_label=relationship.target_label if relationship else None, **(semantics or _dependency_semantics(db, item, "service")))
    return result


def _dependency_semantics(db, item, kind):
    return _dependency_semantics_by_id(db, [item], kind)[item.id]


def _dependency_semantics_by_id(db: Session, items: list, dependency_kind: str) -> dict[uuid.UUID, dict]:
    if not items:
        return {}
    dependency_column = (
        DependencyGroupMembership.service_asset_dependency_id
        if dependency_kind == "asset"
        else DependencyGroupMembership.service_dependency_id
    )
    memberships = list(db.scalars(select(DependencyGroupMembership).where(
        dependency_column.in_([item.id for item in items]),
        DependencyGroupMembership.valid_to.is_(None),
    )))
    group_ids = {membership.dependency_group_id for membership in memberships}
    groups = {
        group.id: group
        for group in db.scalars(select(DependencyGroup).where(
            DependencyGroup.id.in_(group_ids),
            DependencyGroup.valid_to.is_(None),
        ))
    } if group_ids else {}
    dependency_attribute = (
        "service_asset_dependency_id"
        if dependency_kind == "asset"
        else "service_dependency_id"
    )
    memberships_by_dependency_id = {
        getattr(membership, dependency_attribute): membership
        for membership in memberships
    }
    result = {}
    for item in items:
        membership = memberships_by_dependency_id.get(item.id)
        group = groups.get(membership.dependency_group_id) if membership else None
        subject_id = item.service_id if dependency_kind == "asset" else item.source_service_id
        if group is not None and (
            group.service_id != subject_id
            or group.customer_id != item.customer_id
            or group.site_id != item.site_id
        ):
            group = None
        result[item.id] = {
            "dependency_group_id": group.id if group else None,
            "dependency_group_name": group.name if group else None,
            "dependency_strategy": group.strategy if group else None,
            "dependency_requirement": group.requirement if group else ("required" if item.required_for_operation else "optional"),
            "failure_effect": group.failure_effect if group else "unknown",
        }
    return result


def _lock_relationship_endpoints(db, service_id, *, asset_ids=(), target_service_ids=(), function_ids=()):
    lock_subjects(db, {
        "asset": set(asset_ids),
        "service": {service_id, *target_service_ids},
        "business_function": set(function_ids),
    })


def _target(db, principal, model, target_id, permission, label="Relationship endpoint"):
    _, _, target_model, view_permission = RELATIONSHIPS[model]
    target = db.get(target_model, target_id)
    if (target is None or getattr(target, "deleted_at", None) is not None
            or not principal.can(permission, target.customer_id, target.site_id)
            or not principal.can(view_permission, target.customer_id, target.site_id)):
        raise not_found(label)
    return target


def _locked_relationship(db, principal, model, relationship_id, permission, label):
    owner_column, target_column, target_model, _ = RELATIONSHIPS[model]
    candidate = db.get(model, relationship_id)
    if candidate is None:
        raise not_found(label)
    service_id, target_id = getattr(candidate, owner_column), getattr(candidate, target_column)
    _service(db, principal, service_id, permission)
    if target_model is Asset:
        _lock_relationship_endpoints(db, service_id, asset_ids=(target_id,))
    elif target_model is Service:
        _lock_relationship_endpoints(db, service_id, target_service_ids=(target_id,))
    else:
        _lock_relationship_endpoints(db, service_id, function_ids=(target_id,))
    principal = refresh_principal(principal, db)
    service = _service(db, principal, service_id, permission)
    item = db.get(model, relationship_id, populate_existing=True)
    if item is None or item.valid_to is not None:
        raise not_found(label)
    target = _target(db, principal, model, target_id, permission, label)
    if not valid_relationship_scope(item, service, target):
        raise not_found(label)
    return item, service, target


def _group_memberships(
    db: Session,
    group_id: uuid.UUID,
    *,
    active_only: bool = False,
) -> list[DependencyGroupMembership]:
    query = select(DependencyGroupMembership).where(
        DependencyGroupMembership.dependency_group_id == group_id,
    )
    if active_only:
        query = query.where(DependencyGroupMembership.valid_to.is_(None))
    return list(db.scalars(query.execution_options(populate_existing=True).order_by(
        DependencyGroupMembership.created_at,
        DependencyGroupMembership.id,
    )))


def _dependency_group_response(db: Session, item: DependencyGroup) -> dict:
    memberships = _group_memberships(db, item.id, active_only=item.valid_to is None)
    result = DependencyGroupResponse.model_validate(item).model_dump()
    result.update(
        asset_dependency_ids=[row.service_asset_dependency_id for row in memberships if row.service_asset_dependency_id],
        service_dependency_ids=[row.service_dependency_id for row in memberships if row.service_dependency_id],
    )
    return result


def _member_dependency_ids(memberships):
    return (
        [row.service_asset_dependency_id for row in memberships if row.service_asset_dependency_id],
        [row.service_dependency_id for row in memberships if row.service_dependency_id],
    )


def _lock_group_endpoints(db, service_id, asset_dependency_ids, service_dependency_ids):
    # Membership and endpoint IDs are immutable. A group update creates a new
    # group, and members of the original can only be ended while we wait.
    asset_ids = set(db.scalars(select(ServiceAssetDependency.asset_id).where(
        ServiceAssetDependency.id.in_(asset_dependency_ids),
        ServiceAssetDependency.service_id == service_id,
    ))) if asset_dependency_ids else set()
    service_ids = set(db.scalars(select(ServiceDependency.target_service_id).where(
        ServiceDependency.id.in_(service_dependency_ids),
        ServiceDependency.source_service_id == service_id,
    ))) if service_dependency_ids else set()
    _lock_relationship_endpoints(db, service_id, asset_ids=asset_ids, target_service_ids=service_ids)


def _lock_current_group(db, principal, group_id, asset_ids=(), service_ids=()):
    candidate = db.get(DependencyGroup, group_id)
    if candidate is None or candidate.valid_to is not None:
        raise not_found("Dependency group")
    _service(db, principal, candidate.service_id, "service_dependencies.manage")
    prior_assets, prior_services = _member_dependency_ids(_group_memberships(db, group_id, active_only=True))
    _lock_group_endpoints(db, candidate.service_id, {*prior_assets, *asset_ids}, {*prior_services, *service_ids})
    principal = refresh_principal(principal, db)
    service = _service(db, principal, candidate.service_id, "service_dependencies.manage")
    group = db.get(DependencyGroup, group_id, populate_existing=True)
    if group is None or group.valid_to is not None or not matches_service_scope(group, service):
        raise not_found("Dependency group")
    memberships = _group_memberships(db, group_id, active_only=True)
    _validated_group_members(db, principal, service, *_member_dependency_ids(memberships), replacing_group_id=group.id)
    return principal, service, group, memberships


def _validated_group_members(
    db: Session,
    principal: Principal,
    service: Service,
    asset_dependency_ids: list[uuid.UUID],
    service_dependency_ids: list[uuid.UUID],
    *,
    replacing_group_id: uuid.UUID | None = None,
) -> tuple[list[ServiceAssetDependency], list[ServiceDependency]]:
    if not asset_dependency_ids and not service_dependency_ids:
        raise HTTPException(status_code=422, detail="A dependency group must contain at least one dependency")

    asset_rows: list[ServiceAssetDependency] = []
    service_rows: list[ServiceDependency] = []
    for model, identifiers, rows, label in (
        (ServiceAssetDependency, asset_dependency_ids, asset_rows, "Service asset dependency"),
        (ServiceDependency, service_dependency_ids, service_rows, "Service dependency"),
    ):
        owner_column, target_column, _, _ = RELATIONSHIPS[model]
        for dependency_id in identifiers:
            row = db.get(model, dependency_id)
            if (row is None or row.valid_to is not None or getattr(row, owner_column) != service.id
                    or not matches_service_scope(row, service)):
                raise not_found(label)
            target = _target(db, principal, model, getattr(row, target_column), "service_dependencies.manage", label)
            if not compatible_target_scope(service, target):
                raise not_found(label)
            rows.append(row)

    for column, dependency_ids in (
        (DependencyGroupMembership.service_asset_dependency_id, asset_dependency_ids),
        (DependencyGroupMembership.service_dependency_id, service_dependency_ids),
    ):
        if not dependency_ids:
            continue
        memberships = db.scalars(select(DependencyGroupMembership).where(
            column.in_(dependency_ids),
            DependencyGroupMembership.valid_to.is_(None),
        ))
        if any(row.dependency_group_id != replacing_group_id for row in memberships):
            raise HTTPException(status_code=422, detail="A dependency already belongs to another active dependency group")
    return asset_rows, service_rows


def _add_group_memberships(
    db: Session,
    group: DependencyGroup,
    asset_rows: list[ServiceAssetDependency],
    service_rows: list[ServiceDependency],
    principal: Principal,
    effective_at: datetime,
) -> None:
    required = group.requirement == "required"
    for dependency in asset_rows:
        dependency.required_for_operation = required
        dependency.updated_by_user_id = principal.user.id
        db.add(DependencyGroupMembership(
            dependency_group_id=group.id,
            service_asset_dependency_id=dependency.id,
            valid_from=effective_at,
            created_by_user_id=principal.user.id,
        ))
    for dependency in service_rows:
        dependency.required_for_operation = required
        dependency.updated_by_user_id = principal.user.id
        db.add(DependencyGroupMembership(
            dependency_group_id=group.id,
            service_dependency_id=dependency.id,
            valid_from=effective_at,
            created_by_user_id=principal.user.id,
        ))


def _end_dependency_membership(db: Session, item, service: Service, dependency_kind: str, principal: Principal, effective_at: datetime) -> None:
    column = (
        DependencyGroupMembership.service_asset_dependency_id
        if dependency_kind == "asset"
        else DependencyGroupMembership.service_dependency_id
    )
    membership = db.scalar(select(DependencyGroupMembership).where(
        column == item.id,
        DependencyGroupMembership.valid_to.is_(None),
    ))
    if membership is None:
        return
    group = db.get(DependencyGroup, membership.dependency_group_id)
    if group is None or group.valid_to is not None or group.service_id != service.id or not matches_service_scope(group, service):
        raise not_found("Dependency group")
    membership.valid_to = effective_at
    membership.ended_by_user_id = principal.user.id
    remaining = db.scalar(select(func.count()).select_from(DependencyGroupMembership).where(
        DependencyGroupMembership.dependency_group_id == membership.dependency_group_id,
        DependencyGroupMembership.id != membership.id,
        DependencyGroupMembership.valid_to.is_(None),
    ))
    if not remaining:
        group.valid_to = effective_at
        group.ended_by_user_id = principal.user.id


def _relationship_assertion(db: Session, *, service: Service, predicate: str, object_type: str, object_id: uuid.UUID, actor_user_id: uuid.UUID) -> KnowledgeAssertion:
    source = manual_inventory_source(db, service.customer_id, service.site_id)
    assertion, _ = record_assertion(db, customer_id=service.customer_id, site_id=service.site_id, subject_type="service", subject_id=service.id, predicate=predicate, object_type=object_type, object_id=object_id, truth_classification="declared", data_source_id=source.id)
    accept_assertion(db, assertion, user_id=actor_user_id)
    return assertion


@router.get("/services/{service_id}/asset-dependencies", response_model=list[ServiceAssetDependencyResponse])
def list_service_asset_dependencies(service_id: uuid.UUID, principal: Principal = Depends(require_permission("service_dependencies.view")), include_history: bool = False, db: Session = Depends(get_db)):
    service = _service(db, principal, service_id, "service_dependencies.view")
    query = visible_relationships(ServiceAssetDependency, principal, include_history=include_history).where(
        ServiceAssetDependency.service_id == service.id,
    )
    rows = list(db.execute(query.order_by(ServiceAssetDependency.created_at)))
    semantics = _dependency_semantics_by_id(db, [row for _, _, row in rows], "asset")
    return [_asset_dependency_response(db, row, source, target, semantics[row.id]) for source, target, row in rows]



@router.post("/services/{service_id}/asset-dependencies", response_model=ServiceAssetDependencyResponse, status_code=status.HTTP_201_CREATED)
@concurrent_decision
def create_service_asset_dependency(service_id: uuid.UUID, payload: ServiceAssetDependencyCreate, request: Request, principal: Principal = Depends(require_permission("service_dependencies.manage")), db: Session = Depends(get_db)):
    _lock_relationship_endpoints(db, service_id, asset_ids=(payload.asset_id,))
    principal = refresh_principal(principal, db)
    service = _service(db, principal, service_id, "service_dependencies.manage")
    asset = _target(db, principal, ServiceAssetDependency, payload.asset_id, "service_dependencies.manage")
    if not compatible_target_scope(service, asset):
        raise HTTPException(422, detail="Asset is outside the Service customer/site scope")
    relationship = _applicable_relationship(db, payload.relationship_type_id, "service", "asset")
    item = ServiceAssetDependency(customer_id=service.customer_id, site_id=service.site_id, service_id=service.id, asset_id=asset.id, relationship_type_id=relationship.id, required_for_operation=payload.required_for_operation, description=payload.description, source="manual", created_by_user_id=principal.user.id, updated_by_user_id=principal.user.id)
    db.add(item); flush(db, "Service asset dependency")
    assertion = _relationship_assertion(db, service=service, predicate=relationship.key, object_type="asset", object_id=asset.id, actor_user_id=principal.user.id)
    record_assertion_change(db, assertion=assertion, change_type="service_dependency_added", entity_name=service.name, summary=f"{service.name} {relationship.source_label.lower()} {asset.name}", actor_user_id=principal.user.id, metadata={"dependency_id": item.id, "target_name": asset.name})
    from app.services.knowledge_completeness import evaluate_service_safely
    evaluate_service_safely(db, service, trigger_context="service_dependency_added", actor_user_id=principal.user.id)
    add_audit_event(db, action="service_asset_dependency.created", target_type="service_asset_dependency", target_id=item.id, actor=principal.user, customer_id=service.customer_id, site_id=service.site_id, summary="Service asset dependency created", request=request)
    response = _asset_dependency_response(db, item, service, asset)
    commit(db, "Service asset dependency")
    return response


@router.patch("/service-asset-dependencies/{dependency_id}", response_model=ServiceAssetDependencyResponse)
@concurrent_decision
def update_service_asset_dependency(dependency_id: uuid.UUID, payload: ServiceAssetDependencyUpdate, principal: Principal = Depends(require_permission("service_dependencies.manage")), db: Session = Depends(get_db)):
    item, service, asset = _locked_relationship(
        db, principal, ServiceAssetDependency, dependency_id, "service_dependencies.manage", "Service asset dependency",
    )
    changes = payload.model_dump(exclude_unset=True)
    if "required_for_operation" in changes:
        semantics = _dependency_semantics(db, item, "asset")
        if semantics["dependency_group_id"] is not None and changes["required_for_operation"] != (semantics["dependency_requirement"] == "required"):
            raise HTTPException(status_code=422, detail="Change the dependency group's requirement instead")
    old_relationship = db.get(RelationshipType, item.relationship_type_id)
    new_relationship = old_relationship
    if "relationship_type_id" in changes:
        new_relationship = _applicable_relationship(db, changes["relationship_type_id"], "service", "asset")
    for key, value in changes.items(): setattr(item, key, value)
    item.updated_by_user_id = principal.user.id
    if new_relationship and old_relationship and new_relationship.id != old_relationship.id:
        _retract_dependency_assertion(db, service, old_relationship, "asset", item.asset_id, principal)
        assertion = _relationship_assertion(db, service=service, predicate=new_relationship.key, object_type="asset", object_id=item.asset_id, actor_user_id=principal.user.id)
        record_assertion_change(db, assertion=assertion, change_type="service_dependency_added", entity_name=service.name, summary=f"Changed the relationship to {asset.name if asset else 'an Asset'} to {new_relationship.name}", actor_user_id=principal.user.id, metadata={"dependency_id": item.id, "previous_relationship_type_id": old_relationship.id})
    elif changes:
        record_change(db, customer_id=service.customer_id, site_id=service.site_id, change_type="service_updated", entity_type="service", entity_id=service.id, entity_name=service.name, summary=f"Updated the dependency on {asset.name if asset else 'an Asset'}", actor_user_id=principal.user.id, metadata={"dependency_id": item.id, "changed_fields": sorted(changes)})
    flush(db, "Service asset dependency")
    response = _asset_dependency_response(db, item, service, asset)
    commit(db, "Service asset dependency")
    return response


def _retract_dependency_assertion(db: Session, service: Service, relationship: RelationshipType | str | None, object_type: str, object_id: uuid.UUID, principal: Principal) -> None:
    predicate = relationship if isinstance(relationship, str) else relationship.key if relationship else None
    if predicate is None: return
    assertion = db.scalar(select(KnowledgeAssertion).where(
        KnowledgeAssertion.customer_id == service.customer_id,
        KnowledgeAssertion.site_id == service.site_id,
        KnowledgeAssertion.subject_type == "service",
        KnowledgeAssertion.subject_id == service.id,
        KnowledgeAssertion.predicate == predicate,
        KnowledgeAssertion.object_type == object_type,
        KnowledgeAssertion.object_id == object_id,
        KnowledgeAssertion.truth_classification == "declared",
        KnowledgeAssertion.retracted_at.is_(None),
    ).order_by(KnowledgeAssertion.created_at.desc()).limit(1))
    if assertion: retract_assertion(db, assertion, user=principal.user, reason="Manual Service dependency removed", confirm_provenance_gap=True)


@router.delete("/service-asset-dependencies/{dependency_id}", status_code=status.HTTP_204_NO_CONTENT)
@concurrent_decision
def delete_service_asset_dependency(dependency_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("service_dependencies.manage")), db: Session = Depends(get_db)):
    item, service, asset = _locked_relationship(
        db, principal, ServiceAssetDependency, dependency_id, "service_dependencies.manage", "Service asset dependency",
    )
    relationship = db.get(RelationshipType, item.relationship_type_id)
    effective_at = datetime.now(timezone.utc)
    item.valid_to = effective_at; item.ended_by_user_id = principal.user.id
    _end_dependency_membership(db, item, service, "asset", principal, effective_at)
    _retract_dependency_assertion(db, service, relationship, "asset", item.asset_id, principal)
    record_change(db, customer_id=service.customer_id, site_id=service.site_id, change_type="service_dependency_removed", entity_type="service", entity_id=service.id, entity_name=service.name, summary=f"Removed dependency on {asset.name if asset else 'unavailable asset'}", actor_user_id=principal.user.id, metadata={"dependency_id": item.id, "relationship_type_id": item.relationship_type_id})
    from app.services.knowledge_completeness import evaluate_service_safely
    evaluate_service_safely(db, service, trigger_context="service_dependency_removed", actor_user_id=principal.user.id)
    add_audit_event(db, action="service_asset_dependency.ended", target_type="service_asset_dependency", target_id=item.id, actor=principal.user, customer_id=service.customer_id, site_id=service.site_id, summary="Service asset dependency ended", request=request)
    commit(db, "Service asset dependency")


@router.get("/services/{service_id}/service-dependencies", response_model=list[ServiceDependencyResponse])
def list_service_dependencies(service_id: uuid.UUID, principal: Principal = Depends(require_permission("service_dependencies.view")), include_history: bool = False, db: Session = Depends(get_db)):
    service = _service(db, principal, service_id, "service_dependencies.view")
    query = visible_relationships(ServiceDependency, principal, include_history=include_history).where(
        or_(ServiceDependency.source_service_id == service.id, ServiceDependency.target_service_id == service.id),
    )
    rows = list(db.execute(query.order_by(ServiceDependency.created_at)))
    semantics = _dependency_semantics_by_id(db, [row for _, _, row in rows], "service")
    return [_service_dependency_response(db, row, source, target, semantics[row.id]) for source, target, row in rows]



@router.post("/services/{service_id}/service-dependencies", response_model=ServiceDependencyResponse, status_code=status.HTTP_201_CREATED)
@concurrent_decision
def create_service_dependency(service_id: uuid.UUID, payload: ServiceDependencyCreate, request: Request, principal: Principal = Depends(require_permission("service_dependencies.manage")), db: Session = Depends(get_db)):
    _lock_relationship_endpoints(db, service_id, target_service_ids=(payload.target_service_id,))
    principal = refresh_principal(principal, db)
    source = _service(db, principal, service_id, "service_dependencies.manage")
    target = _target(db, principal, ServiceDependency, payload.target_service_id, "service_dependencies.manage")
    if target.id == source.id:
        raise HTTPException(422, "A Service cannot depend on itself")
    if not compatible_target_scope(source, target):
        raise HTTPException(422, detail="Target Service is outside the customer/site scope")
    relationship = _applicable_relationship(db, payload.relationship_type_id, "service", "service")
    item = ServiceDependency(customer_id=source.customer_id, site_id=source.site_id, source_service_id=source.id, target_service_id=target.id, relationship_type_id=relationship.id, required_for_operation=payload.required_for_operation, description=payload.description, created_by_user_id=principal.user.id, updated_by_user_id=principal.user.id)
    db.add(item); flush(db, "Service dependency")
    assertion = _relationship_assertion(db, service=source, predicate=relationship.key, object_type="service", object_id=target.id, actor_user_id=principal.user.id)
    record_assertion_change(db, assertion=assertion, change_type="service_dependency_added", entity_name=source.name, summary=f"{source.name} {relationship.source_label.lower()} {target.name}", actor_user_id=principal.user.id, metadata={"dependency_id": item.id, "target_name": target.name})
    from app.services.knowledge_completeness import evaluate_service_safely
    for endpoint in (source, target):
        evaluate_service_safely(db, endpoint, trigger_context="service_dependency_added", actor_user_id=principal.user.id)
    add_audit_event(db, action="service_dependency.created", target_type="service_dependency", target_id=item.id, actor=principal.user, customer_id=source.customer_id, site_id=source.site_id, summary="Service dependency created", request=request)
    response = _service_dependency_response(db, item, source, target)
    commit(db, "Service dependency")
    return response


@router.patch("/service-dependencies/{dependency_id}", response_model=ServiceDependencyResponse)
@concurrent_decision
def update_service_dependency(dependency_id: uuid.UUID, payload: ServiceDependencyUpdate, principal: Principal = Depends(require_permission("service_dependencies.manage")), db: Session = Depends(get_db)):
    item, service, target = _locked_relationship(
        db, principal, ServiceDependency, dependency_id, "service_dependencies.manage", "Service dependency",
    )
    changes = payload.model_dump(exclude_unset=True)
    if "required_for_operation" in changes:
        semantics = _dependency_semantics(db, item, "service")
        if semantics["dependency_group_id"] is not None and changes["required_for_operation"] != (semantics["dependency_requirement"] == "required"):
            raise HTTPException(status_code=422, detail="Change the dependency group's requirement instead")
    old_relationship = db.get(RelationshipType, item.relationship_type_id)
    new_relationship = old_relationship
    if "relationship_type_id" in changes:
        new_relationship = _applicable_relationship(db, changes["relationship_type_id"], "service", "service")
    for key, value in changes.items(): setattr(item, key, value)
    item.updated_by_user_id = principal.user.id
    if new_relationship and old_relationship and new_relationship.id != old_relationship.id:
        _retract_dependency_assertion(db, service, old_relationship, "service", item.target_service_id, principal)
        assertion = _relationship_assertion(db, service=service, predicate=new_relationship.key, object_type="service", object_id=item.target_service_id, actor_user_id=principal.user.id)
        record_assertion_change(db, assertion=assertion, change_type="service_dependency_added", entity_name=service.name, summary=f"Changed the relationship to {target.name if target else 'a Service'} to {new_relationship.name}", actor_user_id=principal.user.id, metadata={"dependency_id": item.id, "previous_relationship_type_id": old_relationship.id})
    elif changes:
        record_change(db, customer_id=service.customer_id, site_id=service.site_id, change_type="service_updated", entity_type="service", entity_id=service.id, entity_name=service.name, summary=f"Updated the dependency on {target.name if target else 'a Service'}", actor_user_id=principal.user.id, metadata={"dependency_id": item.id, "changed_fields": sorted(changes)})
    flush(db, "Service dependency")
    response = _service_dependency_response(db, item, service, target)
    commit(db, "Service dependency")
    return response


@router.delete("/service-dependencies/{dependency_id}", status_code=status.HTTP_204_NO_CONTENT)
@concurrent_decision
def delete_service_dependency(dependency_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("service_dependencies.manage")), db: Session = Depends(get_db)):
    item, service, target = _locked_relationship(
        db, principal, ServiceDependency, dependency_id, "service_dependencies.manage", "Service dependency",
    )
    relationship = db.get(RelationshipType, item.relationship_type_id)
    effective_at = datetime.now(timezone.utc)
    item.valid_to = effective_at; item.ended_by_user_id = principal.user.id
    _end_dependency_membership(db, item, service, "service", principal, effective_at)
    _retract_dependency_assertion(db, service, relationship, "service", item.target_service_id, principal)
    record_change(db, customer_id=service.customer_id, site_id=service.site_id, change_type="service_dependency_removed", entity_type="service", entity_id=service.id, entity_name=service.name, summary=f"Removed dependency on {target.name if target else 'unavailable Service'}", actor_user_id=principal.user.id, metadata={"dependency_id": item.id})
    from app.services.knowledge_completeness import evaluate_service_safely
    for endpoint in (service, target):
        evaluate_service_safely(db, endpoint, trigger_context="service_dependency_removed", actor_user_id=principal.user.id)
    add_audit_event(db, action="service_dependency.ended", target_type="service_dependency", target_id=item.id, actor=principal.user, customer_id=service.customer_id, site_id=service.site_id, summary="Service dependency ended", request=request)
    commit(db, "Service dependency")


@router.get("/services/{service_id}/dependency-groups", response_model=list[DependencyGroupResponse])
def list_dependency_groups(
    service_id: uuid.UUID,
    principal: Principal = Depends(require_permission("service_dependencies.view")),
    include_history: bool = False,
    db: Session = Depends(get_db),
):
    service = _service(db, principal, service_id, "service_dependencies.view")
    query = select(DependencyGroup).where(DependencyGroup.service_id == service.id)
    if not include_history:
        query = query.where(DependencyGroup.valid_to.is_(None))
    groups = [
        _dependency_group_response(db, row)
        for row in db.scalars(query.order_by(DependencyGroup.valid_from, DependencyGroup.id))
        if (row.valid_to is not None or matches_service_scope(row, service))
        and principal.can("service_dependencies.view", row.customer_id, row.site_id)
    ]
    if not groups:
        return []
    asset_ids = {row["id"] for row in list_service_asset_dependencies(service_id, principal, include_history, db)}
    service_ids = {row["id"] for row in list_service_dependencies(service_id, principal, include_history, db)}
    # A partial member set would misrepresent all/any semantics. Return only
    # groups whose entire membership can be disclosed to this reader.
    return [
        group for group in groups
        if (group["asset_dependency_ids"] or group["service_dependency_ids"])
        and set(group["asset_dependency_ids"]) <= asset_ids
        and set(group["service_dependency_ids"]) <= service_ids
    ]


@router.post(
    "/services/{service_id}/dependency-groups",
    response_model=DependencyGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
@concurrent_decision
def create_dependency_group(
    service_id: uuid.UUID,
    payload: DependencyGroupCreate,
    request: Request,
    principal: Principal = Depends(require_permission("service_dependencies.manage")),
    db: Session = Depends(get_db),
):
    _service(db, principal, service_id, "service_dependencies.manage")
    _lock_group_endpoints(db, service_id, payload.asset_dependency_ids, payload.service_dependency_ids)
    principal = refresh_principal(principal, db)
    service = _service(db, principal, service_id, "service_dependencies.manage")
    asset_rows, service_rows = _validated_group_members(
        db,
        principal,
        service,
        payload.asset_dependency_ids,
        payload.service_dependency_ids,
    )
    effective_at = datetime.now(timezone.utc)
    group = DependencyGroup(
        customer_id=service.customer_id,
        site_id=service.site_id,
        service_id=service.id,
        name=payload.name,
        strategy=payload.strategy,
        requirement=payload.requirement,
        failure_effect=payload.failure_effect,
        valid_from=effective_at,
        created_by_user_id=principal.user.id,
    )
    db.add(group)
    flush(db, "Dependency group")
    _add_group_memberships(db, group, asset_rows, service_rows, principal, effective_at)
    record_change(
        db,
        customer_id=service.customer_id,
        site_id=service.site_id,
        change_type="service_updated",
        entity_type="service",
        entity_id=service.id,
        entity_name=service.name,
        summary=f"Added dependency behaviour {group.name}",
        actor_user_id=principal.user.id,
        metadata={"dependency_group_id": group.id, "strategy": group.strategy, "requirement": group.requirement, "failure_effect": group.failure_effect},
    )
    add_audit_event(
        db,
        action="dependency_group.created",
        target_type="dependency_group",
        target_id=group.id,
        actor=principal.user,
        customer_id=service.customer_id,
        site_id=service.site_id,
        summary="Dependency group created",
        request=request,
    )
    flush(db, "Dependency group")
    response = _dependency_group_response(db, group)
    commit(db, "Dependency group")
    return response


@router.patch("/dependency-groups/{group_id}", response_model=DependencyGroupResponse)
@concurrent_decision
def update_dependency_group(
    group_id: uuid.UUID,
    payload: DependencyGroupUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("service_dependencies.manage")),
    db: Session = Depends(get_db),
):
    changes = payload.model_dump(exclude_unset=True)
    principal, service, current, prior_memberships = _lock_current_group(
        db, principal, group_id, changes.get("asset_dependency_ids", ()), changes.get("service_dependency_ids", ()),
    )
    prior_asset_ids, prior_service_ids = _member_dependency_ids(prior_memberships)
    asset_ids = changes.pop("asset_dependency_ids", prior_asset_ids)
    service_ids = changes.pop("service_dependency_ids", prior_service_ids)
    if len(set(asset_ids)) != len(asset_ids) or len(set(service_ids)) != len(service_ids):
        raise HTTPException(status_code=422, detail="Dependency membership cannot be duplicated")
    values = {
        "name": current.name,
        "strategy": current.strategy,
        "requirement": current.requirement,
        "failure_effect": current.failure_effect,
        **changes,
    }
    asset_rows, service_rows = _validated_group_members(
        db,
        principal,
        service,
        asset_ids,
        service_ids,
        replacing_group_id=current.id,
    )
    effective_at = datetime.now(timezone.utc)
    current.valid_to = effective_at
    current.ended_by_user_id = principal.user.id
    for membership in prior_memberships:
        if membership.valid_to is None:
            membership.valid_to = effective_at
            membership.ended_by_user_id = principal.user.id
    replacement = DependencyGroup(
        customer_id=current.customer_id,
        site_id=current.site_id,
        service_id=current.service_id,
        supersedes_group_id=current.id,
        valid_from=effective_at,
        created_by_user_id=principal.user.id,
        **values,
    )
    db.add(replacement)
    flush(db, "Dependency group")
    _add_group_memberships(db, replacement, asset_rows, service_rows, principal, effective_at)
    record_change(
        db,
        customer_id=service.customer_id,
        site_id=service.site_id,
        change_type="service_updated",
        entity_type="service",
        entity_id=service.id,
        entity_name=service.name,
        summary=f"Updated dependency behaviour {replacement.name}",
        actor_user_id=principal.user.id,
        metadata={"dependency_group_id": replacement.id, "supersedes_group_id": current.id},
    )
    add_audit_event(
        db,
        action="dependency_group.updated",
        target_type="dependency_group",
        target_id=replacement.id,
        actor=principal.user,
        customer_id=service.customer_id,
        site_id=service.site_id,
        summary="Dependency group updated",
        request=request,
    )
    flush(db, "Dependency group")
    response = _dependency_group_response(db, replacement)
    commit(db, "Dependency group")
    return response


@router.delete("/dependency-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
@concurrent_decision
def delete_dependency_group(
    group_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_permission("service_dependencies.manage")),
    db: Session = Depends(get_db),
):
    principal, service, group, memberships = _lock_current_group(db, principal, group_id)
    effective_at = datetime.now(timezone.utc)
    group.valid_to = effective_at
    group.ended_by_user_id = principal.user.id
    for membership in memberships:
        if membership.valid_to is None:
            membership.valid_to = effective_at
            membership.ended_by_user_id = principal.user.id
    record_change(
        db,
        customer_id=service.customer_id,
        site_id=service.site_id,
        change_type="service_updated",
        entity_type="service",
        entity_id=service.id,
        entity_name=service.name,
        summary=f"Removed dependency behaviour {group.name}",
        actor_user_id=principal.user.id,
        metadata={"dependency_group_id": group.id},
    )
    add_audit_event(
        db,
        action="dependency_group.ended",
        target_type="dependency_group",
        target_id=group.id,
        actor=principal.user,
        customer_id=service.customer_id,
        site_id=service.site_id,
        summary="Dependency group ended",
        request=request,
    )
    commit(db, "Dependency group")


def _business_function_link_response(db: Session, item: ServiceBusinessFunction, service: Service, function: BusinessFunction) -> dict:
    relationship = db.get(RelationshipType, item.relationship_type_id) if item.relationship_type_id else None
    result = ServiceBusinessFunctionResponse.model_validate(item).model_dump()
    result.update(service_name=service.name if service else None, business_function_name=function.name if function else None, relationship_type_name=relationship.name if relationship else None, relationship_label=relationship.source_label if relationship else "Supports")
    return result


@router.get("/services/{service_id}/business-functions", response_model=list[ServiceBusinessFunctionResponse])
def list_service_business_functions(service_id: uuid.UUID, principal: Principal = Depends(require_permission("business_functions.view")), include_history: bool = False, db: Session = Depends(get_db)):
    service = _service(db, principal, service_id, "business_functions.view")
    query = visible_relationships(ServiceBusinessFunction, principal, include_history=include_history).where(
        ServiceBusinessFunction.service_id == service.id,
    )
    rows = list(db.execute(query.order_by(ServiceBusinessFunction.created_at)))
    return [_business_function_link_response(db, row, source, target) for source, target, row in rows]



@router.post("/services/{service_id}/business-functions", response_model=ServiceBusinessFunctionResponse, status_code=status.HTTP_201_CREATED)
@concurrent_decision
def link_business_function(service_id: uuid.UUID, payload: ServiceBusinessFunctionCreate, request: Request, principal: Principal = Depends(require_permission("business_functions.manage")), db: Session = Depends(get_db)):
    _lock_relationship_endpoints(db, service_id, function_ids=(payload.business_function_id,))
    principal = refresh_principal(principal, db)
    item, service, function = add_business_function_link(db, service_id, payload, principal, request)
    response = _business_function_link_response(db, item, service, function)
    commit(db, "Service business function")
    return response


def add_business_function_link(
    db: Session, service_id: uuid.UUID, payload: ServiceBusinessFunctionCreate, principal: Principal, request: Request,
) -> tuple[ServiceBusinessFunction, Service, BusinessFunction]:
    """Link endpoints already locked by the caller or created in its transaction."""
    service = _service(db, principal, service_id, "business_functions.manage")
    function = _target(db, principal, ServiceBusinessFunction, payload.business_function_id, "business_functions.manage")
    if not compatible_target_scope(service, function):
        raise HTTPException(422, detail="Business Function is outside the Service customer/site scope")
    relationship = _applicable_relationship(db, payload.relationship_type_id, "service", "business_function") if payload.relationship_type_id else None
    item = ServiceBusinessFunction(customer_id=service.customer_id, site_id=service.site_id, service_id=service.id, business_function_id=function.id, relationship_type_id=payload.relationship_type_id, is_primary=payload.is_primary, importance=payload.importance, description=payload.description, created_by_user_id=principal.user.id)
    db.add(item); flush(db, "Service business function")
    assertion = _relationship_assertion(db, service=service, predicate=relationship.key if relationship else "supports", object_type="business_function", object_id=function.id, actor_user_id=principal.user.id)
    record_assertion_change(db, assertion=assertion, change_type="service_business_function_added", entity_name=service.name, summary=f"Linked {service.name} to {function.name}", actor_user_id=principal.user.id, metadata={"link_id": item.id, "business_function_id": function.id})
    from app.services.knowledge_completeness import evaluate_service_safely
    evaluate_service_safely(db, service, trigger_context="business_function_added", actor_user_id=principal.user.id)
    add_audit_event(db, action="service_business_function.created", target_type="service_business_function", target_id=item.id, actor=principal.user, customer_id=service.customer_id, site_id=service.site_id, summary="Service Business Function link created", request=request)
    return item, service, function


@router.patch("/service-business-functions/{link_id}", response_model=ServiceBusinessFunctionResponse)
@concurrent_decision
def update_business_function_link(link_id: uuid.UUID, payload: ServiceBusinessFunctionUpdate, principal: Principal = Depends(require_permission("business_functions.manage")), db: Session = Depends(get_db)):
    item, service, function = _locked_relationship(
        db, principal, ServiceBusinessFunction, link_id, "business_functions.manage", "Service Business Function link",
    )
    changes = payload.model_dump(exclude_unset=True)
    old_relationship = db.get(RelationshipType, item.relationship_type_id) if item.relationship_type_id else None
    new_relationship = old_relationship
    if "relationship_type_id" in changes:
        new_relationship = _applicable_relationship(db, changes["relationship_type_id"], "service", "business_function") if changes["relationship_type_id"] else None
    for key, value in changes.items(): setattr(item, key, value)
    old_predicate = old_relationship.key if old_relationship else "supports"
    new_predicate = new_relationship.key if new_relationship else "supports"
    if new_predicate != old_predicate:
        _retract_dependency_assertion(db, service, old_predicate, "business_function", item.business_function_id, principal)
        assertion = _relationship_assertion(db, service=service, predicate=new_predicate, object_type="business_function", object_id=item.business_function_id, actor_user_id=principal.user.id)
        record_assertion_change(db, assertion=assertion, change_type="service_business_function_added", entity_name=service.name, summary=f"Changed how {service.name} supports {function.name if function else 'a Business Function'}", actor_user_id=principal.user.id, metadata={"link_id": item.id, "previous_relationship_type_id": old_relationship.id if old_relationship else None})
    elif changes:
        record_change(db, customer_id=service.customer_id, site_id=service.site_id, change_type="service_updated", entity_type="service", entity_id=service.id, entity_name=service.name, summary=f"Updated the link to {function.name if function else 'a Business Function'}", actor_user_id=principal.user.id, metadata={"link_id": item.id, "changed_fields": sorted(changes)})
    flush(db, "Service business function")
    response = _business_function_link_response(db, item, service, function)
    commit(db, "Service business function")
    return response


@router.delete("/service-business-functions/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
@concurrent_decision
def delete_business_function_link(link_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("business_functions.manage")), db: Session = Depends(get_db)):
    item, service, function = _locked_relationship(
        db, principal, ServiceBusinessFunction, link_id, "business_functions.manage", "Service Business Function link",
    )
    item.valid_to = datetime.now(timezone.utc); item.ended_by_user_id = principal.user.id
    relationship = db.get(RelationshipType, item.relationship_type_id) if item.relationship_type_id else None
    _retract_dependency_assertion(db, service, relationship or "supports", "business_function", item.business_function_id, principal)
    record_change(db, customer_id=service.customer_id, site_id=service.site_id, change_type="service_business_function_removed", entity_type="service", entity_id=service.id, entity_name=service.name, summary=f"Unlinked {function.name if function else 'Business Function'} from {service.name}", actor_user_id=principal.user.id, metadata={"link_id": item.id})
    from app.services.knowledge_completeness import evaluate_service_safely
    evaluate_service_safely(db, service, trigger_context="business_function_removed", actor_user_id=principal.user.id)
    add_audit_event(db, action="service_business_function.ended", target_type="service_business_function", target_id=item.id, actor=principal.user, customer_id=service.customer_id, site_id=service.site_id, summary="Service Business Function link ended", request=request)
    commit(db, "Service business function")


@router.get("/services/{service_id}/history", response_model=list[KnowledgeChangeResponse])
def service_history(service_id: uuid.UUID, principal: Principal = Depends(require_permission("changes.view")), limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)):
    service = _service(db, principal, service_id, "changes.view")
    rows = db.scalars(select(KnowledgeChange).where(
        KnowledgeChange.entity_type == "service", KnowledgeChange.entity_id == service.id,
        scope_condition(principal, "changes.view", KnowledgeChange.customer_id, KnowledgeChange.site_id),
    ).order_by(KnowledgeChange.occurred_at.desc()).limit(limit))
    return [_change_response(db, row) for row in rows]


@router.get("/services/{service_id}/assertions", response_model=list[KnowledgeAssertionResponse])
def service_assertions(service_id: uuid.UUID, principal: Principal = Depends(require_permission("services.view")), current_only: bool = False, db: Session = Depends(get_db)):
    service = _service(db, principal, service_id, "services.view")
    query = select(KnowledgeAssertion).where(
        KnowledgeAssertion.subject_type == "service", KnowledgeAssertion.subject_id == service.id,
        scope_condition(principal, "services.view", KnowledgeAssertion.customer_id, KnowledgeAssertion.site_id),
        visible_service_relationship_assertion(principal),
    )
    if current_only: query = query.where(KnowledgeAssertion.is_source_current.is_(True), KnowledgeAssertion.retracted_at.is_(None))
    return [assertion_response(db, row) for row in db.scalars(query.order_by(KnowledgeAssertion.last_observed_at.desc()))]


@router.get("/services/{service_id}/graph", response_model=ServiceGraphResponse)
def service_graph(
    service_id: uuid.UUID,
    context: RequestContext,
    principal: Principal = Depends(require_permission("service_dependencies.view")),
    db: Session = Depends(get_db),
):
    try:
        graph = OperationalGraphBuilder(db, principal).build(
            GraphProjectionRequest(
                focus_type="service",
                focus_id=service_id,
                max_depth=2,
                node_limit=500,
                context=context,
                include_inactive_focus=True,
                edge_families_by_depth=(
                    frozenset(
                        {
                            "service_asset",
                            "service_service",
                            "service_business_function",
                        }
                    ),
                    frozenset({"asset_relationship"}),
                ),
            )
        )
    except GraphFocusNotFound:
        raise not_found("Service")
    return operational_graph_to_service_graph(graph)


@router.get("/services/{service_id}/deletion-eligibility", response_model=EntityDeletionEligibilityResponse)
def service_deletion_eligibility(service_id: uuid.UUID, principal: Principal = Depends(require_permission("services.archive")), db: Session = Depends(get_db)):
    from app.services.entity_lifecycle import deletion_eligible, MESSAGE
    item = _service(db, principal, service_id, "services.archive")
    eligible = deletion_eligible(db, item)
    return {"eligible": eligible, "reason": None if eligible else MESSAGE.format(label="Service")}


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(service_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("services.archive")), db: Session = Depends(get_db)):
    from app.services.entity_lifecycle import delete_mistake
    delete_mistake(db, _service(db, principal, service_id, "services.archive"), principal, request)
