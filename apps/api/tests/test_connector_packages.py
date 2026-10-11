"""I1 immutable catalogue, manifest, trust and archive security regressions."""
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile

import pytest

from app.services.connector_catalogue import (BOOTSTRAP_PATH, CataloguePackage, CatalogueService,
    CatalogueUnavailable, compatibility)
from app.services.connector_contracts import (ManifestValidationError, staging_contract_root,
    manifest_validator, strict_json, validate_manifest)
from app.services import connector_store as store_module
from app.services.connector_store import PackageStore, PackageStoreError
from app.services.connector_verification import (BootstrapReleaseVerifier, GithubSigstoreVerifier,
    OfficialBundleVerifier, VerificationError, verify_digest)


def example():
    return json.loads((staging_contract_root() / "manifests/proxmox.json").read_text())


def manifest():
    value = example()
    value["version"] = "1.0.0"
    value["source_versions"]["qualification"] = "qualified"
    return value


def runtime(**changes):
    return {"status": "healthy", "baseline_version": "1.0.0",
        "protocol_version": "integration-runtime-v1", "capabilities": {
            "aip_versions": ["1.0"], "protocol_version": "integration-runtime-v1",
            "dependencies": [], "runtime_kind": "ansible"}, **changes}


def bundle(tmp_path, *, domain_change=None, extra=None, kind=None, mode=None, version="1.0.0"):
    value = manifest()
    value["version"] = version
    domain = {key: item for key, item in value.items() if key != "distribution"}
    if domain_change:
        domain_change(domain)
    files = [("manifest.json", json.dumps(domain).encode()), ("NOTICE", b"inert test notice"),
             ("sbom.spdx.json", b'{"test":true}')]
    if extra:
        files.extend(extra)
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as archive:
        for name, content in files:
            member = tarfile.TarInfo(name)
            member.size = len(content)
            if kind is not None and name == files[-1][0]:
                member.type = kind
                member.linkname = "../../outside"
            if mode is not None and name == files[-1][0]:
                member.mode = mode
            archive.addfile(member, io.BytesIO(content))
    payload = raw.getvalue()
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    value["distribution"]["bundle_digest"] = digest
    archive_path = tmp_path / "inert-bundle.tar.gz"
    archive_path.write_bytes(payload)
    package = CataloguePackage("proxmox", version, digest, value, "bootstrap", True, archive_path)
    verifier = OfficialBundleVerifier(BootstrapReleaseVerifier(
        frozenset({("proxmox", version, digest)}), "inert-test-release"))
    return package, verifier, payload


def path_for(store, package):
    return store.root / package.connector_id / package.version / package.bundle_digest[7:]


def test_offline_bootstrap_has_truthful_non_executable_entries():
    service = CatalogueService()
    entries = service.entries(runtime=runtime())
    assert {entry["connector_id"] for entry in entries} == {"proxmox", "docker", "unifi-network"}
    for entry in entries:
        assert entry["state"] == "unavailable"
        assert entry["version"] is None and entry["digest"] is None
        assert entry["verification_status"] == "metadata_only"
        assert entry["package_available"] is False and entry["supported_actions"] == []
        assert entry["source_versions"]["qualification"] == "not_qualified"
    assert service.status()["refresh_supported"] is False
    assert service.get("proxmox").manifest["source_versions"]["qualification"] == "example"
    with pytest.raises(CatalogueUnavailable, match="connector_not_in_catalogue"):
        service.get("missing")


def test_catalogue_tampering_and_missing_files_fail_closed(tmp_path):
    candidate = tmp_path / "catalogue.json"
    candidate.write_bytes(BOOTSTRAP_PATH.read_bytes() + b" ")
    with pytest.raises(CatalogueUnavailable, match="bootstrap_catalogue_changed"):
        CatalogueService(candidate).entries()
    candidate.unlink()
    with pytest.raises(CatalogueUnavailable, match="bootstrap_catalogue_unavailable"):
        CatalogueService(candidate).entries()


def test_catalogue_installed_state_is_separate_from_source():
    entries = CatalogueService().entries(installed={"proxmox": {"version": "1.0.0"}})
    entry = next(row for row in entries if row["connector_id"] == "proxmox")
    assert entry["state"] == "installed" and entry["installed_version"] == "1.0.0"
    assert entry["package_available"] is False and entry["version"] is None
    assert entry["supported_actions"] == ["remove"]


