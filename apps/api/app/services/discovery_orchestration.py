"""PostgreSQL-owned discovery intent; Redis carries disposable dispatch hints."""
from datetime import datetime, timedelta, timezone
import logging
import os
import uuid

from sqlalchemy import or_, select

from atlas_connector_sdk.aip import body_hash
from atlas_connector_sdk.configuration import validate_configuration, visible
from app.models import DiscoveryRun, Integration
from app.services.connector_contracts import SDK_VERSION
from app.services.connector_catalogue import compatibility
from app.services.connector_mappings import require_resolved
from app.services.integration_connections import installed_manifest, validate_scopes
from app.services.integration_runtime import runtime, _approved_baseline
from app.services.integration_secrets import AtlasEncryptedSecretProvider
from app.services import discovery_tokens

logger = logging.getLogger("atlas.discovery")
SCHEDULES = {"manual": None, "hourly": 3600, "6_hours": 21600, "12_hours": 43200, "daily": 86400, "weekly": 604800}
QUEUE = "atlas:discovery:dispatch:v1"
MAX_ATTEMPTS = 3
JOB_SECONDS = 600
REQUIRED_OPERATIONS = {"run_discovery", "get_job", "cancel_job"}


class DiscoveryEligibilityError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def utcnow():
    return datetime.now(timezone.utc)


def active_run(db, integration_id):
    return db.scalar(select(DiscoveryRun).where(DiscoveryRun.integration_id == integration_id,
        DiscoveryRun.execution_provenance.is_not(None), or_(DiscoveryRun.status.in_(["pending", "running"]),
            DiscoveryRun.dispatch_state != "settled")).order_by(DiscoveryRun.created_at).limit(1))


def scope_encoding(row, manifest, mappings):
    validate_scopes(manifest, row.selected_scopes)
    selected = set(row.selected_scopes)
    if not selected:
        raise DiscoveryEligibilityError("discovery_scope_required")
    ignored = {item["source_key"] for item in mappings if item["ignored"]}
    scopes = []
    for scope in sorted(manifest["discovery_scopes"], key=lambda item: item["key"]):
        if scope["key"] not in selected:
            continue
        scopes.append({"key": scope["key"], "domains": sorted(set(scope["domains"])),
            "object_classes": sorted(set(scope["object_classes"]) - ignored),
            "filters": [{"field": item["field"], "values": sorted(item["default_values"], key=body_hash)}
                for item in sorted(scope.get("filters", []), key=lambda item: item["field"])]})
    classes = sorted({name for item in scopes for name in item["object_classes"]})
    domains = sorted({name for item in scopes for name in item["domains"]})
    identity = {"version": 1, "scopes": scopes, "ignored_classes": sorted(ignored)}
    return {"key": "connector:v1:" + body_hash(identity),
        "snapshot_mode": "full" if manifest["capabilities"]["complete_snapshot"] else "partial",
        "domains": domains}, classes


async def eligibility(db, row, *, require_runtime=True):
    if row.connector_id is None or row.retired_at or not row.enabled:
        raise DiscoveryEligibilityError("integration_disabled")
    if row.source_compatibility == "known_incompatible":
        raise DiscoveryEligibilityError("source_incompatible")
    record, manifest = installed_manifest(db, row.connector_id)
    if (record.version, record.bundle_digest) != (row.connector_version, row.connector_digest):
        raise DiscoveryEligibilityError("package_identity_changed")
    if manifest["capabilities"]["discover"] != "read_only" or manifest["implementation"]["entry_points"].get("discover") != "discover":
        raise DiscoveryEligibilityError("discovery_unavailable")
    from app.services.connector_lifecycle import package_store
    if not (package_store().root / record.connector_id / record.version / record.bundle_digest / "contents/discover.yml").is_file():
        raise DiscoveryEligibilityError("discovery_unavailable")
    provider = AtlasEncryptedSecretProvider(db)
    validate_configuration(manifest, row.config_json, configured_fields=provider.state(row))
    mappings = require_resolved(db, manifest)
    coverage, classes = scope_encoding(row, manifest, mappings)
    health = await runtime.health() if require_runtime else None
    if health is not None and (compatibility(manifest, health)["state"] != "compatible"
            or not REQUIRED_OPERATIONS <= set(health.get("capabilities", {}).get("operations", []))):
        raise DiscoveryEligibilityError("runtime_unavailable")
    return record, manifest, mappings, coverage, classes, health


