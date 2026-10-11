"""Scoped run administration and a separate, narrow ingestion authenticator."""
import uuid
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas_connector_sdk.contracts import ContractError, strict_json
from app.audit import add_audit_event
from app.authorization import Principal, require_permission, require_scope, scope_condition
from app.database import get_db
from app.models import DiscoveryRun, Integration, DataSource
from app.routes.integration_connections import scoped, require_live
from app.routes.knowledge import run_response
from app.services import discovery_orchestration as orchestration, discovery_tokens, aip_ingestion

router = APIRouter(tags=["integration-discovery"])


def eligibility_error(error):
    code = error.code if isinstance(error, orchestration.DiscoveryEligibilityError) else "discovery_configuration_unavailable"
    value = {"code": code, "message": "Check the Integration, discovery capability, configuration, mappings and runtime."}
    if getattr(error, "run_id", None):
        value.update(run_id=str(error.run_id), message="A discovery run is already active for this Integration.")
    raise HTTPException(409, value) from None


async def start(integration_id, request, principal, db, *, trigger):
    row = scoped(db, principal, "integrations.run", integration_id, lock=True)
    require_live(row)
    try:
        run = await orchestration.create_run(db, row, trigger=trigger, user_id=principal.user.id)
        add_audit_event(db, action="integration.discovery_requested", target_type="discovery_run", target_id=run.id,
            customer_id=row.customer_id, site_id=row.site_id, actor=principal.user, request=request,
            summary="Integration discovery requested", metadata={"trigger": trigger, "integration_id": str(row.id)})
        db.commit()
        orchestration.enqueue(run.id)
        return run_response(db, run)
    except (ValueError, OSError, RuntimeError) as error:
        db.rollback()
        eligibility_error(error)


@router.post("/integrations/{integration_id}/run", status_code=202)
async def run_now(integration_id: uuid.UUID, request: Request,
        principal: Principal = Depends(require_permission("integrations.run")), db: Session = Depends(get_db)):
    return await start(integration_id, request, principal, db, trigger="manual")


@router.post("/integrations/{integration_id}/initial-discovery", status_code=202)
async def initial_discovery(integration_id: uuid.UUID, request: Request,
        principal: Principal = Depends(require_permission("integrations.run")), db: Session = Depends(get_db)):
    return await start(integration_id, request, principal, db, trigger="onboarding")


class ScheduleInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    preset: str


@router.put("/integrations/{integration_id}/schedule")
async def set_schedule(integration_id: uuid.UUID, payload: ScheduleInput, request: Request,
        principal: Principal = Depends(require_permission("integrations.manage")), db: Session = Depends(get_db)):
    row = scoped(db, principal, "integrations.manage", integration_id, lock=True)
    require_scope(principal, "integrations.run", row.customer_id, row.site_id, hide_existence=True)
    require_live(row)
    if payload.preset not in orchestration.SCHEDULES:
        raise HTTPException(422, "Select a supported schedule preset")
    try:
        _, manifest, _, _, _, _ = await orchestration.eligibility(db, row, require_runtime=False)
        if not manifest["capabilities"]["scheduling"]:
            raise orchestration.DiscoveryEligibilityError("scheduling_unavailable")
        row.schedule_preset = payload.preset
        row.next_run_at = orchestration.next_run(payload.preset, orchestration.utcnow())
        add_audit_event(db, action="integration.schedule_changed", target_type="integration", target_id=row.id,
            customer_id=row.customer_id, site_id=row.site_id, actor=principal.user, request=request,
            summary="Integration discovery schedule changed", metadata={"preset": payload.preset})
        db.commit()
        return {"preset": row.schedule_preset, "next_run_at": row.next_run_at}
    except (ValueError, OSError, RuntimeError) as error:
        db.rollback()
        eligibility_error(error)


@router.post("/discovery-runs/{run_id}/cancel")
def cancel_run(run_id: uuid.UUID, request: Request,
        principal: Principal = Depends(require_permission("integrations.run")), db: Session = Depends(get_db)):
    identity = db.scalar(select(DiscoveryRun).where(DiscoveryRun.id == run_id,
        scope_condition(principal, "integrations.run", DiscoveryRun.customer_id, DiscoveryRun.site_id)))
    if identity is None:
        raise HTTPException(404, "Discovery run not found")
    if identity.execution_provenance is None:
        raise HTTPException(409, "This run does not use asynchronous Integration discovery")
    db.scalar(select(Integration).where(Integration.id == identity.integration_id).with_for_update())
    run = db.scalar(select(DiscoveryRun).where(DiscoveryRun.id == run_id).with_for_update().execution_options(populate_existing=True))
    orchestration.cancel_intent(run)
    add_audit_event(db, action="integration.discovery_cancel_requested", target_type="discovery_run", target_id=run.id,
        customer_id=run.customer_id, site_id=run.site_id, actor=principal.user, request=request,
        summary="Integration discovery cancellation requested")
    db.commit()
    orchestration.enqueue(run.id)
    return run_response(db, run)


