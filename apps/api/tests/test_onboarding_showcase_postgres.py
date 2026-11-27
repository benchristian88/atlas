"""E1-H read and completion contracts through authenticated APIs on PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Event
from uuid import UUID

import pytest
from sqlalchemy import delete, insert, select

from app.models import (
    AccessAssignment, Asset, AssetInterface, AssetRelationship, AuditEvent, BusinessFunction, DiscoveryRun,
    InstallationState, Integration, KnowledgeAssertion, KnowledgeChange, KnowledgeGap, Network,
    ReconciliationItem, Service, ServiceAssetDependency, ServiceBusinessFunction, Site,
)
from app.services import onboarding, onboarding_showcase, operational_graph
from tests.test_onboarding_capabilities_postgres import ALL as CAPABILITIES, apply, put, subset
from tests.test_onboarding_integrations_postgres import at_integrations, discovery_history, scope_headers
from tests.test_onboarding_link_services_postgres import case, ok, reach_link_services
from tests.test_onboarding_postgres import ENTRY, INVITATION, env, pytestmark
from tests.test_onboarding_review_postgres import READ, advance, continue_to_showcase

ALL = READ | {"networks.view", "relationships.view"}


def finish(actor, pair, version):
    return actor.client.post(pair.path + "/complete", json={"version": version})


def read(actor, pair, **options):
    return ok(actor.client.get(pair.path + "/showcase", **options))


def ready(actor, pair, state):
    review = advance(actor, pair, state)
    return ok(continue_to_showcase(actor, pair, review["version"]))


def test_showcase_function_associations_follow_graph_effective_time(case, monkeypatch):
    env, pair = case.env, case.pair
    actor = env.actor(ALL)
    local = env.actor(ALL, "site", pair.customer.id, pair.site.id)
    ready(actor, pair, case.state)
    instant = datetime.now(timezone.utc).replace(microsecond=0)

    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    monkeypatch.setattr(operational_graph, "datetime", FixedClock)
    # Freeze both projections when Showcase has an explicit effective time.
    monkeypatch.setattr(onboarding_showcase, "datetime", FixedClock, raising=False)
    day = timedelta(days=1)
    visible = {
        "A open": (instant - day, None),
        "B starts now": (instant, None),
        "C ends later": (instant - day, instant + day),
        "D another current": (instant - day, None),
        "E another current": (instant - day, None),
        "00 starts later": (instant + 60 * day, None),
        "G ends now": (instant - day, instant),
        "H expired": (instant - 2 * day, instant - day),
    }
    services = {name: UUID(case.service(name)["id"]) for name in visible}
    wide = UUID(case.service("Z Customer-wide", customer_wide=True)["id"])
    sibling = UUID(case.service("Sibling", case.sibling)["id"])
    foreign = UUID(case.service("Foreign", case.foreign)["id"])
    with env.sessions.begin() as db:
        function = BusinessFunction(name="Site Function", customer_id=pair.customer.id, site_id=pair.site.id)
        db.add(function)
        db.flush()
        function_id = function.id

        def association(service_id, start, end, *, owner=pair):
            return ServiceBusinessFunction(
                customer_id=owner.customer.id, site_id=owner.site.id if service_id != wide else None,
                service_id=service_id, business_function_id=function_id, valid_from=start, valid_to=end,
            )

        db.add_all([association(services[name], *window) for name, window in visible.items()])
        # History and an overlapping bounded version may coexist with an open row.
        # Count the associated Service once, even if two rows describe the same pair.
        db.add(association(services["A open"], instant - 2 * day, instant - day))
        db.add(association(services["A open"], instant - day, instant + day))
        db.add(association(wide, instant - day, None))
        db.add(association(sibling, instant - day, None, owner=case.sibling))
        db.add(association(foreign, instant - day, None, owner=case.foreign))

    def association_rows():
        table = ServiceBusinessFunction.__table__
        with env.sessions() as db:
            return db.execute(select(table).where(table.c.business_function_id == function_id)
                              .order_by(table.c.id)).all()

    before = association_rows()
    for viewer, expected, service_total in (
        (actor, {"A open", "B starts now", "C ends later", "D another current", "E another current", "Z Customer-wide"}, 9),
        (local, {"A open", "B starts now", "C ends later", "D another current", "E another current"}, 8),
    ):
        graph = ok(viewer.client.get("/api/operational-graph", headers=scope_headers(pair), params={
            "focus_type": "business_function", "focus_id": str(function_id),
            "max_depth": 1, "edge_family": "service_business_function", "site_viewpoint": "true",
        }))
        graph_services = {node["name"] for node in graph["nodes"] if node["entity_type"] == "service"}
        assert graph_services == expected
        result = read(viewer, pair)
        item, = result["business_functions"]["items"]
        assert result["services"] == service_total
        assert [example["name"] for example in item["services"]["examples"]] == sorted(graph_services)[:4]
        assert item["services"]["total"] == len(graph_services)
        assert item["services"]["total"] - len(item["services"]["examples"]) == len(graph_services) - 4
        assert result["services_without_functions"] == 3
    assert association_rows() == before


def test_showcase_projection_matches_canonical_scope_and_permissions(case, discovery_history):
    env, pair = case.env, case.pair
    actor = env.actor(ALL)
    local = env.actor(ALL, "site", pair.customer.id, pair.site.id)
    manager = env.actor(ENTRY, "site", pair.customer.id, pair.site.id)
    relationships_only = env.actor(ENTRY | {"relationships.view", "networks.view"}, "site", pair.customer.id, pair.site.id)
    functions_only = env.actor(ENTRY | {"business_functions.view"}, "site", pair.customer.id, pair.site.id)
    scoped_relationships = env.actor(ENTRY | {"assets.view", "service_dependencies.view"}, "site", pair.customer.id, pair.site.id)
    customer_services = env.actor({"services.view"}, "customer", pair.customer.id)
    with env.sessions.begin() as db:
        db.add(AccessAssignment(user_id=scoped_relationships.id, role_id=db.get(AccessAssignment, customer_services.grant).role_id,
                                scope_type="customer", customer_id=pair.customer.id))
    assert actor.client.get(pair.path + "/showcase").status_code == 404
    assert finish(actor, pair, case.state["version"]).status_code == 409
    state = ready(actor, pair, case.state)
    empty = read(actor, pair)
    assert empty["business_functions"] == {"total": 0, "items": []}
    assert empty["assets"] == {"total": 0, "by_type": [], "other_assets": 0}
    assert empty["services"] == empty["networks"] == empty["required_gaps"] == 0
    assert empty["services_without_functions"] == 0
    assert empty["mappings"] == dict(linked=0, unlinked=0, mappings=0, unavailable=0)
    assert all(value is None for value in read(manager, pair).values())

    wide = case.service("Customer Service", customer_wide=True)
    site = case.service("Site Service")
    unmapped = case.service("Unmapped Service")
    archived = case.service("Archived Service")
    case.service("Sibling Service", case.sibling)
    case.service("Foreign Service", case.foreign)
    ok(case.client.post(f"/api/services/{archived['id']}/archive", json={}))
    a = case.asset("Provider")
    b = case.asset("Host", kind="physical_server")
    retired = case.asset("Retired")
    sibling_asset = case.asset("Sibling Asset", case.sibling)
    case.asset("Foreign Asset", case.foreign)
    ok(case.ordinary(wide, sibling_asset), 201)
    ok(case.ordinary(wide, a), 201)
    ok(case.ordinary(site, retired), 201)
    history = ok(case.ordinary(unmapped, b), 201)
    ok(case.client.patch(f"/api/assets/{retired['id']}", json={"status": "retired"}))
    with env.sessions.begin() as db:
        db.get(ServiceAssetDependency, UUID(history["id"])).valid_to = datetime.now(timezone.utc)
        function = BusinessFunction(name="Customer Operations", customer_id=pair.customer.id)
        site_function = BusinessFunction(name="Site Operations", customer_id=pair.customer.id, site_id=pair.site.id)
        network = Network(customer_id=pair.customer.id, name="Shared Network", network_type="lan")
        site_network = Network(customer_id=pair.customer.id, site_id=pair.site.id, name="Site Network", network_type="lan")
        remote_network = Network(customer_id=pair.customer.id, site_id=case.sibling.site.id, name="Sibling Network", network_type="lan")
        db.add_all([function, site_function, network, site_network, remote_network,
                    BusinessFunction(name="Archived Function", customer_id=pair.customer.id, active=False),
                    BusinessFunction(name="Sibling Function", customer_id=pair.customer.id, site_id=case.sibling.site.id),
                    BusinessFunction(name="Foreign Function", customer_id=case.foreign.customer.id)])
        db.flush()
        for service, target, owner, valid_to in (
            (wide, function, None, None),
            (site, function, pair.site.id, None),
            (site, site_function, pair.site.id, None),
            (unmapped, site_function, pair.site.id, datetime.now(timezone.utc)),
        ):
            db.add(ServiceBusinessFunction(service_id=UUID(service["id"]), business_function_id=target.id,
                                           customer_id=pair.customer.id, site_id=owner, valid_to=valid_to))
        for target in (b, retired, sibling_asset):
            db.add(AssetRelationship(source_asset_id=UUID(a["id"]), target_asset_id=UUID(target["id"]),
                                     customer_id=pair.customer.id, site_id=pair.site.id, relationship_type="depends_on",
                                     legacy_cross_context=target == sibling_asset))
        for index, provider, assigned in ((1, a, network), (2, b, site_network), (3, retired, site_network)):
            db.add(AssetInterface(asset_id=UUID(provider["id"]), network_id=assigned.id, name=f"Interface {index}"))

    discovery_history(pair, "running")
    disabled, _ = discovery_history(pair, "completed")
    withdrawn, _ = discovery_history(pair, "pending")
    discovery_history(case.sibling, "running")
    with env.sessions.begin() as db:
        db.get(Integration, disabled.id).enabled = False
        db.get(Integration, withdrawn.id).retired_at = datetime.now(timezone.utc)

    response = actor.client.get(pair.path + "/showcase", headers=scope_headers(case.foreign))
    result = ok(response)
    assert response.headers["cache-control"] == "no-store"
    assert result["services"] == 3
    assert result["services_without_functions"] == 1
    assert result["business_functions"]["total"] == 2
    groups = result["business_functions"]["items"]
    assert [item["name"] for item in groups] == ["Customer Operations", "Site Operations"]
    assert [[item["name"] for item in group["services"]["examples"]] for group in groups] == [
        ["Customer Service", "Site Service"], ["Site Service"],
    ]
    dashboard = ok(actor.client.get("/api/dashboard/summary?include_customer_wide=true", headers=scope_headers(pair)))
    assert result["assets"]["total"] == dashboard["non_retired_assets"] == 2
    assert {row["count"] for row in result["assets"]["by_type"]} == {1}
    assert result["networks"] == 2 and result["network_memberships"] == 2 and result["asset_relationships"] == 1
    assert result["integrations"] == dict(total=2, enabled=1, disabled=1, active_runs=1)
    assert set(result["integrations"]) == {"total", "enabled", "disabled", "active_runs"}
    assert result["mappings"] == dict(linked=2, unlinked=1, mappings=2, unavailable=0)
    assert result["required_gaps"] == dashboard["open_knowledge_gap_count"] > 0
    partial = read(local, pair)
    assert partial["business_functions"]["total"] == 1
    assert (partial["services"], partial["networks"], partial["network_memberships"]) == (2, 1, 1)
    assert partial["mappings"] == dict(linked=1, unlinked=1, mappings=1, unavailable=0)
    assert read(scoped_relationships, pair)["mappings"] == dict(linked=1, unlinked=1, mappings=1, unavailable=1)
    limits = read(relationships_only, pair)
    assert limits["assets"] is limits["asset_relationships"] is limits["mappings"] is limits["network_memberships"] is None
    assert read(functions_only, pair)["business_functions"]["items"][0]["services"] is None
    assert read(scoped_relationships, pair)["services_without_functions"] is None
    assert actor.client.get(f"/api/onboarding/{case.foreign.customer.id}/{pair.site.id}/showcase").status_code == 404
    assert local.client.get(case.sibling.path + "/showcase").status_code == 404
    assert ok(actor.client.get(pair.path))["progress"] == state


def test_complete_serializes_audits_once_and_preserves_domain_state(case, discovery_history, monkeypatch):
    env, pair = case.env, case.pair
    actor = env.actor(ALL)
    second = env.actor(ENTRY, "site", pair.customer.id, pair.site.id)
    viewer = env.actor(ENTRY - {"sites.manage"}, "site", pair.customer.id, pair.site.id)
    state = ready(actor, pair, case.state)
    service = case.service("Still unmapped")
    provider = case.asset("Manual provider")
    discovery_history(pair, "running")
    tables = (Asset, BusinessFunction, Service, ServiceAssetDependency, Integration, DiscoveryRun,
              ReconciliationItem, KnowledgeAssertion, KnowledgeChange, KnowledgeGap)

    def snapshot():
        with env.sessions() as db:
            return [db.execute(select(*model.__table__.c).where(
                model.customer_id == pair.customer.id,
            ).order_by(model.id)).all() for model in tables]

    before = snapshot()
    assert read(actor, pair)["mappings"]["unlinked"] == 1
    assert finish(viewer, pair, state["version"]).status_code == 404
    assert finish(actor, pair, state["version"] - 1).status_code == 409
    assert finish(actor, case.sibling, state["version"]).status_code == 404

    saved = ok(actor.client.post(pair.path + "/save", json={"version": state["version"]}))
    assert saved["status"] == "saved" and saved["completed_at"] is None
    assert finish(actor, pair, saved["version"]).status_code == 409
    state = ok(actor.client.post(pair.path + "/resume", json={"version": saved["version"]}))
    start = Barrier(2)

    def complete(user):
        start.wait(timeout=5)
        return finish(user, pair, state["version"])

    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(complete, (actor, second)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = (actor, second)[next(i for i, response in enumerate(responses) if response.status_code == 200)]
    completed = next(response.json() for response in responses if response.status_code == 200)
    assert completed["completed_at"] == completed["updated_at"]
    assert completed["status"] == "completed" and completed["version"] == state["version"] + 1
    assert completed["stage_decisions"] == {**state["stage_decisions"], "showcase": "completed"}
    assert finish(actor, pair, completed["version"]).status_code == 409
    for endpoint in ("save", "resume"):
        assert actor.client.post(f"{pair.path}/{endpoint}", json={"version": completed["version"]}).status_code == 409
    assert ok(actor.client.post(pair.path + "/start")) == completed
    assert ok(actor.client.get(pair.path))["progress"] == completed
    assert not ok(actor.client.get(pair.path))["invitation"]["offered"]
    assert ok(actor.client.get(pair.path + "/review-ready"))["link_services"]["unlinked"] == 1
    assert read(actor, pair)["mappings"]["unlinked"] == 1
    assert snapshot() == before

    with env.sessions.begin() as db:
        marker = db.get(InstallationState, 1)
        marker.onboarding_customer_id, marker.onboarding_site_id = pair.customer.id, case.sibling.site.id
        persisted = onboarding.progress(db, pair.site)
        event, = db.scalars(select(AuditEvent).where(AuditEvent.site_id == pair.site.id,
                                                    AuditEvent.event_type == "onboarding.completed")).all()
        assert persisted.last_actor_id == event.user_id == winner.id
        assert persisted.completed_at.isoformat().replace("+00:00", "Z") == completed["completed_at"]
        assert event.metadata_ == {"version": completed["version"]}
    admin = env.actor(ALL | INVITATION)
    assert ok(admin.client.get(case.sibling.path))["invitation"]["offered"]
    assert any(site["id"] == str(pair.site.id) and site["status"] == "completed"
               for site in ok(actor.client.get("/api/onboarding/contexts"))["sites"])

    # An explicit revisit can address a skipped stage without changing guided setup history.
    assert ok(case.add(service, provider)) == {"outcome": "added"}
    assert read(actor, pair)["mappings"]["linked"] == 1
    assert ok(actor.client.get(pair.path))["progress"] == completed
    monkeypatch.delenv("ATLAS_ONBOARDING_PREVIEW")
    assert actor.client.get(pair.path + "/showcase").status_code == 404
    assert finish(actor, pair, completed["version"]).status_code == 404


@pytest.mark.parametrize("checkpoint", ["site", "workflow"])
def test_completion_refreshes_grants_after_locks(env, monkeypatch, checkpoint):
    pair = env.pair()
    actor = env.actor(ENTRY, "site", pair.customer.id, pair.site.id)
    state = ready(actor, pair, reach_link_services(actor, pair))
    attempting_lock = Event()
    original_progress = onboarding.progress
    original_site = onboarding.scoped_site

    def signal_lock(db, site, *, lock=False):
        if lock:
            attempting_lock.set()
        return original_progress(db, site, lock=lock)

    def signal_site(db, principal, customer_id, site_id, **options):
        if options.get("lock"):
            attempting_lock.set()
        return original_site(db, principal, customer_id, site_id, **options)

    if checkpoint == "site":
        monkeypatch.setattr(onboarding, "scoped_site", signal_site)
    else:
        monkeypatch.setattr(onboarding, "progress", signal_lock)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with env.sessions.begin() as db:
            if checkpoint == "site":
                db.scalar(select(Site).where(Site.id == pair.site.id).with_for_update())
            else:
                original_progress(db, pair.site, lock=True)
            future = pool.submit(finish, actor, pair, state["version"])
            assert attempting_lock.wait(timeout=5)
            db.execute(delete(AccessAssignment).where(AccessAssignment.id == actor.grant))
        assert future.result(timeout=5).status_code == 404
    with env.sessions() as db:
        assert original_progress(db, pair.site).version == state["version"]
        assert original_progress(db, pair.site).completed_at is None


def test_showcase_counts_are_exact_beyond_ordinary_list_limits(case):
    actor = case.env.actor(ALL)
    pair = case.pair
    ready(actor, pair, case.state)
    base = case.service("Base service")
    site_scope = dict(customer_id=pair.customer.id, site_id=pair.site.id)
    with case.env.sessions.begin() as db:
        service = db.get(Service, UUID(base["id"]))
        first_function = db.scalar(insert(BusinessFunction).values(name="A Operations", **site_scope)
                                   .returning(BusinessFunction.id))
        db.execute(insert(BusinessFunction), [dict(name=f"Function {i:03d}", **site_scope) for i in range(505)])
        services = db.scalars(insert(Service).returning(Service.id), [
            dict(name=f"Service {i:03d}", slug=f"service-{i}", service_type_id=service.service_type_id,
                 criticality_level_id=service.criticality_level_id, **site_scope) for i in range(505)
        ]).all()
        db.execute(insert(ServiceBusinessFunction), [
            dict(service_id=identifier, business_function_id=first_function, **site_scope) for identifier in services
        ])
        db.execute(insert(Network), [dict(name=f"Network {i}", network_type="lan", **site_scope) for i in range(1002)])
        db.execute(insert(Integration), [
            dict(name=f"Connection {i}", plugin_id="fixture", base_url="", username_or_token_id="", secret_reference="",
                 **site_scope) for i in range(503)
        ])
        db.execute(insert(Asset), [dict(name=f"Asset {i}", asset_type="virtual_machine", workspace_id=pair.customer.workspace_id, **site_scope) for i in range(1002)])
    data = read(actor, pair)
    functions = data["business_functions"]
    assert functions["total"] == data["services"] == 506 and len(functions["items"]) == 6
    examples = functions["items"][0]["services"]
    assert examples["total"] == 505 and [item["name"] for item in examples["examples"]] == [
        "Service 000", "Service 001", "Service 002", "Service 003",
    ]
    assert data["services_without_functions"] == 1
    assert data["networks"] == data["assets"]["total"] == 1002
    assert data["assets"]["by_type"][0]["count"] == 1002
    assert data["mappings"] == dict(linked=0, unlinked=506, mappings=0, unavailable=0)
    assert data["integrations"] == dict(total=503, enabled=503, disabled=0, active_runs=0)


def test_completed_homelab_supports_an_explicit_additional_import(env):
    pair = env.pair()
    actor = env.actor(CAPABILITIES)
    state = at_integrations(actor, pair, "homelab")
    state = ok(actor.client.post(pair.path + "/integrations/decision", json={
        "version": state["version"], "decision": "skipped",
    }))
    state = ok(actor.client.post(pair.path + "/discovery-review/decision", json={
        "version": state["version"], "decision": "skipped",
    }))
    state = ready(actor, pair, state)
    completed = ok(finish(actor, pair, state["version"]))
    path = pair.path + "/capabilities"
    catalogue = ok(actor.client.get(path))
    assert catalogue["defaults"]["functions"] == []
    assert read(actor, pair)["business_functions"]["total"] == 0
    draft = ok(put(actor.client, path, subset(), completed["version"], save_and_exit=True))
    assert draft["status"] == "completed" and draft["completed_at"] == completed["completed_at"]
    assert draft["stage_decisions"] == completed["stage_decisions"]
    assert ok(apply(actor.client, path, draft["version"]))["created"] == dict(functions=1, services=1, associations=1)
    revisited = ok(actor.client.get(pair.path))["progress"]
    assert revisited["status"] == "completed" and revisited["completed_at"] == completed["completed_at"]
    assert revisited["current_stage"] == "showcase"
    assert revisited["stage_decisions"] == {**completed["stage_decisions"], "capabilities": "completed"}
    assert read(actor, pair)["business_functions"]["items"][0]["services"]["total"] == 1
