"""E1-G contract through authenticated APIs on disposable PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, insert, select, update

from app.models import (
    AccessAssignment, Asset, AuditEvent, BusinessFunction, DiscoveryRun, EvidenceRecord, Integration,
    KnowledgeAssertion, KnowledgeChange, KnowledgeGap, KnowledgeRequirementDefinition,
    ReconciliationItem, Service, ServiceAssetDependency, SiteOnboarding,
)
from app.services import onboarding
from tests.test_onboarding_discovery_review_postgres import GRANTS, asset, batch, observe, page
from tests.test_onboarding_integrations_postgres import at_integrations, decide, discovery_history, scope_headers
from tests.test_onboarding_link_services_postgres import PERMISSIONS, case, ok, reach_link_services
from tests.test_onboarding_postgres import ENTRY, env, pytestmark

READ = PERMISSIONS | GRANTS | {"business_functions.view", "business_functions.manage"}


def advance(actor, pair, state):
    return ok(actor.client.post(pair.path + "/link-services/decision", json={
        "version": state["version"], "action": "skip",
    }))


def review(actor, pair, **options):
    return ok(actor.client.get(pair.path + "/review-ready", **options))


def continue_to_showcase(actor, pair, version):
    return actor.client.post(pair.path + "/review-ready/decision", json={"version": version})


@pytest.mark.parametrize("profile", ["blank", "homelab"])
def test_empty_and_restricted_reviews_are_advisory(env, monkeypatch, profile):
    pair = env.pair()
    manager = env.actor(ENTRY, "site", pair.customer.id, pair.site.id)
    reader = env.actor(READ - {"sites.manage"}, "site", pair.customer.id, pair.site.id)
    state = at_integrations(manager, pair, profile)
    assert manager.client.get(pair.path + "/review-ready").status_code == 404
    assert continue_to_showcase(manager, pair, state["version"]).status_code == 409
    state = ok(decide(manager, pair, state["version"], "skipped"))
    state = ok(manager.client.post(pair.path + "/discovery-review/decision", json={
        "version": state["version"], "decision": "skipped",
    }))
    state = advance(manager, pair, state)

    empty = review(reader, pair)
    assert empty["profile"] == profile
    assert empty["business_functions"] == empty["services"] == empty["required_gaps"] == 0
    assert empty["integrations"] == {"items": [], "has_more": False}
    assert empty["discovery"] == {"decisions": dict(eligible=0, conflicts=0, exceptions=0), "active_runs": 0}
    assert empty["link_services"] == dict(linked=0, unlinked=0, mappings=0, unavailable=0)

    restricted = review(manager, pair)
    for key in ("business_functions", "services", "required_gaps", "integrations", "link_services"):
        assert restricted[key] is None
    assert restricted["discovery"] == {"decisions": None, "active_runs": None}
    assert continue_to_showcase(reader, pair, state["version"]).status_code == 404
    saved = ok(manager.client.post(pair.path + "/save", json={"version": state["version"]}))
    assert saved["status"] == "saved" and saved["current_stage"] == "review_ready"
    with env.sessions() as db:
        persisted = db.scalar(select(SiteOnboarding).where(SiteOnboarding.site_id == pair.site.id))
        assert (persisted.status, persisted.current_stage, persisted.version) == ("saved", "review_ready", state["version"] + 1)
        assert persisted.stage_decisions == state["stage_decisions"]
    assert continue_to_showcase(manager, pair, saved["version"]).status_code == 409
    resumed = ok(manager.client.post(pair.path + "/resume", json={"version": saved["version"]}))
    result = ok(continue_to_showcase(manager, pair, resumed["version"]))
    assert result["stage_decisions"] == {**state["stage_decisions"], "review_ready": "completed"}
    assert result["current_stage"] == "showcase"
    assert result["status"] == "in_progress" and result["completed_at"] is None
    assert result["version"] == resumed["version"] + 1
    assert review(reader, pair) == empty
    monkeypatch.delenv("ATLAS_ONBOARDING_PREVIEW")
    assert manager.client.get(pair.path + "/review-ready").status_code == 404
    assert continue_to_showcase(manager, pair, result["version"]).status_code == 404


def test_live_canonical_summary_visibility_and_competing_progress(case, discovery_history, monkeypatch):
    env, pair = case.env, case.pair
    actor = env.actor(READ)
    other = env.actor(ENTRY, "site", pair.customer.id, pair.site.id)
    local = env.actor(READ, "site", pair.customer.id, pair.site.id)
    narrow = env.actor(ENTRY | {"services.view", "reconciliation.view"}, "site", pair.customer.id, pair.site.id)
    state = advance(actor, pair, case.state)
    assert state["stage_decisions"]["capabilities"] == state["stage_decisions"]["link_services"] == "skipped"
    assert review(actor, pair)["services"] == 0

    wide, site_service = case.service("Customer Service", customer_wide=True), case.service("Site Service")
    case.service("Sibling Service", case.sibling)
    case.service("Unrelated Service", case.foreign)
    old = case.service("Archived Service")
    ok(case.client.post(f"/api/services/{old['id']}/archive", json={}))
    ok(case.ordinary(wide, case.asset("Local provider")), 201)
    ok(case.ordinary(wide, case.asset("Other Site provider", case.sibling)), 201)
    for name, customer, site in (
        ("Customer function", pair.customer, None), ("Site function", pair.customer, pair.site),
        ("Sibling function", pair.customer, case.sibling.site), ("Other customer", case.foreign.customer, case.foreign.site),
    ):
        ok(actor.client.post("/api/business-functions", json={
            "name": name, "customer_id": str(customer.id), "site_id": str(site.id) if site else None,
        }), 201)

    failed, _ = discovery_history(pair, "completed", "failed", name="Failed connection")
    running, _ = discovery_history(pair, "running", name="Running connection")
    discovery_history(case.sibling, "running", name="Private connection")
    retired, _ = discovery_history(pair, "failed", name="Retired connection")
    unconfigured, _ = discovery_history(pair, name="Unconfigured connection")
    observe(actor, pair, asset("Previously accepted"))
    row, = page(actor, pair)["items"]
    assert len(ok(batch(actor, pair, row))["accepted"]) == 1
    observe(actor, pair, asset("Eligible"), asset("Blocked", host="Missing endpoint"), asset("Conflict"))
    observe(actor, case.sibling, asset("Unrelated proposal"))
    conflict = next(row for row in page(actor, pair)["items"] if row["entity_name"] == "Conflict")

    with env.sessions.begin() as db:
        db.get(Integration, retired.id).retired_at = datetime.now(timezone.utc)
        integration = db.get(Integration, unconfigured.id)
        integration.connector_id = "proxmox"
        integration.connector_version = "1.0.0"
        integration.connector_digest = "a" * 64
        integration.config_schema_version = "1"
        integration.config_json = {"endpoint": "https://source.example"}
        db.get(ReconciliationItem, UUID(conflict["id"])).category = "possible_duplicate"
        purpose = db.scalars(select(KnowledgeGap).join(KnowledgeRequirementDefinition).where(
            KnowledgeGap.entity_id == UUID(wide["id"]), KnowledgeRequirementDefinition.key == "service_purpose",
        )).one()
        purpose.status = "deferred"

    def snapshot():
        with env.sessions() as db:
            return {model.__name__: db.execute(select(*model.__table__.c).where(
                model.customer_id == pair.customer.id,
            ).order_by(model.id)).all() for model in (
                Asset, BusinessFunction, Service, ServiceAssetDependency, Integration, DiscoveryRun,
                ReconciliationItem, EvidenceRecord, KnowledgeAssertion, KnowledgeGap, KnowledgeChange,
            )}

    before = snapshot()
    continuation_reads = []
    decision_runs = onboarding.integration_decision_runs

    def track_continuation(customer_id, site_id):
        continuation_reads.append((customer_id, site_id))
        return decision_runs(customer_id, site_id)

    monkeypatch.setattr(onboarding, "integration_decision_runs", track_continuation)
    response = actor.client.get(pair.path + "/review-ready", headers=scope_headers(case.foreign))
    result = ok(response)
    assert continuation_reads == []
    ordinary_integrations = ok(actor.client.get("/api/integrations?include_discovery=true", headers=scope_headers(pair)))
    assert continuation_reads == [(pair.customer.id, pair.site.id)]
    assert next(row for row in ordinary_integrations if row["id"] == str(running.id))["continuation_run_id"]
    assert response.headers["Cache-Control"] == "no-store"
    assert (result["business_functions"], result["services"]) == (2, 2)
    assert result["site"]["id"] == str(pair.site.id) and result["customer"]["id"] == str(pair.customer.id)
    assert result["link_services"] == dict(linked=1, unlinked=1, mappings=1, unavailable=0)
    assert result["discovery"] == {"decisions": dict(eligible=2, conflicts=1, exceptions=1), "active_runs": 1}
    assert result["integrations"]["items"] == [
        dict(id=str(failed.id), name="Failed connection", status=failed.status,
             discovery_status="failed", discovery_configured=None),
        dict(id=str(running.id), name="Running connection", status=running.status,
             discovery_status="running", discovery_configured=None),
        dict(id=str(unconfigured.id), name="Unconfigured connection", status="unconfigured",
             discovery_status=None, discovery_configured=None),
    ]
    for user in (actor, local):
        summary = review(user, pair)
        dashboard = ok(user.client.get("/api/dashboard/summary?include_customer_wide=true", headers=scope_headers(pair)))
        assert summary["required_gaps"] == dashboard["open_knowledge_gap_count"] > 0
    assert review(local, pair)["required_gaps"] < result["required_gaps"]
    assert review(local, pair)["business_functions"] == review(local, pair)["services"] == 1
    assert actor.client.get(f"/api/onboarding/{case.foreign.customer.id}/{pair.site.id}/review-ready").status_code == 404
    assert local.client.get(case.sibling.path + "/review-ready").status_code == 404

    independent = review(narrow, pair)
    assert independent["services"] == 1 and independent["link_services"] is None
    assert independent["discovery"]["active_runs"] is None and independent["integrations"] is None
    assert independent["discovery"]["decisions"]["eligible"] == 0
    assert independent["required_gaps"] is None
    with env.sessions.begin() as db:
        domain_grant = AccessAssignment(user_id=other.id, role_id=db.get(AccessAssignment, local.grant).role_id,
                                       scope_type="site", customer_id=pair.customer.id, site_id=pair.site.id)
        db.add(domain_grant)
        db.flush()
        domain_grant_id = domain_grant.id
    assert review(other, pair)["services"] == 1
    with env.sessions.begin() as db:
        db.execute(delete(AccessAssignment).where(AccessAssignment.id == domain_grant_id))
    assert review(other, pair)["services"] is None
    assert review(other, pair)["discovery"] == {"decisions": None, "active_runs": None}

    start = Barrier(2)

    def advance_shared(user):
        start.wait(timeout=5)
        return continue_to_showcase(user, pair, state["version"])

    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(advance_shared, (actor, other)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response.json() for response in responses if response.status_code == 200)
    assert (winner["current_stage"], winner["status"], winner["version"]) == ("showcase", "in_progress", state["version"] + 1)
    assert winner["stage_decisions"] == {**state["stage_decisions"], "review_ready": "completed"}
    with env.sessions() as db:
        assert len(db.scalars(select(AuditEvent).where(
            AuditEvent.site_id == pair.site.id, AuditEvent.event_type == "onboarding.review_ready_completed",
        )).all()) == 1
    assert snapshot() == before


def test_gap_total_exceeds_list_limit_and_excludes_noncurrent_records(case):
    actor, pair = case.actor, case.pair
    advance(actor, pair, case.state)
    service = case.service("Service classification source", customer_wide=True)
    now = datetime.now(timezone.utc)
    with case.env.sessions.begin() as db:
        row = db.get(Service, UUID(service["id"]))
        definition_id = db.scalar(select(KnowledgeRequirementDefinition.id).where(
            KnowledgeRequirementDefinition.key == "service_purpose",
        ))
        ids = [uuid4() for _ in range(501)]
        hidden_ids = [uuid4() for _ in range(4)]
        ids_to_seed = ids + hidden_ids
        db.execute(insert(Service), [
            dict(id=identifier, name=f"Synthetic Service {index}", slug=f"synthetic-{index}", customer_id=pair.customer.id,
                 site_id=pair.site.id, service_type_id=row.service_type_id, criticality_level_id=row.criticality_level_id)
            for index, identifier in enumerate(ids_to_seed)
        ])
        db.execute(insert(KnowledgeGap), [
            dict(customer_id=pair.customer.id, site_id=case.sibling.site.id if index == 502 else pair.site.id,
                 entity_type="service", entity_id=identifier, requirement_definition_id=definition_id,
                 severity="medium", requirement_level="recommended" if index == 503 else "conditional",
                 status="resolved" if index == 504 else "deferred", summary="Seeded review gap",
                 first_detected_at=now, last_evaluated_at=now, last_state_changed_at=now)
            for index, identifier in enumerate(ids_to_seed)
        ])
        db.execute(update(Service).where(Service.id == hidden_ids[0]).values(deleted_at=now))
    expected = ok(actor.client.get("/api/dashboard/summary?include_customer_wide=true",
                                   headers=scope_headers(pair)))["open_knowledge_gap_count"]
    assert expected > 501
    assert review(actor, pair)["required_gaps"] == expected
    # This history has a mismatched scope in the selected Site. It would
    # inflate the count if scalar aggregation bypassed the live-record policy.
    with case.env.sessions.begin() as db:
        gap = db.scalars(select(KnowledgeGap).where(KnowledgeGap.entity_id == hidden_ids[1])
                         .execution_options(include_unmatched_completeness=True)).one()
        gap.site_id = pair.site.id
        db.get(Service, hidden_ids[1]).site_id = case.sibling.site.id
    assert review(actor, pair)["required_gaps"] == expected
