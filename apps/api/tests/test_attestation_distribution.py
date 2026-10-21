"""Distribution boundaries and integrity rejection without network dependencies."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile

import pytest

from app import attestation_distribution as distribution
from scripts import prepare_attestation_verifier as installer

ROOT = Path(__file__).resolve().parents[3]


def test_all_supported_platforms_have_explicit_archive_and_binary_pins(monkeypatch):
    lock = distribution.distribution_lock()
    assert set(lock["platforms"]) == {"linux-amd64", "linux-arm64", "darwin-amd64", "darwin-arm64"}
    for key, record in lock["platforms"].items():
        assert record["archive"].startswith("gh_2.102.1_")
        for name in ("archive_sha256", "binary_sha256"):
            assert len(bytes.fromhex(record[name])) == 32
    for system, machine, key in [
        ("Linux", "x86_64", "linux-amd64"), ("Linux", "aarch64", "linux-arm64"),
        ("Darwin", "x86_64", "darwin-amd64"), ("Darwin", "arm64", "darwin-arm64"),
    ]:
        monkeypatch.setattr(distribution.platform, "system", lambda: system)
        monkeypatch.setattr(distribution.platform, "machine", lambda: machine)
        assert distribution.platform_key() == key


def test_unsupported_platform_has_no_path_fallback(monkeypatch):
    monkeypatch.setattr(distribution.platform, "machine", lambda: "unapproved")
    with pytest.raises(ValueError, match="unsupported_verifier_platform"):
        distribution.platform_key()


@pytest.mark.parametrize("raw", [b"null", b"[]", b"[" * 2000, b'{"version":"0.0.0"}'])
def test_corrupt_distribution_configuration_has_safe_failure(tmp_path, monkeypatch, raw):
    from app.services.connector_verification import GithubSigstoreVerifier
    from app.services.official_provenance import ProvenanceError
    fixtures = Path(__file__).parent / "fixtures/official_catalogue"
    (tmp_path / "distribution.json").write_bytes(raw)
    monkeypatch.setattr(distribution, "DISTRIBUTION", tmp_path)
    with pytest.raises(ProvenanceError, match="unsupported_verifier_version"):
        GithubSigstoreVerifier().verify_catalogue(
            (fixtures / "catalogue-000001.json").read_bytes(), (fixtures / "catalogue.sigstore.json").read_bytes())


def test_real_binary_and_root_integrity():
    lock = distribution.distribution_lock()
    assert distribution.checked_binary(lock).is_absolute()
    roots = distribution.checked_root(lock)
    assert hashlib.sha256(roots).hexdigest() == lock["root_sha256"]
    root = json.loads(roots)
    assert all(ca["uri"] == "https://fulcio.sigstore.dev" for ca in root["certificateAuthorities"])
    assert root["tlogs"] and root["ctlogs"]


@pytest.mark.parametrize("kind", ["corrupt", "symlink", "fifo", "oversized"])
def test_untrusted_build_archive_cannot_replace_working_binary(tmp_path, kind, monkeypatch):
    before = distribution.checked_binary(distribution.distribution_lock()).read_bytes()
    path = tmp_path / "archive"
    if kind == "corrupt":
        path.write_bytes(b"not trusted")
    elif kind == "symlink":
        path.symlink_to(distribution.DISTRIBUTION / "distribution.json")
    elif kind == "fifo":
        import os
        os.mkfifo(path)
    else:
        path.write_bytes(b"x" * 20)
        monkeypatch.setattr(installer, "MAX_ARCHIVE_BYTES", 10)
    with pytest.raises(ValueError):
        installer.prepare(path)
    assert distribution.checked_binary(distribution.distribution_lock()).read_bytes() == before


@pytest.mark.parametrize("extension", [".tar.gz", ".zip"])
@pytest.mark.parametrize("kind", ["wrong_member", "duplicate", "binary_digest"])
def test_archive_structure_and_extracted_digest_are_independently_checked(tmp_path, monkeypatch, extension, kind):
    # Negative-only synthetic build inputs. Nothing here can execute.
    lock = distribution.distribution_lock()
    entry = lock["platforms"][distribution.platform_key()]
    entry["archive"] = "gh_2.102.1_test" + extension
    name = "gh_2.102.1_test/bin/gh"
    if kind == "wrong_member":
        name = "../bin/gh"
    contents = io.BytesIO()
    if extension == ".zip":
        with zipfile.ZipFile(contents, "w") as archive:
            archive.writestr(name, b"untrusted binary")
            if kind == "duplicate":
                with pytest.warns(UserWarning):
                    archive.writestr(name, b"duplicate")
    else:
        with tarfile.open(fileobj=contents, mode="w:gz") as archive:
            for _ in range(2 if kind == "duplicate" else 1):
                member = tarfile.TarInfo(name)
                member.size = len(b"untrusted binary")
                archive.addfile(member, io.BytesIO(b"untrusted binary"))
    raw = contents.getvalue()
    entry["archive_sha256"] = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(distribution, "distribution_lock", lambda: lock)
    path = tmp_path / "archive"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="invalid_verifier_(archive|binary_digest)"):
        installer.prepare(path)


def test_corrupt_offline_cache_never_falls_back_to_download(tmp_path, monkeypatch):
    lock = distribution.distribution_lock()
    for name in ("distribution.json", "trusted-root.jsonl"):
        (tmp_path / name).write_bytes((distribution.DISTRIBUTION / name).read_bytes())
    cache = tmp_path / "archives"
    cache.mkdir()
    (cache / lock["platforms"][distribution.platform_key()]["archive"]).write_bytes(b"corrupt")
    monkeypatch.setattr(distribution, "DISTRIBUTION", tmp_path)
    monkeypatch.setattr(installer.urllib.request, "build_opener", lambda *args: pytest.fail("network fallback"))
    with pytest.raises(ValueError, match="invalid_verifier_archive_digest"):
        installer.prepare()


def test_packaging_services_and_ci_use_one_fixed_distribution():
    api = (ROOT / "apps/api/Dockerfile").read_text()
    assert "python -m scripts.prepare_attestation_verifier" in api
    native = (ROOT / "infra/install/native.py").read_text()
    assert '"-m", "scripts.prepare_attestation_verifier"' in native
    for path in ("apps/worker/Dockerfile", "apps/runtime/ansible/Dockerfile"):
        assert "prepare_attestation_verifier" not in (ROOT / path).read_text()
    for path in (".github/workflows/ci.yml", ".github/workflows/release.yml"):
        assert "PYTHONPATH=apps/api python -m scripts.prepare_attestation_verifier" in (ROOT / path).read_text()
    assert "apps/api/app/attestation/bin" in (ROOT / ".dockerignore").read_text()
    required = json.loads((ROOT / "infra/release/package-manifest.json").read_text())["required_common"]
    assert "apps/api/app/attestation/trusted-root.jsonl" in required
    assert "apps/api/app/attestation/distribution.json" in required

