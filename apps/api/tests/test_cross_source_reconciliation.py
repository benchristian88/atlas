"""Two-source acceptance through real ingestion, HTTP decisions and PostgreSQL."""
from dataclasses import replace
import os
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select

from app.authorization import ActiveContext, get_active_context, get_principal
from app.database import get_db
from app.models import (Asset, AssetInterface, AssetRelationship, AuditEvent, Customer, DataSource,
                        EntitySourceLink, EvidenceRecord, KnowledgeAssertion, KnowledgeChange, Network,
                        ReconciliationItem, Site)
from app.routes import asset_interfaces, knowledge, networks
from app.services import aip_ingestion as aip
from app.services.entity_resolution import ensure_asset_link, ensure_technical_link
from app.services.knowledge_assertions import accept_assertion, record_assertion
from tests.i3_fixtures import message
from tests.test_i3_discovery import db, configured, new_run
from tests.test_reconciliation_entities import review, page, group_named, accept_all
from tests.test_reconciliation_listing import listing, NOW

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")


def rows(group):
    return ([group["parent"]] if group["parent"] else []) + [row for section in group["sections"] for row in section["items"]]


def presented(client, identifier):
    return next(row for group in page(client)["entities"] for row in rows(group) if row["id"] == str(identifier))


@pytest.fixture
def two_sources(db, configured):
    integration, principal, *_ = configured
    principal = replace(principal, grants=(replace(principal.grants[0], permissions=principal.grants[0].permissions |
        {"reconciliation.view", "assets.view", "assets.edit", "networks.view", "relationships.create"}),))
    customer = db.get(Customer, integration.customer_id)
    source_a = DataSource(customer_id=customer.id, site_id=integration.site_id, name="Source A", source_type="connector")
    db.add(source_a)
    host = Asset(customer_id=customer.id, site_id=integration.site_id, workspace_id=customer.workspace_id,
                 name="Fixture node", asset_type="hypervisor_node", source="discovery")
    asset = Asset(customer_id=customer.id, site_id=integration.site_id, workspace_id=customer.workspace_id,
                  name="grafana", asset_type="virtual_machine", source="discovery")
    network = Network(customer_id=customer.id, site_id=integration.site_id, name="Curated LAN", network_type="vlan",
                      vlan_id=9, cidr="192.0.2.0/24", gateway="192.0.2.1")
    db.add_all([host, asset, network]); db.flush()
    interface = AssetInterface(asset_id=asset.id, network_id=network.id, name="eth0", mac_address="02:00:00:00:00:01",
                               ip_address="192.0.2.8", is_primary=True)
    db.add(interface); db.flush()
    for target in (host, asset):
        ensure_asset_link(db, data_source_id=source_a.id, asset=target, external_id="a/" + target.name, observed_at=NOW)
    for target, kind in ((network, "network"), (interface, "asset_interface")):
        ensure_technical_link(db, source=source_a, target=target, entity_type=kind, external_id="a/" + target.name, observed_at=NOW)
    accepted, _ = record_assertion(db, customer_id=customer.id, site_id=integration.site_id,
        subject_type="asset_interface", subject_id=interface.id, subject_external_id="a/eth0", data_source_id=source_a.id,
        predicate="configuration", value={"mac_address": interface.mac_address, "ip_address": interface.ip_address}, observed_at=NOW)
    accept_assertion(db, accepted, user_id=principal.user.id)
    run = new_run(db, configured)
    payload = message(run, technical=True)
    payload["assets"][1]["name"] = "grafana"
    payload["interfaces"][0].update(asset_external_id="vm/1", mac_address="02:00:00:00:00:02", ip_address="192.0.2.9", is_primary=False)
    aip.accept_batch(db, run, payload)
    aip.finalise(db, run, integration, message(run, completion="partial"))
    run.dispatch_state = "settled"; db.commit()
    app = FastAPI()
    for router in (knowledge.router, asset_interfaces.router, networks.router):
        app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_active_context] = lambda: ActiveContext(customer.id, integration.site_id)
    with TestClient(app) as client:
        yield client, asset, host, interface, network, source_a, run, principal, app, payload, accepted


