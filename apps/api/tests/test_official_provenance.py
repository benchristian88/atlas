"""Frozen real cryptographic regressions. Missing verifier dependencies FAIL CI."""
from copy import deepcopy
from dataclasses import replace
import base64
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

import pytest

from app import attestation_distribution as distribution
from app.services import official_provenance as provenance
from app.services.connector_verification import GithubSigstoreVerifier, VerificationEvidence
from app.services.official_catalogue import parse_official_catalogue
from app.services.official_provenance import (
    PackageArtifactContext, ProvenanceError, ProvenanceFailure as Failure, TrustProfile, VerifiedProvenance,
)

FIXTURES = Path(__file__).parent / "fixtures/official_catalogue"
ARTIFACT = (FIXTURES / "catalogue-000001.json").read_bytes()
BUNDLE = (FIXTURES / "catalogue.sigstore.json").read_bytes()
DIGEST = "55533ca67e7e9a14f82961e0a8c34ad78e2596049b3db02fde787494e3975afd"
COMMIT = "91dfd86f18d0b59ff977bb1e8a5fef42c5329943"


def verify(artifact=ARTIFACT, bundle=BUNDLE):
    return GithubSigstoreVerifier().verify_catalogue(artifact, bundle)


def test_genuine_catalogue_exact_bytes_and_authenticated_certificate_claims():
    # No skip, PATH lookup, or signature-verification mock.
    structural = parse_official_catalogue(ARTIFACT)
    evidence = verify(structural.source_bytes)
    assert isinstance(evidence, VerifiedProvenance)
    assert not isinstance(evidence, VerificationEvidence)
    assert evidence.profile == TrustProfile.CATALOGUE
    assert evidence.artifact_sha256 == DIGEST
    assert evidence.repository == provenance.REPOSITORY_URI
    assert evidence.repository_id == "1414494920" and evidence.owner_id == "93822871"
    assert evidence.workflow_identity == provenance.REPOSITORY_URI + "/.github/workflows/catalogue.yml@refs/heads/main"
    assert evidence.source_ref == "refs/heads/main" and evidence.source_commit == COMMIT
    assert evidence.oidc_issuer == provenance.OIDC_ISSUER
    assert evidence.runner_environment == "github-hosted"
    assert evidence.predicate_type == provenance.PREDICATE
    assert evidence.witnessed_at[0].timestamp.isoformat() == "2026-10-18T16:07:56+00:00"
    assert evidence.verifier_version == "2.102.1"
    assert evidence.policy_version == provenance.POLICY_VERSION
    assert evidence.trust_root_sha256 == "3c2cc7f357dc064ec527fdcd78da6e9245c21a381e1abaa0f2b62b186bcac1a1"
    structural.document["sequence"] = 999
    assert verify(structural.source_bytes).artifact_sha256 == DIGEST
    assert GithubSigstoreVerifier().verify_catalogue(
        ARTIFACT, BUNDLE, subject_name="catalogue-000001.json").subject_name == "catalogue-000001.json"


@pytest.mark.parametrize("artifact", [ARTIFACT + b"\n", ARTIFACT.replace(b'"sequence": 1', b'"sequence": 2')])
def test_modified_original_bytes_fail_real_crypto(artifact):
    with pytest.raises(ProvenanceError, match="unverifiable_provenance"):
        verify(artifact)


@pytest.mark.parametrize("mutation", ["signature", "no_signature", "certificate", "no_transparency",
    "transparency_proof", "subject_digest", "predicate", "statement_source", "truncated"])
