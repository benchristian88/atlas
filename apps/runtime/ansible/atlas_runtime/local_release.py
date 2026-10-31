"""Runtime-owned offline validation of local operator authority (not Sigstore roots)."""
import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import time
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from atlas_connector_sdk.contracts import strict_json, validate_manifest

BINDING = Path("/etc/atlas-local-release/instance.json")
DEPLOYMENT = Path("/etc/atlas-local-release-deployment/identity.json")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def check(store, manifest, evidence, read_regular):
    try:
        _check(store, manifest, evidence, read_regular)
    except (InvalidSignature, KeyError, ValueError, TypeError, AttributeError):
        raise ValueError("local_release_not_authorized") from None


def _check(store, manifest, evidence, read_regular):
    def require(condition):
        if not condition:
            raise ValueError("local_release_not_authorized")

    def protected(path):
        raw = read_regular(path, 256 * 1024)
        for item in (path, *path.parents):
            info = item.stat()
            sticky_root = item != path and info.st_uid == 0 and info.st_mode & stat.S_ISVTX
            require(info.st_uid == 0 and (not info.st_mode & 0o022 or sticky_root))
        require(not path.stat().st_mode & 0o222)
        return raw

    validate_manifest(manifest)
    require(store.is_absolute() and ".." not in store.parts and store != Path("/var/lib/atlas-connectors"))
    bound = strict_json(protected(BINDING), maximum=256 * 1024)
    require(isinstance(bound, dict) and set(bound) == {"schema", "purpose", "instance_id", "store_id", "store_path", "public_key", "database", "atlas_commit", "isolation"})
    require(bound["schema"] == 1 and bound["purpose"] == "isolated-local-release-acceptance"
            and bound["store_path"] == str(store) and bound["atlas_commit"] == os.getenv("ATLAS_BUILD_ID"))
    require(strict_json(protected(store / ".local-instance.json")) == {"instance_id": bound["instance_id"], "store_id": bound["store_id"]})
    require(store.stat().st_uid == 0 and not store.stat().st_mode & 0o022)
    resources = bound["isolation"]["resources"]
    require(strict_json(protected(DEPLOYMENT)) == resources["deployment"])
    for name, path in (("store", store), ("public", BINDING.parent)):
        info = path.stat()
        require(resources["storage"][name] == {"path": str(path), "device": info.st_dev, "inode": info.st_ino})
    require(set(bound["isolation"]["checks"]) == {"database", "redis", "runtime", "worker", "credentials", "storage", "production_excluded"}
            and all(v is True for v in bound["isolation"]["checks"].values()))
    require(evidence.get("method") == "operator-local-release")
    identifier = evidence.get("authorization_id")
    require(str(uuid.UUID(identifier)) == identifier)
    directory = store / ".local-acceptance"
    require(not (directory / (identifier + ".revoked.json")).exists()
            and not (directory / (identifier + ".revocation-pending")).exists())
    raw = protected(directory / (identifier + ".json"))
    grant = strict_json(raw, maximum=256 * 1024)
    require(isinstance(grant, dict) and set(grant) == {"payload", "signature"})
    Ed25519PublicKey.from_public_bytes(base64.b64decode(bound["public_key"], validate=True)).verify(
        base64.b64decode(grant["signature"], validate=True), canonical(grant["payload"]))
    value = grant["payload"]
    require(hashlib.sha256(raw).hexdigest() == evidence.get("authorization_digest"))
    require(value.get("binding_digest") == digest(bound) and value.get("authorization_id") == identifier
            and value.get("manifest_digest") == digest(manifest)
            and value.get("connector_id") == manifest["id"] and value.get("version") == manifest["version"]
            and value.get("bundle_digest") == manifest["distribution"]["bundle_digest"]
            and value.get("purpose") == "artifact-staging"
            and type(value.get("issued_at")) is int and value["issued_at"] <= time.time()
            and value["provenance"] == evidence.get("provenance") and value["release"] == evidence.get("release"))
    return bound, protected


def check_execution(store, manifest, evidence, context, read_regular):
    """Independent offline runtime admission, separate from safe artifact inspection."""
    try:
        bound, protected = _check(store, manifest, evidence, read_regular)
        if (not isinstance(context, dict) or set(context) != {"activation", "trigger"}
                or context["trigger"] != "manual" or not isinstance(context["activation"], dict)):
            raise ValueError()
        raw = protected(store / ".local-acceptance" / "execution" / (manifest["id"] + ".json"))
        signed = strict_json(raw, maximum=256 * 1024)
        if set(signed) != {"payload", "signature"}:
            raise ValueError()
        Ed25519PublicKey.from_public_bytes(base64.b64decode(bound["public_key"], validate=True)).verify(
            base64.b64decode(signed["signature"], validate=True), canonical(signed["payload"]))
        lease = signed["payload"]
        activation = context["activation"]
        if (lease.get("purpose") != "manual-execution" or lease.get("activation") != activation
                or activation.get("binding_digest") != digest(bound) or lease.get("binding_digest") != digest(bound)
                or lease.get("artifact_digest") != digest(evidence)
                or lease.get("connector_id") != manifest["id"] or lease.get("version") != manifest["version"]
                or lease.get("bundle_digest") != manifest["distribution"]["bundle_digest"]
                or type(lease.get("issued_at")) is not int or type(lease.get("expires_at")) is not int
                or not lease["issued_at"] <= time.time() < lease["expires_at"] <= lease["issued_at"] + 48 * 3600
                or any(lease.get(key) != activation.get(key) for key in ("lease_id", "issued_at", "expires_at"))):
            raise ValueError()
    except (OSError, InvalidSignature, KeyError, ValueError, TypeError, AttributeError):
        raise ValueError("package_unavailable") from None
