"""S1: real PostgreSQL and signed sessions with database-backed grants.

Only the database dependency is replaced. Each test uses unique definitions;
hidden-data comparisons keep the entire visible response, including ordering.
"""
from datetime import datetime, timezone
import os
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import event, select

from app.auth import COOKIE_NAME, decode_session_token
from app.models import (
    AccessAssignment, Asset, AssetRelationship, AssetType, BusinessFunction,
    CriticalityLevel, Customer, Permission, RelationshipType, RelationshipTypeApplicability,
    Role, RolePermission,
    Service, ServiceAssetDependency, ServiceBusinessFunction, ServiceDependency,
    ServiceType, Site, Workspace,
)
from app.routes import reference_data, service_reference_data
from tests.test_customer_site_deletion_postgres import env

pytestmark = pytest.mark.skipif(
    not os.getenv("ATLAS_TEST_DATABASE_URL"),
    reason="requires disposable migrated PostgreSQL",
)

DEFINITIONS = {"service_types.view", "criticality_levels.view", "relationship_types.view"}
OPERATIONAL = {"services.view", "assets.view", "relationships.view",
               "service_dependencies.view", "business_functions.view"}
FAMILIES = ("asset", "service_asset", "service_service", "service_business_function")
TYPED = FAMILIES[1:]


@pytest.fixture
def usage(env):
    for router in (reference_data.relationship_types_router,
                   service_reference_data.service_types_router,
                   service_reference_data.criticality_router):
        env.client.app.include_router(router, prefix="/api")
    with env.sessions.begin() as db:
        workspace = Workspace(name="S1 synthetic", slug=uuid.uuid4().hex)
        db.add(workspace); db.flush()
        customers = [Customer(workspace_id=workspace.id, name=f"S1 Customer {i}") for i in range(2)]
        db.add_all(customers); db.flush()
        sites = [Site(customer_id=customers[0].id, name="Visible"),
                 Site(customer_id=customers[0].id, name="Sibling"),
                 Site(customer_id=customers[1].id, name="Foreign")]
        db.add_all(sites)
        suffix = uuid.uuid4().hex
        asset_type = AssetType(key=f"s1_{suffix}", name=f"S1 Asset {suffix}")
        service_type = ServiceType(key=f"s1_{suffix}", name=f"S1 Service {suffix}")
        criticality = CriticalityLevel(key=f"s1_{suffix}", name=f"S1 Criticality {suffix}", rank=1)
        relationship = RelationshipType(key=f"s1_{suffix}", name=f"S1 Relationship {suffix}",
            source_label="Uses", target_label="Used by", directional=True)
        db.add_all([asset_type, service_type, criticality, relationship]); db.flush()
        for source, target in (("asset", "asset"), ("service", "asset"),
                               ("service", "service"), ("service", "business_function")):
            db.add(RelationshipTypeApplicability(relationship_type_id=relationship.id,
                source_entity_type=source, target_entity_type=target))
        ids = SimpleNamespace(workspace=workspace.id, customer=customers[0].id,
            sites=[site.id for site in sites], customers=[site.customer_id for site in sites],
            asset_key=asset_type.key, service_type=service_type.id,
            criticality=criticality.id, relationship=relationship.id, relationship_key=relationship.key)
    return SimpleNamespace(env=env, ids=ids)


def clients(usage):
    e, ids = usage.env, usage.ids
    permissions = DEFINITIONS | OPERATIONAL
    return {
        "broad": e.client_for(permissions),
        "customer": e.client_for(permissions, "customer", ids.customer),
        "site": e.client_for(permissions, "site", ids.customer, ids.sites[0]),
        "definitions": e.client_for(DEFINITIONS, "site", ids.customer, ids.sites[0]),
    }


