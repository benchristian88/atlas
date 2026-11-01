"""F1–F5 release gates: real routes, committed rows and independent connections.

Every HTTP request gets the production SessionLocal options. Race gates are
SQL events/barriers, not sleeps; lock_timeout/statement_timeout bound failures.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
import os
from threading import Barrier, Event, Lock
from types import SimpleNamespace
import uuid

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, delete, event, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.authorization import ActiveContext, get_active_context, get_principal
from app.database import SessionLocal, get_db
from app.models import (Asset, AssetInterface, AuditEvent, Base, Customer, DataSource,
    EntitySourceLink, KnowledgeAssertion, KnowledgeChange, Network, ReconciliationItem,
    Site, User, Workspace)
from app.routes import assets, changes, knowledge
from app.services.entity_resolution import ensure_asset_link
from app.services.knowledge_assertions import accept_assertion, record_assertion
from app.services.reconciliation import create_item
from tests.test_administration import make_principal

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")


@pytest.fixture
def committed():
    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"], hide_parameters=True,
        connect_args={"options": "-c lock_timeout=10000 -c statement_timeout=20000"})
    def session():
        return SessionLocal(bind=engine)
    assert SessionLocal.kw["autoflush"] is False
    assert SessionLocal.kw["expire_on_commit"] is False
    principal = make_principal("reconciliation.view", "reconciliation.decide", "assets.view", "assets.edit",
        "networks.view", "networks.edit", "networks.create", "relationships.create", "assertions.retract", "discovery.simulate")
    principal.user.email = uuid.uuid4().hex + "@example.test"
    with session() as db:
        db.add(principal.user)
        workspace = Workspace(name="Integrity release gate", slug=uuid.uuid4().hex)
        db.add(workspace); db.flush()
        customer = Customer(workspace_id=workspace.id, name="Integrity release gate")
        db.add(customer); db.flush()
        site = Site(customer_id=customer.id, name="Integrity release gate")
        db.add(site); db.flush()
        sources = [DataSource(customer_id=customer.id, site_id=site.id, name=name,
            source_type="simulated_discovery") for name in ("Source A", "Source B")]
        asset = Asset(workspace_id=workspace.id, customer_id=customer.id, site_id=site.id,
            name="Curated", asset_type="virtual_machine", status="active", source="manual")
        other = Asset(workspace_id=workspace.id, customer_id=customer.id, site_id=site.id,
            name="Other", asset_type="hypervisor_node", status="active", source="manual")
        network = Network(customer_id=customer.id, site_id=site.id, name="Curated LAN", network_type="lan")
        db.add_all([*sources, asset, other, network]); db.flush()
        interface = AssetInterface(asset_id=asset.id, name="eth0", mac_address="02:00:00:00:00:01", is_primary=True)
        db.add(interface); db.commit()
    app = FastAPI()
    for router in (knowledge.router, assets.router, changes.router):
        app.include_router(router)
    def request_db(request: Request):
        with session() as db:
            db.connection(execution_options={"test_actor": request.headers.get("x-test-actor")})
            yield db
    app.dependency_overrides[get_db] = request_db
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_active_context] = lambda: ActiveContext(customer.id, site.id)
    def proposal(predicate="fixture.serial", value="serial-A", *, source=0, target=True, category="changed", external=None):
        with session() as db:
            claim, _ = record_assertion(db, customer_id=customer.id, site_id=site.id, subject_type="asset",
                subject_id=asset.id if target else None, subject_external_id=external or f"source-{source}",
                predicate=predicate, value=value, data_source_id=sources[source].id,
                fact_metadata={"value_type": "string", "class": "configuration", "cardinality": "single"} if "." in predicate else None)
            current = getattr(db.get(Asset, asset.id), predicate, None) if target else None
            item, _ = create_item(db, assertion=claim, category=category, entity_type="asset", entity_id=asset.id if target else None,
                candidate_external_id=claim.subject_external_id, current_value={"field": predicate, "value": current},
                observed_value={"field": predicate, "value": value} if target else {"name": value, "asset_type": "virtual_machine", "facts": {}},
                recommended_action="Review")
            db.commit()
            return item.id, claim.id
    state = SimpleNamespace(engine=engine, session=session, app=app, principal=principal, asset=asset, other=other,
        network=network, interface=interface, sources=sources, customer=customer, site=site, proposal=proposal)
    with TestClient(app) as client:
        state.client = client
        try:
            yield state
        finally:
            with engine.begin() as connection:
                for table in reversed(Base.metadata.sorted_tables):
                    if "customer_id" in table.c:
                        connection.execute(delete(table).where(table.c.customer_id == customer.id))
                connection.execute(delete(Customer).where(Customer.id == customer.id))
                connection.execute(delete(Workspace).where(Workspace.id == workspace.id))
                connection.execute(delete(User).where(User.id == principal.user.id))
            engine.dispose()


def review(state, identifier):
    response = state.client.get('/reconciliation-entities')
    assert response.status_code == 200, response.text
    for group in response.json()["entities"]:
        for row in ([group["parent"]] if group["parent"] else []) + [row for section in group["sections"] for row in section["items"]]:
            if row["id"] == str(identifier):
                return row, group
    pytest.fail(f"Missing review {identifier}")


def accept(state, identifier, *, version=None, actor=None, bulk=False):
    row, group = review(state, identifier)
    version = version or row["version"]
    headers = {"x-test-actor": actor} if actor else {}
    if bulk:
        return state.client.post(f'/reconciliation-entities/{group["id"]}/accept', headers=headers,
            json={"items": [{"id": str(identifier), "version": version}]})
    return state.client.post(f'/reconciliation-items/{identifier}/accept', headers=headers,
        json={"expected_version": version})


@pytest.mark.parametrize("kind", ["asset", "asset_interface", "network"])
def test_f1_link_commits_separate_review_and_rollback_retry(committed, monkeypatch, kind):
    s = committed
    if kind == "asset":
        identifier, claim_id = s.proposal("name", "Observed", target=False, category="newly_discovered")
        target, path, key = s.asset, "link-asset", "asset_id"
    else:
        with s.session() as db:
            ensure_asset_link(db, data_source_id=s.sources[0].id, asset=db.get(Asset, s.asset.id), external_id="owner")
            value = ({"name": "eth0", "asset_external_id": "owner", "network_external_id": None,
                "mac_address": "02:00:00:00:00:02", "ip_address": None, "is_primary": False} if kind == "asset_interface"
                else {"name": "Observed LAN", "network_type": "lan", "vlan_id": 12, "cidr": None, "gateway": None})
            claim, _ = record_assertion(db, customer_id=s.customer.id, site_id=s.site.id, data_source_id=s.sources[0].id,
                subject_type=kind, subject_external_id="technical", predicate="configuration", value=value)
            item, _ = create_item(db, assertion=claim, category="newly_discovered", entity_type=kind, entity_id=None,
                candidate_external_id="technical", current_value=None, observed_value=value, recommended_action="Review")
            db.commit(); identifier, claim_id = item.id, claim.id
        target, path, key = (s.interface if kind == "asset_interface" else s.network), "link-technical", "entity_id"
    row, _ = review(s, identifier)
    payload = {key: str(target.id), "expected_version": row["version"]}
    from app.services import reconciliation
    original = reconciliation.create_item
    def fail(*args, **kwargs):
        raise RuntimeError("injected follow-up failure")
    with monkeypatch.context() as patch:
        patch.setattr(reconciliation, "create_item", fail)
        with pytest.raises(RuntimeError, match="injected follow-up"):
            s.client.post(f'/reconciliation-items/{identifier}/{path}', json=payload)
    with s.session() as db:
        assert db.get(ReconciliationItem, identifier).status == "open"
        assert db.scalar(select(func.count()).select_from(EntitySourceLink).where(
            EntitySourceLink.entity_type == kind, EntitySourceLink.external_id == ("source-0" if kind == "asset" else "technical"),
            EntitySourceLink.data_source_id == s.sources[0].id)) == 0
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.customer_id == s.customer.id)) == 0
    response = s.client.post(f'/reconciliation-items/{identifier}/{path}', json=payload)
    assert response.status_code == 200, response.text
    assert s.client.post(f'/reconciliation-items/{identifier}/{path}', json=payload).status_code == 409
    with s.session() as db:
        assert db.get(ReconciliationItem, identifier).status == "accepted"
        claim = db.get(KnowledgeAssertion, claim_id)
        assert claim.subject_id == target.id and not claim.is_accepted
        pending = list(db.scalars(select(ReconciliationItem).where(ReconciliationItem.assertion_id == claim_id,
            ReconciliationItem.status == "open")))
        assert len(pending) == 1 and pending[0].id != identifier
        assert pending[0].category == "changed" and pending[0].entity_id == target.id
        assert pending[0].current_value_json and pending[0].observed_value_json
        followup = pending[0].id
        assert db.get(Asset, s.asset.id).name == "Curated"
        assert db.get(AssetInterface, s.interface.id).mac_address == "02:00:00:00:00:01"
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.customer_id == s.customer.id)) == 1
    assert review(s, followup)[0]["can_accept"]
    assert accept(s, followup).status_code == 200


@pytest.mark.parametrize("field,observed,manual", [("asset_type", "virtual_machine", "hypervisor_node"),
    ("name", "Observed", "Administrator"), ("hostname", "old-host", "new-host"),
    ("status", "active", "inactive"), ("vendor", "old-vendor", "new-vendor"),
    ("model", "old-model", "new-model"), ("ip_address", "192.0.2.4", "192.0.2.5"),
    ("description", "old-description", "new-description")])
@pytest.mark.parametrize("bulk", [False, True])
def test_f2_http_manual_edit_invalidates_review(committed, field, observed, manual, bulk):
    s = committed
    identifier, claim_id = s.proposal(field, observed)
    row, _ = review(s, identifier)
    response = s.client.patch(f'/assets/{s.asset.id}', json={field: manual})
    assert response.status_code == 200, response.text
    response = accept(s, identifier, version=row["version"], bulk=bulk)
    if bulk:
        assert response.status_code == 200 and len(response.json()["failed"]) == 1, response.text
    else:
        assert response.status_code == 409, response.text
    with s.session() as db:
        assert getattr(db.get(Asset, s.asset.id), field) == manual
        assert not db.get(KnowledgeAssertion, claim_id).is_accepted
        assert db.get(ReconciliationItem, identifier).status == "open"
    # The same observation can be explicitly selected after a fresh review.
    assert accept(s, identifier).status_code == 200


def test_f2_partial_bulk_preserves_independent_success(committed):
    s = committed
    stale, _ = s.proposal("asset_type", "virtual_machine")
    valid, _ = s.proposal("fixture.serial", "valid")
    old, group = review(s, stale)
    fresh, _ = review(s, valid)
    assert s.client.patch(f'/assets/{s.asset.id}', json={"asset_type": "hypervisor_node"}).status_code == 200
    response = s.client.post(f'/reconciliation-entities/{group["id"]}/accept', json={"items": [
        {"id": str(stale), "version": old["version"]}, {"id": str(valid), "version": fresh["version"]}]})
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()["failed"]] == [str(stale)]
    assert [row["id"] for row in response.json()["accepted"]] == [str(valid)]
    with s.session() as db:
        assert db.get(Asset, s.asset.id).asset_type == "hypervisor_node"
        assert db.get(ReconciliationItem, valid).status == "accepted"


def run_race(engine, operations, *, gate="subjects"):
    barrier, seen, guard = Barrier(2), set(), Lock()
    def synchronize(conn, cursor, statement, parameters, context, executemany):
        actor = context.execution_options.get("test_actor")
        if actor not in {"a", "b"} or ("FOR NO KEY UPDATE" if gate == "sources" else "FOR UPDATE") not in statement:
            return
        if ("FROM assets" if gate == "subjects" else "FROM data_sources") not in statement:
            return
        with guard:
            first = actor not in seen
            seen.add(actor)
        if first:
            barrier.wait(timeout=8)
    event_name = "after_cursor_execute" if gate == "sources" else "before_cursor_execute"
    event.listen(engine, event_name, synchronize)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(operation) for operation in operations]
            results = [future.result(timeout=25) for future in futures]
        assert seen == {"a", "b"}, "Both independent transactions must reach the SQL race gate"
        return results
    finally:
        event.remove(engine, event_name, synchronize)


@pytest.mark.parametrize("predicate,values", [("fixture.serial", ["serial-A", "serial-B"]),
    ("fixture.serial", ["same", "same"]), ("name", ["Name A", "Name B"]), ("name", ["Curated", "Curated"]),
    ("asset_type", ["hypervisor_node", "virtual_machine"])])
@pytest.mark.parametrize("bulk", [False, True])
def test_f3_competing_sources_one_effective_value(committed, predicate, values, bulk):
    s = committed
    proposals = [s.proposal(predicate, value, source=index) for index, value in enumerate(values)]
    versions = [review(s, identifier)[0]["version"] for identifier, _ in proposals]
    results = run_race(s.engine, [lambda i=i: accept(s, proposals[i][0], version=versions[i], actor="ab"[i], bulk=bulk and i == 0)
        for i in range(2)])
    assert all(response.status_code in {200, 409} for response in results), [r.text for r in results]
    succeeded = [i for i, response in enumerate(results) if response.status_code == 200 and not (bulk and i == 0 and response.json().get("failed"))]
    assert succeeded
    with s.session() as db:
        effective = list(db.scalars(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == s.asset.id,
            KnowledgeAssertion.predicate == predicate, KnowledgeAssertion.is_accepted.is_(True), KnowledgeAssertion.retracted_at.is_(None))))
        assert len(effective) == 1 and effective[0].id in [proposals[i][1] for i in succeeded]
        assert effective[0].value_json in values
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.customer_id == s.customer.id,
            AuditEvent.event_type == "reconciliation.accepted")) == len(succeeded)
        assert db.scalar(select(func.count()).select_from(KnowledgeChange).where(KnowledgeChange.customer_id == s.customer.id,
            KnowledgeChange.reconciliation_item_id.in_([p[0] for p in proposals]))) == len(succeeded)
        for identifier, claim_id in proposals:
            assert db.get(KnowledgeAssertion, claim_id).is_source_current
            assert db.get(KnowledgeAssertion, claim_id).superseded_by_id is None


def test_f2_manual_edit_holding_lock_rejects_concurrent_acceptance(committed):
    s = committed
    identifier, claim_id = s.proposal("asset_type", "virtual_machine")
    version = review(s, identifier)[0]["version"]
    locked, attempting = Event(), Event()
    def before(conn, cursor, statement, parameters, context, executemany):
        if context.execution_options.get("test_actor") == "b" and "FROM assets" in statement and "FOR UPDATE" in statement:
            assert locked.wait(8)
            attempting.set()
    def after(conn, cursor, statement, parameters, context, executemany):
        if context.execution_options.get("test_actor") == "a" and "FROM assets" in statement and "FOR UPDATE" in statement:
            locked.set()
            assert attempting.wait(8)
    event.listen(s.engine, "before_cursor_execute", before)
    event.listen(s.engine, "after_cursor_execute", after)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            manual = pool.submit(s.client.patch, f'/assets/{s.asset.id}', json={"asset_type": "hypervisor_node"}, headers={"x-test-actor": "a"})
            assert locked.wait(8)
            decision = pool.submit(accept, s, identifier, version=version, actor="b")
            assert manual.result(timeout=25).status_code == 200
            assert decision.result(timeout=25).status_code == 409
    finally:
        event.remove(s.engine, "before_cursor_execute", before)
        event.remove(s.engine, "after_cursor_execute", after)
    with s.session() as db:
        assert db.get(Asset, s.asset.id).asset_type == "hypervisor_node"
        assert not db.get(KnowledgeAssertion, claim_id).is_accepted


def test_f3_acceptance_versus_retraction(committed):
    s = committed
    first, old = s.proposal(value="serial-A")
    assert accept(s, first).status_code == 200
    second, selected = s.proposal(value="serial-B", source=1)
    results = run_race(s.engine, [lambda: accept(s, second, actor="a"),
        lambda: s.client.post(f'/assertions/{old}/retract', headers={"x-test-actor": "b"},
            json={"reason": "Operator retracts old source", "confirm_provenance_gap": True})])
    assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    with s.session() as db:
        assert db.get(KnowledgeAssertion, old).retracted_at
        assert not db.get(KnowledgeAssertion, old).is_accepted
        assert db.get(KnowledgeAssertion, selected).is_accepted


@pytest.mark.parametrize("changed", [False, True])
def test_f5_reobservation_retains_source_lineage_and_reviewability(committed, changed):
    s = committed
    first, original = s.proposal("asset_type", "virtual_machine")
    assert accept(s, first).status_code == 200
    second, replacement = s.proposal("asset_type", "hypervisor_node", source=1)
    assert accept(s, second).status_code == 200
    repeated, current = s.proposal("asset_type", "hypervisor_node" if changed else "virtual_machine")
    assert accept(s, repeated).status_code == 200
    with s.session() as db:
        old, new = db.get(KnowledgeAssertion, original), db.get(KnowledgeAssertion, current)
        assert old.acceptance_replaced_by_id == replacement or current == original
        assert new.is_source_current and new.is_accepted and new.superseded_by_id is None
        if changed:
            assert current != original and old.superseded_by_id == current and not old.is_source_current
        else:
            assert current == original and old.superseded_by_id is None
        assert not db.get(KnowledgeAssertion, replacement).is_accepted
        assert db.get(KnowledgeAssertion, replacement).is_source_current
        assert db.get(KnowledgeAssertion, replacement).acceptance_replaced_by_id == current
        count = db.scalar(select(func.count()).select_from(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == s.asset.id))
    for _ in range(3):
        _, identifier = s.proposal("asset_type", "hypervisor_node" if changed else "virtual_machine")
        assert identifier == current
    with s.session() as db:
        assert db.scalar(select(func.count()).select_from(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == s.asset.id)) == count
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.customer_id == s.customer.id,
            AuditEvent.event_type == "reconciliation.accepted")) == 3
    response = s.client.get(f'/assets/{s.asset.id}/knowledge-summary')
    assert response.status_code == 200, response.text


def test_f4_concurrent_asset_links_do_not_lock_unrelated_sources(committed):
    s = committed
    proposals = [s.proposal("name", value, source=index, target=False, category="newly_discovered")
        for index, value in enumerate([s.asset.name, s.other.name])]
    with s.session() as db:
        known = db.get(Asset, s.other.id); known.external_id = "known-target"
        for index in range(2):
            claim, _ = record_assertion(db, customer_id=s.customer.id, site_id=s.site.id, subject_type="asset",
                subject_external_id=f"source-{index}", predicate="runs_on", object_type="asset",
                object_external_id="known-target", data_source_id=s.sources[index].id)
            create_item(db, assertion=claim, category="changed", entity_type="asset_relationship", entity_id=None,
                candidate_external_id=f"source-{index}", current_value=None,
                observed_value={"source_external_id": f"source-{index}", "target_external_id": "known-target", "relationship_type": "runs_on"},
                recommended_action="Review")
        db.commit()
    versions = [review(s, identifier)[0]["version"] for identifier, _ in proposals]
    targets = [s.asset.id, s.other.id]
    results = run_race(s.engine, [lambda i=i: s.client.post(f'/reconciliation-items/{proposals[i][0]}/link-asset',
        json={"asset_id": str(targets[i]), "expected_version": versions[i]}, headers={"x-test-actor": "ab"[i]}) for i in range(2)], gate="sources")
    assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    with s.session() as db:
        links = list(db.scalars(select(EntitySourceLink).where(EntitySourceLink.customer_id == s.customer.id)))
        assert len(links) == 2 and {link.entity_id for link in links} == set(targets)
        relationships = list(db.scalars(select(ReconciliationItem).where(ReconciliationItem.customer_id == s.customer.id,
            ReconciliationItem.entity_type == "asset_relationship")))
        assert len(relationships) == 2
        assert all(row.observed_value_json["resolved_target_asset_id"] == str(s.other.id) for row in relationships)
        assert all(row.status == "open" for row in relationships)
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.customer_id == s.customer.id)) == 2


@pytest.mark.parametrize("predicate", ["fixture.serial", "vendor", "configuration", "purpose", "unknown_scalar"])
def test_f3_database_rejects_bypassing_single_value_service(committed, predicate):
    s = committed
    first, old = s.proposal(predicate, "A")
    second, new = s.proposal(predicate, "B", source=1)
    with s.session() as db:
        db.get(KnowledgeAssertion, old).is_accepted = True
        db.commit()
    with s.session() as db:
        db.get(KnowledgeAssertion, new).is_accepted = True
        with pytest.raises(IntegrityError):
            db.commit()
    with s.session() as db:
        assert db.get(KnowledgeAssertion, old).is_accepted
        assert not db.get(KnowledgeAssertion, new).is_accepted


@pytest.mark.parametrize("terminal", ["rejected", "retracted", "superseded"])
def test_f5_terminal_observation_lifecycle(committed, terminal):
    s = committed
    first, old = (s.proposal("name", "New observation", target=False, category="newly_discovered")
                  if terminal == "rejected" else s.proposal("fixture.serial", "A"))
    if terminal == "rejected":
        response = s.client.post(f'/reconciliation-items/{first}/reject', json={"reason": "Keep curated knowledge"})
        assert response.status_code == 200
        with s.session() as db:
            assert db.get(KnowledgeAssertion, old).confirmation_status == "rejected"
        same, identifier = s.proposal("name", "New observation", target=False, category="newly_discovered")
        assert identifier == old  # A repeated identical observation preserves its decision.
        with s.session() as db:
            assert not db.get(KnowledgeAssertion, old).is_accepted
            assert db.get(ReconciliationItem, first).status == "rejected"
        assert accept(s, same).status_code == 200  # Explicit fresh human reconsideration is allowed.
    elif terminal == "retracted":
        response = s.client.post(f'/assertions/{old}/retract', json={"reason": "Incorrect source claim", "confirm_provenance_gap": True})
        assert response.status_code == 200, response.text
        same, identifier = s.proposal("fixture.serial", "A")
        assert identifier != old
        assert accept(s, same).status_code == 200
        with s.session() as db:
            assert db.get(KnowledgeAssertion, old).retracted_at
            assert not db.get(KnowledgeAssertion, old).is_source_current
    else:
        changed, identifier = s.proposal("fixture.serial", "B")
        assert identifier != old
        assert accept(s, first).status_code == 409
        assert accept(s, changed).status_code == 200
        with s.session() as db:
            assert db.get(KnowledgeAssertion, old).superseded_by_id == identifier
            assert not db.get(KnowledgeAssertion, old).is_source_current
    with s.session() as db:
        assert db.get(KnowledgeAssertion, identifier).is_accepted
        assert db.get(KnowledgeAssertion, identifier).is_source_current


def test_f3_acceptance_versus_source_supersession(committed):
    s = committed
    first, old = s.proposal("hostname", "host-A")
    assert accept(s, first).status_code == 200
    second, selected = s.proposal("hostname", "host-B", source=1)
    # Both HTTP transactions hold different source rows before their work begins.
    # Ingestion updates source A's current assertion; acceptance replaces its
    # accepted value while retaining that source's historical supersession.
    payload = {"customer_id": str(s.customer.id), "site_id": str(s.site.id), "data_source_id": str(s.sources[0].id),
        "observations": [{"entity_kind": "asset", "external_id": "source-0", "name": s.asset.name,
            "asset_type": "virtual_machine", "facts": {"hostname": "host-C"}}]}
    with s.session() as db:
        ensure_asset_link(db, data_source_id=s.sources[0].id, asset=db.get(Asset, s.asset.id), external_id="source-0")
        db.commit()
    results = run_race(s.engine, [lambda: accept(s, second, actor="a"),
        lambda: s.client.post('/discovery/simulate', json=payload, headers={"x-test-actor": "b"})], gate="sources")
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    with s.session() as db:
        previous = db.get(KnowledgeAssertion, old)
        assert previous.superseded_by_id and not previous.is_source_current and not previous.is_accepted
        assert previous.acceptance_replaced_by_id == selected
        assert db.get(KnowledgeAssertion, selected).is_accepted
        fresh = db.get(KnowledgeAssertion, previous.superseded_by_id)
        assert fresh.value_json == "host-C" and fresh.is_source_current and not fresh.is_accepted


@pytest.mark.parametrize("race", ["asset", "asset_interface"])
def test_f1_concurrent_link_has_one_followup(committed, race):
    s = committed
    if race == "asset":
        identifier, claim = s.proposal("name", "Observed", target=False, category="newly_discovered")
        target, path, key = s.asset.id, "link-asset", "asset_id"
    else:
        with s.session() as db:
            ensure_asset_link(db, data_source_id=s.sources[0].id, asset=db.get(Asset, s.asset.id), external_id="owner")
            value = {"name": "eth0", "asset_external_id": "owner", "network_external_id": None,
                "ip_address": None, "mac_address": None, "is_primary": False}
            assertion, _ = record_assertion(db, customer_id=s.customer.id, site_id=s.site.id, subject_type="asset_interface",
                subject_external_id="eth0", data_source_id=s.sources[0].id, predicate="configuration", value=value)
            item, _ = create_item(db, assertion=assertion, category="newly_discovered", entity_type="asset_interface",
                entity_id=None, candidate_external_id="eth0", current_value=None, observed_value=value, recommended_action="Review")
            db.commit(); identifier, claim = item.id, assertion.id
        target, path, key = s.interface.id, "link-technical", "entity_id"
    version = review(s, identifier)[0]["version"]
    barrier = Barrier(2)
    def decide():
        barrier.wait(8)
        return s.client.post(f'/reconciliation-items/{identifier}/{path}', json={key: str(target), "expected_version": version})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: decide(), range(2)))
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    with s.session() as db:
        assert db.scalar(select(func.count()).select_from(ReconciliationItem).where(
            ReconciliationItem.assertion_id == claim, ReconciliationItem.status == "open")) == 1
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.customer_id == s.customer.id)) == 1


@pytest.mark.parametrize("sqlstate,expected", [("40P01", 409), ("40001", 409), ("55P03", 409), ("23505", 409), ("08006", None)])
def test_expected_database_conflicts_are_safe_and_other_errors_propagate(committed, monkeypatch, sqlstate, expected):
    from sqlalchemy.exc import DBAPIError
    s = committed
    identifier, _ = s.proposal()
    class DatabaseFailure(Exception):
        pass
    failure = DatabaseFailure("private database configuration")
    failure.sqlstate = sqlstate
    def fail(*args, **kwargs):
        raise DBAPIError("private SQL", {}, failure)
    monkeypatch.setattr(knowledge, "_lock_decision_sources", fail)
    if expected:
        response = s.client.post(f'/reconciliation-items/{identifier}/accept')
        assert response.status_code == expected
        assert "private" not in response.text and sqlstate not in response.text
    else:
        with pytest.raises(DBAPIError):
            s.client.post(f'/reconciliation-items/{identifier}/accept')
    with s.session() as db:
        assert db.get(ReconciliationItem, identifier).status == "open"
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.customer_id == s.customer.id)) == 0


def test_f5_http_reobservation_retains_evidence_and_canonical_ids(committed):
    from app.models import EvidenceRecord
    s = committed
    with s.session() as db:
        for index in range(2):
            ensure_asset_link(db, data_source_id=s.sources[index].id, asset=db.get(Asset, s.asset.id), external_id=f"source-{index}")
        db.commit()
    originals = []
    for source, value in [(0, "virtual_machine"), (1, "hypervisor_node"), (0, "virtual_machine"), (0, "virtual_machine")]:
        response = s.client.post('/discovery/simulate', json={"customer_id": str(s.customer.id), "site_id": str(s.site.id),
            "data_source_id": str(s.sources[source].id), "observations": [{"entity_kind": "asset", "external_id": f"source-{source}",
                "name": s.asset.name, "asset_type": value, "facts": {}}]})
        assert response.status_code == 200, response.text
        with s.session() as db:
            claim = db.scalar(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == s.asset.id,
                KnowledgeAssertion.data_source_id == s.sources[source].id, KnowledgeAssertion.predicate == "asset_type",
                KnowledgeAssertion.is_source_current.is_(True)))
            if len(originals) < 3:
                item = db.scalar(select(ReconciliationItem).where(ReconciliationItem.assertion_id == claim.id,
                    ReconciliationItem.status == "open"))
                assert item is not None
                identifier = item.id
            originals.append(claim.id)
        if len(originals) < 4:
            assert accept(s, identifier).status_code == 200
    assert originals[0] == originals[2] == originals[3] and originals[0] != originals[1]
    with s.session() as db:
        assert db.get(Asset, s.asset.id).asset_type == "virtual_machine"
        assert db.scalar(select(func.count()).select_from(Asset).where(Asset.customer_id == s.customer.id)) == 2
        assert db.scalar(select(func.count()).select_from(EvidenceRecord).where(EvidenceRecord.customer_id == s.customer.id)) == 4
        assert db.get(KnowledgeAssertion, originals[0]).is_accepted
        assert db.get(KnowledgeAssertion, originals[1]).is_source_current
    response = s.client.get(f'/assets/{s.asset.id}/knowledge-summary')
    group = next(row for row in response.json()["groups"] if row["predicate"] == "asset_type")
    assert group["canonical_consistency"] == "matches"
    assert len(group["accepted_values"]) == 1 and group["conflict"]


def test_f2_versionless_and_changed_back_manual_values_need_fresh_review(committed):
    s = committed
    identifier, _ = s.proposal("name", "Observed")
    old = review(s, identifier)[0]["version"]
    assert s.client.patch(f'/assets/{s.asset.id}', json={"name": "Temporary"}).status_code == 200
    assert s.client.post(f'/reconciliation-items/{identifier}/accept').status_code == 409
    assert s.client.patch(f'/assets/{s.asset.id}', json={"name": s.asset.name}).status_code == 200
    assert s.client.post(f'/reconciliation-items/{identifier}/accept').status_code == 409
    assert accept(s, identifier, version=old).status_code == 409
    assert accept(s, identifier).status_code == 200
