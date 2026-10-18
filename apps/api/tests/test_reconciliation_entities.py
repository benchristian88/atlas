"""Entity review, decisions and isolation against disposable PostgreSQL."""
from dataclasses import replace
from datetime import timedelta
import os
import uuid

import pytest
from sqlalchemy import event, func, select

from app.authorization import ActiveContext, Principal, ScopeGrant, get_active_context, get_principal
from app.models import (Asset, AssetInterface, AuditEvent, Customer, EntitySourceLink, KnowledgeAssertion,
                        KnowledgeChange, ReconciliationItem, Site)
from app.services.reconciliation_entities import fact_label
from tests.test_administration import make_principal
from tests.test_reconciliation_listing import listing, NOW
from tests.test_i3_discovery import db

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")


@pytest.fixture
def review(listing, db):
    client, add, _, app, context = listing
    principal = make_principal("reconciliation.view", "reconciliation.decide", "relationships.create", "networks.create", "networks.edit")
    principal.user.email = uuid.uuid4().hex + "@example.test"
    db.add(principal.user); db.flush()
    app.dependency_overrides[get_principal] = lambda: principal

    def entity(name, external=None, kind="asset", **kwargs):
        external = external or uuid.uuid4().hex
        item, claim = add(category="newly_discovered", predicate="name" if kind == "asset" else "configuration", external=external, fact=False, **kwargs)
        item.entity_type = claim.subject_type = kind
        proposal = {"name": name, "asset_type": "virtual_machine", "facts": {}} if kind == "asset" else {"name": name, "asset_external_id": kwargs.get("owner")}
        item.observed_value_json = proposal
        claim.value_json = name if kind == "asset" else proposal
        db.flush()
        return item, claim

    def fact(owner, key="fixture.serial", kind="asset", **kwargs):
        item, claim = add(external=owner.candidate_external_id, predicate=key, **kwargs)
        item.entity_type = claim.subject_type = kind
        item.entity_id = claim.subject_id = owner.entity_id
        db.flush()
        return item, claim

    def interface(owner, name="net0"):
        item, claim = add(category="newly_discovered", predicate="configuration", external=uuid.uuid4().hex, fact=False)
        item.entity_type = claim.subject_type = "asset_interface"
        claim.value_json = {"name": name, "asset_external_id": owner.candidate_external_id, "network_external_id": None,
                            "mac_address": "02:00:00:00:00:01", "ip_address": "192.0.2.8", "is_primary": False}
        item.observed_value_json = claim.value_json
        db.flush()
        return item, claim

    def relationship(owner, target):
        item, claim = add(predicate="runs_on", external=owner.candidate_external_id, fact=False)
        item.entity_type = "asset_relationship"
        claim.object_type, claim.object_external_id = "asset", target.candidate_external_id
        claim.value_json = {"relationship_type": "runs_on"}
        item.observed_value_json = {"relationship_type": "runs_on", "source_external_id": owner.candidate_external_id,
                                    "target_external_id": target.candidate_external_id}
        db.flush()
        return item, claim
    return client, entity, fact, interface, relationship, principal, app, context


