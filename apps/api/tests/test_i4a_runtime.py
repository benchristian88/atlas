"""Reviewed collection identity, isolated packaging and canonical health regressions."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "apps/runtime/ansible"
sys.path.insert(0, str(RUNTIME))
from atlas_runtime import collections, server
from app.services import integration_runtime as transport
from app.services.connector_catalogue import compatibility
from app.services.connector_store import PackageStore, PackageStoreError
from tests.test_connector_packages import bundle, manifest


@pytest.fixture
def installed(tmp_path, monkeypatch):
    path = tmp_path / "collections"
    collections.install(ROOT / "vendor/collections", path=path)
    baseline = json.loads((RUNTIME / "baseline.json").read_bytes())
    monkeypatch.setattr(server, "version", lambda name: baseline["sdk_version"] if name == "atlas-connector-sdk" else baseline["dependencies"][name])
    monkeypatch.setattr(server, "collection_health", lambda: collections.health(path=path))
    return path, server.Runtime(secrets.token_hex(48), tmp_path / "store", "development")


def dependency():
    _, rows = collections.load_lock()
    row = rows[0]
    return {"kind": "collection", "name": row["name"], "version": row["version"],
            "digest": "sha256:" + row["sha256"], "licence": "GPL-3.0-or-later"}


def test_lock_archive_baseline_and_shipped_modules_agree():
    raw, rows = collections.load_lock()
    baseline = json.loads((RUNTIME / "baseline.json").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == baseline["collection_lock_digest"]
    for row in rows:
        contents = collections.reviewed_archive(row, (ROOT / "vendor/collections" / row["archive"]).read_bytes())
        assert baseline["collections"][row["name"]] == {
            "version": row["version"], "digest": "sha256:" + row["sha256"], "state": "compatible"}
        for name in ["proxmox_cluster_status_info", "proxmox_node_info", "proxmox_vm_info", "proxmox_storage_info", "proxmox_node_network_info"]:
            assert "plugins/modules/" + name + ".py" in contents
        from packaging.specifiers import SpecifierSet
        assert baseline["dependencies"]["ansible-core"] in SpecifierSet(row["requires_ansible"])
        assert baseline["dependencies"]["proxmoxer"] in SpecifierSet(row["python_requirements"]["proxmoxer"])


def test_normal_health_satisfies_exact_catalogue_dependency(installed):
    path, runtime = installed
    health = runtime.health()
    assert health["state"] == "healthy"
    row = dependency()
    assert health["collections"][row["name"]]["version"] == row["version"]
    assert health["collections"][row["name"]]["digest"] == row["digest"]
    safe = transport._safe_health(health, runtime.capabilities(), transport._approved_baseline())
    value = manifest()
    value["implementation"]["dependencies"] = [row]
    assert compatibility(value, safe)["state"] == "compatible"
    assert str(path) not in json.dumps(safe)


@pytest.mark.parametrize("attack", ["module", "files_manifest", "version", "missing", "extra", "symlink", "lock"])
def test_installed_identity_drift_fails_closed(installed, tmp_path, monkeypatch, attack):
    path, runtime = installed
    directory = path / "ansible_collections/community/proxmox"
    target = directory / "plugins/modules/proxmox_vm_info.py"
    if attack == "lock":
        local = tmp_path / "baseline"
        local.mkdir()
        local.joinpath("collections.lock.json").write_bytes((RUNTIME / "collections.lock.json").read_bytes() + b"\n")
        monkeypatch.setattr(server, "collection_health", lambda: collections.health(root=local, path=path))
    elif attack == "extra":
        directory.chmod(0o755)
        directory.joinpath("injected.py").write_text("unexpected code")
    elif attack == "symlink":
        target.parent.chmod(0o755)
        data = target.read_bytes()
        target.unlink()
        external = tmp_path / "external.py"
        external.write_bytes(data)
        target.symlink_to(external)
    elif attack == "missing":
        target.parent.chmod(0o755)
        target.unlink()
    else:
        if attack == "files_manifest":
            target = directory / "FILES.json"
        elif attack == "version":
            target = directory / "MANIFEST.json"
        target.chmod(0o644)
        if attack == "version":
            value = json.loads(target.read_bytes())
            value["collection_info"]["version"] = "999.0.0"
            target.write_text(json.dumps(value))
        else:
            target.write_bytes(target.read_bytes() + b"\n")
    health = runtime.health()
    assert health["state"] == "incompatible"
    if attack != "lock":
        assert health["collections"]["community.proxmox"]["state"] == "incompatible"
        assert health["collections"]["community.proxmox"]["digest"] is None
    safe = transport._safe_health(health, runtime.capabilities(), transport._approved_baseline())
    value = manifest()
    value["implementation"]["dependencies"] = [dependency()]
    assert compatibility(value, safe)["state"] != "compatible"


@pytest.mark.parametrize("change", [{"version": "1.0.0"}, {"digest": "sha256:" + "0" * 64},
                                    {"state": "incompatible"}, {"digest": None}])
def test_catalogue_cannot_accept_wrong_or_unverified_collection(installed, change):
    _, runtime = installed
    safe = transport._safe_health(runtime.health(), runtime.capabilities(), transport._approved_baseline())
    value = manifest()
    value["implementation"]["dependencies"] = [dependency()]
    safe["capabilities"]["collections"]["community.proxmox"].update(change)
    assert compatibility(value, safe)["state"] == "runtime_update_required"
    safe["capabilities"]["collections"] = {}
    assert compatibility(value, safe)["state"] == "runtime_update_required"


@pytest.mark.parametrize("change", [{"path": "/private/secret"}, {"version": "/private/secret"},
                                    {"digest": "/private/secret"}, {"state": "/private/secret"}])
def test_health_rejects_unsanitised_collection_data(installed, change):
    _, runtime = installed
    health, capabilities = runtime.health(), runtime.capabilities()
    health["collections"]["community.proxmox"].update(change)
    with pytest.raises(ValueError):
        transport._safe_health(health, capabilities, transport._approved_baseline())


def test_health_and_capability_identity_must_agree(installed):
    _, runtime = installed
    health, capabilities = runtime.health(), runtime.capabilities()
    capabilities["collections"] = {}
    assert transport._safe_health(health, capabilities, transport._approved_baseline())["status"] == "incompatible"


def test_unreviewed_collection_on_protected_search_path_fails_closed(installed):
    path, runtime = installed
    path.joinpath("ansible_collections/unreviewed/extra").mkdir(parents=True)
    health = runtime.health()
    assert health["state"] == "incompatible"
    assert health["collections"]["unreviewed.extra"] == {"version": None, "digest": None, "state": "incompatible"}


def test_tampered_reviewed_archive_cannot_be_installed(tmp_path):
    _, rows = collections.load_lock()
    source = tmp_path / "vendor"
    source.mkdir()
    source.joinpath(rows[0]["archive"]).write_bytes(b"unreviewed")
    with pytest.raises(ValueError, match="collection_archive_mismatch"):
        collections.install(source, path=tmp_path / "collections")
    assert not (tmp_path / "collections").exists()


def test_connector_install_is_store_only_and_cannot_supply_collection_code(installed, tmp_path):
    path, runtime = installed
    before = runtime.health()
    value = dependency()
    package, verifier, _ = bundle(tmp_path, domain_change=lambda m: m["implementation"]["dependencies"].append(value))
    stored = PackageStore(runtime.store).install(package, verifier)
    assert stored.manifest["implementation"]["dependencies"] == [value]
    assert runtime.health() == before
    for name in ["collections/ansible_collections/test/injected/plugins/modules/example.py", "ansible_collections/test/injected/MANIFEST.json"]:
        package, verifier, _ = bundle(tmp_path, extra=[(name, b"injected")])
        with pytest.raises(PackageStoreError, match="runtime_owned_collection_path"):
            PackageStore(tmp_path / "other-store").install(package, verifier)


def test_docker_native_package_and_install_commands_use_same_reviewed_archive(monkeypatch, tmp_path):
    package = json.loads((ROOT / "infra/release/package-manifest.json").read_bytes())
    assert "vendor/collections/" in package["common"]
    assert "apps/runtime/ansible/collections.lock.json" in package["required_common"]
    assert "vendor/collections/community-proxmox-2.0.0.tar.gz" in package["required_common"]
    docker = (RUNTIME / "Dockerfile").read_text()
    assert "python -m atlas_runtime.collections /vendor/collections" in docker
    assert "ANSIBLE_COLLECTIONS_SCAN_SYS_PATH=False" in docker
    sys.path.insert(0, str(ROOT / "infra/install"))
    native = importlib.import_module("native")
    calls = []
    monkeypatch.setattr(native, "DESTINATION", tmp_path)
    monkeypatch.setattr(native, "run", lambda args, **kwargs: calls.append(args))
    native.build_runtime()
    assert any(call[1:3] == ["-m", "atlas_runtime.collections"] and call[-1] == str(tmp_path / "vendor/collections") for call in calls)


def test_production_connector_remains_probe_only():
    from app.services.connector_catalogue import catalogue
    package = catalogue.get("proxmox", "0.1.0")
    assert package.manifest["capabilities"] == {
        "test_connection": True, "discover": False, "scheduling": False, "complete_snapshot": False}
    assert package.manifest["implementation"]["dependencies"] == []
    assert package.manifest["implementation"]["entry_points"] == {"test_connection": "test_connection"}
    assert package.manifest["source_versions"]["qualification"] == "unqualified"


@pytest.mark.skipif(not os.getenv("ATLAS_TEST_RUNTIME_PYTHON"), reason="requires exact installed runtime environment")
def test_real_runtime_versions_and_collection_resolution_ignore_legacy_pythonpath(installed, tmp_path):
    path, _ = installed
    python = os.environ["ATLAS_TEST_RUNTIME_PYTHON"]
    fake = tmp_path / "legacy"
    fake.mkdir()
    fake.joinpath("proxmoxer.py").write_text("raise RuntimeError('legacy import')")
    metadata = fake / "atlas_proxmox-999.0.0.dist-info"
    metadata.mkdir()
    metadata.joinpath("METADATA").write_text("Name: atlas-proxmox\nVersion: 999.0.0\n")
    env = {"PATH": str(Path(python).parent) + ":/usr/bin:/bin", "HOME": str(tmp_path),
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(fake),
           "ANSIBLE_COLLECTIONS_PATH": str(path), "ANSIBLE_COLLECTIONS_SCAN_SYS_PATH": "False"}
    # The runtime child allowlist overwrites inherited plugin search paths.
    env["PYTHONPATH"] = str(RUNTIME)
    code = """import importlib.metadata as m, json
import proxmoxer, requests
print(json.dumps({d.metadata['Name'].lower().replace('_','-'): d.version for d in m.distributions()}))
"""
    process = subprocess.run([python, "-c", code], env=env, capture_output=True, text=True, check=True)
    actual = json.loads(process.stdout)
    baseline = json.loads((RUNTIME / "baseline.json").read_bytes())
    assert {name: actual[name] for name in baseline["dependencies"]} == baseline["dependencies"]
    assert "atlas-proxmox" not in actual and "httpx" not in actual
    listing = subprocess.run([str(Path(python).parent / "ansible-galaxy"), "collection", "list", "--format", "json"],
                             env={**env, "PYTHONPATH": str(RUNTIME)}, capture_output=True, text=True, check=True)
    listed = json.loads(listing.stdout)
    assert listed[str(path / "ansible_collections")] == {"community.proxmox": {"version": "2.0.0"}}
    # Ansible 2.19 also advertises its internal pseudo-collection.
    assert {name for values in listed.values() for name in values} <= {"community.proxmox", "ansible._protomatter"}
