"""Security-review reproductions, using real store/runtime admission and PostgreSQL."""
import asyncio
from copy import deepcopy
import json
import secrets
import time
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import AuditEvent, SystemSetting, InstalledConnectorPackage, DiscoveryRun, Integration
from app.services import connector_release_acceptance as service, local_release_authority as authority
from app.services import discovery_orchestration as discovery, integration_runtime
from app.services.integration_connections import installed_manifest
from tests.test_local_release_authority_postgres import db, configured, unenrolled, staged, preview, runtime, pytestmark
from tests.test_connector_release_acceptance import public_responses, IDENTITY
from tests.test_administration import make_principal, request


def test_staged_only_direct_runtime_probe_cannot_launch(staged, monkeypatch, tmp_path):
    from atlas_runtime.server import Runtime
    from atlas_runtime import probe
    store, stored, _, row, _, _ = staged
    fresh = Runtime(secrets.token_hex(48), store.root, "development")
    monkeypatch.setattr(fresh, "health", lambda: {"state": "healthy"})
    monkeypatch.setattr(probe, "workspace_root", lambda: tmp_path)
    def forbidden(*args, **kwargs):
        pytest.fail("staged-only package reached executable worker launch")
    monkeypatch.setattr(probe.subprocess, "Popen", forbidden)
    try:
        assert fresh.verify_connector({"connector_id": IDENTITY.connector_id, "version": IDENTITY.version,
            "digest": IDENTITY.sha256})["state"] == "verified"  # integrity inspection must remain possible
        result = fresh.test_connection({"reference": {"connector_id": IDENTITY.connector_id,
            "version": IDENTITY.version, "digest": IDENTITY.sha256}, "request_id": str(uuid.uuid4()),
            "config": row.config_json, "credentials": {"token_id": secrets.token_hex(12), "token_secret": secrets.token_hex(24)}})
        assert result["category"] == "package_unavailable"
    finally:
        fresh.jobs.shutdown()


def test_production_health_adapter_timestamp_does_not_invalidate_activation(db, staged, monkeypatch):
    store, _, _, _, _, choices = staged
    from atlas_runtime.server import Runtime
    from atlas_runtime import server
    baseline = integration_runtime._approved_baseline()
    monkeypatch.setattr(server, "version", lambda name: baseline["sdk_version"] if name == "atlas-connector-sdk" else baseline["dependencies"][name])
    monkeypatch.setattr(server, "collection_health", lambda: (baseline["collection_lock_digest"], baseline["collections"]))
    real = Runtime(secrets.token_hex(48), store.root, "development")
    async def control(operation, reference=None):
        return {"health": real.health, "capabilities": real.capabilities,
                "verify_connector": lambda: real.verify_connector(reference)}[operation]()
    monkeypatch.setattr(integration_runtime, "control_request", control)
    adapter = integration_runtime.LocalIntegrationRuntime()
    first, second = asyncio.run(adapter.health()), asyncio.run(adapter.health())
    assert first["status"] == second["status"] == "healthy"
    assert first["last_checked_at"] != second["last_checked_at"]
    with db.begin_nested() as savepoint:
        plan = service.plan(db, store.root, IDENTITY, first, choices=choices)
        savepoint.rollback()
    try:
        active = asyncio.run(service.activate(db, store.root, IDENTITY, plan["approval_digest"], adapter, choices=choices))
        assert active.version == IDENTITY.version
    finally:
        real.jobs.shutdown()


@pytest.mark.parametrize("trigger", ["schedule", "onboarding", "retry"])
def test_local_acceptance_rejects_automatic_discovery(db, staged, trigger):
    store, _, _, row, _, choices = staged
    plan = preview(db, staged)
    asyncio.run(service.activate(db, store.root, IDENTITY, plan["approval_digest"], runtime(staged), choices=choices))
    with pytest.raises(ValueError, match="manual"):
        asyncio.run(discovery.create_run(db, row, trigger=trigger))


def test_artifact_inspection_does_not_expire_with_execution_lease(staged, monkeypatch):
    store, stored, _, _, _, _ = staged
    now = time.time()
    monkeypatch.setattr(authority.time, "time", lambda: now + 49 * 3600)
    assert store.verify_connector(stored.connector_id, stored.version, stored.bundle_digest)["state"] == "verified"


