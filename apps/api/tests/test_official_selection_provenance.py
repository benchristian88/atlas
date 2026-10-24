"""Genuine offline cryptography, followed by separately labelled policy tests.

No mock can produce verification success. Policy tests mutate captured output
from the real pinned verifier and call only the structured-evidence validator.
"""
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import socket
import subprocess
from types import SimpleNamespace

import pytest

from app import attestation_distribution as distribution
from app.services import official_provenance as provenance
from app.services.connector_verification import GithubSigstoreVerifier, VerificationEvidence
from app.services.official_catalogue_selection import parse_official_catalogue_selection
from app.services.official_provenance import ProvenanceError, ProvenanceFailure as Failure, TrustProfile

FIXTURES = Path(__file__).parent / "fixtures/official_catalogue"
RAW = (FIXTURES / "current.json").read_bytes()
BUNDLE = (FIXTURES / "current.sigstore.json").read_bytes()
DIGEST = "a275f63d0ac818a193826478328ee324be62353addc5c97a2ed0a28d217b5372"
BUNDLE_DIGEST = "5ccab9abdc31fbae55787c102e4f2eb305f7d37966d9dacb02d0c5cb8f8cf522"
SIGNING_SOURCE = "8ce0b80c74d6ceb8ce75ac7ec8693f5bba78b305"
INVOCATION = provenance.REPOSITORY_URI + "/actions/runs/39896288128/attempts/1"
WORKFLOW = ".github/workflows/catalogue-publish.yml"


def verify(raw=RAW, bundle=BUNDLE):
    return GithubSigstoreVerifier().verify_selection(raw, bundle)


def test_genuine_sequence_one_selection_verifies_with_actual_pinned_offline_infrastructure(monkeypatch):
    # Python must never retrieve evidence; gh receives local bundle/frozen roots
    # and a constructed environment with no credentials or proxy discovery.
    def no_python_network(*args, **kwargs):
        raise AssertionError("Frozen selection verification must be offline")
    monkeypatch.setattr(socket, "create_connection", no_python_network)
    for name in ("GH_TOKEN", "GITHUB_TOKEN", "HTTPS_PROXY", "GH_HOST"):
        monkeypatch.setenv(name, "ambient-marker")
    original = subprocess.Popen
    calls = []
    def spawn(arguments, **kwargs):
        calls.append(arguments)
        assert "ambient-marker" not in kwargs["env"].values()
        assert kwargs["env"] == provenance._environment(kwargs["cwd"])
        assert kwargs["shell"] is False and kwargs["start_new_session"] is True
        if "attestation" in arguments:
            assert "--bundle" in arguments and "--custom-trusted-root" in arguments
            assert arguments[arguments.index("--cert-identity") + 1] == provenance.REPOSITORY_URI + "/" + WORKFLOW + "@refs/heads/main"
            assert arguments[arguments.index("--source-ref") + 1] == "refs/heads/main"
            assert "--deny-self-hosted-runners" in arguments
            assert (kwargs["cwd"] / "artifact").read_bytes() == RAW
            assert (kwargs["cwd"] / "bundle.json").read_bytes() == BUNDLE
        return original(arguments, **kwargs)
    monkeypatch.setattr(subprocess, "Popen", spawn)
    assert hashlib.sha256(RAW).hexdigest() == DIGEST
    assert hashlib.sha256(BUNDLE).hexdigest() == BUNDLE_DIGEST
    evidence = verify(parse_official_catalogue_selection(RAW).source_bytes)
    assert evidence.profile == TrustProfile.SELECTION
    assert not isinstance(evidence, VerificationEvidence)
    assert evidence.subject_name == "current.json" and evidence.artifact_sha256 == DIGEST
    assert evidence.repository == provenance.REPOSITORY_URI
    assert evidence.repository_id == "1414494920" and evidence.owner_id == "93822871"
    assert evidence.workflow_identity == provenance.REPOSITORY_URI + "/" + WORKFLOW + "@refs/heads/main"
    assert evidence.source_ref == "refs/heads/main" and evidence.source_commit == SIGNING_SOURCE
    assert evidence.invocation_uri == INVOCATION
    assert evidence.oidc_issuer == provenance.OIDC_ISSUER
    assert evidence.runner_environment == "github-hosted" and evidence.predicate_type == provenance.PREDICATE
    assert evidence.witnessed_at[0].kind == "Tlog"
    assert evidence.witnessed_at[0].timestamp.isoformat() == "2026-10-23T03:41:42+00:00"
    assert evidence.verifier_version == "2.102.1" and evidence.policy_version == provenance.POLICY_VERSION
    assert evidence.trust_root_id == "sigstore-public-good-2026-10-21"
    assert evidence.trust_root_sha256 == "3c2cc7f357dc064ec527fdcd78da6e9245c21a381e1abaa0f2b62b186bcac1a1"
    assert len(calls) == 2
    # No comparison to present main or activation revision is made. The signed
    # selection and the original catalogue have genuinely different build sources.
    monkeypatch.setattr(subprocess, "Popen", original)
    catalogue = GithubSigstoreVerifier().verify_catalogue(
        (FIXTURES / "catalogue-000001.json").read_bytes(), (FIXTURES / "catalogue.sigstore.json").read_bytes())
    assert catalogue.source_commit == "91dfd86f18d0b59ff977bb1e8a5fef42c5329943" != evidence.source_commit


