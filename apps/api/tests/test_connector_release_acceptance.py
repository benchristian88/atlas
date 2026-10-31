"""Real frozen signature verification; synthetic public responses are policy tests."""
import asyncio
import base64
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from app.services import connector_release_acceptance as service, local_release_authority as authority
from app.services.catalogue_source import GithubReader, BASE, SourceError
from app.services.official_provenance import GithubAttestationVerifier, ProvenanceError

FIXTURES = Path(__file__).parent / "fixtures/local_release"
IDENTITY = service.ReleaseIdentity("proxmox", "0.2.2", 429608780, 693849044,
    "e58788a667c0c0006477ac149e8ad28aedda0745", "2d66fc69b9cf9c70d7df117fe41bff3e3e056299f1908cde965e9e3f75e59abf")


@pytest.fixture
def public_responses(monkeypatch):
    values = {"release": json.loads((FIXTURES / "release.json").read_bytes()),
              "ref": json.loads((FIXTURES / "tag-ref.json").read_bytes()), "bytes": {}}
    class Reader:
        asset = GithubReader.asset
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def repository(self): pass  # Transport/ID checks have separate existing tests.
        async def get(self, url, maximum):
            assert url.startswith(BASE + "/")
            return json.dumps(values["ref" if "/git/ref/" in url else "release"]).encode()
        async def download(self, asset, *, maximum):
            raw = values["bytes"].get(asset["name"], (FIXTURES / asset["name"]).read_bytes())
            assert len(raw) <= maximum and len(raw) == asset["size"]
            assert "sha256:" + hashlib.sha256(raw).hexdigest() == asset["digest"]
            return raw
    monkeypatch.setattr(service, "GithubReader", Reader)
    return values


def test_original_release_signature_and_retained_result_without_installation(public_responses, tmp_path):
    result = asyncio.run(service.verify_release(IDENTITY, tmp_path / "verification"))
    assert result["provenance"]["artifact_sha256"] == IDENTITY.sha256
    assert result["provenance"]["workflow_identity"].endswith("/release.yml@refs/tags/proxmox-v0.2.2")
    assert result["provenance"]["source_commit"] == IDENTITY.source_commit
    assert result["release"]["immutable"] is True
    assert result["release"]["assets"]["package.sigstore.json"]["id"] == 693848554
    assert service.load_result(tmp_path / "verification")[1] == IDENTITY
    assert not (tmp_path / "verification/verification.json").exists()


@pytest.mark.parametrize("field,value", [("tag_name", "proxmox-v0.2.1"), ("id", 1), ("draft", True),
    ("prerelease", True), ("immutable", False), ("target_commitish", "a" * 40),
    ("html_url", "https://github.com/attacker/repository/releases/tag/proxmox-v0.2.2")])
def test_release_identity_failures_precede_authority(public_responses, tmp_path, field, value):
    public_responses["release"][field] = value
    with pytest.raises(SourceError): asyncio.run(service.verify_release(IDENTITY, tmp_path / "result"))
    assert not (tmp_path / "result").exists()


@pytest.mark.parametrize("failure", ["tag_commit", "annotated_tag", "asset_id", "asset_digest", "asset_url", "duplicate_asset"])
def test_substituted_tags_or_assets_are_rejected(public_responses, tmp_path, failure):
    release = public_responses["release"]
    asset = next(a for a in release["assets"] if a["name"].endswith(".tar.gz"))
    if failure == "tag_commit": public_responses["ref"]["object"]["sha"] = "a" * 40
    elif failure == "annotated_tag": public_responses["ref"]["object"]["type"] = "tag"
    elif failure == "asset_id": asset["id"] += 1
    elif failure == "asset_digest": asset["digest"] = "sha256:" + "0" * 64
    elif failure == "asset_url": asset["url"] = "https://example.test/substitute"
    elif failure == "duplicate_asset": release["assets"].append(deepcopy(asset))
    with pytest.raises(SourceError): asyncio.run(service.verify_release(IDENTITY, tmp_path / "result"))


@pytest.mark.parametrize("field,value", [("connector_id", "other"), ("version", "0.2.3"),
    ("sha256", "0" * 64), ("source_commit", "a" * 40)])
def test_real_signature_rejects_wrong_expected_identity(field, value):
    identity = replace(IDENTITY, **{field:value})
    with pytest.raises(ProvenanceError):
        GithubAttestationVerifier().verify_package((FIXTURES / "proxmox-0.2.2.tar.gz").read_bytes(),
            (FIXTURES / "package.sigstore.json").read_bytes(), identity.context())