async def create_run(db, row, *, trigger="manual", user_id=None):
    """Caller holds the Integration row lock. Unique index is a final DB guard."""
    if trigger not in {"manual", "schedule", "onboarding", "retry"}:
        raise DiscoveryEligibilityError("invalid_trigger")
    existing = active_run(db, row.id)
    if existing:
        error = DiscoveryEligibilityError("run_already_active")
        error.run_id = existing.id
        raise error
    record, manifest, mappings, coverage, classes, health = await eligibility(db, row)
    baseline = _approved_baseline()
    if SDK_VERSION != baseline["sdk_version"]:
        raise DiscoveryEligibilityError("sdk_version_changed")
    provenance = {"connector_id": record.connector_id, "connector_version": record.version,
        "connector_digest": record.bundle_digest, "manifest_version": manifest["manifest_version"],
        "aip_version": "1.0", "sdk_version": SDK_VERSION, "sdk_digest": baseline["sdk_package_digest"],
        "runtime_type": "ansible", "trigger": trigger,
        **{name: health.get(name) for name in ["runtime_version", "protocol_version", "baseline_id", "baseline_version",
            "baseline_digest", "dependency_lock_digest", "packaging_mode"]},
        "manifest": manifest, "mappings": mappings, "config": row.config_json,
        "credential_revision": str(row.credential_reference) if row.credential_reference else None,
        "selected_scopes": sorted(row.selected_scopes), "object_classes": classes, "coverage": coverage}
    run = DiscoveryRun(id=uuid.uuid4(), integration_id=row.id, data_source_id=row.data_source_id,
        customer_id=row.customer_id, site_id=row.site_id, status="pending", started_at=utcnow(),
        created_by_user_id=user_id, coverage_key=coverage["key"], is_complete_snapshot=coverage["snapshot_mode"] == "full",
        completeness_status="unknown", execution_provenance=provenance, dispatch_state="pending",
        dispatch_attempts=0, dispatch_after=utcnow(), batch_count=0, observation_count=0, warning_count=0, summary={})
    db.add(run)
    db.flush()
    row.last_run_at = run.started_at
    logger.info("discovery run=%s integration=%s state=pending", run.id, row.id)
    return run


def redis_client():
    from redis import Redis
    return Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        socket_connect_timeout=1, socket_timeout=1, decode_responses=True)


def enqueue(run_id):
    from redis.exceptions import RedisError
    try:
        with redis_client() as client:
            with client.pipeline(transaction=True) as pipeline:
                pipeline.lpush(QUEUE, str(run_id))
                pipeline.ltrim(QUEUE, 0, 4095)
                pipeline.execute()
        return True
    except (RedisError, OSError, ValueError):
        logger.warning("discovery run=%s category=dispatch_hint_unavailable", run_id)
        return False  # Durable pending intent is scanned/reconciled by worker.


def next_run(preset, now):
    seconds = SCHEDULES.get(preset)
    return now + timedelta(seconds=seconds) if seconds else None


def cancel_intent(run):
    if run.status in {"completed", "failed", "cancelled"}:
        return
    run.cancellation_requested_at = utcnow()
    run.ingestion_generation = None
    run.status, run.completeness_status = "cancelled", "unknown"
    run.finished_at = run.completed_at = utcnow()
    if run.dispatch_state == "pending":
        run.dispatch_state = "settled"


def cancel_integration_runs(db, integration_id):
    for run in db.scalars(select(DiscoveryRun).where(DiscoveryRun.integration_id == integration_id,
            DiscoveryRun.execution_provenance.is_not(None), DiscoveryRun.status.in_(["pending", "running"])).with_for_update()):
        cancel_intent(run)


def fail_run(run, row, code):
    if run.status in {"completed", "failed", "cancelled"}:
        return
    run.status, run.completeness_status = "failed", "failed"
    run.finished_at = run.completed_at = utcnow()
    run.error_message = code
    run.ingestion_generation = None
    row.last_error_code = code
    # Runtime cleanup is reconciled separately; no snapshot absence call here.
    if run.dispatch_state == "pending":
        run.dispatch_state = "settled"
    logger.info("discovery run=%s integration=%s state=failed category=%s", run.id, row.id, code)