def authenticate_ingestion(db, request, run_id, *, finalisation=False):
    """No Principal, cookies, user sessions or payload-selected tenancy here."""
    unauthorized = HTTPException(401, "Invalid discovery ingestion credential", headers={"Cache-Control": "no-store"})
    headers = request.headers.getlist("authorization")
    if len(headers) != 1 or not headers[0].startswith("Bearer "):
        raise unauthorized
    try:
        claims = discovery_tokens.decode(headers[0][7:])
    except discovery_tokens.IngestionAuthenticationError:
        raise unauthorized from None
    if claims["run_id"] != str(run_id):
        raise unauthorized
    identity = db.get(DiscoveryRun, run_id)
    if identity is None or str(identity.integration_id) != claims["integration_id"]:
        raise unauthorized
    row = db.scalar(select(Integration).where(Integration.id == identity.integration_id).with_for_update())
    run = db.scalar(select(DiscoveryRun).where(DiscoveryRun.id == run_id).with_for_update().execution_options(populate_existing=True))
    source = db.get(DataSource, run.data_source_id) if run.data_source_id else None
    if (row is None or source is None or run.execution_provenance is None or row.retired_at or not row.enabled
            or run.cancellation_requested_at or claims["jti"] != str(run.ingestion_generation)
            or (run.customer_id, run.site_id, run.data_source_id) != (row.customer_id, row.site_id, row.data_source_id)
            or (source.customer_id, source.site_id) != (row.customer_id, row.site_id)
            or run.status not in {"pending", "running"} and not (finalisation and run.finalisation_hash)):
        raise unauthorized
    return run, row


async def body(request):
    if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
        raise aip_ingestion.IngestionError("invalid_content_type")
    chunks, size = [], 0
    async with asyncio.timeout(10):
        async for chunk in request.stream():
            size += len(chunk)
            if size > aip_ingestion.MAX_BODY:
                raise aip_ingestion.IngestionError("payload_limit")
            chunks.append(chunk)
    return strict_json(b"".join(chunks), maximum=aip_ingestion.MAX_BODY)


async def ingest(run_id, request, db, operation):
    run, row = authenticate_ingestion(db, request, run_id, finalisation=operation != "batch")
    try:
        message = await body(request)
        aip_ingestion.reject_sensitive_material(db, run, row, message, request.headers["authorization"][7:])
        # Evidence, receipts, review and seal share one transaction. Invalid
        # finalisation rolls back its attempted domain changes before failure.
        with db.begin_nested():
            result = aip_ingestion.accept_batch(db, run, message) if operation == "batch" else aip_ingestion.finalise(
                db, run, row, message, failure=operation == "failure")
            try:
                discovery_tokens.decode(request.headers["authorization"][7:])
            except discovery_tokens.IngestionAuthenticationError:
                raise aip_ingestion.IngestionError("token_expired") from None
        db.commit()
        return result
    except (ContractError, aip_ingestion.IngestionError, TimeoutError) as error:
        code = "payload_timeout" if isinstance(error, TimeoutError) else error.code
        fatal = not isinstance(error, aip_ingestion.IngestionError) or error.fatal
        if fatal:
            orchestration.fail_run(run, row, code)
        db.commit()
        status = 401 if code == "token_expired" else 413 if code in {"payload_limit", "metadata_too_large"} else 409 if code in {
            "conflicting_receipt", "conflicting_completion", "incomplete_receipts", "run_finalised"} else 422
        raise HTTPException(status, {"code": code, "message": "Discovery payload was not accepted."},
            headers={"Cache-Control": "no-store"}) from None


@router.post("/integration-ingestion/{run_id}/batches")
async def ingest_batch(run_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    return await ingest(run_id, request, db, "batch")


@router.post("/integration-ingestion/{run_id}/completion")
async def ingest_completion(run_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    return await ingest(run_id, request, db, "completion")


@router.post("/integration-ingestion/{run_id}/failure")
async def ingest_failure(run_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    return await ingest(run_id, request, db, "failure")