@pytest.mark.parametrize("mutation", ["repository", "workflow", "signature", "signer", "truncated", "oversized", "package", "oversized_package"])
def test_real_crypto_rejects_altered_provenance_and_package(mutation):
    raw = (FIXTURES / "proxmox-0.2.2.tar.gz").read_bytes()
    bundle = json.loads((FIXTURES / "package.sigstore.json").read_bytes())
    if mutation in {"repository", "workflow"}:
        statement = json.loads(base64.b64decode(bundle["dsseEnvelope"]["payload"]))
        statement["predicate"]["buildDefinition"]["externalParameters"]["workflow"][mutation if mutation=="repository" else "path"] = "attacker"
        bundle["dsseEnvelope"]["payload"] = base64.b64encode(json.dumps(statement).encode()).decode()
    elif mutation == "signature": bundle["dsseEnvelope"]["signatures"][0]["sig"] = base64.b64encode(b"bad signature").decode()
    elif mutation == "signer":
        other = json.loads((FIXTURES.parent / "official_catalogue/catalogue.sigstore.json").read_bytes())
        bundle["verificationMaterial"]["certificate"] = other["verificationMaterial"]["certificate"]
    encoded = json.dumps(bundle).encode()
    if mutation == "truncated": encoded = encoded[:-20]
    elif mutation == "oversized": encoded = b"x" * (1024 * 1024 + 1)
    elif mutation == "package": raw += b"substituted"
    elif mutation == "oversized_package": raw = b"x" * (20 * 1024 * 1024 + 1)
    with pytest.raises(ProvenanceError): GithubAttestationVerifier().verify_package(raw, encoded, IDENTITY.context())


def test_shell_uid_cannot_approve_or_enroll(monkeypatch):
    monkeypatch.setattr(authority.os, "geteuid", lambda: 10001)
    with pytest.raises(ValueError, match="requires_root_operator"): authority.operator()


def test_production_store_is_refused_even_with_environment_flags(monkeypatch):
    monkeypatch.setenv("ATLAS_CONNECTOR_QUALIFICATION_ENABLED", "1")
    with pytest.raises(ValueError, match="production_store"): authority.binding(Path("/var/lib/atlas-connectors"))


@pytest.mark.parametrize("field,value", [("repository", "attacker/repository"), ("workflow", ".github/workflows/other.yml"),
    ("publisher_id", "other"), ("source_commit", "0" * 40)])
def test_detached_distribution_claims_cannot_substitute_official_identity(public_responses, tmp_path, field, value):
    manifest=json.loads((FIXTURES / "manifest.json").read_bytes())
    manifest["distribution"]["provenance"][field]=value
    raw=authority.canonical(manifest)
    public_responses["bytes"]["manifest.json"]=raw
    asset=next(a for a in public_responses["release"]["assets"] if a["name"]=="manifest.json")
    asset["size"],asset["digest"]=len(raw),"sha256:"+hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError): asyncio.run(service.verify_release(IDENTITY,tmp_path/"result"))


@pytest.mark.parametrize("failure", ["missing", "false", "expired", "future", "deployment"])
def test_explicit_isolation_inspection_fails_closed(failure):
    import time
    # Every negative starts with a complete, accepted report. In particular,
    # timestamps must be independently responsible for time-based rejection.
    resources = {"database": {"name": "test", "oid": "1", "cluster_id": "2"},
        "deployment": {"schema": 1, "deployment_id": "00000000-0000-0000-0000-000000000001", "name": "test"},
        "storage": {key: {"path": "/test/" + key, "device": 1, "inode": index}
                    for index, key in enumerate(("store", "public", "private"), 1)}}
    report={"deployment":"test", "checked_at":int(time.time()), "checks":{k:True for k in authority.ISOLATION_CHECKS},
            "resources": resources}
    authority.check_isolation(report, "test", resources)
    if failure=="missing": del report["checks"]["redis"]
    elif failure=="false": report["checks"]["storage"]=False
    elif failure=="expired": report["checked_at"]-=3601
    elif failure=="future": report["checked_at"]+=600
    elif failure=="deployment": report["deployment"]="production"
    with pytest.raises(ValueError,match="isolation_required"): authority.check_isolation(report,"test",resources)
    if failure in {"expired", "future"}:
        report["checked_at"] = int(time.time())
        authority.check_isolation(report, "test", resources)
