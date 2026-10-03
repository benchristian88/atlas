"""Lightweight homelab Business Function APIs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, RequestContext, require_permission, require_scope, scope_condition
from app.database import get_db
from app.presentation import default_entity_accent
from app.schemas import EntityDeletionEligibilityResponse
from app.models import BusinessFunction, CriticalityLevel, KnowledgeGap, ServiceBusinessFunction, Service, Site
from app.routes.crud_helpers import commit, flush, not_found
from app.routes.services import _business_function_link_response, _visible_related_ids, service_response
from app.schemas import BusinessFunctionCreate, BusinessFunctionResponse, BusinessFunctionUpdate, ServiceBusinessFunctionResponse, ServiceGraphResponse, ServiceResponse
from app.services.operational_graph import (
    GraphFocusNotFound,
    GraphProjectionRequest,
    OperationalGraphBuilder,
    operational_graph_to_service_graph,
)

router = APIRouter(prefix="/business-functions", tags=["business functions"])


def _function(db: Session, principal: Principal, function_id: uuid.UUID, permission: str) -> BusinessFunction:
    item = db.get(BusinessFunction, function_id)
    if item is None or item.deleted_at is not None:
        raise not_found("Business function")
    require_scope(principal, permission, item.customer_id, item.site_id, hide_existence=True)
    return item


def function_response(db: Session, item: BusinessFunction, principal: Principal) -> dict:
    criticality = db.get(CriticalityLevel, item.criticality_level_id) if item.criticality_level_id else None
    service_ids = list(db.scalars(select(ServiceBusinessFunction.service_id).where(ServiceBusinessFunction.business_function_id == item.id, ServiceBusinessFunction.valid_to.is_(None))))
    visible_service_ids = _visible_related_ids(db, principal, Service, service_ids, "services.view", item.customer_id)
    gap_service_ids = _visible_related_ids(db, principal, Service, visible_service_ids, "knowledge_gaps.view", item.customer_id)
    result = BusinessFunctionResponse.model_validate(item).model_dump()
    result.update(
        criticality_name=criticality.name if criticality else None,
        service_count=sum(service_id in visible_service_ids for service_id in service_ids),
        open_gap_count=int(db.scalar(select(func.count()).select_from(KnowledgeGap).where(KnowledgeGap.entity_type == "service", KnowledgeGap.entity_id.in_(gap_service_ids), KnowledgeGap.status.in_({"open", "deferred"}))) or 0) if gap_service_ids else 0,
    )
    return result


@router.get("", response_model=list[BusinessFunctionResponse])
def list_business_functions(context: RequestContext, principal: Principal = Depends(require_permission("business_functions.view")), active_only: bool = False, search: str | None = None, limit: int = Query(default=200, ge=1, le=500), db: Session = Depends(get_db)):
    query = select(BusinessFunction).where(scope_condition(principal, "business_functions.view", BusinessFunction.customer_id, BusinessFunction.site_id))
    if context.customer_id: query = query.where(BusinessFunction.customer_id == context.customer_id)
    if context.site_id: query = query.where(or_(BusinessFunction.site_id == context.site_id, BusinessFunction.site_id.is_(None)))
    if active_only: query = query.where(BusinessFunction.active.is_(True))
    if search and search.strip():
        pattern = f"%{search.strip()}%"; query = query.where(or_(BusinessFunction.name.ilike(pattern), BusinessFunction.description.ilike(pattern), BusinessFunction.owner_name.ilike(pattern)))
    return [function_response(db, item, principal) for item in db.scalars(query.order_by(BusinessFunction.name).limit(limit))]


@router.post("", response_model=BusinessFunctionResponse, status_code=status.HTTP_201_CREATED)
def create_business_function(payload: BusinessFunctionCreate, request: Request, context: RequestContext, principal: Principal = Depends(require_permission("business_functions.manage")), db: Session = Depends(get_db)):
    if context.customer_id and payload.customer_id != context.customer_id: raise HTTPException(status_code=403, detail="Business Function customer must match the active context")
    if context.site_id and payload.site_id != context.site_id: raise HTTPException(status_code=403, detail="Business Function site must match the active context")
    if payload.site_id:
        site = db.get(Site, payload.site_id)
        if site is None or site.customer_id != payload.customer_id: raise HTTPException(status_code=422, detail="Site does not belong to the selected customer")
    require_scope(principal, "business_functions.manage", payload.customer_id, payload.site_id)
    if payload.criticality_level_id:
        criticality = db.get(CriticalityLevel, payload.criticality_level_id)
        if criticality is None or not criticality.active: raise HTTPException(status_code=422, detail="Criticality level is not active or does not exist")
    item = BusinessFunction(**payload.model_dump(), created_by_user_id=principal.user.id, updated_by_user_id=principal.user.id)
    db.add(item); flush(db, "Business function")
    item.icon_key = item.icon_key or "home"
    item.accent_key = item.accent_key or default_entity_accent(item.id)
    add_audit_event(db, action="business_function.created", target_type="business_function", target_id=item.id, actor=principal.user, customer_id=item.customer_id, site_id=item.site_id, summary="Business Function created", request=request)
    commit(db, "Business function"); db.refresh(item)
    return function_response(db, item, principal)


@router.get("/{function_id}", response_model=BusinessFunctionResponse)
def get_business_function(function_id: uuid.UUID, principal: Principal = Depends(require_permission("business_functions.view")), db: Session = Depends(get_db)):
    return function_response(db, _function(db, principal, function_id, "business_functions.view"), principal)


@router.patch("/{function_id}", response_model=BusinessFunctionResponse)
def update_business_function(function_id: uuid.UUID, payload: BusinessFunctionUpdate, request: Request, principal: Principal = Depends(require_permission("business_functions.manage")), db: Session = Depends(get_db)):
    item = _function(db, principal, function_id, "business_functions.manage")
    changes = payload.model_dump(exclude_unset=True)
    if "site_id" in changes and changes["site_id"] != item.site_id:
        count = int(db.scalar(select(func.count()).select_from(ServiceBusinessFunction).where(ServiceBusinessFunction.business_function_id == item.id, ServiceBusinessFunction.valid_to.is_(None))) or 0)
        if count: raise HTTPException(status_code=409, detail="A Business Function linked to Services cannot be moved")
        if changes["site_id"]:
            site = db.get(Site, changes["site_id"])
            if site is None or site.customer_id != item.customer_id: raise HTTPException(status_code=422, detail="Site does not belong to the selected customer")
    require_scope(principal, "business_functions.manage", item.customer_id, changes.get("site_id", item.site_id))
    if changes.get("criticality_level_id"):
        criticality = db.get(CriticalityLevel, changes["criticality_level_id"])
        if criticality is None or not criticality.active: raise HTTPException(status_code=422, detail="Criticality level is not active or does not exist")
    semantic = {key: value for key, value in changes.items() if getattr(item, key) != value}
    for key, value in semantic.items(): setattr(item, key, value)
    if semantic:
        item.updated_by_user_id = principal.user.id
        add_audit_event(db, action="business_function.updated", target_type="business_function", target_id=item.id, actor=principal.user, customer_id=item.customer_id, site_id=item.site_id, summary="Business Function updated", metadata={"changed_fields": sorted(semantic)}, request=request)
        commit(db, "Business function")
    return function_response(db, item, principal)


@router.get("/{function_id}/services", response_model=list[ServiceBusinessFunctionResponse])
def business_function_services(function_id: uuid.UUID, principal: Principal = Depends(require_permission("business_functions.view")), include_history: bool = False, db: Session = Depends(get_db)):
    function = _function(db, principal, function_id, "business_functions.view")
    query = select(ServiceBusinessFunction).where(ServiceBusinessFunction.business_function_id == function.id)
    if not include_history: query = query.where(ServiceBusinessFunction.valid_to.is_(None))
    rows = list(db.scalars(query.order_by(ServiceBusinessFunction.created_at)))
    visible = _visible_related_ids(db, principal, Service, (row.service_id for row in rows), "services.view", function.customer_id)
    return [_business_function_link_response(db, row) for row in rows if row.service_id in visible]


@router.get("/{function_id}/graph", response_model=ServiceGraphResponse)
def business_function_graph(
    function_id: uuid.UUID,
    context: RequestContext,
    principal: Principal = Depends(require_permission("business_functions.view")),
    db: Session = Depends(get_db),
):
    try:
        graph = OperationalGraphBuilder(db, principal).build(
            GraphProjectionRequest(
                focus_type="business_function",
                focus_id=function_id,
                max_depth=2,
                node_limit=500,
                context=context,
                include_inactive_focus=True,
                edge_families_by_depth=(
                    frozenset({"service_business_function"}),
                    frozenset({"service_asset"}),
                ),
            )
        )
    except GraphFocusNotFound:
        raise not_found("Business function")
    return operational_graph_to_service_graph(graph)


@router.get("/{function_id}/deletion-eligibility", response_model=EntityDeletionEligibilityResponse)
def function_deletion_eligibility(function_id: uuid.UUID, principal: Principal = Depends(require_permission("business_functions.manage")), db: Session = Depends(get_db)):
    from app.services.entity_lifecycle import deletion_eligible, MESSAGE
    item = _function(db, principal, function_id, "business_functions.manage")
    eligible = deletion_eligible(db, item)
    return {"eligible": eligible, "reason": None if eligible else MESSAGE.format(label="Business Function")}


@router.delete("/{function_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_business_function(function_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("business_functions.manage")), db: Session = Depends(get_db)):
    from app.services.entity_lifecycle import delete_mistake
    delete_mistake(db, _function(db, principal, function_id, "business_functions.manage"), principal, request)


@router.post("/{function_id}/archive", response_model=BusinessFunctionResponse)
def archive_business_function(function_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("business_functions.manage")), db: Session = Depends(get_db)):
    return update_business_function(function_id, BusinessFunctionUpdate(active=False), request, principal, db)


@router.post("/{function_id}/restore", response_model=BusinessFunctionResponse)
def restore_business_function(function_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("business_functions.manage")), db: Session = Depends(get_db)):
    return update_business_function(function_id, BusinessFunctionUpdate(active=True), request, principal, db)