def endpoint(db, ids, kind, site):
    scope = dict(customer_id=ids.customers[site], site_id=ids.sites[site])
    suffix = uuid.uuid4().hex
    if kind == "asset":
        item = Asset(**scope, workspace_id=ids.workspace, name=suffix, asset_type=ids.asset_key)
    elif kind == "service":
        item = Service(**scope, name=suffix, slug=suffix,
            service_type_id=ids.service_type, criticality_level_id=ids.criticality)
    else:
        item = BusinessFunction(**scope, name=suffix)
    db.add(item); db.flush()
    return item


def add_usage(usage, family, site=0, *, source_site=None, target_site=None, edge_site=None, ended=False):
    ids = usage.ids
    source_site = site if source_site is None else source_site
    target_site = site if target_site is None else target_site
    edge_site = site if edge_site is None else edge_site
    with usage.env.sessions.begin() as db:
        source = endpoint(db, ids, "asset" if family == "asset" else "service", source_site)
        if family == "service":
            return source.id
        target_kind = {"asset": "asset", "service_asset": "asset",
                       "service_service": "service", "service_business_function": "business_function"}[family]
        target = endpoint(db, ids, target_kind, target_site)
        scope = dict(customer_id=ids.customers[edge_site], site_id=ids.sites[edge_site])
        if family == "asset":
            row = AssetRelationship(**scope, source_asset_id=source.id, target_asset_id=target.id,
                relationship_type=ids.relationship_key, legacy_cross_context=source_site != target_site)
        else:
            fields = dict(**scope, relationship_type_id=ids.relationship)
            if ended:
                fields["valid_to"] = datetime.now(timezone.utc)
            if family == "service_asset":
                row = ServiceAssetDependency(**fields, service_id=source.id, asset_id=target.id)
            elif family == "service_service":
                row = ServiceDependency(**fields, source_service_id=source.id, target_service_id=target.id)
            else:
                row = ServiceBusinessFunction(**fields, service_id=source.id, business_function_id=target.id)
        db.add(row); db.flush()
        return source.id, target.id


def snapshot(api, family, ids, headers=None):
    paths = ("service-types", "criticality-levels") if family == "service" else ("relationship-types",)
    result = {}
    for path in paths:
        response = api.get(f"/api/{path}", headers=headers or {})
        assert response.status_code == 200, response.text
        result[path] = response.json()
    return result


def counts(body, ids):
    identifiers = {"service-types": ids.service_type, "criticality-levels": ids.criticality,
                   "relationship-types": ids.relationship}
    return [next(row["in_use_count"] for row in rows if row["id"] == str(identifiers[path]))
            for path, rows in body.items()]


def assert_counts(body, ids, expected):
    assert counts(body, ids) == [expected] * len(body)
    assert all(type(row["in_use_count"]) is int for rows in body.values() for row in rows)


def definitions(body):
    return {path: [{key: value for key, value in row.items() if key != "in_use_count"}
                   for row in rows] for path, rows in body.items()}


def assignment_for(db, api):
    user_id = decode_session_token(api.cookies.get(COOKIE_NAME)).user_id
    return db.scalar(select(AccessAssignment).where(AccessAssignment.user_id == user_id))


