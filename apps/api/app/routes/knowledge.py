"""Knowledge provenance, discovery, assertion, and reconciliation routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, RequestContext, require_permission, require_scope, scope_condition
from app.database import get_db
from app.models import (
    Customer,
    Asset,
    DataSource,
    DiscoveryRun,
    Integration,
    KnowledgeAssertion,
    ReconciliationItem,
    Site,
)
from app.routes.crud_helpers import commit, flush, not_found
from app.schemas import (
    AssertionRetractionRequest,
    DataSourceCreate,
    DataSourceResponse,
    DiscoveryRunResponse,
    KnowledgeAssertionResponse,
    LifecycleReasonRequest,
    ReconciliationDecisionRequest,
    ReconciliationLinkAssetRequest,
    ReconciliationItemResponse,
    SimulatedDiscoveryRequest,
    SimulatedDiscoveryResponse,
)
from app.services.reconciliation import (
    RelationshipResolutionError,
    accept_item,
    defer_item,
    link_item_to_asset,
    relationship_resolution,
    reject_item,
)
from app.services.knowledge_lifecycle import (
    ProvenanceGapConfirmationRequired,
    UnsafeDeletionError,
    archive_discovery_run,
    assertion_has_provenance_gap,
    can_delete_assertion,
    can_delete_discovery_run,
    delete_assertion,
    delete_discovery_run,
    restore_discovery_run,
    retract_assertion,
)
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


def run_response(
    db: Session, run: DiscoveryRun, *, include_deletion_safety: bool = False
) -> dict:
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
        "archived_at": run.archived_at,
        "archived_by_user_id": run.archived_by_user_id,
        "archive_reason": run.archive_reason,
        "source_name": source_name,
        "deletion_safety": (
            can_delete_discovery_run(db, run).as_dict()
            if include_deletion_safety
            else None
        ),
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def assertion_response(
    db: Session, assertion: KnowledgeAssertion, *, include_deletion_safety: bool = True
) -> dict:
    result = KnowledgeAssertionResponse.model_validate(assertion).model_dump()
    result["source_name"] = _source_name(db, assertion.data_source_id)
    result["deletion_safety"] = (
        can_delete_assertion(db, assertion).as_dict()
        if include_deletion_safety
        else None
    )
    result["provenance_gap_warning"] = assertion_has_provenance_gap(db, assertion)
    return result


def reconciliation_response(db: Session, item: ReconciliationItem) -> dict:
    result = ReconciliationItemResponse.model_validate(item).model_dump()
    assertion = db.get(KnowledgeAssertion, item.assertion_id)
    result["source_name"] = _source_name(db, assertion.data_source_id) if assertion else None
    if item.entity_type == "asset_relationship" and assertion is not None:
        resolution = relationship_resolution(db, item, persist_links=False)
        for field in (
            "source_external_id",
            "target_external_id",
            "resolved_source_asset_id",
            "resolved_target_asset_id",
            "resolved_source_name",
            "resolved_target_name",
            "source_resolution_status",
            "target_resolution_status",
            "blocked_reason",
            "current_relationship_id",
        ):
            result[field] = resolution.get(field)
        result["current_value_json"] = item.current_value_json
        result["observed_value_json"] = resolution
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
    include_archived: bool = False,
    db: Session = Depends(get_db),
):
    query = select(DiscoveryRun).where(
        scope_condition(principal, "integrations.view", DiscoveryRun.customer_id, DiscoveryRun.site_id)
    )
    if context.customer_id is not None:
        query = query.where(DiscoveryRun.customer_id == context.customer_id)
    if context.site_id is not None:
        query = query.where(DiscoveryRun.site_id == context.site_id)
    if not include_archived:
        query = query.where(DiscoveryRun.archived_at.is_(None))
    runs = db.scalars(query.order_by(DiscoveryRun.started_at.desc()).limit(limit))
    return [run_response(db, run, include_deletion_safety=True) for run in runs]


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
    return run_response(db, run, include_deletion_safety=True)


def _lifecycle_run(
    db: Session, principal: Principal, run_id: uuid.UUID, permission: str
) -> DiscoveryRun:
    run = db.get(DiscoveryRun, run_id)
    if run is None:
        raise not_found("Discovery run")
    require_scope(
        principal,
        permission,
        run.customer_id,
        run.site_id,
        hide_existence=True,
    )
    return run


def _audit_run_lifecycle(
    db: Session,
    *,
    request: Request,
    principal: Principal,
    run: DiscoveryRun,
    action: str,
    metadata: dict | None = None,
) -> None:
    customer = db.get(Customer, run.customer_id)
    add_audit_event(
        db,
        action=f"discovery_run.{action}",
        target_type="discovery_run",
        target_id=run.id,
        actor=principal.user,
        workspace_id=customer.workspace_id if customer else None,
        customer_id=run.customer_id,
        site_id=run.site_id,
        summary=f"Discovery run {action}",
        metadata=metadata or {},
        request=request,
    )


@router.post(
    "/discovery-runs/{run_id}/archive", response_model=DiscoveryRunResponse
)
def archive_run(
    run_id: uuid.UUID,
    payload: LifecycleReasonRequest,
    request: Request,
    principal: Principal = Depends(require_permission("discovery_runs.archive")),
    db: Session = Depends(get_db),
):
    run = _lifecycle_run(db, principal, run_id, "discovery_runs.archive")
    try:
        archive_discovery_run(run, user=principal.user, reason=payload.reason)
        _audit_run_lifecycle(
            db,
            request=request,
            principal=principal,
            run=run,
            action="archived",
            metadata={"reason": payload.reason},
        )
        commit(db, "Discovery run archive")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    db.refresh(run)
    return run_response(db, run, include_deletion_safety=True)


@router.post(
    "/discovery-runs/{run_id}/restore", response_model=DiscoveryRunResponse
)
def restore_run(
    run_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_permission("discovery_runs.archive")),
    db: Session = Depends(get_db),
):
    run = _lifecycle_run(db, principal, run_id, "discovery_runs.archive")
    previous_reason = run.archive_reason
    try:
        restore_discovery_run(run)
        _audit_run_lifecycle(
            db,
            request=request,
            principal=principal,
            run=run,
            action="restored",
            metadata={"previous_archive_reason": previous_reason},
        )
        commit(db, "Discovery run restore")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    db.refresh(run)
    return run_response(db, run, include_deletion_safety=True)


@router.delete("/discovery-runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run(
    run_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_permission("discovery_runs.delete")),
    db: Session = Depends(get_db),
):
    run = _lifecycle_run(db, principal, run_id, "discovery_runs.delete")
    try:
        safety = can_delete_discovery_run(db, run)
        if not safety.allowed:
            return JSONResponse(
                status_code=409,
                content=safety.conflict_payload(
                    "Discovery run cannot be deleted because it supports accepted knowledge"
                ),
            )
        audit_metadata = {"source_name": _source_name(db, run.data_source_id)}
        _audit_run_lifecycle(
            db,
            request=request,
            principal=principal,
            run=run,
            action="deleted",
            metadata=audit_metadata,
        )
        delete_discovery_run(db, run)
        commit(db, "Discovery run deletion")
    except UnsafeDeletionError as exc:
        db.rollback()
        return JSONResponse(
            status_code=409,
            content=exc.safety.conflict_payload(exc.detail),
        )
    except Exception:
        db.rollback()
        raise
    return None


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
        response = {
            "run": run_response(db, run),
            "evidence_records_created": evidence_count,
            "assertions_created": assertion_count,
            "reconciliation_items_created": len(items),
            "reconciliation_items": [
                reconciliation_response(db, item) for item in items
            ],
        }
        commit(db, "Simulated discovery")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    return response


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


def _lifecycle_assertion(
    db: Session, principal: Principal, assertion_id: uuid.UUID, permission: str
) -> KnowledgeAssertion:
    assertion = db.get(KnowledgeAssertion, assertion_id)
    if assertion is None:
        raise not_found("Assertion")
    require_scope(
        principal,
        permission,
        assertion.customer_id,
        assertion.site_id,
        hide_existence=True,
    )
    return assertion


def _audit_assertion_lifecycle(
    db: Session,
    *,
    request: Request,
    principal: Principal,
    assertion: KnowledgeAssertion,
    action: str,
    metadata: dict | None = None,
) -> None:
    customer = db.get(Customer, assertion.customer_id)
    add_audit_event(
        db,
        action=f"assertion.{action}",
        target_type="knowledge_assertion",
        target_id=assertion.id,
        actor=principal.user,
        workspace_id=customer.workspace_id if customer else None,
        customer_id=assertion.customer_id,
        site_id=assertion.site_id,
        summary=f"Knowledge assertion {action}",
        metadata={
            "predicate": assertion.predicate,
            "subject_type": assertion.subject_type,
            **(metadata or {}),
        },
        request=request,
    )


@router.get("/assertions/{assertion_id}", response_model=KnowledgeAssertionResponse)
def get_assertion(
    assertion_id: uuid.UUID,
    principal: Principal = Depends(require_permission("assets.view")),
    db: Session = Depends(get_db),
):
    assertion = _lifecycle_assertion(db, principal, assertion_id, "assets.view")
    return assertion_response(db, assertion)


@router.delete("/assertions/{assertion_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_assertion(
    assertion_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_permission("assertions.delete")),
    db: Session = Depends(get_db),
):
    assertion = _lifecycle_assertion(db, principal, assertion_id, "assertions.delete")
    safety = can_delete_assertion(db, assertion)
    if not safety.allowed:
        return JSONResponse(
            status_code=409,
            content=safety.conflict_payload(
                "Assertion cannot be deleted because it supports accepted knowledge"
            ),
        )
    try:
        _audit_assertion_lifecycle(
            db,
            request=request,
            principal=principal,
            assertion=assertion,
            action="deleted",
        )
        delete_assertion(db, assertion)
        commit(db, "Assertion deletion")
    except UnsafeDeletionError as exc:
        db.rollback()
        return JSONResponse(
            status_code=409,
            content=exc.safety.conflict_payload(exc.detail),
        )
    except Exception:
        db.rollback()
        raise
    return None


@router.post(
    "/assertions/{assertion_id}/retract", response_model=KnowledgeAssertionResponse
)
def retract_knowledge_assertion(
    assertion_id: uuid.UUID,
    payload: AssertionRetractionRequest,
    request: Request,
    principal: Principal = Depends(require_permission("assertions.retract")),
    db: Session = Depends(get_db),
):
    assertion = _lifecycle_assertion(db, principal, assertion_id, "assertions.retract")
    try:
        provenance_gap = retract_assertion(
            db,
            assertion,
            user=principal.user,
            reason=payload.reason,
            confirm_provenance_gap=payload.confirm_provenance_gap,
        )
        _audit_assertion_lifecycle(
            db,
            request=request,
            principal=principal,
            assertion=assertion,
            action="retracted",
            metadata={
                "reason": payload.reason,
                "provenance_gap": provenance_gap,
                "operational_data_unchanged": True,
            },
        )
        commit(db, "Assertion retraction")
    except ProvenanceGapConfirmationRequired as exc:
        db.rollback()
        return JSONResponse(
            status_code=409,
            content={
                "detail": str(exc),
                "requires_confirmation": True,
                "operational_data_unchanged": True,
                "recommended_action": "retract_with_confirmation",
            },
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    db.refresh(assertion)
    return assertion_response(db, assertion)


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
        metadata={
            "category": item.category,
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
        },
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
    try:
        accept_item(db, item, principal.user)
    except RelationshipResolutionError as exc:
        db.rollback()
        return JSONResponse(status_code=409, content=exc.payload)
    item.decision_reason = payload.reason if payload else None
    _audit_decision(db, request=request, principal=principal, item=item, action="accepted")
    commit(db, "Reconciliation decision")
    db.refresh(item)
    return reconciliation_response(db, item)


@router.post(
    "/reconciliation-items/{item_id}/link-asset",
    response_model=ReconciliationItemResponse,
)
def link_reconciliation_asset(
    item_id: uuid.UUID,
    payload: ReconciliationLinkAssetRequest,
    request: Request,
    principal: Principal = Depends(require_permission("assets.edit")),
    db: Session = Depends(get_db),
):
    item = _decision_item(db, principal, item_id)
    asset = db.get(Asset, payload.asset_id)
    if asset is None:
        raise not_found("Asset")
    require_scope(
        principal,
        "assets.edit",
        asset.customer_id,
        asset.site_id,
        hide_existence=True,
    )
    link_item_to_asset(
        db,
        item=item,
        asset=asset,
        user=principal.user,
        reason=payload.reason,
    )
    _audit_decision(db, request=request, principal=principal, item=item, action="linked")
    commit(db, "Asset identity link")
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