def test_deployed_adapter_consumes_original_pinned_staging_artifacts(tmp_path, monkeypatch):
    source = staging_contract_root()
    target = tmp_path / "contracts"
    target.mkdir()
    schema = target / "connector-manifest-v1.schema.json"
    schema.write_bytes((source / schema.name).read_bytes())
    (target / "manifests").mkdir()
    for original in (source / "manifests").glob("*.json"):
        (target / "manifests" / original.name).write_bytes(original.read_bytes())
    monkeypatch.setenv("ATLAS_CONNECTOR_SCHEMA_FILE", str(schema))
    manifest_validator.cache_clear()
    try:
        assert len(CatalogueService().entries()) == 3
        schema.write_bytes(schema.read_bytes() + b" ")
        manifest_validator.cache_clear()
        with pytest.raises(ManifestValidationError, match="sdk_contract_changed"):
            validate_manifest(example())
        schema.write_bytes((source / schema.name).read_bytes())
        manifest_validator.cache_clear()
        candidate = target / "manifests/proxmox.json"
        candidate.write_bytes(candidate.read_bytes() + b" ")
        with pytest.raises(CatalogueUnavailable, match="bootstrap_manifest_changed"):
            CatalogueService().entries()
    finally:
        manifest_validator.cache_clear()


@pytest.mark.parametrize("raw", ['{"id":1,"id":2}', '{"number":NaN}', '{"number":Infinity}', '{"number":1e999}', "[]" * 10000])
def test_strict_json_rejects_ambiguous_or_invalid_metadata(raw):
    with pytest.raises(ManifestValidationError):
        strict_json(raw)


def test_strict_metadata_size_bound():
    with pytest.raises(ManifestValidationError, match="metadata_too_large"):
        strict_json('"' + "a" * 100 + '"', maximum=100)


def test_schema_validates_examples_and_rejects_activation():
    assert validate_manifest(example())
    with pytest.raises(ManifestValidationError, match="package_not_qualified"):
        validate_manifest(example(), activation=True)


@pytest.mark.parametrize("mutate", [
    lambda value: value.update(playbook="/tmp/execute.yml"),
    lambda value: value["implementation"]["entry_points"].update(discover="../../execute.yml"),
    lambda value: value["connection_fields"][0].update(secret=True, type="secret", default="never"),
    lambda value: value["object_classes"].append(deepcopy(value["object_classes"][0])),
    lambda value: value["compatibility"]["atlas"].update(minimum="2.0.0", exclusive_maximum="1.0.0"),
    lambda value: value["display"].update(documentation_uri="https://user@example.test/manual"),
    lambda value: value["distribution"]["provenance"].update(publisher_id="unapproved"),
    lambda value: value["facts"][0].update(object_classes=["missing.class"]),
    lambda value: value["discovery_scopes"][0].update(required=True, default_enabled=False),
])
def test_manifest_rejects_unsafe_and_inconsistent_contracts(mutate):
    value = example()
    mutate(value)
    with pytest.raises(ManifestValidationError):
        validate_manifest(value)


@pytest.mark.parametrize("change,state", [
    ({"status": "unavailable"}, "runtime_unavailable"),
    ({"baseline_version": "2.0.0"}, "runtime_update_required"),
    ({"capabilities": {"aip_versions": [], "protocol_version": "integration-runtime-v1"}}, "incompatible"),
    ({"capabilities": {"aip_versions": ["1.0"], "protocol_version": "unknown"}}, "incompatible"),
    ({}, "compatible"),
])
def test_generic_runtime_compatibility(change, state):
    assert compatibility(manifest(), runtime(**change))["state"] == state


def test_dependency_compatibility_requires_exact_approved_identity():
    value = manifest()
    dependency = {"kind": "collection", "name": "test.collection", "version": "1.0.0",
                  "digest": "sha256:" + "a" * 64, "licence": "Apache-2.0"}
    value["implementation"]["dependencies"] = [dependency]
    assert compatibility(value, runtime())["state"] == "runtime_update_required"
    health = runtime()
    health["capabilities"]["dependencies"] = [dependency]
    assert compatibility(value, health)["state"] == "compatible"
    health["capabilities"]["dependencies"][0] = {**dependency, "digest": "sha256:" + "b" * 64}
    assert compatibility(value, health)["state"] == "runtime_update_required"


