"""AT-B02: observed Interface facts never imply canonical Network membership."""
from dataclasses import replace
from datetime import timedelta
import json
import os
from types import SimpleNamespace
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, select

from app.authorization import ActiveContext, get_active_context, get_principal
from app.database import get_db
from app.models import (Asset, AssetInterface, AssetType, AuditEvent, Customer, DataSource, EvidenceRecord,
                        KnowledgeAssertion, KnowledgeChange, Network, ReconciliationItem, Site)
from app.routes import asset_interfaces, knowledge, topology
from app.services.entity_resolution import ensure_asset_link, ensure_technical_link
from app.services.knowledge_assertions import accept_assertion, record_assertion
from app.services.simulated_discovery import ingest_technical_observation
from tests.test_i3_discovery import db, configured, new_run
from tests.test_reconciliation_listing import NOW
from tests.test_cross_source_reconciliation import presented

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")


@pytest.fixture
def case(db, configured):
    integration, principal, *_ = configured
    principal = replace(principal, grants=(replace(principal.grants[0], permissions=principal.grants[0].permissions |
        {"assets.view", "reconciliation.view", "networks.view", "topology.view"}),))
    source = db.get(DataSource, integration.data_source_id)
    customer = db.get(Customer, integration.customer_id)
    asset = Asset(customer_id=customer.id, site_id=integration.site_id, workspace_id=customer.workspace_id,
                  name="Tagged guest", asset_type="virtual_machine")
    network = Network(customer_id=customer.id, site_id=integration.site_id, name="Curated LAN", network_type="vlan", vlan_id=9)
    db.add_all([asset, network]); db.flush()
    interface = AssetInterface(asset_id=asset.id, network_id=network.id, name="eth0", ip_address="192.0.2.8", is_primary=True)
    db.add(interface); db.flush()
    ensure_asset_link(db, data_source_id=source.id, asset=asset, external_id="guest", observed_at=NOW)
    ensure_technical_link(db, source=source, target=interface, entity_type="asset_interface", external_id="nic", observed_at=NOW)
    app = FastAPI()
    for router in (knowledge.router, asset_interfaces.router, topology.router):
        app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_active_context] = lambda: ActiveContext(customer.id, integration.site_id)

    sequence = 0
    def ingest(*, facts=True, external="nic", **changes):
        nonlocal sequence
        sequence += 1
        run = new_run(db, configured)
        evidence = EvidenceRecord(data_source_id=source.id, discovery_run_id=run.id, observed_at=NOW + timedelta(hours=sequence),
            customer_id=customer.id, site_id=integration.site_id, entity_kind="asset_interface",
            payload_json={"private_raw": "must never be returned"})
        db.add(evidence); db.flush()
        observation = {"external_id": external, "asset_external_id": "guest", "name": "eth0", "is_primary": False,
                       "ip_address": "192.0.2.9", "mac_address": "02:00:00:00:00:09", "facts": []}
        if facts:
            observation["facts"] = facts if isinstance(facts, list) else [
                {"key": "proxmox.vlan_tag", "value": 22, "value_type": "integer", "class": "configuration", "cardinality": "single"},
                {"key": "proxmox.bridge_name", "value": "vmbr0", "value_type": "string", "class": "configuration", "cardinality": "single"},
            ]
        observation.update(changes)
        ingest_technical_observation(db, run=run, source=source, evidence=evidence, observation=observation,
                                     entity_type="asset_interface", user_id=principal.user.id)
        run.status, run.dispatch_state = "completed", "settled"
        db.flush()
        return run

    with TestClient(app) as client:
        yield SimpleNamespace(**locals())


def detail(c):
    result = c.client.get("/asset-interfaces", params={"asset_id": str(c.asset.id), "include_knowledge": "true"})
    assert result.status_code == 200, result.text
    return result.json()


def configuration(c):
    item = c.db.scalar(select(ReconciliationItem).join(KnowledgeAssertion).where(
        ReconciliationItem.entity_type == "asset_interface", ReconciliationItem.status == "open",
        KnowledgeAssertion.customer_id == c.customer.id, KnowledgeAssertion.predicate == "configuration"))
    return presented(c.client, item.id)


def accept(c, row):
    result = c.client.post(f'/reconciliation-items/{row["id"]}/accept', json={"expected_version": row["version"]})
    assert result.status_code == 200, result.text


