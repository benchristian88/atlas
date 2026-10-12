"""Real PostgreSQL receipts, tokens, lifecycle and worker regression."""
import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
import os
from pathlib import Path
import secrets
import sys
import uuid

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.models import (Asset, AssetInterface, AssetType, Customer, DataSource, DiscoveryRun, DiscoveryBatchReceipt,
    EvidenceRecord, EntitySourceLink, Integration, KnowledgeAssertion, KnowledgeChange, Network, ReconciliationItem,
    RelationshipType, RunObservedEntity, Site, Workspace)
from app.services import aip_ingestion as aip, discovery_orchestration as orchestration, discovery_tokens as tokens
from app.services import connector_lifecycle as lifecycle
from app.services.connector_store import PackageStore
from app.services.integration_runtime import _approved_baseline
from app.services.integration_secrets import AtlasEncryptedSecretProvider
from app.services.reconciliation import accept_item, link_item_to_technical
from app.routes import integration_discovery as routes
from tests.i3_fixtures import fixture_bundle, message, ROOT
from tests.test_administration import make_principal, request

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")


@pytest.fixture
def db():
    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"], hide_parameters=True)
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()
    engine.dispose()


@pytest.fixture
def configured(db, tmp_path, monkeypatch):
    principal = make_principal("integrations.run", "integrations.view", "integrations.manage", "reconciliation.decide", "networks.create", "networks.edit")
    principal.user.email = uuid.uuid4().hex + "@example.test"; db.add(principal.user)
    workspace = Workspace(name="I3 fixture", slug=uuid.uuid4().hex); db.add(workspace); db.flush()
    customer = Customer(name="I3 customer", workspace_id=workspace.id); db.add(customer); db.flush()
    site = Site(name="I3 site", customer_id=customer.id); db.add(site); db.flush()
    for key in ["hypervisor_node", "virtual_machine"]:
        if db.scalar(select(AssetType).where(AssetType.key == key)) is None:
            db.add(AssetType(key=key, name=key, active=True, icon="server"))
    if db.scalar(select(RelationshipType).where(RelationshipType.key == "runs_on")) is None:
        db.add(RelationshipType(key="runs_on", name="Runs on", directional=True, active=True))
    db.flush()
    store = PackageStore(tmp_path / "store")
    monkeypatch.setattr(lifecycle, "package_store", lambda: store)
    package, verifier = fixture_bundle(tmp_path)
    stored = store.install(package, verifier)
    baseline = _approved_baseline()
    health = {**baseline, "status": "healthy", "packaging_mode": "development", "capabilities": {
        "operations": ["run_discovery", "get_job", "cancel_job"], "aip_versions": ["1.0"],
        "protocol_version": "integration-runtime-v1", "runtime_kind": "ansible", "dependencies": []}}
    lifecycle.activate(db, stored, health)
    async def healthy(): return health
    monkeypatch.setattr(orchestration.runtime, "health", healthy)
    monkeypatch.setenv("ATLAS_DATA_ENCRYPTION_KEY", secrets.token_hex(32))
    monkeypatch.setenv("AUTH_SECRET_KEY", secrets.token_hex(48))
    monkeypatch.setenv("ATLAS_STATE_DIR", str(tmp_path / "state"))
    (tmp_path / "state").mkdir(mode=0o700)
    (tmp_path / "state/requests.lock").touch(mode=0o600)
    tokens.provision_signing_key()
    source = DataSource(customer_id=customer.id, site_id=site.id, name="Test source", source_type="connector", status="active", trust_level="untrusted")
    db.add(source); db.flush()
    row = Integration(id=uuid.uuid4(), customer_id=customer.id, site_id=site.id, name="Test integration", plugin_id="i3-fixture",
        connector_id=stored.connector_id, connector_version=stored.version, connector_digest=stored.bundle_digest[7:],
        data_source_id=source.id, enabled=True, selected_scopes=["inventory"], config_json={"endpoint": "https://example.test", "token_id": "fixture-identity", "verify_tls": True},
        config_schema_version="1.0", creation_key=uuid.uuid4(), schedule_preset="manual", base_url="", username_or_token_id="", secret_reference="")
    db.add(row); db.flush()
    AtlasEncryptedSecretProvider(db).replace(row, {"token_secret": secrets.token_hex(24)})
    db.commit()
    return row, principal, store, health