def link(client, item, identifier, kind="technical", version=None):
    return client.post(f'/reconciliation-items/{item["id"]}/link-{kind}', json={
        "asset_id" if kind == "asset" else "entity_id": str(identifier), "expected_version": version or item["version"]})


def test_two_source_ingestion_link_conflicts_dependencies_and_repeat(two_sources, db, configured):
    client, asset, host, interface, network, source_a, run, _, _, payload, accepted_a = two_sources
    original_ids = (asset.id, interface.id)
    evidence_before = db.scalar(select(func.count()).select_from(EvidenceRecord).where(EvidenceRecord.discovery_run_id == run.id))
    parent = group_named(client, "grafana")["parent"]
    assert parent["category"] == "possible_duplicate"
    assert link(client, parent, asset.id, "asset").status_code == 200
    group = group_named(client, "grafana")
    interface_row = next(row for row in rows(group) if row["technical_identity"])
    assert interface_row["link_asset_id"] == str(asset.id) and interface_row["can_link_technical"]
    assert all("grafana to exist" not in (row["blocked_reason"] or "") for row in rows(group))
    # The Network is genuinely unresolved; bulk does not invent it or bypass identity review.
    partial = accept_all(client, group)
    assert any(entry["id"] == interface_row["id"] for entry in partial["blocked"])
    before = (interface.mac_address, interface.ip_address, interface.network_id, interface.is_primary)
    assert link(client, presented(client, interface_row["id"]), interface.id).status_code == 200
    assert (interface.mac_address, interface.ip_address, interface.network_id, interface.is_primary) == before
    configuration = next(row for row in rows(group_named(client, "grafana")) if row["entity_type"] == "asset_interface")
    assert configuration["category"] == "changed" and not configuration["can_accept"]
    assert configuration["current"]["mac_address"] == before[0]
    assert accepted_a.is_accepted
    network_row = group_named(client, "Fixture LAN")["parent"]
    assert link(client, network_row, network.id).status_code == 200
    assert network.vlan_id == 9 and network.cidr == "192.0.2.0/24"
    configuration = next(row for row in rows(group_named(client, "grafana")) if row["entity_type"] == "asset_interface")
    assert configuration["can_accept"]
    assert client.post(f'/reconciliation-items/{configuration["id"]}/accept', json={"expected_version": configuration["version"]}).status_code == 200
    assert (interface.mac_address, interface.ip_address, interface.is_primary) == ("02:00:00:00:00:02", "192.0.2.9", False)
    assert interface.network_id == network.id
    assert link(client, group_named(client, "Fixture node")["parent"], host.id, "asset").status_code == 200
    assert not accept_all(client, group_named(client, "grafana"))["failed"]
    relationship = db.scalar(select(AssetRelationship).where(AssetRelationship.source_asset_id == asset.id))
    assert relationship.target_asset_id == host.id
    assert (asset.id, interface.id) == original_ids
    assert db.scalar(select(func.count()).select_from(Asset).where(Asset.customer_id == asset.customer_id)) == 2
    assert db.scalar(select(func.count()).select_from(AssetInterface).where(AssetInterface.asset_id == asset.id)) == 1
    links = list(db.scalars(select(EntitySourceLink).where(EntitySourceLink.customer_id == asset.customer_id)))
    assert len(links) == 8 and len({row.data_source_id for row in links}) == 2
    assert db.scalar(select(func.count()).select_from(EvidenceRecord).where(EvidenceRecord.discovery_run_id == run.id)) == evidence_before
    assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == "reconciliation.linked", AuditEvent.customer_id == asset.customer_id)) == 4
    assert db.scalar(select(func.count()).select_from(KnowledgeChange).where(KnowledgeChange.change_type == "source_linked", KnowledgeChange.customer_id == asset.customer_id)) == 4
    # Repeated partial discovery retains canonical identity and current claims.
    next_run = new_run(db, configured)
    repeated = message(next_run, technical=True)
    for key in ("assets", "interfaces", "networks", "relationships"):
        repeated[key] = payload[key]
    aip.accept_batch(db, next_run, repeated)
    aip.finalise(db, next_run, configured[0], message(next_run, completion="partial"))
    assert not db.scalar(select(ReconciliationItem.id).join(KnowledgeAssertion).where(
        KnowledgeAssertion.discovery_run_id == next_run.id, ReconciliationItem.status == "open",
        ReconciliationItem.category.in_(["newly_discovered", "possible_duplicate"])))
    assert db.scalar(select(func.count()).select_from(AssetInterface).where(AssetInterface.asset_id == asset.id)) == 1


