"""Authenticated Site decisions and canonical integration reads on PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.models import AccessAssignment, AuditEvent, DataSource, DiscoveryRun, Integration, SiteOnboarding
from tests.test_onboarding_postgres import ENTRY, confirm, env, pytestmark

INTEGRATIONS = ENTRY | {"integrations.view"}


def at_integrations(actor, pair, profile="blank"):
    assert actor.client.post(f"{pair.path}/start").status_code == 200
    response = confirm(actor.client, pair.path, profile=profile)
    assert response.status_code == 200
    response = actor.client.post(f"{pair.path}/capabilities/skip", json={"version": response.json()["version"]})
    assert response.status_code == 200
    return response.json()


def decide(actor, pair, version, decision, run=None):
    return actor.client.post(f"{pair.path}/integrations/decision", json={
        "version": version, "decision": decision, "discovery_run_id": str(run) if run else None,
    })


@pytest.fixture
def discovery_history(env):
    ids = []

    def add(pair, *statuses, name="Existing test connection"):
        with env.sessions.begin() as db:
            source = DataSource(name="Existing source", source_type="connector", status="active", trust_level="observed",
                customer_id=pair.customer.id, site_id=pair.site.id)
            db.add(source)
            db.flush()
            row = Integration(name=name, plugin_id="proxmox",
                customer_id=pair.customer.id, site_id=pair.site.id, creation_key=uuid4(),
                data_source_id=source.id, base_url="", username_or_token_id="", secret_reference="")
            db.add(row)
            db.flush()
            ids.append(row.id)
            now = datetime.now(timezone.utc)
            runs = [DiscoveryRun(integration_id=row.id, customer_id=row.customer_id,
                site_id=row.site_id, data_source_id=source.id, status=status,
                started_at=now + timedelta(seconds=index),
                dispatch_state=status if status in ("pending", "running") else "settled",
                execution_provenance={"trigger": "manual"} if status in ("pending", "running") else None)
                for index, status in enumerate(statuses)]
            db.add_all(runs)
            db.flush()
            return row, runs

    yield add
    with env.sessions.begin() as db:
        db.execute(delete(DiscoveryRun).where(DiscoveryRun.integration_id.in_(ids)))
        db.execute(delete(Integration).where(Integration.id.in_(ids)))


def scope_headers(pair):
    return {"X-Atlas-Customer-ID": str(pair.customer.id), "X-Atlas-Site-ID": str(pair.site.id)}


@pytest.mark.parametrize("profile", ["blank", "homelab"])
def test_manual_continuation_is_versioned_and_keeps_existing_knowledge(env, discovery_history, profile):
    pair = env.pair()
    manager = env.actor(ENTRY, "site", pair.customer.id, pair.site.id)
    second = env.actor(ENTRY, "site", pair.customer.id, pair.site.id)
    viewer = env.actor(ENTRY - {"sites.manage"}, "site", pair.customer.id, pair.site.id)
    state = at_integrations(manager, pair, profile)
    row, [run] = discovery_history(pair, "completed")
    assert decide(viewer, pair, state["version"], "skipped").status_code == 404
    assert decide(manager, pair, state["version"], "completed", run.id).status_code == 404
    assert decide(manager, pair, state["version"], "skipped", run.id).status_code == 422

    saved = manager.client.post(f"{pair.path}/save", json={"version": state["version"]}).json()
    assert decide(second, pair, state["version"], "skipped").status_code == 409
    assert decide(second, pair, saved["version"], "skipped").status_code == 409
    resumed = second.client.post(f"{pair.path}/resume", json={"version": saved["version"]}).json()
    response = decide(second, pair, resumed["version"], "skipped")
    assert response.status_code == 200, response.text
    progress = response.json()
    assert progress["current_stage"] == "discovery_review"
    assert progress["stage_decisions"] == {**state["stage_decisions"], "integrations": "skipped"}
    assert decide(manager, pair, progress["version"], "skipped").status_code == 409

    with env.sessions() as db:
        assert db.get(Integration, row.id)
        assert db.get(DiscoveryRun, run.id).status == "completed"
        audit = db.scalar(select(AuditEvent).where(AuditEvent.site_id == pair.site.id,
            AuditEvent.event_type == "onboarding.integrations_skipped"))
        assert audit.user_id == second.id
        assert db.scalar(select(SiteOnboarding).where(SiteOnboarding.site_id == pair.site.id)).last_actor_id == second.id


@pytest.mark.parametrize("status", ["pending", "running", "completed"])
def test_run_decision_and_creation_lookup_are_exactly_site_scoped(env, discovery_history, status):
    pair = env.pair()
    sibling = env.pair(customer=pair.customer)
    unrelated = env.pair()
    manager = env.actor(INTEGRATIONS, "site", pair.customer.id, pair.site.id)
    owner = env.actor(INTEGRATIONS)
    state = at_integrations(manager, pair)
    row, [failed, eligible] = discovery_history(pair, "failed", status)
    other, [sibling_run] = discovery_history(sibling, "completed")
    _, [foreign_run] = discovery_history(unrelated, "completed")

    response = manager.client.get("/api/integrations?include_discovery=true", headers=scope_headers(pair))
    assert response.status_code == 200, response.text
    [record] = response.json()
    assert record["id"] == str(row.id)
    assert record["run"]["id"] == str(eligible.id)
    assert record["continuation_run_id"] == str(eligible.id)
    assert "error_message" not in record["run"]
    assert "credentials" not in record
    for key, expected in [(row.creation_key, [str(row.id)]), (other.creation_key, [])]:
        response = owner.client.get(f"/api/integrations?creation_key={key}", headers=scope_headers(pair))
        assert [entry["id"] for entry in response.json()] == expected
    assert owner.client.get(f"/api/integrations?creation_key={row.creation_key}").status_code == 422
    assert manager.client.get("/api/integrations?include_discovery=true", headers=scope_headers(sibling)).status_code == 403
    hidden = env.actor(ENTRY, "site", pair.customer.id, pair.site.id)
    assert hidden.client.get("/api/integrations?include_discovery=true", headers=scope_headers(pair)).status_code == 403

    for unavailable in (failed, sibling_run, foreign_run):
        assert decide(owner, pair, state["version"], "completed", unavailable.id).status_code == 422
    response = decide(manager, pair, state["version"], "completed", eligible.id)
    assert response.status_code == 200, response.text
    assert response.json()["current_stage"] == "discovery_review"
    assert response.json()["stage_decisions"] == {**state["stage_decisions"], "integrations": "completed"}


@pytest.mark.parametrize("status", ["pending", "running", "completed"])
def test_continuation_projection_preserves_history_and_matches_site_decision(env, discovery_history, status):
    pair = env.pair()
    manager = env.actor(INTEGRATIONS, "site", pair.customer.id, pair.site.id)
    second = env.actor(INTEGRATIONS, "site", pair.customer.id, pair.site.id)
    state = at_integrations(manager, pair)
    retired, [historic] = discovery_history(pair, "completed", name="A retired")
    with env.sessions.begin() as db:
        db.get(Integration, retired.id).retired_at = datetime.now(timezone.utc)

    def projection():
        response = manager.client.get("/api/integrations?include_discovery=true", headers=scope_headers(pair))
        assert response.status_code == 200, response.text
        return {record["id"]: record for record in response.json()}

    [record] = projection().values()
    assert record["run"]["id"] == str(historic.id)
    assert record["continuation_run_id"] is None
    assert decide(manager, pair, state["version"], "completed", historic.id).status_code == 422

    live, [eligible, failed] = discovery_history(pair, status, "failed", name="B live")
    following, [fallback, archived] = discovery_history(pair, "completed", "completed", name="C live")
    with env.sessions.begin() as db:
        db.get(DiscoveryRun, archived.id).archived_at = datetime.now(timezone.utc)
    rows = projection()
    assert list(rows) == [str(item.id) for item in (retired, live, following)]
    assert rows[str(live.id)]["run"]["id"] == str(eligible.id if status in ("pending", "running") else failed.id)
    assert rows[str(live.id)]["continuation_run_id"] == str(eligible.id)
    assert rows[str(following.id)]["continuation_run_id"] == str(fallback.id)
    assert decide(manager, pair, state["version"], "completed", archived.id).status_code == 422
    assert all("continuation_run_id" not in row for row in manager.client.get(
        "/api/integrations", headers=scope_headers(pair),
    ).json())

    with env.sessions.begin() as db:
        db.get(Integration, live.id).retired_at = datetime.now(timezone.utc)
    assert decide(manager, pair, state["version"], "completed", eligible.id).status_code == 422
    rows = projection()
    assert rows[str(live.id)]["continuation_run_id"] is None
    assert rows[str(following.id)]["continuation_run_id"] == str(fallback.id)
    result = decide(second, pair, state["version"], "completed", fallback.id)
    assert result.status_code == 200, result.text
    assert result.json()["current_stage"] == "discovery_review"


def test_two_admins_share_one_winning_decision_and_revocation_is_enforced(env):
    pair = env.pair()
    first, second = (env.actor(ENTRY, "site", pair.customer.id, pair.site.id) for _ in range(2))
    revoked = env.actor(ENTRY, "site", pair.customer.id, pair.site.id)
    state = at_integrations(first, pair)
    assert revoked.client.get(pair.path).json()["can_manage"]
    with env.sessions.begin() as db:
        db.delete(db.get(AccessAssignment, revoked.grant))
    assert decide(revoked, pair, state["version"], "skipped").status_code in {403, 404}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(decide, actor, pair, state["version"], "skipped") for actor in (first, second)]
    assert sorted(future.result().status_code for future in futures) == [200, 409]
    with env.sessions() as db:
        events = db.scalars(select(AuditEvent).where(AuditEvent.site_id == pair.site.id,
            AuditEvent.event_type == "onboarding.integrations_skipped")).all()
        assert len(events) == 1
        assert events[0].user_id in {first.id, second.id}