def test_omitted_reference_preserves_manual_link_preview_changes_and_operator_unlink(case):
    c = case
    c.ingest()
    row = configuration(c)
    assert row["proposed"]["network_id"] == str(c.network.id)
    assert row["proposed"]["network"] == c.network.name
    assert "network_external_id" not in row["proposed"]
    accept(c, row)
    c.db.refresh(c.interface)
    assert c.interface.network_id == c.network.id
    assert (c.interface.ip_address, c.interface.is_primary) == ("192.0.2.9", False)
    change = c.db.scalar(select(KnowledgeChange).where(KnowledgeChange.reconciliation_item_id == uuid.UUID(row["id"])))
    assert change.previous_value_json["network_id"] == change.new_value_json["network_id"] == str(c.network.id)
    audits = list(c.db.scalars(select(AuditEvent).where(AuditEvent.target_id == uuid.UUID(row["id"]))))
    assert len(audits) == 1 and audits[0].event_type == "reconciliation.accepted"
    assert "cleared" not in json.dumps([a.metadata_ for a in audits])
    # Re-observation does not propose an unlink simply because the canonical link exists.
    c.ingest(facts=False)
    assert not c.db.scalar(select(ReconciliationItem.id).join(KnowledgeAssertion).where(
        ReconciliationItem.status == "open", KnowledgeAssertion.customer_id == c.customer.id,
        KnowledgeAssertion.predicate == "configuration"))
    result = c.client.patch(f"/asset-interfaces/{c.interface.id}", json={"network_id": None})
    assert result.status_code == 200 and result.json()["network_id"] is None


def test_whole_configuration_apply_preserves_locked_membership(case):
    c = case
    c.ingest()
    accept(c, configuration(c))
    c.db.refresh(c.interface)
    assert c.interface.network_id == c.network.id
    assert c.interface.ip_address == "192.0.2.9"


def test_intervening_manual_assignment_requires_refresh_and_apply_uses_new_link(case):
    c = case
    c.ingest()
    old = configuration(c)
    network = Network(customer_id=c.customer.id, site_id=c.asset.site_id, name="New manual LAN", network_type="lan")
    c.db.add(network); c.db.flush()
    assert c.client.patch(f"/asset-interfaces/{c.interface.id}", json={"network_id": str(network.id)}).status_code == 200
    response = c.client.post(f'/reconciliation-items/{old["id"]}/accept', json={"expected_version": old["version"]})
    assert response.status_code == 409
    fresh = configuration(c)
    assert fresh["proposed"]["network_id"] == str(network.id)
    accept(c, fresh)
    assert c.interface.network_id == network.id
    change = c.db.scalar(select(KnowledgeChange).where(KnowledgeChange.reconciliation_item_id == uuid.UUID(old["id"])))
    assert change.previous_value_json["network_id"] == change.new_value_json["network_id"] == str(network.id)


@pytest.mark.parametrize("candidate_count", [1, 2])
def test_tagged_new_interface_has_facts_but_no_membership_even_with_vlan_matches(case, candidate_count):
    c = case
    for index in range(candidate_count):
        c.db.add(Network(customer_id=c.customer.id, site_id=c.asset.site_id, name=f"VLAN match {index}", network_type="vlan", vlan_id=22))
    c.db.flush()
    c.ingest(external="new-nic", name="eth1")
    accept(c, configuration(c))
    interface = c.db.scalar(select(AssetInterface).where(AssetInterface.asset_id == c.asset.id, AssetInterface.name == "eth1"))
    for claim in c.db.scalars(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == interface.id, KnowledgeAssertion.fact_metadata.is_not(None))):
        accept_assertion(c.db, claim, user_id=c.principal.user.id)
    c.db.flush()
    row = next(row for row in detail(c) if row["id"] == str(interface.id))
    assert row["network_id"] is None and row["assigned_network"] is None
    assert {fact["value"] for fact in row["observed_facts"]} == {22, "vmbr0"}
    assert all(fact["is_accepted"] and fact["source_name"] == c.source.name for fact in row["observed_facts"])
    asset_type = c.db.scalar(select(AssetType).where(AssetType.key == c.asset.asset_type))
    result = c.client.get("/topology/connectivity", params={"focus_asset_id": str(c.asset.id), "category_ids": str(asset_type.category_id)})
    assert result.status_code == 200, result.text
    assert str(interface.id) not in json.dumps(result.json().get("edges", []))
    assert any(edge["key"] == f"interface:{c.interface.id}" for edge in result.json()["edges"])


