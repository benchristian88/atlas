"""Atlas-owned, instance-global activation; knowledge history is never deleted."""
from datetime import datetime, timezone
import os
from pathlib import Path

from sqlalchemy import func, select, text, or_, and_

from app.models import InstalledConnectorPackage, Integration, DiscoveryRun


class ConnectorInUse(ValueError):
    pass


def connector_usage_count(db, connector_id: str) -> int:
    """Conservative existing owner adapter; I2 adds connector-key/retirement fields.

    All existing Integration rows (including disabled ones) are live references.
    No current legacy status establishes the future audited retirement workflow.
    """
    live = db.scalar(select(func.count()).select_from(Integration)
                     .where(or_(and_(Integration.connector_id == connector_id, Integration.retired_at.is_(None)),
                                and_(Integration.connector_id.is_(None), Integration.plugin_id == connector_id)))) or 0
    return live + active_connector_runs(db, connector_id)


def active_connector_runs(db, connector_id):
    return db.scalar(select(func.count()).select_from(DiscoveryRun).where(
        DiscoveryRun.execution_provenance["connector_id"].astext == connector_id,
        or_(DiscoveryRun.status.in_(["pending", "running"]), DiscoveryRun.dispatch_state != "settled"))) or 0


def require_unused(db, connector_id: str, usage_counter=connector_usage_count):
    if usage_counter(db, connector_id):
        raise ConnectorInUse("Remove configured connections before changing this Connector package")


def package_store():
    from app.services.connector_store import PackageStore
    return PackageStore(Path(os.getenv("ATLAS_CONNECTOR_STORE_PATH", "/var/lib/atlas-connectors")))


def lock_connector(db, connector_id: str):
    # Also serializes absent-row install, update and uninstall. PostgreSQL owns
    # active state; hash collisions only serialize extra work and confer no access.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": "atlas-connector:" + connector_id})


def activate(db, stored, health: dict):
    from app.services.connector_contracts import validate_manifest
    validate_manifest(stored.manifest, activation=True)
    if (stored.verification.get("status") != "verified"
            or stored.verification.get("bundle_digest") != stored.bundle_digest
            or stored.manifest["id"] != stored.connector_id
            or stored.manifest["version"] != stored.version
            or stored.manifest["distribution"]["bundle_digest"] != stored.bundle_digest
            or health.get("status") != "healthy"):
        raise ValueError("Only verified packages can become active")
    lock_connector(db, stored.connector_id)
    if active_connector_runs(db, stored.connector_id):
        raise ConnectorInUse("Wait for active discovery runs to settle before changing this Connector package")
    from app.services.connector_mappings import require_resolved
    from app.services.integration_connections import validate_dependents
    require_resolved(db, stored.manifest, auto_map=True)
    dependents = validate_dependents(db, stored.manifest)
    active = db.get(InstalledConnectorPackage, stored.connector_id)
    now = datetime.now(timezone.utc)
    values = dict(version=stored.version, bundle_digest=stored.bundle_digest.removeprefix("sha256:"),
        manifest_version=stored.manifest["manifest_version"], protocol_version="integration-runtime-v1",
        publisher_id=stored.manifest["publisher"]["id"], trust_tier="atlas_official",
        verification_status="verified", verification_evidence=stored.verification,
        runtime_baseline_id=health["baseline_id"], runtime_baseline_digest=health["baseline_digest"],
        status="active", installed_at=now, activated_at=now)
    if active is None:
        active = InstalledConnectorPackage(connector_id=stored.connector_id, **values)
        db.add(active)
    else:
        for field, value in values.items():
            setattr(active, field, value)
    db.flush()
    for integration in dependents:
        integration.connector_version = stored.version
        integration.connector_digest = stored.bundle_digest.removeprefix("sha256:")
        integration.config_schema_version = stored.manifest["manifest_version"]
        integration.last_test_at = integration.last_test_status = integration.source_version = integration.source_compatibility = None
    db.flush()
    return active


def installed_response(record: InstalledConnectorPackage) -> dict:
    # Never serialize filesystem/transport details or mutable ORM state.
    return {"connector_id": record.connector_id, "version": record.version,
        "digest": record.bundle_digest, "manifest_version": record.manifest_version,
        "protocol_version": record.protocol_version, "publisher_id": record.publisher_id,
        "trust_tier": record.trust_tier, "verification_status": record.verification_status,
        "runtime_baseline_id": record.runtime_baseline_id,
        "runtime_baseline_digest": record.runtime_baseline_digest,
        "status": record.status, "installed_at": record.installed_at,
        "activated_at": record.activated_at}
