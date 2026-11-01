"""AK-01/AK-02: real PostgreSQL read model, scope and acceptance contracts."""
from dataclasses import replace
import json
import os
import uuid

import pytest
from sqlalchemy import event, select

from app.authorization import get_principal
from app.models import Asset, AssetType, Customer, DataSource, KnowledgeAssertion, ReconciliationItem, RelationshipType, Site
from app.routes import changes
from app.schemas import AssetKnowledgeSummaryResponse
from app.services.entity_resolution import ensure_asset_link
from app.services.knowledge_assertions import accept_assertion, record_assertion
from app.services.knowledge_summary import asset_knowledge_summary
from tests.test_administration import make_principal
from tests.test_i3_discovery import db
from tests.test_reconciliation_listing import listing, NOW
from tests.test_cross_source_reconciliation import two_sources, configured, group_named, rows, link

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")


@pytest.fixture
def summary(listing, db):
    client, _, _, app, (customer, site, source, _) = listing
    app.include_router(changes.router)
    principal = make_principal("assets.view", "reconciliation.view", "reconciliation.decide")
    principal.user.email = uuid.uuid4().hex + "@example.test"
    db.add(principal.user)
    app.dependency_overrides[get_principal] = lambda: principal
    for key, label in (("lxc_container", "LXC Container"), ("virtual_machine", "Virtual Machine")):
        if db.scalar(select(AssetType).where(AssetType.key == key)) is None:
            db.add(AssetType(key=key, name=label, active=True, icon="server"))
    relationship_type = db.scalar(select(RelationshipType).where(RelationshipType.key == "runs_on"))
    if relationship_type is None:
        relationship_type = RelationshipType(key="runs_on", name="Runs on", directional=True, active=True)
        db.add(relationship_type)
    source_b = DataSource(customer_id=customer.id, site_id=site.id, name="Proxmox source B", source_type="connector")
    asset = Asset(customer_id=customer.id, site_id=site.id, workspace_id=customer.workspace_id,
                  name="esphome", asset_type="lxc_container", source="discovery")
    target = Asset(customer_id=customer.id, site_id=site.id, workspace_id=customer.workspace_id,
                   name="Proxmox host with a long descriptive operational name", asset_type="virtual_machine")
    db.add_all([source_b, asset, target]); db.flush()

    def claim(predicate="asset_type", value="lxc_container", source=source, accepted=False, target_id=None, external=None, **kwargs):
        row, _ = record_assertion(db, customer_id=customer.id, site_id=site.id, subject_type="asset", subject_id=asset.id,
            subject_external_id="esphome/" + str(source.id), predicate=predicate, value=value, data_source_id=source.id,
            observed_at=NOW, object_type="asset" if predicate == "runs_on" else None, object_id=target_id,
            object_external_id=external, **kwargs)
        if accepted:
            accept_assertion(db, row, user_id=principal.user.id)
        db.flush()
        return row

    def get():
        response = client.get(f"/assets/{asset.id}/knowledge-summary")
        assert response.status_code == 200, response.text
        result = response.json()
        AssetKnowledgeSummaryResponse.model_validate(result)
        return {row["predicate"]: row for row in result["groups"]}
    return client, asset, target, source, source_b, principal, app, claim, get


@pytest.mark.parametrize("values,accepted,conflict,unresolved", [
    (("lxc_container", "lxc_container"), False, False, False),
    (("lxc_container", "virtual_machine"), False, False, True),
    (("lxc_container", "lxc_container"), True, False, False),
    (("lxc_container", "virtual_machine"), True, True, False),
])
def test_asset_type_agreement_is_not_ambiguity_and_never_grants_acceptance(summary, values, accepted, conflict, unresolved):
    _, _, _, source_a, source_b, _, _, claim, get = summary
    first = claim(value=values[0], source=source_a, accepted=accepted)
    second = claim(value=values[1], source=source_b)
    group = get()["asset_type"]
    assert group["conflict"] is conflict and group["unresolved"] is unresolved
    assert group["source_count"] == 2 and len(group["latest_observations"]) == 2
    assert bool(group["accepted"]) is accepted and not second.is_accepted
    assert bool(first.is_accepted) is accepted
    assert group["canonical_consistency"] == ("matches" if accepted else "missing_acceptance")
    if values[0] == values[1]:
        assert len(group["observation_groups"]) == 1 and group["observation_groups"][0]["source_count"] == 2
    if not accepted and not unresolved:
        assert group["state"] == "observed" and group["awaiting_acceptance"]