def test_explicit_approved_source_network_reference_and_unresolved_reference(case):
    c = case
    c.ingest(network_external_id="approved-network")
    row = configuration(c)
    assert not row["can_accept"]
    assert row["proposed"]["network_id"] == str(c.network.id)
    result = c.client.post(f'/reconciliation-items/{row["id"]}/accept', json={"expected_version": row["version"]})
    assert result.status_code == 409 and c.interface.network_id == c.network.id
    target = Network(customer_id=c.customer.id, site_id=c.asset.site_id, name="Approved exact target", network_type="vlan", vlan_id=44)
    c.db.add(target); c.db.flush()
    ensure_technical_link(c.db, source=c.source, target=target, entity_type="network", external_id="approved-network", observed_at=NOW)
    accept(c, configuration(c))
    assert c.interface.network_id == target.id


def test_aip_null_is_invalid_and_omission_remains_valid(case):
    from atlas_connector_sdk.aip import validate_batch
    from atlas_connector_sdk.contracts import ContractError
    from tests.i3_fixtures import message
    c = case
    run = new_run(c.db, c.configured)
    payload = message(run, technical=True)
    payload["interfaces"][0].pop("network_external_id")
    assert validate_batch(payload, run.execution_provenance["manifest"]) is payload
    payload["interfaces"][0]["network_external_id"] = None
    with pytest.raises(ContractError, match="invalid_aip"):
        validate_batch(payload, run.execution_provenance["manifest"])


@pytest.mark.parametrize("same_customer", [False, True])
def test_network_reference_cannot_resolve_through_foreign_source_link(case, same_customer):
    c = case
    customer = c.customer if same_customer else Customer(workspace_id=c.customer.workspace_id, name="Foreign customer")
    if not same_customer:
        c.db.add(customer); c.db.flush()
    site = Site(customer_id=customer.id, name="Foreign site")
    c.db.add(site); c.db.flush()
    source = DataSource(customer_id=customer.id, site_id=site.id, name="Foreign source", source_type="connector")
    target = Network(customer_id=customer.id, site_id=site.id, name="Foreign target", network_type="vlan", vlan_id=22)
    c.db.add_all([source, target]); c.db.flush()
    ensure_technical_link(c.db, source=source, target=target, entity_type="network", external_id="shared-label", observed_at=NOW)
    c.ingest(network_external_id="shared-label")
    row = configuration(c)
    assert not row["can_accept"]
    assert target.name not in json.dumps(row) and str(target.id) not in json.dumps(row)
    result = c.client.post(f'/reconciliation-items/{row["id"]}/accept', json={"expected_version": row["version"]})
    assert result.status_code == 409
    assert c.interface.network_id == c.network.id


def test_accepted_and_new_unaccepted_observations_and_later_omission(case):
    c = case
    c.ingest()
    accepted = c.db.scalar(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == c.interface.id,
        KnowledgeAssertion.predicate == "proxmox.vlan_tag"))
    accept_assertion(c.db, accepted, user_id=c.principal.user.id); c.db.flush()
    c.ingest(facts=[{"key": "proxmox.vlan_tag", "value": 33, "value_type": "integer", "class": "configuration", "cardinality": "single"}])
    row = detail(c)[0]
    assert row["assigned_network"]["vlan_id"] == 9
    facts = [f for f in row["observed_facts"] if f["predicate"] == "proxmox.vlan_tag"]
    assert {(f["value"], f["is_accepted"]) for f in facts} == {(22, True), (33, False)}
    before = row["observed_facts"]
    c.ingest(facts=False)
    assert detail(c)[0]["observed_facts"] == before
    assert accepted.is_accepted  # No stored freshness/withdrawal mutation by the read model.


@pytest.mark.parametrize("boundary", ["customer", "site", "assets_permission", "networks_permission", "context"])
def test_read_scope_never_discloses_hidden_interfaces(case, boundary):
    c = case
    c.ingest()
    if boundary == "context":
        c.app.dependency_overrides[get_active_context] = lambda: ActiveContext(c.customer.id, uuid.uuid4())
    else:
        grant = replace(c.principal.grants[0], scope_type="site", customer_id=c.customer.id, site_id=c.asset.site_id)
        if boundary == "customer": grant = replace(grant, customer_id=uuid.uuid4())
        if boundary == "site": grant = replace(grant, site_id=uuid.uuid4())
        if boundary.endswith("permission"):
            grant = replace(grant, permissions=grant.permissions - {"assets.view" if boundary == "assets_permission" else "networks.view"})
        limited = replace(c.principal, grants=(grant,))
        c.app.dependency_overrides[get_principal] = lambda: limited
    response = c.client.get("/asset-interfaces", params={"asset_id": str(c.asset.id), "include_knowledge": "true"})
    assert response.status_code in {200, 403, 404}
    assert c.interface.name not in response.text and c.source.name not in response.text and c.network.name not in response.text