def test_corrupt_evidence_fails_real_crypto(mutation):
    value = json.loads(BUNDLE)
    if mutation == "signature":
        value["dsseEnvelope"]["signatures"][0]["sig"] = base64.b64encode(b"invalid signature").decode()
    elif mutation == "no_signature":
        value["dsseEnvelope"]["signatures"] = []
    elif mutation == "certificate":
        other = json.loads((FIXTURES / "package.sigstore.json").read_bytes())
        value["verificationMaterial"]["certificate"] = other["verificationMaterial"]["certificate"]
    elif mutation == "no_transparency":
        value["verificationMaterial"]["tlogEntries"] = []
    elif mutation == "transparency_proof":
        value["verificationMaterial"]["tlogEntries"][0]["inclusionProof"]["rootHash"] = base64.b64encode(b"\0" * 32).decode()
    elif mutation in {"subject_digest", "predicate", "statement_source"}:
        statement = json.loads(base64.b64decode(value["dsseEnvelope"]["payload"]))
        if mutation == "subject_digest":
            for subject in statement["subject"]:
                subject["digest"]["sha256"] = "0" * 64
        elif mutation == "predicate":
            statement["predicateType"] = "https://example.test/unaccepted"
        else:
            statement["predicate"]["buildDefinition"]["externalParameters"]["workflow"]["repository"] = "https://github.com/attacker/repository"
        value["dsseEnvelope"]["payload"] = base64.b64encode(json.dumps(statement).encode()).decode()
    raw = json.dumps(value).encode()
    if mutation == "truncated":
        raw = raw[:-50]
    with pytest.raises(ProvenanceError) as caught:
        verify(bundle=raw)
    assert caught.value.reason in {Failure.UNVERIFIABLE, Failure.MALFORMED_BUNDLE}


@pytest.mark.parametrize("old,new", [
    (b"1414494920", b"2414494920"), (b"93822871", b"93822872"),
    (b"benchristian88", b"benchristian89"), (b"catalogue.yml", b"malicious.yml"),
    (b"refs/heads/main", b"refs/heads/evil"), (b"github-hosted", b"self--hosted"),
    (b"https://token.actions.githubusercontent.com", b"https://token.actions.attackercontentxx.com"),
])
def test_tampered_certificate_identity_claims_cannot_authenticate(old, new):
    value = json.loads(BUNDLE)
    certificate = base64.b64decode(value["verificationMaterial"]["certificate"]["rawBytes"])
    assert old in certificate
    value["verificationMaterial"]["certificate"]["rawBytes"] = base64.b64encode(certificate.replace(old, new)).decode()
    with pytest.raises(ProvenanceError, match="unverifiable_provenance"):
        verify(bundle=json.dumps(value).encode())


def test_catalogue_workflow_is_not_package_authority():
    context = PackageArtifactContext("future-connector", "17.3.1", DIGEST, COMMIT)
    with pytest.raises(ProvenanceError, match="unverifiable_provenance"):
        GithubSigstoreVerifier().verify_package(ARTIFACT, BUNDLE, context)


def test_package_bundle_is_not_catalogue_authority():
    with pytest.raises(ProvenanceError, match="unverifiable_provenance"):
        verify(bundle=(FIXTURES / "package.sigstore.json").read_bytes())


def test_expected_package_digest_is_checked_before_external_verification():
    context = PackageArtifactContext("future-connector", "17.3.1", "0" * 64, COMMIT)
    with pytest.raises(ProvenanceError, match="wrong_subject_digest"):
        GithubSigstoreVerifier().verify_package(ARTIFACT, BUNDLE, context)


@pytest.fixture
def authenticated_output(monkeypatch):
    original = provenance._run
    captured = []
    def run(*args):
        raw = original(*args)
        if "attestation" in args[0]:
            captured.append(raw)
        return raw
    monkeypatch.setattr(provenance, "_run", run)
    verify()
    assert len(captured) == 1
    return json.loads(captured[0])


def enforce(output):
    return provenance._evidence(json.dumps(output).encode(), profile=TrustProfile.CATALOGUE,
        digest=DIGEST, name="catalogue.json", ref="refs/heads/main", workflow=".github/workflows/catalogue.yml",
        commit=None, lock=distribution.distribution_lock())