@pytest.mark.parametrize("kind", ["network", "asset_interface"])
@pytest.mark.parametrize("stale", ["version", "retracted", "superseded", "not_current", "context", "identity"])
def test_link_rejects_stale_or_mismatched_identity(two_sources, db, kind, stale):
    client, asset, _, interface, network, *_ = two_sources
    assert link(client, group_named(client, "grafana")["parent"], asset.id, "asset").status_code == 200
    row = next(row for group in page(client)["entities"] for row in rows(group)
               if row["entity_type"] == kind and row["technical_identity"])
    item = db.get(ReconciliationItem, uuid.UUID(row["id"]))
    claim = db.get(KnowledgeAssertion, item.assertion_id)
    if stale == "retracted": claim.retracted_at = NOW
    elif stale == "superseded": claim.superseded_by_id = claim.id
    elif stale == "not_current": claim.is_source_current = False
    elif stale == "context": claim.site_id = None
    elif stale == "identity": claim.subject_external_id = "unrelated"
    db.flush()
    response = link(client, row, network.id if kind == "network" else interface.id,
                    version="0" * 64 if stale == "version" else row["version"])
    assert response.status_code == 409, response.text
    assert item.status == "open"


@pytest.mark.parametrize("boundary", ["customer", "site", "owner", "context", "permission", "decision_permission"])
def test_target_scope_permissions_and_no_hidden_details(two_sources, db, boundary):
    client, asset, host, interface, network, _, _, principal, app, *_ = two_sources
    assert link(client, group_named(client, "grafana")["parent"], asset.id, "asset").status_code == 200
    row = next(row for row in rows(group_named(client, "grafana")) if row["technical_identity"])
    owner = host
    if boundary in {"customer", "site"}:
        customer = db.get(Customer, asset.customer_id)
        if boundary == "customer":
            customer = Customer(workspace_id=customer.workspace_id, name="Hidden customer")
            db.add(customer); db.flush()
        site = Site(customer_id=customer.id, name="Hidden site"); db.add(site); db.flush()
        owner = Asset(workspace_id=customer.workspace_id, customer_id=customer.id, site_id=site.id,
                      name="Hidden owner", asset_type="virtual_machine")
        db.add(owner); db.flush()
    target = AssetInterface(asset_id=owner.id, name="hidden-interface", mac_address="02:00:00:00:00:ff")
    db.add(target); db.flush()
    if boundary == "context":
        app.dependency_overrides[get_active_context] = lambda: ActiveContext(asset.customer_id, uuid.uuid4())
    if boundary in {"permission", "decision_permission"}:
        removed = "networks.edit" if boundary == "permission" else "reconciliation.decide"
        limited = replace(principal, grants=(replace(principal.grants[0], permissions=principal.grants[0].permissions - {removed}),))
        app.dependency_overrides[get_principal] = lambda: limited
    response = link(client, row, target.id)
    assert response.status_code in {403, 404, 409}, response.text
    assert "hidden-interface" not in response.text and "02:00:00:00:00:ff" not in response.text
    assert not db.scalar(select(EntitySourceLink.id).where(EntitySourceLink.data_source_id == row["data_source_id"], EntitySourceLink.interface_id == target.id))


