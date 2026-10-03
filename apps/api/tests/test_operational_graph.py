from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.authorization import (
    ActiveContext,
    Principal,
    ScopeGrant,
    get_active_context,
    get_principal,
)
from app.database import get_db
from app.main import app
from app.models import (
    Asset,
    AssetCategory,
    AssetRelationship,
    AssetType,
    BusinessFunction,
    CriticalityLevel,
    KnowledgeCompletenessSummary,
    KnowledgeGap,
    RelationshipType,
    Service,
    ServiceAssetDependency,
    ServiceBusinessFunction,
    ServiceDependency,
    ServiceType,
    User,
)
from app.services.operational_graph import (
    GraphFocusNotFound,
    GraphProjectionRequest,
    OperationalGraphBuilder,
    graph_edge_key,
    graph_node_key,
    operational_graph_to_service_graph,
)

NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)


class GraphDatabase:
    """Small SQLAlchemy-aware record source for projection unit tests."""

    def __init__(self, *records):
        self.records = list(records)
        self.by_key = {(type(record), record.id): record for record in records}
        self.queries = Counter()

    def get(self, model, record_id):
        self.queries[("get", model)] += 1
        return self.by_key.get((model, record_id))

    def scalars(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        self.queries[("select", entity)] += 1
        return [record for record in self.records if isinstance(record, entity)]


def principal(*permissions: str, customer_id=None, site_id=None) -> Principal:
    user = User(
        id=uuid.uuid4(),
        email="viewer@example.test",
        password_hash="not-a-real-secret",
        display_name="Viewer",
        is_active=True,
        force_password_change=False,
    )
    return Principal(
        user=user,
        grants=(
            ScopeGrant(
                assignment_id=uuid.uuid4(),
                role_id=uuid.uuid4(),
                role_name="Test viewer",
                scope_type="global" if customer_id is None else ("site" if site_id else "customer"),
                customer_id=customer_id,
                site_id=site_id,
                permissions=frozenset(permissions),
            ),
        ),
    )


def reference_records():
    service_type = ServiceType(
        id=uuid.uuid4(),
        key="infrastructure_service",
        name="Infrastructure Service",
        active=True,
        system_defined=True,
        sort_order=10,
        requires_asset_dependency=True,
    )
    criticality = CriticalityLevel(
        id=uuid.uuid4(),
        key="high",
        name="High",
        rank=75,
        active=True,
        system_defined=True,
        sort_order=10,
    )
    asset_type = AssetType(
        id=uuid.uuid4(),
        key="server",
        name="Server",
        active=True,
        system_defined=True,
        sort_order=10,
    )
    depends_on = RelationshipType(
        id=uuid.uuid4(),
        key="depends_on",
        name="Depends on",
        source_label="Depends on",
        target_label="Required by",
        directional=True,
        active=True,
        system_defined=True,
        sort_order=10,
        allowed_source_asset_type_keys=[],
        allowed_target_asset_type_keys=[],
    )
    runs_on = RelationshipType(
        id=uuid.uuid4(),
        key="runs_on",
        name="Runs on",
        source_label="Runs on",
        target_label="Hosts",
        directional=True,
        active=True,
        system_defined=True,
        sort_order=20,
        allowed_source_asset_type_keys=[],
        allowed_target_asset_type_keys=[],
    )
    supports = RelationshipType(
        id=uuid.uuid4(),
        key="supports",
        name="Supports",
        source_label="Supports",
        target_label="Supported by",
        directional=True,
        active=True,
        system_defined=True,
        sort_order=30,
        allowed_source_asset_type_keys=[],
        allowed_target_asset_type_keys=[],
    )
    return service_type, criticality, asset_type, depends_on, runs_on, supports


def service(name, customer_id, service_type, criticality, *, site_id=None, entity_id=None):
    return Service(
        id=entity_id or uuid.uuid4(),
        customer_id=customer_id,
        site_id=site_id,
        name=name,
        slug=name.lower().replace(" ", "-"),
        service_type_id=service_type.id,
        criticality_level_id=criticality.id,
        lifecycle_status="active",
        operational_status="unknown",
        source="manual",
        archived_at=None,
        updated_at=NOW,
    )


def asset(name, customer_id, site_id, *, entity_id=None):
    return Asset(
        id=entity_id or uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        customer_id=customer_id,
        site_id=site_id,
        name=name,
        asset_type="server",
        status="active",
        source="manual",
        metadata_={},
        updated_at=NOW,
    )


def function(name, customer_id, criticality, *, site_id=None, entity_id=None):
    return BusinessFunction(
        id=entity_id or uuid.uuid4(),
        customer_id=customer_id,
        site_id=site_id,
        name=name,
        criticality_level_id=criticality.id,
        active=True,
        updated_at=NOW,
    )


def builder(*records, permissions=None):
    permissions = permissions or (
        "assets.view",
        "relationships.view",
        "services.view",
        "service_dependencies.view",
        "business_functions.view",
    )
    db = GraphDatabase(*records)
    return db, OperationalGraphBuilder(db, principal(*permissions), clock=lambda: NOW)


def test_namespaced_identity_prevents_cross_table_and_edge_family_collisions():
    shared_id = uuid.uuid4()
    assert graph_node_key("asset", shared_id) != graph_node_key("service", shared_id)
    assert graph_edge_key("service_asset", shared_id) != graph_edge_key("service_service", shared_id)


def test_all_focus_types_depth_zero_and_business_function_metadata():
    customer_id, site_id = uuid.uuid4(), uuid.uuid4()
    service_type, criticality, asset_type, *relationships = reference_records()
    records = [
        service_type,
        criticality,
        asset_type,
        *relationships,
        asset("PVE", customer_id, site_id),
        service("DNS", customer_id, service_type, criticality),
        function("Secure access", customer_id, criticality),
    ]
    _, graph_builder = builder(*records)
    for entity_type, item in zip(("asset", "service", "business_function"), records[-3:]):
        graph = graph_builder.build(
            GraphProjectionRequest(
                focus_type=entity_type, focus_id=item.id, max_depth=0
            )
        )
        assert graph.focus_key == f"{entity_type}:{item.id}"
        assert len(graph.nodes) == 1
        assert graph.edges == []
        assert graph.truncated is False
    business_node = graph.nodes[0]
    assert business_node.completeness_status is None
    assert business_node.open_gap_count is None


def test_archived_services_inactive_functions_and_missing_entity_permissions_are_excluded():
    customer_id, site_id = uuid.uuid4(), uuid.uuid4()
    service_type, criticality, asset_type, depends_on, runs_on, supports = reference_records()
    active_service = service("Active", customer_id, service_type, criticality, site_id=site_id)
    archived_service = service("Archived", customer_id, service_type, criticality, site_id=site_id)
    archived_service.archived_at = NOW
    inactive_function = function("Inactive", customer_id, criticality, site_id=site_id)
    inactive_function.active = False
    host = asset("Host", customer_id, site_id)
    rows = [
        ServiceAssetDependency(
            id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
            service_id=active_service.id, asset_id=host.id,
            relationship_type_id=runs_on.id, required_for_operation=True,
            source="manual", valid_from=NOW - timedelta(days=1), valid_to=None,
        ),
        ServiceDependency(
            id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
            source_service_id=active_service.id, target_service_id=archived_service.id,
            relationship_type_id=depends_on.id, required_for_operation=True,
            valid_from=NOW - timedelta(days=1), valid_to=None,
        ),
        ServiceBusinessFunction(
            id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
            service_id=active_service.id, business_function_id=inactive_function.id,
            relationship_type_id=supports.id, is_primary=False,
            valid_from=NOW - timedelta(days=1), valid_to=None,
        ),
    ]
    db = GraphDatabase(
        service_type, criticality, asset_type, depends_on, runs_on, supports,
        active_service, archived_service, inactive_function, host, *rows,
    )
    without_assets = OperationalGraphBuilder(
        db,
        principal("services.view", "service_dependencies.view", "business_functions.view"),
        clock=lambda: NOW,
    )
    graph = without_assets.build(GraphProjectionRequest(
        focus_type="service", focus_id=active_service.id,
    ))
    assert [node.entity_id for node in graph.nodes] == [active_service.id]
    assert graph.edges == []
    with pytest.raises(GraphFocusNotFound):
        without_assets.build(GraphProjectionRequest(
            focus_type="service", focus_id=archived_service.id,
        ))
    with pytest.raises(GraphFocusNotFound):
        without_assets.build(GraphProjectionRequest(
            focus_type="business_function", focus_id=inactive_function.id,
        ))
    assert without_assets.build(GraphProjectionRequest(
        focus_type="service", focus_id=archived_service.id,
        include_inactive_focus=True,
    )).focus_key == f"service:{archived_service.id}"
    assert without_assets.build(GraphProjectionRequest(
        focus_type="business_function", focus_id=inactive_function.id,
        include_inactive_focus=True,
    )).focus_key == f"business_function:{inactive_function.id}"


def test_depth_direction_cycles_and_semantic_direction_are_deterministic():
    customer_id = uuid.uuid4()
    service_type, criticality, asset_type, depends_on, runs_on, supports = reference_records()
    first = service("First", customer_id, service_type, criticality)
    second = service("Second", customer_id, service_type, criticality)
    third = service("Third", customer_id, service_type, criticality)
    first_second = ServiceDependency(
        id=uuid.uuid4(), customer_id=customer_id, site_id=None,
        source_service_id=first.id, target_service_id=second.id,
        relationship_type_id=depends_on.id, required_for_operation=True,
        valid_from=NOW - timedelta(days=1), valid_to=None,
    )
    second_third = ServiceDependency(
        id=uuid.uuid4(), customer_id=customer_id, site_id=None,
        source_service_id=second.id, target_service_id=third.id,
        relationship_type_id=depends_on.id, required_for_operation=True,
        valid_from=NOW - timedelta(days=1), valid_to=None,
    )
    third_first = ServiceDependency(
        id=uuid.uuid4(), customer_id=customer_id, site_id=None,
        source_service_id=third.id, target_service_id=first.id,
        relationship_type_id=depends_on.id, required_for_operation=True,
        valid_from=NOW - timedelta(days=1), valid_to=None,
    )
    _, graph_builder = builder(
        service_type, criticality, asset_type, depends_on, runs_on, supports,
        first, second, third, first_second, second_third, third_first,
    )
    outgoing_one = graph_builder.build(GraphProjectionRequest(
        focus_type="service", focus_id=first.id, max_depth=1,
        direction="outgoing", edge_families=frozenset({"service_service"}),
    ))
    assert [edge.edge_id for edge in outgoing_one.edges] == [first_second.id]
    incoming_one = graph_builder.build(GraphProjectionRequest(
        focus_type="service", focus_id=first.id, max_depth=1,
        direction="incoming", edge_families=frozenset({"service_service"}),
    ))
    assert [edge.edge_id for edge in incoming_one.edges] == [third_first.id]
    assert incoming_one.edges[0].source_key == f"service:{third.id}"
    assert incoming_one.edges[0].target_key == f"service:{first.id}"

    outgoing_two = graph_builder.build(GraphProjectionRequest(
        focus_type="service", focus_id=first.id, max_depth=2,
        direction="outgoing", edge_families=frozenset({"service_service"}),
    ))
    assert {node.entity_id for node in outgoing_two.nodes} == {first.id, second.id, third.id}
    assert {edge.edge_id for edge in outgoing_two.edges} == {first_second.id, second_third.id}
    assert [node.key for node in outgoing_two.nodes] == sorted(node.key for node in outgoing_two.nodes)
    assert [edge.key for edge in outgoing_two.edges] == sorted(edge.key for edge in outgoing_two.edges)


@pytest.mark.parametrize(
    ("valid_from", "valid_to", "included"),
    [
        (NOW + timedelta(seconds=1), None, False),
        (NOW, None, True),
        (NOW - timedelta(seconds=1), NOW + timedelta(seconds=1), True),
        (NOW - timedelta(seconds=1), NOW, False),
        (NOW - timedelta(seconds=2), NOW - timedelta(seconds=1), False),
    ],
)
@pytest.mark.parametrize("depth", [1, 3])
def test_temporal_boundaries_are_inclusive_from_and_exclusive_to(
    valid_from, valid_to, included, depth
):
    customer_id, site_id = uuid.uuid4(), uuid.uuid4()
    service_type, criticality, asset_type, depends_on, runs_on, supports = reference_records()
    item = service("Atlas", customer_id, service_type, criticality, site_id=site_id)
    host = asset("Host", customer_id, site_id)
    dependency = ServiceAssetDependency(
        id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
        service_id=item.id, asset_id=host.id, relationship_type_id=runs_on.id,
        required_for_operation=True, source="manual",
        valid_from=valid_from, valid_to=valid_to,
    )
    _, graph_builder = builder(
        service_type, criticality, asset_type, depends_on, runs_on, supports,
        item, host, dependency,
    )
    graph = graph_builder.build(GraphProjectionRequest(
        focus_type="service", focus_id=item.id, max_depth=depth,
        edge_families=frozenset({"service_asset"}),
    ))
    assert bool(graph.edges) is included
    assert graph.generated_at == NOW


def test_all_edge_families_metadata_and_completeness_are_projected_in_batches():
    customer_id, site_id = uuid.uuid4(), uuid.uuid4()
    service_type, criticality, asset_type, depends_on, runs_on, supports = reference_records()
    asset_type.category_record = AssetCategory(id=uuid.uuid4(), key="custom", name="Custom", icon_key="cloud", accent_key="rose")
    service_type.icon_key = "database"
    service_type.accent_key = "purple"
    first = service("Photos", customer_id, service_type, criticality, site_id=site_id)
    second = service("DNS", customer_id, service_type, criticality, site_id=site_id)
    host = asset("LXC", customer_id, site_id)
    storage = asset("NAS", customer_id, site_id)
    business_function = function("Household information", customer_id, criticality, site_id=site_id)
    rows = [
        AssetRelationship(
            id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
            source_asset_id=host.id, target_asset_id=storage.id,
            relationship_type="depends_on", legacy_cross_context=False, metadata_={},
        ),
        ServiceAssetDependency(
            id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
            service_id=first.id, asset_id=host.id, relationship_type_id=runs_on.id,
            required_for_operation=True, source="manual",
            valid_from=NOW - timedelta(days=1), valid_to=None,
        ),
        ServiceDependency(
            id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
            source_service_id=first.id, target_service_id=second.id,
            relationship_type_id=depends_on.id, required_for_operation=True,
            valid_from=NOW - timedelta(days=1), valid_to=None,
        ),
        ServiceBusinessFunction(
            id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
            service_id=first.id, business_function_id=business_function.id,
            relationship_type_id=supports.id, is_primary=True,
            valid_from=NOW - timedelta(days=1), valid_to=None,
        ),
    ]
    summary = KnowledgeCompletenessSummary(
        id=uuid.uuid4(), entity_type="service", entity_id=first.id,
        customer_id=customer_id, site_id=site_id,
        completeness_status="incomplete", open_gap_count=1,
    )
    gap = KnowledgeGap(
        id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
        requirement_definition_id=uuid.uuid4(), entity_type="service",
        entity_id=first.id, status="open", severity="high",
        requirement_level="required", summary="Owner missing",
        first_detected_at=NOW, last_evaluated_at=NOW, last_state_changed_at=NOW,
    )
    db, graph_builder = builder(
        service_type, criticality, asset_type, depends_on, runs_on, supports,
        first, second, host, storage, business_function, *rows, summary, gap,
    )
    graph = graph_builder.build(GraphProjectionRequest(
        focus_type="service", focus_id=first.id, max_depth=2,
    ))
    assert {edge.edge_family for edge in graph.edges} == {
        "asset_relationship", "service_asset", "service_service",
        "service_business_function",
    }
    service_node = next(node for node in graph.nodes if node.entity_id == first.id)
    assert (service_node.service_type_icon_key, service_node.service_type_accent_key) == ("database", "purple")
    asset_node = next(node for node in graph.nodes if node.entity_id == host.id)
    assert (asset_node.icon_key, asset_node.accent_key) == ("cloud", "rose")
    assert service_node.completeness_status == "incomplete"
    assert service_node.open_gap_count == 1
    assert service_node.criticality_key == "high"
    assert next(edge for edge in graph.edges if edge.edge_family == "service_asset").required_for_operation is True
    assert db.queries[("select", RelationshipType)] == 1
    assert db.queries[("select", KnowledgeCompletenessSummary)] == 1
    assert db.queries[("select", KnowledgeGap)] == 1
    assert sum(count for (kind, _), count in db.queries.items() if kind == "get") == 1


@pytest.mark.parametrize("depth", [1, 3])
def test_authorization_context_and_truncation_do_not_disclose_hidden_nodes(depth):
    customer_a, customer_b, site_a, site_b = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service_type, criticality, asset_type, depends_on, runs_on, supports = reference_records()
    item = service("Visible", customer_a, service_type, criticality, site_id=site_a)
    hidden = asset("Hidden", customer_b, site_b)
    edge = ServiceAssetDependency(
        id=uuid.uuid4(), customer_id=customer_a, site_id=site_a,
        service_id=item.id, asset_id=hidden.id, relationship_type_id=runs_on.id,
        required_for_operation=True, source="manual",
        valid_from=NOW - timedelta(days=1), valid_to=None,
    )
    db = GraphDatabase(
        service_type, criticality, asset_type, depends_on, runs_on, supports,
        item, hidden, edge,
    )
    scoped = principal(
        "assets.view", "services.view", "service_dependencies.view",
        customer_id=customer_a,
    )
    graph_builder = OperationalGraphBuilder(db, scoped, clock=lambda: NOW)
    graph = graph_builder.build(GraphProjectionRequest(
        focus_type="service", focus_id=item.id, max_depth=depth, node_limit=1,
        context=ActiveContext(customer_a, site_a),
    ))
    assert [node.name for node in graph.nodes] == ["Visible"]
    assert graph.edges == []
    assert graph.truncated is False
    assert graph.warnings == []

    with pytest.raises(GraphFocusNotFound):
        graph_builder.build(GraphProjectionRequest(
            focus_type="asset", focus_id=hidden.id,
            context=ActiveContext(customer_a, site_a),
        ))


@pytest.mark.parametrize("depth", [1, 3])
def test_accessible_limit_is_explicit_deterministic_and_has_no_dangling_edges(depth):
    customer_id, site_id = uuid.uuid4(), uuid.uuid4()
    service_type, criticality, asset_type, depends_on, runs_on, supports = reference_records()
    item = service("Focus", customer_id, service_type, criticality, site_id=site_id)
    first = asset("A", customer_id, site_id)
    second = asset("B", customer_id, site_id)
    rows = [
        ServiceAssetDependency(
            id=edge_id, customer_id=customer_id, site_id=site_id,
            service_id=item.id, asset_id=target.id, relationship_type_id=runs_on.id,
            required_for_operation=True, source="manual",
            valid_from=NOW - timedelta(days=1), valid_to=None,
        )
        for edge_id, target in sorted(
            [(uuid.uuid4(), first), (uuid.uuid4(), second)], key=lambda pair: str(pair[0])
        )
    ]
    _, graph_builder = builder(
        service_type, criticality, asset_type, depends_on, runs_on, supports,
        item, first, second, *rows,
    )
    graph = graph_builder.build(GraphProjectionRequest(
        focus_type="service", focus_id=item.id, max_depth=depth, node_limit=2,
        edge_families=frozenset({"service_asset"}),
    ))
    assert graph.truncated is True
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    keys = {node.key for node in graph.nodes}
    assert all(edge.source_key in keys and edge.target_key in keys for edge in graph.edges)


def test_limit_retains_later_legitimate_edges_between_existing_nodes():
    customer_id = uuid.uuid4()
    service_type, criticality, asset_type, depends_on, runs_on, supports = reference_records()
    first = service("First", customer_id, service_type, criticality)
    second = service("Second", customer_id, service_type, criticality)
    third = service("Third", customer_id, service_type, criticality)
    rows = [
        ServiceDependency(
            id=edge_id, customer_id=customer_id, site_id=None,
            source_service_id=source.id, target_service_id=target.id,
            relationship_type_id=depends_on.id, required_for_operation=True,
            valid_from=NOW - timedelta(days=1), valid_to=None,
        )
        for edge_id, source, target in (
            (uuid.UUID(int=1), first, second),
            (uuid.UUID(int=2), first, third),
            (uuid.UUID(int=3), second, first),
        )
    ]
    _, graph_builder = builder(
        service_type, criticality, asset_type, depends_on, runs_on, supports,
        first, second, third, *rows,
    )
    graph = graph_builder.build(GraphProjectionRequest(
        focus_type="service", focus_id=first.id, node_limit=2,
        edge_families=frozenset({"service_service"}),
    ))
    assert graph.truncated is True
    assert {edge.edge_id for edge in graph.edges} == {uuid.UUID(int=1), uuid.UUID(int=3)}


def test_compatibility_adapter_retains_existing_shape_and_route_registration():
    customer_id = uuid.uuid4()
    service_type, criticality, asset_type, depends_on, runs_on, supports = reference_records()
    first = service("First", customer_id, service_type, criticality)
    second = service("Second", customer_id, service_type, criticality)
    dependency = ServiceDependency(
        id=uuid.uuid4(), customer_id=customer_id, site_id=None,
        source_service_id=first.id, target_service_id=second.id,
        relationship_type_id=depends_on.id, required_for_operation=True,
        valid_from=NOW - timedelta(days=1), valid_to=None,
    )
    _, graph_builder = builder(
        service_type, criticality, asset_type, depends_on, runs_on, supports,
        first, second, dependency,
    )
    graph = graph_builder.build(GraphProjectionRequest(
        focus_type="service", focus_id=first.id,
        edge_families=frozenset({"service_service"}),
    ))
    legacy = operational_graph_to_service_graph(graph).model_dump()
    assert set(legacy) == {"nodes", "edges"}
    assert set(legacy["nodes"][0]) == {"id", "entity_type", "name", "subtitle", "href"}
    assert set(legacy["edges"][0]) == {"id", "source_id", "target_id", "label", "edge_type"}
    assert any(
        route.path == "/api/operational-graph" and "GET" in route.methods
        for route in app.routes
    )
    operation = app.openapi()["paths"]["/api/operational-graph"]["get"]
    assert "as_of" not in {parameter["name"] for parameter in operation["parameters"]}


def test_generic_route_serializes_contract_validates_limits_and_hides_cross_customer_focus():
    customer_a, customer_b, site_a, site_b = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service_type, criticality, asset_type, depends_on, runs_on, supports = reference_records()
    visible = asset("Visible", customer_a, site_a)
    hidden = asset("Hidden", customer_b, site_b)
    db = GraphDatabase(
        service_type, criticality, asset_type, depends_on, runs_on, supports,
        visible, hidden,
    )
    scoped = principal(
        "assets.view", "relationships.view", customer_id=customer_a
    )
    app.dependency_overrides[get_principal] = lambda: scoped
    app.dependency_overrides[get_active_context] = lambda: ActiveContext(customer_a, site_a)
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/operational-graph",
                params={"focus_type": "asset", "focus_id": str(visible.id), "max_depth": 0},
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["focus_key"] == f"asset:{visible.id}"
            assert payload["nodes"][0]["key"] == f"asset:{visible.id}"
            assert payload["nodes"][0]["entity_id"] == str(visible.id)
            assert "confidence" not in payload

            assert client.get(
                "/api/operational-graph",
                params={"focus_type": "asset", "focus_id": str(visible.id), "max_depth": 3},
            ).status_code == 200
            for invalid_depth in [-1, 4, 100]:
                assert client.get(
                    "/api/operational-graph",
                    params={"focus_type": "asset", "focus_id": str(visible.id), "max_depth": invalid_depth},
                ).status_code == 422

            hidden_response = client.get(
                "/api/operational-graph",
                params={"focus_type": "asset", "focus_id": str(hidden.id)},
            )
            assert hidden_response.status_code == 404
            assert str(hidden.id) not in hidden_response.text
            assert "Hidden" not in hidden_response.text

            assert client.get(
                "/api/operational-graph",
                params={"focus_type": "asset", "focus_id": str(visible.id), "node_limit": 501},
            ).status_code == 422
            assert client.get(
                "/api/operational-graph",
                params={"focus_type": "asset", "focus_id": str(visible.id), "edge_family": "unknown"},
            ).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_existing_service_and_business_function_routes_use_compatible_responses():
    customer_id, site_id = uuid.uuid4(), uuid.uuid4()
    service_type, criticality, asset_type, depends_on, runs_on, supports = reference_records()
    item = service("Atlas", customer_id, service_type, criticality, site_id=site_id)
    host = asset("LXC", customer_id, site_id)
    business_function = function("Administration", customer_id, criticality, site_id=site_id)
    dependency = ServiceAssetDependency(
        id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
        service_id=item.id, asset_id=host.id, relationship_type_id=runs_on.id,
        required_for_operation=True, source="manual",
        valid_from=NOW - timedelta(days=1), valid_to=None,
    )
    link = ServiceBusinessFunction(
        id=uuid.uuid4(), customer_id=customer_id, site_id=site_id,
        service_id=item.id, business_function_id=business_function.id,
        relationship_type_id=supports.id, is_primary=True,
        valid_from=NOW - timedelta(days=1), valid_to=None,
    )
    db = GraphDatabase(
        service_type, criticality, asset_type, depends_on, runs_on, supports,
        item, host, business_function, dependency, link,
    )
    viewer = principal(
        "assets.view", "relationships.view", "services.view",
        "service_dependencies.view", "business_functions.view",
    )
    app.dependency_overrides[get_principal] = lambda: viewer
    app.dependency_overrides[get_active_context] = lambda: ActiveContext(customer_id, site_id)
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            service_response = client.get(f"/api/services/{item.id}/graph")
            function_response = client.get(
                f"/api/business-functions/{business_function.id}/graph"
            )
        assert service_response.status_code == 200
        assert function_response.status_code == 200
        for response in (service_response, function_response):
            payload = response.json()
            assert set(payload) == {"nodes", "edges"}
            assert all(set(node) == {"id", "entity_type", "name", "subtitle", "href"} for node in payload["nodes"])
            assert all(set(edge) == {"id", "source_id", "target_id", "label", "edge_type"} for edge in payload["edges"])
        assert {edge["edge_type"] for edge in service_response.json()["edges"]} == {
            "service_asset", "service_business_function"
        }
        assert {edge["edge_type"] for edge in function_response.json()["edges"]} == {
            "service_asset", "service_business_function"
        }
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("direction", ["incoming", "outgoing", "both"])
def test_third_hop_preserves_cycles_ordering_and_canonical_direction(direction):
    customer = uuid.uuid4()
    refs = reference_records()
    services = [service(f"Service {i}", customer, refs[0], refs[1]) for i in range(5)]
    rows = [ServiceDependency(
        id=uuid.uuid4(), customer_id=customer, site_id=None,
        source_service_id=services[i].id, target_service_id=services[(i + 1) % 5].id,
        relationship_type_id=refs[3].id, required_for_operation=True,
        valid_from=NOW, valid_to=None,
    ) for i in range(5)]
    _, graph_builder = builder(*refs, *services, *rows)
    request = GraphProjectionRequest(focus_type="service", focus_id=services[0].id, max_depth=3, direction=direction)
    graph = graph_builder.build(request)
    assert graph == graph_builder.build(request)
    _, reversed_builder = builder(*reversed([*refs, *services, *rows]))
    assert graph == reversed_builder.build(request)
    expected = {"outgoing": [0, 1, 2, 3], "incoming": [0, 4, 3, 2], "both": list(range(5))}[direction]
    assert {node.entity_id for node in graph.nodes} == {services[i].id for i in expected}
    assert len({node.key for node in graph.nodes}) == len(graph.nodes)
    assert len({edge.key for edge in graph.edges}) == len(graph.edges)
    for edge in graph.edges:
        row = next(row for row in rows if row.id == edge.edge_id)
        assert edge.source_key == f"service:{row.source_service_id}"
        assert edge.target_key == f"service:{row.target_service_id}"
    for depth in [-1, 4]:
        with pytest.raises(ValueError, match="between 0 and 3"):
            graph_builder.build(GraphProjectionRequest(focus_type="service", focus_id=services[0].id, max_depth=depth))


@pytest.mark.parametrize("boundary", ["node_limit", "customer", "future", "ended"])
def test_third_hop_obeys_limits_scope_and_temporal_boundaries(boundary):
    customer, site = uuid.uuid4(), uuid.uuid4()
    refs = reference_records()
    services = [service(f"Hop {i}", customer, refs[0], refs[1], site_id=site) for i in range(4)]
    rows = [ServiceDependency(
        id=uuid.uuid4(), customer_id=customer, site_id=site,
        source_service_id=services[i].id, target_service_id=services[i + 1].id,
        relationship_type_id=refs[3].id, required_for_operation=True,
        valid_from=NOW, valid_to=None,
    ) for i in range(3)]
    if boundary == "customer":
        services[-1].customer_id = uuid.uuid4()
    elif boundary == "future":
        rows[-1].valid_from = NOW + timedelta(seconds=1)
    elif boundary == "ended":
        rows[-1].valid_to = NOW
    db = GraphDatabase(*refs, *services, *rows)
    graph_builder = OperationalGraphBuilder(db, principal("services.view", "service_dependencies.view", customer_id=customer), clock=lambda: NOW)
    request = GraphProjectionRequest(
        focus_type="service", focus_id=services[0].id, max_depth=3,
        direction="outgoing", context=ActiveContext(customer, site),
        node_limit=3 if boundary == "node_limit" else 250,
    )
    graph = graph_builder.build(request)
    assert graph == graph_builder.build(request)
    assert {node.entity_id for node in graph.nodes} == {item.id for item in services[:3]}
    assert {edge.edge_id for edge in graph.edges} == {row.id for row in rows[:2]}
    assert graph.truncated is (boundary == "node_limit")
    assert str(services[-1].id) not in graph.model_dump_json()