def test_empty_dependency_manifest_accepts_health_version_map():
    health = runtime()
    health["capabilities"]["dependencies"] = {"ansible-core": "2.19.3", "ansible-runner": "2.4.2"}
    assert compatibility(manifest(), health)["state"] == "compatible"
    value = manifest()
    value["implementation"]["dependencies"] = [{"kind": "python_package", "name": "ansible-core",
        "version": "2.19.3", "digest": "sha256:" + "a" * 64, "licence": "GPL-3.0-or-later"}]
    assert compatibility(value, health)["state"] == "runtime_update_required"


@pytest.mark.parametrize("change,state", [({"baseline_version": "invalid"}, "runtime_update_required"),
    ({"capabilities": "invalid"}, "incompatible"),
    ({"capabilities": {"aip_versions": None}}, "incompatible")])
def test_malformed_runtime_metadata_fails_closed(change, state):
    assert compatibility(manifest(), runtime(**change))["state"] == state


def test_atlas_and_sdk_bounds_are_checked_independently():
    assert compatibility(manifest(), runtime(), atlas_version="1.0.0")["state"] == "incompatible"
    value = manifest()
    value["compatibility"]["sdk"] = {"minimum": "2.0.0", "exclusive_maximum": "3.0.0"}
    assert compatibility(value, runtime())["state"] == "incompatible"


def test_digest_and_bootstrap_allowlist_are_both_required(tmp_path):
    package, verifier, payload = bundle(tmp_path)
    result = verifier.verify(payload, package)
    assert result.method == "atlas-release-bootstrap"
    assert result.bundle_digest == package.bundle_digest
    with pytest.raises(VerificationError, match="bundle_digest_mismatch"):
        verifier.verify(payload + b"changed", package)
    with pytest.raises(VerificationError, match="bootstrap_package_not_approved"):
        BootstrapReleaseVerifier(frozenset(), "test").verify(payload, package)


def test_remote_official_verifier_fails_closed_without_cli_or_network(tmp_path):
    package, _, payload = bundle(tmp_path)
    with pytest.raises(VerificationError, match="official_provenance_verifier_unavailable"):
        GithubSigstoreVerifier().verify(payload, package)
    remote = CataloguePackage(package.connector_id, package.version, package.bundle_digest,
                              package.manifest, "official", True, package.archive_path)
    with pytest.raises(VerificationError, match="official_provenance_verifier_unavailable"):
        OfficialBundleVerifier().verify(payload, remote)
    with pytest.raises(VerificationError, match="bundle_digest_mismatch"):
        GithubSigstoreVerifier().verify(payload + b"changed", package)


def test_future_publisher_signature_cannot_self_approve(tmp_path):
    package, verifier, payload = bundle(tmp_path)
    altered = deepcopy(package.manifest)
    altered["publisher"]["id"] = "third-party"
    other = CataloguePackage("proxmox", "1.0.0", package.bundle_digest, altered, "bootstrap", True, package.archive_path)
    with pytest.raises(VerificationError, match="publisher_not_approved"):
        verifier.verify(payload, other)


def test_safe_install_is_atomic_immutable_idempotent_and_verifiable(tmp_path):
    package, verifier, _ = bundle(tmp_path)
    store = PackageStore(tmp_path / "store")
    result = store.install(package, verifier)
    assert result.verification["status"] == "verified"
    assert result.safe_metadata()["verification_status"] == "verified"
    assert store.verify_connector("proxmox", "1.0.0", package.bundle_digest)["state"] == "verified"
    installed = path_for(store, package)
    assert stat.S_IMODE(installed.stat().st_mode) == 0o555
    assert stat.S_IMODE((installed / "contents/NOTICE").stat().st_mode) == 0o444
    assert not list(store.root.glob(".stage-*"))
    again = store.install(package, verifier)
    assert again.bundle_digest == result.bundle_digest


def test_unreleased_catalogue_entry_cannot_install(tmp_path):
    service = CatalogueService()
    with pytest.raises(PackageStoreError, match="package_not_released"):
        PackageStore(tmp_path / "store").install(service.get("proxmox"), service.verifier())


