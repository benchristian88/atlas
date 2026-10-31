"""Root-authorized handoff to ordinary bundled management, never local promotion.

The signed persisted handoff only permits the normal globally authorized install
route to replace one exact revoked activation in one exact ordinary store.
Consumption, replacement and both application audits share a DB transaction.
"""
from pathlib import Path
import time
import uuid

from sqlalchemy import select

from app.audit import add_audit_event
from app.models import AuditEvent, InstalledConnectorPackage, SystemSetting, Integration, IntegrationSecret, ConnectorMapping
from app.services import connector_lifecycle as lifecycle, local_release_authority as authority
from app.services import connector_release_acceptance as acceptance
from app.services.connector_contracts import strict_json
from app.services.connector_store import MAX_ARCHIVE_BYTES, PackageStore, _read_regular, _without_links
from app.services.local_release_revocation import verified

PREFIX = "connector_local_release_restoration:"


def ordinary_store(root):
    _without_links(root)
    info = root.stat()
    authority.require(root.is_absolute() and ".." not in root.parts and root.is_dir() and not info.st_mode & 0o022
        and not (root / ".local-instance.json").exists() and not (root / ".qualification.json").exists(),
        "local_release_ordinary_store_required")
    return {"path": str(root), "device": info.st_dev, "inode": info.st_ino, "owner": info.st_uid}


def revoked_record(db, root, active, *, reverify_release=False):
    bound = authority.binding(root)
    authority.check_database(db, bound)
    authority.require(active is not None and active.verification_evidence.get("method") == "operator-local-release",
                      "local_release_activation_required")
    evidence = authority.artifact_evidence(active.verification_evidence)
    identifier = evidence["authorization_id"]
    tombstone = verified(root, identifier, bound)
    directory = PackageStore(root)._path(active.connector_id, active.version, "sha256:" + active.bundle_digest)
    manifest = strict_json(authority.protected(directory / "manifest.json"))
    receipt = strict_json(authority.protected(directory / "verification.json", 512 * 1024), maximum=512 * 1024)
    raw = authority.protected(root / authority.DIRECTORY / (identifier + ".json"))
    grant = authority.authenticated(raw, bound)
    import hashlib
    authority.require(receipt["verification"] == evidence and hashlib.sha256(raw).hexdigest() == evidence["authorization_digest"]
        and grant.get("authorization_id") == identifier and grant.get("binding_digest") == authority.digest(bound)
        and grant.get("purpose") == "artifact-staging" and grant.get("connector_id") == active.connector_id
        and grant.get("version") == active.version and grant.get("bundle_digest") == "sha256:" + active.bundle_digest
        and grant.get("manifest_digest") == authority.digest(manifest)
        and grant.get("provenance") == evidence["provenance"] and grant.get("release") == evidence["release"],
        "local_release_active_authorization_mismatch")
    if reverify_release:
        # Original public-download evidence is intentionally root-only (0700).
        # Root reauthenticates it before signing the handoff. Application
        # consumers authenticate that handoff plus the public grant/receipt;
        # they must never gain access to the root evidence directory or key.
        authority.operator()
        _, identity = acceptance.load_result(root / authority.DIRECTORY / identifier)
        authority.require((identity.connector_id, identity.version, identity.sha256) ==
            (active.connector_id, active.version, active.bundle_digest), "local_release_active_authorization_mismatch")
    archive = _read_regular(directory / "bundle.tar.gz", MAX_ARCHIVE_BYTES)
    from app.services.connector_verification import verify_digest
    verify_digest(archive, "sha256:" + active.bundle_digest)
    authority.require(PackageStore(root)._extract(archive, None, manifest) == receipt["files"],
                      "local_release_active_authorization_mismatch")
    return bound, tombstone


def replacement(root, connector_id, version, digest):
    from app.services.connector_catalogue import catalogue
    package = catalogue.get(connector_id, version)
    authority.require(package.source == "bootstrap" and package.package_available
        and package.bundle_digest == "sha256:" + digest, "local_release_bundled_replacement_required")
    # Uses the unchanged release-packaged catalogue verifier and exact allowlist.
    stored = PackageStore(root).install(package, catalogue.verifier())
    return stored


def dependent_state(db, connector_id):
    rows = list(db.scalars(select(Integration).where(Integration.connector_id == connector_id,
        Integration.retired_at.is_(None)).order_by(Integration.id)))
    secrets = list(db.scalars(select(IntegrationSecret).where(IntegrationSecret.integration_id.in_([r.id for r in rows]))
        .order_by(IntegrationSecret.id)))
    mappings = list(db.scalars(select(ConnectorMapping).where(ConnectorMapping.connector_id == connector_id)
        .order_by(ConnectorMapping.id)))
    return authority.digest([[acceptance.snapshot(row) for row in group] for group in (rows, secrets, mappings)])


def apply_scopes(db, connector_id, manifest, scopes):
    if scopes is not None:
        rows = list(db.scalars(select(Integration).where(Integration.connector_id == connector_id,
            Integration.retired_at.is_(None))))
        acceptance.apply_choices(db, manifest, [], scopes, rows)