def page(client, **params):
    response = client.get("/reconciliation-entities", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def group_named(client, name, **params):
    return next(group for group in page(client, **params)["entities"] if group["name"] == name)


def accept_all(client, group):
    response = client.post(f'/reconciliation-entities/{group["id"]}/accept', json={"items": group["decision_items"]})
    assert response.status_code == 200, response.text
    return response.json()


def test_new_asset_facts_relationship_and_network_group_generically(review):
    client, entity, fact, interface, relationship, *_ = review
    parent, _ = entity("Workload", "an opaque identity with no hierarchy")
    target, _ = entity("Host", "another completely opaque identity")
    fact(parent)
    network, _ = interface(parent)
    bridge, _ = fact(network, "fixture.bridge_name", "asset_interface")
    relationship(parent, target)
    result = page(client)
    assert result["record_total"] == 6 and result["entity_total"] == 2
    assert [group["name"] for group in result["entities"]] == ["Host", "Workload"]
    group = group_named(client, "Workload")
    assert group["default_expanded"]
    assert {section["key"]: section["total"] for section in group["sections"]} == {"facts": 1, "relationships": 1, "network": 2}
    relation = next(section for section in group["sections"] if section["key"] == "relationships")["items"][0]
    assert relation["label"] == "Runs on → Host"
    assert {blocker["name"] for blocker in relation["blockers"]} == {"Workload", "Host"}
    assert all(blocker["entity_id"] for blocker in relation["blockers"])
    proposed = next(section for section in group["sections"] if section["key"] == "network")["items"]
    assert next(row for row in proposed if row["id"] == str(bridge.id))["label"] == "net0 · Bridge Name"
    assert all(not row["can_accept"] for section in group["sections"] for row in section["items"])


def test_accept_asset_only_keeps_card_and_independent_children(review, db):
    client, entity, fact, interface, relationship, *_ = review
    parent, _ = entity("Workload")
    child, claim = fact(parent)
    network, _ = interface(parent)
    target, _ = entity("Host")
    relation, _ = relationship(parent, target)
    before = group_named(client, "Workload")
    blocked = client.post(f"/reconciliation-items/{child.id}/accept", json={"expected_version": before["sections"][0]["items"][0]["version"]})
    assert blocked.status_code == 409
    response = client.post(f"/reconciliation-items/{parent.id}/accept", json={"expected_version": before["parent"]["version"]})
    assert response.status_code == 200, response.text
    assert parent.status == "accepted" and child.status == network.status == relation.status == "open"
    assert not claim.is_accepted
    after = group_named(client, "Workload")
    assert after["id"] == before["id"] and after["parent"]["status"] == "accepted"
    assert after["sections"][0]["items"][0]["can_accept"]
    assert client.post(f"/reconciliation-items/{child.id}/accept", json={"expected_version": after["sections"][0]["items"][0]["version"]}).status_code == 200
    assert claim.is_accepted
    assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == "reconciliation.accepted", AuditEvent.customer_id == parent.customer_id)) == 2


def test_accept_all_accepts_eligible_children_and_preserves_external_prerequisite(review, db):
    client, entity, fact, interface, relationship, *_ = review
    parent, _ = entity("Workload")
    fact(parent)
    network, _ = interface(parent)
    fact(network, "fixture.vlan_tag", "asset_interface")
    target, _ = entity("Host")
    relation, _ = relationship(parent, target)
    result = accept_all(client, group_named(client, "Workload"))
    assert len(result["accepted"]) == 4 and len(result["blocked"]) == 1 and not result["failed"]
    assert result["blocked"][0]["id"] == str(relation.id) and "Host" in result["blocked"][0]["reason"]
    assert target.status == relation.status == "open"
    assert db.scalar(select(func.count()).select_from(Asset).where(Asset.customer_id == parent.customer_id)) == 1
    assert db.scalar(select(func.count()).select_from(AssetInterface).join(Asset).where(Asset.customer_id == parent.customer_id)) == 1
    assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == "reconciliation.accepted", AuditEvent.customer_id == parent.customer_id)) == 4
    assert db.scalar(select(func.count()).select_from(KnowledgeChange).where(
        KnowledgeChange.reconciliation_item_id.in_([uuid.UUID(row["id"]) for row in result["accepted"]]))) == 4
    accept_all(client, group_named(client, "Host"))
    final = accept_all(client, group_named(client, "Workload"))
    assert len(final["accepted"]) == 1 and not final["blocked"]
    assert page(client)["entity_total"] == page(client)["record_total"] == 0


def test_existing_asset_changes_search_filters_and_resolved_deferred(review, db):
    client, entity, fact, _, _, principal, app, context = review
    parent, _ = entity("Original name")
    accept_all(client, group_named(client, "Original name"))
    for index in range(3):
        fact(parent, f"fixture.fact_{index}")
    deferred, _ = fact(parent, "fixture.later", status="deferred")
    unrelated, _ = entity("Other")
    result = page(client, search="original", section="facts")
    assert result["entity_total"] == 1 and result["record_total"] == 3
    group = result["entities"][0]
    assert group["parent"]["status"] == "accepted" and not group["default_expanded"]
    assert group["sections"][0]["total"] == 3
    assert page(client, search="fixture.fact")["record_total"] == 0
    assert page(client, status="deferred")["record_total"] == 1
    assert page(client, status="resolved")["record_total"] == 1
    assert page(client, section="relationships")["record_total"] == 0