@pytest.mark.parametrize("raw", [RAW + b"\n", RAW.replace(b'"sequence": 1', b'"sequence": 2'),
    RAW.replace(b"667867351", b"667867352")])
def test_altered_original_pointer_fails_real_cryptography(raw):
    with pytest.raises(ProvenanceError, match="unverifiable_provenance"):
        verify(raw)


@pytest.mark.parametrize("name", ["catalogue.sigstore.json", "package.sigstore.json"])
def test_substituted_bundle_fails_real_cryptography(name):
    with pytest.raises(ProvenanceError, match="unverifiable_provenance"):
        verify(bundle=(FIXTURES / name).read_bytes())


def test_selection_signature_is_not_catalogue_profile_authority():
    with pytest.raises(ProvenanceError, match="unverifiable_provenance"):
        GithubSigstoreVerifier().verify_catalogue(RAW, BUNDLE)


def test_genuine_selection_evidence_cannot_promote_trusted_catalogue_state():
    from app.services import catalogue_source, trusted_catalogue

    candidate = SimpleNamespace(raw=RAW, provenance=verify(), publication={"immutable": True})
    # Fails before any database access or publication acceptance.
    with pytest.raises(catalogue_source.SourceError, match="catalogue_evidence_mismatch"):
        trusted_catalogue._promote(None, None, candidate)


@pytest.mark.parametrize("mutation", ["subject", "digest", "predicate", "source", "invocation", "signature", "proof", "no_transparency"])
def test_tampered_signed_evidence_rejected_by_real_cryptography(mutation):
    value = json.loads(BUNDLE)
    if mutation == "signature":
        value["dsseEnvelope"]["signatures"][0]["sig"] = base64.b64encode(b"invalid").decode()
    elif mutation == "proof":
        value["verificationMaterial"]["tlogEntries"][0]["inclusionProof"]["rootHash"] = base64.b64encode(b"\0" * 32).decode()
    elif mutation == "no_transparency":
        value["verificationMaterial"]["tlogEntries"] = []
    else:
        statement = json.loads(base64.b64decode(value["dsseEnvelope"]["payload"]))
        if mutation == "subject":
            statement["subject"][0]["name"] = "other.json"
        elif mutation == "digest":
            statement["subject"][0]["digest"]["sha256"] = "0" * 64
        elif mutation == "predicate":
            statement["predicateType"] = "unsupported"
        elif mutation == "source":
            statement["predicate"]["buildDefinition"]["resolvedDependencies"][0]["digest"]["gitCommit"] = "0" * 40
        else:
            statement["predicate"]["runDetails"]["metadata"]["invocationId"] = INVOCATION[:-1] + "2"
        value["dsseEnvelope"]["payload"] = base64.b64encode(json.dumps(statement).encode()).decode()
    with pytest.raises(ProvenanceError, match="unverifiable_provenance"):
        verify(bundle=json.dumps(value).encode())