@pytest.mark.parametrize("name", ["../outside", "/outside", "a/../../outside", "a\\outside", "a//outside", "./outside", "C:outside"])
def test_archive_traversal_is_rejected_without_publication(tmp_path, name):
    package, verifier, _ = bundle(tmp_path, extra=[(name, b"inert")])
    store = PackageStore(tmp_path / "store")
    with pytest.raises(PackageStoreError, match="unsafe_archive_path"):
        store.install(package, verifier)
    assert not path_for(store, package).exists() and not list(store.root.glob(".stage-*"))
    assert not (tmp_path / "outside").exists()


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE,
    tarfile.XHDTYPE, tarfile.XGLTYPE, tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK, tarfile.GNUTYPE_SPARSE])
def test_archive_links_and_special_files_are_rejected(tmp_path, kind):
    package, verifier, _ = bundle(tmp_path, extra=[("special", b"")], kind=kind)
    with pytest.raises(PackageStoreError, match="unsafe_archive_member"):
        PackageStore(tmp_path / "store").install(package, verifier)


def test_archive_privileged_modes_are_rejected(tmp_path):
    package, verifier, _ = bundle(tmp_path, extra=[("privileged", b"inert")], mode=0o4755)
    with pytest.raises(PackageStoreError, match="unsafe_archive_permissions"):
        PackageStore(tmp_path / "store").install(package, verifier)


def test_duplicate_archive_members_are_rejected(tmp_path):
    package, verifier, _ = bundle(tmp_path, extra=[("NOTICE", b"duplicate")])
    with pytest.raises(PackageStoreError, match="unsafe_archive_member"):
        PackageStore(tmp_path / "store").install(package, verifier)


@pytest.mark.parametrize("size", [1, 1024 * 1024 * 1024])
def test_directory_records_cannot_hide_unaccounted_payloads(tmp_path, size):
    package, verifier, _ = bundle(tmp_path, extra=[("malicious-directory", b"x")], kind=tarfile.DIRTYPE)
    if size > 1:
        # Change only the first malicious directory header's declared size. A
        # huge claimed payload must be rejected before tarfile skips it, even
        # when the attacker omitted its bytes altogether.
        import gzip
        decoded = bytearray(gzip.decompress(package.archive_path.read_bytes()))
        for offset in range(0, len(decoded), 512):
            if decoded[offset:offset + 100].split(b"\0", 1)[0] == b"malicious-directory":
                header = tarfile.TarInfo("malicious-directory")
                header.type, header.size = tarfile.DIRTYPE, size
                decoded[offset:offset + 512] = header.tobuf()
                break
        compressed = gzip.compress(decoded)
        package.archive_path.write_bytes(compressed)
        digest = "sha256:" + hashlib.sha256(compressed).hexdigest()
        value = deepcopy(package.manifest)
        value["distribution"]["bundle_digest"] = digest
        package = CataloguePackage(package.connector_id, package.version, digest, value,
                                  "bootstrap", True, package.archive_path)
        verifier = OfficialBundleVerifier(BootstrapReleaseVerifier(
            frozenset({(package.connector_id, package.version, digest)}), "inert-test-release"))
    store = PackageStore(tmp_path / "store")
    with pytest.raises(PackageStoreError, match="unsafe_archive_directory"):
        store.install(package, verifier)
    assert not path_for(store, package).exists() and not list(store.root.glob(".stage-*"))


@pytest.mark.parametrize("kind", [tarfile.XHDTYPE, tarfile.XGLTYPE,
                                  tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK])
def test_huge_internal_metadata_headers_are_rejected_before_library_reads(tmp_path, monkeypatch, kind):
    import gzip
    package, _, _ = bundle(tmp_path)
    header = tarfile.TarInfo("hidden-metadata")
    header.type, header.size = kind, 1024 * 1024 * 1024
    payload = gzip.compress(header.tobuf(format=tarfile.USTAR_FORMAT) + b"\0" * 1024)
    package.archive_path.write_bytes(payload)
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    value = deepcopy(package.manifest)
    value["distribution"]["bundle_digest"] = digest
    package = CataloguePackage(package.connector_id, package.version, digest, value,
                              "bootstrap", True, package.archive_path)
    verifier = OfficialBundleVerifier(BootstrapReleaseVerifier(
        frozenset({(package.connector_id, package.version, digest)}), "inert-test-release"))
    monkeypatch.setattr(store_module, "MAX_FILE_BYTES", 128)
    with pytest.raises(PackageStoreError, match="unsafe_archive_member"):
        PackageStore(tmp_path / "store").install(package, verifier)


