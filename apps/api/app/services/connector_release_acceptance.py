"""Explicit official-release acceptance outside authenticated catalogue selection."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
import time
import uuid

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.models import InstalledConnectorPackage, Integration, IntegrationSecret, ConnectorMapping, AssetType, RelationshipType
from app.services import connector_lifecycle as lifecycle, connector_mappings as mappings
from app.services import local_release_authority as authority
from app.services.catalogue_source import BASE, GithubReader, decode, require
from app.services.connector_catalogue import CataloguePackage, compatibility
from app.services.connector_contracts import strict_json, validate_manifest
from app.services.connector_store import MAX_ARCHIVE_BYTES, PackageStore, StoredPackage, _read_regular, _write
from app.services.official_provenance import GithubAttestationVerifier, PackageArtifactContext, MAX_BUNDLE_BYTES


@dataclass(frozen=True)
class ReleaseIdentity:
    connector_id: str
    version: str
    release_id: int
    package_asset_id: int
    source_commit: str
    sha256: str

    def context(self):
        return PackageArtifactContext(self.connector_id, self.version, self.sha256, self.source_commit)


def release_identity(reader, release, ref, identity):
    tag = f"{identity.connector_id}-v{identity.version}"
    require(isinstance(release, dict) and release.get("id") == identity.release_id
            and type(identity.release_id) is int and identity.release_id > 0
            and release.get("tag_name") == tag and release.get("draft") is False
            and release.get("prerelease") is False and release.get("immutable") is True
            and release.get("target_commitish") == identity.source_commit
            and release.get("html_url") == f"https://github.com/benchristian88/atlas-connectors/releases/tag/{tag}"
            and isinstance(release.get("assets"), list) and len(release["assets"]) <= 100,
            "local_release_identity_mismatch")
    require(isinstance(ref, dict) and ref.get("ref") == f"refs/tags/{tag}"
            and ref.get("object", {}).get("type") == "commit"
            and ref["object"].get("sha") == identity.source_commit, "local_release_tag_mismatch")
    assets = {name: reader.asset(release, name, tag=tag, maximum=maximum) for name, maximum in (
        (f"{identity.connector_id}-{identity.version}.tar.gz", MAX_ARCHIVE_BYTES),
        ("manifest.json", 256 * 1024), ("package.sigstore.json", MAX_BUNDLE_BYTES))}
    package = assets[f"{identity.connector_id}-{identity.version}.tar.gz"]
    require(type(identity.package_asset_id) is int and package["id"] == identity.package_asset_id
            and package["digest"] == "sha256:" + identity.sha256, "local_release_asset_mismatch")
    return {"id": release["id"], "tag": tag, "source_commit": identity.source_commit,
            "immutable": True, "assets": {name: {k: value[k] for k in ("id", "name", "size", "digest", "state", "url", "browser_download_url")}
                                       for name, value in assets.items()}}


async def verify_release(identity, destination):
    # Validate context before deriving ANY URL/path, using the fixed verifier's
    # input rules without invoking a subprocess or treating claims as evidence.
    import re
    from app.services.connector_store import _identity
    _identity(identity.connector_id, identity.version, "sha256:" + identity.sha256)
    require(re.fullmatch(r"[a-f0-9]{40}", identity.source_commit) is not None, "invalid_artifact_context")
    require(not destination.exists(), "local_release_evidence_already_exists")
    tag = f"{identity.connector_id}-v{identity.version}"
    async with GithubReader() as reader:
        await reader.repository()
        release_raw = await reader.get(f"{BASE}/releases/tags/{tag}", 256 * 1024)
        ref_raw = await reader.get(f"{BASE}/git/ref/tags/{tag}", 16 * 1024)
        selected = release_identity(reader, decode(release_raw), decode(ref_raw), identity)
        downloaded = {name: await reader.download(asset, maximum=MAX_ARCHIVE_BYTES if name.endswith(".tar.gz") else MAX_BUNDLE_BYTES if name == "package.sigstore.json" else 256 * 1024)
                      for name, asset in selected["assets"].items()}
        package_name = f"{identity.connector_id}-{identity.version}.tar.gz"
        provenance = GithubAttestationVerifier().verify_package(downloaded[package_name], downloaded["package.sigstore.json"], identity.context())
        manifest = validate_manifest(strict_json(downloaded["manifest.json"]), activation=True)
        from app.services.official_catalogue import _validate_entry
        # Reuse official structural declarations without creating/accepting a
        # catalogue entry or conferring catalogue installation authority.
        _validate_entry({"status": "active", "release_tag": tag,
                         "release_asset_id": identity.package_asset_id, "manifest": manifest})
        require(manifest["id"] == identity.connector_id and manifest["version"] == identity.version
                and manifest["distribution"]["bundle_digest"] == "sha256:" + identity.sha256
                and manifest["publisher"]["id"] == "atlas-official"
                and manifest["distribution"]["provenance"].get("source_commit") == identity.source_commit,
                "local_release_manifest_mismatch")
        # Authenticates the manifest domain by matching it to the signed archive;
        # detached distribution metadata is retained separately, never signed by us.
        PackageStore(Path("/unused-local-release-validation"))._extract(downloaded[package_name], None, manifest)
        after = release_identity(reader, decode(await reader.get(f"{BASE}/releases/tags/{tag}", 256 * 1024)),
                                 decode(await reader.get(f"{BASE}/git/ref/tags/{tag}", 16 * 1024)), identity)
        require(after == selected, "local_release_changed")
    result = {"schema": 1, "identity": asdict(identity), "release": selected,
              "provenance": strict_json(authority.canonical(asdict(provenance)), maximum=256 * 1024)}
    destination.mkdir(mode=0o700, parents=False)
    for name, raw in {**downloaded, "release.json": release_raw, "tag-ref.json": ref_raw,
                      "result.json": authority.canonical(result)}.items():
        _write(destination / name, raw)
    authority.sync_directory(destination)
    authority.sync_directory(destination.parent)
    return result


def load_result(directory):
    result = strict_json(_read_regular(directory / "result.json", 256 * 1024))
    require(isinstance(result, dict) and result.get("schema") == 1, "local_release_invalid_result")
    identity = ReleaseIdentity(**result["identity"])
    raw = _read_regular(directory / f"{identity.connector_id}-{identity.version}.tar.gz", MAX_ARCHIVE_BYTES)
    provenance = GithubAttestationVerifier().verify_package(raw, _read_regular(directory / "package.sigstore.json", MAX_BUNDLE_BYTES), identity.context())
    require(provenance.artifact_sha256 == result["provenance"]["artifact_sha256"], "local_release_invalid_result")
    return result, identity


class LocalReleaseVerifier:
    def __init__(self, root, evidence):
        self.root, self.evidence = root, evidence

    def verify(self, archive, package):
        authority.authorize(self.root, package.manifest, self.evidence)
        proof = self.evidence["provenance"]
        directory = self.root / authority.DIRECTORY / self.evidence["authorization_id"]
        verified = GithubAttestationVerifier().verify_package(archive, _read_regular(directory / "package.sigstore.json", MAX_BUNDLE_BYTES),
            PackageArtifactContext(package.connector_id, package.version, package.bundle_digest[7:], proof["source_commit"]))
        require(verified.artifact_sha256 == proof["artifact_sha256"], "local_release_invalid_result")
        return self

    def safe_metadata(self):
        return self.evidence


async def stage(db, root, identity):
    authority.operator()
    bound = authority.binding(root)
    authority.check_database(db, bound)
    identifier = str(uuid.uuid4())
    directory = root / authority.DIRECTORY
    directory.mkdir(mode=0o755, exist_ok=True)
    # Fresh public observations and original bytes are required for each grant;
    # a caller-edited retained verify result cannot grant authority.
    result = await verify_release(identity, directory / identifier)
    manifest = validate_manifest(strict_json(_read_regular(directory / identifier / "manifest.json", 256 * 1024)), activation=True)
    now = int(time.time())
    grant = {"authorization_id": identifier, "binding_digest": authority.digest(bound), "connector_id": identity.connector_id,
             "version": identity.version, "bundle_digest": "sha256:" + identity.sha256, "manifest_digest": authority.digest(manifest),
             "purpose": "artifact-staging", "issued_at": now, "provenance": result["provenance"], "release": result["release"]}
    raw = authority.canonical(authority.signed(grant, bound))
    evidence = {"method": "operator-local-release", "bundle_digest": grant["bundle_digest"], "publisher_id": "atlas-official",
                "authorization_id": identifier, "authorization_digest": hashlib.sha256(raw).hexdigest(),
                "provenance": grant["provenance"], "release": grant["release"]}
    store = PackageStore(root)
    # No replacement/renewal of an immutable receipt at an already-staged tuple.
    require(not store._path(identity.connector_id, identity.version, grant["bundle_digest"]).exists(), "local_release_already_staged")
    with store._lock():
        authority.publish(directory / (identifier + ".json"), raw)
    package = CataloguePackage(identity.connector_id, identity.version, grant["bundle_digest"], manifest, "operator-local-release", True,
                               directory / identifier / f"{identity.connector_id}-{identity.version}.tar.gz")
    try:
        stored = store.install(package, LocalReleaseVerifier(root, evidence))
        # PackageStore's existing-tuple path may win a concurrent stage. Never
        # return a newly minted UUID when the immutable receipt uses another one.
        actual = stored_package(root, identity)
        require(actual.verification["authorization_id"] == identifier, "local_release_already_staged")
    except (OSError, ValueError):
        revoke(root, identifier)  # Keep the failed grant and original evidence.
        raise
    return stored


def revoke(root, identifier, db=None, *, corrupt_sha256=None):
    from app.services.local_release_revocation import publish
    publish(root, identifier, corrupt_sha256=corrupt_sha256)
    # Durable denial precedes any database access, including connection failure.
    return reconcile_revocation(root, identifier, db=db)


def reconcile_revocation(root, identifier, db=None):
    authority.operator()
    bound = authority.binding(root)
    require(str(uuid.UUID(identifier)) == identifier, "local_release_invalid_authorization")
    from app.services.local_release_revocation import verified
    tombstone = verified(root, identifier, bound)
    from app.models import AuditEvent
    from app.audit import add_audit_event
    from sqlalchemy.exc import SQLAlchemyError
    try:
        if db is None:
            from app.database import SessionLocal
            with SessionLocal() as session:
                return reconcile_revocation(root, identifier, db=session)
        authority.check_database(db, bound)
        lifecycle.lock_connector(db, "local-revocation:" + identifier)
        existing = db.scalar(select(AuditEvent.id).where(AuditEvent.event_type == "connector.local_release_revoked",
            AuditEvent.metadata_["artifact_id"].astext == identifier,
            AuditEvent.metadata_["instance_id"].astext == bound["instance_id"]))
        if existing is None:
            add_audit_event(db, action="connector.local_release_revoked", target_type="connector_package",
                summary="Root operator revoked local release authority; filesystem denial is durable",
                metadata={**tombstone, "instance_id": bound["instance_id"], "authority": "local-root-operator"})
        recovery = tombstone.get("recovered_evidence")
        if recovery is not None and db.scalar(select(AuditEvent.id).where(
            AuditEvent.event_type == "connector.local_revocation_recovered",
            AuditEvent.metadata_["tombstone_digest"].astext == authority.digest(tombstone))) is None:
            add_audit_event(db, action="connector.local_revocation_recovered", target_type="connector_package",
                summary="Root operator preserved corrupt revocation evidence and republished durable denial",
                metadata={**tombstone, "tombstone_digest": authority.digest(tombstone), "instance_id": bound["instance_id"]})
        db.commit()
        return {"status": "revoked", "audit": "recorded"}
    except (SQLAlchemyError, OSError, ValueError):
        if db is not None:
            db.rollback()
        return {"status": "revoked", "audit": "reconciliation_required"}


def stored_package(root, identity):
    store = PackageStore(root)
    store.verify_connector(identity.connector_id, identity.version, "sha256:" + identity.sha256)
    directory = store._path(identity.connector_id, identity.version, "sha256:" + identity.sha256)
    manifest = strict_json(_read_regular(directory / "manifest.json", 256 * 1024))
    receipt = strict_json(_read_regular(directory / "verification.json", 512 * 1024), maximum=512 * 1024)
    require(receipt["verification"].get("method") == "operator-local-release", "local_release_invalid_authorization")
    require(receipt["verification"]["release"]["id"] == identity.release_id
            and receipt["verification"]["release"]["assets"][f"{identity.connector_id}-{identity.version}.tar.gz"]["id"] == identity.package_asset_id
            and receipt["verification"]["provenance"]["source_commit"] == identity.source_commit, "local_release_identity_mismatch")
    return StoredPackage(identity.connector_id, identity.version, "sha256:" + identity.sha256, manifest, receipt["verification"])


def snapshot(row):
    return {column.name: getattr(row, column.key) for column in row.__mapper__.columns}


def apply_choices(db, manifest, choices, scopes, rows):
    from app.services.integration_connections import validate_scopes
    if scopes is not None:
        validate_scopes(manifest, scopes)
        for row in rows:
            row.selected_scopes = sorted(scopes)
    require(isinstance(choices, list) and len(choices) <= 256, "local_release_invalid_mappings")
    declared = {(kind, row["key"]) for kind, row, _ in mappings.declarations(manifest)}
    seen = set()
    for choice in choices:
        require(isinstance(choice, dict) and set(choice) == {"kind", "source_key", "target_key"}
                and all(isinstance(value, str) for value in choice.values()), "local_release_invalid_mappings")
        key = (choice["kind"], choice["source_key"])
        require(key in declared and key not in seen and mappings.target(db, choice["kind"], choice["target_key"]) is not None,
                "local_release_invalid_mappings")
        seen.add(key)
        row = db.scalar(select(ConnectorMapping).where(ConnectorMapping.connector_id == manifest["id"],
            ConnectorMapping.connector_version == manifest["version"], ConnectorMapping.kind == choice["kind"],
            ConnectorMapping.source_key == choice["source_key"]))
        if row is None:
            row = ConnectorMapping(connector_id=manifest["id"], connector_version=manifest["version"],
                                   kind=choice["kind"], source_key=choice["source_key"])
            db.add(row)
        row.target_key, row.ignored = choice["target_key"], False
        row.asset_type_key = row.target_key if row.kind == "asset" else None
        row.relationship_type_key = row.target_key if row.kind == "relationship" else None
    db.flush()


def _plan(db, root, identity, health, *, choices=None, scopes=None, isolation=None):
    authority.operator()
    bound = authority.binding(root)
    authority.check_database(db, bound)
    isolation = isolation or bound["isolation"]
    authority.check_isolation(isolation, bound["isolation"]["deployment"], authority.inspect_resources(db, root))
    stored = stored_package(root, identity)
    require(compatibility(stored.manifest, health)["state"] == "compatible", "local_release_runtime_incompatible")
    lifecycle.lock_connector(db, identity.connector_id)
    # Re-read after obtaining the connector lock, including on the second pass
    # after runtime I/O; a Session identity-map value is not current-state proof.
    db.expire_all()
    require(not lifecycle.active_connector_runs(db, identity.connector_id), "local_release_active_runs")
    rows = list(db.scalars(select(Integration).where(Integration.retired_at.is_(None),
                (Integration.connector_id == identity.connector_id) | (Integration.plugin_id == identity.connector_id)).with_for_update()))
    require(all(row.connector_id is not None and row.schedule_preset == "manual" for row in rows), "local_release_requires_manual_connections")
    from app.services.integration_connections import validate_dependents
    before = {"integrations": sorted([snapshot(row) for row in rows], key=lambda r: str(r["id"])),
              "mappings": sorted([snapshot(row) for row in db.scalars(select(ConnectorMapping).where(
                  ConnectorMapping.connector_id == identity.connector_id).with_for_update())], key=lambda r:str(r["id"]))}
    choices = choices or []
    apply_choices(db, stored.manifest, choices, scopes, rows)
    configuration_ready = True
    try:
        validate_dependents(db, stored.manifest)
    except ValueError:
        configuration_ready = False
    mapping_state = mappings.mapping_state(db, stored.manifest, auto_map=True)
    active = db.get(InstalledConnectorPackage, identity.connector_id)
    # Hash all dependent fields, including ciphertext identity; never print them.
    # Do not change scopes/mappings implicitly as part of local acceptance.
    secrets = [snapshot(row) for row in db.scalars(select(IntegrationSecret).where(IntegrationSecret.integration_id.in_([r.id for r in rows])).with_for_update())]
    targets = {kind: sorted([snapshot(row) for row in db.scalars(select(model).order_by(model.id).with_for_update(of=model))], key=lambda r: str(r["id"]))
               for kind, model in (("asset", AssetType), ("relationship", RelationshipType))}
    state = {"before": before, "secrets": sorted(secrets, key=lambda r: str(r["id"])), "taxonomy": targets}
    value = {"schema": 1, "instance_id": bound["instance_id"], "store_id": bound["store_id"], "store_path": str(root),
             "atlas_commit": bound["atlas_commit"], "package": asdict(identity), "verification": authority.digest(stored.verification),
             "runtime": runtime_identity(health),
             "mappings": mapping_state, "dependent_state_digest": authority.digest(state),
             "mapping_choices": sorted(choices, key=lambda r:(r["kind"], r["source_key"])), "scopes": scopes,
             "isolation": isolation, "ready": configuration_ready and all(r["resolved"] for r in mapping_state if r["required"]),
             "dependent_configuration_ready": configuration_ready,
             "integrations": sorted([{"id": str(row.id), "customer_id": str(row.customer_id), "site_id": str(row.site_id)} for row in rows], key=lambda r:r["id"]),
             "replaces": None if active is None else {"connector_id": active.connector_id, "version": active.version,
                    "digest": active.bundle_digest, "verification_digest": authority.digest(active.verification_evidence),
                    "activated_at": active.activated_at.isoformat()}}
    return value


def runtime_identity(health):
    """Stable compatibility identity; timestamps and available job slots are liveness."""
    require(health.get("status") == "healthy", "local_release_runtime_incompatible")
    fields = ("runtime_version", "protocol_version", "baseline_id", "baseline_version", "baseline_digest",
              "dependency_lock_digest", "packaging_mode", "ansible_core_version", "ansible_runner_version")
    capabilities = health.get("capabilities", {})
    return {**{key: health.get(key) for key in fields},
        "capabilities": {key: capabilities.get(key) for key in ("operations", "aip_versions", "dependencies", "collections")}}


def lock_review_state(db, connector_id):
    """Acquire outside preview savepoints: PostgreSQL releases rolled-back row locks."""
    lifecycle.lock_connector(db, connector_id)
    rows = list(db.scalars(select(Integration).where(Integration.retired_at.is_(None),
        (Integration.connector_id == connector_id) | (Integration.plugin_id == connector_id)).with_for_update()))
    list(db.scalars(select(IntegrationSecret).where(IntegrationSecret.integration_id.in_([row.id for row in rows])).with_for_update()))
    list(db.scalars(select(ConnectorMapping).where(ConnectorMapping.connector_id == connector_id).with_for_update()))
    for model in (AssetType, RelationshipType):
        list(db.scalars(select(model).order_by(model.id).with_for_update(of=model)))


def plan(db, root, identity, health, *, choices=None, scopes=None, isolation=None, action="activate", lease_seconds=authority.MAX_LIFETIME):
    authority.operator()
    require(action in {"activate", "renew", "recover"}, "local_release_invalid_action")
    require(type(lease_seconds) is int and 0 < lease_seconds <= authority.MAX_LIFETIME, "local_release_invalid_lease")
    state = _plan(db, root, identity, health, choices=choices, scopes=scopes, isolation=isolation)
    if action != "activate":
        active = db.get(InstalledConnectorPackage, identity.connector_id)
        require(active is not None and (active.version, active.bundle_digest) == (identity.version, identity.sha256)
                and active.verification_evidence.get("local_activation"), "local_release_activation_required")
        require(not choices and scopes is None, "local_release_renewal_cannot_reconfigure")
    now = int(time.time())
    approval = {"purpose": "exact-plan-approval", "action": action, "plan_digest": authority.digest(state),
        "binding_digest": authority.digest(authority.binding(root)), "approval_id": str(uuid.uuid4()),
        "issued_at": now, "expires_at": now + authority.APPROVAL_LIFETIME, "lease_seconds": lease_seconds}
    identifier = authority.digest(approval)
    directory = root / authority.DIRECTORY / "approvals"
    directory.mkdir(mode=0o755, exist_ok=True)
    authority.publish(directory / (identifier + ".json"), authority.canonical(authority.signed(approval, authority.binding(root))))
    return {**state, "approval": approval, "approval_digest": identifier}


def approved(root, identifier, action):
    import re
    require(isinstance(identifier, str) and re.fullmatch(r"[a-f0-9]{64}", identifier), "local_release_explicit_approval_required")
    directory = root / authority.DIRECTORY / "approvals"
    require(not (directory / (identifier + ".consumed.json")).exists(), "local_release_approval_consumed")
    bound = authority.binding(root)
    value = authority.authenticated(authority.protected(directory / (identifier + ".json")), bound)
    require(authority.digest(value) == identifier and value.get("purpose") == "exact-plan-approval"
        and value.get("action") == action and value.get("binding_digest") == authority.digest(bound)
        and type(value.get("issued_at")) is int and type(value.get("expires_at")) is int
        and value["issued_at"] <= time.time() < value["expires_at"] <= value["issued_at"] + authority.APPROVAL_LIFETIME,
        "local_release_approval_expired_or_mismatched")
    return value


def consume(root, identifier, activation, action):
    authority.publish(root / authority.DIRECTORY / "approvals" / (identifier + ".consumed.json"),
        authority.canonical(authority.signed({"approval_digest": identifier, "activation": activation,
            "action": action}, authority.binding(root))))


def publish_execution(db, root, active):
    """Only called AFTER commit; a fresh database transaction rechecks that commit."""
    from sqlalchemy.orm import Session
    require(not db.in_transaction(), "local_release_commit_required")
    connector_id = active.connector_id
    expected = active.verification_evidence.get("local_activation")
    bind = db.get_bind()
    engine = getattr(bind, "engine", bind)
    with Session(engine, expire_on_commit=False) as committed:
        lifecycle.lock_connector(committed, connector_id)
        record = committed.get(InstalledConnectorPackage, connector_id)
        require(record is not None and record.verification_evidence.get("local_activation") == expected,
                "local_release_commit_required")
        _publish_committed_execution(committed, root, record)


def _publish_committed_execution(db, root, active):
    evidence = authority.artifact_evidence(active.verification_evidence)
    activation = active.verification_evidence["local_activation"]
    bound = authority.binding(root)
    authority.check_database(db, bound)
    consumed = authority.authenticated(authority.protected(root / authority.DIRECTORY / "approvals" /
        (activation["approval_digest"] + ".consumed.json")), bound)
    require(consumed.get("activation") == activation and consumed.get("action") in {"activate", "renew"},
            "local_release_activation_approval_required")
    # Verify durable approved-activation evidence, never a merely flushed ORM row.
    from app.models import AuditEvent
    require(db.scalar(select(AuditEvent.id).where(AuditEvent.event_type.in_([
        "connector.local_release_activated", "connector.local_execution_renewed"]),
        AuditEvent.metadata_["activation"] == activation)) is not None, "local_release_activation_audit_required")
    directory = root / active.connector_id / active.version / active.bundle_digest
    manifest = strict_json(_read_regular(directory / "manifest.json", 256 * 1024))
    authority.authorize(root, manifest, evidence)
    lease = {"purpose": "manual-execution", "activation": activation, "binding_digest": authority.digest(bound),
        "artifact_digest": authority.digest(evidence), "connector_id": active.connector_id, "version": active.version,
        "bundle_digest": "sha256:" + active.bundle_digest,
        **{key: activation[key] for key in ("issued_at", "expires_at", "lease_id")}}
    require(lease["issued_at"] <= time.time() < lease["expires_at"], "local_release_execution_expired")
    path = authority.execution_path(root, active.connector_id)
    path.parent.mkdir(mode=0o755, exist_ok=True)
    raw = authority.canonical(authority.signed(lease, bound))
    history = path.parent / (activation["lease_id"] + ".lease.json")
    if not history.exists():
        authority.publish(history, raw)
    temporary = path.parent / (str(uuid.uuid4()) + ".pending")
    authority.publish(temporary, raw)
    temporary.replace(path)
    authority.sync_directory(path.parent)


def activation_metadata(root, approval_digest, approval, *, generation=None):
    now = int(time.time())
    return {"generation": generation or str(uuid.uuid4()), "approval_digest": approval_digest,
        "plan_digest": approval["plan_digest"], "binding_digest": authority.digest(authority.binding(root)),
        "lease_id": str(uuid.uuid4()), "issued_at": now, "expires_at": now + approval["lease_seconds"]}


def publication_failed(db, root, connector_id, activation):
    authority.fence_execution(root, connector_id)
    from app.audit import add_audit_event
    try:
        add_audit_event(db, action="connector.local_execution_publication_failed", target_type="connector_package",
            summary="Committed local activation has no execution authority; reviewed recovery required", success=False,
            metadata={"connector_id": connector_id, "activation": activation, "authority": "local-root-operator"})
        db.commit()
    except (SQLAlchemyError, OSError):
        db.rollback()  # The committed activation audit and consumed approval remain.


async def activate(db, root, identity, approved_digest, runtime, *, choices=None, scopes=None, isolation=None):
    authority.operator()
    require(isinstance(approved_digest, str) and len(approved_digest) == 64, "local_release_explicit_approval_required")
    # Root store lock serializes revocation and activation; the normal connector
    # advisory/row locks serialize application updates and discovery admission.
    with PackageStore(root)._lock():
        approval = approved(root, approved_digest, "activate")
        health = await runtime.health()
        lock_review_state(db, identity.connector_id)
        # A savepoint keeps previews/failed approval from changing dependent state.
        with db.begin_nested() as preview:
            current = _plan(db, root, identity, health, choices=choices, scopes=scopes, isolation=isolation)
            preview.rollback()
        require(authority.digest(current) == approval["plan_digest"], "local_release_stale_approval")
        require(current["ready"], "local_release_configuration_required")
        stored = stored_package(root, identity)
        evidence_dir = root / authority.DIRECTORY / stored.verification["authorization_id"]
        load_result(evidence_dir)  # Reauthenticate retained original signature offline.
        reference = {"connector_id": identity.connector_id, "version": identity.version, "digest": identity.sha256}
        require((await runtime.verify_connector(reference)).get("state") == "verified", "local_release_runtime_verification_failed")
        require(runtime_identity(await runtime.health()) == runtime_identity(health), "local_release_runtime_changed")
        require(authority.digest(_plan(db, root, identity, health, choices=choices, scopes=scopes, isolation=isolation)) == approval["plan_digest"], "local_release_stale_approval")
        approved(root, approved_digest, "activate")  # approval may expire during runtime I/O
        activation = activation_metadata(root, approved_digest, approval)
        consume(root, approved_digest, activation, "activate")
        authority.fence_execution(root, identity.connector_id)
        active = lifecycle.activate(db, stored, health, local_release_acceptance=True)
        active.verification_evidence = {**stored.verification, "local_activation": activation}
        from app.audit import add_audit_event
        add_audit_event(db, action="connector.local_release_activated", target_type="connector_package",
            summary="Root operator activated an exact signed release in the bound isolated instance",
            metadata={**reference, "authority": "local-root-operator", "approval_digest": approved_digest,
                      "artifact_id": stored.verification["authorization_id"], "instance_id": current["instance_id"], "activation": activation})
        try:
            db.commit()
        except (SQLAlchemyError, OSError):
            db.rollback()
            raise
        try:
            publish_execution(db, root, active)
        except (SQLAlchemyError, OSError, ValueError, KeyError, TypeError):
            # The committed audit and consumed approval identify the exact
            # generation. Recovery needs a new reviewed plan, never restaging.
            publication_failed(db, root, identity.connector_id, activation)
            raise ValueError("local_release_committed_execution_denied_recovery_required") from None
        return active


async def maintain_execution(db, root, identity, approved_digest, runtime, *, action, isolation=None):
    """Explicit reviewed renewal or post-commit recovery, without changing artifacts."""
    authority.operator()
    require(action in {"renew", "recover"}, "local_release_invalid_action")
    with PackageStore(root)._lock():
        approval = approved(root, approved_digest, action)
        health = await runtime.health()
        lock_review_state(db, identity.connector_id)
        with db.begin_nested() as preview:
            state = _plan(db, root, identity, health, isolation=isolation)
            preview.rollback()
        require(authority.digest(state) == approval["plan_digest"], "local_release_stale_approval")
        require(state["ready"], "local_release_configuration_required")
        stored = stored_package(root, identity)
        load_result(root / authority.DIRECTORY / stored.verification["authorization_id"])
        require((await runtime.verify_connector({"connector_id": identity.connector_id, "version": identity.version,
            "digest": identity.sha256})).get("state") == "verified", "local_release_runtime_verification_failed")
        require(runtime_identity(await runtime.health()) == runtime_identity(health), "local_release_runtime_changed")
        require(authority.digest(_plan(db, root, identity, health, isolation=isolation)) == approval["plan_digest"], "local_release_stale_approval")
        active = db.get(InstalledConnectorPackage, identity.connector_id)
        require(active is not None and (active.version, active.bundle_digest) == (identity.version, identity.sha256)
            and active.verification_evidence.get("local_activation"), "local_release_activation_required")
        previous = active.verification_evidence["local_activation"]
        activation = activation_metadata(root, approved_digest, approval, generation=previous["generation"]) if action == "renew" else previous
        approved(root, approved_digest, action)
        consume(root, approved_digest, activation, action)
        authority.fence_execution(root, identity.connector_id)
        if action == "renew":
            active.verification_evidence = {**stored.verification, "local_activation": activation}
        from app.audit import add_audit_event
        add_audit_event(db, action="connector.local_execution_renewed" if action == "renew" else "connector.local_execution_recovery_requested",
            target_type="connector_package", summary="Root operator reviewed local execution " + action,
            metadata={"activation": activation, "review_digest": approved_digest, "authority": "local-root-operator"})
        try:
            db.commit()
        except (SQLAlchemyError, OSError):
            db.rollback()
            raise
        try:
            publish_execution(db, root, active)
        except (SQLAlchemyError, OSError, ValueError, KeyError, TypeError):
            publication_failed(db, root, identity.connector_id, activation)
            raise ValueError("local_release_committed_execution_denied_recovery_required") from None
        return active