@pytest.mark.parametrize("old,new", [
    (b"1414494920", b"2414494920"), (b"93822871", b"93822872"),
    (b"benchristian88", b"benchristian89"), (b"catalogue-publish.yml", b"malicious-signerx.yml"),
    (b"refs/heads/main", b"refs/heads/evil"), (b"github-hosted", b"self--hosted"),
    (b"https://token.actions.githubusercontent.com", b"https://token.actions.attackercontentxx.com"),
    (SIGNING_SOURCE.encode(), b"0" * 40), (b"/attempts/1", b"/attempts/2"),
])
def test_certificate_tampering_fails_real_cryptography(old, new):
    value = json.loads(BUNDLE)
    certificate = base64.b64decode(value["verificationMaterial"]["certificate"]["rawBytes"])
    assert old in certificate
    value["verificationMaterial"]["certificate"]["rawBytes"] = base64.b64encode(certificate.replace(old, new)).decode()
    with pytest.raises(ProvenanceError, match="unverifiable_provenance"):
        verify(bundle=json.dumps(value).encode())


@pytest.mark.parametrize("raw", [None, "text", b"", b"x" * 1025])
def test_selection_artifact_bound(raw):
    with pytest.raises(ProvenanceError, match="invalid_artifact_bytes"):
        verify(raw)


# Structured-output policy unit tests below are NOT cryptographic acceptance.
@pytest.fixture(scope="module")
def genuine_verified_output():
    captured = []
    original = provenance._run
    with pytest.MonkeyPatch.context() as patch:
        def run(*args):
            raw = original(*args)
            if "attestation" in args[0]:
                captured.append(raw)
            return raw
        patch.setattr(provenance, "_run", run)
        verify()
    assert len(captured) == 1
    return json.loads(captured[0])


@pytest.fixture
def policy_output(genuine_verified_output):
    return deepcopy(genuine_verified_output)


def enforce_policy(output):
    return provenance._evidence(json.dumps(output).encode(), profile=TrustProfile.SELECTION,
        digest=DIGEST, name="current.json", ref="refs/heads/main", workflow=WORKFLOW,
        commit=None, lock=distribution.distribution_lock())


@pytest.mark.parametrize("field,value,reason", [
    ("sourceRepositoryURI", "https://github.com/attacker/repo", Failure.WRONG_REPOSITORY),
    ("sourceRepositoryIdentifier", "1", Failure.WRONG_REPOSITORY),
    ("sourceRepositoryOwnerURI", "https://github.com/attacker", Failure.WRONG_REPOSITORY),
    ("sourceRepositoryOwnerIdentifier", "1", Failure.WRONG_REPOSITORY),
    ("subjectAlternativeName", "https://github.com/attacker", Failure.WRONG_WORKFLOW),
    ("buildSignerURI", provenance.REPOSITORY_URI + "/.github/workflows/catalogue.yml@refs/heads/main", Failure.WRONG_WORKFLOW),
    ("buildConfigURI", "https://github.com/attacker", Failure.WRONG_WORKFLOW),
    ("sourceRepositoryRef", "refs/heads/evil", Failure.WRONG_SOURCE_REF),
    ("sourceRepositoryDigest", "0" * 40, Failure.WRONG_SOURCE_COMMIT),
    ("buildSignerDigest", "0" * 40, Failure.WRONG_SOURCE_COMMIT),
    ("buildConfigDigest", "0" * 40, Failure.WRONG_SOURCE_COMMIT),
    ("issuer", "https://attacker.test", Failure.WRONG_ISSUER),
    ("runnerEnvironment", "self-hosted", Failure.UNTRUSTED_RUNNER),
])
def test_structured_policy_certificate_constraints(policy_output, field, value, reason):
    policy_output[0]["verificationResult"]["signature"]["certificate"][field] = value
    with pytest.raises(ProvenanceError) as caught:
        enforce_policy(policy_output)
    assert caught.value.reason == reason