def test_total_decoded_archive_bound_includes_hidden_header_payloads(tmp_path, monkeypatch):
    package, verifier, _ = bundle(tmp_path)
    # Extra unreferenced compressed tar bytes still consume the global decoded
    # bound, including data tarfile would normally ignore after its end marker.
    import gzip
    decoded = gzip.decompress(package.archive_path.read_bytes()) + b"\0" * 50000
    compressed = gzip.compress(decoded)
    package.archive_path.write_bytes(compressed)
    digest = "sha256:" + hashlib.sha256(compressed).hexdigest()
    value = deepcopy(package.manifest)
    value["distribution"]["bundle_digest"] = digest
    package = CataloguePackage(package.connector_id, package.version, digest, value,
                              "bootstrap", True, package.archive_path)
    verifier = OfficialBundleVerifier(BootstrapReleaseVerifier(
        frozenset({(package.connector_id, package.version, digest)}), "inert-test-release"))
    monkeypatch.setattr(store_module, "MAX_EXPANDED_BYTES", 1024)
    monkeypatch.setattr(store_module, "MAX_MEMBERS", 10)
    with pytest.raises(PackageStoreError, match="archive_size_limit"):
        PackageStore(tmp_path / "store").install(package, verifier)


def test_failed_new_version_preserves_previous_verified_package(tmp_path):
    package, verifier, _ = bundle(tmp_path)
    store = PackageStore(tmp_path / "store")
    store.install(package, verifier)
    newer, newer_verifier, _ = bundle(tmp_path, version="1.1.0", extra=[("../../outside", b"inert")])
    with pytest.raises(PackageStoreError, match="unsafe_archive_path"):
        store.install(newer, newer_verifier)
    assert store.verify_connector(package.connector_id, package.version, package.bundle_digest)["state"] == "verified"
    assert not path_for(store, newer).exists()


def test_embedded_manifest_must_match_verified_detached_metadata(tmp_path):
    package, verifier, _ = bundle(tmp_path, domain_change=lambda value: value.update(version="9.0.0"))
    with pytest.raises(PackageStoreError, match="embedded_manifest_mismatch"):
        PackageStore(tmp_path / "store").install(package, verifier)


@pytest.mark.parametrize("bound,code", [("MAX_MEMBERS", "archive_file_limit"),
    ("MAX_FILE_BYTES", "archive_file_size_limit"), ("MAX_EXPANDED_BYTES", "archive_size_limit")])
def test_archive_bounds_prevent_partial_publication(tmp_path, monkeypatch, bound, code):
    package, verifier, _ = bundle(tmp_path)
    monkeypatch.setattr(store_module, bound, 1)
    store = PackageStore(tmp_path / "store")
    with pytest.raises(PackageStoreError, match=code):
        store.install(package, verifier)
    assert not path_for(store, package).exists() and not list(store.root.glob(".stage-*"))


def test_archive_size_is_bounded_before_verification(tmp_path, monkeypatch):
    package, verifier, _ = bundle(tmp_path)
    monkeypatch.setattr(store_module, "MAX_ARCHIVE_BYTES", 1)
    with pytest.raises(PackageStoreError, match="package_file_invalid"):
        PackageStore(tmp_path / "store").install(package, verifier)


