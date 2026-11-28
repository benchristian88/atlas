"""Authenticated save regression against one Uvicorn loop and real PostgreSQL."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import secrets
import socket
from threading import Event, Thread
from time import monotonic, sleep
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
from anyio import from_thread
import jwt.api_jwt
import pytest
from sqlalchemy import delete, select, text, update
import uvicorn

from app import auth
from app.auth import COOKIE_NAME
from app.main import app
from app.models import (
    AccessAssignment, AuditEvent, ConnectorMapping, DataSource, DiscoveryRun, DiscoveryRunDebugTrace,
    InstalledConnectorPackage, Integration, IntegrationSecret, Permission, RolePermission, SystemSetting, User,
)
from app.routes import integration_connections
from app.services import connector_catalogue, connector_lifecycle, discovery_orchestration
from app.services.backups import RESTORE_EPOCH_KEY, restore_epoch
from app.services.connector_store import PackageStore
from app.services.integration_runtime import _approved_baseline, runtime
from app.services.integration_secrets import AtlasEncryptedSecretProvider
from app.services.integration_transactions import run_integration_write
from tests.i3_fixtures import fixture_bundle
from tests.test_onboarding_postgres import env, pytestmark


def test_cancelled_request_waits_for_its_dispatched_write_to_finish():
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        completed = Event()

        async def runtime_call():
            entered.set()
            await release.wait()

        def write():
            from_thread.run(runtime_call)
            completed.set()

        task = asyncio.create_task(run_integration_write(write))
        try:
            await asyncio.wait_for(entered.wait(), 3)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
            assert not completed.is_set()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        assert completed.is_set()

    asyncio.run(scenario())


def test_overlapping_creates_keep_api_responsive_and_retry_exactly_once(env, tmp_path, monkeypatch):
    pair = env.pair()
    permissions = {"integrations.view", "integrations.manage", "integrations.run"}
    actor = env.actor(permissions, "site", pair.customer.id, pair.site.id)
    second = env.actor(permissions, "site", pair.customer.id, pair.site.id)
    customer_id, site_id = pair.customer.id, pair.site.id
    package, verifier = fixture_bundle(tmp_path)
    store = PackageStore(tmp_path / "store")
    stored = store.install(package, verifier)
    health = {**_approved_baseline(), "status": "healthy", "packaging_mode": "development",
        "capabilities": {"operations": ["run_discovery", "get_job", "cancel_job"], "aip_versions": ["1.0"]}}
    entered, release, listening = Event(), Event(), Event()
    calls, hints = [], []

    async def gated_health():
        calls.append(None)
        # Park the first save after its Data Source and credentials are staged,
        # immediately before its initial discovery intent is prepared.
        if len(calls) == 2:
            entered.set()
            if not await asyncio.to_thread(release.wait, 12):
                raise TimeoutError("Test did not release the runtime response")
        return health

    monkeypatch.setattr(runtime, "health", gated_health)
    monkeypatch.setattr(connector_lifecycle, "package_store", lambda: store)
    monkeypatch.setattr(discovery_orchestration, "enqueue", hints.append)
    monkeypatch.setenv("ATLAS_DATA_ENCRYPTION_KEY", secrets.token_hex(32))
    with env.sessions.begin() as db:
        connector_lifecycle.activate(db, stored, health)

    config = uvicorn.Config(app, host="127.0.0.1", port=0, workers=1, log_level="warning")

    class Server(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            listening.set()

    server = Server(config)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
        thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        first_body = {"creation_key": str(uuid4()), "name": "First connection",
            "customer_id": str(customer_id), "site_id": str(site_id), "connector_id": stored.connector_id,
            "expected_connector_digest": stored.bundle_digest.removeprefix("sha256:"),
            "config": {"endpoint": "https://example.test", "token_id": "fixture", "verify_tls": True},
            "credentials": {"token_secret": secrets.token_urlsafe(32)}, "selected_scopes": ["inventory"]}
        second_body = {**first_body, "creation_key": str(uuid4()), "name": "Second connection",
            "start_initial_discovery": False}
        try:
            assert listening.wait(6) and server.started
            with (httpx.Client(base_url=origin, cookies=actor.client.cookies, timeout=15, trust_env=False) as a,
                  httpx.Client(base_url=origin, cookies=second.client.cookies, timeout=1, trust_env=False) as b,
                  ThreadPoolExecutor(max_workers=1) as executor):
                saving = executor.submit(a.post, "/api/integrations", json=first_body)
                try:
                    assert entered.wait(5), "Save did not reach initial discovery"
                    for payload in (first_body, second_body):
                        busy = b.post("/api/integrations", json=payload)
                        assert busy.status_code == 409
                        assert busy.json()["detail"]["code"] == "integration_save_busy"
                        assert b.get("/api/health").status_code == 200
                        assert b.get("/api/auth/me").json()["id"] == str(second.id)
                    with env.sessions() as db:
                        assert db.scalar(select(Integration.id).where(Integration.site_id == site_id)) is None
                        assert db.scalar(select(DataSource.id).where(DataSource.site_id == site_id)) is None
                finally:
                    release.set()
                saved = saving.result()
                assert saved.status_code == 201
                replay = b.post("/api/integrations", json=first_body)
                assert replay.status_code == 201 and replay.json()["id"] == saved.json()["id"]
                separate = b.post("/api/integrations", json=second_body)
                assert separate.status_code == 201 and separate.json()["id"] != saved.json()["id"]
                assert len(calls) == 3
                write_only = first_body["credentials"]["token_secret"] not in saved.text
                assert write_only, "Save exposed the fixture credential"
                with env.sessions() as db:
                    row = db.get(Integration, UUID(saved.json()["id"]))
                    source = db.get(DataSource, row.data_source_id)
                    assert (source.customer_id, source.site_id, source.source_type) == (customer_id, site_id, "connector")
                    assert (row.connector_version, row.connector_digest) == (
                        stored.version, stored.bundle_digest.removeprefix("sha256:"))
                    with AtlasEncryptedSecretProvider(db).materialize_for_job(row, uuid4(), ["token_secret"]) as lease:
                        credentials_match = lease.values == first_body["credentials"]
                        assert credentials_match, "Persisted credentials differ from the submitted values"
                    [run] = db.scalars(select(DiscoveryRun).where(DiscoveryRun.site_id == site_id))
                    assert (run.integration_id, run.data_source_id, run.dispatch_state, run.created_by_user_id) == (
                        row.id, source.id, "pending", actor.id)
                    assert hints == [run.id]
                    audits = db.execute(select(AuditEvent.event_type, AuditEvent.user_id)
                        .where(AuditEvent.target_id == row.id).order_by(AuditEvent.event_type)).all()
                    assert audits == [("integration.created", actor.id), ("integration.credential_configured", actor.id)]
        finally:
            release.set()
            server.should_exit = True
            thread.join(20)
            assert not thread.is_alive()
            with env.sessions.begin() as db:
                db.execute(delete(DiscoveryRun).where(DiscoveryRun.site_id == site_id))
                db.execute(delete(IntegrationSecret).where(IntegrationSecret.site_id == site_id))
                db.execute(delete(Integration).where(Integration.site_id == site_id))
                db.execute(delete(AuditEvent).where(AuditEvent.site_id == site_id))
                db.execute(delete(ConnectorMapping).where(ConnectorMapping.connector_id == stored.connector_id))
                db.execute(delete(InstalledConnectorPackage).where(InstalledConnectorPackage.connector_id == stored.connector_id))


@pytest.fixture
def authorization_case(env, tmp_path, monkeypatch, request):
    pair = env.pair()
    package, verifier = fixture_bundle(tmp_path, scheduling=getattr(request, "param", True))
    store = PackageStore(tmp_path / "authority-store")
    health = {**_approved_baseline(), "status": "healthy", "packaging_mode": "development",
        "capabilities": {"operations": ["run_discovery", "get_job", "cancel_job"], "aip_versions": ["1.0"]}}
    references, hints = [], []

    async def report_health():
        return health

    async def verify_reference(reference):
        references.append(reference)
        store.verify_connector(reference["connector_id"], reference["version"], "sha256:" + reference["digest"])
        return {**reference, "state": "verified"}

    monkeypatch.setattr(connector_catalogue, "catalogue", SimpleNamespace(
        get=lambda connector_id, version: package, verifier=lambda: verifier))
    monkeypatch.setattr(connector_lifecycle, "package_store", lambda: store)
    monkeypatch.setattr(runtime, "health", report_health)
    monkeypatch.setattr(runtime, "verify_connector", verify_reference)
    monkeypatch.setattr(discovery_orchestration, "enqueue", hints.append)
    monkeypatch.setenv("ATLAS_DATA_ENCRYPTION_KEY", secrets.token_hex(32))
    try:
        yield SimpleNamespace(pair=pair, package=package, verifier=verifier, store=store,
            health=health, references=references, hints=hints)
    finally:
        with env.sessions.begin() as db:
            for model in (DiscoveryRun, IntegrationSecret, Integration, AuditEvent):
                db.execute(delete(model).where(model.site_id == pair.site.id))
            db.execute(delete(ConnectorMapping).where(ConnectorMapping.connector_id == package.connector_id))
            db.execute(delete(InstalledConnectorPackage).where(InstalledConnectorPackage.connector_id == package.connector_id))


def wait_for_lock_waiter(db):
    blocker = db.scalar(text("SELECT pg_backend_pid()"))
    deadline = monotonic() + 5
    with db.get_bind().connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
        while monotonic() < deadline:
            if observer.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                    "WHERE :blocker = ANY(pg_blocking_pids(pid)))"), {"blocker": blocker}):
                return
            sleep(0.02)
    pytest.fail("Request did not wait for the PostgreSQL lock")


def connection_payload(case, *, start_initial_discovery=True):
    return {"creation_key": str(uuid4()), "name": "Staged connection",
        "customer_id": str(case.pair.customer.id), "site_id": str(case.pair.site.id),
        "connector_id": case.package.connector_id,
        "expected_connector_digest": case.package.bundle_digest.removeprefix("sha256:"),
        "config": {"endpoint": "https://example.test", "token_id": "fixture", "verify_tls": True},
        "credentials": {"token_secret": secrets.token_urlsafe(32)}, "selected_scopes": ["inventory"],
        "start_initial_discovery": start_initial_discovery}


def assert_invalid_session(result):
    assert result.status_code == 401
    assert result.json() == {"detail": "Authentication required"}
    assert result.headers["WWW-Authenticate"] == "Bearer"


def invalidate_session(env, actor):
    with env.sessions.begin() as db:
        db.get(User, actor.id).session_version += 1


def assert_no_saved_state(env, site_id):
    with env.sessions() as db:
        for model in (Integration, DataSource, IntegrationSecret, DiscoveryRun, AuditEvent):
            assert db.scalar(select(model.id).where(model.site_id == site_id)) is None, model.__name__


@pytest.fixture
def active_connector(env, authorization_case):
    case = authorization_case
    stored = case.store.install(case.package, case.verifier)
    with env.sessions.begin() as db:
        connector_lifecycle.activate(db, stored, case.health)
    return case


@pytest.mark.parametrize("checkpoint", ["connector_lock", "before_commit"])
@pytest.mark.parametrize("revocation", ["grant", "session"])
def test_activation_rechecks_authority(env, authorization_case, monkeypatch, checkpoint, revocation):
    case = authorization_case
    actor = env.actor({"integration_runtime.manage"})
    path = f"/api/integration-catalogue/{case.package.connector_id}/activate"
    payload = {"version": case.package.version, "digest": case.package.bundle_digest.removeprefix("sha256:")}
    entered, release = Event(), Event()
    activate = connector_lifecycle.activate

    def stage_activation(*args, **kwargs):
        active = activate(*args, **kwargs)
        entered.set()
        assert release.wait(6), "Test did not release the staged activation"
        return active

    if checkpoint == "before_commit":
        monkeypatch.setattr(connector_lifecycle, "activate", stage_activation)

    def revoke():
        if revocation == "session":
            invalidate_session(env, actor)
            return
        with env.sessions.begin() as db:
            db.execute(delete(AccessAssignment).where(AccessAssignment.id == actor.grant))

    with ThreadPoolExecutor(max_workers=1) as pool:
        if checkpoint == "connector_lock":
            with env.sessions.begin() as lock_db:
                connector_lifecycle.lock_connector(lock_db, case.package.connector_id)
                request = pool.submit(actor.client.post, path, json=payload)
                wait_for_lock_waiter(lock_db)
                revoke()
        else:
            request = pool.submit(actor.client.post, path, json=payload)
            try:
                assert entered.wait(5), "Activation did not stage its database writes"
                revoke()
            finally:
                release.set()
        result = request.result(timeout=8)
    try:
        if revocation == "session":
            assert_invalid_session(actor.client.get("/api/auth/me"))
            assert_invalid_session(result)
        else:
            assert result.status_code == 403
        with env.sessions() as db:
            assert db.get(InstalledConnectorPackage, case.package.connector_id) is None
            assert db.scalar(select(ConnectorMapping.id)
                .where(ConnectorMapping.connector_id == case.package.connector_id)) is None
            assert db.scalar(select(AuditEvent.id).where(AuditEvent.user_id == actor.id)) is None
        assert len(case.references) == (0 if checkpoint == "connector_lock" else 1)
    finally:
        # Also remove the mutation audit if this regression runs against the broken code.
        with env.sessions.begin() as db:
            db.execute(delete(AuditEvent).where(AuditEvent.user_id == actor.id))


@pytest.mark.parametrize("restriction", ["password_change", "session", "inactive"])
def test_staged_save_rolls_back_when_actor_loses_authority(env, active_connector, monkeypatch, restriction):
    case = active_connector
    customer_id, site_id = case.pair.customer.id, case.pair.site.id
    actor = env.actor({"integrations.manage", "integrations.run"}, "site", customer_id, site_id)
    entered, release = Event(), Event()
    create_run = discovery_orchestration.create_run_sync

    def stage_run(db, row, **kwargs):
        run = create_run(db, row, **kwargs)
        assert db.get(DataSource, row.data_source_id) is not None
        assert db.get(IntegrationSecret, row.credential_reference) is not None
        assert db.get(DiscoveryRun, run.id) is not None
        entered.set()
        assert release.wait(6), "Test did not release the staged save"
        return run

    monkeypatch.setattr(discovery_orchestration, "create_run_sync", stage_run)
    with ThreadPoolExecutor(max_workers=1) as pool:
        saving = pool.submit(actor.client.post, "/api/integrations", json=connection_payload(case))
        try:
            assert entered.wait(5), "Save did not stage initial discovery"
            if restriction == "session":
                invalidate_session(env, actor)
            else:
                with env.sessions.begin() as db:
                    user = db.get(User, actor.id)
                    if restriction == "inactive":
                        user.is_active = False
                    else:
                        user.force_password_change = True
        finally:
            release.set()
        result = saving.result(timeout=8)
    if restriction == "password_change":
        assert result.status_code == 403
        assert result.json()["detail"] == "You must change your password before continuing"
    else:
        assert_invalid_session(actor.client.get("/api/auth/me"))
        assert_invalid_session(result)
    assert_no_saved_state(env, site_id)
    assert case.hints == []


@pytest.mark.parametrize("operation", ["run", "initial-discovery", "test-connection", "schedule"])
@pytest.mark.parametrize("revocation", ["scope", "session"])
def test_saved_integration_writer_rechecks_authority_after_connector_lock(env, active_connector, operation, revocation):
    case = active_connector
    customer_id, site_id = case.pair.customer.id, case.pair.site.id
    actor = env.actor({"integrations.manage", "integrations.run"}, "site", customer_id, site_id)
    saved = actor.client.post("/api/integrations", json=connection_payload(case, start_initial_discovery=False))
    assert saved.status_code == 201
    integration_id = UUID(saved.json()["id"])
    path = f"/api/integrations/{integration_id}/{operation}"
    method, body = ("PUT", {"preset": "daily"}) if operation == "schedule" else ("POST", None)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with env.sessions.begin() as lock_db:
            connector_lifecycle.lock_connector(lock_db, case.package.connector_id)
            request = pool.submit(actor.client.request, method, path, json=body)
            wait_for_lock_waiter(lock_db)
            if revocation == "session":
                invalidate_session(env, actor)
            else:
                with env.sessions.begin() as db:
                    db.execute(delete(AccessAssignment).where(AccessAssignment.id == actor.grant))
        result = request.result(timeout=8)
    if revocation == "session":
        assert_invalid_session(result)
    else:
        assert result.status_code == 404
    with env.sessions() as db:
        row = db.get(Integration, integration_id)
        assert (row.schedule_preset, row.last_test_at) == ("manual", None)
        assert db.scalar(select(DiscoveryRun.id).where(DiscoveryRun.integration_id == row.id)) is None
        actions = set(db.scalars(select(AuditEvent.event_type).where(AuditEvent.site_id == site_id)))
        assert actions == {"integration.created", "integration.credential_configured"}
    assert case.hints == []


@pytest.mark.parametrize("revocation", ["grant", "session"])
def test_debug_delete_rechecks_authority_after_run_lock(env, active_connector, monkeypatch, revocation):
    case = active_connector
    actor = env.actor({"integrations.manage", "integrations.run", "integrations.view", "integration_runtime.manage"})
    saved = actor.client.post("/api/integrations", json=connection_payload(case))
    assert saved.status_code == 201
    [run_id] = case.hints
    runtime_deletions = []

    async def get_job(*args, **kwargs):
        runtime_deletions.append((args, kwargs))
        return {}

    monkeypatch.setattr(runtime, "get_job", get_job)
    with env.sessions.begin() as db:
        db.get(DiscoveryRun, run_id).runtime_job_id = uuid4()
        db.add(DiscoveryRunDebugTrace(discovery_run_id=run_id, expires_at=discovery_orchestration.utcnow(), events=[]))

    with ThreadPoolExecutor(max_workers=1) as pool:
        with env.sessions.begin() as lock_db:
            lock_db.get(DiscoveryRun, run_id, with_for_update=True)
            request = pool.submit(actor.client.delete, f"/api/discovery-runs/{run_id}/debug-trace")
            wait_for_lock_waiter(lock_db)
            if revocation == "session":
                invalidate_session(env, actor)
            else:
                with env.sessions.begin() as db:
                    db.execute(delete(AccessAssignment).where(AccessAssignment.id == actor.grant))
        result = request.result(timeout=8)
    if revocation == "session":
        assert_invalid_session(result)
    else:
        assert result.status_code == 403
    with env.sessions() as db:
        assert db.get(DiscoveryRunDebugTrace, run_id) is not None
        assert db.get(DiscoveryRun, run_id).debug_deleted_at is None
        assert db.scalar(select(AuditEvent.id).where(AuditEvent.target_id == run_id)) is None
    assert runtime_deletions == []


@pytest.mark.parametrize("restriction", ["session", "expiry", "restore_epoch", "missing_user"])
def test_create_revalidates_originating_session_after_runtime_health(env, active_connector, monkeypatch, restriction):
    case = active_connector
    customer_id, site_id = case.pair.customer.id, case.pair.site.id
    actor = env.actor({"integrations.manage"}, "site", customer_id, site_id)
    entered, release = Event(), Event()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    expires_at = now + timedelta(seconds=60)
    original_epoch = None
    epoch_changed = False

    if restriction == "expiry":
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls.fromtimestamp(now.timestamp(), tz)

        monkeypatch.setattr(auth, "datetime", Clock)
        monkeypatch.setattr(jwt.api_jwt, "datetime", Clock)
        with env.sessions() as db:
            token = auth.create_session_token(db.get(User, actor.id), duration=expires_at - now,
                restore_epoch=restore_epoch(db))
        # Exercise bearer precedence over the longer-lived session cookie.
        actor.client.headers["Authorization"] = f"Bearer {token}"

    async def wait_for_health():
        entered.set()
        assert await asyncio.to_thread(release.wait, 6), "Test did not release runtime health"
        return case.health

    monkeypatch.setattr(runtime, "health", wait_for_health)
    try:
        assert actor.client.get("/api/auth/me").status_code == 200
        with ThreadPoolExecutor(max_workers=1) as pool:
            request = pool.submit(actor.client.post, "/api/integrations", json=connection_payload(case))
            try:
                assert entered.wait(5), "Save did not reach runtime health"
                if restriction == "session":
                    invalidate_session(env, actor)
                elif restriction == "expiry":
                    now = expires_at
                elif restriction == "missing_user":
                    with env.sessions.begin() as db:
                        db.delete(db.get(User, actor.id))
                else:
                    with env.sessions.begin() as db:
                        setting = db.scalar(select(SystemSetting).where(SystemSetting.key == RESTORE_EPOCH_KEY))
                        if setting is None:
                            db.add(SystemSetting(key=RESTORE_EPOCH_KEY, value_=str(uuid4())))
                        else:
                            original_epoch = setting.value_
                            setting.value_ = str(uuid4())
                    epoch_changed = True
                assert_invalid_session(actor.client.get("/api/auth/me"))
            finally:
                release.set()
            result = request.result(timeout=8)
        assert_invalid_session(result)
        assert_no_saved_state(env, site_id)
        assert case.hints == []
    finally:
        if epoch_changed:
            with env.sessions.begin() as db:
                setting = db.scalar(select(SystemSetting).where(SystemSetting.key == RESTORE_EPOCH_KEY))
                if original_epoch is not None:
                    setting.value_ = original_epoch
                elif setting is not None:
                    db.delete(setting)


def test_saved_probe_rolls_back_after_dispatched_runtime_work(env, active_connector, monkeypatch):
    case = active_connector
    customer_id, site_id = case.pair.customer.id, case.pair.site.id
    actor = env.actor({"integrations.manage", "integrations.run"}, "site", customer_id, site_id)
    saved = actor.client.post("/api/integrations", json=connection_payload(case, start_initial_discovery=False))
    assert saved.status_code == 201
    integration_id = UUID(saved.json()["id"])
    entered, release, completed = Event(), Event(), Event()

    async def probe(*args):
        entered.set()
        assert await asyncio.to_thread(release.wait, 6), "Test did not release the dispatched probe"
        completed.set()
        return {"success": True, "category": "connected", "source_version": "8.4.0", "compatibility": "compatible"}

    monkeypatch.setattr(integration_connections, "invoke", probe)
    with ThreadPoolExecutor(max_workers=1) as pool:
        request = pool.submit(actor.client.post, f"/api/integrations/{integration_id}/test-connection")
        try:
            assert entered.wait(5), "The request did not dispatch the probe"
            invalidate_session(env, actor)
        finally:
            release.set()
        result = request.result(timeout=8)
    assert completed.is_set()
    assert_invalid_session(result)
    with env.sessions() as db:
        row = db.get(Integration, integration_id)
        assert row.last_test_at is None
        assert set(db.scalars(select(AuditEvent.event_type).where(AuditEvent.target_id == row.id))) == {
            "integration.created", "integration.credential_configured",
        }
    assert case.hints == []


@pytest.mark.parametrize("authorization_case,preparation,authority,requested,enabled,schedule,run_exists", [
    (True, "success", "retained", True, True, "hourly", True),
    (True, "recoverable", "retained", True, True, "hourly", False),
    (True, "skipped", "manage_only", True, True, "manual", False),
    (True, "success", "withdrawn", True, True, None, False),
    (True, "recoverable", "withdrawn", True, True, None, False),
    (False, "success", "retained", True, True, "manual", True),
    (False, "recoverable", "withdrawn", True, True, "manual", False),
    (True, "skipped", "retained", False, True, "manual", False),
    (True, "integrity", "retained", True, True, None, False),
    (True, "skipped", "retained", True, False, "manual", False),
], indirect=["authorization_case"], ids=[
    "initial-run", "recoverable-with-schedule", "manage-only", "withdrawn-with-run", "withdrawn-with-schedule",
    "no-scheduling-capability", "withdrawn-without-intent", "explicit-opt-out", "integrity-failure", "disabled",
])
def test_create_checks_every_durable_discovery_intent(env, active_connector, monkeypatch,
        preparation, authority, requested, enabled, schedule, run_exists):
    case = active_connector
    customer_id, site_id = case.pair.customer.id, case.pair.site.id
    permissions = {"integrations.manage"}
    if authority != "manage_only":
        permissions.add("integrations.run")
    actor = env.actor(permissions, "site", customer_id, site_id)
    create_run = discovery_orchestration.create_run_sync
    entered, release = Event(), Event()
    preparations = []

    def prepare(db, row, **kwargs):
        preparations.append(row.id)
        if authority == "withdrawn":
            entered.set()
            assert release.wait(6), "Test did not release initial discovery preparation"
        run = create_run(db, row, **kwargs)
        if preparation == "integrity":
            db.execute(update(DiscoveryRun).where(DiscoveryRun.id == run.id).values(status=None))
        if preparation == "recoverable":
            raise discovery_orchestration.DiscoveryEligibilityError("runtime_unavailable")
        return run

    monkeypatch.setattr(discovery_orchestration, "create_run_sync", prepare)
    payload = {**connection_payload(case, start_initial_discovery=requested), "enabled": enabled}
    with ThreadPoolExecutor(max_workers=1) as pool:
        saving = pool.submit(actor.client.post, "/api/integrations", json=payload)
        if authority == "withdrawn":
            try:
                assert entered.wait(5), "Save did not reach initial discovery preparation"
                assert_no_saved_state(env, site_id)
                with env.sessions.begin() as db:
                    role_id = db.get(AccessAssignment, actor.grant).role_id
                    run_permission = select(Permission.id).where(Permission.key == "integrations.run").scalar_subquery()
                    db.execute(delete(RolePermission).where(RolePermission.role_id == role_id,
                        RolePermission.permission_id == run_permission))
            finally:
                release.set()
        saved = saving.result(timeout=8)

    if schedule is None:
        with env.sessions() as db:
            persisted = db.execute(select(Integration.schedule_preset, Integration.next_run_at)
                .where(Integration.site_id == site_id)).one_or_none()
        assert saved.status_code == (409 if preparation == "integrity" else 403), persisted
        if authority == "withdrawn":
            assert saved.json()["detail"] == "Discovery permission changed while saving the Integration"
        assert_no_saved_state(env, site_id)
        assert case.hints == []
        # The failed request did not claim the key. The same actor can retry a
        # configuration-only save on the same key, then replay the result.
        saved = actor.client.post("/api/integrations", json={**payload, "start_initial_discovery": False})
        assert saved.status_code == 201
        schedule = "manual"
        expected_error = None
    else:
        assert saved.status_code == 201
        expected_error = "initial_discovery_unavailable" if preparation == "recoverable" else None

    assert len(preparations) == (0 if preparation == "skipped" else 1)
    replay = actor.client.post("/api/integrations", json=payload)
    assert replay.status_code == 201 and replay.json() == saved.json()
    assert len(preparations) == (0 if preparation == "skipped" else 1)
    with env.sessions() as db:
        [row] = db.scalars(select(Integration).where(Integration.site_id == site_id))
        [source] = db.scalars(select(DataSource).where(DataSource.site_id == site_id))
        [credential] = db.scalars(select(IntegrationSecret).where(IntegrationSecret.site_id == site_id))
        assert (row.id, row.creation_key, row.data_source_id, row.credential_reference) == (
            UUID(saved.json()["id"]), UUID(payload["creation_key"]), source.id, credential.id,
        )
        assert row.schedule_preset == schedule
        assert (row.next_run_at is not None) == (schedule != "manual")
        assert row.last_error_code == expected_error
        runs = list(db.scalars(select(DiscoveryRun).where(DiscoveryRun.site_id == site_id)))
        if run_exists:
            [run] = runs
            assert (run.integration_id, run.data_source_id, run.dispatch_state, run.created_by_user_id) == (
                row.id, source.id, "pending", actor.id,
            )
            assert row.last_run_at == run.started_at
            assert case.hints == [run.id]
        else:
            assert runs == [] and row.last_run_at is None and case.hints == []
        assert set(db.execute(select(AuditEvent.event_type, AuditEvent.user_id).where(AuditEvent.site_id == site_id))) == {
            ("integration.created", actor.id), ("integration.credential_configured", actor.id),
        }