def new_run(db, configured):
    row = configured[0]
    run = asyncio.run(orchestration.create_run(db, row, user_id=configured[1].user.id))
    run.ingestion_generation = uuid.uuid4(); run.deadline_at = orchestration.utcnow() + timedelta(minutes=10)
    db.commit()
    return run


def auth_request(token):
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [(b"authorization", ("Bearer " + token).encode())]})


def test_provenance_receipts_and_scope_database_guards(db, configured):
    run = new_run(db, configured)
    assert run.execution_provenance["connector_digest"] == configured[0].connector_digest
    for change in [{"execution_provenance": {"changed": True}}, {"coverage_key": "changed"}, {"site_id": uuid.uuid4()}]:
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text("UPDATE discovery_runs SET " + next(iter(change)) + " = :value WHERE id = :id"),
                {"value": json.dumps(next(iter(change.values()))) if "execution_provenance" in change else next(iter(change.values())), "id": run.id})
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(DiscoveryRun(integration_id=run.integration_id, data_source_id=run.data_source_id, customer_id=run.customer_id,
            site_id=run.site_id, status="pending", started_at=orchestration.utcnow(), execution_provenance=run.execution_provenance))
        db.flush()
    payload = message(run)
    assert not aip.accept_batch(db, run, payload)["replayed"]
    assert aip.accept_batch(db, run, deepcopy(payload))["replayed"]
    assert db.scalar(select(func.count()).select_from(EvidenceRecord).where(EvidenceRecord.discovery_run_id == run.id)) == 2
    assert db.scalar(select(func.count()).select_from(RunObservedEntity).where(RunObservedEntity.discovery_run_id == run.id)) == 2
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(text("UPDATE discovery_batch_receipts SET body_hash=:hash WHERE discovery_run_id=:id"), {"hash": "a"*64, "id": run.id})
    payload["assets"][0]["name"] = "Changed replay"
    with pytest.raises(aip.IngestionError, match="conflicting_receipt"):
        aip.accept_batch(db, run, payload)


@pytest.mark.parametrize("mutation", ["aud", "run_id", "integration_id", "exp", "jti", "tampered"])
def test_narrow_token_binding_and_revocation(db, configured, mutation):
    run = new_run(db, configured)
    original = tokens.mint(run)
    claims = tokens.decode(original)
    assert routes.authenticate_ingestion(db, auth_request(original), run.id)[0].id == run.id
    if mutation == "tampered":
        altered = original[:-8] + "badvalue"
    else:
        claims[mutation] = "normal-api" if mutation == "aud" else claims["iat"] - 1 if mutation == "exp" else str(uuid.uuid4())
        altered = jwt.encode(claims, tokens.signing_key(), algorithm="HS256")
    with pytest.raises(HTTPException) as error:
        routes.authenticate_ingestion(db, auth_request(altered), run.id)
    assert error.value.status_code == 401
    orchestration.cancel_intent(run)
    with pytest.raises(HTTPException): routes.authenticate_ingestion(db, auth_request(original), run.id)


def test_key_survives_restart_and_has_no_other_credential_authority(db, configured, tmp_path):
    key = tokens.signing_key()
    assert tokens.provision_signing_key() == key and tokens.key_path().stat().st_mode & 0o777 == 0o600
    token = tokens.mint(new_run(db, configured))
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    for path in ["/api/assets", "/api/integrations", "/api/discovery-runs", "/api/auth/me"]:
        assert client.get(path, headers={"Authorization": "Bearer " + token}).status_code == 401
    tokens.key_path().chmod(0o644)
    with pytest.raises(tokens.IngestionAuthenticationError): tokens.provision_signing_key()


