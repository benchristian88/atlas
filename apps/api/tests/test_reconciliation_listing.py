"""Real PostgreSQL pagination, scoped counts and initial-fact presentation."""
from datetime import datetime, timedelta, timezone
import base64
import json
import os
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.authorization import ActiveContext, ScopeGrant, Principal, get_active_context, get_principal
from app.database import get_db
from sqlalchemy import func, select

from app.models import (Asset, AssetType, Customer, DataSource, DiscoveryRun, EntitySourceLink,
                        KnowledgeAssertion, ReconciliationItem, RunObservedEntity, Site, Workspace)
from app.routes.knowledge import router
from app.schemas import SimulatedDiscoveryRequest
from app.services.reconciliation import accept_item
from app.services.simulated_discovery import run_simulation
from tests.test_administration import make_principal
from tests.test_i3_discovery import db

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")
NOW = datetime(2026, 10, 13, tzinfo=timezone.utc)


@pytest.fixture
def listing(db):
    workspace = Workspace(name="Listing", slug=uuid.uuid4().hex)
    db.add(workspace); db.flush()
    customer = Customer(name="Listing", workspace_id=workspace.id)
    db.add(customer); db.flush()
    site = Site(name="Listing", customer_id=customer.id)
    db.add(site); db.flush()
    source = DataSource(customer_id=customer.id, site_id=site.id, name="Source", source_type="connector")
    db.add(source); db.flush()
    run = DiscoveryRun(customer_id=customer.id, site_id=site.id, data_source_id=source.id, status="completed", completeness_status="partial")
    db.add(run); db.flush()
    principal = make_principal("reconciliation.view", "reconciliation.decide")
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_active_context] = lambda: ActiveContext(customer.id, site.id)
    def add(category="changed", external="guest/lxc/1006", predicate="proxmox.vmid", stamp=NOW,
            status="open", source_id=None, run_id=None, fact=True, current=None, confirmation="unreviewed"):
        claim = KnowledgeAssertion(customer_id=customer.id, site_id=site.id, subject_type="asset",
            subject_external_id=external, predicate=predicate, value_json=1006,
            data_source_id=source_id or source.id, discovery_run_id=run_id or run.id,
            fact_metadata={"class": "identity", "value_type": "integer", "cardinality": "single"} if fact else None,
            first_observed_at=stamp, last_observed_at=stamp, confirmation_status=confirmation,
            truth_classification="observed", confidence=1, is_current=True, is_source_current=True, is_accepted=False)
        db.add(claim); db.flush()
        item = ReconciliationItem(customer_id=customer.id, site_id=site.id, category=category, status=status,
            entity_type="asset", candidate_external_id=external, assertion_id=claim.id, current_value_json=current,
            observed_value_json={"field": predicate, "value": 1006}, created_at=stamp, updated_at=stamp)
        db.add(item); db.flush()
        return item, claim
    with TestClient(app) as client:
        yield client, add, principal, app, (customer, site, source, run)


def pages(client, **params):
    found, cursor = [], None
    while True:
        response = client.get("/reconciliation-items/page", params={**params, **({"cursor": cursor} if cursor else {})})
        assert response.status_code == 200, response.text
        result = response.json()
        found.extend(result["items"])
        assert len(result["items"]) <= int(params.get("limit", 50))
        cursor = result["next_cursor"]
        if cursor is None:
            return found, result


def test_more_than_200_items_and_category_union_with_equal_timestamps(listing):
    client, add, *_ = listing
    categories = ["newly_discovered", "changed", "no_longer_observed", "contradiction", "possible_duplicate"]
    expected = [add(category=categories[index % 5], external=f"entity/{index}", fact=False)[0].id for index in range(235)]
    add(status="deferred", fact=False); add(status="accepted", fact=False); add(status="rejected", fact=False)
    all_rows, result = pages(client, status="open")
    assert result["total"] == 235
    assert [row["id"] for row in all_rows] == sorted(map(str, expected), reverse=True)
    union = set()
    for category in categories:
        rows, result = pages(client, status="open", category=category, limit=17)
        assert result["total"] == 47
        union.update(row["id"] for row in rows)
    assert union == {row["id"] for row in all_rows}
    rows, result = pages(client, status="resolved", limit=1)
    assert result["total"] == 2 and {row["status"] for row in rows} == {"accepted", "rejected"}
    assert len(client.get("/reconciliation-items?status=open").json()) == 200  # legacy contract


