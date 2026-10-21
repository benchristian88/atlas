"""Offline cryptographic provenance, never catalogue or installation authority.

Only successful output from the pinned verifier is policy evidence. Certificate
claims are OIDC/CA authenticated; statement claims are signed workflow assertions.
Neither establishes GitHub Release approval, asset identity or immutability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import tempfile
import time

from app import attestation_distribution as distribution
from app.release import Version
from app.services.connector_contracts import ConnectorPackageError

REPOSITORY = "benchristian88/atlas-connectors"
REPOSITORY_URI = f"https://github.com/{REPOSITORY}"
REPOSITORY_ID = "1414494920"
OWNER_ID = "93822871"
OWNER_URI = "https://github.com/benchristian88"
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
PREDICATE = "https://slsa.dev/provenance/v1"
POLICY_VERSION = "atlas-official-provenance-v1"
MAX_BUNDLE_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024  # combined stdout/stderr
TIMEOUT_SECONDS = 20
TEMP_ROOT = Path("/private/tmp" if os.uname().sysname == "Darwin" else "/tmp")


class ProvenanceFailure(StrEnum):
    VERIFIER_UNAVAILABLE = "official_provenance_verifier_unavailable"
    UNSUPPORTED_VERSION = "unsupported_verifier_version"
    MISSING_ATTESTATION = "missing_attestation"
    MALFORMED_BUNDLE = "malformed_attestation_bundle"
    OVERSIZED_BUNDLE = "oversized_attestation_bundle"
    INVALID_SIGNATURE = "invalid_signature"
    INVALID_ROOT = "invalid_trust_root"
    WRONG_REPOSITORY = "wrong_repository"
    WRONG_WORKFLOW = "wrong_workflow"
    WRONG_SOURCE_REF = "wrong_source_ref"
    WRONG_SOURCE_COMMIT = "wrong_source_commit"
    WRONG_SUBJECT_DIGEST = "wrong_subject_digest"
    WRONG_SUBJECT_NAME = "wrong_subject_name"
    WRONG_ISSUER = "wrong_oidc_issuer"
    UNSUPPORTED_PREDICATE = "unsupported_predicate"
    UNTRUSTED_RUNNER = "untrusted_runner"
    UNVERIFIABLE = "unverifiable_provenance"
    TIMEOUT = "verifier_timeout"
    MALFORMED_OUTPUT = "malformed_verifier_output"
    OVERSIZED_OUTPUT = "oversized_verifier_output"
    INTERNAL = "internal_verification_failure"
    INVALID_CONTEXT = "invalid_artifact_context"
    INVALID_ARTIFACT = "invalid_artifact_bytes"


class ProvenanceError(ConnectorPackageError):
    def __init__(self, reason: ProvenanceFailure):
        self.reason = reason
        super().__init__(reason.value)


class TrustProfile(StrEnum):
    CATALOGUE = "official-catalogue"
    PACKAGE = "official-package"


@dataclass(frozen=True)
class PackageArtifactContext:
    """Expected identity, not evidence; B3 must obtain it from accepted metadata."""
    connector_id: str
    version: str
    sha256: str
    source_commit: str


@dataclass(frozen=True)
class VerifiedTimestamp:
    kind: str
    uri: str
    timestamp: datetime


@dataclass(frozen=True)
class VerifiedProvenance:
    profile: TrustProfile
    artifact_sha256: str
    subject_name: str
    repository: str
    repository_id: str
    owner_id: str
    workflow_identity: str
    source_ref: str
    source_commit: str
    oidc_issuer: str
    runner_environment: str
    predicate_type: str
    invocation_uri: str
    witnessed_at: tuple[VerifiedTimestamp, ...]
    verifier_version: str
    policy_version: str
    trust_root_id: str
    trust_root_sha256: str
    verified_at: datetime


def _require(condition: bool, reason: ProvenanceFailure) -> None:
    if not condition:
        raise ProvenanceError(reason)


def _json(raw: bytes, reason: ProvenanceFailure):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError()
            result[key] = value
        return result
    def constant(_):
        raise ValueError()
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ProvenanceError(reason) from None


def _bundle(raw: bytes) -> None:
    _require(isinstance(raw, bytes) and bool(raw), ProvenanceFailure.MISSING_ATTESTATION)
    _require(len(raw) <= MAX_BUNDLE_BYTES, ProvenanceFailure.OVERSIZED_BUNDLE)
    value = _json(raw, ProvenanceFailure.MALFORMED_BUNDLE)
    try:
        _require(value["mediaType"] == "application/vnd.dev.sigstore.bundle.v0.3+json",
                 ProvenanceFailure.MALFORMED_BUNDLE)
        envelope = value["dsseEnvelope"]
        _require(envelope["payloadType"] == "application/vnd.in-toto+json"
                 and isinstance(envelope["payload"], str) and bool(envelope["payload"])
                 and isinstance(envelope["signatures"], list) and len(envelope["signatures"]) == 1
                 and isinstance(envelope["signatures"][0]["sig"], str)
                 and bool(envelope["signatures"][0]["sig"]), ProvenanceFailure.MALFORMED_BUNDLE)
        _require(isinstance(value["verificationMaterial"], dict), ProvenanceFailure.MALFORMED_BUNDLE)
    except (KeyError, TypeError, IndexError):
        raise ProvenanceError(ProvenanceFailure.MALFORMED_BUNDLE) from None


def _environment(workspace: Path) -> dict[str, str]:
    # Deliberately constructed, not a filtered copy of os.environ. No tokens,
    # proxies, application secrets, Git config, extension or user HOME discovery.
    return {"HOME": str(workspace), "GH_CONFIG_DIR": str(workspace / "config"),
            "XDG_CONFIG_HOME": str(workspace / "config"),
            "XDG_CACHE_HOME": str(workspace / "cache"), "TMPDIR": str(workspace),
            "PATH": "/nonexistent", "GH_HOST": "github.com", "GH_PROMPT_DISABLED": "1",
            "GH_NO_UPDATE_NOTIFIER": "1", "GH_NO_EXTENSION_UPDATE_NOTIFIER": "1",
            "GH_PAGER": "cat", "NO_COLOR": "1", "TZ": "UTC", "LC_ALL": "C"}


def _run(arguments: list[str], workspace: Path, deadline: float) -> bytes:
    """Drain bounded pipes, kill the process group on every failure, reap it."""
    process = None
    try:
        process = subprocess.Popen(arguments, cwd=workspace, env=_environment(workspace),
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, shell=False, close_fds=True,
                                   start_new_session=True)
        output = bytearray()
        total = 0
        with selectors.DefaultSelector() as selector:
            for pipe in (process.stdout, process.stderr):
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                _require(remaining > 0, ProvenanceFailure.TIMEOUT)
                for key, _ in selector.select(min(remaining, 0.1)):
                    data = os.read(key.fileobj.fileno(), 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    total += len(data)
                    _require(total <= MAX_OUTPUT_BYTES, ProvenanceFailure.OVERSIZED_OUTPUT)
                    if key.fileobj is process.stdout:
                        output.extend(data)
        remaining = deadline - time.monotonic()
        _require(remaining > 0, ProvenanceFailure.TIMEOUT)
        process.wait(timeout=remaining)
        # gh does not provide stable machine-readable failure reasons. Never
        # infer cryptographic errors by matching attacker-influenced stderr.
        _require(process.returncode == 0, ProvenanceFailure.UNVERIFIABLE)
        return bytes(output)
    except subprocess.TimeoutExpired:
        raise ProvenanceError(ProvenanceFailure.TIMEOUT) from None
    except OSError:
        raise ProvenanceError(ProvenanceFailure.VERIFIER_UNAVAILABLE) from None
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            process.stdout.close()
            process.stderr.close()


def _write_private(path: Path, raw: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)


def _timestamp(value: str) -> datetime:
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise ValueError()
    return stamp.astimezone(timezone.utc)


def _evidence(raw: bytes, *, profile: TrustProfile, digest: str, name: str,
              ref: str, workflow: str, commit: str | None, lock: dict) -> VerifiedProvenance:
    result = _json(raw, ProvenanceFailure.MALFORMED_OUTPUT)
    try:
        _require(isinstance(result, list) and len(result) == 1, ProvenanceFailure.MALFORMED_OUTPUT)
        verified = result[0]["verificationResult"]
        _require(verified["mediaType"] == "application/vnd.dev.sigstore.verificationresult+json;version=0.1",
                 ProvenanceFailure.MALFORMED_OUTPUT)
        certificate = verified["signature"]["certificate"]
        statement = verified["statement"]
        _require(certificate["sourceRepositoryURI"] == REPOSITORY_URI
                 and certificate["sourceRepositoryIdentifier"] == REPOSITORY_ID
                 and certificate["sourceRepositoryOwnerURI"] == OWNER_URI
                 and certificate["sourceRepositoryOwnerIdentifier"] == OWNER_ID,
                 ProvenanceFailure.WRONG_REPOSITORY)
        identity = f"{REPOSITORY_URI}/{workflow}@{ref}"
        _require(certificate["subjectAlternativeName"] == identity
                 and certificate["buildSignerURI"] == identity
                 and certificate["buildConfigURI"] == identity, ProvenanceFailure.WRONG_WORKFLOW)
        _require(certificate["sourceRepositoryRef"] == ref, ProvenanceFailure.WRONG_SOURCE_REF)
        source = certificate["sourceRepositoryDigest"]
        _require(isinstance(source, str) and re.fullmatch(r"[a-f0-9]{40}", source) is not None
                 and certificate["buildSignerDigest"] == source
                 and certificate["buildConfigDigest"] == source
                 and (commit is None or source == commit), ProvenanceFailure.WRONG_SOURCE_COMMIT)
        _require(certificate["issuer"] == OIDC_ISSUER, ProvenanceFailure.WRONG_ISSUER)
        _require(certificate["runnerEnvironment"] == "github-hosted", ProvenanceFailure.UNTRUSTED_RUNNER)
        _require(statement["_type"] == "https://in-toto.io/Statement/v1"
                 and statement["predicateType"] == PREDICATE, ProvenanceFailure.UNSUPPORTED_PREDICATE)
        subjects = statement["subject"]
        _require(isinstance(subjects, list) and 1 <= len(subjects) <= 32,
                 ProvenanceFailure.MALFORMED_OUTPUT)
        matches = [s for s in subjects if s["name"] == name]
        _require(len(matches) == 1, ProvenanceFailure.WRONG_SUBJECT_NAME)
        _require(matches[0]["digest"] == {"sha256": digest}, ProvenanceFailure.WRONG_SUBJECT_DIGEST)
        # Signed workflow assertions must agree with the stronger certificate
        # identity. They are not independent proof of build correctness/release.
        predicate = statement["predicate"]
        definition = predicate["buildDefinition"]
        _require(definition["buildType"] == "https://actions.github.io/buildtypes/workflow/v1"
                 and definition["externalParameters"]["workflow"] == {
                     "path": workflow, "ref": ref, "repository": REPOSITORY_URI}
                 and definition["resolvedDependencies"] == [{
                     "uri": f"git+{REPOSITORY_URI}@{ref}", "digest": {"gitCommit": source}}]
                 and predicate["runDetails"]["builder"]["id"] == identity,
                 ProvenanceFailure.UNVERIFIABLE)
        invocation = certificate["runInvocationURI"]
        _require(isinstance(invocation, str) and re.fullmatch(
            re.escape(REPOSITORY_URI) + r"/actions/runs/[0-9]{1,20}/attempts/[0-9]{1,8}", invocation)
            is not None and predicate["runDetails"]["metadata"]["invocationId"] == invocation,
            ProvenanceFailure.UNVERIFIABLE)
        stamps = verified["verifiedTimestamps"]
        _require(isinstance(stamps, list) and 1 <= len(stamps) <= 8, ProvenanceFailure.UNVERIFIABLE)
        witnessed = tuple(VerifiedTimestamp(s["type"], s["uri"], _timestamp(s["timestamp"])) for s in stamps)
        _require(all(s.kind == "Tlog" and s.uri in {
            "https://rekor.sigstore.dev", "https://log2025-1.rekor.sigstore.dev"}
            for s in witnessed), ProvenanceFailure.UNVERIFIABLE)
        return VerifiedProvenance(profile, digest, matches[0]["name"], certificate["sourceRepositoryURI"],
            certificate["sourceRepositoryIdentifier"], certificate["sourceRepositoryOwnerIdentifier"],
            certificate["subjectAlternativeName"], certificate["sourceRepositoryRef"], source,
            certificate["issuer"], certificate["runnerEnvironment"], statement["predicateType"], invocation,
            witnessed, distribution.VERIFIER_VERSION, POLICY_VERSION, lock["root_id"], lock["root_sha256"],
            datetime.now(timezone.utc))
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as error:
        if isinstance(error, ProvenanceError):
            raise
        raise ProvenanceError(ProvenanceFailure.MALFORMED_OUTPUT) from None


class GithubAttestationVerifier:
    """Fixed trusted policy; callers supply bytes and expected artifact context."""

    def verify_catalogue(self, artifact: bytes, bundle: bytes, *,
                         subject_name: str = "catalogue.json") -> VerifiedProvenance:
        _require(isinstance(subject_name, str) and re.fullmatch(
            r"catalogue(?:-[0-9]{6,16})?\.json", subject_name) is not None,
            ProvenanceFailure.INVALID_CONTEXT)
        return self._verify(artifact, bundle, TrustProfile.CATALOGUE, subject_name,
                            "refs/heads/main", ".github/workflows/catalogue.yml", None, None, 4_194_304)

    def verify_package(self, artifact: bytes, bundle: bytes,
                       context: PackageArtifactContext) -> VerifiedProvenance:
        try:
            _require(isinstance(context, PackageArtifactContext)
                     and isinstance(context.connector_id, str) and len(context.connector_id) <= 100
                     and re.fullmatch(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*", context.connector_id) is not None
                     and isinstance(context.version, str) and len(context.version) <= 64
                     and isinstance(context.sha256, str) and re.fullmatch(r"[a-f0-9]{64}", context.sha256) is not None
                     and isinstance(context.source_commit, str) and re.fullmatch(r"[a-f0-9]{40}", context.source_commit) is not None,
                     ProvenanceFailure.INVALID_CONTEXT)
            Version(context.version)
        except ValueError as error:
            if isinstance(error, ProvenanceError):
                raise
            raise ProvenanceError(ProvenanceFailure.INVALID_CONTEXT) from None
        return self._verify(artifact, bundle, TrustProfile.PACKAGE,
            f"{context.connector_id}-{context.version}.tar.gz",
            f"refs/tags/{context.connector_id}-v{context.version}", ".github/workflows/release.yml",
            context.source_commit, context.sha256, 20 * 1024 * 1024)

    def _verify(self, artifact, bundle, profile, name, ref, workflow, commit, expected_digest, maximum):
        _require(isinstance(artifact, bytes) and 0 < len(artifact) <= maximum,
                 ProvenanceFailure.INVALID_ARTIFACT)
        digest = hashlib.sha256(artifact).hexdigest()
        _require(expected_digest is None or digest == expected_digest, ProvenanceFailure.WRONG_SUBJECT_DIGEST)
        _bundle(bundle)
        try:
            lock = distribution.distribution_lock()
        except (OSError, ValueError, KeyError):
            raise ProvenanceError(ProvenanceFailure.UNSUPPORTED_VERSION) from None
        try:
            roots = distribution.checked_root(lock)
        except (OSError, ValueError, KeyError):
            raise ProvenanceError(ProvenanceFailure.INVALID_ROOT) from None
        try:
            executable = distribution.checked_binary(lock)
        except (OSError, ValueError, KeyError):
            raise ProvenanceError(ProvenanceFailure.VERIFIER_UNAVAILABLE) from None
        try:
            info = TEMP_ROOT.lstat()
            _require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
                     and info.st_uid == 0 and bool(info.st_mode & stat.S_ISVTX), ProvenanceFailure.INTERNAL)
            with tempfile.TemporaryDirectory(prefix="atlas-attestation-", dir=TEMP_ROOT) as directory:
                workspace = Path(directory)
                deadline = time.monotonic() + TIMEOUT_SECONDS
                version = _run([str(executable), "--version"], workspace, deadline)
                _require(bool(version.splitlines()) and version.splitlines()[0] == b"gh version 2.102.1 (2026-10-20)",
                         ProvenanceFailure.UNSUPPORTED_VERSION)
                for filename, raw in (("artifact", artifact), ("bundle.json", bundle), ("roots.jsonl", roots)):
                    _write_private(workspace / filename, raw)
                arguments = [str(executable), "attestation", "verify", str(workspace / "artifact"),
                    "--bundle", str(workspace / "bundle.json"), "--custom-trusted-root", str(workspace / "roots.jsonl"),
                    "--repo", REPOSITORY, "--hostname", "github.com", "--cert-identity",
                    f"{REPOSITORY_URI}/{workflow}@{ref}", "--cert-oidc-issuer", OIDC_ISSUER,
                    "--source-ref", ref, "--deny-self-hosted-runners", "--predicate-type", PREDICATE,
                    "--digest-alg", "sha256", "--format", "json"]
                if commit is not None:
                    arguments.extend(["--source-digest", commit, "--signer-digest", commit])
                raw = _run(arguments, workspace, deadline)
                return _evidence(raw, profile=profile, digest=digest, name=name, ref=ref,
                                 workflow=workflow, commit=commit, lock=lock)
        except (OSError, IndexError):
            raise ProvenanceError(ProvenanceFailure.INTERNAL) from None
