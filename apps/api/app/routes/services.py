"""First-class Service CRUD, dependency, provenance, and graph APIs."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, RequestContext, require_permission, require_scope, scope_condition
from app.database import get_db
from app.models import (
    Asset, BusinessFunction, CriticalityLevel, DependencyGroup,
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
from app.services.knowledge_assertions import accept_assertion, record_assertion
from app.services.knowledge_changes import record_assertion_change, record_change
from app.services.knowledge_lifecycle import retract_assertion
from app.services.manual_knowledge import MANUAL_SERVICE_KNOWLEDGE_FIELDS, declare_service_changes
from app.services.operational_graph import (
    GraphFocusNotFound,
    GraphProjectionRequest,
    OperationalGraphBuilder,
    operational_graph_to_service_graph,
)

router = APIRouter(tags=["services"])


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return result[:255] or "service"


def _service(db: Session, principal: Principal, service_id: uuid.UUID, permission: str) -> Service:
    item = db.get(Service, service_id)
    if item is None:
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


def _active_type(db: Session, model, item_id: uuid.UUID, label: str, *, allow_inactive_id: uuid.UUID | None = None):
    item = db.get(model, item_id)
    if item is None or (not item.active and item.id != allow_inactive_id):
        raise HTTPException(status_code=422, detail=f"{label} is not active or does not exist")
    return item


def service_response(db: Session, item: Service, principal: Principal) -> dict:
    service_type = db.get(ServiceType, item.service_type_id)
    criticality = db.get(CriticalityLevel, item.criticality_level_id)
    summary = db.scalar(select(KnowledgeCompletenessSummary).where(
        KnowledgeCompletenessSummary.entity_type == "service",
        KnowledgeCompletenessSummary.entity_id == item.id,
    )) if principal.can("knowledge_gaps.view", item.customer_id, item.site_id) else None
    open_gaps = list(db.scalars(select(KnowledgeGap).where(
        KnowledgeGap.entity_type == "service",
        KnowledgeGap.entity_id == item.id,
        KnowledgeGap.status.in_({"open", "deferred"}),
    ))) if principal.can("knowledge_gaps.view", item.customer_id, item.site_id) else []
    visible_assets = select(Asset.id).where(Asset.customer_id == item.customer_id, scope_condition(principal, "assets.view", Asset.customer_id, Asset.site_id))
    visible_services = select(Service.id).where(Service.customer_id == item.customer_id, scope_condition(principal, "services.view", Service.customer_id, Service.site_id))
    visible_functions = select(BusinessFunction.id).where(BusinessFunction.customer_id == item.customer_id, scope_condition(principal, "business_functions.view", BusinessFunction.customer_id, BusinessFunction.site_id))
    can_dependencies = principal.can("service_dependencies.view", item.customer_id, item.site_id)
    can_functions = principal.can("business_functions.view", item.customer_id, item.site_id)
    result = ServiceResponse.model_validate(item).model_dump()
    result.update(
        service_type_key=service_type.key if service_type else None,
        service_type_name=service_type.name if service_type else None,
        criticality_key=criticality.key if criticality else None,
        criticality_name=criticality.name if criticality else None,
        criticality_rank=criticality.rank if criticality else None,
        suggested_rto_minutes=criticality.default_rto_minutes if criticality else None,
        suggested_rpo_minutes=criticality.default_rpo_minutes if criticality else None,
        asset_dependency_count=int(db.scalar(select(func.count()).select_from(ServiceAssetDependency).where(ServiceAssetDependency.service_id == item.id, ServiceAssetDependency.valid_to.is_(None), ServiceAssetDependency.asset_id.in_(visible_assets))) or 0) if can_dependencies else 0,
        service_dependency_count=int(db.scalar(select(func.count()).select_from(ServiceDependency).where(or_(ServiceDependency.source_service_id == item.id, ServiceDependency.target_service_id == item.id), ServiceDependency.valid_to.is_(None), ServiceDependency.source_service_id.in_(visible_services), ServiceDependency.target_service_id.in_(visible_services))) or 0) if can_dependencies else 0,
        business_function_count=int(db.scalar(select(func.count()).select_from(ServiceBusinessFunction).where(ServiceBusinessFunction.service_id == item.id, ServiceBusinessFunction.valid_to.is_(None), ServiceBusinessFunction.business_function_id.in_(visible_functions))) or 0) if can_functions else 0,
        completeness_status=summary.completeness_status if summary else "not_evaluated",
        open_gap_count=summary.open_gap_count if summary else 0,
        required_gap_count=sum(gap.requirement_level in {"required", "conditional"} for gap in open_gaps),
        recommended_gap_count=sum(gap.requirement_level == "recommended" for gap in open_gaps),
    )
    return result


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
            ServiceBusinessFunction.valid_to.is_(None),
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
            query = query.where(~select(ServiceAssetDependency.id).where(ServiceAssetDependency.service_id == Service.id, ServiceAssetDependency.valid_to.is_(None)).exists())
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
    _active_type(db, ServiceType, payload.service_type_id, "Service type")
    _active_type(db, CriticalityLevel, payload.criticality_level_id, "Criticality level")
    values = payload.model_dump()
    values["slug"] = payload.slug or _slug(payload.name)
    item = Service(**values, source="manual", created_by_user_id=principal.user.id, updated_by_user_id=principal.user.id)
    db.add(item)
    flush(db, "Service")
    declare_service_changes(db, service=item, previous_values={field: None for field in MANUAL_SERVICE_KNOWLEDGE_FIELDS}, actor_user_id=principal.user.id, record_changes=False)
    record_change(db, customer_id=item.customer_id, site_id=item.site_id, change_type="service_created", entity_type="service", entity_id=item.id, entity_name=item.name, summary=f"Created Service {item.name}", actor_user_id=principal.user.id)
    from app.services.knowledge_completeness import evaluate_service_safely
    evaluate_service_safely(db, item, trigger_context="service_created", actor_user_id=principal.user.id)
    add_audit_event(db, action="service.created", target_type="service", target_id=item.id, actor=principal.user, customer_id=item.customer_id, site_id=item.site_id, summary="Service created", request=request)
    commit(db, "Service")
    db.refresh(item)
    return service_response(db, item, principal)


@router.get("/services/{service_id}", response_model=ServiceResponse)
def get_service(service_id: uuid.UUID, principal: Principal = Depends(require_permission("services.view")), db: Session = Depends(get_db)):
    return service_response(db, _service(db, principal, service_id, "services.view"), principal)


@router.patch("/services/{service_id}", response_model=ServiceResponse)
def update_service(service_id: uuid.UUID, payload: ServiceUpdate, request: Request, context: RequestContext, principal: Principal = Depends(require_permission("services.edit")), db: Session = Depends(get_db)):
    item = _service(db, principal, service_id, "services.edit")
    changes = payload.model_dump(exclude_unset=True)
    new_site_id = changes.get("site_id", item.site_id)
    if context.site_id and new_site_id != context.site_id:
        raise HTTPException(status_code=403, detail="Service site must match the active context")
    _validate_context(db, principal, "services.edit", item.customer_id, new_site_id)
    if new_site_id != item.site_id:
        dependency_count = sum(int(db.scalar(query) or 0) for query in (
            select(func.count()).select_from(ServiceAssetDependency).where(ServiceAssetDependency.service_id == item.id, ServiceAssetDependency.valid_to.is_(None)),
            select(func.count()).select_from(ServiceDependency).where(or_(ServiceDependency.source_service_id == item.id, ServiceDependency.target_service_id == item.id), ServiceDependency.valid_to.is_(None)),
            select(func.count()).select_from(ServiceBusinessFunction).where(ServiceBusinessFunction.service_id == item.id, ServiceBusinessFunction.valid_to.is_(None)),
        ))
        if dependency_count:
            raise HTTPException(status_code=409, detail="A Service with dependencies cannot be moved to another site")
    if "service_type_id" in changes:
        _active_type(db, ServiceType, changes["service_type_id"], "Service type", allow_inactive_id=item.service_type_id)
    if "criticality_level_id" in changes:
        _active_type(db, CriticalityLevel, changes["criticality_level_id"], "Criticality level", allow_inactive_id=item.criticality_level_id)
    previous = {field: getattr(item, field) for field in MANUAL_SERVICE_KNOWLEDGE_FIELDS if field in changes}
    if "name" in changes and "slug" not in changes and item.slug == _slug(item.name):
        changes["slug"] = _slug(changes["name"])
    semantic_changes = {key: value for key, value in changes.items() if getattr(item, key) != value}
    if not semantic_changes:
        return service_response(db, item, principal)
    for key, value in semantic_changes.items():
        setattr(item, key, value)
    item.updated_by_user_id = principal.user.id
    flush(db, "Service")
    declare_service_changes(db, service=item, previous_values=previous, actor_user_id=principal.user.id)
    from app.services.knowledge_completeness import evaluate_service_safely
    evaluate_service_safely(db, item, trigger_context="service_updated", actor_user_id=principal.user.id)
    add_audit_event(db, action="service.updated", target_type="service", target_id=item.id, actor=principal.user, customer_id=item.customer_id, site_id=item.site_id, summary="Service updated", metadata={"changed_fields": sorted(semantic_changes)}, request=request)
    commit(db, "Service")
    db.refresh(item)
    return service_response(db, item, principal)


@router.post("/services/{service_id}/archive", response_model=ServiceResponse)
def archive_service(service_id: uuid.UUID, payload: ServiceArchiveRequest, request: Request, principal: Principal = Depends(require_permission("services.archive")), db: Session = Depends(get_db)):
    item = _service(db, principal, service_id, "services.archive")
    if item.archived_at is None:
        item.archived_at = datetime.now(timezone.utc); item.archived_by_user_id = principal.user.id; item.archive_reason = payload.reason
        record_change(db, customer_id=item.customer_id, site_id=item.site_id, change_type="service_archived", entity_type="service", entity_id=item.id, entity_name=item.name, summary=f"Archived Service {item.name}", actor_user_id=principal.user.id, metadata={"reason": payload.reason})
        add_audit_event(db, action="service.archived", target_type="service", target_id=item.id, actor=principal.user, customer_id=item.customer_id, site_id=item.site_id, summary="Service archived", request=request)
        commit(db, "Service archive")
    return service_response(db, item, principal)


@router.post("/services/{service_id}/restore", response_model=ServiceResponse)
def restore_service(service_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("services.archive")), db: Session = Depends(get_db)):
    item = _service(db, principal, service_id, "services.archive")
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


def _asset_dependency_response(db: Session, item: ServiceAssetDependency, semantics: dict | None = None) -> dict:
    service, asset, relationship = db.get(Service, item.service_id), db.get(Asset, item.asset_id), db.get(RelationshipType, item.relationship_type_id)
    result = ServiceAssetDependencyResponse.model_validate(item).model_dump()
    result.update(service_name=service.name if service else None, asset_name=asset.name if asset else None, asset_type=asset.asset_type if asset else None, relationship_type_name=relationship.name if relationship else None, source_label=relationship.source_label if relationship else None, target_label=relationship.target_label if relationship else None, **(semantics or _dependency_semantics(db, item, "asset")))
    return result


def _service_dependency_response(db: Session, item: ServiceDependency, semantics: dict | None = None) -> dict:
    source, target, relationship = db.get(Service, item.source_service_id), db.get(Service, item.target_service_id), db.get(RelationshipType, item.relationship_type_id)
    result = ServiceDependencyResponse.model_validate(item).model_dump()
    result.update(source_service_name=source.name if source else None, target_service_name=target.name if target else None, relationship_type_name=relationship.name if relationship else None, source_label=relationship.source_label if relationship else None, target_label=relationship.target_label if relationship else None, **(semantics or _dependency_semantics(db, item, "service")))
    return result


def _dependency_semantics(db: Session, item, dependency_kind: str) -> dict:
    dependency_column = (
        DependencyGroupMembership.service_asset_dependency_id
        if dependency_kind == "asset"
        else DependencyGroupMembership.service_dependency_id
    )
    membership = db.scalar(
        select(DependencyGroupMembership).where(
            dependency_column == item.id,
            DependencyGroupMembership.valid_to.is_(None),
        )
    )
    group = db.get(DependencyGroup, membership.dependency_group_id) if membership else None
    if group is None or group.valid_to is not None:
        return {
            "dependency_group_id": None,
            "dependency_group_name": None,
            "dependency_strategy": None,
            "dependency_requirement": "required" if item.required_for_operation else "optional",
            "failure_effect": "unknown",
        }
    return {
        "dependency_group_id": group.id,
        "dependency_group_name": group.name,
        "dependency_strategy": group.strategy,
        "dependency_requirement": group.requirement,
        "failure_effect": group.failure_effect,
    }


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
    return list(db.scalars(query.order_by(
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
    for dependency_id in asset_dependency_ids:
        row = db.get(ServiceAssetDependency, dependency_id)
        if (
            row is None
            or row.valid_to is not None
            or row.service_id != service.id
            or row.customer_id != service.customer_id
            or row.site_id != service.site_id
        ):
            raise not_found("Service asset dependency")
        require_scope(principal, "service_dependencies.manage", row.customer_id, row.site_id, hide_existence=True)
        asset_rows.append(row)
    for dependency_id in service_dependency_ids:
        row = db.get(ServiceDependency, dependency_id)
        if (
            row is None
            or row.valid_to is not None
            or row.source_service_id != service.id
            or row.customer_id != service.customer_id
            or row.site_id != service.site_id
        ):
            raise not_found("Service dependency")
        require_scope(principal, "service_dependencies.manage", row.customer_id, row.site_id, hide_existence=True)
        service_rows.append(row)

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


def _end_dependency_membership(db: Session, dependency_id: uuid.UUID, dependency_kind: str, principal: Principal, effective_at: datetime) -> None:
    column = (
        DependencyGroupMembership.service_asset_dependency_id
        if dependency_kind == "asset"
        else DependencyGroupMembership.service_dependency_id
    )
    membership = db.scalar(select(DependencyGroupMembership).where(
        column == dependency_id,
        DependencyGroupMembership.valid_to.is_(None),
    ))
    if membership is None:
        return
    membership.valid_to = effective_at
    membership.ended_by_user_id = principal.user.id
    remaining = db.scalar(select(func.count()).select_from(DependencyGroupMembership).where(
        DependencyGroupMembership.dependency_group_id == membership.dependency_group_id,
        DependencyGroupMembership.id != membership.id,
        DependencyGroupMembership.valid_to.is_(None),
    ))
    if not remaining:
        group = db.get(DependencyGroup, membership.dependency_group_id)
        if group and group.valid_to is None:
            group.valid_to = effective_at
            group.ended_by_user_id = principal.user.id


def _relationship_assertion(db: Session, *, service: Service, predicate: str, object_type: str, object_id: uuid.UUID, actor_user_id: uuid.UUID) -> KnowledgeAssertion:
    from app.services.data_sources import manual_inventory_source
    source = manual_inventory_source(db, service.customer_id, service.site_id)
    assertion, _ = record_assertion(db, customer_id=service.customer_id, site_id=service.site_id, subject_type="service", subject_id=service.id, predicate=predicate, object_type=object_type, object_id=object_id, truth_classification="declared", data_source_id=source.id)
    accept_assertion(db, assertion, user_id=actor_user_id)
    return assertion


@router.get("/services/{service_id}/asset-dependencies", response_model=list[ServiceAssetDependencyResponse])
def list_service_asset_dependencies(service_id: uuid.UUID, principal: Principal = Depends(require_permission("service_dependencies.view")), include_history: bool = False, db: Session = Depends(get_db)):
    item = _service(db, principal, service_id, "service_dependencies.view")
    query = select(ServiceAssetDependency).where(ServiceAssetDependency.service_id == item.id)
    if not include_history: query = query.where(ServiceAssetDependency.valid_to.is_(None))
    rows = list(db.scalars(query.order_by(ServiceAssetDependency.created_at)))
    visible = _visible_related_ids(db, principal, Asset, (row.asset_id for row in rows), "assets.view", item.customer_id)
    rows = [row for row in rows if row.asset_id in visible]
    semantics = _dependency_semantics_by_id(db, rows, "asset")
    return [_asset_dependency_response(db, row, semantics[row.id]) for row in rows]


@router.post("/services/{service_id}/asset-dependencies", response_model=ServiceAssetDependencyResponse, status_code=status.HTTP_201_CREATED)
def create_service_asset_dependency(service_id: uuid.UUID, payload: ServiceAssetDependencyCreate, request: Request, principal: Principal = Depends(require_permission("service_dependencies.manage")), db: Session = Depends(get_db)):
    service = _service(db, principal, service_id, "service_dependencies.manage")
    asset = db.get(Asset, payload.asset_id)
    if asset is None: raise not_found("Asset")
    require_scope(principal, "service_dependencies.manage", asset.customer_id, asset.site_id, hide_existence=True)
    if asset.customer_id != service.customer_id or (service.site_id is not None and asset.site_id != service.site_id):
        raise HTTPException(status_code=422, detail="Asset is outside the Service customer/site scope")
    relationship = _applicable_relationship(db, payload.relationship_type_id, "service", "asset")
    item = ServiceAssetDependency(customer_id=service.customer_id, site_id=service.site_id, service_id=service.id, asset_id=asset.id, relationship_type_id=relationship.id, required_for_operation=payload.required_for_operation, description=payload.description, source="manual", created_by_user_id=principal.user.id, updated_by_user_id=principal.user.id)
    db.add(item); flush(db, "Service asset dependency")
    assertion = _relationship_assertion(db, service=service, predicate=relationship.key, object_type="asset", object_id=asset.id, actor_user_id=principal.user.id)
    record_assertion_change(db, assertion=assertion, change_type="service_dependency_added", entity_name=service.name, summary=f"{service.name} {relationship.source_label.lower()} {asset.name}", actor_user_id=principal.user.id, metadata={"dependency_id": item.id, "target_name": asset.name})
    from app.services.knowledge_completeness import evaluate_service_safely
    evaluate_service_safely(db, service, trigger_context="service_dependency_added", actor_user_id=principal.user.id)
    add_audit_event(db, action="service_asset_dependency.created", target_type="service_asset_dependency", target_id=item.id, actor=principal.user, customer_id=service.customer_id, site_id=service.site_id, summary="Service asset dependency created", request=request)
    commit(db, "Service asset dependency"); db.refresh(item)
    return _asset_dependency_response(db, item)


@router.patch("/service-asset-dependencies/{dependency_id}", response_model=ServiceAssetDependencyResponse)
def update_service_asset_dependency(dependency_id: uuid.UUID, payload: ServiceAssetDependencyUpdate, principal: Principal = Depends(require_permission("service_dependencies.manage")), db: Session = Depends(get_db)):
    item = db.get(ServiceAssetDependency, dependency_id)
    if item is None or item.valid_to is not None: raise not_found("Service asset dependency")
    service = _service(db, principal, item.service_id, "service_dependencies.manage")
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
    asset = db.get(Asset, item.asset_id)
    if new_relationship and old_relationship and new_relationship.id != old_relationship.id:
        _retract_dependency_assertion(db, service, old_relationship, "asset", item.asset_id, principal)
        assertion = _relationship_assertion(db, service=service, predicate=new_relationship.key, object_type="asset", object_id=item.asset_id, actor_user_id=principal.user.id)
        record_assertion_change(db, assertion=assertion, change_type="service_dependency_added", entity_name=service.name, summary=f"Changed the relationship to {asset.name if asset else 'an Asset'} to {new_relationship.name}", actor_user_id=principal.user.id, metadata={"dependency_id": item.id, "previous_relationship_type_id": old_relationship.id})
    elif changes:
        record_change(db, customer_id=service.customer_id, site_id=service.site_id, change_type="service_updated", entity_type="service", entity_id=service.id, entity_name=service.name, summary=f"Updated the dependency on {asset.name if asset else 'an Asset'}", actor_user_id=principal.user.id, metadata={"dependency_id": item.id, "changed_fields": sorted(changes)})
    commit(db, "Service asset dependency")
    return _asset_dependency_response(db, item)


def _retract_dependency_assertion(db: Session, service: Service, relationship: RelationshipType | str | None, object_type: str, object_id: uuid.UUID, principal: Principal) -> None:
    predicate = relationship if isinstance(relationship, str) else relationship.key if relationship else None
    if predicate is None: return
    assertion = db.scalar(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_type == "service", KnowledgeAssertion.subject_id == service.id, KnowledgeAssertion.predicate == predicate, KnowledgeAssertion.object_type == object_type, KnowledgeAssertion.object_id == object_id, KnowledgeAssertion.retracted_at.is_(None)).order_by(KnowledgeAssertion.created_at.desc()))
    if assertion: retract_assertion(db, assertion, user=principal.user, reason="Manual Service dependency removed", confirm_provenance_gap=True)


@router.delete("/service-asset-dependencies/{dependency_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service_asset_dependency(dependency_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("service_dependencies.manage")), db: Session = Depends(get_db)):
    item = db.get(ServiceAssetDependency, dependency_id)
    if item is None or item.valid_to is not None: raise not_found("Service asset dependency")
    service = _service(db, principal, item.service_id, "service_dependencies.manage"); asset = db.get(Asset, item.asset_id); relationship = db.get(RelationshipType, item.relationship_type_id)
    effective_at = datetime.now(timezone.utc)
    item.valid_to = effective_at; item.ended_by_user_id = principal.user.id
    _end_dependency_membership(db, item.id, "asset", principal, effective_at)
    _retract_dependency_assertion(db, service, relationship, "asset", item.asset_id, principal)
    record_change(db, customer_id=service.customer_id, site_id=service.site_id, change_type="service_dependency_removed", entity_type="service", entity_id=service.id, entity_name=service.name, summary=f"Removed dependency on {asset.name if asset else 'unavailable asset'}", actor_user_id=principal.user.id, metadata={"dependency_id": item.id, "relationship_type_id": item.relationship_type_id})
    from app.services.knowledge_completeness import evaluate_service_safely
    evaluate_service_safely(db, service, trigger_context="service_dependency_removed", actor_user_id=principal.user.id)
    add_audit_event(db, action="service_asset_dependency.ended", target_type="service_asset_dependency", target_id=item.id, actor=principal.user, customer_id=service.customer_id, site_id=service.site_id, summary="Service asset dependency ended", request=request)
    commit(db, "Service asset dependency")


@router.get("/services/{service_id}/service-dependencies", response_model=list[ServiceDependencyResponse])
def list_service_dependencies(service_id: uuid.UUID, principal: Principal = Depends(require_permission("service_dependencies.view")), include_history: bool = False, db: Session = Depends(get_db)):
    service = _service(db, principal, service_id, "service_dependencies.view")
    query = select(ServiceDependency).where(or_(ServiceDependency.source_service_id == service.id, ServiceDependency.target_service_id == service.id))
    if not include_history: query = query.where(ServiceDependency.valid_to.is_(None))
    rows = list(db.scalars(query.order_by(ServiceDependency.created_at)))
    visible = _visible_related_ids(db, principal, Service, (entity_id for row in rows for entity_id in (row.source_service_id, row.target_service_id)), "services.view", service.customer_id)
    rows = [row for row in rows if row.source_service_id in visible and row.target_service_id in visible]
    semantics = _dependency_semantics_by_id(db, rows, "service")
    return [_service_dependency_response(db, row, semantics[row.id]) for row in rows]


@router.post("/services/{service_id}/service-dependencies", response_model=ServiceDependencyResponse, status_code=status.HTTP_201_CREATED)
def create_service_dependency(service_id: uuid.UUID, payload: ServiceDependencyCreate, request: Request, principal: Principal = Depends(require_permission("service_dependencies.manage")), db: Session = Depends(get_db)):
    source = _service(db, principal, service_id, "service_dependencies.manage")
    target = db.get(Service, payload.target_service_id)
    if target is None: raise not_found("Target Service")
    require_scope(principal, "service_dependencies.manage", target.customer_id, target.site_id, hide_existence=True)
    if target.id == source.id: raise HTTPException(status_code=422, detail="A Service cannot depend on itself")
    if target.customer_id != source.customer_id or (source.site_id is not None and target.site_id not in {None, source.site_id}): raise HTTPException(status_code=422, detail="Target Service is outside the customer/site scope")
    relationship = _applicable_relationship(db, payload.relationship_type_id, "service", "service")
    item = ServiceDependency(customer_id=source.customer_id, site_id=source.site_id, source_service_id=source.id, target_service_id=target.id, relationship_type_id=relationship.id, required_for_operation=payload.required_for_operation, description=payload.description, created_by_user_id=principal.user.id, updated_by_user_id=principal.user.id)
    db.add(item); flush(db, "Service dependency")
    assertion = _relationship_assertion(db, service=source, predicate=relationship.key, object_type="service", object_id=target.id, actor_user_id=principal.user.id)
    record_assertion_change(db, assertion=assertion, change_type="service_dependency_added", entity_name=source.name, summary=f"{source.name} {relationship.source_label.lower()} {target.name}", actor_user_id=principal.user.id, metadata={"dependency_id": item.id, "target_name": target.name})
    from app.services.knowledge_completeness import evaluate_service_safely
    evaluate_service_safely(db, source, trigger_context="service_dependency_added", actor_user_id=principal.user.id)
    add_audit_event(db, action="service_dependency.created", target_type="service_dependency", target_id=item.id, actor=principal.user, customer_id=source.customer_id, site_id=source.site_id, summary="Service dependency created", request=request)
    commit(db, "Service dependency"); db.refresh(item)
    return _service_dependency_response(db, item)


@router.patch("/service-dependencies/{dependency_id}", response_model=ServiceDependencyResponse)
def update_service_dependency(dependency_id: uuid.UUID, payload: ServiceDependencyUpdate, principal: Principal = Depends(require_permission("service_dependencies.manage")), db: Session = Depends(get_db)):
    item = db.get(ServiceDependency, dependency_id)
    if item is None or item.valid_to is not None: raise not_found("Service dependency")
    service = _service(db, principal, item.source_service_id, "service_dependencies.manage")
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
    target = db.get(Service, item.target_service_id)
    if new_relationship and old_relationship and new_relationship.id != old_relationship.id:
        _retract_dependency_assertion(db, service, old_relationship, "service", item.target_service_id, principal)
        assertion = _relationship_assertion(db, service=service, predicate=new_relationship.key, object_type="service", object_id=item.target_service_id, actor_user_id=principal.user.id)
        record_assertion_change(db, assertion=assertion, change_type="service_dependency_added", entity_name=service.name, summary=f"Changed the relationship to {target.name if target else 'a Service'} to {new_relationship.name}", actor_user_id=principal.user.id, metadata={"dependency_id": item.id, "previous_relationship_type_id": old_relationship.id})
    elif changes:
        record_change(db, customer_id=service.customer_id, site_id=service.site_id, change_type="service_updated", entity_type="service", entity_id=service.id, entity_name=service.name, summary=f"Updated the dependency on {target.name if target else 'a Service'}", actor_user_id=principal.user.id, metadata={"dependency_id": item.id, "changed_fields": sorted(changes)})
    commit(db, "Service dependency")
    return _service_dependency_response(db, item)


@router.delete("/service-dependencies/{dependency_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service_dependency(dependency_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("service_dependencies.manage")), db: Session = Depends(get_db)):
    item = db.get(ServiceDependency, dependency_id)
    if item is None or item.valid_to is not None: raise not_found("Service dependency")
    service = _service(db, principal, item.source_service_id, "service_dependencies.manage"); target = db.get(Service, item.target_service_id); relationship = db.get(RelationshipType, item.relationship_type_id)
    effective_at = datetime.now(timezone.utc)
    item.valid_to = effective_at; item.ended_by_user_id = principal.user.id
    _end_dependency_membership(db, item.id, "service", principal, effective_at)
    _retract_dependency_assertion(db, service, relationship, "service", item.target_service_id, principal)
    record_change(db, customer_id=service.customer_id, site_id=service.site_id, change_type="service_dependency_removed", entity_type="service", entity_id=service.id, entity_name=service.name, summary=f"Removed dependency on {target.name if target else 'unavailable Service'}", actor_user_id=principal.user.id, metadata={"dependency_id": item.id})
    from app.services.knowledge_completeness import evaluate_service_safely
    evaluate_service_safely(db, service, trigger_context="service_dependency_removed", actor_user_id=principal.user.id)
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
    groups = [_dependency_group_response(db, row) for row in db.scalars(query.order_by(DependencyGroup.valid_from, DependencyGroup.id))]
    if not groups:
        return []
    asset_ids = {row["id"] for row in list_service_asset_dependencies(service_id, principal, include_history, db)}
    service_ids = {row["id"] for row in list_service_dependencies(service_id, principal, include_history, db)}
    # A partial member set would misrepresent all/any semantics. Return only
    # groups whose entire membership can be disclosed to this reader.
    return [group for group in groups if set(group["asset_dependency_ids"]) <= asset_ids and set(group["service_dependency_ids"]) <= service_ids]


@router.post(
    "/services/{service_id}/dependency-groups",
    response_model=DependencyGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_dependency_group(
    service_id: uuid.UUID,
    payload: DependencyGroupCreate,
    request: Request,
    principal: Principal = Depends(require_permission("service_dependencies.manage")),
    db: Session = Depends(get_db),
):
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
    commit(db, "Dependency group")
    db.refresh(group)
    return _dependency_group_response(db, group)


@router.patch("/dependency-groups/{group_id}", response_model=DependencyGroupResponse)
def update_dependency_group(
    group_id: uuid.UUID,
    payload: DependencyGroupUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("service_dependencies.manage")),
    db: Session = Depends(get_db),
):
    current = db.get(DependencyGroup, group_id)
    if current is None or current.valid_to is not None:
        raise not_found("Dependency group")
    service = _service(db, principal, current.service_id, "service_dependencies.manage")
    prior_memberships = _group_memberships(db, current.id, active_only=True)
    changes = payload.model_dump(exclude_unset=True)
    asset_ids = changes.pop(
        "asset_dependency_ids",
        [row.service_asset_dependency_id for row in prior_memberships if row.service_asset_dependency_id],
    )
    service_ids = changes.pop(
        "service_dependency_ids",
        [row.service_dependency_id for row in prior_memberships if row.service_dependency_id],
    )
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
    commit(db, "Dependency group")
    db.refresh(replacement)
    return _dependency_group_response(db, replacement)


@router.delete("/dependency-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dependency_group(
    group_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_permission("service_dependencies.manage")),
    db: Session = Depends(get_db),
):
    group = db.get(DependencyGroup, group_id)
    if group is None or group.valid_to is not None:
        raise not_found("Dependency group")
    service = _service(db, principal, group.service_id, "service_dependencies.manage")
    effective_at = datetime.now(timezone.utc)
    group.valid_to = effective_at
    group.ended_by_user_id = principal.user.id
    for membership in _group_memberships(db, group.id, active_only=True):
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


def _business_function_link_response(db: Session, item: ServiceBusinessFunction) -> dict:
    service, function = db.get(Service, item.service_id), db.get(BusinessFunction, item.business_function_id)
    relationship = db.get(RelationshipType, item.relationship_type_id) if item.relationship_type_id else None
    result = ServiceBusinessFunctionResponse.model_validate(item).model_dump()
    result.update(service_name=service.name if service else None, business_function_name=function.name if function else None, relationship_type_name=relationship.name if relationship else None, relationship_label=relationship.source_label if relationship else "Supports")
    return result


@router.get("/services/{service_id}/business-functions", response_model=list[ServiceBusinessFunctionResponse])
def list_service_business_functions(service_id: uuid.UUID, principal: Principal = Depends(require_permission("business_functions.view")), include_history: bool = False, db: Session = Depends(get_db)):
    service = _service(db, principal, service_id, "business_functions.view")
    query = select(ServiceBusinessFunction).where(ServiceBusinessFunction.service_id == service.id)
    if not include_history:
        query = query.where(ServiceBusinessFunction.valid_to.is_(None))
    rows = list(db.scalars(query.order_by(ServiceBusinessFunction.created_at)))
    visible = _visible_related_ids(db, principal, BusinessFunction, (row.business_function_id for row in rows), "business_functions.view", service.customer_id)
    return [_business_function_link_response(db, row) for row in rows if row.business_function_id in visible]


@router.post("/services/{service_id}/business-functions", response_model=ServiceBusinessFunctionResponse, status_code=status.HTTP_201_CREATED)
def link_business_function(service_id: uuid.UUID, payload: ServiceBusinessFunctionCreate, request: Request, principal: Principal = Depends(require_permission("business_functions.manage")), db: Session = Depends(get_db)):
    service = _service(db, principal, service_id, "business_functions.manage")
    function = db.get(BusinessFunction, payload.business_function_id)
    if function is None: raise not_found("Business function")
    require_scope(principal, "business_functions.manage", function.customer_id, function.site_id, hide_existence=True)
    if function.customer_id != service.customer_id or (service.site_id is not None and function.site_id not in {None, service.site_id}): raise HTTPException(status_code=422, detail="Business Function is outside the Service customer/site scope")
    relationship = _applicable_relationship(db, payload.relationship_type_id, "service", "business_function") if payload.relationship_type_id else None
    item = ServiceBusinessFunction(customer_id=service.customer_id, site_id=service.site_id, service_id=service.id, business_function_id=function.id, relationship_type_id=payload.relationship_type_id, is_primary=payload.is_primary, importance=payload.importance, description=payload.description, created_by_user_id=principal.user.id)
    db.add(item); flush(db, "Service business function")
    assertion = _relationship_assertion(db, service=service, predicate=relationship.key if relationship else "supports", object_type="business_function", object_id=function.id, actor_user_id=principal.user.id)
    record_assertion_change(db, assertion=assertion, change_type="service_business_function_added", entity_name=service.name, summary=f"Linked {service.name} to {function.name}", actor_user_id=principal.user.id, metadata={"link_id": item.id, "business_function_id": function.id})
    from app.services.knowledge_completeness import evaluate_service_safely
    evaluate_service_safely(db, service, trigger_context="business_function_added", actor_user_id=principal.user.id)
    add_audit_event(db, action="service_business_function.created", target_type="service_business_function", target_id=item.id, actor=principal.user, customer_id=service.customer_id, site_id=service.site_id, summary="Service Business Function link created", request=request)
    commit(db, "Service business function"); db.refresh(item)
    return _business_function_link_response(db, item)


@router.patch("/service-business-functions/{link_id}", response_model=ServiceBusinessFunctionResponse)
def update_business_function_link(link_id: uuid.UUID, payload: ServiceBusinessFunctionUpdate, principal: Principal = Depends(require_permission("business_functions.manage")), db: Session = Depends(get_db)):
    item = db.get(ServiceBusinessFunction, link_id)
    if item is None or item.valid_to is not None: raise not_found("Service Business Function link")
    service = _service(db, principal, item.service_id, "business_functions.manage")
    changes = payload.model_dump(exclude_unset=True)
    old_relationship = db.get(RelationshipType, item.relationship_type_id) if item.relationship_type_id else None
    new_relationship = old_relationship
    if "relationship_type_id" in changes:
        new_relationship = _applicable_relationship(db, changes["relationship_type_id"], "service", "business_function") if changes["relationship_type_id"] else None
    for key, value in changes.items(): setattr(item, key, value)
    function = db.get(BusinessFunction, item.business_function_id)
    if "relationship_type_id" in changes and (new_relationship.id if new_relationship else None) != (old_relationship.id if old_relationship else None):
        _retract_dependency_assertion(db, service, old_relationship or "supports", "business_function", item.business_function_id, principal)
        assertion = _relationship_assertion(db, service=service, predicate=new_relationship.key if new_relationship else "supports", object_type="business_function", object_id=item.business_function_id, actor_user_id=principal.user.id)
        record_assertion_change(db, assertion=assertion, change_type="service_business_function_added", entity_name=service.name, summary=f"Changed how {service.name} supports {function.name if function else 'a Business Function'}", actor_user_id=principal.user.id, metadata={"link_id": item.id, "previous_relationship_type_id": old_relationship.id if old_relationship else None})
    elif changes:
        record_change(db, customer_id=service.customer_id, site_id=service.site_id, change_type="service_updated", entity_type="service", entity_id=service.id, entity_name=service.name, summary=f"Updated the link to {function.name if function else 'a Business Function'}", actor_user_id=principal.user.id, metadata={"link_id": item.id, "changed_fields": sorted(changes)})
    commit(db, "Service business function")
    return _business_function_link_response(db, item)


@router.delete("/service-business-functions/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_business_function_link(link_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("business_functions.manage")), db: Session = Depends(get_db)):
    item = db.get(ServiceBusinessFunction, link_id)
    if item is None or item.valid_to is not None: raise not_found("Service Business Function link")
    service = _service(db, principal, item.service_id, "business_functions.manage"); function = db.get(BusinessFunction, item.business_function_id)
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
    rows = db.scalars(select(KnowledgeChange).where(KnowledgeChange.entity_type == "service", KnowledgeChange.entity_id == service.id).order_by(KnowledgeChange.occurred_at.desc()).limit(limit))
    return [_change_response(db, row) for row in rows]


@router.get("/services/{service_id}/assertions", response_model=list[KnowledgeAssertionResponse])
def service_assertions(service_id: uuid.UUID, principal: Principal = Depends(require_permission("services.view")), current_only: bool = False, db: Session = Depends(get_db)):
    service = _service(db, principal, service_id, "services.view")
    query = select(KnowledgeAssertion).where(KnowledgeAssertion.subject_type == "service", KnowledgeAssertion.subject_id == service.id)
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