def test_decisions_and_new_arrivals_do_not_shift_next_page(listing, db):
    client, add, *_ = listing
    records = [add(external=f"entity/{index}", stamp=NOW + timedelta(seconds=index), fact=False)[0] for index in range(220)]
    first = client.get("/reconciliation-items/page?limit=50").json()
    first_ids = {row["id"] for row in first["items"]}
    for item in records:
        if str(item.id) in first_ids:
            item.status = "accepted"
    newer, _ = add(external="new-arrival", stamp=NOW + timedelta(days=1), fact=False)
    db.flush()
    remaining, result = pages(client, cursor=first["next_cursor"], limit=50)
    assert len(remaining) == 170 and result["total"] == 170
    assert first_ids.isdisjoint(row["id"] for row in remaining)
    assert str(newer.id) not in {row["id"] for row in remaining}
    refreshed, result = pages(client)
    assert result["total"] == 171 and refreshed[0]["id"] == str(newer.id)


def test_scope_counts_context_and_permission_on_every_page(listing, db):
    client, add, principal, app, (customer, site, source, run) = listing
    for index in range(211): add(external=f"entity/{index}", fact=False)
    other = Site(name="Other", customer_id=customer.id); db.add(other); db.flush()
    hidden, claim = add(external="hidden", fact=False)
    hidden.site_id = claim.site_id = other.id; db.flush()
    other_customer = Customer(name="Hidden customer", workspace_id=customer.workspace_id)
    db.add(other_customer); db.flush()
    other_site = Site(name="Hidden site", customer_id=other_customer.id)
    db.add(other_site); db.flush()
    cross_customer, cross_claim = add(external="hidden-customer", fact=False)
    cross_customer.customer_id = cross_claim.customer_id = other_customer.id
    cross_customer.site_id = cross_claim.site_id = other_site.id
    db.flush()
    grant = ScopeGrant(uuid.uuid4(), uuid.uuid4(), "Viewer", "site", customer.id, site.id, frozenset(["reconciliation.view"]))
    app.dependency_overrides[get_principal] = lambda: Principal(principal.user, (grant,))
    app.dependency_overrides[get_active_context] = lambda: ActiveContext(None, None)
    rows, result = pages(client)
    assert result["total"] == 211 and str(hidden.id) not in {row["id"] for row in rows}
    assert str(cross_customer.id) not in {row["id"] for row in rows}
    app.dependency_overrides[get_active_context] = lambda: ActiveContext(customer.id, other.id)
    assert client.get("/reconciliation-items/page").json()["total"] == 0
    app.dependency_overrides[get_principal] = lambda: make_principal()
    assert client.get("/reconciliation-items/page").status_code == 403


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"cursor": "bad"}, {"cursor": "a" * 513}])
def test_invalid_paging_inputs_are_bounded(listing, params):
    assert listing[0].get("/reconciliation-items/page", params=params).status_code == 422


def test_structurally_malformed_cursor_returns_validation_error(listing):
    cursor = base64.urlsafe_b64encode(json.dumps({"snapshot": [NOW.isoformat(), 1],
                                               "before": [NOW.isoformat(), str(uuid.uuid4())]}).encode()).decode()
    assert listing[0].get("/reconciliation-items/page", params={"cursor": cursor}).status_code == 422


def test_initial_facts_keep_parent_context_across_page_and_category_boundaries(listing):
    client, add, *_ = listing
    parent, _ = add(category="newly_discovered", predicate="name", fact=False)
    fact, _ = add()
    rows, result = pages(client, category="changed", limit=1)
    assert rows[0]["initial_entity_item_id"] == str(parent.id)
    assert result["related_new_entities"][0]["id"] == str(parent.id)
    assert rows[0]["assertion_predicate"] == "proxmox.vmid"
    assert rows[0]["status"] == "open"  # presentation only


@pytest.mark.parametrize("case", ["later", "coalesced_run", "prior_claim", "contradiction", "conflicted", "entity", "source", "run", "current"])
def test_later_changed_facts_conflicts_and_other_context_never_group(listing, db, case):
    client, add, _, _, (customer, site, source, run) = listing
    parent, anchor = add(category="newly_discovered", predicate="name", fact=False)
    kwargs = {}
    if case == "later": kwargs["stamp"] = NOW + timedelta(hours=1)
    if case == "coalesced_run":
        other = DiscoveryRun(customer_id=customer.id, site_id=site.id, data_source_id=source.id,
                             status="completed", completeness_status="partial")
        db.add(other); db.flush()
        anchor.discovery_run_id = other.id
        kwargs.update(run_id=other.id, stamp=NOW + timedelta(hours=1))
    if case == "prior_claim":
        _, prior = add(stamp=NOW - timedelta(days=1), status="accepted")
        prior.is_accepted = True
    if case == "contradiction": kwargs["category"] = "contradiction"
    if case == "conflicted": kwargs["confirmation"] = "conflicted"
    if case == "entity": kwargs["external"] = "another/entity"
    if case == "source":
        other = DataSource(customer_id=customer.id, site_id=site.id, name="Other", source_type="connector")
        db.add(other); db.flush(); kwargs["source_id"] = other.id
    if case == "run":
        other = DiscoveryRun(customer_id=customer.id, site_id=site.id, data_source_id=source.id, status="completed", completeness_status="partial")
        db.add(other); db.flush(); kwargs["run_id"] = other.id
    if case == "current": kwargs["current"] = {"field": "proxmox.vmid", "value": 99}
    fact, _ = add(**kwargs)
    rows, result = pages(client)
    assert next(row for row in rows if row["id"] == str(fact.id))["initial_entity_item_id"] is None


