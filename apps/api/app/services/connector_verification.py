"""Digest verification and strict approved-provenance policy boundaries."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Protocol

from app.services.connector_contracts import ConnectorPackageError


class VerificationError(ConnectorPackageError):
    pass


@dataclass(frozen=True)
class VerificationEvidence:
    method: str
    bundle_digest: str
    publisher_id: str
    repository: str | None = None
    workflow: str | None = None
    source_commit: str | None = None
    release_identity: str | None = None

    def safe_metadata(self) -> dict:
        return {key: value for key, value in self.__dict__.items() if value is not None}


class BundleVerifier(Protocol):
    def verify(self, archive: bytes, package) -> VerificationEvidence: ...


def verify_digest(archive: bytes, expected: str) -> str:
    if not isinstance(expected, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", expected):
        raise VerificationError("invalid_bundle_digest")
    digest = "sha256:" + hashlib.sha256(archive).hexdigest()
    if digest != expected:
        raise VerificationError("bundle_digest_mismatch")
    return digest


class GithubSigstoreVerifier:
    """Fail closed until a reviewed verifier and official identity are packaged.

    A manifest claim is never authenticated provenance. The future adapter must
    enforce the configured repository AND signer workflow, source commit, SLSA
    predicate and issuer against authenticated certificate claims, and validate
    the Sigstore chain/transparency timestamps with a reviewed pinned trust root.
    No shell/gh lookup, network fallback, or skip-verification switch exists.
    """

    def verify(self, archive: bytes, package) -> VerificationEvidence:
        verify_digest(archive, package.bundle_digest)
        raise VerificationError("official_provenance_verifier_unavailable")


class BootstrapReleaseVerifier:
    """Exact allowlist inherited from a trusted packaged Atlas release snapshot.

    The allowlist is supplied by the fixed, release-packaged catalogue loader,
    never by request data or the bundle's self-asserted provenance. No executable
    entries are shipped in I1; the boundary is exercised with inert test bundles.
    """

    def __init__(self, approved: frozenset[tuple[str, str, str]], release_identity: str):
        self.approved = approved
        self.release_identity = release_identity

    def verify(self, archive: bytes, package) -> VerificationEvidence:
        digest = verify_digest(archive, package.bundle_digest)
        if (package.source != "bootstrap" or not package.package_available
                or (package.connector_id, package.version, digest) not in self.approved
                or package.manifest["publisher"]["id"] != "atlas-official"):
            raise VerificationError("bootstrap_package_not_approved")
        return VerificationEvidence("atlas-release-bootstrap", digest, "atlas-official",
                                    release_identity=self.release_identity)


class OfficialBundleVerifier:
    def __init__(self, bootstrap: BootstrapReleaseVerifier | None = None,
                 github: BundleVerifier | None = None):
        self.bootstrap = bootstrap
        self.github = github or GithubSigstoreVerifier()

    def verify(self, archive: bytes, package) -> VerificationEvidence:
        verify_digest(archive, package.bundle_digest)
        if package.manifest["publisher"]["id"] != "atlas-official":
            raise VerificationError("publisher_not_approved")
        if package.source == "bootstrap":
            if self.bootstrap is None:
                raise VerificationError("bootstrap_verifier_unavailable")
            return self.bootstrap.verify(archive, package)
        if package.source == "official":
            if package.manifest["distribution"]["provenance"]["method"] != "github-artifact-attestation-sigstore":
                raise VerificationError("official_provenance_required")
            return self.github.verify(archive, package)
        raise VerificationError("package_source_not_approved")
