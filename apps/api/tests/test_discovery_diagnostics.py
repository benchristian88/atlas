"""PostgreSQL one-shot intent, isolated diagnostics, expiry and administrator RBAC."""
import asyncio
from dataclasses import replace
from datetime import timedelta
import json
import os
import uuid

from fastapi import HTTPException
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.models import DiscoveryRun, DiscoveryRunDebugTrace, EvidenceRecord, KnowledgeAssertion, ReconciliationItem
from app.routes import integration_discovery as routes
from app.routes.integration_connections import integration_detail
from app.routes.knowledge import run_response
from app.schemas import DiscoveryRunResponse
from app.services import discovery_diagnostics as diagnostics, discovery_orchestration as orchestration
from tests.test_i3_discovery import db, configured, new_run
from tests.test_administration import request

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")


def administrator(configured):
    principal = configured[1]
    return replace(principal, grants=(replace(principal.grants[0], permissions=principal.permissions | {"integration_runtime.manage"}),))


def sample(debug=True):
    rows = [{"sequence": 1, "stage": "guest_interface", "result": "warning", "reason_code": "interface_invalid",
        "object_class": "fixture.guest", "external_id": "guest/1027", "parent_external_id": "node/example",
        **({"field": "net0", "encountered_type": "string", "validation_rule": "interface_config"} if debug else {})},
        {"sequence": 2, "stage": "discovery", "result": "accepted", "reason_code": "discovery_finished"}]
    return diagnostics.report(rows, debug=debug)


def test_one_shot_transactional_consumption_and_immutable_run_intent(db, configured):
    row, admin = configured[0], administrator(configured)
    assert not row.debug_next_run
    routes.set_debug_next_run(row.id, routes.DebugNextRunInput(enabled=True), request(), admin, db)
    assert integration_detail(row.id, admin, db)["debug_next_run"]
    assert "debug_next_run" not in integration_detail(row.id, configured[1], db)
    run = asyncio.run(orchestration.create_run(db, row))
    assert not row.debug_next_run and run.debug_enabled and run.execution_provenance["debug_enabled"]
    assert run.debug_expires_at == run.created_at + timedelta(hours=48)
    db.rollback()
    assert db.get(DiscoveryRun, run.id) is None
    db.refresh(row); assert row.debug_next_run  # Insertion rolled back; arming survives.
    run = new_run(db, configured)
    assert run.debug_enabled and not row.debug_next_run
    with pytest.raises(orchestration.DiscoveryEligibilityError):
        asyncio.run(orchestration.create_run(db, row))
    for name, value in [("debug_enabled", False), ("debug_expires_at", run.debug_expires_at + timedelta(hours=1))]:
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text(f"UPDATE discovery_runs SET {name}=:value WHERE id=:id"), {"id": run.id, "value": value})
    orchestration.cancel_intent(run); db.commit()
    following = new_run(db, configured)
    assert not following.debug_enabled and not following.execution_provenance["debug_enabled"]


def test_failed_eligibility_does_not_consume_arming(db, configured):
    row = configured[0]
    row.debug_next_run = True; row.enabled = False; db.commit()
    with pytest.raises(orchestration.DiscoveryEligibilityError): asyncio.run(orchestration.create_run(db, row))
    assert row.debug_next_run


def test_normal_provenance_survives_debug_deletion_and_cannot_rehydrate(db, configured):
    configured[0].debug_next_run = True
    run = new_run(db, configured)
    diagnostics.persist(db, run, sample()); db.commit()
    safe = DiscoveryRunResponse.model_validate(run_response(db, run)).model_dump(mode="json")
    assert safe["diagnostics_events"][0]["reason_code"] == "interface_invalid"
    assert "field" not in safe["diagnostics_events"][0]
    assert "debug_events" not in json.dumps(safe)
    admin = administrator(configured)
    response = routes.get_debug_trace(run.id, admin, db)
    assert json.loads(response.body)["events"][0]["field"] == "net0"
    assert response.headers["cache-control"] == "no-store"
    assert asyncio.run(routes.delete_debug_trace(run.id, request(), admin, db)) == {"deleted": True}
    assert db.get(DiscoveryRunDebugTrace, run.id) is None
    assert json.loads(routes.get_debug_trace(run.id, admin, db).body)["state"] == "deleted"
    diagnostics.persist(db, run, sample()); db.commit()
    assert db.get(DiscoveryRunDebugTrace, run.id) is None
    assert run.diagnostics_summary["counts"]["warning"] == 1 and run.diagnostics_events
    assert db.get(DiscoveryRun, run.id) is not None