@pytest.mark.parametrize("field,value,reason", [
    ("sourceRepositoryIdentifier", "1", Failure.WRONG_REPOSITORY),
    ("sourceRepositoryOwnerIdentifier", "1", Failure.WRONG_REPOSITORY),
    ("sourceRepositoryURI", "https://github.com/attacker/repo", Failure.WRONG_REPOSITORY),
    ("sourceRepositoryOwnerURI", "https://github.com/attacker", Failure.WRONG_REPOSITORY),
    ("subjectAlternativeName", "https://github.com/attacker", Failure.WRONG_WORKFLOW),
    ("buildSignerURI", "https://github.com/attacker", Failure.WRONG_WORKFLOW),
    ("buildConfigURI", "https://github.com/attacker", Failure.WRONG_WORKFLOW),
    ("sourceRepositoryRef", "refs/heads/other", Failure.WRONG_SOURCE_REF),
    ("sourceRepositoryDigest", "a" * 40, Failure.WRONG_SOURCE_COMMIT),
    ("buildSignerDigest", "a" * 40, Failure.WRONG_SOURCE_COMMIT),
    ("buildConfigDigest", "a" * 40, Failure.WRONG_SOURCE_COMMIT),
    ("issuer", "https://example.test", Failure.WRONG_ISSUER),
    ("runnerEnvironment", "self-hosted", Failure.UNTRUSTED_RUNNER),
])
def test_additional_certificate_policy_rejects_disagreement(authenticated_output, field, value, reason):
    # Negative unit test of policy layer; never a fabricated crypto success.
    authenticated_output[0]["verificationResult"]["signature"]["certificate"][field] = value
    with pytest.raises(ProvenanceError) as caught:
        enforce(authenticated_output)
    assert caught.value.reason == reason


@pytest.mark.parametrize("mutation,reason", [
    ("subject", Failure.WRONG_SUBJECT_DIGEST), ("name", Failure.WRONG_SUBJECT_NAME),
    ("predicate", Failure.UNSUPPORTED_PREDICATE), ("timestamps", Failure.UNVERIFIABLE),
    ("missing_id", Failure.MALFORMED_OUTPUT), ("workflow", Failure.UNVERIFIABLE),
    ("source", Failure.UNVERIFIABLE), ("multiple", Failure.MALFORMED_OUTPUT),
])
def test_incomplete_or_inconsistent_verified_output_is_not_evidence(authenticated_output, mutation, reason):
    verified = authenticated_output[0]["verificationResult"]
    if mutation == "subject":
        verified["statement"]["subject"][1]["digest"]["sha256"] = "0" * 64
    elif mutation == "name":
        verified["statement"]["subject"][1]["name"] = "other.json"
    elif mutation == "predicate":
        verified["statement"]["predicateType"] = "unsupported"
    elif mutation == "timestamps":
        verified["verifiedTimestamps"] = []
    elif mutation == "missing_id":
        del verified["signature"]["certificate"]["sourceRepositoryIdentifier"]
    elif mutation == "workflow":
        verified["statement"]["predicate"]["buildDefinition"]["externalParameters"]["workflow"]["path"] = ".github/workflows/release.yml"
    elif mutation == "source":
        verified["statement"]["predicate"]["buildDefinition"]["resolvedDependencies"][0]["digest"]["gitCommit"] = "0" * 40
    elif mutation == "multiple":
        authenticated_output.append(deepcopy(authenticated_output[0]))
    with pytest.raises(ProvenanceError) as caught:
        enforce(authenticated_output)
    assert caught.value.reason == reason


@pytest.mark.parametrize("raw,reason", [(b"", Failure.MISSING_ATTESTATION), (None, Failure.MISSING_ATTESTATION),
    (b"{}", Failure.MALFORMED_BUNDLE), (b"[]", Failure.MALFORMED_BUNDLE),
    (b'{"a":1,"a":2}', Failure.MALFORMED_BUNDLE), (b"\xff", Failure.MALFORMED_BUNDLE),
    (b"[" * 2000, Failure.MALFORMED_BUNDLE), (b"x" * (provenance.MAX_BUNDLE_BYTES + 1), Failure.OVERSIZED_BUNDLE)])
def test_input_bounds_and_missing_bundle(raw, reason):
    with pytest.raises(ProvenanceError) as caught:
        verify(bundle=raw)
    assert caught.value.reason == reason