@pytest.mark.parametrize("suffix", ["0/attempts/1", "01/attempts/1", "-1/attempts/1", "+1/attempts/1",
    "1.0/attempts/1", "1e2/attempts/1", "1/attempts/2", "1/attempts/99", "1/attempts/01",
    "1", "1/attempts/1/", "1/attempts/1?x=1", "1/attempts/1#fragment", "1/attempts/1\n", "a/attempts/1",
    "1" * 21 + "/attempts/1"])
def test_structured_policy_requires_exact_positive_first_attempt_invocation(policy_output, suffix):
    invocation = provenance.REPOSITORY_URI + "/actions/runs/" + suffix
    result = policy_output[0]["verificationResult"]
    result["signature"]["certificate"]["runInvocationURI"] = invocation
    result["statement"]["predicate"]["runDetails"]["metadata"]["invocationId"] = invocation
    with pytest.raises(ProvenanceError, match="unverifiable_provenance"):
        enforce_policy(policy_output)


@pytest.mark.parametrize("invocation", [INVOCATION.replace("github.com/", "github.com.evil.test/"),
    INVOCATION.replace("https:", "http:"), INVOCATION.replace("atlas-connectors", "other-repo"),
    INVOCATION.replace("benchristian88", "attacker"), INVOCATION.replace("github.com", "github.com:443"), None])
def test_structured_policy_invocation_origin_cannot_change(policy_output, invocation):
    result = policy_output[0]["verificationResult"]
    result["signature"]["certificate"]["runInvocationURI"] = invocation
    result["statement"]["predicate"]["runDetails"]["metadata"]["invocationId"] = invocation
    with pytest.raises(ProvenanceError, match="unverifiable_provenance"):
        enforce_policy(policy_output)


@pytest.mark.parametrize("mutation,reason", [
    ("name", Failure.WRONG_SUBJECT_NAME), ("digest", Failure.WRONG_SUBJECT_DIGEST),
    ("duplicate_subject", Failure.WRONG_SUBJECT_NAME), ("predicate", Failure.UNSUPPORTED_PREDICATE),
    ("workflow", Failure.UNVERIFIABLE), ("ref", Failure.UNVERIFIABLE), ("source", Failure.UNVERIFIABLE),
    ("builder", Failure.UNVERIFIABLE), ("invocation_mismatch", Failure.UNVERIFIABLE),
    ("timestamps", Failure.UNVERIFIABLE), ("untrusted_log", Failure.UNVERIFIABLE),
    ("missing_identity", Failure.MALFORMED_OUTPUT), ("multiple", Failure.MALFORMED_OUTPUT),
])
def test_structured_policy_predicate_and_evidence_consistency(policy_output, mutation, reason):
    result = policy_output[0]["verificationResult"]
    statement = result["statement"]
    predicate = statement["predicate"]
    if mutation == "name":
        statement["subject"][0]["name"] = "catalogue.json"
    elif mutation == "digest":
        statement["subject"][0]["digest"]["sha256"] = "0" * 64
    elif mutation == "duplicate_subject":
        statement["subject"].append(deepcopy(statement["subject"][0]))
    elif mutation == "predicate":
        statement["predicateType"] = "unsupported"
    elif mutation in {"workflow", "ref"}:
        field = "path" if mutation == "workflow" else "ref"
        predicate["buildDefinition"]["externalParameters"]["workflow"][field] = "other"
    elif mutation == "source":
        predicate["buildDefinition"]["resolvedDependencies"][0]["digest"]["gitCommit"] = "0" * 40
    elif mutation == "builder":
        predicate["runDetails"]["builder"]["id"] = "other"
    elif mutation == "invocation_mismatch":
        predicate["runDetails"]["metadata"]["invocationId"] = INVOCATION.replace("39896288128", "39896288129")
    elif mutation == "timestamps":
        result["verifiedTimestamps"] = []
    elif mutation == "untrusted_log":
        result["verifiedTimestamps"][0]["uri"] = "https://attacker.test"
    elif mutation == "missing_identity":
        del result["signature"]["certificate"]["sourceRepositoryIdentifier"]
    else:
        policy_output.append(deepcopy(policy_output[0]))
    with pytest.raises(ProvenanceError) as caught:
        enforce_policy(policy_output)
    assert caught.value.reason == reason