def test_collision_is_actionable_and_bulk_keeps_independent_success(two_sources, db):
    client, asset, _, interface, network, *_ = two_sources
    assert link(client, group_named(client, "grafana")["parent"], asset.id, "asset").status_code == 200
    assert link(client, group_named(client, "Fixture LAN")["parent"], network.id).status_code == 200
    group = group_named(client, "grafana")
    row = next(row for row in rows(group) if row["technical_identity"])
    response = client.post(f'/reconciliation-items/{row["id"]}/accept', json={"expected_version": row["version"]})
    assert response.status_code == 409 and "explicitly link" in response.json()["detail"]
    result = accept_all(client, group)
    assert result["accepted"] and result["failed"] and result["blocked"]
    assert any("explicitly link" in entry["reason"] for entry in result["failed"])
    assert interface.mac_address == "02:00:00:00:00:01"


def test_link_propagates_technical_fact_identity_and_replay_is_denied(review, db):
    client, entity, fact, interface_proposal, _, principal, app, (customer, site, source, _) = review
    principal = replace(principal, grants=(replace(principal.grants[0], permissions=principal.grants[0].permissions | {"networks.view"}),))
    app.dependency_overrides[get_principal] = lambda: principal
    parent, _ = entity("esphome")
    assert client.post(f"/reconciliation-items/{parent.id}/accept").status_code == 200
    proposal, _ = interface_proposal(parent, "eth0")
    child, claim = fact(proposal, "fixture.vlan_tag", "asset_interface")
    target = AssetInterface(asset_id=parent.entity_id, name="eth0", mac_address="02:00:00:00:00:01")
    db.add(target); db.flush()
    row = presented(client, proposal.id)
    assert link(client, row, target.id).status_code == 200
    assert claim.subject_id == target.id and not claim.is_accepted
    child_row = presented(client, child.id)
    assert child_row["can_accept"]
    assert link(client, row, target.id).status_code == 409
    assert client.post(f"/reconciliation-items/{child.id}/accept", json={"expected_version": child_row["version"]}).status_code == 200
    from types import SimpleNamespace
    from app.services.simulated_discovery import ingest_technical_observation
    run = review[-1][-1]
    ingest_technical_observation(db, run=run, source=source, evidence=SimpleNamespace(id=None, observed_at=NOW),
        entity_type="asset_interface", user_id=principal.user.id, observation={
            **proposal.observed_value_json, "external_id": proposal.candidate_external_id,
            "facts": [{"key": claim.predicate, "value": claim.value_json, **claim.fact_metadata}]})
    assert db.scalar(select(func.count()).select_from(KnowledgeAssertion).where(
        KnowledgeAssertion.data_source_id == source.id, KnowledgeAssertion.subject_type == "asset_interface",
        KnowledgeAssertion.subject_external_id == proposal.candidate_external_id, KnowledgeAssertion.predicate == claim.predicate)) == 1


def test_candidate_lists_use_real_permissions_owner_and_context(two_sources, db):
    client, asset, host, interface, network, _, _, principal, app, *_ = two_sources
    other = AssetInterface(asset_id=host.id, name="eth0")
    db.add(other); db.flush()
    response = client.get("/asset-interfaces", params={"asset_id": str(asset.id), "limit": 100, "offset": 0})
    assert response.status_code == 200 and [row["id"] for row in response.json()] == [str(interface.id)]
    response = client.get("/networks", params={"customer_id": str(asset.customer_id), "site_id": str(asset.site_id)})
    assert response.status_code == 200 and [row["id"] for row in response.json()] == [str(network.id)]
    limited = replace(principal, grants=(replace(principal.grants[0], permissions=principal.grants[0].permissions - {"networks.view"}),))
    app.dependency_overrides[get_principal] = lambda: limited
    assert client.get("/asset-interfaces", params={"asset_id": str(asset.id)}).status_code == 403
    assert client.get("/networks").status_code == 403