def test_canonical_type_without_assertions_is_reported_without_fabricated_history(summary):
    _, asset, _, _, _, _, _, _, get = summary
    group = get()["asset_type"]
    assert group["canonical_value"] == asset.asset_type
    assert group["accepted"] is None and group["assertion_count"] == 0
    assert group["canonical_consistency"] == "missing_acceptance" and group["state"] == "unknown"


def test_accepted_and_operational_discrepancy_is_explicit(summary):
    *_, claim, get = summary
    claim(value="virtual_machine", accepted=True)
    group = get()["asset_type"]
    assert group["canonical_consistency"] == "mismatch"
    assert group["accepted"]["value"] == "virtual_machine" and group["canonical_value"] == "lxc_container"


@pytest.mark.parametrize("form", ["object", "legacy_json", "source_link"])
def test_relationship_forms_resolve_managed_label_direction_and_authorized_target(summary, db, form):
    _, asset, target, source, _, _, _, claim, get = summary
    if form == "source_link":
        ensure_asset_link(db, data_source_id=source.id, asset=target, external_id="source/host", observed_at=NOW)
    row = claim("runs_on", value={"target_asset_id": str(target.id), "source_asset_id": str(asset.id)} if form == "legacy_json" else None,
                target_id=target.id if form == "object" else None, external="source/host" if form == "source_link" else None, accepted=True)
    group = get()["runs_on"]
    relation = group["accepted"]["relationship"]
    assert group["cardinality"] == "multi" and group["label"] == "Runs on"
    assert relation["target_name"] == target.name and relation["target_id"] == str(target.id)
    assert relation["href"] == f"/assets/{target.id}" and relation["direction"] == "outgoing"
    db.refresh(row)
    assert row.value_json == ({"target_asset_id": str(target.id), "source_asset_id": str(asset.id)} if form == "legacy_json" else None)


def test_two_sources_one_logical_relationship_retains_individual_provenance(summary):
    _, _, target, source_a, source_b, _, _, claim, get = summary
    first = claim("runs_on", value=None, target_id=target.id, source=source_a, external="a/host", accepted=True)
    second = claim("runs_on", value={"target_id": str(target.id)}, target_id=target.id, source=source_b, external="b/host", accepted=True)
    group = get()["runs_on"]
    assert len(group["accepted_values"]) == 2 and len(group["accepted_groups"]) == 1
    logical = group["accepted_groups"][0]
    assert logical["source_count"] == group["source_count"] == 2
    assert {row["assertion_id"] for row in logical["assertions"]} == {str(first.id), str(second.id)}
    assert all(row["accepted_at"] and row["last_observed_at"] and row["source_name"] for row in logical["assertions"])


def test_same_named_targets_are_distinct_and_unresolved_references_never_merge(summary, db):
    _, asset, target, source_a, source_b, _, _, claim, get = summary
    other = Asset(workspace_id=asset.workspace_id, customer_id=asset.customer_id, site_id=asset.site_id,
                  name=target.name, asset_type="virtual_machine")
    db.add(other); db.flush()
    claim("runs_on", None, source=source_a, target_id=target.id, external="a/host", accepted=True)
    claim("runs_on", None, source=source_b, target_id=other.id, external="b/host", accepted=True)
    claim("runs_on", None, source=source_a, external="same-unresolved-reference")
    claim("runs_on", None, source=source_b, external="same-unresolved-reference")
    group = get()["runs_on"]
    assert len(group["accepted_groups"]) == 2 and len(group["observation_groups"]) == 4
    unresolved = [row for row in group["observation_groups"] if not row["relationship"]["target_id"]]
    assert len(unresolved) == 2 and all(row["relationship"]["href"] is None for row in unresolved)


