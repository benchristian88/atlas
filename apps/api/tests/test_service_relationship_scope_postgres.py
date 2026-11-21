"""Service relationship integrity through signed sessions and migrated PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import Request
from sqlalchemy import event, select, text

from app.auth import COOKIE_NAME, decode_session_token
from app.database import get_db
from app.models import (
    AccessAssignment, Asset, BusinessFunction, DependencyGroupMembership,
    KnowledgeAssertion, KnowledgeChange, KnowledgeGap, KnowledgeRequirementDefinition,
    RelationshipType, RelationshipTypeApplicability,
    Service, ServiceAssetDependency, ServiceBusinessFunction, ServiceDependency, ServiceType,
)
from app.routes import asset_relationships, assets, context, dependency_analysis, knowledge, knowledge_completeness
from app.services.knowledge_completeness import evaluate_service_rule
from app.services.service_relationship_scope import current_relationship
from tests.test_customer_site_deletion_postgres import snapshot
from tests.test_reference_usage_postgres import env, pytestmark, usage


PERMISSIONS = {
    "assets.create", "assets.edit", "assets.view", "services.create", "services.edit",
    "services.view", "services.archive", "service_dependencies.manage", "service_dependencies.view",
    "business_functions.manage", "business_functions.view", "relationships.create",
    "relationships.view", "changes.view", "knowledge_gaps.view", "service_completeness.evaluate",
}

FAMILIES = {
    "asset": (ServiceAssetDependency, Asset, "asset-dependencies", "service-asset-dependencies", "asset_id"),
    "service": (ServiceDependency, Service, "service-dependencies", "service-dependencies", "target_service_id"),
    "function": (ServiceBusinessFunction, BusinessFunction, "business-functions", "service-business-functions", "business_function_id"),
}


def ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json() if response.content else None


@pytest.fixture
def case(usage):
    env, ids = usage.env, usage.ids
    for router in (assets.router, asset_relationships.router, knowledge_completeness.router,
                   dependency_analysis.router, context.router, knowledge.router):
        env.client.app.include_router(router, prefix="/api")
    api = env.client_for(PERMISSIONS)

    def entity(kind, site=0):
        customer_id = ids.customers[site] if site is not None else ids.customer
        site_id = str(ids.sites[site]) if site is not None else None
        plural = {"asset": "assets", "service": "services", "function": "business-functions"}[kind]
        fields = {"name": str(uuid4()), "customer_id": str(customer_id), "site_id": site_id}
        if kind == "asset":
            fields.update(asset_type=ids.asset_key)
        if kind == "service":
            fields.update(service_type_id=str(ids.service_type), criticality_level_id=str(ids.criticality))
        row = ok(api.post(f"/api/{plural}", json=fields), 201)
        return SimpleNamespace(**row, path=f"/api/{plural}/{row['id']}")

    def operations(kind, source, target, client=api):
        model, target_model, collection, member, parameter = FAMILIES[kind]
        return SimpleNamespace(
            model=model, target_model=target_model, path=f"{source.path}/{collection}",
            create=lambda **kwargs: client.post(f"{source.path}/{collection}", json={
                parameter: target.id, "relationship_type_id": str(ids.relationship),
            }, **kwargs),
            url=lambda edge: f"/api/{member}/{edge}",
        )

    return SimpleNamespace(env=env, ids=ids, api=api, entity=entity, operations=operations)


def stored(case, model, row_id):
    with case.env.sessions() as db:
        return db.get(model, UUID(str(row_id)))


def assert_live_edges_valid(case, relation):
    with case.env.sessions() as db:
        assert not db.scalars(select(relation.model.id).where(
            relation.model.relationship_type_id == case.ids.relationship,
            relation.model.valid_to.is_(None),
            ~current_relationship(relation.model),
        )).all()


@pytest.mark.parametrize("kind,source_site,target_site", [
    ("asset", 0, 0), ("asset", None, 1), ("service", 0, 0), ("service", 0, None),
    ("service", None, 1), ("function", 0, 0), ("function", 0, None), ("function", None, 1),
])
def test_normal_link_update_and_end_preserve_identity_and_provenance(case, kind, source_site, target_site):
    source = case.entity("service", source_site)
    target = case.entity(kind, target_site)
    relation = case.operations(kind, source, target)
    edge = ok(relation.create(), 201)
    assert [row["id"] for row in ok(case.api.get(relation.path))] == [edge["id"]]
    other = case.entity(kind, 2)
    parameter = FAMILIES[kind][4]
    patch = {"description": "Reviewed dependency", parameter: other.id}
    updated = ok(case.api.patch(relation.url(edge["id"]), json=patch))
    assert updated["description"] == patch["description"]
    assert updated[parameter] == target.id
    assert stored(case, relation.model, edge["id"]).valid_to is None
    ok(case.api.delete(relation.url(edge["id"])), 204)
    assert ok(case.api.get(relation.path)) == []
    history, = ok(case.api.get(relation.path, params={"include_history": True}))
    assert history["id"] == edge["id"] and history["valid_to"]
    assert stored(case, relation.model, edge["id"]).valid_to is not None
    with case.env.sessions() as db:
        assertion, = db.scalars(select(KnowledgeAssertion).where(
            KnowledgeAssertion.subject_id == UUID(source.id), KnowledgeAssertion.object_id == UUID(target.id),
        ))
        assert assertion.retracted_at and assertion.valid_to
        types = set(db.scalars(select(KnowledgeChange.change_type).where(KnowledgeChange.entity_id == UUID(source.id))))
        prefix = "service_business_function" if kind == "function" else "service_dependency"
        assert {f"{prefix}_added", f"{prefix}_removed", "service_updated"} <= types


def test_asset_moves_with_active_archived_multiple_and_ended_dependencies(case):
    asset = case.entity("asset")
    sibling = {"site_id": str(case.ids.sites[1])}
    ok(case.api.patch(asset.path, json=sibling))
    assert stored(case, Asset, asset.id).site_id == case.ids.sites[1]
    wide = case.entity("service", None)
    local = case.entity("service", 1)
    shared = case.operations("asset", wide, asset)
    bound = case.operations("asset", local, asset)
    wide_edge = ok(shared.create(), 201)
    local_edge = ok(bound.create(), 201)
    ok(case.api.post(local.path + "/archive", json={"reason": "Synthetic archive"}))
    original = {"site_id": str(case.ids.sites[0])}
    foreign = {"customer_id": str(case.ids.customers[2]), "site_id": str(case.ids.sites[2])}
    before = snapshot(case.env.engine)
    ok(case.api.patch(asset.path, json=original), 409)
    ok(case.api.patch(asset.path, json=foreign), 409)
    assert snapshot(case.env.engine) == before
    ok(case.api.delete(bound.url(local_edge["id"])), 204)
    ok(case.api.patch(asset.path, json=original))
    assert stored(case, Asset, asset.id).site_id == case.ids.sites[0]
    assert_live_edges_valid(case, shared)
    assert [row["id"] for row in ok(case.api.get(shared.path))] == [wide_edge["id"]]
    ok(case.api.patch(asset.path, json=foreign), 409)

    neighbor = case.entity("asset")
    ok(case.api.post("/api/asset-relationships", json={
        "source_asset_id": asset.id, "target_asset_id": neighbor.id,
        "relationship_type": case.ids.relationship_key,
    }), 201)
    before = snapshot(case.env.engine)
    ok(case.api.patch(asset.path, json=sibling), 409)
    assert snapshot(case.env.engine) == before


def test_relationship_type_conflict_rolls_back_edge_and_provenance(case):
    source = case.entity("service")
    target = case.entity("asset")
    relation = case.operations("asset", source, target)
    edge = ok(relation.create(), 201)
    with case.env.sessions.begin() as db:
        other_type = RelationshipType(
            key=f"test_{uuid4().hex}", name=f"Alternative {uuid4()}",
            source_label="Uses", target_label="Used by", directional=True,
        )
        db.add(other_type)
        db.flush()
        db.add(RelationshipTypeApplicability(
            relationship_type_id=other_type.id, source_entity_type="service", target_entity_type="asset",
        ))
        other_id = other_type.id
    duplicate = ok(case.api.post(relation.path, json={
        "asset_id": target.id, "relationship_type_id": str(other_id),
    }), 201)
    before = snapshot(case.env.engine)
    ok(case.api.patch(relation.url(edge["id"]), json={"relationship_type_id": str(other_id)}), 409)
    assert snapshot(case.env.engine) == before
    ok(case.api.delete(relation.url(duplicate["id"])), 204)
    updated = ok(case.api.patch(relation.url(edge["id"]), json={"relationship_type_id": str(other_id)}))
    assert updated["id"] == edge["id"] and updated["relationship_type_id"] == str(other_id)
    with case.env.sessions() as db:
        assertions = list(db.scalars(select(KnowledgeAssertion).where(
            KnowledgeAssertion.subject_id == UUID(source.id), KnowledgeAssertion.object_id == UUID(target.id),
        )))
        assert len(assertions) == 3
        assert sum(row.is_accepted and row.retracted_at is None for row in assertions) == 1


def test_cross_customer_transfer_after_ending_retains_relationship_and_assertion(case):
    asset = case.entity("asset")
    service = case.entity("service")
    relation = case.operations("asset", service, asset)
    edge = ok(relation.create(), 201)
    ok(case.api.delete(relation.url(edge["id"])), 204)
    ok(case.api.patch(asset.path, json={
        "customer_id": str(case.ids.customers[2]), "site_id": str(case.ids.sites[2]),
    }))
    assert stored(case, Asset, asset.id).customer_id == case.ids.customers[2]
    record = stored(case, relation.model, edge["id"])
    assert record.customer_id == case.ids.customer and record.valid_to
    assert ok(case.api.get(relation.path, params={"include_history": True})) == []
    with case.env.sessions() as db:
        assertion, = db.scalars(select(KnowledgeAssertion).where(KnowledgeAssertion.object_id == UUID(asset.id)))
        assert assertion.retracted_at and assertion.customer_id == case.ids.customer


@pytest.mark.parametrize("kind", ["service", "function"])
def test_target_transfer_checks_incoming_and_preserves_customer_wide_links(case, kind):
    source = case.entity("service", 0)
    target = case.entity(kind, None)
    relation = case.operations(kind, source, target)
    edge = ok(relation.create(), 201)
    sibling = {"site_id": str(case.ids.sites[1])}
    ok(case.api.patch(target.path, json=sibling), 409)
    assert stored(case, relation.target_model, target.id).site_id is None
    ok(case.api.patch(target.path, json={"site_id": str(case.ids.sites[0])}))
    ok(case.api.patch(source.path, json=sibling), 409)
    assert_live_edges_valid(case, relation)
    ok(case.api.delete(relation.url(edge["id"])), 204)
    ok(case.api.patch(source.path, json=sibling))
    ok(case.api.patch(target.path, json=sibling))
    assert stored(case, relation.target_model, target.id).site_id == case.ids.sites[1]
    assert ok(case.api.get(relation.path, params={"include_history": True}))[0]["id"] == edge["id"]


def scoped_view(case, site=0):
    api = case.env.client_for(PERMISSIONS - {"assets.view"}, "customer", case.ids.customer)
    grant = case.env.client_for({"assets.view"}, "site", case.ids.customer, case.ids.sites[site])
    with case.env.sessions.begin() as db:
        user_id = decode_session_token(api.cookies.get(COOKIE_NAME)).user_id
        donor = decode_session_token(grant.cookies.get(COOKIE_NAME)).user_id
        assignment = db.scalar(select(AccessAssignment).where(AccessAssignment.user_id == donor))
        db.add(AccessAssignment(
            user_id=user_id, role_id=assignment.role_id, scope_type="site",
            customer_id=case.ids.customer, site_id=case.ids.sites[site],
        ))
    return api


def test_group_writes_validate_old_and_new_members_and_preserve_membership(case):
    service = case.entity("service", None)
    visible = case.entity("asset", 0)
    hidden = case.entity("asset", 1)
    asset_link = case.operations("asset", service, visible)
    hidden_link = case.operations("asset", service, hidden)
    one = ok(asset_link.create(), 201)["id"]
    two = ok(hidden_link.create(), 201)["id"]
    collection = service.path + "/dependency-groups"
    group = ok(case.api.post(collection, json={"name": "Providers", "asset_dependency_ids": [one, two]}), 201)
    path = f"/api/dependency-groups/{group['id']}"
    limited = scoped_view(case)
    assert [row["id"] for row in ok(limited.get(asset_link.path))] == [one]
    assert ok(limited.get(collection)) == []
    assert ok(limited.get(service.path))["asset_dependency_count"] == 1
    before = snapshot(case.env.engine)
    for result in (
        limited.patch(hidden_link.url(two), json={"description": "Denied"}),
        limited.delete(hidden_link.url(two)),
        limited.patch(path, json={"asset_dependency_ids": [one]}),
        limited.delete(path),
        limited.post(collection, json={"name": "Denied", "asset_dependency_ids": [two]}),
    ):
        ok(result, 404)
        assert hidden.name not in result.text and hidden.id not in result.text
    assert snapshot(case.env.engine) == before
    replacement = ok(case.api.patch(path, json={"requirement": "optional"}))
    assert set(replacement["asset_dependency_ids"]) == {one, two}
    assert replacement["supersedes_group_id"] == group["id"]
    ok(case.api.delete(asset_link.url(one)), 204)
    assert ok(case.api.get(collection))[0]["asset_dependency_ids"] == [two]
    with case.env.sessions() as db:
        rows = list(db.scalars(select(DependencyGroupMembership).where(
            DependencyGroupMembership.dependency_group_id == UUID(replacement["id"]),
        )))
        assert {str(row.service_asset_dependency_id): row.valid_to is None for row in rows} == {one: False, two: True}


@pytest.mark.parametrize("kind", FAMILIES)
def test_legacy_mismatch_is_invisible_and_cannot_be_mutated(case, kind):
    source = case.entity("service")
    target = case.entity(kind)
    relation = case.operations(kind, source, target)
    edge = ok(relation.create(), 201)
    with case.env.sessions.begin() as db:
        stored_target = db.get(relation.target_model, UUID(target.id))
        # Simulate historical drift outside supported routes. The foreign keys
        # enforce valid entities and Sites, but cannot detect the mismatched edge.
        stored_target.site_id = case.ids.sites[2 if kind == "asset" else 1]
        if kind == "asset":
            stored_target.customer_id = case.ids.customers[2]
            db.get(ServiceType, case.ids.service_type).requires_asset_dependency = True
    before = snapshot(case.env.engine)
    assert ok(case.api.get(relation.path, params={"include_history": True})) == []
    scoped_claims = ok(case.api.get(source.path + "/assertions", params={"current_only": True}))
    general_claims = ok(case.api.get("/api/assertions", params={"subject_type": "service", "subject_id": source.id}))
    assert target.id not in {row["object_id"] for row in scoped_claims + general_claims}
    assert ok(case.api.get(source.path))[{
        "asset": "asset_dependency_count", "service": "service_dependency_count",
        "function": "business_function_count",
    }[kind]] == 0
    graph = ok(case.api.get(source.path + "/graph"))
    assert edge["id"] not in {row["id"] for row in graph["edges"]}
    if kind == "function":
        assert ok(case.api.get(target.path + "/services")) == []
        assert ok(case.api.get("/api/services", params={"business_function_id": target.id})) == []
    if kind in {"asset", "service"}:
        analysis = ok(case.api.post("/api/dependency-analysis", json={"focus_type": kind, "focus_id": target.id}))
        assert analysis["results"] == []
    if kind == "asset":
        assert source.id in {row["id"] for row in ok(case.api.get("/api/services", params={"attention": "missing_dependencies", "search": source.name}))}
    ok(case.api.patch(relation.url(edge["id"]), json={"description": "Invalid"}), 404)
    ok(case.api.delete(relation.url(edge["id"])), 404)
    with case.env.sessions() as db:
        rule = {"asset": "service_asset_dependency_exists", "service": "service_dependency_exists",
                "function": "service_business_function_exists"}[kind]
        result = evaluate_service_rule(db, db.get(Service, UUID(source.id)), rule, {"minimum": 1})
        assert not result.satisfied and result.details["matching_count"] == 0
    assert snapshot(case.env.engine) == before


def assert_concurrent(case, first, second, table):
    """Pause after a real row lock and prove the second backend waits for it."""
    first_locked, second_started, release = Event(), Event(), Event()
    pids = {}
    app = case.api.app

    def request_db(request: Request):
        with case.env.sessions() as db:
            db.connection(execution_options={"scope_race": request.headers.get("x-scope-race")})
            yield db

    def before_execute(conn, cursor, sql, params, execution, many):
        if execution.execution_options.get("scope_race") == "second" and "FOR " in sql and " UPDATE" in sql:
            pids["second"] = conn.connection.driver_connection.info.backend_pid
            second_started.set()

    def after_execute(conn, cursor, sql, params, execution, many):
        if (execution.execution_options.get("scope_race") == "first" and not first_locked.is_set()
                and f"FROM {table}" in sql and "FOR " in sql and " UPDATE" in sql):
            pids["first"] = conn.connection.driver_connection.info.backend_pid
            first_locked.set()
            assert release.wait(8), "first PostgreSQL writer was held too long"

    old_db = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = request_db
    event.listen(case.env.engine, "before_cursor_execute", before_execute)
    event.listen(case.env.engine, "after_cursor_execute", after_execute)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first_call = workers.submit(first, headers={"x-scope-race": "first"})
            try:
                assert first_locked.wait(5)
                second_call = workers.submit(second, headers={"x-scope-race": "second"})
                assert second_started.wait(5)
                with case.env.engine.connect() as connection:
                    deadline = monotonic() + 3
                    while monotonic() < deadline:
                        blockers = connection.scalar(text("select pg_blocking_pids(:pid)"), {"pid": pids["second"]})
                        if pids["first"] in blockers:
                            break
                    else:
                        pytest.fail("PostgreSQL did not report the expected blocked writer")
                assert not second_call.done()
            finally:
                release.set()
            return first_call.result(timeout=12), second_call.result(timeout=12)
    finally:
        event.remove(case.env.engine, "before_cursor_execute", before_execute)
        event.remove(case.env.engine, "after_cursor_execute", after_execute)
        app.dependency_overrides[get_db] = old_db


@pytest.mark.parametrize("race", ["asset_create", "asset_update", "service_create", "service_end", "function_create", "completeness"])
@pytest.mark.parametrize("move_first", [True, False])
def test_relationship_transactions_serialize_in_both_orders(case, race, move_first):
    kind, action = race.split("_") if "_" in race else ("asset", "evaluate")
    source = case.entity("service", None if action == "update" else 0)
    target = case.entity(kind)
    relation = case.operations(kind, source, target)
    table = relation.target_model.__tablename__
    destination = case.ids.sites[1]
    move = lambda **kw: case.api.patch(target.path, json={"site_id": str(destination)}, **kw)
    mutate = relation.create
    expected = (200, 422) if move_first else (409, 201)
    active = not move_first

    if action == "update":
        edge = ok(relation.create(), 201)
        limited = scoped_view(case)
        mutate = lambda **kw: limited.patch(relation.url(edge["id"]), json={"description": "Reviewed"}, **kw)
        expected = (200, 404 if move_first else 200)
        active = True
    elif action == "end":
        edge = ok(relation.create(), 201)
        mutate = lambda **kw: case.api.delete(relation.url(edge["id"]), **kw)
        expected = (409 if move_first else 200, 204)
        active = False
    elif action == "evaluate":
        with case.env.sessions.begin() as db:
            db.get(ServiceType, case.ids.service_type).requires_asset_dependency = True
            requirement = KnowledgeRequirementDefinition(
                key=uuid4().hex, name="Supporting Asset", entity_type="service",
                service_type_id=case.ids.service_type, requirement_level="required",
                severity="medium", rule_type="service_asset_dependency_exists",
                rule_config_json={"minimum": 1}, active=True,
            )
            db.add(requirement)
            db.flush()
            requirement_id = requirement.id
        move = lambda **kw: case.api.post(source.path + "/evaluate-completeness", **kw)
        table = "services"
        expected = (200, 201)
        active = True

    if move_first:
        responses = assert_concurrent(case, move, mutate, table)
    else:
        responses = assert_concurrent(case, mutate, move, table)[::-1]
    for response, status in zip(responses, expected):
        ok(response, status)
        if status == 409:
            assert "cannot be moved" in response.json()["detail"]
    if action != "evaluate":
        assert stored(case, relation.target_model, target.id).site_id == (
            destination if expected[0] == 200 else case.ids.sites[0]
        )
    rows = ok(case.api.get(relation.path))
    assert len(rows) == int(active)
    if action == "update":
        assert rows[0]["description"] == (None if move_first else "Reviewed")
    if action == "end":
        assert stored(case, relation.model, edge["id"]).valid_to
    if action == "evaluate":
        with case.env.sessions() as db:
            gaps = list(db.scalars(select(KnowledgeGap).where(
                KnowledgeGap.requirement_definition_id == requirement_id,
                KnowledgeGap.entity_id == UUID(source.id),
            )))
            assert {gap.status for gap in gaps} == ({"resolved"} if move_first else set())
    assert_live_edges_valid(case, relation)


@pytest.mark.parametrize("family", ["asset", "outgoing", "incoming", "function", "support"])
@pytest.mark.parametrize("boundary", ["permission", "site", "customer", "allowed"])
def test_signed_readers_get_only_authorized_link_details(case, family, boundary):
    kind = {"asset": "asset", "outgoing": "service", "incoming": "service",
            "function": "function", "support": "function"}[family]
    # A customer-wide endpoint forms a legitimate edge to either site.
    source = case.entity("service", None if boundary == "site" and family not in {"incoming", "support"} else 0)
    target = case.entity(kind, None if boundary == "site" and family in {"incoming", "support"} else 1 if boundary == "site" else 0)
    relation = case.operations(kind, source, target)
    edge_id = ok(relation.create(), 201)["id"]
    endpoint = {"asset": "assets.view", "outgoing": "services.view", "incoming": "services.view",
                "function": "business_functions.view", "support": "services.view"}[family]
    focus = target if family in {"incoming", "support"} else source
    path = (
        focus.path + "/service-dependencies" if family == "incoming"
        else focus.path + "/services" if family == "support" else relation.path
    )
    permissions = PERMISSIONS - {endpoint} if boundary == "permission" else PERMISSIONS
    if boundary == "customer":
        api = case.env.client_for(permissions, "customer", case.ids.customers[2])
        ok(api.get(path), 404)
        return
    if boundary == "site":
        # A site grant can view a site-specific derivative, never a wide record.
        api = case.env.client_for(permissions, "site", case.ids.customer, case.ids.sites[0])
        ok(api.get(path), 404)
        scoped_path = (
            target.path + "/service-dependencies" if family == "outgoing"
            else target.path + "/services" if family == "function"
            else source.path + "/service-dependencies" if family == "incoming"
            else source.path + "/business-functions" if family == "support"
            else None
        )
        if scoped_path is not None:
            # Use the grant covering the site-specific end in this direction.
            site = 0 if family in {"incoming", "support"} else 1
            api = case.env.client_for(permissions, "site", case.ids.customer, case.ids.sites[site])
            assert ok(api.get(scoped_path)) == []
        return
    api = case.env.client_for(permissions, "customer", case.ids.customer)
    if boundary == "permission" and family == "function":
        ok(api.get(path), 403)
    else:
        rows = ok(api.get(path))
        assert [row["id"] for row in rows] == ([edge_id] if boundary == "allowed" else [])
