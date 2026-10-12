"""Real private HTTP and independent immutable-store inspection regressions."""
import hashlib
import io
import json
from pathlib import Path
import secrets
import sys
import tarfile
import threading
import urllib.error
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/runtime/ansible"))
from atlas_runtime import server


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    baseline = json.loads((ROOT / "apps/runtime/ansible/baseline.json").read_text())
    monkeypatch.setattr(server, "version", lambda name: baseline["sdk_version"] if name == "atlas-connector-sdk" else baseline["dependencies"][name])
    return server.Runtime(secrets.token_hex(48), tmp_path / "store", "development")


@pytest.fixture
def private_http(runtime):
    listener = server.Server(("127.0.0.1", 0), runtime)
    thread = threading.Thread(target=listener.serve_forever, daemon=True)
    thread.start()
    yield runtime, f"http://127.0.0.1:{listener.server_address[1]}"
    listener.shutdown()
    listener.server_close()
    thread.join(2)


def request(url, secret=None, body=None, *, headers=None):
    headers = {**({"Authorization": "Bearer " + secret} if secret else {}), **(headers or {})}
    if body is not None:
        headers["Content-Type"] = "application/json"
    call = urllib.request.Request(url, data=body, headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(call, timeout=2) as response:
        return json.loads(response.read())


@pytest.mark.parametrize("path", ["/v1/health", "/v1/capabilities", "/v1/connectors/verify", "/v1/connectors/test-connection",
    "/v1/discovery/start", "/v1/discovery/status", "/v1/discovery/cancel"])
@pytest.mark.parametrize("credential", [None, "incorrect"])
def test_every_control_operation_requires_independent_credential(private_http, path, credential):
    runtime, address = private_http
    with pytest.raises(urllib.error.HTTPError) as error:
        request(address + path, credential, b"{}" if "/connectors/" in path or "/discovery/" in path else None)
    assert error.value.code == 401
    assert error.value.read() == b'{"diagnostic_code":"unauthorized"}'


def test_real_http_health_and_capabilities_do_not_disclose_secret_or_store(private_http, capsys):
    runtime, address = private_http
    health = request(address + "/v1/health", runtime._secret)
    capabilities = request(address + "/v1/capabilities", runtime._secret)
    assert health["state"] == "healthy"
    assert capabilities["operations"] == ["health", "capabilities", "verify_connector", "test_connection", "run_discovery", "get_job", "cancel_job"]
    assert capabilities["aip_versions"] == ["1.0"]
    output = json.dumps([health, capabilities]) + str(capsys.readouterr())
    assert runtime._secret not in output and str(runtime.store) not in output


def test_dependency_drift_fails_compatibility(runtime, monkeypatch):
    monkeypatch.setattr(server, "version", lambda name: "999.0")
    assert runtime.health()["state"] == "incompatible"
    assert runtime.health()["diagnostic_code"] == "baseline_dependency_mismatch"


@pytest.mark.parametrize("payload", [
    {"command": "id"}, {"playbook": "/tmp/x"}, {"connector_id": "../other", "version": "1.0.0", "digest": "0" * 64},
    {"connector_id": "valid", "version": "../x", "digest": "0" * 64},
    {"connector_id": "valid", "version": "1.0.0", "digest": "../../x"},
    {"connector_id": "valid", "version": "1.0.0", "digest": "0" * 64, "path": "/tmp/x"},
])
def test_arbitrary_execution_and_paths_rejected(private_http, payload):
    runtime, address = private_http
    with pytest.raises(urllib.error.HTTPError) as error:
        request(address + "/v1/connectors/verify", runtime._secret, json.dumps(payload).encode())
    assert error.value.code == 400


def test_oversized_requests_and_execution_endpoint_rejected(private_http):
    runtime, address = private_http
    with pytest.raises(urllib.error.HTTPError) as error:
        request(address + "/v1/connectors/verify", runtime._secret, b" " * (server.MAX_BODY + 1))
    assert error.value.code == 413
    with pytest.raises(urllib.error.HTTPError) as error:
        request(address + "/v1/jobs/start", runtime._secret, b"{}")
    assert error.value.code == 404


def stored_package(runtime):
    manifest = {"id": "test.connector", "version": "1.0.0"}
    files = {"manifest.json": json.dumps(manifest).encode(), "NOTICE": b"test fixture\n"}
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in files.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            archive.addfile(entry, io.BytesIO(content))
    bundle = buffer.getvalue()
    digest = hashlib.sha256(bundle).hexdigest()
    reference = {"connector_id": manifest["id"], "version": manifest["version"], "digest": digest}
    directory = runtime.store / reference["connector_id"] / reference["version"] / reference["digest"]
    (directory / "contents").mkdir(parents=True)
    (directory / "bundle.tar.gz").write_bytes(bundle)
    (directory / "manifest.json").write_text(json.dumps({**manifest, "distribution": {"bundle_digest": "sha256:" + digest}}))
    receipt = {**reference, "status": "verified", "verification": {"bundle_digest": "sha256:" + digest}, "files": {name: "sha256:" + hashlib.sha256(content).hexdigest() for name, content in files.items()}}
    (directory / "verification.json").write_text(json.dumps(receipt))
    for name, content in files.items():
        (directory / "contents" / name).write_bytes(content)
    return reference, directory


def test_exact_verified_package_independently_inspected(runtime):
    reference, _ = stored_package(runtime)
    assert runtime.verify_connector(reference)["state"] == "verified"
    assert runtime.verify_connector({**reference, "connector_id": "another"})["state"] == "unavailable"
    assert runtime.verify_connector({**reference, "version": "2.0.0"})["state"] == "unavailable"
    assert runtime.verify_connector({**reference, "digest": "0" * 64})["state"] == "unavailable"


@pytest.mark.parametrize("target", ["bundle.tar.gz", "manifest.json", "contents/NOTICE"])
def test_archive_manifest_and_extracted_content_tampering_fail_closed(runtime, target):
    reference, directory = stored_package(runtime)
    (directory / target).write_bytes(b"tampered")
    assert runtime.verify_connector(reference)["state"] == "unavailable"


def test_unverified_receipt_and_symlink_fail_closed(runtime, tmp_path):
    reference, directory = stored_package(runtime)
    receipt = json.loads((directory / "verification.json").read_text())
    receipt["status"] = "unverified"
    (directory / "verification.json").write_text(json.dumps(receipt))
    assert runtime.verify_connector(reference)["state"] == "unavailable"
    receipt["status"] = "verified"
    (directory / "verification.json").write_text(json.dumps(receipt))
    external = tmp_path / "external"
    external.write_text("external")
    (directory / "contents/NOTICE").unlink()
    (directory / "contents/NOTICE").symlink_to(external)
    assert runtime.verify_connector(reference)["state"] == "unavailable"


@pytest.mark.parametrize("kind", ["nonempty_directory", "symlink", "traversal", "oversized_member", "pax_metadata"])
def test_malicious_archive_inspection_fails_closed_even_with_matching_archive_digest(runtime, kind):
    reference, directory = stored_package(runtime)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        entry = tarfile.TarInfo("bad")
        if kind == "nonempty_directory":
            entry.type = tarfile.DIRTYPE
            entry.size = 128 * 1024
            archive.addfile(entry, io.BytesIO(b"\0" * entry.size))
        elif kind == "symlink":
            entry.type = tarfile.SYMTYPE
            entry.linkname = "/etc/passwd"
            archive.addfile(entry)
        elif kind == "traversal":
            entry.name = "../escape"
            archive.addfile(entry)
        elif kind == "pax_metadata":
            entry.type = tarfile.XHDTYPE
            entry.size = server.MAX_METADATA + 1
            archive.addfile(entry, io.BytesIO(b"0" * entry.size))
        else:
            entry.size = server.MAX_FILE + 1
            archive.addfile(entry, io.BytesIO(b"\0" * entry.size))
    bundle = buffer.getvalue()
    digest = hashlib.sha256(bundle).hexdigest()
    destination = directory.parent / digest
    directory.rename(destination)
    reference["digest"] = digest
    (destination / "bundle.tar.gz").write_bytes(bundle)
    manifest = json.loads((destination / "manifest.json").read_text())
    manifest["distribution"]["bundle_digest"] = "sha256:" + digest
    (destination / "manifest.json").write_text(json.dumps(manifest))
    receipt = json.loads((destination / "verification.json").read_text())
    receipt["digest"] = digest
    receipt["verification"]["bundle_digest"] = "sha256:" + digest
    (destination / "verification.json").write_text(json.dumps(receipt))
    assert runtime.verify_connector(reference)["state"] == "unavailable"
    assert not (runtime.store / "escape").exists()


def test_missing_malformed_or_symlink_credential_fails_startup(tmp_path):
    path = tmp_path / "control.secret"
    with pytest.raises(OSError):
        server.load_secret(path)
    path.write_text("short")
    with pytest.raises(ValueError):
        server.load_secret(path)
    actual = tmp_path / "actual"
    actual.write_text(secrets.token_hex(48))
    path.unlink(); path.symlink_to(actual)
    with pytest.raises(ValueError):
        server.load_secret(path)