def test_application_cannot_modify_enrollment_checkpoint(db, staged):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db
    from app.authorization import get_principal
    original = deepcopy(db.scalar(select(SystemSetting).where(SystemSetting.key == authority.DATABASE_KEY)).value_)
    principal = make_principal("system_settings.manage")
    db.add(principal.user)
    db.flush()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: principal
    try:
        response = TestClient(app).patch("/api/system-settings/" + authority.DATABASE_KEY, json={"value": {}})
        assert response.status_code == 409
    finally:
        app.dependency_overrides.clear()
    assert db.scalar(select(SystemSetting).where(SystemSetting.key == authority.DATABASE_KEY)).value_ == original


def test_boolean_only_isolation_report_is_insufficient():
    report = {"deployment": "disposable-tests", "checked_at": int(time.time()),
              "checks": {key: True for key in authority.ISOLATION_CHECKS}}
    with pytest.raises(ValueError, match="isolation"):
        authority.check_isolation(report)


def test_revocation_records_database_audit(db, staged):
    store, stored, _, _, _, _ = staged
    service.revoke(store.root, stored.verification["authorization_id"], db=db)
    assert db.scalar(select(AuditEvent).where(AuditEvent.event_type == "connector.local_release_revoked")) is not None


def activate(db, staged):
    store, _, _, _, _, choices = staged
    approval = preview(db, staged)
    return asyncio.run(service.activate(db, store.root, IDENTITY, approval["approval_digest"], runtime(staged), choices=choices))


def reference():
    return {"connector_id": IDENTITY.connector_id, "version": IDENTITY.version, "digest": IDENTITY.sha256}


def fresh_admission(staged, context, *, epoch=None):
    """A new OS process, no API/DB imports and no network access, on every call."""
    import subprocess
    import sys
    child = '''import json,sys,socket
from pathlib import Path
from atlas_runtime import local_release
from atlas_runtime.server import Runtime
p=json.load(sys.stdin)
local_release.BINDING=Path(p['binding']);local_release.DEPLOYMENT=Path(p['deployment'])
if p['epoch'] is not None: local_release.time.time=lambda:p['epoch']
def forbidden(*args,**kwargs):raise AssertionError('offline admission attempted network')
socket.socket=forbidden
r=Runtime('unused-offline-control',Path(p['store']),'development')
try:
 try:r.execution_admission(p['reference'],p['context']);print('authorized')
 except (ValueError,OSError):print('denied')
finally:r.jobs.shutdown()
'''
    result = subprocess.run([sys.executable, "-c", child], input=json.dumps({"store": str(staged[0].root),
        "binding": str(authority.BINDING), "deployment": str(authority.DEPLOYMENT), "context": context,
        "reference": reference(), "epoch": epoch}).encode(), capture_output=True, timeout=10, check=True)
    return result.stdout.decode().strip()


def fresh_api_admission(db, staged, epoch):
    """New API process and DB session; forbid public HTTP while retaining PostgreSQL."""
    import subprocess
    import sys
    from sqlalchemy import text
    child = '''import json,sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.services import local_release_authority as a,connector_lifecycle as lifecycle
from app.services.connector_store import PackageStore
from app.services.integration_connections import installed_manifest
import aiohttp
p=json.load(sys.stdin)
a.BINDING=Path(p['binding']);a.DEPLOYMENT=Path(p['deployment']);a.time.time=lambda:p['epoch']
lifecycle.package_store=lambda:PackageStore(Path(p['store']))
def forbidden(*args,**kwargs):raise AssertionError('offline API attempted HTTP')
aiohttp.ClientSession=forbidden
engine=create_engine(p['url'],hide_parameters=True,connect_args={'options':'-csearch_path='+p['schema']})
try:
 with Session(engine) as db:
  try:installed_manifest(db,'proxmox');print('authorized')
  except (ValueError,OSError):print('denied')
finally:engine.dispose()
'''
    result = subprocess.run([sys.executable, "-c", child], input=json.dumps({"url": db.get_bind().url.render_as_string(hide_password=False),
        "schema": db.scalar(text("SELECT current_schema()")), "store": str(staged[0].root), "binding": str(authority.BINDING),
        "deployment": str(authority.DEPLOYMENT), "epoch": epoch}).encode(), capture_output=True, timeout=10, check=True)
    return result.stdout.decode().strip()