def test_manually_curated_asset_needs_no_parent_and_cross_source_facts_share_its_card(review, db):
    from app.models import DataSource
    client, entity, fact, _, _, _, _, (customer, site, source, run) = review
    asset = Asset(workspace_id=customer.workspace_id, customer_id=customer.id, site_id=site.id,
                  name="Curated Asset", asset_type="virtual_machine", source="manual", icon_url="https://example.test/icon.png")
    db.add(asset); db.flush()
    anchor, _ = entity("Source identity")
    first, first_claim = fact(anchor)
    first.entity_id = first_claim.subject_id = asset.id
    second, second_claim = fact(anchor, "fixture.other")
    other_source = DataSource(customer_id=customer.id, site_id=site.id, name="Other source", source_type="connector")
    db.add(other_source); db.flush()
    second_claim.data_source_id = other_source.id
    second.entity_id = second_claim.subject_id = asset.id
    db.flush()
    group = group_named(client, "Curated Asset")
    assert group["parent"] is None and not group["default_expanded"]
    assert group["cached_icon_url"].startswith(f"/api/assets/{asset.id}/icon?v=")
    assert asset.icon_url not in str(group)
    assert group["matching_record_count"] == group["sections"][0]["total"] == 2
    assert all(row["can_accept"] for row in group["sections"][0]["items"])
    # The same opaque external ID without a durable link does not merge an
    # unrelated source's candidate with this manually curated Asset.
    assert page(client)["entity_total"] == 2


def test_bulk_refuses_another_visible_entity_even_when_it_is_a_prerequisite(review):
    client, entity, _, _, relationship, *_ = review
    child, _ = entity("Workload")
    target, _ = entity("Host")
    relationship(child, target)
    group = group_named(client, "Workload")
    host = group_named(client, "Host")
    response = client.post(f"/reconciliation-entities/{group['id']}/accept", json={"items": group["decision_items"] + host["decision_items"]})
    assert response.status_code == 404
    assert child.status == target.status == "open"


def test_explicit_link_unblocks_children_without_accepting_them(review, db):
    client, entity, fact, _, _, principal, app, (customer, site, source, run) = review
    principal = replace(principal, grants=(replace(principal.grants[0], permissions=principal.grants[0].permissions | {"assets.edit"}),))
    app.dependency_overrides[get_principal] = lambda: principal
    asset = Asset(workspace_id=customer.workspace_id, customer_id=customer.id, site_id=site.id,
                  name="Curated", asset_type="virtual_machine", source="manual")
    db.add(asset); db.flush()
    parent, _ = entity("Observed")
    child, claim = fact(parent)
    response = client.post(f"/reconciliation-items/{parent.id}/link-asset", json={"asset_id": str(asset.id)})
    assert response.status_code == 200, response.text
    group = group_named(client, "Curated")
    assert group["parent"]["status"] == "accepted" and group["sections"][0]["items"][0]["can_accept"]
    assert child.status == "open" and not claim.is_accepted
    assert client.post(f"/reconciliation-items/{child.id}/accept").status_code == 200


def test_cycles_are_deterministic_and_prerequisite_focus_is_scoped(review):
    client, entity, _, _, relationship, *_ = review
    first, _ = entity("First")
    second, _ = entity("Second")
    relationship(first, second); relationship(second, first)
    result = page(client)
    assert result == page(client)
    assert result["entity_total"] == 2
    focused = client.get(f"/reconciliation-entities/{first.id}")
    assert focused.status_code == 200 and focused.json()["name"] == "First"


def test_reobserved_candidate_uses_current_parent_and_retains_historical_anchor(review, db):
    client, entity, fact, *_ = review
    old, old_claim = entity("Earlier proposal", "opaque identity", status="rejected")
    old_claim.is_source_current = False
    current, _ = entity("Current proposal", "opaque identity", stamp=NOW + timedelta(days=1))
    fact(current)
    db.flush()
    group = group_named(client, "Current proposal")
    assert group["parent"]["id"] == str(current.id) and group["parent"]["status"] == "open"
    assert group["id"] == str(old.id) and group["matching_record_count"] == 2