def _plan(db, original, target, connector_id, version, digest, *, scopes=None):
    acceptance.lock_review_state(db, connector_id)
    db.expire_all()
    active = db.get(InstalledConnectorPackage, connector_id)
    bound, tombstone = revoked_record(db, original, active, reverify_release=True)
    authority.require(original != target, "local_release_ordinary_store_required")
    target_identity = ordinary_store(target)
    authority.require(not lifecycle.active_connector_runs(db, connector_id), "local_release_active_runs")
    authority.require(db.scalar(select(Integration.id).where(Integration.connector_id.is_(None),
        Integration.plugin_id == connector_id).limit(1)) is None, "local_release_legacy_dependents")
    stored = replacement(target, connector_id, version, digest)
    # Preview the same schema/scope/mapping gates used by normal activation.
    # No connection, credential, mapping or active-state change commits here.
    from app.services.connector_mappings import require_resolved
    from app.services.integration_connections import validate_dependents
    before = dependent_state(db, connector_id)
    previous_scopes = [{"integration_id": str(row.id), "selected_scopes": row.selected_scopes}
        for row in db.scalars(select(Integration).where(Integration.connector_id == connector_id,
            Integration.retired_at.is_(None)).order_by(Integration.id))]
    with db.begin_nested() as preview:
        apply_scopes(db, connector_id, stored.manifest, scopes)
        require_resolved(db, stored.manifest, auto_map=True)
        validate_dependents(db, stored.manifest)
        preview.rollback()
    return {"purpose": "restore-bundled-management", "binding_digest": authority.digest(bound),
        "instance_id": bound["instance_id"], "original_store": str(original), "target_store": target_identity,
        "active_digest": authority.digest(acceptance.snapshot(active)), "revocation_digest": authority.digest(tombstone),
        "dependent_state_digest": before, "scope_selection": scopes, "previous_scopes": previous_scopes,
        "connector_id": connector_id, "version": version, "digest": digest,
        "replacement_evidence_digest": authority.digest(stored.verification)}


def plan(db, original, target, connector_id, version, digest, *, scopes=None):
    authority.operator()
    with PackageStore(original)._lock():
        value = _plan(db, original, target, connector_id, version, digest, scopes=scopes)
        return {**value, "plan_digest": authority.digest(value)}


def authorize(db, original, target, connector_id, version, digest, approved_digest, *, scopes=None):
    authority.operator()
    with PackageStore(original)._lock():
        state = _plan(db, original, target, connector_id, version, digest, scopes=scopes)
        authority.require(authority.digest(state) == approved_digest, "local_release_stale_restoration_plan")
        bound = authority.binding(original)
        value = {**state, "transition_id": str(uuid.uuid4()), "issued_at": int(time.time())}
        envelope = authority.signed(value, bound)
        directory = original / authority.DIRECTORY / "restorations"
        directory.mkdir(mode=0o755, exist_ok=True)
        authority.publish(directory / (value["transition_id"] + ".json"), authority.canonical(envelope))
        key = PREFIX + connector_id
        record = db.scalar(select(SystemSetting).where(SystemSetting.key == key).with_for_update())
        if record is None:
            record = SystemSetting(key=key, sensitive=True, description="Root-signed exact bundled-management handoff")
            db.add(record)
        record.value_ = envelope
        add_audit_event(db, action="connector.local_restoration_authorized", target_type="connector_package",
            summary="Root operator authorized exact revoked local activation handoff to ordinary bundled management",
            metadata={"transition_id": value["transition_id"], "handoff_digest": authority.digest(value),
                      "connector_id": connector_id, "instance_id": bound["instance_id"]})
        db.commit()
        return value


def consume(db, active, stored):
    """Called only by normal activation, under its existing connector lock."""
    acceptance.lock_review_state(db, active.connector_id)
    record = db.scalar(select(SystemSetting).where(SystemSetting.key == PREFIX + active.connector_id).with_for_update())
    authority.require(record is not None, "local_release_bundled_handoff_required")
    value = record.value_["payload"]
    original = Path(value["original_store"])
    bound, tombstone = revoked_record(db, original, active)
    authority.require(authority.authenticated(authority.canonical(record.value_), bound) == value
        and value.get("purpose") == "restore-bundled-management" and value.get("binding_digest") == authority.digest(bound)
        and value.get("instance_id") == bound["instance_id"]
        and value.get("active_digest") == authority.digest(acceptance.snapshot(active))
        and value.get("revocation_digest") == authority.digest(tombstone)
        and value.get("dependent_state_digest") == dependent_state(db, active.connector_id)
        and value.get("target_store") == ordinary_store(lifecycle.package_store().root)
        and (value.get("connector_id"), value.get("version"), value.get("digest")) ==
            (stored.connector_id, stored.version, stored.bundle_digest.removeprefix("sha256:")),
        "local_release_bundled_handoff_mismatch")
    retained = authority.authenticated(authority.protected(original / authority.DIRECTORY / "restorations" /
        (str(uuid.UUID(value["transition_id"])) + ".json")), bound)
    authority.require(retained == value and db.scalar(select(AuditEvent.id).where(
        AuditEvent.event_type == "connector.local_restoration_authorized",
        AuditEvent.metadata_["transition_id"].astext == value["transition_id"],
        AuditEvent.metadata_["handoff_digest"].astext == authority.digest(value))) is not None,
        "local_release_bundled_handoff_audit_required")
    verified_stored = replacement(lifecycle.package_store().root, stored.connector_id, stored.version, value["digest"])
    authority.require(verified_stored.verification == stored.verification
        and verified_stored.manifest == stored.manifest
        and value["replacement_evidence_digest"] == authority.digest(stored.verification),
        "local_release_bundled_handoff_mismatch")
    apply_scopes(db, active.connector_id, stored.manifest, value.get("scope_selection"))
    db.delete(record)
    add_audit_event(db, action="connector.local_restoration_completed", target_type="connector_package",
        summary="Normal bundled activation consumed root handoff; local authority remains revoked",
        metadata={"transition_id": value["transition_id"], "handoff_digest": authority.digest(value),
                  "connector_id": stored.connector_id, "instance_id": bound["instance_id"]})