def test_expiry_is_unavailable_and_physically_purged_on_read_or_worker_tick(db, configured, monkeypatch):
    configured[0].debug_next_run = True
    run = new_run(db, configured)
    diagnostics.persist(db, run, sample()); db.commit()
    assert db.get(DiscoveryRunDebugTrace, run.id)
    monkeypatch.setattr(orchestration, "utcnow", lambda: run.debug_expires_at + timedelta(seconds=1))
    response = json.loads(routes.get_debug_trace(run.id, administrator(configured), db).body)
    assert response["state"] == "expired" and not response["events"]
    assert db.get(DiscoveryRunDebugTrace, run.id) is None
    assert run.diagnostics_summary and run.diagnostics_events
    # Independently prove worker expiry purges actual rows, including archived history.
    db.add(DiscoveryRunDebugTrace(discovery_run_id=run.id, expires_at=run.debug_expires_at, events=sample()["debug_events"]))
    db.flush()
    assert diagnostics.purge_expired(db, now=run.debug_expires_at + timedelta(seconds=1)) == 1
    db.commit()
    assert db.get(DiscoveryRunDebugTrace, run.id) is None


@pytest.mark.parametrize("operation", ["arm", "view", "delete"])
@pytest.mark.parametrize("access", ["viewer", "scoped_manager", "other_customer", "other_site"])
def test_debug_requires_global_management_plus_scoped_view(db, configured, operation, access):
    run = new_run(db, configured)
    principal = configured[1]
    grant = principal.grants[0]
    if access == "scoped_manager":
        principal = replace(principal, grants=(replace(grant, scope_type="site", customer_id=run.customer_id,
            site_id=run.site_id, permissions=grant.permissions | {"integration_runtime.manage"}),))
    elif access in {"other_customer", "other_site"}:
        view = replace(grant, scope_type="site", customer_id=uuid.uuid4() if access == "other_customer" else run.customer_id,
            site_id=uuid.uuid4(), permissions=frozenset({"integrations.view"}))
        manager = replace(grant, permissions=frozenset({"integration_runtime.manage"}))
        principal = replace(principal, grants=(view, manager))
    with pytest.raises(HTTPException) as caught:
        if operation == "arm": routes.set_debug_next_run(configured[0].id, routes.DebugNextRunInput(enabled=True), request(), principal, db)
        elif operation == "view": routes.get_debug_trace(run.id, principal, db)
        else: asyncio.run(routes.delete_debug_trace(run.id, request(), principal, db))
    assert caught.value.status_code == (404 if access.startswith("other_") else 403)


def test_worker_reconciliation_persists_failure_trace_without_touching_knowledge(db, configured, monkeypatch):
    configured[0].debug_next_run = True
    run = new_run(db, configured)
    run.dispatch_state = "running"; run.runtime_job_id = uuid.uuid4(); db.commit()
    async def crashed(*args):
        return {"state": "failed", "job_id": str(run.runtime_job_id), "diagnostic_code": "source_unavailable", "diagnostics": sample()}
    monkeypatch.setattr(orchestration.runtime, "get_job", crashed)
    asyncio.run(orchestration.reconcile(db, run.id))
    assert run.status == "failed" and run.dispatch_state == "settled"
    assert run.diagnostics_events[0]["external_id"] == "guest/1027"
    assert db.get(DiscoveryRunDebugTrace, run.id)
    for model in [EvidenceRecord, KnowledgeAssertion, ReconciliationItem]:
        assert not list(db.scalars(select(model).where(model.customer_id == run.customer_id)))


def test_unarmed_and_malformed_reports_cannot_persist_debug_or_arbitrary_config(db, configured):
    run = new_run(db, configured)
    for value in [sample(), {**sample(False), "source_body": {"private": "omitted"}}]:
        with pytest.raises(ValueError): diagnostics.persist(db, run, value)
    assert run.diagnostics_summary is None and db.get(DiscoveryRunDebugTrace, run.id) is None