def test_more_than_200_entity_pages_no_truncation_and_snapshot_survives_decisions(review, db):
    client, entity, *_ = review
    for index in range(211):
        entity(f"Entity {index}", stamp=NOW + timedelta(seconds=index))
    first = page(client, limit=37)
    assert first["entity_total"] == first["record_total"] == 211
    seen = {group["id"] for group in first["entities"]}
    for identifier in seen:
        db.get(ReconciliationItem, uuid.UUID(identifier)).status = "rejected"
    entity("New arrival", stamp=NOW + timedelta(days=1))
    db.flush()
    cursor = first["next_cursor"]
    while cursor:
        result = page(client, cursor=cursor, limit=37)
        ids = {group["id"] for group in result["entities"]}
        assert not ids & seen
        assert all(group["name"] != "New arrival" for group in result["entities"])
        seen |= ids
        cursor = result["next_cursor"]
    assert len(seen) == 211
    assert page(client)["record_total"] == 175


def test_large_section_is_bounded_and_continues(review):
    client, entity, fact, *_ = review
    parent, _ = entity("Many facts")
    for index in range(43): fact(parent, f"fixture.number_{index}")
    group = group_named(client, "Many facts")
    section = group["sections"][0]
    assert section["total"] == 43 and len(section["items"]) == 20
    next_page = client.get(f"/reconciliation-entities/{group['id']}/section", params={"section": "facts", "offset": section["next_offset"]}).json()
    assert len(next_page["items"]) == 20
    assert not {row["id"] for row in section["items"]} & {row["id"] for row in next_page["items"]}


def test_previous_cursor_restores_the_previous_page_after_refresh(review):
    client, entity, *_ = review
    for index in range(13): entity(f"Entity {index}")
    first = page(client, limit=4)
    second = page(client, limit=4, cursor=first["next_cursor"])
    third = page(client, limit=4, cursor=second["next_cursor"])
    assert third["previous_cursor"]
    restored = page(client, limit=4, cursor=third["previous_cursor"])
    assert [row["id"] for row in restored["entities"]] == [row["id"] for row in second["entities"]]
    entity("New arrival", stamp=NOW + timedelta(days=1))
    restored_first = page(client, limit=4, cursor=second["previous_cursor"])
    assert [row["id"] for row in restored_first["entities"]] == [row["id"] for row in first["entities"]]
    assert restored_first["entity_total"] == 13


def test_cursor_is_bound_to_filters_and_malformed_positions_are_rejected(review):
    import base64
    import json
    client, entity, *_ = review
    for index in range(3): entity(f"Entity {index}")
    cursor = page(client, limit=1)["next_cursor"]
    assert client.get("/reconciliation-entities", params={"cursor": cursor, "status": "deferred"}).status_code == 422
    value = json.loads(base64.urlsafe_b64decode(cursor))
    value["snapshot"][1] = 42
    malformed = base64.urlsafe_b64encode(json.dumps(value).encode()).decode()
    assert client.get("/reconciliation-entities", params={"cursor": malformed}).status_code == 422


def test_stale_and_already_resolved_bulk_outcomes_and_partial_failure_are_explicit(review, db):
    client, entity, fact, *_ = review
    parent, _ = entity("Workload")
    stale, claim = fact(parent)
    group = group_named(client, "Workload")
    claim.value_json = "newer proposal"
    db.flush()
    result = accept_all(client, group)
    assert len(result["accepted"]) == 1 and len(result["failed"]) == 1
    assert "changed" in result["failed"][0]["reason"] and stale.status == "open"
    replay = accept_all(client, group)
    assert len(replay["already_resolved"]) == 1 and len(replay["failed"]) == 1
    version = group_named(client, "Workload")["sections"][0]["items"][0]["version"]
    claim.is_source_current = False
    db.flush()
    assert client.post(f"/reconciliation-items/{stale.id}/accept", json={"expected_version": version}).status_code == 409


def test_per_item_validation_failure_rolls_back_just_that_item_and_audits_successes(review, db):
    client, entity, fact, *_ = review
    parent, _ = entity("Workload")
    invalid, claim = fact(parent, "unsupported_field")
    claim.fact_metadata = None
    valid, _ = fact(parent)
    db.flush()
    result = accept_all(client, group_named(client, "Workload"))
    assert len(result["accepted"]) == 2 and len(result["failed"]) == 1
    assert invalid.status == "open" and valid.status == "accepted"
    assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.customer_id == parent.customer_id)) == 2