@pytest.mark.parametrize("family", ("service",) + FAMILIES)
def test_hidden_data_invariance_and_visible_positive_controls(usage, family):
    apis = clients(usage)
    add_usage(usage, family)
    before = {name: snapshot(api, family, usage.ids) for name, api in apis.items()}
    for name, body in before.items():
        assert_counts(body, usage.ids, 0 if name == "definitions" else 1)
        assert definitions(body) == definitions(before["broad"])

    # Only foreign-Customer usage is inserted. Visible records remain fixed.
    add_usage(usage, family, site=2)
    foreign = {name: snapshot(api, family, usage.ids) for name, api in apis.items()}
    for name in ("customer", "site", "definitions"):
        assert foreign[name] == before[name]
    assert_counts(foreign["broad"], usage.ids, 2)

    # Only sibling-Site usage is inserted; Customer control must increase.
    add_usage(usage, family, site=1)
    sibling = {name: snapshot(api, family, usage.ids) for name, api in apis.items()}
    for name in ("site", "definitions"):
        assert sibling[name] == foreign[name]
    assert_counts(sibling["customer"], usage.ids, 2)
    assert_counts(sibling["broad"], usage.ids, 3)

    add_usage(usage, family)
    for name, api in apis.items():
        body = snapshot(api, family, usage.ids)
        assert definitions(body) == definitions(before["broad"])
        assert_counts(body, usage.ids, {"broad": 4, "customer": 3, "site": 2, "definitions": 0}[name])


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("hidden_site", (1, 2), ids=("sibling", "foreign"))
@pytest.mark.parametrize("hidden_endpoint", ("source", "target"))
def test_one_hidden_endpoint_cannot_contribute(usage, family, hidden_site, hidden_endpoint):
    apis = clients(usage)
    add_usage(usage, family)
    before = {name: snapshot(api, family, usage.ids) for name, api in apis.items()}
    add_usage(usage, family, **{f"{hidden_endpoint}_site": hidden_site})
    assert snapshot(apis["site"], family, usage.ids) == before["site"]
    assert snapshot(apis["definitions"], family, usage.ids) == before["definitions"]
    assert_counts(snapshot(apis["broad"], family, usage.ids), usage.ids, 2)
    if hidden_site == 2:
        assert snapshot(apis["customer"], family, usage.ids) == before["customer"]
    else:
        assert_counts(snapshot(apis["customer"], family, usage.ids), usage.ids, 2)


@pytest.mark.parametrize("family", TYPED)
def test_relationship_scope_is_checked_even_when_both_endpoints_are_visible(usage, family):
    apis = clients(usage)
    add_usage(usage, family)
    before = snapshot(apis["site"], family, usage.ids)
    add_usage(usage, family, edge_site=1)
    assert snapshot(apis["site"], family, usage.ids) == before
    assert_counts(snapshot(apis["customer"], family, usage.ids), usage.ids, 2)
    assert_counts(snapshot(apis["broad"], family, usage.ids), usage.ids, 2)


@pytest.mark.parametrize("family,permission", [
    ("service", "services.view"),
    ("asset", "assets.view"), ("asset", "relationships.view"),
    ("service_asset", "service_dependencies.view"), ("service_asset", "services.view"),
    ("service_asset", "assets.view"), ("service_service", "service_dependencies.view"),
    ("service_service", "services.view"), ("service_business_function", "services.view"),
    ("service_business_function", "business_functions.view"),
])
def test_each_operational_permission_is_required_in_its_own_scope(usage, family, permission):
    add_usage(usage, family)
    api = usage.env.client_for(DEFINITIONS | (OPERATIONAL - {permission}))
    assert_counts(snapshot(api, family, usage.ids), usage.ids, 0)
    with usage.env.sessions.begin() as db:
        # Permissions on unrelated global grants must not widen this site grant.
        assignment = assignment_for(db, api)
        role = Role(name=uuid.uuid4().hex, active=True)
        db.add(role); db.flush()
        permission_id = db.scalar(select(Permission.id).where(Permission.key == permission))
        db.add(RolePermission(role_id=role.id, permission_id=permission_id))
        grant = AccessAssignment(user_id=assignment.user_id, role_id=role.id, scope_type="site",
            customer_id=usage.ids.customer, site_id=usage.ids.sites[1])
        db.add(grant); db.flush()
        grant_id = grant.id
    assert_counts(snapshot(api, family, usage.ids), usage.ids, 0)
    with usage.env.sessions.begin() as db:
        db.get(AccessAssignment, grant_id).site_id = usage.ids.sites[0]
    assert_counts(snapshot(api, family, usage.ids), usage.ids, 1)