@pytest.mark.parametrize("artifact", [None, "text", b"", b"x" * 4_194_305])
def test_artifact_bounds(artifact):
    with pytest.raises(ProvenanceError, match="invalid_artifact_bytes"):
        verify(artifact)


def test_environment_arguments_private_files_and_cleanup(monkeypatch):
    for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "DATABASE_URL", "AUTH_SECRET_KEY",
                 "HTTPS_PROXY", "GH_HOST", "GH_DEBUG", "GIT_CONFIG", "BASH_ENV", "LD_PRELOAD"):
        monkeypatch.setenv(name, "untrusted-ambient-marker")
    original = subprocess.Popen
    workspaces = []
    def spawn(args, **kwargs):
        workspace = kwargs["cwd"]
        workspaces.append(workspace)
        assert "untrusted-ambient-marker" not in kwargs["env"].values()
        assert kwargs["env"]["HOME"] == str(workspace)
        assert kwargs["env"]["GH_CONFIG_DIR"] == str(workspace / "config")
        assert kwargs["shell"] is False and kwargs["close_fds"] is True
        assert kwargs["start_new_session"] is True and kwargs["stdin"] == subprocess.DEVNULL
        assert args[0] == str(distribution.DISTRIBUTION / "bin/gh")
        assert stat.S_IMODE(workspace.stat().st_mode) == 0o700
        if "attestation" in args:
            assert "--bundle" in args and "--custom-trusted-root" in args
            assert (workspace / "artifact").read_bytes() == ARTIFACT
            assert all(stat.S_IMODE((workspace / name).stat().st_mode) == 0o600
                       for name in ("artifact", "bundle.json", "roots.jsonl"))
        return original(args, **kwargs)
    monkeypatch.setattr(subprocess, "Popen", spawn)
    assert verify().artifact_sha256 == DIGEST
    assert workspaces and all(not p.exists() for p in workspaces)


@pytest.mark.parametrize("name", ["--repo=attacker/repo", "../catalogue.json", "catalogue.json;evil", "oci://evil"])
def test_subject_cannot_inject_arguments_or_paths(name):
    with pytest.raises(ProvenanceError, match="invalid_artifact_context"):
        GithubSigstoreVerifier().verify_catalogue(ARTIFACT, BUNDLE, subject_name=name)


@pytest.mark.parametrize("field,value", [("connector_id", "../evil"), ("version", "1.0.0;evil"),
    ("sha256", "--repo=evil"), ("source_commit", "--source-ref=evil")])
def test_package_context_cannot_inject_arguments(field, value):
    context = replace(PackageArtifactContext("generic", "1.0.0", DIGEST, COMMIT), **{field: value})
    with pytest.raises(ProvenanceError, match="invalid_artifact_context"):
        GithubSigstoreVerifier().verify_package(ARTIFACT, BUNDLE, context)


@pytest.mark.parametrize("kind", ["missing", "corrupt", "link", "writable"])
def test_missing_or_changed_executable_fails_closed(tmp_path, monkeypatch, kind):
    root = tmp_path / "distribution"
    root.mkdir()
    for name in ("distribution.json", "trusted-root.jsonl"):
        (root / name).write_bytes((distribution.DISTRIBUTION / name).read_bytes())
    (root / "bin").mkdir()
    binary = root / "bin/gh"
    if kind == "corrupt":
        binary.write_bytes(b"corrupt")
        binary.chmod(0o555)
    elif kind == "link":
        binary.symlink_to(distribution.DISTRIBUTION / "bin/gh")
    elif kind == "writable":
        binary.write_bytes((distribution.DISTRIBUTION / "bin/gh").read_bytes())
        binary.chmod(0o755)
    monkeypatch.setattr(distribution, "DISTRIBUTION", root)
    with pytest.raises(ProvenanceError, match="official_provenance_verifier_unavailable"):
        verify()