@pytest.mark.parametrize("completeness", ["complete", "partial", "failed", "cancelled"])
def test_transactional_finalisation_and_no_accepted_overwrite(db, configured, completeness):
    run = new_run(db, configured)
    aip.accept_batch(db, run, message(run, technical=True))
    assert not list(db.scalars(select(ReconciliationItem).where(ReconciliationItem.assertion_id.in_(select(KnowledgeAssertion.id).where(KnowledgeAssertion.discovery_run_id == run.id)))))
    outcome = message(run, completion=completeness)
    aip.finalise(db, run, configured[0], outcome, failure=completeness in {"failed", "cancelled"})
    assert aip.finalise(db, run, configured[0], outcome, failure=completeness in {"failed", "cancelled"})["replayed"]
    assert db.scalar(select(func.count()).select_from(Asset).where(Asset.customer_id == run.customer_id)) == 0
    claims = list(db.scalars(select(KnowledgeAssertion).where(KnowledgeAssertion.discovery_run_id == run.id)))
    if completeness in {"complete", "partial"}:
        assert claims and not any(claim.is_accepted for claim in claims)
        fact = next(claim for claim in claims if claim.predicate == "i3-fixture.tags")
        assert fact.value_json == ["a", "b"] and fact.fact_metadata["cardinality"] == "multi"
    else:
        assert not claims
    assert run.status not in {"pending", "running"}
    assert not list(db.scalars(select(KnowledgeChange).where(KnowledgeChange.discovery_run_id == run.id, KnowledgeChange.change_type == "no_longer_observed")))
    with pytest.raises(aip.IngestionError, match="run_finalised"):
        aip.accept_batch(db, run, message(run, sequence=2, assets=False))


def test_source_identity_review_complete_absence_and_reobservation(db, configured):
    run = new_run(db, configured)
    aip.accept_batch(db, run, message(run, technical=True))
    aip.finalise(db, run, configured[0], message(run, completion="complete"))
    items = list(db.scalars(select(ReconciliationItem).join(KnowledgeAssertion).where(KnowledgeAssertion.discovery_run_id == run.id)))
    for kind in ["asset", "network", "asset_interface", "asset_relationship"]:
        for item in items:
            if item.entity_type == kind and item.category == "newly_discovered" or item.entity_type == kind and kind == "asset_relationship":
                accept_item(db, item, configured[1].user)
    asset_ids = set(db.scalars(select(Asset.id).where(Asset.customer_id == run.customer_id)))
    assert len(asset_ids) == 2
    assert db.scalar(select(func.count()).select_from(EntitySourceLink).where(EntitySourceLink.data_source_id == run.data_source_id)) == 4
    run.dispatch_state = "settled"; db.commit()
    for completeness in ["partial", "failed", "complete"]:
        current = new_run(db, configured)
        aip.accept_batch(db, current, message(current, assets=False))
        aip.finalise(db, current, configured[0], message(current, completion=completeness), failure=completeness == "failed")
        assert current.summary.get("no_longer_observed_count", 0) == (2 if completeness == "complete" else 0)
        current.dispatch_state = "settled"; db.commit()
    observed = new_run(db, configured)
    aip.accept_batch(db, observed, message(observed))
    aip.finalise(db, observed, configured[0], message(observed, completion="complete"))
    assert set(db.scalars(select(Asset.id).where(Asset.customer_id == observed.customer_id))) == asset_ids
    assert observed.summary["reobserved_count"] == 2


def test_out_of_order_missing_batch_and_declared_mapping_checks(db, configured, monkeypatch):
    run = new_run(db, configured)
    aip.accept_batch(db, run, message(run, sequence=2, assets=False))
    with pytest.raises(aip.IngestionError, match="incomplete_receipts"):
        aip.finalise(db, run, configured[0], message(run, sequence=2, completion="complete"))
    aip.accept_batch(db, run, message(run))
    aip.finalise(db, run, configured[0], message(run, sequence=2, completion="complete"))
    assert run.batch_count == 2