def test_symlinked_store_or_archive_is_rejected(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(PackageStoreError, match="unsafe_store_path"):
        PackageStore(link)
    package, verifier, _ = bundle(tmp_path)
    archive_link = tmp_path / "archive-link.tar.gz"
    archive_link.symlink_to(package.archive_path)
    linked = CataloguePackage(package.connector_id, package.version, package.bundle_digest,
                              package.manifest, "bootstrap", True, archive_link)
    with pytest.raises(PackageStoreError, match="unsafe_store_path"):
        PackageStore(tmp_path / "store").install(linked, verifier)


def test_fifo_archive_is_rejected_without_blocking_open(tmp_path):
    package, verifier, _ = bundle(tmp_path)
    package.archive_path.unlink()
    os.mkfifo(package.archive_path)
    with pytest.raises(PackageStoreError, match="package_file_invalid"):
        PackageStore(tmp_path / "store").install(package, verifier)


@pytest.mark.parametrize("field,value", [("connector_id", "../outside"), ("version", "1.0.0/../outside"),
    ("bundle_digest", "sha256:" + "x" * 64)])
def test_package_identity_never_becomes_a_caller_supplied_path(tmp_path, field, value):
    identity = {"connector_id": "proxmox", "version": "1.0.0", "bundle_digest": "sha256:" + "a" * 64}
    identity[field] = value
    with pytest.raises(PackageStoreError, match="invalid_package_identity"):
        PackageStore(tmp_path / "store").verify_connector(**identity)


def test_changed_contents_or_receipt_cannot_hide_behind_original_archive(tmp_path):
    package, verifier, _ = bundle(tmp_path)
    store = PackageStore(tmp_path / "store")
    store.install(package, verifier)
    path = path_for(store, package)
    notice = path / "contents/NOTICE"
    notice.chmod(0o644)
    notice.write_bytes(b"changed")
    with pytest.raises(PackageStoreError, match="installed_file_changed"):
        store.verify_connector("proxmox", "1.0.0", package.bundle_digest)
    receipt = path / "verification.json"
    receipt.chmod(0o644)
    value = json.loads(receipt.read_text())
    value["files"]["NOTICE"] = "sha256:" + hashlib.sha256(b"changed").hexdigest()
    receipt.write_text(json.dumps(value))
    with pytest.raises(PackageStoreError, match="installed_archive_mismatch"):
        store.verify_connector("proxmox", "1.0.0", package.bundle_digest)


@pytest.mark.parametrize("metadata", [[], {"verification": "malformed"}])
def test_malformed_installed_receipts_fail_with_safe_code(tmp_path, metadata):
    package, verifier, _ = bundle(tmp_path)
    store = PackageStore(tmp_path / "store")
    store.install(package, verifier)
    receipt = path_for(store, package) / "verification.json"
    receipt.chmod(0o644)
    receipt.write_text(json.dumps(metadata))
    with pytest.raises(PackageStoreError, match="invalid_installed_metadata"):
        store.verify_connector(package.connector_id, package.version, package.bundle_digest)


def test_quarantine_rollback_and_committed_removal_preserve_history_boundary(tmp_path):
    package, verifier, _ = bundle(tmp_path)
    store = PackageStore(tmp_path / "store")
    store.install(package, verifier)
    token = store.quarantine("proxmox", "1.0.0", package.bundle_digest)
    assert not path_for(store, package).exists()
    store.restore(token)
    assert store.verify_connector("proxmox", "1.0.0", package.bundle_digest)["state"] == "verified"
    token = store.quarantine("proxmox", "1.0.0", package.bundle_digest)
    store.finish_remove(token)
    assert not path_for(store, package).exists() and not (store.root / token.name).exists()
    # Store lifecycle has no Session, knowledge/history imports or deletion calls.


def test_whole_connector_quarantine_restores_all_versions_or_removes_all_contents(tmp_path):
    store = PackageStore(tmp_path / "store")
    packages = []
    for version in ("1.0.0", "1.1.0"):
        directory = tmp_path / version
        directory.mkdir()
        package, verifier, _ = bundle(directory, version=version)
        store.install(package, verifier)
        packages.append(package)
    token = store.quarantine_connector("proxmox")
    assert not (store.root / "proxmox").exists()
    store.restore(token)
    for package in packages:
        assert store.verify_connector(package.connector_id, package.version, package.bundle_digest)["state"] == "verified"
    token = store.quarantine_connector("proxmox")
    store.finish_remove(token)
    assert not (store.root / "proxmox").exists() and not (store.root / token.name).exists()


def test_committed_connector_cleanup_cannot_remove_new_concurrent_identity(tmp_path):
    store = PackageStore(tmp_path / "store")
    package, verifier, _ = bundle(tmp_path)
    store.install(package, verifier)
    token = store.quarantine_connector("proxmox")
    store.install(package, verifier)
    store.finish_remove(token)
    assert store.verify_connector(package.connector_id, package.version, package.bundle_digest)["state"] == "verified"
