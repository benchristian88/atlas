"""Knowledge provenance, discovery, assertion, and reconciliation routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, RequestContext, require_permission, require_scope, scope_condition
from app.database import get_db
from app.models import (
    Customer,
    DataSource,
    DiscoveryRun,
    Integration,
    KnowledgeAssertion,
    ReconciliationItem,
    Site,
)
from app.routes.crud_helpers import commit, flush, not_found
from app.schemas import (
    DataSourceCreate,
    DataSourceResponse,
    DiscoveryRunResponse,
    KnowledgeAssertionResponse,
    ReconciliationDecisionRequest,
    ReconciliationItemResponse,
    SimulatedDiscoveryRequest,
    SimulatedDiscoveryResponse,
)
from app.services.reconciliation import accept_item, defer_item, reject_item
from app.services.simulated_discovery import run_simulation

router = APIRouter(tags=["knowledge"])


def _context_match(context: RequestContext, customer_id: uuid.UUID, site_id: uuid.UUID | None) -> None:
    if context.customer_id is not None and context.customer_id != customer_id:
        raise HTTPException(status_code=403, detail="Customer does not match the active context")
    if context.site_id is not None and context.site_id != site_id:
        raise HTTPException(status_code=403, detail="Site does not match the active context")


def _validate_context(db: Session, customer_id: uuid.UUID, site_id: uuid.UUID | None) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise not_found("Customer")
    if site_id is not None:
        site = db.get(Site, site_id)
        if site is None or site.customer_id != customer_id:
            raise not_found("Site for customer")
    return customer


def _source_name(db: Session, source_id: uuid.UUID | None) -> str | None:
    source = db.get(DataSource, source_id) if source_id else None
    return source.name if source else None


def run_response(db: Session, run: DiscoveryRun) -> dict:
    source_name = _source_name(db, run.data_source_id)
    if source_name is None and run.integration_id is not None:
        integration = db.get(Integration, run.integration_id)
        source_name = integration.name if integration else None
    return {
        "id": run.id,
        "integration_id": run.integration_id,
        "data_source_id": run.data_source_id,
        "customer_id": run.customer_id,
        "site_id": run.site_id,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at or run.completed_at,
        "summary": run.summary,
        "error_message": run.error_message,
        "created_by_user_id": run.created_by_user_id,
        "source_name": source_name,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def assertion_response(db: Session, assertion: KnowledgeAssertion) -> dict:
    result = KnowledgeAssertionResponse.model_validate(assertion).model_dump()
    result["source_name"] = _source_name(db, assertion.data_source_id)
    return result


def reconciliation_response(db: Session, item: ReconciliationItem) -> dict:
    result = ReconciliationItemResponse.model_validate(item).model_dump()
    assertion = db.get(KnowledgeAssertion, item.assertion_id)
    result["source_name"] = _source_name(db, assertion.data_source_id) if assertion else None
    return result


@router.get("/data-sources", response_model=list[DataSourceResponse])
def list_data_sources(
    context: RequestContext,
    principal: Principal = Depends(require_permission("integrations.view")),
    db: Session = Depends(get_db),
):
    query = select(DataSource).where(
        scope_condition(principal, "integrations.view", DataSource.customer_id, DataSource.site_id)
    )
    if context.customer_id is not None:
        query = query.where(DataSource.customer_id == context.customer_id)
    if context.site_id is not None:
        query = query.where(DataSource.site_id == context.site_id)
    return list(db.scalars(query.order_by(DataSource.name)))


@router.post("/data-sources", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
def create_data_source(
    payload: DataSourceCreate,
    request: Request,
    context: RequestContext,
    principal: Principal = Depends(require_permission("integrations.manage")),
    db: Session = Depends(get_db),
):
    _context_match(context, payload.customer_id, payload.site_id)
    require_scope(principal, "integrations.manage", payload.customer_id, payload.site_id)
    customer = _validate_context(db, payload.customer_id, payload.site_id)
    if customer.status != "active":
        raise HTTPException(status_code=409, detail="Data sources cannot be created for an inactive customer")
    if payload.site_id is not None and db.get(Site, payload.site_id).status != "active":
        raise HTTPException(status_code=409, detail="Data sources cannot be created for an inactive site")
    source = DataSource(**payload.model_dump())
    db.add(source)
    flush(db, "Data source")
    add_audit_event(
        db,
        action="data_source.created",
        target_type="data_source",
        target_id=source.id,
        actor=principal.user,
        workspace_id=customer.workspace_id,
        customer_id=source.customer_id,
        site_id=source.site_id,
        summary="Data source created",
        metadata={"name": source.name, "source_type": source.source_type},
        request=request,
    )
    commit(db, "Data source")
    db.refresh(source)
    return source


@router.get("/discovery-runs", response_model=list[DiscoveryRunResponse])
def list_discovery_runs(
    context: RequestContext,
    principal: Principal = Depends(require_permission("integrations.view")),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = select(DiscoveryRun).where(
        scope_condition(principal, "integrations.view", DiscoveryRun.customer_id, DiscoveryRun.site_id)
    )
    if context.customer_id is not None:
        query = query.where(DiscoveryRun.customer_id == context.customer_id)
    if context.site_id is not None:
        query = query.where(DiscoveryRun.site_id == context.site_id)
    runs = db.scalars(query.order_by(DiscoveryRun.started_at.desc()).limit(limit))
    return [run_response(db, run) for run in runs]


@router.get("/discovery-runs/{run_id}", response_model=DiscoveryRunResponse)
def get_discovery_run(
    run_id: uuid.UUID,
    principal: Principal = Depends(require_permission("integrations.view")),
    db: Session = Depends(get_db),
):
    run = db.get(DiscoveryRun, run_id)
    if run is None:
        raise not_found("Discovery run")
    require_scope(principal, "integrations.view", run.customer_id, run.site_id, hide_existence=True)
    return run_response(db, run)


@router.post("/discovery/simulate", response_model=SimulatedDiscoveryResponse)
def simulate_discovery(
    payload: SimulatedDiscoveryRequest,
    request: Request,
    context: RequestContext,
    principal: Principal = Depends(require_permission("integrations.manage")),
    db: Session = Depends(get_db),
):
    _context_match(context, payload.customer_id, payload.site_id)
    require_scope(principal, "integrations.manage", payload.customer_id, payload.site_id)
    customer = _validate_context(db, payload.customer_id, payload.site_id)
    if customer.status != "active":
        raise HTTPException(status_code=409, detail="Discovery cannot run for an inactive customer")
    if payload.site_id is not None and db.get(Site, payload.site_id).status != "active":
        raise HTTPException(status_code=409, detail="Discovery cannot run for an inactive site")
    if payload.site_id is None and any(item.entity_kind == "asset" for item in payload.observations):
        raise HTTPException(status_code=422, detail="Asset observations require a site")
    try:
        run, evidence_count, assertion_count, items = run_simulation(
            db, payload=payload, user_id=principal.user.id
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    add_audit_event(
        db,
        action="discovery.simulated",
        target_type="discovery_run",
        target_id=run.id,
        actor=principal.user,
        workspace_id=customer.workspace_id,
        customer_id=payload.customer_id,
        site_id=payload.site_id,
        summary="Simulated discovery completed",
        metadata=run.summary or {},
        request=request,
    )
    commit(db, "Simulated discovery")
    return {
        "run": run_response(db, run),
        "evidence_records_created": evidence_count,
        "assertions_created": assertion_count,
        "reconciliation_items_created": len(items),
        "reconciliation_items": [reconciliation_response(db, item) for item in items],
    }


@router.get("/assertions", response_model=list[KnowledgeAssertionResponse])
def list_assertions(
    context: RequestContext,
    principal: Principal = Depends(require_permission("assets.view")),
    subject_type: str | None = None,
    subject_id: uuid.UUID | None = None,
    current_only: bool = True,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = select(KnowledgeAssertion).where(
        scope_condition(principal, "assets.view", KnowledgeAssertion.customer_id, KnowledgeAssertion.site_id)
    )
    if context.customer_id is not None:
        query = query.where(KnowledgeAssertion.customer_id == context.customer_id)
    if context.site_id is not None:
        query = query.where(KnowledgeAssertion.site_id == context.site_id)
    if subject_type:
        query = query.where(KnowledgeAssertion.subject_type == subject_type)
    if subject_id:
        query = query.where(KnowledgeAssertion.subject_id == subject_id)
    if current_only:
        query = query.where(KnowledgeAssertion.is_current.is_(True))
    assertions = db.scalars(query.order_by(KnowledgeAssertion.last_observed_at.desc()).limit(limit))
    return [assertion_response(db, assertion) for assertion in assertions]


@router.get("/reconciliation-items", response_model=list[ReconciliationItemResponse])
def list_reconciliation_items(
    context: RequestContext,
    principal: Principal = Depends(require_permission("assets.view")),
    item_status: str | None = Query(default="open", alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = select(ReconciliationItem).where(
        scope_condition(principal, "assets.view", ReconciliationItem.customer_id, ReconciliationItem.site_id)
    )
    if context.customer_id is not None:
        query = query.where(ReconciliationItem.customer_id == context.customer_id)
    if context.site_id is not None:
        query = query.where(ReconciliationItem.site_id == context.site_id)
    if item_status:
        query = query.where(ReconciliationItem.status == item_status)
    items = db.scalars(query.order_by(ReconciliationItem.created_at.desc()).limit(limit))
    return [reconciliation_response(db, item) for item in items]


def _decision_item(db: Session, principal: Principal, item_id: uuid.UUID) -> ReconciliationItem:
    item = db.get(ReconciliationItem, item_id)
    if item is None:
        raise not_found("Reconciliation item")
    require_scope(principal, "assets.edit", item.customer_id, item.site_id, hide_existence=True)
    return item


def _audit_decision(
    db: Session,
    *,
    request: Request,
    principal: Principal,
    item: ReconciliationItem,
    action: str,
) -> None:
    customer = db.get(Customer, item.customer_id)
    add_audit_event(
        db,
        action=f"reconciliation.{action}",
        target_type="reconciliation_item",
        target_id=item.id,
        actor=principal.user,
        workspace_id=customer.workspace_id if customer else None,
        customer_id=item.customer_id,
        site_id=item.site_id,
        summary=f"Reconciliation item {action}",
        metadata={"category": item.category, "entity_type": item.entity_type},
        request=request,
    )


@router.post("/reconciliation-items/{item_id}/accept", response_model=ReconciliationItemResponse)
def accept_reconciliation_item(
    item_id: uuid.UUID,
    request: Request,
    payload: ReconciliationDecisionRequest | None = None,
    principal: Principal = Depends(require_permission("assets.edit")),
    db: Session = Depends(get_db),
):
    item = _decision_item(db, principal, item_id)
    if item.entity_type == "asset_relationship":
        require_scope(principal, "relationships.create", item.customer_id, item.site_id)
    accept_item(db, item, principal.user)
    item.decision_reason = payload.reason if payload else None
    _audit_decision(db, request=request, principal=principal, item=item, action="accepted")
    commit(db, "Reconciliation decision")
    db.refresh(item)
    return reconciliation_response(db, item)


@router.post("/reconciliation-items/{item_id}/reject", response_model=ReconciliationItemResponse)
def reject_reconciliation_item(
    item_id: uuid.UUID,
    request: Request,
    payload: ReconciliationDecisionRequest | None = None,
    principal: Principal = Depends(require_permission("assets.edit")),
    db: Session = Depends(get_db),
):
    item = _decision_item(db, principal, item_id)
    reject_item(db, item, principal.user, payload.reason if payload else None)
    _audit_decision(db, request=request, principal=principal, item=item, action="rejected")
    commit(db, "Reconciliation decision")
    db.refresh(item)
    return reconciliation_response(db, item)


@router.post("/reconciliation-items/{item_id}/defer", response_model=ReconciliationItemResponse)
def defer_reconciliation_item(
    item_id: uuid.UUID,
    request: Request,
    payload: ReconciliationDecisionRequest | None = None,
    principal: Principal = Depends(require_permission("assets.edit")),
    db: Session = Depends(get_db),
):
    item = _decision_item(db, principal, item_id)
    defer_item(db, item, principal.user, payload.reason if payload else None)
    _audit_decision(db, request=request, principal=principal, item=item, action="deferred")
    commit(db, "Reconciliation decision")
    db.refresh(item)
    return reconciliation_response(db, item)
