"""Verified async runtime jobs, process isolation, cleanup and fixed callback."""
from copy import deepcopy
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import threading
import time
import uuid

import pytest

from tests.i3_fixtures import fixture_bundle, ROOT
from app.services.connector_store import PackageStore
sys.path.insert(0, str(ROOT / "apps/runtime/ansible"))
from atlas_runtime.server import Runtime
from atlas_runtime import jobs


@pytest.fixture
def installed(tmp_path, monkeypatch):
    store = PackageStore(tmp_path / "store")
    package, verifier = fixture_bundle(tmp_path)
    stored = store.install(package, verifier)
    runtime = Runtime(secrets.token_hex(48), store.root, "development")
    monkeypatch.setattr(runtime, "health", lambda: {"state": "healthy"})
    monkeypatch.setattr(jobs, "workspace_root", lambda: tmp_path)
    run = str(uuid.uuid4())
    payload = {"request_id": run, "run_id": run, "integration_id": str(uuid.uuid4()),
        "reference": {"connector_id": stored.connector_id, "version": stored.version, "digest": stored.bundle_digest[7:]},
        "config": {"endpoint": "https://example.test", "token_id": "fixture-identity", "verify_tls": True},
        "credentials": {"token_secret": secrets.token_hex(24)}, "selected_scopes": ["inventory"],
        "object_classes": [row["key"] for row in package.manifest["object_classes"]],
        "coverage": {"key": "test:inventory", "snapshot_mode": "full", "domains": ["assets", "interfaces", "networks", "relationships"]},
        "ingestion_token": secrets.token_urlsafe(48), "timeout_seconds": 60}
    yield runtime, payload
    runtime.jobs.shutdown()


@pytest.mark.parametrize("extra", ["playbook", "path", "command", "shell", "callback_url", "git_url", "ansible_args"])
def test_arbitrary_execution_and_callback_rejected(installed, extra):
    runtime, payload = installed
    payload[extra] = "forbidden"
    with pytest.raises(ValueError, match="invalid_request"): runtime.run_discovery(payload)
    assert payload["credentials"] == {}


@pytest.mark.parametrize("field,value", [("connector_id", "missing"), ("version", "9.9.9"), ("digest", "a" * 64)])
def test_exact_tuple_rejected_before_execution(installed, field, value, monkeypatch):
    runtime, payload = installed
    payload["reference"][field] = value
    monkeypatch.setattr(jobs.subprocess, "Popen", lambda *a, **kw: pytest.fail("unverified tuple executed"))
    with pytest.raises(ValueError, match="package_unavailable"): runtime.run_discovery(payload)
    assert payload["credentials"] == {}


def test_capacity_idempotent_request_and_cancellation(installed, monkeypatch):
    runtime, payload = installed
    # Hold accepted jobs before execution, allowing deterministic registry checks.
    monkeypatch.setattr(jobs.threading.Thread, "start", lambda self: None)
    replay = deepcopy(payload)
    first = runtime.run_discovery(payload)
    assert runtime.run_discovery(deepcopy(replay))["job_id"] == first["job_id"]
    for _ in range(3):
        extra = deepcopy(replay); extra["request_id"] = extra["run_id"] = str(uuid.uuid4())
        assert runtime.run_discovery(extra)["state"] == "queued"
    extra = deepcopy(replay); extra["request_id"] = extra["run_id"] = str(uuid.uuid4())
    with pytest.raises(ValueError, match="runtime_capacity"): runtime.run_discovery(extra)
    changed = deepcopy(replay); changed["config"]["scenario"] = "partial"
    with pytest.raises(ValueError, match="conflicting_request"): runtime.run_discovery(changed)
    assert runtime.jobs.capacity() == {"maximum": 4, "active": 4, "available": 0}
    assert runtime.cancel_job({"request_id": first["request_id"], "job_id": first["job_id"]})["job_id"] == first["job_id"]
    assert runtime.get_job({"request_id": first["request_id"], "job_id": str(uuid.uuid4())})["state"] == "unavailable"
    # Unstarted test threads have no process/workspace to reap.
    for job in runtime.jobs.by_request.values(): job.thread = None


