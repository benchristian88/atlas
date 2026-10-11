"""Deployment and release invariants for the isolated local runtime."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "infra/install"))
sys.path.insert(0, str(ROOT / "apps/runtime/ansible"))
from atlas_runtime import bootstrap
configuration = importlib.import_module("configuration")


def test_docker_runtime_is_private_isolated_read_only_and_failure_independent():
    compose = yaml.safe_load((ROOT / "infra/docker/docker-compose.yml").read_text())
    runtime = compose["services"]["runtime"]
    assert "ports" not in runtime
    assert runtime["networks"] == ["runtime_private", "runtime_source"]
    assert compose["networks"]["runtime_private"]["internal"] is True
    assert compose["networks"]["runtime_source"]["driver"] == "bridge"
    assert compose["networks"]["runtime_source"]["internal"] is False
    assert {
        name for name, service in compose["services"].items()
        if "runtime_source" in service.get("networks", [])
    } == {"runtime"}
    assert {
        name for name, service in compose["services"].items()
        if "runtime_private" in service.get("networks", [])
    } == {"api", "runtime"}
    assert runtime["read_only"] is True
    assert runtime["cap_drop"] == ["ALL"]
    assert runtime["security_opt"] == ["no-new-privileges:true"]
    assert not runtime.get("privileged", False)
    assert "network_mode" not in runtime
    assert not runtime.get("cap_add") and not runtime.get("devices")
    assert set(runtime["volumes"]) == {
        "runtime_control:/run/atlas-runtime-control:ro",
        "connector_store:/var/lib/atlas-connectors:ro",
    }
    assert not any("postgres" in mount or "docker.sock" in mount for mount in runtime["volumes"])
    assert not any("DATABASE" in key or "AUTH_SECRET" in key for key in runtime["environment"])
    assert "runtime" not in compose["services"]["api"]["depends_on"]
    assert "runtime-init" not in compose["services"]["api"]["depends_on"]
    assert "runtime_private" in compose["services"]["api"]["networks"]
    assert compose["services"]["runtime-init"]["network_mode"] == "none"
    assert runtime["healthcheck"]["test"] == ["CMD", "python", "-m", "atlas_runtime.healthcheck"]
    assert not any("runtime" in str(value) for value in compose["services"]["gateway"].get("environment", {}).values())


def test_native_runtime_is_loopback_dedicated_and_has_no_atlas_credentials(monkeypatch):
    from atlas_runtime import server
    unit = (ROOT / "infra/systemd/atlas-runtime.service").read_text()
    assert "User=atlas-runtime" in unit and "NoNewPrivileges=true" in unit
    assert "runtime-venv/bin/python" in unit
    assert "EnvironmentFile=" not in unit and "postgres" not in unit.lower()
    assert "ReadOnlyPaths=/var/lib/atlas-connectors /etc/atlas-runtime" in unit
    secret = secrets.token_hex(48)
    monkeypatch.setenv("ATLAS_RUNTIME_CONTROL_SECRET_FILE", "/unread")
    monkeypatch.setenv("ATLAS_RUNTIME_PACKAGING_MODE", "systemd")
    monkeypatch.setenv("ATLAS_RUNTIME_HOST", "0.0.0.0")
    monkeypatch.setattr(server, "load_secret", lambda path: secret)
    addresses = []
    class FakeServer:
        def __init__(self, address, runtime): addresses.append(address)
        def serve_forever(self): pass
    monkeypatch.setattr(server, "Server", FakeServer)
    server.main()
    assert addresses == [("127.0.0.1", 8091)]
    api = (ROOT / "infra/systemd/atlas-api.service").read_text()
    assert "Requires=atlas-runtime" not in api and "atlas-runtime.service" not in api


def test_compose_secret_generated_once_protected_and_not_derived_from_auth(monkeypatch, tmp_path):
    monkeypatch.setattr(bootstrap.os, "chown", lambda *args: None)
    directory, store = tmp_path / "control", tmp_path / "store"
    bootstrap.provision(directory, store)
    secret = (directory / "control.secret").read_bytes()
    assert re.fullmatch(rb"[a-f0-9]{96}\n", secret)
    assert stat.S_IMODE((directory / "control.secret").stat().st_mode) == 0o400
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    bootstrap.provision(directory, store)
    assert (directory / "control.secret").read_bytes() == secret
    (directory / "control.secret").chmod(0o600)
    (directory / "control.secret").write_text("invalid")
    with pytest.raises(ValueError): bootstrap.provision(directory, store)
    assert (directory / "control.secret").read_text() == "invalid"


def test_runtime_upgrade_settings_preserve_secrets_and_manual_only(tmp_path):
    path = tmp_path / "atlas.env"
    content = "AUTH_SECRET_KEY=" + secrets.token_hex(48) + "\nATLAS_RUNTIME_ENABLED=false\n"
    path.write_text(content)
    path.chmod(0o600)
    configuration.add_runtime_configuration(path, "systemd")
    first = path.read_bytes()
    configuration.add_runtime_configuration(path, "systemd")
    assert path.read_bytes() == first and first.startswith(content.encode())
    assert b"ATLAS_RUNTIME_URL=http://127.0.0.1:8091" in first
    assert b"ATLAS_RUNTIME_CONTROL_SECRET=" not in first
    assert path.stat().st_mode & 0o777 == 0o600


def test_native_secret_provision_is_protected_idempotent_and_preserves_store(monkeypatch, tmp_path):
    native_runtime = importlib.import_module("runtime")
    account = SimpleNamespace(pw_uid=10002, pw_gid=10002)
    monkeypatch.setattr(native_runtime.pwd, "getpwnam", lambda name: account)
    monkeypatch.setattr(native_runtime.grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=10002 if name == "atlas-runtime" else 10003))
    calls = []
    monkeypatch.setattr(native_runtime, "run", lambda args: calls.append(args))
    monkeypatch.setattr(native_runtime.os, "chown", lambda *args: None)
    configuration = tmp_path / "etc/atlas/atlas.env"
    configuration.parent.mkdir(parents=True)
    configuration.write_text("AUTH_SECRET_KEY=" + secrets.token_hex(48) + "\n")
    original_config = configuration.read_bytes()
    store = tmp_path / "var/lib/atlas-connectors"
    store.parent.mkdir(parents=True)
    directory = tmp_path / "etc/atlas-runtime"
    original_stat = Path.stat
    def root_stat(path, **kwargs):
        info = original_stat(path, **kwargs)
        if path in {store, directory}:
            return SimpleNamespace(st_uid=0, st_mode=info.st_mode)
        return info
    monkeypatch.setattr(Path, "stat", root_stat)
    original_fstat = os.fstat
    monkeypatch.setattr(native_runtime.os, "fstat", lambda descriptor: SimpleNamespace(st_uid=0, st_mode=original_fstat(descriptor).st_mode))
    native_runtime.configure(configuration, store)
    secret = directory / "control.secret"
    credential = secret.read_bytes()
    assert re.fullmatch(rb"[a-f0-9]{96}\n", credential)
    assert secret.stat().st_mode & 0o777 == 0o640
    assert directory.stat().st_mode & 0o777 == store.stat().st_mode & 0o777 == 0o750
    preserved = store / "history-marker"
    preserved.write_text("preserve")
    native_runtime.configure(configuration, store)
    assert secret.read_bytes() == credential
    assert preserved.read_text() == "preserve" and configuration.read_bytes() == original_config
    assert ["usermod", "--append", "--groups", "atlas-runtime-control", "atlas"] in calls
    assert ["usermod", "--append", "--groups", "atlas-runtime-control", "atlas-runtime"] in calls
    secret.chmod(0o644)
    with pytest.raises(ValueError, match="refusing to replace"):
        native_runtime.configure(configuration, store)
    assert secret.read_bytes() == credential


def test_native_installs_original_contracts_without_overwriting_other_docs(monkeypatch, tmp_path):
    native = importlib.import_module("native")
    destination = tmp_path / "installation"
    monkeypatch.setattr(native, "DESTINATION", destination)
    unrelated = destination / "docs/operator-notes.md"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("preserve operator notes")
    for _ in range(2):
        native.install_contracts()
        target = destination / "docs/architecture/integrations/contracts"
        source = ROOT / "docs/architecture/integrations/contracts"
        assert (target / "connector-manifest-v1.schema.json").read_bytes() == (source / "connector-manifest-v1.schema.json").read_bytes()
        assert {path.name: path.read_bytes() for path in (target / "manifests").glob("*.json")} == {path.name: path.read_bytes() for path in (source / "manifests").glob("*.json")}
        assert unrelated.read_text() == "preserve operator notes"
        assert not (target / "aip-v1.schema.json").exists()


def test_native_runtime_start_failure_does_not_abort_knowledge_startup(monkeypatch, capsys):
    native = importlib.import_module("native")
    monkeypatch.setattr(native, "run", lambda args: (_ for _ in ()).throw(OSError("internal failure")))
    native.start_runtime({"ATLAS_RUNTIME_ENABLED": "true"})
    output = capsys.readouterr().out
    assert "Atlas knowledge services will continue" in output
    assert "internal failure" not in output


def test_native_runtime_dependency_or_missing_legacy_unit_failure_is_isolated(monkeypatch, tmp_path, capsys):
    native = importlib.import_module("native")
    monkeypatch.setattr(native, "DESTINATION", tmp_path / "installation")
    monkeypatch.setattr(native, "run", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("internal failure")))
    native.build_runtime()
    native.stop_runtime()
    output = capsys.readouterr().out
    assert output.count("Atlas knowledge services will continue") == 2
    assert "internal failure" not in output


def test_compose_install_runtime_failure_still_hands_off_setup_code(monkeypatch, tmp_path, capsys):
    installer = importlib.import_module("compose")
    monkeypatch.setattr(sys, "argv", ["compose.py", "--env-file", str(tmp_path / "atlas.env")])
    monkeypatch.setattr(installer, "generate_configuration", lambda path, method: {"ATLAS_BIND_ADDRESS": "127.0.0.1", "ATLAS_PORT": "3000"})
    calls = []
    def call(args, **kwargs):
        calls.append(args)
        if args[-1] == "runtime":
            raise OSError("internal runtime failure")
    monkeypatch.setattr(installer.subprocess, "run", call)
    installer.main()
    assert len(calls) == 3 and "scripts.setup_code" in calls[-1]
    assert "runtime" not in calls[0]
    assert "Atlas knowledge services are ready" in capsys.readouterr().out


def test_dependency_baseline_sbom_and_notices_are_exact_and_core_boundary_preserved():
    root = ROOT / "apps/runtime/ansible"
    baseline = json.loads((root / "baseline.json").read_text())
    pins = dict(line.split("==") for line in (root / "requirements.lock").read_text().splitlines() if line and not line.startswith("#"))
    assert {name.lower().replace("_", "-"): value for name, value in pins.items()} == baseline["dependencies"]
    assert hashlib.sha256((root / "requirements.lock").read_bytes()).hexdigest() == baseline["dependency_lock_digest"]
    sbom = json.loads((root / "sbom.cdx.json").read_text())
    assert {entry["name"]: entry["version"] for entry in sbom["components"]} == pins
    for entry in sbom["components"]:
        assert entry["licenses"] and entry["hashes"][0]["alg"] == "SHA-256"
        notices = next(prop["value"] for prop in entry["properties"] if prop["name"] == "atlas:upstream-notices")
        assert all((root / path).is_file() for path in notices.split(",") if path)
    assert (root / "notices/ansible-core/COPYING").is_file()
    assert re.search(r"FROM python:3\.12-slim-trixie@sha256:[a-f0-9]{64}", (root / "Dockerfile").read_text())
    for path in (ROOT / "apps/api/app").rglob("*.py"):
        assert not re.search(r"(?m)^\s*(?:import|from)\s+(?:ansible|ansible_runner|atlas_runtime)\b", path.read_text()), path
    assert "ansible" not in (ROOT / "apps/api/requirements.txt").read_text()