@pytest.mark.parametrize("attack", ["bad_json", "duplicate_key", "tenant", "wrong_run", "wrong_connector", "unknown_class", "undeclared_fact", "secret", "oversized", "sequence", "observation_limit", "batch_limit"])
def test_ingestion_security_surface_fails_closed_without_payload_disclosure(db, configured, monkeypatch, attack):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db
    run = new_run(db, configured)
    token = tokens.mint(run); payload = message(run)
    if attack == "tenant": payload["customer_id"] = str(uuid.uuid4())
    elif attack == "wrong_run": payload["run_id"] = str(uuid.uuid4())
    elif attack == "wrong_connector": payload["connector"]["id"] = "other"
    elif attack == "unknown_class": payload["assets"][0]["object_class"] = "not.declared"
    elif attack == "undeclared_fact": payload["assets"][1]["facts"][0]["key"] = "not.declared"
    elif attack == "sequence": payload["batch"]["sequence"] = 0
    elif attack == "secret":
        provider = AtlasEncryptedSecretProvider(db)
        with provider.materialize_for_job(configured[0], run.id, ["token_secret"]) as lease:
            payload["assets"][0]["name"] = lease.values["token_secret"]
    elif attack == "observation_limit": monkeypatch.setattr(aip, "MAX_OBSERVATIONS", 1)
    elif attack == "batch_limit": monkeypatch.setattr(aip, "MAX_BATCHES", 0)
    raw = json.dumps(payload).encode()
    if attack == "bad_json": raw = b'{broken'
    elif attack == "duplicate_key": raw = b'{"x":1,"x":2}'
    elif attack == "oversized": raw = b' ' * (aip.MAX_BODY + 1)
    app.dependency_overrides[get_db] = lambda: db
    try:
        response = TestClient(app).post(f"/api/integration-ingestion/{run.id}/batches", content=raw,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code in {413, 422}
    assert token not in response.text and payload["assets"][0]["name"] not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert run.status == "failed" and run.batch_count == 0
    assert not db.scalar(select(EvidenceRecord.id).where(EvidenceRecord.discovery_run_id == run.id))


def test_explicit_network_link_preserves_manual_configuration_and_routes_conflict(db, configured):
    run = new_run(db, configured)
    aip.accept_batch(db, run, message(run, technical=True)); aip.finalise(db, run, configured[0], message(run, completion="complete"))
    manual = Network(customer_id=run.customer_id, site_id=run.site_id, name="Curated LAN", network_type="vlan", vlan_id=9)
    db.add(manual); db.flush()
    item = db.scalar(select(ReconciliationItem).join(KnowledgeAssertion).where(KnowledgeAssertion.discovery_run_id == run.id,
        ReconciliationItem.entity_type == "network", ReconciliationItem.category == "newly_discovered"))
    link_item_to_technical(db, item=item, target=manual, user=configured[1].user)
    assert manual.name == "Curated LAN" and manual.vlan_id == 9
    conflict = db.scalar(select(ReconciliationItem).where(ReconciliationItem.assertion_id == item.assertion_id, ReconciliationItem.status == "open"))
    assert conflict and conflict.category == "changed"


def test_connector_identity_does_not_auto_merge_matching_manual_asset(db, configured):
    run = new_run(db, configured)
    existing = Asset(workspace_id=db.get(Customer, run.customer_id).workspace_id, customer_id=run.customer_id, site_id=run.site_id, name="Fixture node", asset_type="hypervisor_node", status="active")
    db.add(existing); db.flush()
    aip.accept_batch(db, run, message(run)); aip.finalise(db, run, configured[0], message(run, completion="complete"))
    assert not db.scalar(select(EntitySourceLink.id).where(EntitySourceLink.data_source_id == run.data_source_id, EntitySourceLink.entity_id == existing.id))
    assert db.scalar(select(ReconciliationItem.id).join(KnowledgeAssertion).where(KnowledgeAssertion.discovery_run_id == run.id, ReconciliationItem.category == "possible_duplicate"))


def test_dispatch_duplicate_delivery_secret_lease_and_runtime_recovery(db, configured, monkeypatch):
    run = new_run(db, configured)
    calls = []
    async def start(payload):
        calls.append(payload["credentials"])
        assert tokens.decode(payload["ingestion_token"])["run_id"] == str(run.id)
        return {"state": "queued", "job_id": str(uuid.uuid4())}
    monkeypatch.setattr(orchestration.runtime, "run_discovery", start)
    asyncio.run(orchestration.dispatch(db, run.id)); asyncio.run(orchestration.dispatch(db, run.id))
    assert len(calls) == 1 and calls[0] == {} and run.status == "running"
    async def unavailable(*args): return {"state": "unavailable", "diagnostic_code": "job_unavailable"}
    monkeypatch.setattr(orchestration.runtime, "get_job", unavailable)
    asyncio.run(orchestration.reconcile(db, run.id))
    assert run.status == "failed" and run.dispatch_state == "settled" and run.error_message == "runtime_interrupted"


def test_run_now_real_redis_duplicate_hints_dispatch_once(db, configured, monkeypatch):
    monkeypatch.setattr(orchestration, "QUEUE", "atlas:test:i3:" + uuid.uuid4().hex)
    with orchestration.redis_client() as redis:
        assert redis.ping()
        result = asyncio.run(routes.run_now(configured[0].id, request(), configured[1], db))
        identifier = result["id"]
        assert result["status"] == "pending" and redis.llen(orchestration.QUEUE) == 1
        with pytest.raises(HTTPException) as error:
            asyncio.run(routes.run_now(configured[0].id, request(), configured[1], db))
        assert error.value.status_code == 409 and error.value.detail["run_id"] == str(identifier)
        redis.lpush(orchestration.QUEUE, str(identifier), str(identifier))
        calls = []
        async def start(payload):
            calls.append(payload["credentials"])
            return {"state": "queued", "job_id": str(uuid.uuid4())}
        monkeypatch.setattr(orchestration.runtime, "run_discovery", start)
        sys.path.insert(0, str(ROOT / "apps/worker"))
        from worker.main import tick
        asyncio.run(tick(session_factory=lambda: db))
        asyncio.run(orchestration.dispatch(db, identifier))
        assert calls == [{}] and redis.llen(orchestration.QUEUE) == 0


def test_retry_bounds_and_disabled_pending_intent_never_execute(db, configured, monkeypatch):
    run = new_run(db, configured)
    async def unavailable(): return {"status": "unavailable", "capabilities": {}}
    monkeypatch.setattr(orchestration.runtime, "health", unavailable)
    for attempt in range(1, 4):
        run.dispatch_after = orchestration.utcnow() - timedelta(seconds=1); db.commit()
        asyncio.run(orchestration.dispatch(db, run.id))
        assert run.dispatch_attempts == attempt
    assert run.status == "failed" and run.dispatch_state == "settled" and run.ingestion_generation is None
    monkeypatch.setattr(orchestration.runtime, "health", lambda: asyncio.sleep(0, result=configured[3]))
    pending = new_run(db, configured)
    configured[0].enabled = False; db.commit()
    calls = []
    async def start(payload): calls.append(payload)
    monkeypatch.setattr(orchestration.runtime, "run_discovery", start)
    asyncio.run(orchestration.dispatch(db, pending.id))
    assert pending.status == "failed" and calls == []


def test_schedule_manual_permission_and_scoped_nondisclosure(db, configured, monkeypatch):
    row, principal, _, _ = configured
    assert asyncio.run(routes.set_schedule(row.id, routes.ScheduleInput(preset="daily"), request(), principal, db))["preset"] == "daily"
    scoped = replace(principal, grants=(replace(principal.grants[0], scope_type="site", customer_id=uuid.uuid4(), site_id=uuid.uuid4()),))
    with pytest.raises(HTTPException) as error: asyncio.run(routes.run_now(row.id, request(), scoped, db))
    assert error.value.status_code == 404
    with pytest.raises(HTTPException): asyncio.run(routes.set_schedule(row.id, routes.ScheduleInput(preset="* * * * *"), request(), principal, db))
    row.next_run_at = orchestration.utcnow() - timedelta(hours=2); db.commit()
    sys.path.insert(0, str(ROOT / "apps/worker"))
    from worker.main import tick
    dispatched = []
    async def capture(session, identifier): dispatched.append(identifier)
    monkeypatch.setattr(orchestration, "dispatch", capture)
    asyncio.run(tick(session_factory=lambda: db))
    # tick owns/closes its sessions: use the shared connection for verification.
    assert len(dispatched) == 1