@pytest.mark.parametrize("mutation", ["missing", "generation", "binding", "lease", "automatic"])
def test_runtime_independently_rejects_replayed_or_automatic_authority(db, staged, mutation):
    active = activate(db, staged)
    context = authority.execution_context(active)
    assert fresh_admission(staged, context) == "authorized"
    if mutation == "missing": context = None
    elif mutation == "automatic": context["trigger"] = "schedule"
    elif mutation == "binding": context["activation"]["binding_digest"] = "0" * 64
    elif mutation == "lease": context["activation"]["lease_id"] = str(uuid.uuid4())
    else: context["activation"]["generation"] = str(uuid.uuid4())
    assert fresh_admission(staged, context) == "denied"


def test_short_lived_approval_cannot_activate_after_expiry_or_be_reused(db, staged, monkeypatch):
    store, _, _, _, _, choices = staged
    plan = preview(db, staged)
    with monkeypatch.context() as patch:
        patch.setattr(authority.time, "time", lambda: plan["approval"]["expires_at"])
        with pytest.raises(ValueError, match="approval_expired"):
            asyncio.run(service.activate(db, store.root, IDENTITY, plan["approval_digest"], runtime(staged), choices=choices))
    active = asyncio.run(service.activate(db, store.root, IDENTITY, plan["approval_digest"], runtime(staged), choices=choices))
    with pytest.raises(ValueError, match="approval_consumed"):
        asyncio.run(service.activate(db, store.root, IDENTITY, plan["approval_digest"], runtime(staged), choices=choices))
    assert fresh_admission(staged, authority.execution_context(active)) == "authorized"


def maintenance_plan(db, staged, action):
    store, _, bound, _, health, _ = staged
    isolation = {**bound["isolation"], "checked_at": int(time.time())}
    with db.begin_nested() as savepoint:
        plan = service.plan(db, store.root, IDENTITY, health, action=action, isolation=isolation)
        savepoint.rollback()
    return plan, isolation


def test_expiry_reviewed_renewal_and_offline_restart_do_not_change_artifact_evidence(db, staged, monkeypatch):
    store, stored, _, _, _, _ = staged
    active = activate(db, staged)
    before = deepcopy(authority.execution_context(active))
    receipt = store._path(stored.connector_id, stored.version, stored.bundle_digest) / "verification.json"
    original = receipt.read_bytes()
    def offline(*args, **kwargs): pytest.fail("renewal attempted public-origin retrieval")
    monkeypatch.setattr(service, "GithubReader", offline)
    expiry = before["activation"]["expires_at"]
    assert fresh_admission(staged, before, epoch=expiry - 1) == "authorized"
    assert fresh_admission(staged, before, epoch=expiry) == "denied"
    assert fresh_api_admission(db, staged, expiry - 1) == "authorized"
    assert fresh_api_admission(db, staged, expiry) == "denied"
    monkeypatch.setattr(authority.time, "time", lambda: expiry + 1)
    assert authority.effective_status(active)["status"] == "expired"
    with pytest.raises(ValueError):
        installed_manifest(db, "proxmox")
    plan, isolation = maintenance_plan(db, staged, "renew")
    renewed = asyncio.run(service.maintain_execution(db, store.root, IDENTITY, plan["approval_digest"], runtime(staged), action="renew", isolation=isolation))
    after = authority.execution_context(renewed)
    assert after["activation"]["generation"] == before["activation"]["generation"]
    assert after["activation"]["lease_id"] != before["activation"]["lease_id"]
    assert receipt.read_bytes() == original
    assert fresh_admission(staged, before, epoch=expiry + 2) == "denied"
    assert fresh_admission(staged, after, epoch=expiry + 2) == "authorized"
    assert fresh_api_admission(db, staged, expiry + 2) == "authorized"
    assert fresh_admission(staged, after, epoch=after["activation"]["expires_at"]) == "denied"
    with pytest.raises(ValueError, match="approval_consumed"):
        asyncio.run(service.maintain_execution(db, store.root, IDENTITY, plan["approval_digest"], runtime(staged), action="renew", isolation=isolation))