@pytest.mark.parametrize("category", ["newly_discovered", "possible_duplicate"])
def test_discovered_asset_heading_uses_observed_name_without_changing_identity(listing, db, category):
    client, add, *_ = listing
    item, claim = add(category=category, external="guest/lxc/1008", predicate="name", fact=False)
    claim.value_json = "joomla-lab"
    item.observed_value_json = {"name": "joomla-lab", "asset_type": "lxc_container", "facts": {}}
    db.flush()
    for path in ("/reconciliation-items", "/reconciliation-items/page"):
        response = client.get(path)
        assert response.status_code == 200
        rows = response.json() if path == "/reconciliation-items" else response.json()["items"]
        assert rows[0]["entity_name"] == "joomla-lab"
        assert rows[0]["candidate_external_id"] == "guest/lxc/1008"
        assert rows[0]["assertion_id"] == str(claim.id)
    assert claim.subject_external_id == "guest/lxc/1008"


@pytest.mark.parametrize("name", [None, "", "   ", 1008, {"name": "unsafe shape"}, "x" * 256])
def test_missing_or_invalid_observed_name_falls_back_to_external_identity(listing, db, name):
    client, add, *_ = listing
    item, _ = add(category="newly_discovered", fact=False)
    item.observed_value_json = {"name": name}
    db.flush()
    row = client.get("/reconciliation-items/page").json()["items"][0]
    assert row["entity_name"] == item.candidate_external_id


@pytest.mark.parametrize("external,key", [("guest/lxc/1008", "lxc_container"),
                                         ("guest/qemu/203", "virtual_machine"),
                                         ("opaque-source-object", "virtual_machine")])
def test_source_rename_changes_reviewed_presentation_and_preserves_asset_identity(listing, db, external, key):
    client, _, principal, _, (customer, site, source, _) = listing
    principal.user.email = uuid.uuid4().hex + "@example.test"
    db.add(principal.user); db.flush()
    managed_type = db.scalar(select(AssetType).where(AssetType.key == key))
    assert managed_type is not None and managed_type.active
    if key == "lxc_container":
        assert managed_type.name == "LXC Container"

    def discover(name):
        payload = SimulatedDiscoveryRequest(customer_id=customer.id, site_id=site.id,
            data_source_id=source.id, observations=[{"external_id": external, "entity_kind": "asset",
                                                    "asset_type": key, "name": name}])
        run, _, _, items = run_simulation(db, payload=payload, user_id=principal.user.id)
        db.flush()
        return run, items

    first, items = discover("joomla-lab")
    new = next(item for item in items if item.category == "newly_discovered")
    assert client.get("/reconciliation-items/page").json()["items"][0]["entity_name"] == "joomla-lab"
    accepted = accept_item(db, new, principal.user)
    db.flush()
    link = db.scalar(select(EntitySourceLink).where(EntitySourceLink.data_source_id == source.id))
    link_id, asset_id = link.id, accepted.id

    repeated, changes = discover("joomla-renamed")
    assert not any(item.category == "newly_discovered" for item in changes)
    rename = next(item for item in changes if item.observed_value_json == {"field": "name", "value": "joomla-renamed"})
    assert rename.entity_id == asset_id
    # The accepted Asset name changes only after an operator accepts the rename.
    assert db.get(Asset, asset_id).name == "joomla-lab"
    accept_item(db, rename, principal.user)
    db.flush()
    row = next(row for row in client.get("/reconciliation-items?status=resolved").json() if row["id"] == str(rename.id))
    assert row["entity_name"] == "joomla-renamed"
    assert row["candidate_external_id"] == external
    assert db.scalar(select(func.count()).select_from(Asset).where(Asset.customer_id == customer.id)) == 1
    links = list(db.scalars(select(EntitySourceLink).where(EntitySourceLink.data_source_id == source.id)))
    assert [(link.id, link.external_id, link.entity_id) for link in links] == [(link_id, external, asset_id)]
    observations = list(db.scalars(select(RunObservedEntity).where(RunObservedEntity.discovery_run_id.in_([first.id, repeated.id]))))
    assert len(observations) == 2 and {row.external_id for row in observations} == {external}
