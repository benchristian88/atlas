"""Exact local authorization never confers normal catalogue qualification."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import time
from types import SimpleNamespace

import pytest

from app.services.connector_contracts import validate_manifest
from app.services.connector_catalogue import catalogue
from app.services.connector_qualification import authorize, manifest_digest, OperatorQualificationVerifier
from app.services.connector_store import PackageStore
from app.services import connector_lifecycle as lifecycle
from scripts import qualify_connector as cli
from tests.test_connector_packages import bundle

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/runtime/ansible"))
from atlas_runtime.server import Runtime


def unqualified(package):
    """Only inert synthetic code; no source call or claimed vendor evidence."""
    manifest = deepcopy(package.manifest)
    manifest["manifest_version"] = "1.1"
    manifest["version"] = "1.0.0-operator-test"
    manifest["source_versions"].update(qualification="unqualified", qualified_versions=[])
    manifest["distribution"]["provenance"]["source_commit"] = "b" * 40
    with tarfile.open(package.archive_path) as archive:
        files = {m.name: archive.extractfile(m).read() for m in archive if m.isfile()}
    files["manifest.json"] = json.dumps({k: v for k, v in manifest.items() if k != "distribution"}).encode()
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz", format=tarfile.USTAR_FORMAT) as archive:
        for name, raw in files.items():
            member = tarfile.TarInfo(name); member.size = len(raw); member.mode = 0o644
            archive.addfile(member, io.BytesIO(raw))
    package.archive_path.write_bytes(output.getvalue())
    digest = "sha256:" + hashlib.sha256(output.getvalue()).hexdigest()
    manifest["distribution"]["bundle_digest"] = digest
    return replace(package, version=manifest["version"], bundle_digest=digest, manifest=manifest, source="operator-qualification")


def arguments(package, tmp_path):
    path = tmp_path / "manifest.json"; path.write_text(json.dumps(package.manifest))
    return SimpleNamespace(manifest=path, bundle=package.archive_path, connector_id=package.connector_id,
        version=package.version, digest=package.bundle_digest, atlas_commit="a" * 40, connector_commit="b" * 40)


@pytest.fixture
def staged(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_CONNECTOR_QUALIFICATION_ENABLED", "1")
    monkeypatch.setenv("ATLAS_BUILD_ID", "a" * 40)
    store = PackageStore(tmp_path / "qualification-store")
    monkeypatch.setattr(lifecycle, "package_store", lambda: store)
    package = unqualified(bundle(tmp_path)[0])
    args = arguments(package, tmp_path)
    cli.stage(args)
    return store, package, args


def runtime_result(store, package):
    runtime = Runtime("test-inspection-only", store.root, "development")
    try:
        return runtime.verify_connector({"connector_id": package.connector_id, "version": package.version,
                                         "digest": package.bundle_digest[7:]})
    finally:
        runtime.jobs.shutdown()


def test_exact_stage_is_verified_independently_and_still_production_rejected(staged):
    store, package, args = staged
    assert store.verify_connector(package.connector_id, package.version, package.bundle_digest)["state"] == "verified"
    assert runtime_result(store, package)["state"] == "verified"
    cli.stage(args)  # Idempotent, keeps the original expiry/receipt.
    with pytest.raises(ValueError, match="package_not_qualified"):
        validate_manifest(package.manifest, activation=True)
    with pytest.raises(ValueError, match="package_not_qualified"):
        PackageStore(store.root.parent / "ordinary-store").install(replace(package, source="bootstrap"), catalogue.verifier())
    with pytest.raises(ValueError, match="package_not_qualified"):
        lifecycle.activate(None, store.install(package, OperatorQualificationVerifier(store.root)), {})
    assert catalogue.get("proxmox").version == "0.1.0"


@pytest.mark.parametrize("failure", ["disabled", "wrong_atlas", "missing", "expired", "writable", "wrong_store", "wrong_manifest", "wrong_commit", "bad_receipt", "forged_method", "symlink", "unexpected_field"])
def test_both_verifiers_fail_closed_on_revocation_tamper_or_scope_failure(staged, monkeypatch, failure):
    store, package, _ = staged
    path = store.root / ".qualification.json"
    grant = json.loads(path.read_text())
    if failure == "disabled":
        monkeypatch.delenv("ATLAS_CONNECTOR_QUALIFICATION_ENABLED")
    elif failure == "wrong_atlas":
        monkeypatch.setenv("ATLAS_BUILD_ID", "c" * 40)
    elif failure == "missing":
        path.unlink()
    elif failure == "symlink":
        path.rename(store.root / "other.json"); path.symlink_to(store.root / "other.json")
    elif failure in {"bad_receipt", "forged_method"}:
        receipt = store._path(package.connector_id, package.version, package.bundle_digest) / "verification.json"
        value = json.loads(receipt.read_text()); value["verification"]["qualification_digest"] = "sha256:" + "0" * 64
        if failure == "forged_method": value["verification"]["method"] = "atlas-release-bootstrap"
        receipt.chmod(0o644); receipt.write_text(json.dumps(value)); receipt.chmod(0o444)
    else:
        if failure == "expired": grant["expires_at"] = int(time.time()) - 1
        if failure == "wrong_store": grant["store_path"] = "/elsewhere"
        if failure == "wrong_manifest": grant["manifest_digest"] = "sha256:" + "0" * 64
        if failure == "wrong_commit": grant["connector_commit"] = "c" * 40
        if failure == "unexpected_field": grant["skip_verification"] = True
        path.chmod(0o644); path.write_text(json.dumps(grant))
        if failure != "writable": path.chmod(0o444)
    with pytest.raises(ValueError):
        store.verify_connector(package.connector_id, package.version, package.bundle_digest)
    assert runtime_result(store, package)["state"] == "unavailable"


def test_grant_cannot_approve_another_identity_or_be_used_in_default_store(staged, monkeypatch):
    store, package, args = staged
    manifest = deepcopy(package.manifest); manifest["version"] = "1.0.0-other"
    with pytest.raises(ValueError): authorize(store.root, manifest)
    monkeypatch.setattr(lifecycle, "package_store", lambda: SimpleNamespace(root=Path("/var/lib/atlas-connectors")))
    with pytest.raises(ValueError, match="operator_qualification_disabled"): cli.selected(args)


def test_staging_requires_exact_build_commit_and_bundle(staged, monkeypatch):
    _, _, args = staged
    monkeypatch.setenv("ATLAS_BUILD_ID", "c" * 40)
    with pytest.raises(ValueError, match="qualification_atlas_build_mismatch"): cli.selected(args)
    monkeypatch.setenv("ATLAS_BUILD_ID", "a" * 40)
    args.bundle.write_bytes(args.bundle.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="bundle_digest_mismatch"): cli.selected(args)


def test_local_command_requires_installation_authority(monkeypatch):
    monkeypatch.setattr(cli.os, "geteuid", lambda: 501)
    monkeypatch.setattr(cli.os, "getegid", lambda: 501)
    with pytest.raises(ValueError, match="qualification_requires_installation_authority"): cli.installation_authority()


def test_archive_failure_removes_new_grant_and_publishes_no_package(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_CONNECTOR_QUALIFICATION_ENABLED", "1")
    monkeypatch.setenv("ATLAS_BUILD_ID", "a" * 40)
    store = PackageStore(tmp_path / "qualification-store")
    monkeypatch.setattr(lifecycle, "package_store", lambda: store)
    package = unqualified(bundle(tmp_path, extra=[("../outside", b"inert")])[0])
    with pytest.raises(ValueError, match="unsafe_archive_path"): cli.stage(arguments(package, tmp_path))
    assert not (store.root / ".qualification.json").exists()
    assert not (store.root / package.connector_id).exists()
