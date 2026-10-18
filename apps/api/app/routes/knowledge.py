"""Knowledge provenance, discovery, assertion, and reconciliation routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, RequestContext, require_permission, require_scope, scope_condition
from app.database import get_db
from app.models import (
    Customer,
    Asset,
    AssetRelationship,
    AssetInterface,
    Network,
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
    ReconciliationLinkTechnicalRequest,
    ReconciliationItemResponse,
    ReconciliationItemPageResponse,
    ReconciliationSummaryResponse,
    ReconciliationEntityResponse,
    ReconciliationEntityPageResponse,
    ReconciliationReviewSection,
    ReconciliationGroupAcceptRequest,
    ReconciliationGroupAcceptResponse,
    SimulatedDiscoveryRequest,
    SimulatedDiscoveryResponse,
)
from app.services.reconciliation import (
    RelationshipResolutionError,
    accept_item,
    defer_item,
    link_item_to_asset,
    link_item_to_technical,
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
from app.services.knowledge_changes import record_assertion_change
from app.utils.json_values import to_json_value
from app.services.reconciliation_listing import filtered_items, initial_fact_context, page_rows
from app.services.reconciliation_entities import EntityReview, entity_page, item_version, SECTION_LIMIT

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
        "coverage_key": run.coverage_key,
        "is_complete_snapshot": run.is_complete_snapshot,
        "completeness_status": run.completeness_status,
        "source_name": source_name,
        "deletion_safety": (
            can_delete_discovery_run(db, run).as_dict()
            if include_deletion_safety
            else None
        ),
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "execution_provenance": ({name: run.execution_provenance.get(name) for name in [
            "connector_id", "connector_version", "connector_digest", "manifest_version", "aip_version", "sdk_version",
            "sdk_digest", "runtime_type", "runtime_version", "protocol_version", "baseline_id", "baseline_version",
            "baseline_digest", "dependency_lock_digest", "packaging_mode", "trigger"]} if run.execution_provenance else None),
        "runtime_job_id": run.runtime_job_id,
        "dispatch_state": run.dispatch_state if run.execution_provenance else None,
        "dispatch_attempts": run.dispatch_attempts,
        "batch_count": run.batch_count,
        "observation_count": run.observation_count,
        "warning_count": run.warning_count,
        "source_version": run.source_version,
        "cancellation_requested_at": run.cancellation_requested_at,
        "debug_enabled": bool(run.debug_enabled),
        "diagnostics_summary": run.diagnostics_summary,
        "diagnostics_events": run.diagnostics_events or [],
    }


def assertion_response(
    db: Session, assertion: KnowledgeAssertion, *, include_deletion_safety: bool = True
) -> dict:
    # Server defaults are populated in PostgreSQL. These fallbacks keep the
    # presenter safe for detached/pre-migration objects used by imports and
    # tests without conflating source freshness with acceptance.
    if assertion.is_source_current is None:
        assertion.is_source_current = bool(assertion.is_current)
    if assertion.is_accepted is None:
        assertion.is_accepted = bool(
            assertion.is_current
            and assertion.confirmation_status == "confirmed"
            and assertion.retracted_at is None
        )
    result = KnowledgeAssertionResponse.model_validate(assertion).model_dump()
    result["value_json"] = to_json_value(assertion.value_json)
    result["source_name"] = _source_name(db, assertion.data_source_id)
    result["deletion_safety"] = (
        can_delete_assertion(db, assertion).as_dict()
        if include_deletion_safety
        else None
    )
    result["provenance_gap_warning"] = assertion_has_provenance_gap(db, assertion)
    return to_json_value(result)


def reconciliation_response(db: Session, item: ReconciliationItem) -> dict:
    result = ReconciliationItemResponse.model_validate(item).model_dump()
    assertion = db.get(KnowledgeAssertion, item.assertion_id)
    result["source_name"] = _source_name(db, assertion.data_source_id) if assertion else None
    run = db.get(DiscoveryRun, assertion.discovery_run_id) if assertion and assertion.discovery_run_id else None
    asset = db.get(Asset, item.entity_id) if item.entity_type == "asset" and item.entity_id else None
    observed = item.observed_value_json if isinstance(item.observed_value_json, dict) else {}
    observed_name = observed.get("name") if item.entity_type == "asset" else None
    if not isinstance(observed_name, str) or not 0 < len(observed_name.strip()) <= 255:
        observed_name = None
    result.update(
        {
            "discovery_run_id": assertion.discovery_run_id if assertion else None,
            "data_source_id": assertion.data_source_id if assertion else None,
            "assertion_predicate": assertion.predicate if assertion else None,
            "discovery_run_status": run.status if run else None,
            "entity_name": asset.name if asset else (observed_name.strip() if observed_name else item.candidate_external_id),
            "last_observed_at": observed.get("last_observed_at"),
            "missing_since_run_id": observed.get("missing_since_run_id"),
            "missing_since_at": assertion.first_observed_at if assertion and item.category == "no_longer_observed" else None,
        }
    )
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
    return to_json_value(result)


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
    integration_id: uuid.UUID | None = None,
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
    if integration_id is not None:
        query = query.where(DiscoveryRun.integration_id == integration_id)
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
    principal: Principal = Depends(require_permission("discovery.simulate")),
    db: Session = Depends(get_db),
):
    _context_match(context, payload.customer_id, payload.site_id)
    if principal.can("discovery.simulate", payload.customer_id, payload.site_id):
        require_scope(principal, "discovery.simulate", payload.customer_id, payload.site_id)
    else:
        # Compatibility for callers holding the pre-v2 integration-management grant.
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
        snapshot = run.snapshot_reconciliation
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
            "baseline_run_id": snapshot.baseline_run_id,
            "observed_count": len(payload.observations),
            "new_count": sum(item.category in {"newly_discovered", "possible_duplicate"} for item in items),
            "changed_count": sum(item.category in {"changed", "contradiction", "inferred_relationship"} for item in items),
            "no_longer_observed_count": snapshot.no_longer_observed_count,
            "reobserved_count": snapshot.reobserved_count,
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
        query = query.where(KnowledgeAssertion.is_source_current.is_(True))
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
        asset = db.get(Asset, assertion.subject_id) if assertion.subject_type == "asset" and assertion.subject_id else None
        record_assertion_change(
            db,
            assertion=assertion,
            change_type="assertion_retracted",
            entity_name=asset.name if asset else assertion.subject_external_id or assertion.subject_type,
            summary=f"Retracted {assertion.predicate} assertion",
            actor_user_id=principal.user.id,
            previous_value=assertion.value_json,
            new_value=None,
            metadata={"reason": payload.reason, "provenance_gap": provenance_gap},
            occurred_at=assertion.retracted_at,
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
    principal: Principal = Depends(require_permission("reconciliation.view")),
    item_status: str | None = Query(default="open", alias="status"),
    category: str | None = None,
    source_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = filtered_items(context, principal, item_status=item_status, category=category,
                           source_id=source_id, run_id=run_id, entity_type=entity_type)
    items = db.scalars(query.order_by(ReconciliationItem.created_at.desc(), ReconciliationItem.id.desc()).limit(limit))
    return [reconciliation_response(db, item) for item in items]


@router.get("/reconciliation-items/page", response_model=ReconciliationItemPageResponse)
def list_reconciliation_item_page(
    context: RequestContext,
    principal: Principal = Depends(require_permission("reconciliation.view")),
    item_status: str | None = Query(default="open", alias="status"),
    category: str | None = None,
    source_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None, max_length=512),
    db: Session = Depends(get_db),
):
    query = filtered_items(context, principal, item_status=item_status, category=category,
                           source_id=source_id, run_id=run_id, entity_type=entity_type)
    items, total, next_cursor = page_rows(db, query, limit=limit, cursor=cursor)
    grouping, related = initial_fact_context(db, context, principal, items)
    return {"items": [{**reconciliation_response(db, item), "initial_entity_item_id": grouping.get(item.id)}
                      for item in items], "total": total, "limit": limit, "next_cursor": next_cursor,
            "related_new_entities": [reconciliation_response(db, item) for item in related]}


@router.get("/reconciliation-items/summary", response_model=ReconciliationSummaryResponse)
def reconciliation_summary(
    context: RequestContext,
    principal: Principal = Depends(require_permission("reconciliation.view")),
    db: Session = Depends(get_db),
):
    query = select(ReconciliationItem).where(
        scope_condition(
            principal,
            "reconciliation.view",
            ReconciliationItem.customer_id,
            ReconciliationItem.site_id,
        )
    )
    if context.customer_id is not None:
        query = query.where(ReconciliationItem.customer_id == context.customer_id)
    if context.site_id is not None:
        query = query.where(ReconciliationItem.site_id == context.site_id)
    rows = list(db.scalars(query))
    by_status: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for item in rows:
        by_status[item.status] = by_status.get(item.status, 0) + 1
        by_category[item.category] = by_category.get(item.category, 0) + 1
    return {
        "by_status": by_status,
        "by_category": by_category,
        "actionable": sum(by_status.get(status, 0) for status in ("open", "deferred")),
    }


def _decision_item(db: Session, principal: Principal, item_id: uuid.UUID, expected_version=None) -> ReconciliationItem:
    item = db.get(ReconciliationItem, item_id, with_for_update=True, populate_existing=True)
    if item is None:
        raise not_found("Reconciliation item")
    permission = (
        "reconciliation.decide"
        if principal.can("reconciliation.decide", item.customer_id, item.site_id)
        else "assets.edit"
    )
    require_scope(principal, permission, item.customer_id, item.site_id, hide_existence=True)
    if expected_version:
        claim = db.get(KnowledgeAssertion, item.assertion_id, with_for_update=True, populate_existing=True)
        if claim is None or item_version(item, claim) != expected_version:
            raise HTTPException(409, "This proposal changed; refresh before deciding")
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


def _apply_acceptance(db, item, request, principal, payload):
    """One authorization, decision, Changes/completeness and audit path."""
    if item.entity_type == "asset_relationship":
        require_scope(principal, "relationships.create", item.customer_id, item.site_id)
    elif item.entity_type in {"network", "asset_interface"}:
        require_scope(principal, "networks.create" if item.category == "newly_discovered" and item.entity_id is None else "networks.edit",
            item.customer_id, item.site_id, hide_existence=True)
    accepted = accept_item(
            db,
            item,
            principal.user,
            disposition=payload.disposition if payload else None,
            reason=payload.reason if payload else None,
            exception_review_at=payload.exception_review_at if payload else None,
        )
    if payload and payload.reason is not None:
        item.decision_reason = payload.reason
    from app.services.knowledge_completeness import evaluate_asset_safely
    if isinstance(accepted, Asset):
        evaluate_asset_safely(db, accepted, trigger_context="reconciliation_accepted", actor_user_id=principal.user.id)
    elif isinstance(accepted, AssetRelationship):
        for endpoint_id in {accepted.source_asset_id, accepted.target_asset_id}:
            endpoint = db.get(Asset, endpoint_id)
            if endpoint:
                evaluate_asset_safely(db, endpoint, trigger_context="reconciliation_relationship_accepted", actor_user_id=principal.user.id)
    _audit_decision(db, request=request, principal=principal, item=item, action="accepted")


@router.post("/reconciliation-items/{item_id}/accept", response_model=ReconciliationItemResponse)
def accept_reconciliation_item(
    item_id: uuid.UUID,
    request: Request,
    payload: ReconciliationDecisionRequest | None = None,
    principal: Principal = Depends(require_permission("reconciliation.decide")),
    db: Session = Depends(get_db),
):
    item = _decision_item(db, principal, item_id, payload.expected_version if payload else None)
    try:
        _apply_acceptance(db, item, request, principal, payload)
    except RelationshipResolutionError as exc:
        db.rollback()
        return JSONResponse(status_code=409, content=exc.payload)
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
    principal: Principal = Depends(require_permission("reconciliation.decide")),
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
    from app.services.knowledge_completeness import evaluate_asset_safely
    evaluate_asset_safely(db, asset, trigger_context="reconciliation_identity_linked", actor_user_id=principal.user.id)
    _audit_decision(db, request=request, principal=principal, item=item, action="linked")
    commit(db, "Asset identity link")
    db.refresh(item)
    return reconciliation_response(db, item)


@router.post("/reconciliation-items/{item_id}/link-technical", response_model=ReconciliationItemResponse)
def link_reconciliation_technical(item_id: uuid.UUID, payload: ReconciliationLinkTechnicalRequest, request: Request,
        principal: Principal = Depends(require_permission("reconciliation.decide")), db: Session = Depends(get_db)):
    item = _decision_item(db, principal, item_id)
    if item.entity_type not in {"network", "asset_interface"}:
        raise HTTPException(422, "This item is not a technical source identity")
    require_scope(principal, "networks.edit", item.customer_id, item.site_id, hide_existence=True)
    target = db.get(Network if item.entity_type == "network" else AssetInterface, payload.entity_id)
    owner = db.get(Asset, target.asset_id) if target is not None and item.entity_type == "asset_interface" else target
    if owner is None or (owner.customer_id, owner.site_id) != (item.customer_id, item.site_id):
        raise not_found("Technical entity")
    link_item_to_technical(db, item=item, target=target, user=principal.user, reason=payload.reason)
    _audit_decision(db, request=request, principal=principal, item=item, action="linked")
    commit(db, "Technical source identity link")
    return reconciliation_response(db, item)


@router.post("/reconciliation-items/{item_id}/reject", response_model=ReconciliationItemResponse)
def reject_reconciliation_item(
    item_id: uuid.UUID,
    request: Request,
    payload: ReconciliationDecisionRequest | None = None,
    principal: Principal = Depends(require_permission("reconciliation.decide")),
    db: Session = Depends(get_db),
):
    item = _decision_item(db, principal, item_id, payload.expected_version if payload else None)
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
    principal: Principal = Depends(require_permission("reconciliation.decide")),
    db: Session = Depends(get_db),
):
    item = _decision_item(db, principal, item_id, payload.expected_version if payload else None)
    defer_item(db, item, principal.user, payload.reason if payload else None)
    _audit_decision(db, request=request, principal=principal, item=item, action="deferred")
    commit(db, "Reconciliation decision")
    db.refresh(item)
    return reconciliation_response(db, item)


@router.get("/reconciliation-entities", response_model=ReconciliationEntityPageResponse)
def list_reconciliation_entities(
    context: RequestContext,
    principal: Principal = Depends(require_permission("reconciliation.view")),
    item_status: str = Query(default="open", alias="status", pattern="^(open|deferred|resolved|accepted|rejected|exception)$"),
    category: str | None = None,
    section: str | None = Query(default=None, pattern="^(facts|relationships|network)$"),
    search: str = Query(default="", max_length=255),
    source_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=1024),
    db: Session = Depends(get_db),
):
    return entity_page(db, context, principal, limit=limit, cursor=cursor, item_status=item_status,
                       category=category, section=section, search=search, source_id=source_id,
                       run_id=run_id, entity_type=entity_type)


@router.get("/reconciliation-entities/{entity_id}", response_model=ReconciliationEntityResponse)
def get_reconciliation_entity(
    entity_id: uuid.UUID, context: RequestContext,
    principal: Principal = Depends(require_permission("reconciliation.view")),
    db: Session = Depends(get_db),
):
    review = EntityReview(db, context, principal)
    key = review.key_for(entity_id)
    # A focused prerequisite includes its unresolved work, including deferred
    # work, plus the parent as context. It never resurrects resolved children.
    return review.present_group(key, [row for row in review.groups[key] if row.status in {"open", "deferred"}])


@router.get("/reconciliation-entities/{entity_id}/section", response_model=ReconciliationReviewSection)
def get_reconciliation_entity_section(
    entity_id: uuid.UUID, context: RequestContext,
    section: str = Query(pattern="^(facts|relationships|network)$"),
    offset: int = Query(default=0, ge=0),
    item_status: str = Query(default="open", alias="status", pattern="^(open|deferred|resolved|accepted|rejected|exception|active)$"),
    category: str | None = None,
    principal: Principal = Depends(require_permission("reconciliation.view")),
    db: Session = Depends(get_db),
):
    review = EntityReview(db, context, principal)
    key = review.key_for(entity_id)
    parent = review.parents_by_key.get(key)
    rows = [row for row in review.groups[key] if (not parent or row.id != parent.id)
            and review.section(row) == section
            and (row.status in {"open", "deferred"} if item_status == "active" else review.matches(row, {"item_status": item_status, "category": category}))]
    from app.services.reconciliation_entities import SECTION_LABELS
    return {"key": section, "label": SECTION_LABELS[section], "total": len(rows),
            "blocked_count": sum(row.status in {"open", "deferred"} and not review.eligibility(row)["can_accept"] for row in rows),
            "warnings": sorted(set(review.eligibility(row)["blocked_reason"] for row in rows if row.status in {"open", "deferred"} and not review.eligibility(row)["can_accept"])),
            "items": [review.present_item(row) for row in rows[offset:offset + SECTION_LIMIT]],
            "next_offset": offset + SECTION_LIMIT if len(rows) > offset + SECTION_LIMIT else None}


@router.post("/reconciliation-entities/{entity_id}/accept", response_model=ReconciliationGroupAcceptResponse)
def accept_reconciliation_entity(
    entity_id: uuid.UUID, payload: ReconciliationGroupAcceptRequest, request: Request, context: RequestContext,
    principal: Principal = Depends(require_permission("reconciliation.decide")),
    db: Session = Depends(get_db),
):
    review = EntityReview(db, context, principal)
    key = review.key_for(entity_id)
    requested = {entry.id: entry.version for entry in payload.items}
    if len(requested) != len(payload.items):
        raise HTTPException(422, "Each reconciliation item may be requested only once")
    if any(review.group_for_item.get(identifier) != key for identifier in requested):
        raise HTTPException(404, "Reconciliation items not found in this entity")
    # Lock in deterministic order and refresh the identity map. Individual
    # decisions use these same row locks, so concurrent requests cannot both win.
    locked = list(db.scalars(select(ReconciliationItem).where(ReconciliationItem.id.in_(requested)).order_by(
        ReconciliationItem.id).with_for_update().execution_options(populate_existing=True)))
    list(db.scalars(select(KnowledgeAssertion).where(KnowledgeAssertion.id.in_(
        [row.assertion_id for row in locked])).order_by(KnowledgeAssertion.id).with_for_update().execution_options(populate_existing=True)))
    review = EntityReview(db, context, principal)
    key = review.key_for(entity_id)
    if len(locked) != len(requested) or any(review.group_for_item.get(identifier) != key for identifier in requested):
        raise HTTPException(409, "Entity membership changed; refresh before deciding")
    result = {name: [] for name in ("accepted", "already_resolved", "blocked", "failed")}
    pending = []
    for identifier, version in requested.items():
        item = review.items[identifier]
        entry = {"id": item.id, "label": review.present_item(item)["label"]}
        if item.status not in {"open", "deferred"}:
            result["already_resolved"].append({**entry, "reason": f"Already {item.status}"})
        elif item_version(item, review.claims[item.id]) != version:
            result["failed"].append({**entry, "reason": "This proposal changed; refresh before deciding"})
        else:
            pending.append(item.id)

    def phase(identifier):
        item, claim = review.items[identifier], review.claims[identifier]
        if item.entity_type == "asset" and item.category in {"newly_discovered", "possible_duplicate"}:
            return 0
        if item.entity_type in {"network", "asset_interface"} and claim.fact_metadata is None:
            return 1
        return 3 if item.entity_type == "asset_relationship" else 2

    phases = {number: [identifier for identifier in pending if phase(identifier) == number] for number in range(4)}
    for identifiers in phases.values():
        if not identifiers:
            continue
        review = EntityReview(db, context, principal)
        for identifier in identifiers:
            item = review.items[identifier]
            entry = {"id": item.id, "label": review.present_item(item)["label"]}
            eligibility = review.eligibility(item)
            if not eligibility["can_accept"]:
                result["blocked"].append({**entry, "reason": eligibility["blocked_reason"]})
                continue
            try:
                with db.begin_nested():
                    _apply_acceptance(db, item, request, principal, ReconciliationDecisionRequest(reason=payload.reason))
                    db.flush()
                result["accepted"].append(entry)
            except RelationshipResolutionError:
                result["blocked"].append({**entry, "reason": "Relationship endpoints are unresolved; refresh to review prerequisites"})
            except HTTPException as exc:
                result["failed"].append({**entry, "reason": exc.detail if isinstance(exc.detail, str) else "This item could not be accepted"})
            except DBAPIError:
                result["failed"].append({**entry, "reason": "A concurrent change prevented acceptance; refresh and review this item"})
    commit(db, "Entity reconciliation decisions")
    return result