def test_postcommit_write_failure_requires_reviewed_audited_recovery(db, staged, monkeypatch):
    from sqlalchemy.orm import Session
    store, _, _, _, _, choices = staged
    plan = preview(db, staged)
    original = authority.publish
    def fail(path, raw):
        if path.suffix == ".pending":
            raise OSError("simulated post-commit disk failure")
        return original(path, raw)
    with monkeypatch.context() as patch:
        patch.setattr(authority, "publish", fail)
        with pytest.raises(ValueError, match="committed_execution_denied_recovery_required"):
            asyncio.run(service.activate(db, store.root, IDENTITY, plan["approval_digest"], runtime(staged), choices=choices))
    with Session(db.get_bind()) as independent:
        active = independent.get(InstalledConnectorPackage, "proxmox")
        context = authority.execution_context(active)
        assert active.version == IDENTITY.version
        assert authority.effective_status(active)["status"] == "recovery_required"
        assert independent.scalar(select(AuditEvent.id).where(AuditEvent.event_type == "connector.local_release_activated"))
        assert independent.scalar(select(AuditEvent.id).where(AuditEvent.event_type == "connector.local_execution_publication_failed"))
    assert fresh_admission(staged, context) == "denied"
    plan, isolation = maintenance_plan(db, staged, "recover")
    recovered = asyncio.run(service.maintain_execution(db, store.root, IDENTITY, plan["approval_digest"], runtime(staged), action="recover", isolation=isolation))
    assert authority.execution_context(recovered) == context  # recovery cannot extend expiry
    assert fresh_admission(staged, context) == "authorized"
    assert db.scalar(select(AuditEvent.id).where(AuditEvent.event_type == "connector.local_execution_recovery_requested"))


@pytest.mark.parametrize("previously_active", [False, True])
def test_failed_database_commit_never_publishes_execution_or_reusable_approval(db, staged, monkeypatch, previously_active):
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import SQLAlchemyError
    store, _, _, _, _, choices = staged
    previous = authority.execution_context(activate(db, staged)) if previously_active else None
    expected_version = IDENTITY.version if previously_active else "1.0.0"
    plan = preview(db, staged)
    def fail(): raise SQLAlchemyError("simulated commit failure")
    with monkeypatch.context() as patch:
        patch.setattr(db, "commit", fail)
        with pytest.raises(SQLAlchemyError):
            asyncio.run(service.activate(db, store.root, IDENTITY, plan["approval_digest"], runtime(staged), choices=choices))
    db.rollback()
    with Session(db.get_bind()) as independent:
        assert independent.get(InstalledConnectorPackage, "proxmox").version == expected_version
    assert not authority.execution_path(store.root, "proxmox").exists()
    assert fresh_admission(staged, previous) == "denied"
    with pytest.raises(ValueError, match="approval_consumed"):
        asyncio.run(service.activate(db, store.root, IDENTITY, plan["approval_digest"], runtime(staged), choices=choices))


def test_reactivation_invalidates_old_generation_and_revocation_blocks_renewal(db, staged):
    first = deepcopy(authority.execution_context(activate(db, staged)))
    second = authority.execution_context(activate(db, staged))
    assert first["activation"]["generation"] != second["activation"]["generation"]
    assert fresh_admission(staged, first) == "denied"
    assert fresh_admission(staged, second) == "authorized"
    service.revoke(staged[0].root, staged[1].verification["authorization_id"], db=db)
    assert fresh_admission(staged, second) == "denied"
    with pytest.raises(ValueError, match="revoked"):
        maintenance_plan(db, staged, "renew")


