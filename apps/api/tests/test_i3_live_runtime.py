"""Real Ansible child and HTTP callbacks; no production source connection."""
import asyncio
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.test_i3_discovery import db, configured, new_run
from tests.i3_fixtures import ROOT
from app.services import discovery_orchestration as orchestration
from app.services.integration_runtime import LocalIntegrationRuntime, _approved_baseline
from app.database import get_db
from app.main import app
from app.models import EvidenceRecord

pytestmark = [pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable PostgreSQL"),
    pytest.mark.skipif(not os.getenv("ATLAS_TEST_RUNTIME_PYTHON"), reason="requires installed pinned Ansible runtime environment")]


@pytest.mark.parametrize("scenario", ["complete", "partial", "failed", "missing", "malformed", "slow"])
def test_real_ansible_private_dispatch_callback_and_cancel(db, configured, tmp_path, monkeypatch, scenario):
    sys.path.insert(0, str(ROOT / "apps/runtime/ansible"))
    from atlas_runtime.server import Runtime, Server
    from atlas_runtime import jobs
    monkeypatch.setattr(jobs.sys, "executable", os.environ["ATLAS_TEST_RUNTIME_PYTHON"])
    monkeypatch.setattr(jobs, "workspace_root", lambda: tmp_path)
    configured[0].config_json = {**configured[0].config_json, "scenario": scenario}
    db.commit()
    secret = secrets.token_hex(48)
    secret_file = tmp_path/"control.secret"; secret_file.write_text(secret); secret_file.chmod(0o600)
    monkeypatch.setenv("ATLAS_RUNTIME_CONTROL_SECRET_FILE", str(secret_file))
    monkeypatch.setenv("ATLAS_RUNTIME_URL", "http://127.0.0.1:8091")
    baseline = _approved_baseline()
    runtime = Runtime(secret, configured[2].root, "development")
    def health():
        return {name: baseline[name] for name in ["runtime_version", "protocol_version", "baseline_id", "baseline_version", "baseline_digest", "dependency_lock_digest", "dependencies", "collections"]} | {
            "state": "healthy", "packaging_mode": "development", "diagnostic_code": None,
            "ansible_core_version": baseline["dependencies"]["ansible-core"], "ansible_runner_version": baseline["dependencies"]["ansible-runner"]}
    monkeypatch.setattr(runtime, "health", health)
    client = LocalIntegrationRuntime()
    monkeypatch.setattr(orchestration, "runtime", client)
    app.dependency_overrides[get_db] = lambda: db
    callback_paths = []
    class Callback(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            response = TestClient(app).post(self.path, content=body, headers={"Authorization": self.headers["Authorization"], "Content-Type": "application/json"})
            callback_paths.append((self.path, response.status_code))
            self.send_response(response.status_code); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(response.content)
        def log_message(self, *args): pass
    control = Server(("127.0.0.1", 8091), runtime)
    callbacks = HTTPServer(("127.0.0.1", 8000), Callback)
    threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in [control, callbacks]]
    for thread in threads: thread.start()
    try:
        assert asyncio.run(client.health())["status"] == "healthy"
        run = new_run(db, configured)
        asyncio.run(orchestration.dispatch(db, run.id))
        assert run.runtime_job_id and run.status == "running"
        if scenario == "slow":
            deadline = time.monotonic() + 12
            while not list(tmp_path.glob("job-*/fixture.pid")) and time.monotonic() < deadline:
                time.sleep(.1)
            paths = list(tmp_path.glob("job-*/fixture.pid"))
            assert paths, "Source child did not reach its deterministic cancellation point"
            source_pid = int(paths[0].read_text())
            orchestration.cancel_intent(run); db.commit()
            asyncio.run(client.cancel_job(run.id, run.runtime_job_id))
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            status = asyncio.run(client.get_job(run.id, run.runtime_job_id))
            if status["state"] in {"succeeded", "failed", "cancelled"}: break
            time.sleep(.1)
        assert status["state"] in {"succeeded", "failed", "cancelled"}
        db.expire_all()
        asyncio.run(orchestration.reconcile(db, run.id))
        assert run.status == ("completed" if scenario in {"complete", "partial"} else "cancelled" if scenario == "slow" else "failed")
        assert run.dispatch_state == "settled" and not list(tmp_path.glob("job-*"))
        if scenario == "slow":
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                try: os.kill(source_pid, 0)
                except ProcessLookupError: break
                time.sleep(.1)
            else: pytest.fail("Cancelled source descendant was not killed and reaped")
        if scenario in {"complete", "partial", "failed"}:
            assert run.batch_count == 2 and run.observation_count == 1 and all(code == 200 for _, code in callback_paths)
            assert db.scalar(select(EvidenceRecord.id).where(EvidenceRecord.discovery_run_id == run.id))
            assert run.completeness_status == {"complete": "complete", "partial": "partial", "failed": "failed"}[scenario]
    finally:
        runtime.jobs.shutdown()
        for server in [control, callbacks]: server.shutdown(); server.server_close()
        for thread in threads: thread.join(2)
        app.dependency_overrides.clear()
