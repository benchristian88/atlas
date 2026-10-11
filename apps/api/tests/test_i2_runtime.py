"""Real trusted bundle identity and bounded private probe material cleanup."""
import json
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/runtime/ansible"))
from atlas_runtime.server import Runtime
from atlas_runtime import probe
from app.services.connector_catalogue import catalogue
from app.services.connector_store import PackageStore


@pytest.fixture
def installed(tmp_path, monkeypatch):
    store = PackageStore(tmp_path / "store")
    package = catalogue.get("proxmox", "0.1.0")
    stored = store.install(package, catalogue.verifier())
    runtime = Runtime(secrets.token_hex(48), store.root, "development")
    monkeypatch.setattr(runtime, "health", lambda: {"state": "healthy"})
    monkeypatch.setattr(probe, "workspace_root", lambda: tmp_path)
    reference = {"connector_id": stored.connector_id, "version": stored.version, "digest": stored.bundle_digest[7:]}
    payload = {"reference": reference, "request_id": str(uuid.uuid4()), "config": {"endpoint": "https://192.168.1.2:8006"},
        "credentials": {"token_id": "fixture_" + secrets.token_hex(8) + "@pve!probe", "token_secret": secrets.token_urlsafe(32)}}
    return runtime, payload


@pytest.mark.parametrize("outcome", ["connected", "authentication_failed", "timeout"])
def test_success_failure_timeout_cleanup_no_credentials_in_argv_or_environment(installed, tmp_path, monkeypatch, outcome, capsys):
    runtime, payload = installed
    values = list(payload["credentials"].values())
    killed = []
    monkeypatch.setattr(probe.os, "killpg", lambda pid, signal: killed.append(pid))
    class Process:
        pid = 919191
        def __init__(self, args, **kwargs):
            self.root = Path(args[-1])
            assert args[1:3] == ["-m", "atlas_runtime.probe_worker"]
            assert all(value not in json.dumps(args) + json.dumps(kwargs["env"]) for value in values)
            assert stat.S_IMODE(self.root.stat().st_mode) == 0o700
        def communicate(self, data, timeout):
            assert timeout == 22
            assert all(value in data.decode() for value in values)
            if outcome == "timeout":
                raise subprocess.TimeoutExpired("fixed-probe", timeout)
            output = {"success": outcome == "connected", "category": outcome, "source_version": "8.4",
                "raw": values[0], "stdout": values[1]}
            path = self.root / "result.json"
            path.write_text(json.dumps(output))
            path.chmod(0o600)
        def wait(self): pass
    monkeypatch.setattr(probe.subprocess, "Popen", Process)
    result = runtime.test_connection(payload)
    assert result["category"] == outcome
    assert payload["credentials"] == {}
    assert not list(tmp_path.glob("probe-*"))
    assert killed == [Process.pid]
    assert all(value not in json.dumps(result) + str(capsys.readouterr()) for value in values)


@pytest.mark.parametrize("field,value", [("connector_id", "missing"), ("version", "9.9.9"), ("digest", "a" * 64)])
def test_wrong_identity_cannot_execute(installed, monkeypatch, field, value):
    runtime, payload = installed
    payload["reference"][field] = value
    monkeypatch.setattr(probe.subprocess, "Popen", lambda *a, **kw: pytest.fail("unverified package executed"))
    assert runtime.test_connection(payload)["category"] == "package_unavailable"


@pytest.mark.parametrize("extra", ["command", "playbook", "path", "git_url", "ansible_args"])
def test_no_arbitrary_execution_surface(installed, extra):
    runtime, payload = installed
    payload[extra] = "forbidden"
    with pytest.raises(ValueError):
        runtime.test_connection(payload)


def test_stale_workspace_cleanup_is_restricted_to_owned_probe_directories(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "workspace_root", lambda: tmp_path)
    stale = tmp_path / "probe-abandoned"
    stale.mkdir(mode=0o700)
    (stale / "input.json").write_text("opaque fixture")
    unrelated = tmp_path / "retain"
    unrelated.mkdir()
    (tmp_path / "probe-link").symlink_to(unrelated, target_is_directory=True)
    probe.cleanup_stale()
    assert not stale.exists() and unrelated.exists() and (tmp_path / "probe-link").is_symlink()


def test_probe_capacity_failure_revokes_received_credentials(installed, monkeypatch):
    runtime, payload = installed
    for _ in range(4):
        assert runtime._probe_slots.acquire(blocking=False)
    monkeypatch.setattr(probe.subprocess, 'Popen', lambda *a, **kw: pytest.fail('busy runtime executed'))
    try:
        assert runtime.test_connection(payload)['category'] == 'runtime_unavailable'
        assert payload['credentials'] == {}
    finally:
        for _ in range(4):
            runtime._probe_slots.release()
