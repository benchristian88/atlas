"""Crash-safe, irreversible local revocation and explicit root evidence repair."""
import hashlib
import os
import stat
import time
import uuid

from app.services import local_release_authority as authority
from app.services.connector_store import PackageStore, _read_regular, _without_links


def paths(root, identifier):
    authority.require(str(uuid.UUID(identifier)) == identifier, "local_release_invalid_authorization")
    directory = root / authority.DIRECTORY
    return directory / (identifier + ".revoked.json"), directory / (identifier + ".revocation-pending")


def verified(root, identifier, bound):
    path, _ = paths(root, identifier)
    value = authority.authenticated(authority.protected(path), bound)
    authority.require(value.get("artifact_id") == identifier and value.get("binding_digest") == authority.digest(bound)
        and type(value.get("revoked_at")) is int and value["revoked_at"] <= time.time(), "local_release_invalid_revocation")
    return value


def atomic_publish(path, raw, *, replace=False):
    """Protected complete data, fsync, atomic no-clobber link (or reviewed replace)."""
    _without_links(path)
    temporary = path.parent / ("." + str(uuid.uuid4()) + ".revocation-tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path, follow_symlinks=False)
        authority.sync_directory(path.parent)
    finally:
        # A real crash can retain a protected temporary. It is never authority.
        if temporary.exists():
            temporary.unlink()
        authority.sync_directory(path.parent)


def deny(root, identifier, grant):
    path, pending = paths(root, identifier)
    _without_links(pending)
    if not pending.exists():
        pending.mkdir(mode=0o555)
    authority.require(pending.is_dir() and pending.stat().st_uid == 0 and not pending.stat().st_mode & 0o222,
                      "local_release_unprotected_authority")
    # The durable intent is checked by API/runtime even if no signed tombstone
    # was published. Neither lease recovery nor renewal can undo it.
    authority.sync_directory(path.parent)
    authority.fence_execution(root, grant["connector_id"])


def publish(root, identifier, *, corrupt_sha256=None):
    authority.operator()
    bound = authority.binding(root)
    path, _ = paths(root, identifier)
    with PackageStore(root)._lock():
        grant = authority.authenticated(authority.protected(path.parent / (identifier + ".json")), bound)
        authority.require(grant.get("authorization_id") == identifier
            and grant.get("binding_digest") == authority.digest(bound) and grant.get("purpose") == "artifact-staging",
            "local_release_invalid_authorization")
        deny(root, identifier, grant)
        recovered = None
        if path.exists():
            try:
                verified(root, identifier, bound)
                return  # Idempotent; never rewrite a valid tombstone.
            except (OSError, ValueError, KeyError, TypeError):
                authority.require(corrupt_sha256 is not None, "local_release_corrupt_revocation_recovery_required")
            raw = _read_regular(path, 256 * 1024)
            info = path.stat()
            authority.require(info.st_uid == 0 and stat.S_ISREG(info.st_mode) and not info.st_mode & 0o022,
                              "local_release_unprotected_authority")
            digest = hashlib.sha256(raw).hexdigest()
            authority.require(digest == corrupt_sha256, "local_release_corrupt_evidence_changed")
            retained = path.parent / (identifier + "." + str(uuid.uuid4()) + ".corrupt-evidence")
            # Copy exact bytes to immutable forensic evidence before replacement.
            atomic_publish(retained, raw)
            recovered = {"path": retained.name, "sha256": digest, "mode": stat.S_IMODE(info.st_mode)}
        else:
            authority.require(corrupt_sha256 is None, "local_release_corrupt_evidence_missing")
        value = {"artifact_id": identifier, "binding_digest": authority.digest(bound), "revoked_at": int(time.time())}
        if recovered is not None:
            value["recovered_evidence"] = recovered
        atomic_publish(path, authority.canonical(authority.signed(value, bound)), replace=recovered is not None)
        verified(root, identifier, bound)