async def dispatch(db, run_id):
    identity = db.get(DiscoveryRun, run_id)
    if identity is None or identity.execution_provenance is None:
        return
    row = db.scalar(select(Integration).where(Integration.id == identity.integration_id).with_for_update())
    run = db.scalar(select(DiscoveryRun).where(DiscoveryRun.id == run_id).with_for_update().execution_options(populate_existing=True))
    if run.status != "pending" or run.dispatch_state != "pending" or run.dispatch_after and run.dispatch_after > utcnow():
        return
    if run.created_at < utcnow() - timedelta(minutes=15):
        fail_run(run, row, "dispatch_expired")
        db.commit()
        return
    run.dispatch_attempts += 1
    try:
        _, manifest, _, _, _, _ = await eligibility(db, row)
        provenance = run.execution_provenance
        if (row.connector_id, row.connector_version, row.connector_digest, row.data_source_id,
                row.customer_id, row.site_id, str(row.credential_reference) if row.credential_reference else None,
                row.config_json, sorted(row.selected_scopes)) != (provenance["connector_id"], provenance["connector_version"],
                provenance["connector_digest"], run.data_source_id, run.customer_id, run.site_id,
                provenance["credential_revision"], provenance["config"], provenance["selected_scopes"]):
            raise DiscoveryEligibilityError("integration_configuration_changed")
        run.deadline_at = utcnow() + timedelta(seconds=JOB_SECONDS + 60)
        run.ingestion_generation = uuid.uuid4()
        run.dispatch_state = "dispatching"
        # Other workers must allow the bounded start request to finish before
        # interpreting a missing runtime job as a crash.
        run.dispatch_after = utcnow() + timedelta(seconds=15)
        token = discovery_tokens.mint(run)
        provider = AtlasEncryptedSecretProvider(db)
        fields = provider.state(row)
        required = [field["key"] for field in manifest["connection_fields"]
            if field["secret"] and field["key"] in fields and visible(field, row.config_json)]
        with provider.materialize_for_job(row, run.id, required, duration_seconds=JOB_SECONDS + 60) as lease:
            request = {"request_id": str(run.id), "run_id": str(run.id), "integration_id": str(row.id),
                "reference": {"connector_id": provenance["connector_id"], "version": provenance["connector_version"],
                    "digest": provenance["connector_digest"]}, "config": provenance["config"],
                "credentials": lease.values, "selected_scopes": provenance["selected_scopes"], "object_classes": provenance["object_classes"],
                "coverage": provenance["coverage"], "ingestion_token": token, "timeout_seconds": JOB_SECONDS}
            # Persist generation and attempt before the runtime can callback.
            db.commit()
            try:
                result = await runtime.run_discovery(request)
            finally:
                request.clear()
        row = db.scalar(select(Integration).where(Integration.id == row.id).with_for_update().execution_options(populate_existing=True))
        run = db.scalar(select(DiscoveryRun).where(DiscoveryRun.id == run_id).with_for_update().execution_options(populate_existing=True))
        if result.get("job_id"):
            run.runtime_job_id = uuid.UUID(result["job_id"])
            if run.status == "pending":
                run.status, run.dispatch_state = "running", "running"
                run.started_at = utcnow()
        elif result.get("diagnostic_code") == "runtime_capacity" and run.status == "pending":
            run.ingestion_generation = None
            run.dispatch_state = "pending"
            if run.dispatch_attempts >= MAX_ATTEMPTS:
                fail_run(run, row, "runtime_capacity")
            else:
                run.dispatch_after = utcnow() + timedelta(seconds=5 * 2 ** run.dispatch_attempts)
        elif result.get("diagnostic_code") in {"invalid_request", "package_unavailable", "discovery_unavailable", "source_incompatible"}:
            fail_run(run, row, result["diagnostic_code"])
            run.dispatch_state = "settled"
        # Ambiguous dispatch is reconciled by request identity, never blindly rerun.
        db.commit()
    except (ValueError, OSError, RuntimeError) as error:
        code = error.code if isinstance(error, DiscoveryEligibilityError) else "configuration_unavailable"
        if code == "runtime_unavailable" and run.dispatch_attempts < MAX_ATTEMPTS and run.dispatch_state == "pending":
            run.dispatch_after = utcnow() + timedelta(seconds=5 * 2 ** run.dispatch_attempts)
        else:
            fail_run(run, row, code)
        db.commit()


async def reconcile(db, run_id):
    identity = db.get(DiscoveryRun, run_id)
    if identity is None or identity.execution_provenance is None:
        return
    if identity.dispatch_state == "dispatching" and identity.dispatch_after and identity.dispatch_after > utcnow():
        return
    result = await runtime.get_job(run_id, identity.runtime_job_id)
    row = db.scalar(select(Integration).where(Integration.id == identity.integration_id).with_for_update())
    run = db.scalar(select(DiscoveryRun).where(DiscoveryRun.id == run_id).with_for_update().execution_options(populate_existing=True))
    if run.dispatch_state == "settled":
        return
    if run.cancellation_requested_at or run.status in {"failed", "cancelled"}:
        result = await runtime.cancel_job(run.id, run.runtime_job_id)
    elif run.deadline_at and run.deadline_at <= utcnow():
        fail_run(run, row, "timeout")
        result = await runtime.cancel_job(run.id, run.runtime_job_id)
    if result.get("job_id"):
        run.runtime_job_id = uuid.UUID(result["job_id"])
    state = result.get("state")
    if state in {"succeeded", "failed", "cancelled"}:
        if run.status in {"pending", "running"}:
            fail_run(run, row, "missing_completion" if state == "succeeded" else result.get("diagnostic_code") or "runtime_failed")
        run.dispatch_state = "settled"
    elif state == "unavailable" and result.get("diagnostic_code") == "job_unavailable":
        fail_run(run, row, "runtime_interrupted")
        run.dispatch_state = "settled"
    elif state == "unavailable" and run.deadline_at and run.deadline_at + timedelta(seconds=60) <= utcnow():
        # Runtime jobs have their own deadline. A lost control service cannot
        # retain executable ownership forever after that bounded lifetime.
        fail_run(run, row, "runtime_unavailable")
        run.dispatch_state = "settled"
    elif state in {"queued", "running"} and run.status == "pending":
        run.status, run.dispatch_state = "running", "running"
    db.commit()