@pytest.mark.parametrize("same_customer", [False, True])
def test_batched_bounded_read_redacts_foreign_provenance_and_membership(case, same_customer):
    c = case
    c.ingest()
    customer = c.customer if same_customer else Customer(workspace_id=c.customer.workspace_id, name="Restricted customer")
    if not same_customer:
        c.db.add(customer); c.db.flush()
    site = Site(customer_id=customer.id, name="Restricted site")
    c.db.add(site); c.db.flush()
    hidden = DataSource(customer_id=customer.id, site_id=site.id, name="Restricted source", source_type="connector")
    hidden_network = Network(customer_id=customer.id, site_id=site.id, name="Restricted Network", network_type="vlan", vlan_id=999)
    c.db.add_all([hidden, hidden_network]); c.db.flush()
    # Legacy cross-context assertion pointers and invalid canonical links are not disclosure authority.
    claim = c.db.scalar(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == c.interface.id, KnowledgeAssertion.predicate == "proxmox.vlan_tag"))
    claim.data_source_id = hidden.id
    c.interface.network_id = hidden_network.id
    for index in range(30):
        c.db.add(AssetInterface(asset_id=c.asset.id, name=f"nic-{index}"))
    c.db.flush()
    statements = []
    def capture(conn, cursor, sql, params, context, many):
        if sql.lstrip().startswith("SELECT"): statements.append(sql)
    event.listen(c.db.bind, "before_cursor_execute", capture)
    try:
        result = detail(c)
    finally:
        event.remove(c.db.bind, "before_cursor_execute", capture)
    assert len(result) == 31 and len(statements) <= 5
    encoded = json.dumps(result)
    assert hidden.name not in encoded and hidden_network.name not in encoded and str(hidden_network.id) not in encoded
    assert "private_raw" not in encoded and "evidence_record_id" not in encoded and "discovery_run_id" not in encoded
    assert all(len(row["observed_facts"]) <= 4 for row in result)
    assert all(fact["predicate"] != "proxmox.vlan_tag" for row in result for fact in row["observed_facts"])


def test_retired_detail_still_shows_facts_and_retained_history_still_blocks_delete(case):
    c = case
    c.ingest()
    c.asset.status = "retired"; c.db.flush()
    assert detail(c)[0]["observed_facts"]
    principal = replace(c.principal, grants=(replace(c.principal.grants[0], permissions=c.principal.grants[0].permissions | {"networks.delete"}),))
    c.app.dependency_overrides[get_principal] = lambda: principal
    response = c.client.delete(f"/asset-interfaces/{c.interface.id}")
    assert response.status_code == 409 and "retained discovery history" in response.text


def test_projection_requires_asset_and_default_list_contract_stays_compatible(case):
    c = case
    assert c.client.get("/asset-interfaces?include_knowledge=true").status_code == 422
    result = c.client.get("/asset-interfaces", params={"asset_id": str(c.asset.id)})
    assert result.status_code == 200
    assert "observed_facts" not in result.json()[0] and "assigned_network" not in result.json()[0]


def test_fact_history_is_ranked_in_database_and_rejected_retracted_values_are_excluded(case):
    c = case
    c.ingest()
    for index in range(60):
        record_assertion(c.db, customer_id=c.customer.id, site_id=c.asset.site_id,
            subject_type="asset_interface", subject_id=c.interface.id, subject_external_id="nic",
            predicate="proxmox.vlan_tag", value=index, data_source_id=c.source.id,
            observed_at=NOW + timedelta(days=index + 1))
    c.db.flush()
    result = detail(c)[0]["observed_facts"]
    vlan = [fact for fact in result if fact["predicate"] == "proxmox.vlan_tag"]
    assert len(vlan) == 1 and vlan[0]["value"] == 59
    latest = c.db.scalar(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_id == c.interface.id,
        KnowledgeAssertion.predicate == "proxmox.vlan_tag", KnowledgeAssertion.is_source_current.is_(True)))
    latest.confirmation_status = "rejected"; c.db.flush()
    assert all(fact["predicate"] != "proxmox.vlan_tag" for fact in detail(c)[0]["observed_facts"])
    latest.confirmation_status, latest.retracted_at = "confirmed", NOW; c.db.flush()
    assert all(fact["predicate"] != "proxmox.vlan_tag" for fact in detail(c)[0]["observed_facts"])
