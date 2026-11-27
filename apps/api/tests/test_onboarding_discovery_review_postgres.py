"""E1-E acceptance through authenticated canonical and Site workflow APIs."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import secrets
from threading import Barrier, Event
from uuid import UUID

from fastapi import HTTPException
import pytest
from sqlalchemy import delete, func, select

from app.models import (AccessAssignment, Asset, AssetRelationship, AuditEvent, Base, Customer, DiscoveryRun,
                        EvidenceRecord, Integration, KnowledgeAssertion, KnowledgeChange, ReconciliationItem,
                        Service, Site)
from app.routes import knowledge
from tests.test_onboarding_integrations_postgres import at_integrations, decide, discovery_history, scope_headers
from tests.test_onboarding_postgres import ENTRY, env, pytestmark
from tests.test_knowledge_integrity_migration import migrated_history
from tests.test_proxmox_guest_identity_postgres import cases

REVIEW = "/api/reconciliation-entities/discovery-review"
GRANTS = ENTRY | {"integrations.view", "discovery.simulate", "reconciliation.view", "reconciliation.decide",
                  "assets.view", "assets.edit", "relationships.create"}


@pytest.fixture
def review_site(env, discovery_history):
    pairs = []

    def create(*, customer=None):
        pair = env.pair(customer=customer)
        pairs.append(pair)
        return pair

    yield create
    with env.sessions.begin() as db:
        customer_ids = {pair.customer.id for pair in pairs}
        for table in reversed(Base.metadata.sorted_tables):
            if table not in {Site.__table__, Customer.__table__} and "customer_id" in table.c:
                db.execute(delete(table).where(table.c.customer_id.in_(customer_ids)))


def state_at_review(actor, pair):
    state = at_integrations(actor, pair)
    response = decide(actor, pair, state["version"], "skipped")
    assert response.status_code == 200, response.text
    return response.json()


def observe(actor, pair, *observations, source=None, complete=False):
    response = actor.client.post("/api/discovery/simulate", headers=scope_headers(pair), json={
        "customer_id": str(pair.customer.id), "site_id": str(pair.site.id),
        "observations": observations, "data_source_id": str(source) if source else None,
        "is_complete_snapshot": complete,
    })
    assert response.status_code == 200, response.text
    return response.json()


def asset(name, *, external=None, host=None):
    return {"name": name, "external_id": external or name, "asset_type": "virtual_machine",
            "relationships": [{"relationship_type": "runs_on", "target_external_id": host}] if host else []}


def page(actor, pair, **params):
    response = actor.client.get(REVIEW, headers=scope_headers(pair), params=params)
    assert response.status_code == 200, response.text
    return response.json()


def items(result):
    return {row["id"]: row for row in result["items"]}


def batch(actor, pair, *rows):
    return actor.client.post(REVIEW + "/accept", headers=scope_headers(pair), json={
        "items": [{"id": row["id"], "version": row["batch_version"] or row["version"]} for row in rows],
    })


def individual(actor, pair, row, **body):
    return actor.client.post(f"/api/reconciliation-items/{row['id']}/accept",
        headers=scope_headers(pair), json={"expected_version": row["version"], **body})


def advance(actor, pair, version, decision, snapshot=None):
    return actor.client.post(pair.path + "/discovery-review/decision", json={
        "version": version, "decision": decision, "review_version": snapshot,
    })


def test_unified_scope_bounded_batch_and_newly_eligible(env, review_site, discovery_history):
    pair = review_site()
    sibling = review_site(customer=pair.customer)
    unrelated = review_site()
    actor = env.actor(GRANTS)
    manager = env.actor(GRANTS, "site", pair.customer.id, pair.site.id)
    viewer = env.actor(GRANTS - {"reconciliation.decide", "sites.manage"}, "site", pair.customer.id, pair.site.id)
    state_at_review(manager, pair)
    completed, _ = discovery_history(pair, "completed", name="Old completed connection")
    discovery_history(pair, "running", name="Independent running connection")
    observe(actor, sibling, asset("Sibling asset"))
    foreign = observe(actor, unrelated, asset("Unrelated asset"))
    earlier = observe(actor, pair, asset("Earlier asset"), source=completed.data_source_id)
    linked = observe(actor, pair, asset("Guest", host="Host"), asset("Host"), asset("Stale"))
    ids = {row["id"] for result in (earlier, linked) for row in result["reconciliation_items"]}
    before = page(manager, pair)
    assert set(items(before)) == ids
    assert before["summary"]["active_runs"] == 1 and before["summary"]["accepted"] == 0
    assert (before["eligible"], before["needs_review"]) == (4, 1)
    assert len(before["sources"]) == 2
    assert page(manager, pair, search="earlier", source_id=completed.data_source_id, category="newly_discovered")["eligible"] == 1
    limited = page(manager, pair, limit=1)
    assert len(limited["items"]) == 1 and limited["eligible"] == 4 and limited["needs_review"] == 1
    assert page(viewer, pair)["eligible"] == 0
    assert page(viewer, pair)["needs_review"] == 5
    assert viewer.client.get(REVIEW, headers=scope_headers(sibling)).status_code == 403
    assert viewer.client.get(REVIEW, headers=scope_headers(unrelated)).status_code == 403

    row_by_name = {row["entity_name"]: row for row in before["items"] if row["batch_version"]}
    blocked = next(row for row in before["items"] if not row["batch_version"])
    assert blocked["entity_type"] == "asset_relationship"
    assert len(blocked["blockers"]) == 2
    assert batch(viewer, pair, row_by_name["Host"]).status_code == 403
    foreign_row = next(iter(items(page(actor, unrelated)).values()))
    assert foreign_row["id"] == foreign["reconciliation_items"][0]["id"]
    assert batch(actor, pair, foreign_row).status_code == 404

    with env.sessions.begin() as db:
        def count(model):
            return db.scalar(select(func.count()).select_from(model).where(model.site_id == pair.site.id))
        assert count(EvidenceRecord) == 4 and count(ReconciliationItem) == 5
        assert count(Asset) == count(AssetRelationship) == 0
        stale = db.get(ReconciliationItem, UUID(row_by_name["Stale"]["id"]))
        stale.observed_value_json = {**stale.observed_value_json, "name": "Updated stale proposal"}

    arrived = observe(actor, pair, asset("Arrived after review"))["reconciliation_items"][0]
    result = batch(manager, pair, *row_by_name.values(), blocked)
    assert result.status_code == 200, result.text
    result = result.json()
    accepted_ids = {row_by_name[name]["id"] for name in ("Earlier asset", "Guest", "Host")}
    assert {row["id"] for row in result["accepted"]} == accepted_ids
    assert [row["id"] for row in result["blocked"]] == [blocked["id"]]
    assert [row["id"] for row in result["failed"]] == [row_by_name["Stale"]["id"]]
    assert result["newly_eligible_total"] == 1
    assert result["newly_eligible"][0]["id"] == blocked["id"]

    now = page(manager, pair)
    assert now["summary"]["accepted"] == 3
    assert set(items(now)) == {blocked["id"], arrived["id"], row_by_name["Stale"]["id"]}
    assert batch(actor, pair, row_by_name["Host"]).json()["already_resolved"][0]["id"] == row_by_name["Host"]["id"]
    assert batch(actor, pair, blocked).json()["failed"][0]["id"] == blocked["id"]
    assert individual(manager, pair, items(now)[blocked["id"]]).status_code == 200

    with env.sessions() as db:
        assert set(db.scalars(select(Asset.name).where(Asset.site_id == pair.site.id))) == {"Earlier asset", "Guest", "Host"}
        relationship = db.scalars(select(AssetRelationship).where(AssetRelationship.site_id == pair.site.id)).one()
        assert relationship.customer_id == pair.customer.id
        assert db.get(Asset, relationship.source_asset_id).name == "Guest"
        assert db.get(Asset, relationship.target_asset_id).name == "Host"
        for identifier in accepted_ids | {blocked["id"]}:
            item = db.get(ReconciliationItem, UUID(identifier))
            claim = db.get(KnowledgeAssertion, item.assertion_id)
            assert item.status == "accepted" and item.decided_by_user_id == manager.id
            assert claim.is_accepted and claim.accepted_by_user_id == manager.id
            assert db.scalar(select(KnowledgeChange).where(KnowledgeChange.reconciliation_item_id == item.id))
            audit = db.scalars(select(AuditEvent).where(AuditEvent.target_id == item.id,
                AuditEvent.event_type == "reconciliation.accepted")).one()
            assert audit.user_id == manager.id and audit.site_id == pair.site.id
        assert db.get(ReconciliationItem, UUID(arrived["id"])).status == "open"
        assert db.scalar(select(func.count()).select_from(Service).where(Service.customer_id == pair.customer.id)) == 0


def test_exception_is_individual_and_retired_source_is_excluded(env, review_site, discovery_history):
    pair = review_site()
    actor = env.actor(GRANTS)
    state_at_review(actor, pair)
    integration, _ = discovery_history(pair, "completed")
    observe(actor, pair, asset("Retirement target"), source=integration.data_source_id, complete=True)
    first = page(actor, pair)["items"][0]
    assert individual(actor, pair, first).status_code == 200
    observe(actor, pair, asset("Different observation"), source=integration.data_source_id, complete=True)
    absence = next(row for row in page(actor, pair)["items"] if row["category"] == "no_longer_observed")
    assert absence["batch_version"] is None and "lifecycle" in absence["batch_exclusion"]
    assert batch(actor, pair, absence).json()["blocked"][0]["id"] == absence["id"]
    with env.sessions() as db:
        assert db.get(Asset, UUID(absence["entity_id"])).status == "active"
    assert individual(actor, pair, absence, disposition="retire").status_code == 200
    with env.sessions.begin() as db:
        assert db.get(Asset, UUID(absence["entity_id"])).status == "retired"
        db.get(Integration, integration.id).retired_at = datetime.now(timezone.utc)
    assert page(actor, pair)["items"] == []


def test_ordinary_asset_proposal_can_require_explicit_link_after_another_source_is_accepted(env, review_site, discovery_history):
    pair = review_site()
    actor = env.actor(GRANTS)
    state_at_review(actor, pair)
    first, _ = discovery_history(pair, "completed", name="First integration")
    second, _ = discovery_history(pair, "completed", name="Second integration")
    observe(actor, pair, asset("Shared name"), source=first.data_source_id)
    observe(actor, pair, asset("Shared name"), source=second.data_source_id)
    original = page(actor, pair)["items"]
    assert len(original) == 2 and all(row["batch_version"] for row in original)
    response = individual(actor, pair, original[0])
    assert response.status_code == 200, response.text
    [remaining] = page(actor, pair)["items"]
    assert remaining["category"] == "newly_discovered"
    assert remaining["batch_version"] is None and not remaining["can_accept"]
    assert batch(actor, pair, original[1]).json()["blocked"][0]["id"] == remaining["id"]
    linked = actor.client.post(f"/api/reconciliation-items/{remaining['id']}/link-asset", headers=scope_headers(pair),
        json={"asset_id": response.json()["entity_id"], "expected_version": remaining["version"]})
    assert linked.status_code == 200, linked.text
    with env.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Asset).where(Asset.site_id == pair.site.id)) == 1


def test_progress_rechecks_review_save_resume_skip_and_manual(env, review_site, discovery_history):
    pair = review_site()
    actor = env.actor(GRANTS)
    other = env.actor(GRANTS, "site", pair.customer.id, pair.site.id)
    state = state_at_review(actor, pair)
    initial = page(actor, pair)["summary"]
    assert initial["eligible"] == initial["active_runs"] == 0
    discovery_history(pair, "pending")
    assert advance(actor, pair, state["version"], "completed", initial["version"]).json()["detail"]["code"] == "discovery_review_changed"
    queued = page(actor, pair)["summary"]
    assert queued["active_runs"] == 1
    assert advance(actor, pair, state["version"], "completed", queued["version"]).status_code == 422

    saved = actor.client.post(pair.path + "/save", json={"version": state["version"]}).json()
    assert advance(other, pair, state["version"], "attention", queued["version"]).status_code == 409
    resumed = other.client.post(pair.path + "/resume", json={"version": saved["version"]}).json()
    observe(actor, pair, asset("Outstanding after resume"))
    current = page(other, pair)["summary"]
    assert current["eligible"] == 1
    advanced = advance(other, pair, resumed["version"], "attention", current["version"])
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["stage_decisions"]["discovery_review"] == "attention"
    assert advanced.json()["current_stage"] == "link_services"
    assert advance(actor, pair, advanced.json()["version"], "skipped").status_code == 409
    assert page(actor, pair)["eligible"] == 1

    skipped = review_site()
    state = state_at_review(actor, skipped)
    observe(actor, skipped, asset("Still open after skip"))
    advance_response = advance(actor, skipped, state["version"], "skipped")
    assert advance_response.json()["stage_decisions"]["discovery_review"] == "skipped"
    assert advance_response.json()["current_stage"] == "link_services"
    assert page(actor, skipped)["eligible"] == 1

    manual = review_site()
    state = state_at_review(actor, manual)
    blank = page(actor, manual)["summary"]
    assert blank["eligible"] == blank["needs_review"] == blank["accepted"] == blank["active_runs"] == 0
    assert advance(actor, manual, state["version"], "completed", blank["version"]).json()["stage_decisions"]["discovery_review"] == "completed"

    limited = review_site()
    manager = env.actor(ENTRY, "site", limited.customer.id, limited.site.id)
    state = state_at_review(manager, limited)
    proposal = observe(actor, limited, asset("Outside this operator's review permissions"))["reconciliation_items"][0]
    restricted = page(manager, limited, decision_id=proposal["id"])
    assert restricted["items"] == [] and restricted["decisions"] == {}
    assert all(restricted["summary"][key] is None for key in ("eligible", "needs_review", "accepted", "active_runs"))
    assert advance(manager, limited, state["version"], "completed", restricted["summary"]["version"]).status_code == 422
    assert advance(manager, limited, state["version"], "attention", restricted["summary"]["version"]).status_code == 200
    assert page(actor, limited)["eligible"] == 1


def test_rollback_then_competing_decisions_and_revoked_permissions(env, review_site, monkeypatch):
    pair = review_site()
    actor = env.actor(GRANTS, "site", pair.customer.id, pair.site.id)
    other = env.actor(GRANTS, "site", pair.customer.id, pair.site.id)
    viewer = env.actor(GRANTS, "site", pair.customer.id, pair.site.id)
    state_at_review(actor, pair)
    observe(actor, pair, asset("First"), asset("Second"))
    rows = page(actor, pair)["items"]
    real_commit = knowledge.commit

    def fail_at_commit(db, operation):
        if operation == "Entity reconciliation decisions":
            assert db.scalar(select(func.count()).select_from(Asset).where(Asset.site_id == pair.site.id)) == 2
            raise HTTPException(409, "Forced commit failure")
        return real_commit(db, operation)

    with monkeypatch.context() as patch:
        patch.setattr(knowledge, "commit", fail_at_commit)
        assert batch(actor, pair, *rows).status_code == 409
    with env.sessions() as db:
        assert list(db.scalars(select(Asset).where(Asset.site_id == pair.site.id))) == []
    assert page(actor, pair)["eligible"] == 2

    gate = Barrier(2)

    def compete(principal):
        gate.wait(timeout=5)
        response = batch(principal, pair, *rows)
        assert response.status_code == 200, response.text
        return response.json()

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(compete, (actor, other)))
    assert sorted(len(result["accepted"]) for result in results) == [0, 2]
    assert sorted(len(result["already_resolved"]) for result in results) == [0, 2]

    observe(actor, pair, asset("Permission changed"))
    candidate = page(viewer, pair)["items"][0]
    reached_locks, continue_request = Event(), Event()
    lock_sources = knowledge._lock_decision_sources

    def pause_after_locks(db, identifiers):
        lock_sources(db, identifiers)
        reached_locks.set()
        assert continue_request.wait(5)

    with monkeypatch.context() as patch:
        patch.setattr(knowledge, "_lock_decision_sources", pause_after_locks)
        with ThreadPoolExecutor(1) as pool:
            in_flight = pool.submit(batch, viewer, pair, candidate)
            assert reached_locks.wait(5)
            try:
                with env.sessions.begin() as db:
                    db.execute(delete(AccessAssignment).where(AccessAssignment.id == viewer.grant))
            finally:
                continue_request.set()
            assert in_flight.result().status_code == 404
    assert batch(viewer, pair, candidate).status_code == 403
    assert page(actor, pair)["eligible"] == 1


def test_discovery_review_preview_gate(env, review_site, monkeypatch):
    pair = review_site()
    actor = env.actor(GRANTS)
    state = state_at_review(actor, pair)
    monkeypatch.delenv("ATLAS_ONBOARDING_PREVIEW")
    assert actor.client.get(REVIEW, headers=scope_headers(pair)).status_code == 404
    assert advance(actor, pair, state["version"], "skipped").status_code == 404


@pytest.mark.parametrize("outcome", ["reactivate", "replace"])
def test_proxmox_identity_case_uses_canonical_comparison_and_decision(cases, monkeypatch, outcome):
    from dataclasses import replace
    from app.authorization import get_principal

    monkeypatch.setenv("AUTH_SECRET_KEY", secrets.token_hex(48))
    monkeypatch.setenv("ATLAS_ONBOARDING_PREVIEW", "true")
    case = cases()
    case.seed()
    case.retire()
    case.run(name="Guest awaiting an explicit decision")
    principal = replace(case.principal, grants=(replace(case.principal.grants[0],
        permissions=case.principal.grants[0].permissions | {"customers.view", "integrations.view"}),))
    case.client.app.dependency_overrides[get_principal] = lambda: principal
    path = REVIEW.removeprefix("/api")
    response = case.client.get(path)
    assert response.status_code == 200, response.text
    row = next(row for row in response.json()["items"] if row["entity_type"] == "source_identity")
    assert row["batch_version"] is None and not row["can_accept"]
    assert row["identity_review"]["actions"][outcome] is None
    rejected = case.client.post(path + "/accept", json={"items": [{"id": row["id"], "version": row["version"]}]})
    assert rejected.status_code == 200, rejected.text
    assert [entry["id"] for entry in rejected.json()["blocked"]] == [row["id"]]
    version_key = "replacement_expected_version" if outcome == "replace" else "expected_version"
    result = case.decide(row, "identity-decision", outcome=outcome, reason="Verified the guest identity",
                         expected_version=row["identity_review"][version_key])
    assert result.status_code == 200, result.text
    assert result.json()["outcome"] == outcome
    assert row["id"] not in items(case.client.get(path).json())