@pytest.mark.parametrize("boundary", ["customer", "site"])
def test_cross_context_names_counts_prerequisites_and_bulk_membership_never_leak(review, db, boundary):
    client, entity, fact, _, relationship, principal, app, (customer, site, source, run) = review
    visible, _ = entity("Visible", "shared opaque identity")
    visible_fact, _ = fact(visible)
    hidden, hidden_claim = entity("SECRET PREREQUISITE", "hidden opaque identity")
    hidden_child, hidden_child_claim = fact(hidden)
    hidden_customer = customer
    if boundary == "customer":
        hidden_customer = Customer(name="Other customer", workspace_id=customer.workspace_id)
        db.add(hidden_customer); db.flush()
    hidden_site = Site(name="Other site", customer_id=hidden_customer.id)
    db.add(hidden_site); db.flush()
    for item, claim in [(hidden, hidden_claim), (hidden_child, hidden_child_claim)]:
        item.customer_id = claim.customer_id = hidden_customer.id
        item.site_id = claim.site_id = hidden_site.id
    relation, _ = relationship(visible, hidden)
    db.flush()
    grant = ScopeGrant(uuid.uuid4(), uuid.uuid4(), "Reviewer", "site", customer.id, site.id,
                       frozenset(["reconciliation.view", "reconciliation.decide", "relationships.create"]))
    app.dependency_overrides[get_principal] = lambda: Principal(principal.user, (grant,))
    app.dependency_overrides[get_active_context] = lambda: ActiveContext(None, None)
    result = page(client)
    assert result["entity_total"] == 1 and result["record_total"] == 3
    assert "SECRET" not in str(result)
    assert client.get(f"/reconciliation-entities/{hidden.id}").status_code == 404
    group = result["entities"][0]
    attack = [*group["decision_items"], {"id": str(hidden_child.id), "version": "0" * 64}]
    response = client.post(f"/reconciliation-entities/{group['id']}/accept", json={"items": attack})
    assert response.status_code == 404 and "SECRET" not in response.text
    assert visible.status == hidden.status == hidden_child.status == "open"
    # Even a globally authorized operator's explicit active context is enforced.
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_active_context] = lambda: ActiveContext(customer.id, site.id)
    assert client.post(f"/reconciliation-entities/{hidden.id}/accept", json={"items": [{"id": str(hidden.id), "version": "0" * 64}]}).status_code == 404


def test_view_decide_and_additional_permissions_remain_authoritative(review, db):
    client, entity, fact, interface, relationship, principal, app, *_ = review
    parent, _ = entity("Workload")
    network, _ = interface(parent)
    app.dependency_overrides[get_principal] = lambda: replace(principal, grants=())
    assert client.get("/reconciliation-entities").status_code == 403
    assert client.post(f"/reconciliation-entities/{parent.id}/accept", json={"items": [{"id": str(parent.id), "version": "0" * 64}]}).status_code == 403
    view_only = make_principal("reconciliation.view")
    app.dependency_overrides[get_principal] = lambda: view_only
    group = group_named(client, "Workload")
    assert not group["parent"]["can_accept"]
    assert client.post(f"/reconciliation-entities/{parent.id}/accept", json={"items": group["decision_items"]}).status_code == 403
    limited = replace(principal, grants=(replace(principal.grants[0], permissions=frozenset(["reconciliation.view", "reconciliation.decide"])),))
    app.dependency_overrides[get_principal] = lambda: limited
    result = accept_all(client, group_named(client, "Workload"))
    assert len(result["accepted"]) == 1 and len(result["blocked"]) == 1
    assert "Permission" in result["blocked"][0]["reason"]