def test_revocation_database_outage_keeps_durable_denial_and_reconciles_idempotently(db, staged, monkeypatch):
    from app import database
    context = authority.execution_context(activate(db, staged))
    def unavailable(): raise OSError("disposable database unavailable")
    monkeypatch.setattr(database, "SessionLocal", unavailable)
    result = service.revoke(staged[0].root, staged[1].verification["authorization_id"])
    assert result == {"status": "revoked", "audit": "reconciliation_required"}
    assert fresh_admission(staged, context) == "denied"
    for _ in range(2):
        assert service.reconcile_revocation(staged[0].root, staged[1].verification["authorization_id"], db=db)["audit"] == "recorded"
    assert len(list(db.scalars(select(AuditEvent).where(AuditEvent.event_type == "connector.local_release_revoked")))) == 1


@pytest.mark.parametrize("resource", ["database", "deployment", "store", "public", "private"])
def test_enrollment_rejects_substituted_inspected_resources(db, unenrolled, resource):
    store, report = unenrolled
    altered = deepcopy(report)
    if resource == "database": altered["resources"]["database"]["cluster_id"] = "substitute"
    elif resource == "deployment": altered["resources"]["deployment"]["deployment_id"] = str(uuid.uuid4())
    else: altered["resources"]["storage"][resource]["inode"] += 1
    with pytest.raises(ValueError, match="isolation_required"):
        authority.provision(db, store.root, altered)
    assert not authority.BINDING.exists() and not authority.PRIVATE_KEY.exists()


def test_direct_staged_discovery_and_spoofed_generation_fail_actual_admission(staged):
    from atlas_runtime.server import Runtime
    store = staged[0]
    fresh = Runtime(secrets.token_hex(48), store.root, "development")
    try:
        with pytest.raises(ValueError, match="package_unavailable"):
            fresh.execution_admission(reference(), {"activation": {"generation": str(uuid.uuid4())}, "trigger": "manual"})
        payload = {"request_id": str(uuid.uuid4()), "run_id": "", "integration_id": str(uuid.uuid4()),
            "reference": reference(), "config": {}, "credentials": {}, "selected_scopes": [], "object_classes": [],
            "coverage": {}, "ingestion_token": secrets.token_hex(12), "timeout_seconds": 60}
        payload["run_id"] = payload["request_id"]
        with pytest.raises(ValueError, match="package_unavailable"):
            fresh.run_discovery(payload)
    finally:
        fresh.jobs.shutdown()


def test_connection_creation_and_schedule_endpoints_enforce_manual_only(db, staged, configured):
    from app.routes import integration_connections as connections, integration_discovery as routes
    active = activate(db, staged)
    row, principal, _, _ = configured
    payload = connections.ConnectionCreate(creation_key=uuid.uuid4(), name="Manual acceptance connection",
        customer_id=row.customer_id, site_id=row.site_id, connector_id="proxmox", config=row.config_json,
        credentials={"token_id": secrets.token_hex(12), "token_secret": secrets.token_hex(24)}, selected_scopes=row.selected_scopes)
    result = asyncio.run(connections.create_integration(payload, request(), principal, db))
    assert result["schedule_preset"] == "manual" and result["next_run_at"] is None
    assert not list(db.scalars(select(DiscoveryRun)))
    identifier = result["id"]
    detail = connections.integration_detail(identifier, principal, db)
    assert detail["scheduling_capable"] is False and detail["discovery_capable"] is True
    with pytest.raises(HTTPException) as denied:
        asyncio.run(routes.set_schedule(identifier, routes.ScheduleInput(preset="hourly"), request(), principal, db))
    assert denied.value.status_code == 409
    assert asyncio.run(routes.set_schedule(identifier, routes.ScheduleInput(preset="manual"), request(), principal, db))["preset"] == "manual"
    with pytest.raises(HTTPException) as denied:
        asyncio.run(routes.initial_discovery(identifier, request(), principal, db))
    assert denied.value.status_code == 409
    run = asyncio.run(routes.run_now(identifier, request(), principal, db))
    assert run["status"] == "pending"
    assert db.get(DiscoveryRun, run["id"]).execution_provenance["local_execution"] == authority.execution_context(active)