@pytest.mark.parametrize("family", ("service",) + FAMILIES)
def test_overlapping_grants_do_not_duplicate_usage(usage, family):
    api = usage.env.client_for(DEFINITIONS | OPERATIONAL, "customer", usage.ids.customer)
    with usage.env.sessions.begin() as db:
        assignment = assignment_for(db, api)
        db.add(AccessAssignment(user_id=assignment.user_id, role_id=assignment.role_id, scope_type="site",
            customer_id=usage.ids.customer, site_id=usage.ids.sites[0]))
    add_usage(usage, family)
    assert_counts(snapshot(api, family, usage.ids), usage.ids, 1)


def test_service_usage_matches_selected_context_and_retains_customer_wide_rules(usage):
    apis = clients(usage)
    for site in range(3):
        add_usage(usage, "service", site=site)
    with usage.env.sessions.begin() as db:
        row = endpoint(db, usage.ids, "service", 0)
        row.site_id = None
    headers = {"X-Atlas-Customer-ID": str(usage.ids.customer), "X-Atlas-Site-ID": str(usage.ids.sites[0])}
    for name in ("broad", "customer"):
        assert_counts(snapshot(apis[name], "service", usage.ids, headers), usage.ids, 2)
        # The normal context dependency resolves a site-only header's Customer.
        assert_counts(snapshot(apis[name], "service", usage.ids,
            {"X-Atlas-Site-ID": str(usage.ids.sites[0])}), usage.ids, 2)
    assert_counts(snapshot(apis["site"], "service", usage.ids, headers), usage.ids, 1)
    assert_counts(snapshot(apis["definitions"], "service", usage.ids, headers), usage.ids, 0)
    for path in ("service-types", "criticality-levels", "relationship-types"):
        # Definition-only access must not require operational context grants.
        assert apis["definitions"].get(f"/api/{path}", headers=headers).status_code == 200


def test_asset_relationship_usage_matches_its_list_context(usage):
    apis = clients(usage)
    for site in range(3):
        add_usage(usage, "asset", site=site)
    headers = {"X-Atlas-Customer-ID": str(usage.ids.customer), "X-Atlas-Site-ID": str(usage.ids.sites[0])}
    assert_counts(snapshot(apis["broad"], "asset", usage.ids), usage.ids, 3)
    for name in ("broad", "customer", "site"):
        assert_counts(snapshot(apis[name], "asset", usage.ids, headers), usage.ids, 1)
    assert_counts(snapshot(apis["definitions"], "asset", usage.ids, headers), usage.ids, 0)


def test_relationship_total_preserves_each_family_contribution(usage):
    apis = clients(usage)
    for family in FAMILIES:
        add_usage(usage, family)
        add_usage(usage, family, site=2)
    assert_counts(snapshot(apis["site"], "asset", usage.ids), usage.ids, 4)
    assert_counts(snapshot(apis["broad"], "asset", usage.ids), usage.ids, 8)


def test_archived_service_usage_is_retained_and_tombstones_are_excluded(usage):
    api = clients(usage)["broad"]
    add_usage(usage, "service")
    with usage.env.sessions.begin() as db:
        archived = endpoint(db, usage.ids, "service", 0)
        archived.archived_at = datetime.now(timezone.utc)
        # A retained mistake is not part of the operational model.
        tombstone = Service(customer_id=usage.ids.customer, site_id=usage.ids.sites[0],
            name=uuid.uuid4().hex, slug=uuid.uuid4().hex, service_type_id=usage.ids.service_type,
            criticality_level_id=usage.ids.criticality, deleted_at=datetime.now(timezone.utc))
        db.add(tombstone)
    assert_counts(snapshot(api, "service", usage.ids), usage.ids, 2)


