"""Protected local operator authority; never package-signing or catalogue trust.

The public binding is provisioned by root outside the package store. Its private
key is available only to the operator, never API, worker or runtime processes.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import time
import uuid

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.models import SystemSetting
from app.services.connector_contracts import ConnectorPackageError, strict_json
from app.services.connector_store import _read_regular, _write

BINDING = Path("/etc/atlas-local-release/instance.json")
PRIVATE_KEY = Path("/etc/atlas-local-release-private/operator.key")
DEPLOYMENT = Path("/etc/atlas-local-release-deployment/identity.json")
DATABASE_KEY = "connector_local_release_instance"
DIRECTORY = ".local-acceptance"
ISOLATION_CHECKS = {"database", "redis", "runtime", "worker", "credentials", "storage", "production_excluded"}
MAX_LIFETIME = 48 * 3600  # maximum execution lease, never artifact evidence
APPROVAL_LIFETIME = 10 * 60


def canonical(value):
    from datetime import datetime, date
    def encode(item):
        if isinstance(item, (datetime, date, uuid.UUID)):
            return str(item)
        raise TypeError("invalid_local_release_value")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, default=encode).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def require(condition, code="local_release_not_authorized"):
    if not condition:
        raise ConnectorPackageError(code)


def operator():
    # The application UID and shell access are explicitly insufficient.
    require(os.geteuid() == 0, "local_release_requires_root_operator")


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish(path, raw):
    _write(path, raw)
    sync_directory(path.parent)


def protected(path, maximum=256 * 1024, *, private=False):
    raw = _read_regular(path, maximum)
    for item in (path, *path.parents):
        info = item.stat()
        sticky_root = item != path and info.st_uid == 0 and info.st_mode & stat.S_ISVTX
        require(info.st_uid == 0 and (not info.st_mode & 0o022 or sticky_root), "local_release_unprotected_authority")
    mode = path.stat().st_mode
    require(not mode & (0o077 if private else 0o222), "local_release_unprotected_authority")
    return raw


def database_identity(db):
    # No database credentials or connection URL are retained or emitted.
    return dict(db.execute(text("SELECT current_database() AS name, oid::text AS oid, "
        "(SELECT system_identifier::text FROM pg_control_system()) AS cluster_id "
        "FROM pg_database WHERE datname=current_database()")).mappings().one())


def resource_identity(path):
    from app.services.connector_store import _without_links
    _without_links(path)
    info = path.stat()
    require(info.st_uid == 0 and not info.st_mode & 0o022, "local_release_unprotected_resource")
    return {"path": str(path), "device": info.st_dev, "inode": info.st_ino}


def deployment_identity():
    value = strict_json(protected(DEPLOYMENT))
    require(isinstance(value, dict) and set(value) == {"schema", "deployment_id", "name"}
            and value["schema"] == 1 and str(uuid.UUID(value["deployment_id"])) == value["deployment_id"]
            and isinstance(value["name"], str) and 1 <= len(value["name"]) <= 100,
            "local_release_invalid_deployment")
    return value


def inspect_resources(db, root):
    """Fresh independent observations; the human must still inspect isolation."""
    operator()
    return {"database": database_identity(db), "deployment": deployment_identity(),
            "storage": {"store": resource_identity(root), "public": resource_identity(BINDING.parent),
                        "private": resource_identity(PRIVATE_KEY.parent)}}


def binding(root):
    require(root.is_absolute() and ".." not in root.parts and root != Path("/var/lib/atlas-connectors"), "local_release_production_store")
    value = strict_json(protected(BINDING), maximum=256 * 1024)
    require(isinstance(value, dict) and set(value) == {"schema", "purpose", "instance_id", "store_id", "store_path", "public_key", "database", "atlas_commit", "isolation"})
    require(value["schema"] == 1 and value["purpose"] == "isolated-local-release-acceptance"
            and value["store_path"] == str(root) and value["atlas_commit"] == os.getenv("ATLAS_BUILD_ID"))
    marker = strict_json(protected(root / ".local-instance.json"))
    require(marker == {"instance_id": value["instance_id"], "store_id": value["store_id"]}, "local_release_instance_mismatch")
    require(root.stat().st_uid == 0 and not root.stat().st_mode & 0o022, "local_release_unprotected_store")
    resources = value["isolation"]["resources"]
    require(deployment_identity() == resources["deployment"]
            and resource_identity(root) == resources["storage"]["store"]
            and resource_identity(BINDING.parent) == resources["storage"]["public"], "local_release_resource_substitution")
    require(set(value["isolation"]["checks"]) == ISOLATION_CHECKS
            and all(v is True for v in value["isolation"]["checks"].values()))
    return value


def check_database(db, bound):
    marker = db.scalar(select(SystemSetting).where(SystemSetting.key == DATABASE_KEY).execution_options(populate_existing=True))
    require(marker is not None and marker.value_ == {"instance_id": bound["instance_id"], "binding_digest": digest(bound)}
            and database_identity(db) == bound["database"], "local_release_database_mismatch")


def check_isolation(isolation, deployment=None, resources=None):
    require(isinstance(isolation, dict) and set(isolation) == {"deployment", "checked_at", "checks", "resources"}
            and isinstance(isolation["deployment"], str) and 1 <= len(isolation["deployment"]) <= 100
            and (deployment is None or isolation["deployment"] == deployment)
            and type(isolation["checked_at"]) is int and 0 <= time.time() - isolation["checked_at"] < 3600
            and isinstance(isolation["checks"], dict) and set(isolation["checks"]) == ISOLATION_CHECKS
            and all(v is True for v in isolation["checks"].values())
            and isinstance(isolation["resources"], dict)
            and set(isolation["resources"]) == {"database", "deployment", "storage"}
            and (resources is None or isolation["resources"] == resources), "local_release_isolation_required")


def provision(db, root, isolation):
    """One-time root enrollment after explicit external infrastructure inspection."""
    operator()
    from app.services.connector_store import _without_links
    for path in (root, BINDING, PRIVATE_KEY):
        _without_links(path)
    require(root.is_absolute() and ".." not in root.parts and root != Path("/var/lib/atlas-connectors"), "local_release_production_store")
    observed = inspect_resources(db, root)
    check_isolation(isolation, observed["deployment"]["name"], observed)
    require(not BINDING.exists() and not PRIVATE_KEY.exists()
            and db.scalar(select(SystemSetting).where(SystemSetting.key == DATABASE_KEY)) is None,
            "local_release_instance_already_bound")
    require(not root.exists() or not any(root.iterdir()), "local_release_requires_empty_store")
    import re
    require(re.fullmatch(r"[a-f0-9]{40}", os.getenv("ATLAS_BUILD_ID", "")) is not None, "local_release_exact_build_required")
    key = Ed25519PrivateKey.generate()
    bound = {"schema": 1, "purpose": "isolated-local-release-acceptance", "instance_id": str(uuid.uuid4()),
             "store_id": str(uuid.uuid4()), "store_path": str(root), "database": observed["database"],
             "atlas_commit": os.environ["ATLAS_BUILD_ID"], "isolation": isolation,
             "public_key": base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()}
    for directory in (root, BINDING.parent, PRIVATE_KEY.parent):
        directory.mkdir(parents=True, exist_ok=True, mode=0o755)
        require(directory.stat().st_uid == 0 and not directory.stat().st_mode & 0o022)
    PRIVATE_KEY.parent.chmod(0o700)
    publish(PRIVATE_KEY, key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))
    PRIVATE_KEY.chmod(0o400)
    publish(root / ".local-instance.json", canonical({"instance_id": bound["instance_id"], "store_id": bound["store_id"]}))
    publish(BINDING, canonical(bound))
    db.add(SystemSetting(key=DATABASE_KEY, value_={"instance_id": bound["instance_id"], "binding_digest": digest(bound)},
                         description="Root-bound isolated local Connector release instance; never catalogue eligibility", sensitive=False))
    db.flush()
    return bound


def signed(payload, bound):
    operator()
    key = Ed25519PrivateKey.from_private_bytes(protected(PRIVATE_KEY, 32, private=True))
    require(base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode() == bound["public_key"])
    return {"payload": payload, "signature": base64.b64encode(key.sign(canonical(payload))).decode()}


def authenticated(raw, bound):
    value = strict_json(raw)
    require(isinstance(value, dict) and set(value) == {"payload", "signature"})
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(bound["public_key"], validate=True)).verify(
            base64.b64decode(value["signature"], validate=True), canonical(value["payload"]))
    except (ValueError, TypeError, InvalidSignature):
        raise ConnectorPackageError("local_release_invalid_authorization") from None
    return value["payload"]


def authorize(root, manifest, evidence):
    bound = binding(root)
    require(isinstance(evidence, dict) and evidence.get("method") == "operator-local-release")
    identifier = evidence.get("authorization_id")
    try:
        require(str(uuid.UUID(identifier)) == identifier)
    except (ValueError, TypeError, AttributeError):
        raise ConnectorPackageError("local_release_invalid_authorization") from None
    directory = root / DIRECTORY
    require(not (directory / (identifier + ".revoked.json")).exists()
            and not (directory / (identifier + ".revocation-pending")).exists(), "local_release_revoked")
    raw = protected(directory / (identifier + ".json"))
    payload = authenticated(raw, bound)
    require(hashlib.sha256(raw).hexdigest() == evidence.get("authorization_digest"))
    require(payload.get("binding_digest") == digest(bound) and payload.get("authorization_id") == identifier
            and payload.get("manifest_digest") == digest(manifest)
            and payload.get("connector_id") == manifest["id"] and payload.get("version") == manifest["version"]
            and payload.get("bundle_digest") == manifest["distribution"]["bundle_digest"]
            and payload.get("purpose") == "artifact-staging"
            and type(payload.get("issued_at")) is int and payload["issued_at"] <= time.time(),
            "local_release_authorization_mismatch")
    require(payload["provenance"] == evidence.get("provenance") and payload["release"] == evidence.get("release"))
    return bound, payload


def execution_path(root, connector_id):
    from app.services.connector_store import _identity
    _identity(connector_id, "0.0.0", "sha256:" + "0" * 64)
    return root / DIRECTORY / "execution" / (connector_id + ".json")


def fence_execution(root, connector_id):
    """Deny durably BEFORE changing PostgreSQL active identity. Root/store lock held."""
    operator()
    path = execution_path(root, connector_id)
    if path.exists():
        path.unlink()
        sync_directory(path.parent)


def execution(root, manifest, evidence, activation):
    bound, _ = authorize(root, manifest, evidence)
    require(isinstance(activation, dict), "local_release_activation_required")
    lease = authenticated(protected(execution_path(root, manifest["id"])), bound)
    require(lease.get("purpose") == "manual-execution" and lease.get("activation") == activation
            and activation.get("binding_digest") == digest(bound)
            and lease.get("binding_digest") == digest(bound)
            and lease.get("artifact_digest") == digest(evidence)
            and lease.get("connector_id") == manifest["id"] and lease.get("version") == manifest["version"]
            and lease.get("bundle_digest") == manifest["distribution"]["bundle_digest"]
            and type(lease.get("issued_at")) is int and type(lease.get("expires_at")) is int
            and all(lease.get(key) == activation.get(key) for key in ("lease_id", "issued_at", "expires_at"))
            and lease["issued_at"] <= time.time() < lease["expires_at"] <= lease["issued_at"] + MAX_LIFETIME,
            "local_release_execution_denied")
    return lease


def execution_context(record):
    activation = record.verification_evidence.get("local_activation")
    require(isinstance(activation, dict), "local_release_activation_required")
    return {"activation": activation, "trigger": "manual"}


def artifact_evidence(evidence):
    return {key: value for key, value in evidence.items() if key != "local_activation"}


def effective_status(record, *, root=None, db=None):
    if record.verification_evidence.get("method") != "operator-local-release":
        return {"status": "catalogue_policy"}
    from app.services.connector_lifecycle import package_store
    root = root or package_store().root
    value = {"status": "denied", "manual_only": True, "activation": record.verification_evidence.get("local_activation")}
    try:
        if db is not None:
            check_database(db, binding(root))
        activation = value["activation"]
        if not isinstance(activation, dict):
            return {**value, "status": "activation_required"}
        value.update(expires_at=activation["expires_at"], lease_id=activation["lease_id"])
        if any((root / DIRECTORY / (record.verification_evidence["authorization_id"] + suffix)).exists()
               for suffix in (".revoked.json", ".revocation-pending")):
            return {**value, "status": "revoked"}
        if time.time() >= activation["expires_at"]:
            return {**value, "status": "expired"}
        if not execution_path(root, record.connector_id).exists():
            return {**value, "status": "recovery_required"}
        directory = root / record.connector_id / record.version / record.bundle_digest
        manifest = strict_json(_read_regular(directory / "manifest.json", 256 * 1024))
        lease = execution(root, manifest, artifact_evidence(record.verification_evidence), value["activation"])
        value.update(status="authorized", expires_at=lease["expires_at"], lease_id=lease["lease_id"])
    except (SQLAlchemyError, OSError, ValueError, KeyError, TypeError):
        pass
    return value
