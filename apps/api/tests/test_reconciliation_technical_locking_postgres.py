"""R4-N1: natural PostgreSQL races, production sessions and committed state.

Ported from the independent Network/Interface counterexamples. Synchronization
allows either the corrected canonical lock attempt or the vulnerable claim write;
it never requires a waiter to write while the holder is paused.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import event, func, select, text
from fastapi import HTTPException

from app.models import (Asset, AssetInterface, AuditEvent, DataSource, DiscoveryRun,
    EntitySourceLink, EvidenceRecord, KnowledgeAssertion, KnowledgeChange, Network, ReconciliationItem)
from app.services.entity_resolution import ensure_asset_link, ensure_technical_link
from app.services.knowledge_assertions import record_assertion
from app.services.knowledge_locks import lock_ingestion_subjects
from app.services.reconciliation import create_item
from app.services.simulated_discovery import ingest_technical_observation
from tests.test_reconciliation_integrity_postgres import committed, review, pytestmark


def technical_case(s, kind):
    target = s.network if kind == "network" else s.interface
    config = ({"name": target.name, "network_type": "lan", "vlan_id": None,
               "cidr": None, "gateway": None} if kind == "network" else
              {"name": "eth0", "asset_external_id": "owner", "network_external_id": None,
               "ip_address": None, "mac_address": "02:00:00:00:00:01", "is_primary": True})
    with s.session() as db:
        for source in s.sources:
            if kind == "asset_interface":
                ensure_asset_link(db, data_source_id=source.id,
                    asset=db.get(Asset, s.asset.id), external_id="owner")
            ensure_technical_link(db, source=db.get(DataSource, source.id),
                target=db.get(type(target), target.id), entity_type=kind,
                external_id="technical", observed_at=datetime.now(timezone.utc))
        db.commit()

    def proposal(source):
        with s.session() as db:
            claim, _ = record_assertion(db, customer_id=s.customer.id, site_id=s.site.id,
                subject_type=kind, subject_id=target.id, subject_external_id="technical",
                predicate="configuration", value=config, data_source_id=s.sources[source].id)
            # Deterministic legitimate SQLAlchemy flush order for the original
            # old-A update -> other-source B confirmation-status cycle.
            claim.id = uuid.UUID(int=1 if source == 0 else 2)
            db.flush()
            item, _ = create_item(db, assertion=claim, category="changed", entity_type=kind,
                entity_id=target.id, candidate_external_id="technical", current_value=config,
                observed_value=config, recommended_action="Review")
            db.commit()
            return item.id, claim.id

    initial, old_id = proposal(0)
    version = review(s, initial)[0]["version"]
    response = s.client.post(f"/reconciliation-items/{initial}/accept", json={"expected_version": version})
    assert response.status_code == 200, response.text
    item_id, new_id = proposal(1)
    version = review(s, item_id)[0]["version"]
    with s.session() as db:
        assert db.get(KnowledgeAssertion, new_id).confirmation_status == "unreviewed"
        run = DiscoveryRun(customer_id=s.customer.id, site_id=s.site.id,
            data_source_id=s.sources[0].id, started_at=datetime.now(timezone.utc), status="running", summary={})
        db.add(run)
        db.flush()
        evidence = EvidenceRecord(discovery_run_id=run.id, data_source_id=s.sources[0].id,
            customer_id=s.customer.id, site_id=s.site.id, external_id="technical", entity_kind=kind,
            payload_json={}, payload_hash="synthetic-lock-probe", observed_at=datetime.now(timezone.utc))
        db.add(evidence)
        db.commit()
        return SimpleNamespace(target=target, config=config, old_id=old_id, new_id=new_id,
            item_id=item_id, version=version, run_id=run.id, evidence_id=evidence.id)


def ingest(s, case, kind):
    with s.session() as db:
        db.connection(execution_options={"test_actor": "ingest"})
        observation = {"external_id": "technical", **case.config, "facts": [],
                       "name": case.config["name"] + "-new"}
        ingest_technical_observation(db, run=db.get(DiscoveryRun, case.run_id),
            source=db.get(DataSource, s.sources[0].id), evidence=db.get(EvidenceRecord, case.evidence_id),
            observation=observation, entity_type=kind, user_id=s.principal.user.id)
        db.commit()


@pytest.mark.parametrize("kind", ["network", "asset_interface"])
@pytest.mark.parametrize("first", ["decision", "ingest"])
def test_technical_ingestion_acceptance_lock_graph(committed, kind, first):
    s = committed
    case = technical_case(s, kind)
    decision_locked, ingestion_ready, decision_ready = Event(), Event(), Event()
    states, steps = [], []

    def before(conn, cursor, sql, params, context, many):
        actor = context.execution_options.get("test_actor")
        if actor == "ingest" and "FOR UPDATE" in sql and first == "decision":
            ingestion_ready.set()
        if actor == "decision" and "FOR UPDATE" in sql:
            decision_ready.set()

    def after(conn, cursor, sql, params, context, many):
        actor = context.execution_options.get("test_actor")
        if actor == "decision" and "FROM knowledge_assertions" in sql and "FOR UPDATE" in sql:
            decision_locked.set()
            if first == "decision":
                assert ingestion_ready.wait(8)
        if actor == "ingest" and "FOR UPDATE" in sql:
            steps.append("subject")
            if first == "ingest":
                ingestion_ready.set()
                assert decision_ready.wait(8)
        if actor == "ingest" and sql.startswith("UPDATE knowledge_assertions"):
            steps.append("claim")
            if str(case.old_id) in str(params):
                ingestion_ready.set()
                if first == "ingest":
                    assert decision_ready.wait(8)

    def error(context):
        states.append(getattr(context.original_exception, "sqlstate", None))

    hooks = [("before_cursor_execute", before), ("after_cursor_execute", after), ("handle_error", error)]
    for name, hook in hooks:
        event.listen(s.engine, name, hook)
    try:
        def decision():
            return s.client.post(f"/reconciliation-items/{case.item_id}/accept",
                json={"expected_version": case.version}, headers={"x-test-actor": "decision"})
        with ThreadPoolExecutor(max_workers=2) as pool:
            if first == "decision":
                accepted = pool.submit(decision)
                assert decision_locked.wait(8)
                ingested = pool.submit(ingest, s, case, kind)
            else:
                ingested = pool.submit(ingest, s, case, kind)
                assert ingestion_ready.wait(8)
                accepted = pool.submit(decision)
            response = accepted.result(timeout=25)
            ingested.result(timeout=25)
        assert not states, states
        assert steps.index("subject") < steps.index("claim")
        assert response.status_code == (200 if first == "decision" else 409), response.text
    finally:
        for name, hook in hooks:
            event.remove(s.engine, name, hook)

    if first == "ingest":
        # Ingestion changed B's conflict status/update epoch. The old reviewed
        # token must fail safely; selecting B again requires an explicit refresh.
        with s.session() as db:
            assert db.get(ReconciliationItem, case.item_id).status == "open"
            assert db.get(KnowledgeAssertion, case.old_id).is_accepted
            assert not db.get(KnowledgeAssertion, case.new_id).is_accepted
            assert db.scalar(select(func.count()).select_from(KnowledgeChange).where(
                KnowledgeChange.reconciliation_item_id == case.item_id)) == 0
            assert db.scalar(select(func.count()).select_from(AuditEvent).where(
                AuditEvent.customer_id == s.customer.id, AuditEvent.event_type == "reconciliation.accepted")) == 1
        fresh = review(s, case.item_id)[0]["version"]
        assert fresh != case.version
        response = s.client.post(f"/reconciliation-items/{case.item_id}/accept", json={"expected_version": fresh})
        assert response.status_code == 200, response.text
    with s.session() as db:
        previous = db.get(KnowledgeAssertion, case.old_id)
        assert previous.value_json == case.config
        assert not previous.is_accepted and not previous.is_source_current
        assert previous.acceptance_replaced_by_id == case.new_id and previous.superseded_by_id
        assert db.get(KnowledgeAssertion, previous.superseded_by_id).value_json["name"] == case.config["name"] + "-new"
        selected = db.get(KnowledgeAssertion, case.new_id)
        assert selected.is_accepted and selected.value_json == case.config
        assert db.get(type(case.target), case.target.id).name == case.config["name"]
        assert db.scalar(select(func.count()).select_from(KnowledgeAssertion).where(
            KnowledgeAssertion.customer_id == s.customer.id)) == 3
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(
            AuditEvent.customer_id == s.customer.id, AuditEvent.event_type == "reconciliation.accepted")) == 2
        assert db.scalar(select(func.count()).select_from(EvidenceRecord).where(
            EvidenceRecord.discovery_run_id == case.run_id)) == 1
        assert db.get(DiscoveryRun, case.run_id).status == "running"
        assert db.get(ReconciliationItem, case.item_id).status == "accepted"
        assert db.scalar(select(func.count()).select_from(KnowledgeChange).where(
            KnowledgeChange.reconciliation_item_id == case.item_id)) == 1
        change = db.scalar(select(KnowledgeChange).where(KnowledgeChange.reconciliation_item_id == case.item_id))
        if kind == "asset_interface":
            from app.services.reconciliation import technical_configuration
            assert change.previous_value_json == change.new_value_json == technical_configuration(db.get(AssetInterface, case.target.id))
        else:
            assert change.previous_value_json == change.new_value_json == case.config
        audit = db.scalar(select(AuditEvent).where(AuditEvent.target_id == case.item_id,
            AuditEvent.event_type == "reconciliation.accepted"))
        assert audit.success and audit.user_id == s.principal.user.id
        assert audit.metadata_["entity_id"] == str(case.target.id)
        links = list(db.scalars(select(EntitySourceLink).where(EntitySourceLink.customer_id == s.customer.id,
            EntitySourceLink.entity_type == kind, EntitySourceLink.external_id == "technical")))
        assert len(links) == 2
        assert {link.network_id if kind == "network" else link.interface_id for link in links} == {case.target.id}


@pytest.mark.parametrize("kind", ["network", "asset_interface"])
def test_technical_ingestion_leaves_unrelated_entities_writable(committed, kind):
    s = committed
    case = technical_case(s, kind)
    with s.session() as db:
        unrelated = (Network(customer_id=s.customer.id, site_id=s.site.id, name="Unrelated LAN", network_type="lan")
            if kind == "network" else AssetInterface(asset_id=s.other.id, name="eth1", is_primary=False))
        db.add(unrelated)
        db.commit()
        identifier = unrelated.id
    held, release = Event(), Event()

    def after(conn, cursor, sql, params, context, many):
        table = "networks" if kind == "network" else "asset_interfaces"
        if context.execution_options.get("test_actor") == "ingest" and f"FROM {table}" in sql and "FOR UPDATE" in sql:
            held.set()
            assert release.wait(8)
    event.listen(s.engine, "after_cursor_execute", after)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            stream = pool.submit(ingest, s, case, kind)
            assert held.wait(8)
            try:
                with s.session() as db:
                    db.execute(text("SET LOCAL lock_timeout='1000ms'"))
                    db.get(type(unrelated), identifier, with_for_update=True).name = "Independent edit"
                    db.commit()
            finally:
                release.set()
            stream.result(timeout=15)
    finally:
        event.remove(s.engine, "after_cursor_execute", after)
        release.set()
    with s.session() as db:
        assert db.get(type(unrelated), identifier).name == "Independent edit"


def test_ingestion_locks_only_source_customer_site_references(committed):
    s = committed
    case = technical_case(s, "network")
    locked = []
    def after(conn, cursor, sql, params, context, many):
        if "FOR UPDATE" in sql:
            locked.append(sql)
    event.listen(s.engine, "after_cursor_execute", after)
    try:
        with s.session() as db:
            # Source B has the same opaque external identity: it must not be
            # selected when A's operation references a different identity.
            lock_ingestion_subjects(db, source_id=s.sources[0].id, customer_id=s.customer.id,
                site_id=s.site.id, references={("network", "unreferenced")})
            assert locked == []
            with pytest.raises(HTTPException) as exc:
                lock_ingestion_subjects(db, source_id=s.sources[0].id, customer_id=uuid.uuid4(),
                    site_id=s.site.id, references={("network", "technical")})
            assert exc.value.status_code == 409
            assert locked == []
    finally:
        event.remove(s.engine, "after_cursor_execute", after)
