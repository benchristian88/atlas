"""R4-N1 full authenticated HTTP ingestion and cross-source acceptance.

Synthetic Integration authority stays in pytest temporary storage. Every request
uses production SessionLocal and independent committed-state inspection.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Event
from types import SimpleNamespace
import uuid

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import DBAPIError

from app.authorization import ActiveContext, get_active_context, get_principal
from app.database import SessionLocal, get_db
from app.models import (AuditEvent, DataSource, DiscoveryRun, EvidenceRecord,
    KnowledgeAssertion, KnowledgeChange, Network, ReconciliationItem)
from app.routes import integration_discovery, knowledge
from app.services import discovery_tokens
from app.services.entity_resolution import ensure_technical_link
from app.services.knowledge_assertions import record_assertion
from app.services.reconciliation import create_item
from tests.i3_fixtures import message
from tests.test_i3_discovery import configured, new_run
from tests.test_knowledge_integrity_migration import migrated_history, HEAD, pytestmark


@pytest.fixture
def db(migrated_history):
    migrated_history.migrate("upgrade", HEAD)
    with SessionLocal(bind=migrated_history.engine) as session:
        yield session


def row_for(client, identifier):
    response = client.get("/reconciliation-entities")
    assert response.status_code == 200, response.text
    return next(row for group in response.json()["entities"]
        for row in ([group["parent"]] if group["parent"] else []) +
            [row for section in group["sections"] for row in section["items"]]
        if row["id"] == str(identifier))


@pytest.fixture
def ingestion_review(db, configured):
    integration, principal, *_ = configured
    principal = replace(principal, grants=(replace(principal.grants[0],
        permissions=principal.grants[0].permissions | {"reconciliation.view", "networks.view"}),))
    source_a = db.get(DataSource, integration.data_source_id)
    source_b = DataSource(customer_id=integration.customer_id, site_id=integration.site_id,
        name="Independent source B", source_type="connector")
    network = Network(customer_id=integration.customer_id, site_id=integration.site_id,
        name="Review LAN", network_type="lan")
    db.add_all([source_b, network])
    db.flush()
    for source in (source_a, source_b):
        ensure_technical_link(db, source=source, target=network, entity_type="network",
            external_id="network/1", observed_at=datetime.now(timezone.utc))
    config = {"name": network.name, "network_type": "lan", "vlan_id": None, "cidr": None, "gateway": None}

    def proposal(source, number):
        claim, _ = record_assertion(db, customer_id=integration.customer_id, site_id=integration.site_id,
            subject_type="network", subject_id=network.id, subject_external_id="network/1",
            predicate="configuration", value=config, data_source_id=source.id)
        claim.id = uuid.UUID(int=number)
        db.flush()
        item, _ = create_item(db, assertion=claim, category="changed", entity_type="network",
            entity_id=network.id, candidate_external_id="network/1", current_value=config,
            observed_value=config, recommended_action="Review")
        db.commit()
        return item.id, claim.id

    app = FastAPI()
    app.include_router(knowledge.router)
    app.include_router(integration_discovery.router)
    engine = db.get_bind()
    def request_db(request: Request):
        with SessionLocal(bind=engine) as session:
            session.connection(execution_options={"test_actor": request.headers.get("x-test-actor")})
            if request.headers.get("x-test-lock-timeout"):
                session.execute(text("SET LOCAL lock_timeout='100ms'"))
            yield session
    app.dependency_overrides[get_db] = request_db
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_active_context] = lambda: ActiveContext(integration.customer_id, integration.site_id)
    with TestClient(app, raise_server_exceptions=False) as client:
        first, old_id = proposal(source_a, 10)
        response = client.post(f"/reconciliation-items/{first}/accept",
            json={"expected_version": row_for(client, first)["version"]})
        assert response.status_code == 200, response.text
        item_id, new_id = proposal(source_b, 20)
        version = row_for(client, item_id)["version"]
        run = new_run(db, configured)
        token = discovery_tokens.mint(run)
        payload = message(run, assets=False)
        payload["networks"] = [{"external_id": "network/1", "object_class": "i3-fixture.network",
            "name": "Changed LAN", "network_type": "lan", "facts": []}]
        headers = {"Authorization": "Bearer " + token}
        response = client.post(f"/integration-ingestion/{run.id}/batches", json=payload, headers=headers)
        assert response.status_code == 200, response.text
        yield SimpleNamespace(client=client, engine=engine, config=config, network_id=network.id,
            customer_id=integration.customer_id, site_id=integration.site_id, source_id=source_a.id,
            old_id=old_id, new_id=new_id, item_id=item_id, version=version, run_id=run.id,
            completion=message(run, completion="partial"), headers=headers, run=run)


def persisted(case):
    with SessionLocal(bind=case.engine) as fresh:
        old = fresh.get(KnowledgeAssertion, case.old_id)
        run = fresh.get(DiscoveryRun, case.run_id)
        source = fresh.get(DataSource, case.source_id)
        return {"network_name": fresh.get(Network, case.network_id).name,
            "review_status": fresh.get(ReconciliationItem, case.item_id).status,
            "old_selected": old.is_accepted,
            "new_selected": fresh.get(KnowledgeAssertion, case.new_id).is_accepted,
            "source_lineage": old.superseded_by_id, "acceptance_lineage": old.acceptance_replaced_by_id,
            "run_status": run.status, "finalisation_hash": run.finalisation_hash,
            "run_finished": run.finished_at, "source_success": source.last_success_at,
            "source_error": source.last_error_at,
            "changes": fresh.scalar(select(func.count()).select_from(KnowledgeChange).where(
                KnowledgeChange.reconciliation_item_id == case.item_id)),
            "audits": fresh.scalar(select(func.count()).select_from(AuditEvent).where(
                AuditEvent.customer_id == case.customer_id, AuditEvent.event_type == "reconciliation.accepted")),
            "all_audits": fresh.scalar(select(func.count()).select_from(AuditEvent).where(
                AuditEvent.customer_id == case.customer_id)),
            "all_changes": fresh.scalar(select(func.count()).select_from(KnowledgeChange).where(
                KnowledgeChange.customer_id == case.customer_id)),
            "assertions": fresh.scalar(select(func.count()).select_from(KnowledgeAssertion).where(
                KnowledgeAssertion.customer_id == case.customer_id)),
            "evidence": fresh.scalar(select(func.count()).select_from(EvidenceRecord).where(
                EvidenceRecord.discovery_run_id == case.run_id))}


def test_actual_http_network_finalisation_vs_acceptance(ingestion_review):
    case = ingestion_review
    locked, ingestion_ready = Event(), Event()
    states = []
    def before(conn, cursor, sql, params, context, many):
        if context.execution_options.get("test_actor") == "ingest" and "FROM networks" in sql and "FOR UPDATE" in sql:
            ingestion_ready.set()
    def after(conn, cursor, sql, params, context, many):
        actor = context.execution_options.get("test_actor")
        if actor == "decision" and "FROM knowledge_assertions" in sql and "FOR UPDATE" in sql and not locked.is_set():
            locked.set()
            assert ingestion_ready.wait(8)
        if actor == "ingest" and sql.startswith("UPDATE knowledge_assertions") and str(case.old_id) in str(params):
            ingestion_ready.set()  # Exact vulnerable path: write A before waiting on B.
    def error(context):
        states.append(getattr(context.original_exception, "sqlstate", None))
    hooks = [("before_cursor_execute", before), ("after_cursor_execute", after), ("handle_error", error)]
    for name, hook in hooks:
        event.listen(case.engine, name, hook)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            decision = pool.submit(case.client.post, f"/reconciliation-items/{case.item_id}/accept",
                json={"expected_version": case.version}, headers={"x-test-actor": "decision"})
            assert locked.wait(8)
            ingestion = pool.submit(case.client.post, f"/integration-ingestion/{case.run_id}/completion",
                json=case.completion, headers={**case.headers, "x-test-actor": "ingest"})
            accepted, completed = decision.result(timeout=25), ingestion.result(timeout=25)
        assert not states, states
        assert accepted.status_code == completed.status_code == 200, (accepted.text, completed.text)
    finally:
        for name, hook in hooks:
            event.remove(case.engine, name, hook)
    state = persisted(case)
    assert state["network_name"] == case.config["name"] and state["review_status"] == "accepted"
    assert state["new_selected"] and not state["old_selected"]
    assert state["source_lineage"] and state["acceptance_lineage"] == case.new_id
    assert state["run_status"] == "completed" and state["finalisation_hash"]
    assert state["changes"] == 1 and state["audits"] == 2 and state["assertions"] == 3 and state["evidence"] == 1
    with SessionLocal(bind=case.engine) as fresh:
        change = fresh.scalar(select(KnowledgeChange).where(KnowledgeChange.reconciliation_item_id == case.item_id))
        assert change.previous_value_json == change.new_value_json == case.config


def test_actual_http_completion_lock_timeout_rolls_back_and_is_retryable(ingestion_review):
    case = ingestion_review
    before = persisted(case)
    with SessionLocal(bind=case.engine) as holder:
        holder.get(Network, case.network_id, with_for_update=True)
        response = case.client.post(f"/integration-ingestion/{case.run_id}/completion", json=case.completion,
            headers={**case.headers, "x-test-lock-timeout": "bounded"})
        assert response.status_code == 409, response.text
        assert response.json()["detail"].startswith("A concurrent change")
    assert persisted(case) == before
    # Caller explicitly resubmits the same authenticated completion after the
    # holder ends; the server neither retries nor seals a failed transaction.
    response = case.client.post(f"/integration-ingestion/{case.run_id}/completion",
        json=case.completion, headers=case.headers)
    assert response.status_code == 200, response.text
    assert persisted(case)["run_status"] == "completed"


@pytest.mark.parametrize("sqlstate", ["23505", "40001", "40P01", "55P03", "08006"])
def test_actual_http_completion_post_flush_conflict_rollback(ingestion_review, sqlstate):
    case = ingestion_review
    before = persisted(case)
    reached = []
    def abort_after_flush(session):
        if not session.in_nested_transaction() and session.connection().get_execution_options().get("test_actor") == "victim":
            session.flush()
            reached.append(True)
            # Real PostgreSQL marks the transaction failed AFTER domain writes;
            # these fallback checks are separate from natural no-deadlock races.
            session.execute(text(f"DO $$ BEGIN RAISE EXCEPTION 'synthetic victim' USING ERRCODE='{sqlstate}'; END $$"))
    event.listen(SessionLocal.class_, "before_commit", abort_after_flush)
    try:
        response = case.client.post(f"/integration-ingestion/{case.run_id}/completion", json=case.completion,
            headers={**case.headers, "x-test-actor": "victim"})
        assert reached == [True]
        assert response.status_code == (500 if sqlstate == "08006" else 409), response.text
        if sqlstate != "08006":
            assert response.json()["detail"].startswith("A concurrent change")
        else:
            assert "concurrent" not in response.text.lower()
    finally:
        event.remove(SessionLocal.class_, "before_commit", abort_after_flush)
    assert persisted(case) == before


@pytest.mark.parametrize("blocked_kind", ["network", "interface_owner", "absence_asset"])
def test_completion_prelocks_all_batches_before_any_claims(ingestion_review, db, blocked_kind):
    """A later batch's earlier-order row cannot be discovered under claim locks."""
    from app.models import Asset, AssetInterface, Customer, RunObservedEntity
    from app.services.entity_resolution import ensure_asset_link
    case = ingestion_review
    second = message(case.run, sequence=2, assets=False)
    if blocked_kind == "network":
        # The first batch's Network has a random UUID; put the later one first
        # in canonical UUID order, while retaining the opposite payload order.
        blocked = Network(id=uuid.UUID(int=3), customer_id=case.customer_id, site_id=case.site_id,
            name="Second LAN", network_type="lan")
        db.add(blocked)
        db.flush()
        ensure_technical_link(db, source=db.get(DataSource, case.source_id), target=blocked,
            entity_type="network", external_id="network/2", observed_at=datetime.now(timezone.utc))
        second["networks"] = [{"external_id": "network/2", "object_class": "i3-fixture.network",
            "name": "Observed second LAN", "network_type": "lan", "facts": []}]
    elif blocked_kind == "interface_owner":
        customer = db.get(Customer, case.customer_id)
        blocked = Asset(workspace_id=customer.workspace_id, customer_id=case.customer_id,
            site_id=case.site_id, name="Interface owner", asset_type="virtual_machine", source="manual")
        db.add(blocked)
        db.flush()
        interface = AssetInterface(asset_id=blocked.id, name="eth0", is_primary=False)
        db.add(interface)
        db.flush()
        source = db.get(DataSource, case.source_id)
        ensure_asset_link(db, data_source_id=source.id, asset=blocked, external_id="owner/2")
        ensure_technical_link(db, source=source, target=interface, entity_type="asset_interface",
            external_id="interface/2", observed_at=datetime.now(timezone.utc))
        second["interfaces"] = [{"external_id": "interface/2", "object_class": "i3-fixture.interface",
            "name": "eth0", "asset_external_id": "owner/2", "is_primary": False, "facts": []}]
    else:
        assert case.run.is_complete_snapshot
        customer = db.get(Customer, case.customer_id)
        blocked = Asset(workspace_id=customer.workspace_id, customer_id=case.customer_id,
            site_id=case.site_id, name="Previously observed", asset_type="virtual_machine", source="manual")
        db.add(blocked)
        db.flush()
        ensure_asset_link(db, data_source_id=case.source_id, asset=blocked, external_id="baseline/asset")
        at = datetime.now(timezone.utc) - timedelta(days=1)
        baseline = DiscoveryRun(customer_id=case.customer_id, site_id=case.site_id,
            data_source_id=case.source_id, status="completed", started_at=at, finished_at=at,
            is_complete_snapshot=True, completeness_status="complete", coverage_key=case.run.coverage_key)
        db.add(baseline)
        db.flush()
        db.add(RunObservedEntity(discovery_run_id=baseline.id, data_source_id=case.source_id,
            customer_id=case.customer_id, site_id=case.site_id, coverage_key=case.run.coverage_key,
            entity_type="asset", external_id="baseline/asset", entity_id=blocked.id, observed_at=at))
    db.commit()
    response = case.client.post(f"/integration-ingestion/{case.run_id}/batches", json=second, headers=case.headers)
    assert response.status_code == 200, response.text
    completion = {**case.completion, "last_sequence": 2}
    if blocked_kind == "absence_asset":
        completion["completeness"] = "complete"
    waiting, writes = Event(), []
    def before(conn, cursor, sql, params, context, many):
        if context.execution_options.get("test_actor") != "batch-order":
            return
        if "FOR UPDATE" in sql and str(blocked.id) in str(params):
            waiting.set()
        if sql.startswith(("INSERT INTO knowledge_assertions", "UPDATE knowledge_assertions")):
            writes.append(sql)
    event.listen(case.engine, "before_cursor_execute", before)
    try:
        with SessionLocal(bind=case.engine) as holder, ThreadPoolExecutor(max_workers=1) as pool:
            holder.get(type(blocked), blocked.id, with_for_update=True)
            pending = pool.submit(case.client.post, f"/integration-ingestion/{case.run_id}/completion",
                json=completion, headers={**case.headers, "x-test-actor": "batch-order"})
            try:
                assert waiting.wait(8)
                assert writes == [], "A later canonical subject was first acquired after writing claims"
            finally:
                holder.rollback()
            response = pending.result(timeout=20)
        assert response.status_code == 200, response.text
    finally:
        event.remove(case.engine, "before_cursor_execute", before)
    state = persisted(case)
    assert state["run_status"] == "completed" and state["evidence"] == (1 if blocked_kind == "absence_asset" else 2)
    assert state["network_name"] == case.config["name"] and state["old_selected"]
    assert not state["new_selected"] and state["changes"] == 0 and state["audits"] == 1
    if blocked_kind == "absence_asset":
        with SessionLocal(bind=case.engine) as fresh:
            assert fresh.get(Asset, blocked.id).status == "active"
            assert fresh.scalar(select(func.count()).select_from(ReconciliationItem).where(
                ReconciliationItem.customer_id == case.customer_id,
                ReconciliationItem.entity_id == blocked.id,
                ReconciliationItem.category == "no_longer_observed", ReconciliationItem.status == "open")) == 1
