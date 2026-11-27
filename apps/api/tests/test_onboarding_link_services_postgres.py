"""E1-F through authenticated APIs with independent committed PostgreSQL reads."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier, Event
from time import monotonic, sleep
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import delete, select, text

from app.models import (
    AccessAssignment, Asset, AuditEvent, Base, CriticalityLevel, Customer, DataSource,
    KnowledgeAssertion, KnowledgeChange, KnowledgeGap, KnowledgeRequirementDefinition,
    RelationshipType, Service, ServiceAssetDependency, ServiceType, Site,
)
from app.routes import services as canonical
from app.services.knowledge_completeness import ACTIVE_GAP_STATUSES
from tests.test_onboarding_postgres import ENTRY, env, pytestmark

PERMISSIONS = ENTRY | {
    "assets.view", "assets.create", "assets.edit", "assets.delete", "services.view", "services.create",
    "services.archive", "services.edit", "service_dependencies.view", "service_dependencies.manage",
    "knowledge_gaps.view",
}


def ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json() if response.content else None


def reach_link_services(actor, pair):
    client, path = actor.client, pair.path
    state = ok(client.post(path + "/start"))
    state = ok(client.patch(path + "/environment", json={"version": state["version"], "environment_profile": "blank"}))
    state = ok(client.post(path + "/capabilities/skip", json={"version": state["version"]}))
    state = ok(client.post(path + "/integrations/decision", json={"version": state["version"], "decision": "skipped"}))
    return ok(client.post(path + "/discovery-review/decision", json={"version": state["version"], "decision": "skipped"}))


@pytest.fixture
def case(env):
    pair = env.pair()
    sibling = env.pair(customer=pair.customer)
    foreign = env.pair()
    actor = env.actor(PERMISSIONS)
    state = reach_link_services(actor, pair)

    with env.sessions() as db:
        type_id = str(db.scalar(select(ServiceType.id).where(ServiceType.key == "application_service")))
        criticality_id = str(db.scalar(select(CriticalityLevel.id).where(CriticalityLevel.key == "medium")))
        runs_on = str(db.scalar(select(RelationshipType.id).where(RelationshipType.key == "runs_on")))
        depends_on = db.scalar(select(RelationshipType.id).where(RelationshipType.key == "depends_on"))

    def asset(name, where=pair, kind="virtual_machine", *, hostname=None):
        return ok(actor.client.post("/api/assets", json={
            "name": name, "customer_id": str(where.customer.id), "site_id": str(where.site.id), "asset_type": kind,
            "hostname": hostname,
        }), 201)

    def service(name, where=pair, *, customer_wide=False):
        return ok(actor.client.post("/api/services", json={
            "name": name, "customer_id": str(where.customer.id), "site_id": None if customer_wide else str(where.site.id),
            "service_type_id": type_id, "criticality_level_id": criticality_id,
        }), 201)

    path = pair.path + "/link-services"
    member = lambda service: f"{path}/services/{service['id']}"
    add = lambda service, asset, who=actor: who.client.post(f"{member(service)}/assets/{asset['id']}")
    ordinary = lambda service, asset, who=actor, kind=runs_on: who.client.post(
        f"/api/services/{service['id']}/asset-dependencies", json={"asset_id": asset["id"], "relationship_type_id": str(kind)},
    )
    def remove(service, mapping_id, who=actor, *, version="0" * 64):
        return who.client.request("DELETE", f"{member(service)}/mappings/{mapping_id}",
                                  json={"removal_version": version})

    yield SimpleNamespace(
        env=env, pair=pair, sibling=sibling, foreign=foreign, actor=actor, state=state,
        asset=asset, service=service, client=actor.client, add=add, ordinary=ordinary,
        path=path, member=member, remove=remove, depends_on=depends_on,
    )

    with env.sessions.begin() as db:
        customer_ids = {pair.customer.id, foreign.customer.id}
        for table in reversed(Base.metadata.sorted_tables):
            if table not in {Site.__table__, Customer.__table__} and "customer_id" in table.c:
                db.execute(delete(table).where(table.c.customer_id.in_(customer_ids)))


def edges(case, service):
    with case.env.sessions() as db:
        return list(db.scalars(select(ServiceAssetDependency).where(ServiceAssetDependency.service_id == UUID(service["id"]))))


def gap_history(db, service, requirement):
    return {gap.id: gap for gap in db.scalars(select(KnowledgeGap).join(
        KnowledgeRequirementDefinition, KnowledgeGap.requirement_definition_id == KnowledgeRequirementDefinition.id,
    ).where(
        KnowledgeGap.entity_type == "service", KnowledgeGap.entity_id == UUID(service["id"]),
        KnowledgeRequirementDefinition.key == requirement,
    ))}


def active_gaps(history):
    return {gap_id: gap for gap_id, gap in history.items() if gap.status in ACTIVE_GAP_STATUSES}


def gap_lifecycle(gap):
    return (gap.status, gap.first_detected_at, gap.last_state_changed_at, gap.resolved_at, gap.resolved_by_user_id)


def shown_mapping(case, service, dependency_id):
    return next(item for item in ok(case.client.get(case.member(service)))["site_mappings"]
                if item["id"] == str(dependency_id))


def test_mapping_reads_writes_and_canonical_effects(case):
    wide = case.service("Alpha service", customer_wide=True)
    local = case.service("Beta service")
    unmapped = case.service("Gamma service")
    case.service("Sibling only", case.sibling)
    case.service("Foreign service", case.foreign)
    first = case.asset("Alpha Asset")
    second = case.asset("Beta Asset", kind="physical_server")
    third = case.asset("Gamma Asset")
    remote = case.asset("Sibling Asset", case.sibling)
    retired = case.asset("Retired Asset")
    sibling_edge = ok(case.ordinary(wide, remote), 201)
    existing = ok(case.ordinary(wide, first), 201)
    retired_edge = ok(case.ordinary(wide, retired), 201)
    with case.env.sessions() as db:
        original, = gap_history(db, local, "service_asset_dependency").values()
        purpose, = gap_history(db, local, "service_purpose").values()
        assert original.status == purpose.status == "open"
    ok(case.client.patch(f"/api/assets/{retired['id']}", json={"status": "retired"}))
    assert ok(case.client.get(case.path, params={"search": "Beta", "mapping": "unlinked", "limit": 1})) == {
        "summary": {"linked": 1, "unlinked": 2, "mappings": 2, "unavailable": 0}, "has_more": False,
        "services": [{
            "id": local["id"], "name": local["name"], "site_id": str(case.pair.site.id),
            "service_type_id": local["service_type_id"], "service_type_icon_key": local["service_type_icon_key"],
            "service_type_accent_key": local["service_type_accent_key"], "mapping_count": 0,
        }],
    }
    first_page = ok(case.client.get(case.path, params={"limit": 1}))
    assert first_page["has_more"] and first_page["services"][0]["id"] == wide["id"]
    assert [row["id"] for row in ok(case.client.get(case.path, params={"mapping": "linked"}))["services"]] == [wide["id"]]
    detail = ok(case.client.get(case.member(wide), params={"asset_type": "physical_server", "search": "Beta"}))
    assert {item["id"] for item in detail["site_mappings"]} == {existing["id"], retired_edge["id"]}
    assert next(item for item in detail["site_mappings"] if item["id"] == retired_edge["id"])["asset"]["status"] == "retired"
    assert [item["id"] for item in detail["other_mappings"]] == [sibling_edge["id"]]
    assert [item["id"] for item in detail["available"]] == [second["id"]]
    assert [item["id"] for item in ok(case.client.get(case.member(wide), params={"limit": 1, "offset": 1}))["available"]] == [third["id"]]
    assert ok(case.add(wide, first)) == {"outcome": "already_exists"}
    for service, asset in ((wide, second), (wide, third), (local, second)):
        assert ok(case.add(service, asset)) == {"outcome": "added"}

    local_edge, = edges(case, local)
    assert (local_edge.created_by_user_id, local_edge.asset_id, local_edge.relationship_type_id, local_edge.source) == (
        case.actor.id, UUID(second["id"]), case.depends_on, "manual",
    )
    assert local_edge.required_for_operation and local_edge.site_id == case.pair.site.id
    assert ok(case.client.get(case.path))["summary"] == {"linked": 2, "unlinked": 1, "mappings": 5, "unavailable": 0}
    assert ok(case.client.get(case.member(wide)))["available"] == []
    assert ok(case.client.get(f"/api/services/{local['id']}/asset-dependencies"))[0]["id"] == str(local_edge.id)
    assert ok(case.client.get(f"/api/services/{local['id']}"))["asset_dependency_count"] == 1
    assert str(local_edge.id) in str(ok(case.client.get(f"/api/services/{local['id']}/graph")))
    assert local["id"] in str(ok(case.client.get("/api/operational-graph", params={
        "focus_type": "asset", "focus_id": second["id"], "max_depth": 1,
    })))
    analysis = ok(case.client.post("/api/dependency-analysis", json={
        "focus_type": "asset", "focus_id": second["id"],
    }))
    assert next(row for row in analysis["results"] if row["service"]["entity_id"] == local["id"])["state"] == "unknown"

    with case.env.sessions() as db:
        assertion = db.scalar(select(KnowledgeAssertion).where(
            KnowledgeAssertion.subject_id == UUID(local["id"]), KnowledgeAssertion.object_id == UUID(second["id"]),
        ))
        assert assertion.is_accepted and assertion.accepted_by_user_id == case.actor.id
        assert assertion.predicate == "depends_on" and assertion.truth_classification == "declared"
        assert db.get(DataSource, assertion.data_source_id).source_type == "manual"
        history = gap_history(db, local, "service_asset_dependency")
        assert set(history) == {original.id} and active_gaps(history) == {}
        resolved = history[original.id]
        assert resolved.status == "resolved" and resolved.resolved_at is not None
        assert resolved.first_detected_at == original.first_detected_at
        purpose_history = gap_history(db, local, "service_purpose")
        assert set(purpose_history) == {purpose.id}
        assert gap_lifecycle(purpose_history[purpose.id]) == gap_lifecycle(purpose)
        unmet, = active_gaps(gap_history(db, unmapped, "service_asset_dependency")).values()
        assert unmet.status == "open"

    assert case.remove(wide, sibling_edge["id"]).status_code == 409
    assert case.remove(wide, local_edge.id).status_code == 404
    reviewed = shown_mapping(case, local, local_edge.id)
    ok(case.remove(local, local_edge.id, version=reviewed["removal_version"]), 204)
    assert ok(case.client.get(f"/api/services/{local['id']}/asset-dependencies")) == []
    assert len(edges(case, wide)) == 5 and all(edge.valid_to is None for edge in edges(case, wide))
    ended, = edges(case, local)
    assert ended.valid_to and ended.ended_by_user_id == case.actor.id
    with case.env.sessions() as db:
        assertion = db.get(KnowledgeAssertion, assertion.id)
        assert assertion.retracted_at and assertion.valid_to
        actions = set(db.execute(select(AuditEvent.event_type, AuditEvent.user_id).where(AuditEvent.target_id == ended.id)))
        assert actions == {("service_asset_dependency.created", case.actor.id), ("service_asset_dependency.ended", case.actor.id)}
        changes = set(db.execute(select(KnowledgeChange.change_type, KnowledgeChange.actor_user_id).where(
            KnowledgeChange.entity_id == UUID(local["id"]), KnowledgeChange.change_type.in_(
                ("service_dependency_added", "service_dependency_removed"),
            ),
        )))
        assert changes == {("service_dependency_added", case.actor.id), ("service_dependency_removed", case.actor.id)}
        history = gap_history(db, local, "service_asset_dependency")
        successor, = active_gaps(history).values()
        assert set(history) == {original.id, successor.id} and successor.id != original.id
        assert successor.status == "open" and successor.resolved_at is None
        assert successor.first_detected_at >= resolved.resolved_at
        assert gap_lifecycle(history[original.id]) == gap_lifecycle(resolved)
        purpose_history = gap_history(db, local, "service_purpose")
        assert set(purpose_history) == {purpose.id}
        assert gap_lifecycle(purpose_history[purpose.id]) == gap_lifecycle(purpose)
        assert db.get(Asset, UUID(second["id"])).status != "retired"


def test_asset_identity_is_scoped_and_stable_across_pages_and_linking(case):
    service = case.service("Service")
    hosted = [case.asset("Duplicate", hostname=hostname) for hostname in ("primary.lab", "standby.lab")]
    blank = [case.asset("Missing hostname", hostname=hostname)
             for hostname in (None, "", " ", "\t", "\r\n\u00a0\u2003")]
    identical = [case.asset("Same hostname", hostname="shared.lab") for _ in range(2)]
    unique = case.asset("Unique", hostname=" \tunique.lab\u2003")
    sibling = case.asset("Unique", case.sibling, hostname="unique.lab")
    foreign = case.asset("Unique", case.foreign, hostname="unique.lab")
    expected_hostnames = {
        hosted[0]["id"]: "primary.lab", hosted[1]["id"]: "standby.lab",
        **{asset["id"]: None for asset in blank},
        **{asset["id"]: "shared.lab" for asset in identical},
        unique["id"]: "unique.lab",
    }
    shown = {}
    for offset in range(len(expected_hostnames)):
        row, = ok(case.client.get(case.member(service), params={"limit": 1, "offset": offset}))["available"]
        shown[row["id"]] = row
    assert {asset_id: row["hostname"] for asset_id, row in shown.items()} == expected_hostnames
    assert {row["type_name"] for row in shown.values()} == {"Virtual Machine"}

    unique_page = ok(case.client.get(case.member(service), params={"search": "Unique", "asset_type": "virtual_machine"}))
    assert unique_page["available"] == [shown[unique["id"]]]
    assert all(asset["id"] not in str(unique_page) for asset in (sibling, foreign))

    selected = [blank[3], identical[1]]
    for asset in selected:
        assert ok(case.add(service, asset)) == {"outcome": "added"}
    committed = edges(case, service)
    assert {str(edge.asset_id) for edge in committed} == {asset["id"] for asset in selected}
    for edge in committed:
        assert shown_mapping(case, service, edge.id)["asset"] == shown[str(edge.asset_id)]
    remaining = ok(case.client.get(case.member(service), params={"search": "Missing hostname"}))["available"]
    assert {row["id"] for row in remaining} == {asset["id"] for asset in blank if asset != selected[0]}


def test_scoped_permissions_and_inaccessible_relationships(case):
    pair, env = case.pair, case.env
    wide = case.service("Customer Service", customer_wide=True)
    local = case.service("Site Service")
    remote_service = case.service("Outside Service", case.sibling)
    asset = case.asset("Available")
    remote = case.asset("Other Site Asset", case.sibling)
    foreign = case.asset("Other Customer Asset", case.foreign)
    other_mapping = ok(case.ordinary(wide, remote), 201)
    scoped = env.actor(PERMISSIONS, "site", pair.customer.id, pair.site.id)
    customer = env.actor(PERMISSIONS, "customer", pair.customer.id)
    workflow_only = env.actor(ENTRY, "site", pair.customer.id, pair.site.id)
    read_only = env.actor(PERMISSIONS - {"service_dependencies.manage"}, "customer", pair.customer.id)
    mapping_hidden = env.actor(PERMISSIONS - {"service_dependencies.view"}, "customer", pair.customer.id)
    assert ok(workflow_only.client.get(case.path)) == {"services": [], "summary": None, "has_more": False}
    assert case.add(local, asset, workflow_only).status_code == 404
    page = ok(scoped.client.get(case.path))
    assert [row["id"] for row in page["services"]] == [local["id"]]
    assert page["summary"] == {"linked": 0, "unlinked": 1, "mappings": 0, "unavailable": 0}
    assert case.add(wide, asset, scoped).status_code == 404
    assert case.add(local, remote, scoped).status_code == 404
    assert case.add(wide, foreign, customer).status_code == 404
    assert case.add(wide, remote, customer).status_code == 409
    assert case.add(remote_service, asset, customer).status_code == 409
    assert case.add(local, asset, read_only).status_code == 403
    assert ok(case.add(local, asset, scoped)) == {"outcome": "added"}
    assert ok(case.add(wide, asset, customer)) == {"outcome": "added"}
    editor = ok(read_only.client.get(case.member(wide)))
    assert not editor["can_manage"] and editor["available"] is None
    assert [item["asset"]["id"] for item in editor["other_mappings"]] == [remote["id"]]
    assert editor["other_mappings"][0]["removal_version"] is None
    assert all(item["removal_version"] is None for item in editor["site_mappings"])
    no_site_view = env.actor(PERMISSIONS - {"sites.view", "sites.manage"}, "customer", pair.customer.id)
    with env.sessions.begin() as db:
        grant = db.get(AccessAssignment, scoped.grant)
        db.add(AccessAssignment(user_id=no_site_view.id, role_id=grant.role_id, scope_type="site",
            customer_id=pair.customer.id, site_id=pair.site.id))
    constrained = ok(no_site_view.client.get(case.member(wide)))
    assert constrained["other_mappings"] == [] and remote["id"] not in str(constrained)
    assert case.remove(wide, other_mapping["id"], no_site_view).status_code == 404
    assert case.add(wide, remote, no_site_view).status_code == 404
    assert ok(customer.client.get(case.path, headers={
        "X-Atlas-Customer-ID": str(case.foreign.customer.id), "X-Atlas-Site-ID": str(case.foreign.site.id),
    }))["summary"]["linked"] == 2
    hidden = ok(mapping_hidden.client.get(case.path))
    assert hidden["summary"] == {"linked": 0, "unlinked": 0, "mappings": 0, "unavailable": 2}
    assert all(item["mapping_count"] is None for item in hidden["services"])


def test_resume_attention_skip_revisit_and_conflicts(case):
    service, asset = case.service("Mapped"), case.asset("Asset")
    case.service("Unmapped")
    add_result = ok(case.add(service, asset))
    assert add_result["outcome"] == "added"
    version = case.state["version"]
    saved = ok(case.client.post(case.pair.path + "/save", json={"version": version}))
    assert saved["status"] == "saved"
    assert case.add(service, asset).status_code == 409
    resumed = ok(case.client.post(case.pair.path + "/resume", json={"version": saved["version"]}))
    decision = case.path + "/decision"
    assert case.client.post(decision, json={"version": version, "action": "skip"}).status_code == 409
    assert case.client.post(decision, json={"version": resumed["version"], "action": "continue"}).json()["detail"]["code"] == "link_services_attention"
    continued = ok(case.client.post(decision, json={
        "version": resumed["version"], "action": "continue", "acknowledge_attention": True,
    }))
    assert continued["stage_decisions"]["link_services"] == "attention"
    assert continued["current_stage"] == "review_ready" and "review_ready" not in continued["stage_decisions"]
    assert len(ok(case.client.get(case.member(service)))["site_mappings"]) == 1
    assert ok(case.add(service, asset)) == {"outcome": "already_exists"}
    assert ok(case.client.get(case.pair.path))["progress"] == continued
    empty = reach_link_services(case.actor, case.foreign)
    assert ok(case.client.get(case.foreign.path + "/link-services"))["services"] == []
    skipped = ok(case.client.post(case.foreign.path + "/link-services/decision",
        json={"version": empty["version"], "action": "skip"}))
    assert skipped["stage_decisions"]["link_services"] == "skipped"
    assert skipped["current_stage"] == "review_ready"
    complete = reach_link_services(case.actor, case.sibling)
    result = ok(case.client.post(case.sibling.path + "/link-services/decision",
        json={"version": complete["version"], "action": "continue"}))
    assert result["stage_decisions"]["link_services"] == "completed"


def wait_for_database_lock(db, blocker):
    deadline = monotonic() + 5
    while monotonic() < deadline:
        db.execute(text("SELECT pg_stat_clear_snapshot()"))
        if db.scalar(text(
            "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE :blocker = ANY(pg_blocking_pids(pid)))"
        ), {"blocker": blocker}):
            return
        sleep(0.02)
    pytest.fail("The mapping request did not wait for the canonical lock")


def test_competing_onboarding_creates_commit_one_relationship(case):
    service, asset = case.service("Shared Service", customer_wide=True), case.asset("Provider")
    other = case.env.actor(PERMISSIONS)
    gate = Barrier(2)

    def submit(actor):
        gate.wait(timeout=5)
        return ok(case.add(service, asset, actor))["outcome"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        one, two = [pool.submit(submit, actor) for actor in (case.actor, other)]
        outcomes = [one.result(timeout=12), two.result(timeout=12)]
    assert set(outcomes) == {"added", "already_exists"}
    row, = edges(case, service)
    assert row.created_by_user_id == [case.actor.id, other.id][outcomes.index("added")]


@pytest.mark.parametrize(("change", "expected"), [
    ("retire_asset", 409), ("move_asset", 409), ("delete_asset", 404),
    ("move_service", 409), ("delete_service", 404), ("revoke", 404),
])
def test_submission_rechecks_locked_live_endpoints_and_permissions(case, change, expected):
    service, asset = case.service("Site Service"), case.asset("Provider")
    actor = case.env.actor(PERMISSIONS, "customer", case.pair.customer.id)
    assert ok(actor.client.get(case.member(service)))["available"][0]["id"] == asset["id"]

    with ThreadPoolExecutor(max_workers=1) as pool:
        with case.env.sessions.begin() as writer, case.env.sessions() as monitor:
            blocker = writer.scalar(text("SELECT pg_backend_pid()"))
            if change.endswith("service"):
                target = writer.get(Service, UUID(service["id"]), with_for_update=True)
            else:
                target = writer.get(Asset, UUID(asset["id"]), with_for_update=True)
            request = pool.submit(case.add, service, asset, actor)
            wait_for_database_lock(monitor, blocker)
            if change == "retire_asset":
                target.status = "retired"
            elif change.startswith("move"):
                target.site_id = case.sibling.site.id
            elif change == "delete_asset":
                writer.delete(target)
            elif change == "delete_service":
                target.deleted_at = datetime.now(timezone.utc)
            else:
                writer.execute(delete(AccessAssignment).where(AccessAssignment.id == actor.grant))
        assert request.result(timeout=12).status_code == expected
    assert edges(case, service) == []


def test_permission_revoked_after_staging_rolls_back_canonical_side_effects(case, monkeypatch):
    service, asset = case.service("Site Service"), case.asset("Provider")
    actor = case.env.actor(PERMISSIONS, "customer", case.pair.customer.id)
    add = canonical.add_asset_dependency

    def revoke_after_add(*args):
        result = add(*args)
        with case.env.sessions.begin() as writer:
            writer.execute(delete(AccessAssignment).where(AccessAssignment.id == actor.grant))
        return result

    monkeypatch.setattr(canonical, "add_asset_dependency", revoke_after_add)
    assert case.add(service, asset, actor).status_code == 404
    assert edges(case, service) == []
    with case.env.sessions() as db:
        assert db.scalar(select(KnowledgeAssertion.id).where(KnowledgeAssertion.object_id == UUID(asset["id"]))) is None
        assert db.scalar(select(AuditEvent.id).where(AuditEvent.event_type == "service_asset_dependency.created",
            AuditEvent.user_id == actor.id)) is None
        gap, = gap_history(db, service, "service_asset_dependency").values()
        assert gap.status == "open"


def test_removal_waits_for_competing_canonical_removal(case, monkeypatch):
    service, asset = case.service("Site Service"), case.asset("Provider")
    edge = ok(case.ordinary(service, asset), 201)
    reviewed = shown_mapping(case, service, edge["id"])
    other = case.env.actor(PERMISSIONS)
    staged, release = Event(), Event()
    lock = {}
    end = canonical.end_asset_dependency

    def delay_end(db, *args):
        end(db, *args)
        lock["pid"] = db.scalar(text("SELECT pg_backend_pid()"))
        staged.set()
        assert release.wait(8)

    monkeypatch.setattr(canonical, "end_asset_dependency", delay_end)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(other.client.delete, f"/api/service-asset-dependencies/{edge['id']}")
        try:
            assert staged.wait(5)
            second = pool.submit(case.remove, service, edge["id"], version=reviewed["removal_version"])
            with case.env.sessions() as monitor:
                wait_for_database_lock(monitor, lock["pid"])
        finally:
            release.set()
        assert first.result(timeout=10).status_code == 204
        assert second.result(timeout=10).status_code == 404
    ended, = edges(case, service)
    assert ended.valid_to and ended.ended_by_user_id == other.id


def test_removal_rejects_type_changed_while_waiting_for_canonical_locks(case, monkeypatch):
    service, asset = case.service("Site Service"), case.asset("Provider")
    edge = ok(case.ordinary(service, asset), 201)
    reviewed = shown_mapping(case, service, edge["id"])
    assert reviewed["relationship_name"] == "Runs on"
    other = case.env.actor(PERMISSIONS)
    staged, release = Event(), Event()
    lock = {}
    commit = canonical.commit

    def snapshot(db):
        return [
            db.execute(select(model.__table__).where(
                model.customer_id == case.pair.customer.id,
            ).order_by(model.id)).all()
            for model in (ServiceAssetDependency, KnowledgeAssertion, KnowledgeChange, AuditEvent)
        ]

    def delay_commit(db, resource):
        lock["pid"] = db.scalar(text("SELECT pg_backend_pid()"))
        lock["changed"] = snapshot(db)
        staged.set()
        assert release.wait(8)
        commit(db, resource)

    monkeypatch.setattr(canonical, "commit", delay_commit)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(other.client.patch, f"/api/service-asset-dependencies/{edge['id']}",
                            json={"relationship_type_id": str(case.depends_on)})
        try:
            assert staged.wait(5)
            second = pool.submit(case.remove, service, edge["id"], version=reviewed["removal_version"])
            with case.env.sessions() as monitor:
                wait_for_database_lock(monitor, lock["pid"])
        finally:
            release.set()
        assert ok(first.result(timeout=10))["relationship_type_name"] == "Depends on"
        rejected = ok(second.result(timeout=10), 409)
    assert rejected["detail"]["code"] == "link_mapping_changed"
    with case.env.sessions() as db:
        assert snapshot(db) == lock["changed"]
        current = db.get(ServiceAssetDependency, UUID(edge["id"]))
        assert current.relationship_type_id == case.depends_on and current.valid_to is None
    assert case.client.delete(f"{case.member(service)}/mappings/{edge['id']}").status_code == 422
    refreshed = shown_mapping(case, service, edge["id"])
    assert refreshed["relationship_name"] == "Depends on"
    assert refreshed["removal_version"] != reviewed["removal_version"]
    ok(case.remove(service, edge["id"], version=refreshed["removal_version"]), 204)
    ended, = edges(case, service)
    assert ended.valid_to and ended.ended_by_user_id == case.actor.id


def test_competing_ordinary_relationship_is_recognized_after_lock_wait(case, monkeypatch):
    service, asset = case.service("Shared Service", customer_wide=True), case.asset("Provider")
    admin = case.env.actor(PERMISSIONS)
    staged, release = Event(), Event()
    lock = {}
    add = canonical.add_asset_dependency

    def delay_add(db, *args):
        result = add(db, *args)
        lock["pid"] = db.scalar(text("SELECT pg_backend_pid()"))
        staged.set()
        assert release.wait(8)
        return result

    monkeypatch.setattr(canonical, "add_asset_dependency", delay_add)
    with ThreadPoolExecutor(max_workers=2) as pool:
        ordinary = pool.submit(case.ordinary, service, asset, admin)
        try:
            assert staged.wait(5)
            wizard = pool.submit(case.add, service, asset)
            with case.env.sessions() as monitor:
                wait_for_database_lock(monitor, lock["pid"])
        finally:
            release.set()
        saved = ok(ordinary.result(timeout=10), 201)
        assert ok(wizard.result(timeout=10)) == {"outcome": "already_exists"}
    row, = edges(case, service)
    assert str(row.id) == saved["id"] and row.created_by_user_id == admin.id


def test_reads_and_writes_require_preview_and_link_stage(case, monkeypatch):
    service, asset = case.service("Site Service"), case.asset("Provider")
    client = case.client
    assert client.get(case.sibling.path + "/link-services").status_code == 404
    started = ok(client.post(case.sibling.path + "/start"))
    ok(client.patch(case.sibling.path + "/environment", json={"version": started["version"], "environment_profile": "blank"}))
    assert client.get(case.sibling.path + "/link-services").status_code == 404
    monkeypatch.delenv("ATLAS_ONBOARDING_PREVIEW")
    assert client.get(case.path).status_code == 404
    assert client.get(case.member(service)).status_code == 404
    assert case.add(service, asset).status_code == 404
    assert client.post(case.path + "/decision", json={"version": case.state["version"], "action": "skip"}).status_code == 404
    assert edges(case, service) == []