def test_asset_link_does_not_accept_a_conflicting_name(review, db):
    client, entity, _, _, _, principal, app, (customer, site, source, _) = review
    principal = replace(principal, grants=(replace(principal.grants[0], permissions=principal.grants[0].permissions | {"assets.edit"}),))
    app.dependency_overrides[get_principal] = lambda: principal
    asset = Asset(workspace_id=customer.workspace_id, customer_id=customer.id, site_id=site.id,
                  name="Curated name", asset_type="virtual_machine")
    db.add(asset); db.flush()
    proposal, claim = entity("Observed name")
    assert link(client, presented(client, proposal.id), asset.id, "asset").status_code == 200
    assert asset.name == "Curated name" and not claim.is_accepted
    followup = next(row for row in rows(group_named(client, "Curated name")) if row["status"] == "open")
    assert followup["current"] == "Curated name" and followup["proposed"] == "Observed name"


@pytest.mark.parametrize("bulk", [False, True])
def test_configuration_version_includes_the_current_accepted_values(two_sources, db, bulk):
    client, asset, _, interface, network, *_ = two_sources
    assert link(client, group_named(client, "grafana")["parent"], asset.id, "asset").status_code == 200
    assert link(client, group_named(client, "Fixture LAN")["parent"], network.id).status_code == 200
    row = next(row for row in rows(group_named(client, "grafana")) if row["technical_identity"])
    assert link(client, row, interface.id).status_code == 200
    group = group_named(client, "grafana")
    row = next(row for row in rows(group) if row["entity_type"] == "asset_interface")
    interface.ip_address = "192.0.2.99"; db.flush()
    if bulk:
        result = accept_all(client, group)
        assert any(entry["id"] == row["id"] and "proposal changed" in entry["reason"] for entry in result["failed"])
    else:
        response = client.post(f'/reconciliation-items/{row["id"]}/accept', json={"expected_version": row["version"]})
        assert response.status_code == 409
    assert interface.ip_address == "192.0.2.99"


@pytest.mark.parametrize("action", ["accept", "link-asset", "reject", "defer"])
def test_decide_permission_in_another_site_cannot_fall_back_to_asset_edit(review, action):
    client, entity, _, _, _, principal, app, (customer, site, _, _) = review
    proposal, _ = entity("Restricted decision")
    grants = (replace(principal.grants[0], permissions=frozenset({"reconciliation.view", "assets.edit"})),
              replace(principal.grants[0], scope_type="site", customer_id=customer.id, site_id=uuid.uuid4(),
                      permissions=frozenset({"reconciliation.decide"})))
    app.dependency_overrides[get_principal] = lambda: replace(principal, grants=grants)
    response = client.post(f"/reconciliation-items/{proposal.id}/{action}", json={"asset_id": str(uuid.uuid4())} if action == "link-asset" else {})
    assert response.status_code == 404 and proposal.status == "open"


@pytest.mark.parametrize("boundary", ["customer", "site"])
def test_network_link_cannot_cross_target_scope(two_sources, db, boundary):
    client, asset, _, _, _, _, _, _, _, *_ = two_sources
    customer = db.get(Customer, asset.customer_id)
    if boundary == "customer":
        customer = Customer(workspace_id=customer.workspace_id, name="Hidden network customer")
        db.add(customer); db.flush()
    site = Site(customer_id=customer.id, name="Hidden network site"); db.add(site); db.flush()
    target = Network(customer_id=customer.id, site_id=site.id, name="Hidden network", network_type="lan", cidr="198.51.100.0/24")
    db.add(target); db.flush()
    response = link(client, group_named(client, "Fixture LAN")["parent"], target.id)
    assert response.status_code == 404
    assert "Hidden network" not in response.text and "198.51.100" not in response.text