def test_projection_uses_constant_queries_and_never_mutates_read_state(review, db):
    client, entity, fact, interface, relationship, *_ = review
    parent, _ = entity("First")
    target, _ = entity("Second")
    relation, claim = relationship(parent, target)
    original = dict(relation.observed_value_json)
    counts = []
    def count_queries(*args): counts.append(args[2])
    connection = db.connection()
    event.listen(connection, "before_cursor_execute", count_queries)
    try:
        first = page(client)
        initial_count = len(counts)
        for index in range(50):
            owner, _ = entity(f"Owner {index}")
            fact(owner); interface(owner)
        counts.clear()
        page(client)
        assert len(counts) == initial_count == 8
        assert not any(query.lstrip().upper().startswith(("UPDATE", "INSERT", "DELETE")) for query in counts)
    finally:
        event.remove(connection, "before_cursor_execute", count_queries)
    assert relation.observed_value_json == original and claim.subject_id is None


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"cursor": "broken"}, {"section": "unknown"}])
def test_invalid_group_pagination_is_rejected(review, params):
    assert review[0].get("/reconciliation-entities", params=params).status_code == 422


def test_generic_labels_prefer_metadata_without_special_source_keys():
    assert fact_label("any-source.bridge_name") == "Bridge Name"
    assert fact_label("another-source.vlan_tag", {"label": "VLAN"}) == "VLAN"


def test_concurrent_group_decisions_accept_once_with_one_audit():
    """Two independent connections compete for the same reviewed proposal."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import create_engine, delete
    from sqlalchemy.orm import Session
    from app.models import Base, DataSource, DiscoveryRun, Workspace, User
    from app.routes.knowledge import accept_reconciliation_entity
    from app.schemas import ReconciliationGroupAcceptRequest
    from app.services.reconciliation_entities import entity_page
    from tests.test_administration import request
    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"], hide_parameters=True)
    principal = make_principal("reconciliation.view", "reconciliation.decide")
    principal.user.email = uuid.uuid4().hex + "@example.test"
    customer_id = workspace_id = None
    try:
        with Session(engine, expire_on_commit=False) as setup:
            setup.add(principal.user)
            workspace = Workspace(name="Concurrent entity review", slug=uuid.uuid4().hex)
            setup.add(workspace); setup.flush(); workspace_id = workspace.id
            customer = Customer(name="Concurrent entity review", workspace_id=workspace.id)
            setup.add(customer); setup.flush(); customer_id = customer.id
            site = Site(name="Concurrent entity review", customer_id=customer.id)
            setup.add(site); setup.flush()
            source = DataSource(customer_id=customer.id, site_id=site.id, name="Source", source_type="connector")
            setup.add(source); setup.flush()
            claim = KnowledgeAssertion(customer_id=customer.id, site_id=site.id, subject_type="asset",
                subject_external_id=uuid.uuid4().hex, predicate="name", value_json="Concurrent review",
                data_source_id=source.id, truth_classification="observed", confirmation_status="unreviewed",
                first_observed_at=NOW, last_observed_at=NOW, confidence=1)
            setup.add(claim); setup.flush()
            item = ReconciliationItem(customer_id=customer.id, site_id=site.id, category="newly_discovered", status="open",
                entity_type="asset", candidate_external_id=claim.subject_external_id, assertion_id=claim.id,
                observed_value_json={"name": "Concurrent review", "asset_type": "virtual_machine", "facts": {}})
            setup.add(item); setup.commit()
            context = ActiveContext(customer.id, site.id)
            group = entity_page(setup, context, principal, limit=50)["entities"][0]
            payload = ReconciliationGroupAcceptRequest.model_validate({"items": group["decision_items"]})
            identifier = uuid.UUID(group["id"])
        barrier = Barrier(2)
        def decide():
            with Session(engine) as connection:
                barrier.wait(timeout=10)
                return accept_reconciliation_entity(identifier, payload, request(), context, principal, connection)
        with ThreadPoolExecutor(max_workers=2) as workers:
            outcomes = list(workers.map(lambda _: decide(), range(2)))
        assert sorted(len(result["accepted"]) for result in outcomes) == [0, 1]
        assert sorted(len(result["already_resolved"]) for result in outcomes) == [0, 1]
        with Session(engine) as check:
            assert check.scalar(select(func.count()).select_from(Asset).where(Asset.customer_id == customer_id)) == 1
            assert check.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.customer_id == customer_id)) == 1
    finally:
        # Only this test's committed disposable fixtures are removed. The test
        # suite requires ATLAS_TEST_DATABASE_URL, never an operator installation.
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
