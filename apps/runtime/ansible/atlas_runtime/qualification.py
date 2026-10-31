"""Independent runtime check of a protected, expiring operator authorization."""
import hashlib
import json
import os
from pathlib import Path
import re
import time

from atlas_connector_sdk.contracts import strict_json, validate_manifest


def check(store, manifest, evidence, read_regular):
    if (store / ".local-instance.json").exists() or evidence.get("method") == "operator-local-release":
        from .local_release import check as check_local_release
        check_local_release(store, manifest, evidence, read_regular)
        return
    if evidence.get("method") != "operator-qualification":
        # Retain inspection compatibility with historical minimal I1 receipts;
        # execution still requires the fixed complete entry-point contracts.
        qualification = manifest.get("source_versions", {}).get("qualification")
        if qualification is not None:
            validate_manifest(manifest)
            probe_only = manifest["manifest_version"] == "1.1" and manifest["capabilities"]["discover"] is False
            if qualification == "example" or not probe_only and qualification != "qualified":
                raise ValueError("package_not_qualified")
        return
    validate_manifest(manifest)
    qualification = manifest["source_versions"]["qualification"]
    if (os.getenv("ATLAS_CONNECTOR_QUALIFICATION_ENABLED") != "1"
            or not store.is_absolute() or ".." in store.parts
            or store == Path("/var/lib/atlas-connectors")):
        raise ValueError("operator_qualification_disabled")
    path = store / ".qualification.json"
    raw = read_regular(path, 4096)
    grant = strict_json(raw, maximum=4096)
    info, parent = path.stat(), store.stat()
    fields = {"schema_version", "purpose", "store_path", "connector_id", "version",
              "bundle_digest", "manifest_digest", "atlas_commit", "connector_commit", "expires_at"}
    digest = "sha256:" + hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if (info.st_mode & 0o222 or parent.st_mode & 0o022 or info.st_uid != parent.st_uid
            or not isinstance(grant, dict) or set(grant) != fields
            or grant["schema_version"] != "1.0" or grant["purpose"] != "operator-live-qualification"
            or grant["store_path"] != str(store)
            or grant["atlas_commit"] != os.getenv("ATLAS_BUILD_ID")
            or type(grant["expires_at"]) is not int
            or not time.time() < grant["expires_at"] <= time.time() + 7 * 86400
            or any(not isinstance(grant[k], str) or not re.fullmatch(r"[a-f0-9]{40}", grant[k])
                   for k in ("atlas_commit", "connector_commit"))
            or qualification != "unqualified" or manifest["source_versions"]["qualified_versions"]
            or "-" not in manifest["version"]
            or any(grant[k] != value for k, value in {
                "connector_id": manifest["id"], "version": manifest["version"],
                "bundle_digest": manifest["distribution"]["bundle_digest"],
                "manifest_digest": digest,
                "connector_commit": manifest["distribution"]["provenance"].get("source_commit")}.items())
            or evidence.get("source_commit") != grant["connector_commit"]
            or evidence.get("qualification_digest") != "sha256:" + hashlib.sha256(raw).hexdigest()):
        raise ValueError("operator_qualification_not_authorized")
