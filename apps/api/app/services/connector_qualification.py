"""Local installation-authority permission for one unqualified test package.

This is never a catalogue source or a source-version qualification assertion.
The protected store and explicit process configuration are both required.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time

from app.services.connector_contracts import ConnectorPackageError, strict_json, validate_manifest
from app.services.connector_verification import VerificationEvidence, verify_digest

GRANT_FILE = ".qualification.json"
FIELDS = {"schema_version", "purpose", "store_path", "connector_id", "version",
          "bundle_digest", "manifest_digest", "atlas_commit", "connector_commit", "expires_at"}


def manifest_digest(manifest):
    return "sha256:" + hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def require_test_store(root):
    root = Path(root)
    if (os.getenv("ATLAS_CONNECTOR_QUALIFICATION_ENABLED") != "1"
            or not root.is_absolute() or ".." in root.parts
            or root == Path("/var/lib/atlas-connectors")):
        raise ConnectorPackageError("operator_qualification_disabled")
    return root


def authorize(root, manifest, evidence=None):
    from app.services.connector_store import _read_regular
    root = require_test_store(root)
    validate_manifest(manifest)
    path = root / GRANT_FILE
    raw = _read_regular(path, 4096)
    info, parent = path.stat(), root.stat()
    grant = strict_json(raw, maximum=4096)
    if (info.st_mode & 0o222 or parent.st_mode & 0o022 or info.st_uid != parent.st_uid
            or not isinstance(grant, dict) or set(grant) != FIELDS
            or grant["schema_version"] != "1.0" or grant["purpose"] != "operator-live-qualification"
            or grant["store_path"] != str(root)
            or grant["atlas_commit"] != os.getenv("ATLAS_BUILD_ID")
            or type(grant["expires_at"]) is not int
            or not time.time() < grant["expires_at"] <= time.time() + 7 * 86400
            or any(not isinstance(grant[k], str) or not re.fullmatch(r"[a-f0-9]{40}", grant[k])
                   for k in ("atlas_commit", "connector_commit"))
            or manifest["source_versions"]["qualification"] != "unqualified"
            or manifest["source_versions"]["qualified_versions"]
            or "-" not in manifest["version"]
            or any(grant[key] != value for key, value in {
                "connector_id": manifest["id"], "version": manifest["version"],
                "bundle_digest": manifest["distribution"]["bundle_digest"],
                "manifest_digest": manifest_digest(manifest),
                "connector_commit": manifest["distribution"]["provenance"].get("source_commit")}.items())):
        raise ConnectorPackageError("operator_qualification_not_authorized")
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    if evidence is not None and (evidence.get("method") != "operator-qualification"
            or evidence.get("qualification_digest") != digest
            or evidence.get("source_commit") != grant["connector_commit"]):
        raise ConnectorPackageError("operator_qualification_receipt_mismatch")
    return grant, digest


class OperatorQualificationVerifier:
    def __init__(self, root):
        self.root = root

    def verify(self, archive, package):
        verify_digest(archive, package.bundle_digest)
        if package.source != "operator-qualification" or package.manifest["publisher"]["id"] != "atlas-official":
            raise ConnectorPackageError("package_source_not_approved")
        grant, digest = authorize(self.root, package.manifest)
        return VerificationEvidence("operator-qualification", package.bundle_digest, "atlas-official",
                                    source_commit=grant["connector_commit"], qualification_digest=digest)