@pytest.mark.parametrize("kind", ["missing", "corrupt", "link"])
def test_missing_or_corrupt_roots_fail_closed(tmp_path, monkeypatch, kind):
    (tmp_path / "distribution.json").write_bytes((distribution.DISTRIBUTION / "distribution.json").read_bytes())
    if kind == "corrupt":
        (tmp_path / "trusted-root.jsonl").write_bytes(b"{}\n")
    elif kind == "link":
        (tmp_path / "trusted-root.jsonl").symlink_to(distribution.DISTRIBUTION / "trusted-root.jsonl")
    monkeypatch.setattr(distribution, "DISTRIBUTION", tmp_path)
    with pytest.raises(ProvenanceError, match="invalid_trust_root"):
        verify()


@pytest.mark.parametrize("program,reason", [
    ("import time; time.sleep(5)", Failure.TIMEOUT),
    ("import sys; sys.stdout.write('[]'); sys.exit(1)", Failure.UNVERIFIABLE),
    ("import sys; sys.stdout.write('x'*20000)", Failure.OVERSIZED_OUTPUT),
    ("import sys; sys.stderr.write('x'*20000)", Failure.OVERSIZED_OUTPUT),
])
def test_subprocess_timeout_failure_and_combined_output_bounds(tmp_path, monkeypatch, program, reason):
    monkeypatch.setattr(provenance, "MAX_OUTPUT_BYTES", 4096)
    with pytest.raises(ProvenanceError) as caught:
        provenance._run([sys.executable, "-c", program], tmp_path, time.monotonic() + 0.5)
    assert caught.value.reason == reason


def test_subprocess_missing_executable(tmp_path):
    with pytest.raises(ProvenanceError, match="official_provenance_verifier_unavailable"):
        provenance._run([str(tmp_path / "absent")], tmp_path, time.monotonic() + 1)


@pytest.mark.parametrize("kind,reason", [("version", Failure.UNSUPPORTED_VERSION),
    ("output", Failure.MALFORMED_OUTPUT), ("failure", Failure.UNVERIFIABLE)])
def test_failed_process_and_malformed_output_cleanup(tmp_path, monkeypatch, kind, reason):
    # Negative-only fake executable; never capable of successful verification.
    binary = tmp_path / "fake-gh"
    version = "bad version" if kind == "version" else "gh version 2.102.1 (2026-10-20)"
    binary.write_text(f"#!{sys.executable}\nimport sys\nif '--version' in sys.argv: print({version!r})\nelse:\n print('not JSON')\n sys.exit({1 if kind == 'failure' else 0})\n")
    binary.chmod(0o555)
    monkeypatch.setattr(distribution, "checked_binary", lambda _: binary)
    before = set(provenance.TEMP_ROOT.glob("atlas-attestation-*"))
    with pytest.raises(ProvenanceError) as caught:
        verify()
    assert caught.value.reason == reason
    assert set(provenance.TEMP_ROOT.glob("atlas-attestation-*")) == before


def test_unsafe_temporary_root_is_rejected(tmp_path, monkeypatch):
    link = tmp_path / "link"
    link.symlink_to(provenance.TEMP_ROOT)
    monkeypatch.setattr(provenance, "TEMP_ROOT", link)
    with pytest.raises(ProvenanceError, match="internal_verification_failure"):
        verify()


def test_untrusted_root_fails_actual_cryptographic_verifier(tmp_path):
    lock = distribution.distribution_lock()
    root = json.loads(distribution.checked_root(lock))
    root["certificateAuthorities"] = []
    (tmp_path / "roots.jsonl").write_text(json.dumps(root) + "\n")
    (tmp_path / "artifact").write_bytes(ARTIFACT)
    (tmp_path / "bundle.json").write_bytes(BUNDLE)
    with pytest.raises(ProvenanceError, match="unverifiable_provenance"):
        provenance._run([str(distribution.checked_binary(lock)), "attestation", "verify", str(tmp_path / "artifact"),
            "--bundle", str(tmp_path / "bundle.json"), "--custom-trusted-root", str(tmp_path / "roots.jsonl"),
            "--repo", provenance.REPOSITORY, "--format", "json"], tmp_path, time.monotonic() + 10)