@pytest.mark.parametrize("outcome", ["complete", "partial", "failed", "missing", "timeout", "cancelled", "secret"])
def test_terminal_workspace_cleanup_pipe_only_secrets(installed, tmp_path, monkeypatch, outcome, capsys):
    runtime, payload = installed
    monkeypatch.setenv("PYTHONPATH", "/legacy/atlas-proxmox")
    monkeypatch.setenv("ANSIBLE_COLLECTIONS_PATH", "/unreviewed/collections")
    secrets_used = [*payload["credentials"].values(), payload["ingestion_token"]]
    killed, callbacks = [], []
    monkeypatch.setattr(jobs.os, "killpg", lambda pid, number: killed.append(pid))
    class Process:
        pid = 424242
        returncode = 0
        def __init__(self, args, **kwargs):
            self.root = Path(args[-1])
            assert args[1:3] == ["-m", "atlas_runtime.discovery_worker"]
            assert all(secret not in json.dumps(args) + json.dumps(kwargs["env"]) for secret in secrets_used)
            assert kwargs["env"]["PYTHONPATH"] == str(ROOT / "apps/runtime/ansible")
            assert kwargs["env"]["ANSIBLE_COLLECTIONS_PATH"] == str(ROOT / "apps/runtime/ansible/collections")
            assert kwargs["env"]["ANSIBLE_COLLECTIONS_SCAN_SYS_PATH"] == "False"
            assert "/legacy/atlas-proxmox" not in json.dumps(kwargs["env"])
            assert self.root.stat().st_mode & 0o777 == 0o700
        def communicate(self, raw, timeout):
            inputs = json.loads(raw)
            assert secrets_used[0] in raw.decode() and secrets_used[1] not in raw.decode()
            if outcome == "timeout": raise subprocess.TimeoutExpired("fixed-child", timeout)
            if outcome == "cancelled":
                next(iter(runtime.jobs.by_request.values())).cancel.set()
            envelope = {"protocol_version": "1.0", "run_id": inputs["run_id"], "integration_id": inputs["integration_id"],
                "connector": {"id": inputs["reference"]["connector_id"], "version": inputs["reference"]["version"], "bundle_digest": "sha256:"+inputs["reference"]["digest"]},
                "observed_at": "2026-10-12T00:00:00Z", "coverage": inputs["coverage"], "source": {"version": "8.4.0"}}
            batch = {**envelope, "message_type": "observations", "batch": {"sequence": 1}, "assets": [], "networks": [], "interfaces": [], "relationships": []}
            if outcome == "secret": batch["assets"] = [{"external_id": "secret", "object_class": "i3-fixture.node", "name": secrets_used[0], "facts": []}]
            rows = [batch]
            if outcome != "missing": rows.append({**envelope, "message_type": "completion", "last_sequence": 1,
                "status": "failed" if outcome == "failed" else "completed", "completeness": "failed" if outcome == "failed" else "partial" if outcome == "partial" else "complete",
                **({"errors": [{"code": "source_unavailable"}]} if outcome == "failed" else {})})
            (self.root/"aip.ndjson").write_text("\n".join(json.dumps(row) for row in rows)); (self.root/"aip.ndjson").chmod(0o600)
        def wait(self, timeout): pass
    monkeypatch.setattr(jobs.subprocess, "Popen", Process)
    monkeypatch.setattr(runtime.jobs, "callback", lambda job, inputs, operation, message, env: callbacks.append(operation))
    accepted = runtime.run_discovery(payload)
    job = runtime.jobs.by_request[accepted["request_id"]]; job.thread.join(5)
    result = runtime.get_job({"request_id": job.request_id, "job_id": job.job_id})
    assert result["state"] == ("succeeded" if outcome in {"complete", "partial"} else "cancelled" if outcome == "cancelled" else "failed")
    assert not list(tmp_path.glob("job-*")) and payload["credentials"] == {} and killed
    assert all(secret not in json.dumps(result)+str(capsys.readouterr()) for secret in secrets_used)
    assert runtime.jobs.capacity()["available"] == 4


def test_owned_stale_workspace_cleanup(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "workspace_root", lambda: tmp_path)
    stale = tmp_path/"job-abandoned"; stale.mkdir(mode=0o700); (stale/"input.json").write_text("private temporary material")
    retain = tmp_path/"retain"; retain.mkdir(); (tmp_path/"job-link").symlink_to(retain, target_is_directory=True)
    jobs.cleanup_stale()
    assert not stale.exists() and retain.exists() and (tmp_path/"job-link").is_symlink()


def test_official_probe_only_bundle_cannot_execute_discovery(installed, tmp_path):
    from app.services.connector_catalogue import catalogue
    runtime, payload = installed
    store = PackageStore(runtime.store)
    stored = store.install(catalogue.get("proxmox", "0.1.0"), catalogue.verifier())
    payload["reference"] = {"connector_id": stored.connector_id, "version": stored.version, "digest": stored.bundle_digest[7:]}
    with pytest.raises(ValueError, match="discovery_unavailable"): runtime.run_discovery(payload)
    assert payload["credentials"] == {}