@pytest.mark.parametrize("boundary", ["customer", "site", "permission", "missing", "malformed"])
def test_relationship_projection_never_discloses_hidden_target_metadata(summary, db, boundary):
    client, asset, target, source, _, principal, app, claim, get = summary
    hidden_id = target.id
    if boundary in {"customer", "site"}:
        customer = db.get(Customer, asset.customer_id)
        if boundary == "customer":
            customer = Customer(workspace_id=asset.workspace_id, name="Hidden customer"); db.add(customer); db.flush()
        site = Site(customer_id=customer.id, name="Hidden site"); db.add(site); db.flush()
        target.customer_id, target.site_id = customer.id, site.id
    elif boundary == "permission":
        claim("runs_on", None, target_id=target.id, accepted=True)
        limited = replace(principal, grants=(replace(principal.grants[0], scope_type="site", customer_id=asset.customer_id, site_id=uuid.uuid4()),))
        # The route correctly refuses the starting Asset as well.
        app.dependency_overrides[get_principal] = lambda: limited
        assert client.get(f"/assets/{asset.id}/knowledge-summary").status_code == 404
        result = asset_knowledge_summary(db, asset, limited)
        assert target.name not in json.dumps(result)
        return
    elif boundary == "missing": hidden_id = uuid.uuid4()
    claim("runs_on", {"target_id": "invalid" if boundary == "malformed" else str(hidden_id), "target_name": "Hidden raw name"},
          target_id=None if boundary == "malformed" else hidden_id, accepted=True)
    group = get()["runs_on"]
    encoded = json.dumps(group)
    assert str(hidden_id) not in encoded and "Hidden raw name" not in encoded and target.name not in encoded
    assert group["accepted"]["relationship"]["href"] is None
    history = client.get(f"/assets/{asset.id}/fact-history")
    assert history.status_code == 200 and target.name not in history.text and "Hidden raw name" not in history.text


def test_historical_rejected_retracted_relationships_remain_raw_and_do_not_contribute(summary, db):
    client, asset, target, source, _, _, _, claim, get = summary
    historical = claim("runs_on", {"target_asset_id": str(target.id), "legacy": True}, external="history")
    rejected = claim("runs_on", None, target_id=target.id, external="rejected")
    retracted = claim("runs_on", None, target_id=target.id, external="retracted", accepted=True)
    historical.is_source_current = False; historical.confirmation_status = "superseded"
    rejected.confirmation_status = "rejected"
    retracted.retracted_at = NOW
    db.flush()
    group = get()["runs_on"]
    assert group["accepted_values"] == group["latest_observations"] == []
    assert group["historical_count"] == group["assertion_count"] == 3 and group["source_count"] == 0
    response = client.get("/assertions", params={"subject_type": "asset", "subject_id": str(asset.id), "current_only": "false"})
    assert response.status_code == 200
    original = next(row for row in response.json() if row["id"] == str(historical.id))
    assert original["value_json"] == historical.value_json


def test_asset_link_exposes_unaccepted_core_fields_and_acceptance_updates_summary(two_sources, db):
    client, asset, _, _, _, _, _, _, app, *_ = two_sources
    app.include_router(changes.router)
    assert link(client, group_named(client, "grafana")["parent"], asset.id, "asset").status_code == 200
    before = client.get(f"/assets/{asset.id}/knowledge-summary").json()
    assert next(row for row in before["groups"] if row["predicate"] == "asset_type")["canonical_consistency"] == "missing_acceptance"
    proposal = next(row for row in rows(group_named(client, "grafana")) if row["assertion_predicate"] == "asset_type")
    assert client.post(f'/reconciliation-items/{proposal["id"]}/accept', json={"expected_version": proposal["version"]}).status_code == 200
    after = client.get(f"/assets/{asset.id}/knowledge-summary").json()
    group = next(row for row in after["groups"] if row["predicate"] == "asset_type")
    assert group["canonical_consistency"] == "matches" and group["state"] == "accepted"


def test_relationship_summary_batches_metadata_instead_of_per_assertion_queries(summary, db):
    _, _, target, source, _, _, _, claim, get = summary
    for index in range(30):
        claim("runs_on", None, target_id=target.id, external=f"source/host/{index}", accepted=True)
    queries = []
    def capture(_connection, _cursor, statement, *_):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)
    event.listen(db.bind, "before_cursor_execute", capture)
    try:
        group = get()["runs_on"]
    finally:
        event.remove(db.bind, "before_cursor_execute", capture)
    assert len(group["accepted_values"]) == 30 and len(group["accepted_groups"]) == 1
    assert group["accepted_groups"][0]["source_count"] == 1
    assert len(queries) <= 8