def test_worker_rejects_preexisting_automatic_intent_after_local_activation(db, staged, monkeypatch):
    activate(db, staged)
    row = staged[3]
    run = asyncio.run(discovery.create_run(db, row))
    values = {column.key: deepcopy(getattr(run, column.key)) for column in run.__mapper__.columns}
    discovery.cancel_intent(run)
    db.commit()
    values.update(id=uuid.uuid4(), execution_provenance={**values["execution_provenance"], "trigger": "schedule"})
    automatic = DiscoveryRun(**values)
    db.add(automatic)
    db.commit()
    calls = []
    async def forbidden(payload):
        calls.append(payload)
        pytest.fail("automatic local acceptance intent reached runtime transport")
    monkeypatch.setattr(discovery.runtime, "run_discovery", forbidden)
    asyncio.run(discovery.dispatch(db, automatic.id))
    assert automatic.status == "failed" and automatic.dispatch_state == "settled" and not calls


def test_unrevoked_local_authority_cannot_be_replaced_through_ordinary_lifecycle(db, staged):
    from app.services import connector_lifecycle as lifecycle
    active = activate(db, staged)
    with pytest.raises((ValueError, OSError)):
        lifecycle.require_local_revoked(active)
    context = authority.execution_context(active)
    assert fresh_admission(staged, context) == "authorized"
    service.revoke(staged[0].root, staged[1].verification["authorization_id"], db=db)
    lifecycle.require_local_revoked(active)
    assert fresh_admission(staged, context) == "denied"


def test_effective_status_checks_database_binding_separately_from_active_record(db, staged):
    from app.services import connector_lifecycle as lifecycle
    active = activate(db, staged)
    assert lifecycle.installed_response(active, db=db)["local_execution"]["status"] == "authorized"
    checkpoint = db.scalar(select(SystemSetting).where(SystemSetting.key == authority.DATABASE_KEY))
    checkpoint.value_ = {}
    db.flush()
    value = lifecycle.installed_response(active, db=db)
    assert value["status"] == "active" and value["local_execution"]["status"] == "denied"


def test_independent_postgres_session_mutation_invalidates_approval(db, staged):
    from sqlalchemy.orm import Session
    store, _, _, row, _, choices = staged
    plan = preview(db, staged)
    identifier = row.id
    db.rollback()  # release preview locks; the next mutation uses a separate connection
    with Session(db.get_bind()) as other:
        other.get(Integration, identifier).name = "Committed independent-session change"
        other.commit()
    with pytest.raises(ValueError, match="stale_approval"):
        asyncio.run(service.activate(db, store.root, IDENTITY, plan["approval_digest"], runtime(staged), choices=choices))


def test_activation_uses_real_postgres_locks_and_publishes_only_after_commit(db, staged):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    from sqlalchemy.orm import Session
    store, _, _, row, _, choices = staged
    identifier = row.id
    plan = preview(db, staged)
    db.rollback()
    entered, release = threading.Event(), threading.Event()
    transport = runtime(staged)
    original = transport.verify_connector
    async def pause(reference):
        entered.set()
        assert release.wait(10)
        return await original(reference)
    transport.verify_connector = pause
    def install():
        with Session(db.get_bind(), expire_on_commit=False) as session:
            active = asyncio.run(service.activate(session, store.root, IDENTITY, plan["approval_digest"], transport, choices=choices))
            return authority.execution_context(active)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(install)
        assert entered.wait(10)
        try:
            with Session(db.get_bind()) as other:
                assert other.get(InstalledConnectorPackage, "proxmox").version == "1.0.0"
                other.execute(text("SET LOCAL lock_timeout = '200ms'"))
                with pytest.raises(DBAPIError):
                    other.execute(text("UPDATE integrations SET name='racing' WHERE id=:id"), {"id": identifier})
            assert fresh_admission(staged, None) == "denied"
            with Session(db.get_bind(), expire_on_commit=False) as other:
                with pytest.raises(ValueError, match="operation_in_progress"):
                    asyncio.run(service.activate(other, store.root, IDENTITY, plan["approval_digest"], runtime(staged), choices=choices))
        finally:
            release.set()
        context = future.result(timeout=15)
    assert fresh_admission(staged, context) == "authorized"
