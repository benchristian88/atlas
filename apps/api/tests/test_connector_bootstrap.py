"""Compose staging entry point uses real offline trust/store verification."""
import builtins
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import runpy
import socket
import stat
import sys
import secrets

import pytest

from app.services.connector_catalogue import catalogue
from app.services.connector_store import PackageStore
from scripts import stage_integration_bootstrap as staging

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/runtime/ansible"))
from atlas_runtime import bootstrap
from atlas_runtime.server import Runtime


@pytest.fixture
def docker_store(tmp_path, monkeypatch):
    control, directory = tmp_path / "control", tmp_path / "connector-store"
    # Emulate volume provisioning without changing the host account/ownership.
    monkeypatch.setattr(bootstrap.os, "chown", lambda *args: None)
    bootstrap.provision(control, directory)
    store = PackageStore(directory)
    monkeypatch.setenv("ATLAS_INSTALL_METHOD", "docker_compose")
    monkeypatch.setattr(staging.os, "geteuid", lambda: 10001)
    monkeypatch.setattr(staging.os, "getegid", lambda: 10001)
    for name in ("DATABASE_URL", "POSTGRES_PASSWORD", "AUTH_SECRET_KEY", "ATLAS_DATA_ENCRYPTION_KEY"):
        monkeypatch.delenv(name, raising=False)
    def mounted_store(path):
        assert path == Path("/var/lib/atlas-connectors")
        return store
    monkeypatch.setattr(staging, "PackageStore", mounted_store)
    monkeypatch.setattr("app.services.connector_store.PackageStore", mounted_store)
    def no_network(*args, **kwargs):
        pytest.fail("Offline Connector staging attempted network access")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    original_import = builtins.__import__
    def no_database(name, *args, **kwargs):
        assert not name.startswith(("app.database", "app.models", "sqlalchemy", "psycopg"))
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", no_database)
    return store, control


def run_entry_point():
    # Execute the same __main__ failure/success path as Compose's module command.
    runpy.run_path(str(ROOT / "apps/api/scripts/stage_integration_bootstrap.py"), run_name="__main__")


def snapshot(directory):
    return {str(path.relative_to(directory)): (
        path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns,
        stat.S_IMODE(path.stat().st_mode), path.stat().st_uid, path.stat().st_gid,
    ) for path in directory.rglob("*") if path.is_file()}


def test_fresh_docker_store_receives_exact_offline_bundle_and_restart_preserves_state(docker_store, capsys):
    store, control = docker_store
    assert list(store.root.iterdir()) == []
    secret = (control / "control.secret").read_bytes()
    run_entry_point()
    package = catalogue.get("proxmox", "0.1.0")
    digest = package.bundle_digest.removeprefix("sha256:")
    installed = store.root / "proxmox" / "0.1.0" / digest
    assert (installed / "bundle.tar.gz").read_bytes() == package.archive_path.read_bytes()
    assert hashlib.sha256((installed / "bundle.tar.gz").read_bytes()).hexdigest() == digest
    assert stat.S_IMODE(installed.stat().st_mode) == 0o555
    assert stat.S_IMODE((store.root / ".install.lock").stat().st_mode) == 0o600
    assert (store.root / ".install.lock").stat().st_uid == os.getuid()
    runtime = Runtime(secrets.token_hex(48), store.root, "docker_compose")
    reference = {"connector_id": "proxmox", "version": "0.1.0", "digest": digest}
    assert runtime.verify_connector(reference)["state"] == "verified"
    before = snapshot(store.root)
    bootstrap.provision(control, store.root)
    run_entry_point()
    assert snapshot(store.root) == before
    assert (control / "control.secret").read_bytes() == secret
    assert runtime.verify_connector(reference)["state"] == "verified"
    assert capsys.readouterr().out.count("Approved bootstrap packages verified and staged") == 2


@pytest.mark.parametrize("failure", ["tampered_bundle", "mismatched_identity"])
def test_bad_bootstrap_fails_nonzero_without_publishing_or_success(docker_store, tmp_path, monkeypatch, capsys, failure):
    store, _ = docker_store
    index, packages = catalogue._load()
    package = next(package for package in packages if package.package_available)
    if failure == "tampered_bundle":
        archive = tmp_path / "invalid-bundle.tar.gz"
        archive.write_bytes(package.archive_path.read_bytes() + b"tampered")
        package = replace(package, archive_path=archive)
    else:
        package = replace(package, connector_id="mismatched")
    monkeypatch.setattr(catalogue, "_load", lambda: (index, [package]))
    with pytest.raises(SystemExit) as error:
        run_entry_point()
    assert error.value.code and "Cannot stage approved bootstrap" in str(error.value)
    assert list(store.root.iterdir()) == []
    assert "verified and staged" not in capsys.readouterr().out


def test_tampered_installed_bytes_are_not_silently_repaired(docker_store, capsys):
    store, _ = docker_store
    run_entry_point()
    capsys.readouterr()
    package = catalogue.get("proxmox", "0.1.0")
    path = store.root / "proxmox" / "0.1.0" / package.bundle_digest[7:] / "contents/NOTICE"
    path.chmod(0o600)
    path.write_text("tampered")
    with pytest.raises(SystemExit):
        run_entry_point()
    assert path.read_text() == "tampered"
    assert "verified and staged" not in capsys.readouterr().out


@pytest.mark.parametrize("method,uid,gid", [("systemd", 10001, 10001), ("docker_compose", 10002, 10001), ("docker_compose", 10001, 10002)])
def test_staging_refuses_wrong_service_authority(monkeypatch, method, uid, gid):
    monkeypatch.setenv("ATLAS_INSTALL_METHOD", method)
    monkeypatch.setattr(staging.os, "geteuid", lambda: uid)
    monkeypatch.setattr(staging.os, "getegid", lambda: gid)
    monkeypatch.setattr(staging, "PackageStore", lambda *args: pytest.fail("Unauthorized staging accessed the store"))
    with pytest.raises(SystemExit, match="installation authority"):
        staging.main()
