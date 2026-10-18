"""Diagnostic successor through actual Runner, private control and PostgreSQL.

The separate synthetic fixture is built from .3; original I4B fixture is intact.
"""
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import time

import pytest
from sqlalchemy import select, func

from app.models import DiscoveryRunDebugTrace, EvidenceRecord, Integration, KnowledgeAssertion, ReconciliationItem, RunObservedEntity
from app.routes.integration_discovery import delete_debug_trace
from app.routes.knowledge import run_response
from app.services import discovery_orchestration as orchestration
from tests import test_i4b_runtime as i4b
from tests.test_i4b_runtime import candidate, db, configured
from tests.test_administration import request
from tests.test_discovery_diagnostics import administrator
from tests.test_i3_discovery import new_run

pytestmark = [pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable PostgreSQL"),
    pytest.mark.skipif(not os.getenv("ATLAS_TEST_RUNTIME_PYTHON"), reason="requires pinned Ansible runtime")]


@pytest.fixture(autouse=True)
def successor(monkeypatch):
    monkeypatch.setattr(i4b, "FIXTURES", Path(__file__).parent / "fixtures/i4c-diagnostics")


@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("scenario,expected", [("complete", "complete"), ("malformed", "partial"), ("source_failure", "failed")])
def test_successor_diagnostics_survive_actual_runner_and_ingestion(db, candidate, scenario, expected, debug):
    configured, runtime, client, callbacks = candidate
    configured[0].debug_next_run = debug; db.commit()
    run, state = i4b.execute(db, candidate, scenario)
    assert run.completeness_status == expected and run.debug_enabled is debug
    assert not configured[0].debug_next_run
    assert run.diagnostics_summary["available"]
    assert "diagnostics" in state
    assert not run.diagnostics_summary["processing_errors"]
    assert bool(db.get(DiscoveryRunDebugTrace, run.id)) is debug
    if scenario == "malformed":
        warning = next(row for row in run.diagnostics_events if row["reason_code"] == "guest_interface_invalid")
        assert warning["external_id"] == "guest/qemu/100/interface/net0" and "field" not in warning
        if debug:
            trace = db.get(DiscoveryRunDebugTrace, run.id)
            assert any(row.get("field") == "net0" and row.get("validation_rule") == "guest_interface_config" for row in trace.events)
            assert "debug_events" not in json.dumps(run_response(db, run), default=str)
            retained_models = [EvidenceRecord, KnowledgeAssertion, ReconciliationItem, RunObservedEntity]
            def retained_counts():
                return tuple(db.scalar(select(func.count()).select_from(model).where(model.customer_id == run.customer_id))
                    for model in retained_models)
            before = retained_counts()
            assert all(before)
            asyncio.run(delete_debug_trace(run.id, request(), administrator(configured), db))
            assert db.get(DiscoveryRunDebugTrace, run.id) is None
            assert retained_counts() == before
            result = asyncio.run(client.get_job(run.id, run.runtime_job_id))
            assert result["diagnostics"]["debug_events"] == []
            assert result["diagnostics"]["events"] and run.diagnostics_summary


@pytest.mark.parametrize("terminal", ["cancelled", "timeout"])
def test_actual_source_child_termination_retains_flushed_trace_and_removes_workspace(db, candidate, tmp_path, terminal):
    configured, runtime, client, callbacks = candidate
    configured[0].config_json = {**configured[0].config_json, "fixture_scenario": "slow"}
    configured[0].debug_next_run = True; db.commit()
    run = new_run(db, configured)
    asyncio.run(orchestration.dispatch(db, run.id))
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and not list(tmp_path.glob("job-*/fixture.pid")): time.sleep(.1)
    paths = list(tmp_path.glob("job-*/fixture.pid")); assert paths
    pid = int(paths[0].read_text())
    if terminal == "cancelled":
        orchestration.cancel_intent(run); db.commit()
        asyncio.run(client.cancel_job(run.id, run.runtime_job_id))
    else:
        run.deadline_at = orchestration.utcnow() - timedelta(seconds=1); db.commit()
        asyncio.run(orchestration.reconcile(db, run.id))
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        result = asyncio.run(client.get_job(run.id, run.runtime_job_id))
        if result["state"] == "cancelled": break
        time.sleep(.1)
    assert result["state"] == "cancelled"
    asyncio.run(orchestration.reconcile(db, run.id))
    trace = db.get(DiscoveryRunDebugTrace, run.id)
    assert trace and trace.events[0]["reason_code"] == "discovery_started"
    assert "diagnostic_incomplete" in run.diagnostics_summary["processing_errors"]
    assert not list(tmp_path.glob("job-*")) and run.status == ("cancelled" if terminal == "cancelled" else "failed")
    if terminal == "timeout":
        assert run.error_message == "timeout"
    assert db.scalar(select(Integration.debug_next_run).where(Integration.id == run.integration_id)) is False
    with pytest.raises(ProcessLookupError): os.kill(pid, 0)