@pytest.mark.parametrize("race", ["link_link", "link_accept", "competing_items"])
def test_concurrent_technical_decisions_retain_one_identity(race):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi import HTTPException
    from sqlalchemy import create_engine, delete
    from sqlalchemy.orm import Session
    from app.models import Base, User, Workspace
    from app.schemas import ReconciliationLinkTechnicalRequest
    from app.services.reconciliation import create_item
    from tests.test_administration import make_principal, request

    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"], hide_parameters=True)
    principal = make_principal("reconciliation.decide", "networks.create", "networks.edit")
    principal.user.email = uuid.uuid4().hex + "@example.test"
    customer_id = workspace_id = None
    try:
        with Session(engine, autoflush=False, expire_on_commit=False) as setup:
            setup.add(principal.user)
            workspace = Workspace(name="Technical concurrency", slug=uuid.uuid4().hex)
            setup.add(workspace); setup.flush(); workspace_id = workspace.id
            customer = Customer(workspace_id=workspace.id, name="Technical concurrency")
            setup.add(customer); setup.flush(); customer_id = customer.id
            site = Site(customer_id=customer.id, name="Technical concurrency")
            setup.add(site); setup.flush()
            source = DataSource(customer_id=customer.id, site_id=site.id, name="Concurrent source", source_type="connector")
            asset = Asset(workspace_id=workspace.id, customer_id=customer.id, site_id=site.id, name="Concurrent owner", asset_type="virtual_machine")
            setup.add_all([source, asset]); setup.flush()
            ensure_asset_link(setup, data_source_id=source.id, asset=asset, external_id="owner", observed_at=NOW)
            targets = [AssetInterface(asset_id=asset.id, name=name) for name in ("eth0", "eth1")]
            setup.add_all(targets); setup.flush()
            claim, _ = record_assertion(setup, customer_id=customer.id, site_id=site.id, subject_type="asset_interface",
                subject_external_id="observed/eth0", data_source_id=source.id, predicate="configuration", observed_at=NOW,
                value={"name": "eth0", "asset_external_id": "owner", "network_external_id": None, "is_primary": False})
            item, _ = create_item(setup, assertion=claim, category="newly_discovered", entity_type="asset_interface",
                entity_id=None, candidate_external_id="observed/eth0", current_value=None, observed_value=claim.value_json, recommended_action="Review")
            second = item
            if race == "competing_items":
                second = ReconciliationItem(customer_id=customer.id, site_id=site.id, category="newly_discovered", status="open",
                    entity_type="asset_interface", candidate_external_id="observed/eth0", assertion_id=claim.id, observed_value_json=claim.value_json)
                setup.add(second); setup.flush()
            identifiers = [item.id, second.id]
            target_ids = [target.id for target in targets]
            context = ActiveContext(customer.id, site.id)
            setup.commit()
        barrier = Barrier(2)
        def decide(index):
            with Session(engine, autoflush=False, expire_on_commit=False) as connection:
                barrier.wait(timeout=10)
                try:
                    if race == "link_accept" and index:
                        knowledge.accept_reconciliation_item(identifiers[index], request(), None, principal, connection, context)
                    else:
                        knowledge.link_reconciliation_technical(identifiers[index], ReconciliationLinkTechnicalRequest(entity_id=target_ids[index]), request(), principal, connection, context)
                    return 200
                except HTTPException as error:
                    connection.rollback()
                    return error.status_code
        with ThreadPoolExecutor(max_workers=2) as workers:
            assert sorted(workers.map(decide, range(2))) == [200, 409]
        with Session(engine, autoflush=False, expire_on_commit=False) as check:
            links = list(check.scalars(select(EntitySourceLink).where(EntitySourceLink.customer_id == customer_id,
                EntitySourceLink.entity_type == "asset_interface")))
            assert len(links) == 1 and links[0].interface_id in target_ids
            assert check.scalar(select(func.count()).select_from(AssetInterface).where(AssetInterface.asset_id == asset.id)) == 2
            assert check.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.customer_id == customer_id)) == 1
    finally:
        with engine.begin() as connection:
            if customer_id:
                for table in reversed(Base.metadata.sorted_tables):
                    if "customer_id" in table.c:
                        connection.execute(delete(table).where(table.c.customer_id == customer_id))
                connection.execute(delete(Customer).where(Customer.id == customer_id))
            if workspace_id:
                connection.execute(delete(Workspace).where(Workspace.id == workspace_id))
            connection.execute(delete(User).where(User.id == principal.user.id))
        engine.dispose()