@pytest.mark.parametrize("path,identifier,manage,family", [
    ("service-types", "service_type", "service_types.manage", "service"),
    ("criticality-levels", "criticality", "criticality_levels.manage", "service"),
    ("relationship-types", "relationship", "relationship_types.manage", "service_asset"),
])
def test_definition_only_mutation_responses_and_filters_preserve_visibility(usage, path, identifier, manage, family):
    add_usage(usage, family)
    api = usage.env.client_for(DEFINITIONS | {manage})
    record_id = str(getattr(usage.ids, identifier))
    url = f"/api/{path}/{record_id}"
    headers = {"X-Atlas-Customer-ID": str(usage.ids.customer), "X-Atlas-Site-ID": str(usage.ids.sites[0])}
    response = api.patch(url, json={"active": False}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["in_use_count"] == 0
    rows = api.get(f"/api/{path}", headers=headers).json()
    assert record_id in {row["id"] for row in rows}
    assert record_id not in {row["id"] for row in api.get(f"/api/{path}?active_only=true", headers=headers).json()}
    response = api.patch(url, json={"active": True}, headers=headers)
    assert response.status_code == 200 and response.json()["in_use_count"] == 0
    if path != "relationship-types":
        for action in ("deactivate", "activate"):
            response = api.post(f"{url}/{action}", headers=headers)
            assert response.status_code == 200 and response.json()["in_use_count"] == 0
    else:
        response = api.get(f"/api/{path}?source_entity_type=service&target_entity_type=asset", headers=headers)
        assert response.status_code == 200
        assert record_id in {row["id"] for row in response.json()}
        assert all(row["in_use_count"] == 0 for row in response.json())
    suffix = uuid.uuid4().hex
    payload = {"key": f"s1_{suffix}", "name": suffix}
    if path == "criticality-levels":
        payload["rank"] = 1
    if path == "relationship-types":
        payload.update(source_label="Uses", target_label="Used by")
    response = api.post(f"/api/{path}", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    assert response.json()["in_use_count"] == 0


def test_unavailable_context_does_not_hide_global_definitions(usage):
    apis = clients(usage)
    # Also cover a definition reader with an unrelated operational permission.
    apis["asset_reader"] = usage.env.client_for(DEFINITIONS | {"assets.view"}, "site",
        usage.ids.customer, usage.ids.sites[0])
    add_usage(usage, "service")
    add_usage(usage, "service_asset")
    for family in ("service", "service_asset"):
        before = snapshot(apis["broad"], family, usage.ids)
        for name, api in apis.items():
            headers = {"X-Atlas-Site-ID": str(uuid.uuid4())}
            body = snapshot(api, family, usage.ids, headers)
            assert definitions(body) == definitions(before)
            assert_counts(body, usage.ids, 0)
        for name in ("site", "definitions", "asset_reader"):
            body = snapshot(apis[name], family, usage.ids,
                {"X-Atlas-Site-ID": str(usage.ids.sites[1])})
            assert definitions(body) == definitions(before)
            assert_counts(body, usage.ids, 0)


@pytest.mark.parametrize("family", TYPED)
def test_ended_relationships_do_not_contribute(usage, family):
    api = clients(usage)["broad"]
    add_usage(usage, family)
    before = snapshot(api, family, usage.ids)
    add_usage(usage, family, ended=True)
    assert snapshot(api, family, usage.ids) == before


@pytest.mark.parametrize("family", ("service", "service_asset"))
def test_usage_aggregation_query_count_does_not_grow_with_definitions(usage, family):
    api = clients(usage)["broad"]
    add_usage(usage, family)
    def query_count():
        statements = []
        def record(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        event.listen(usage.env.engine, "before_cursor_execute", record)
        try:
            snapshot(api, family, usage.ids)
        finally:
            event.remove(usage.env.engine, "before_cursor_execute", record)
        return sum("count(" in statement.lower() for statement in statements)
    before = query_count()
    with usage.env.sessions.begin() as db:
        for _ in range(5):
            suffix = uuid.uuid4().hex
            db.add(ServiceType(key=suffix, name=suffix))
            db.add(CriticalityLevel(key=suffix, name=suffix, rank=1))
            db.add(RelationshipType(key=suffix, name=suffix, source_label="Uses", target_label="Used by"))
    assert query_count() == before == (2 if family == "service" else 4)
