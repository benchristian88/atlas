"""C2.4 Site viewpoint, bounded landscape and metadata regression tests."""
import os
import time
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session

from app.authorization import ActiveContext, Principal, get_active_context, get_principal
from app.database import get_db
from app.main import app
from app.models import AssetInterface, Customer, Network, ServiceAssetDependency, ServiceBusinessFunction, ServiceDependency, Site, Workspace
from app.services.operational_graph import GraphFocusNotFound, OperationalGraphBuilder
from tests.test_operational_graph import NOW, GraphDatabase, asset, builder, function, principal, reference_records, service

PERMISSIONS = ("assets.view", "services.view", "business_functions.view", "service_dependencies.view", "relationships.view", "networks.view")


def topology():
    customer, local_site, remote_site, other_customer = [uuid.uuid4() for _ in range(4)]
    refs = reference_records()
    svc = service("Customer-wide DNS", customer, refs[0], refs[1])
    local = asset("Local host", customer, local_site)
    remote = asset("Remote DNS provider", customer, remote_site)
    unrelated = asset("Unrelated remote host", customer, remote_site)
    foreign = asset("Hidden other Customer", other_customer, uuid.uuid4())
    edge = ServiceAssetDependency(id=uuid.uuid4(), customer_id=customer, site_id=None, service_id=svc.id, asset_id=remote.id, relationship_type_id=refs[3].id, required_for_operation=True, source="manual", valid_from=NOW - timedelta(days=1), valid_to=None)
    records = [*refs, svc, local, remote, unrelated, foreign, edge]
    return records, ActiveContext(customer, local_site), svc, remote, edge


def test_landscape_includes_only_direct_authorized_cross_site_provider():
    records, context, svc, remote, edge = topology()
    _, projection = builder(*records)
    graph = projection.landscape(context)
    assert {n.name for n in graph.nodes} == {"Customer-wide DNS", "Local host", "Remote DNS provider"}
    assert {e.edge_id for e in graph.edges} == {edge.id}
    assert graph.edges[0].source_key == f"service:{svc.id}"
    assert graph.edges[0].target_key == f"asset:{remote.id}"
    assert not graph.truncated


def test_site_assignment_does_not_gain_customer_wide_or_remote_access():
    records, context, *_ = topology()
    viewer = principal(*PERMISSIONS, customer_id=context.customer_id, site_id=context.site_id)
    graph = OperationalGraphBuilder(GraphDatabase(*records), viewer, clock=lambda: NOW).landscape(context)
    assert [n.name for n in graph.nodes] == ["Local host"]
    assert graph.edges == []


def test_mixed_grants_hide_remote_provider_without_leaking_counts():
    records, context, *_ = topology()
    service_view = principal("services.view", "service_dependencies.view", customer_id=context.customer_id)
    asset_view = principal("assets.view", customer_id=context.customer_id, site_id=context.site_id)
    viewer = Principal(user=service_view.user, grants=service_view.grants + asset_view.grants)
    graph = OperationalGraphBuilder(GraphDatabase(*records), viewer, clock=lambda: NOW).landscape(context)
    assert {n.name for n in graph.nodes} == {"Customer-wide DNS", "Local host"}
    assert graph.edges == []
    assert graph.warnings == []


def test_landscape_preserves_temporal_eligibility_and_customer_boundary():
    records, context, _, remote, edge = topology()
    for mode in ("ended", "future", "other_customer"):
        edge.valid_from, edge.valid_to = NOW - timedelta(days=1), None
        remote.customer_id = context.customer_id
        if mode == "ended": edge.valid_to = NOW
        if mode == "future": edge.valid_from = NOW + timedelta(seconds=1)
        if mode == "other_customer": remote.customer_id = uuid.uuid4()
        _, projection = builder(*records)
        graph = projection.landscape(context)
        assert "Remote DNS provider" not in {n.name for n in graph.nodes}
        assert graph.edges == []


def test_landscape_requires_explicit_viewpoint_and_bounded_output():
    records, context, *_ = topology()
    _, projection = builder(*records)
    with pytest.raises(GraphFocusNotFound): projection.landscape(ActiveContext(context.customer_id, None))
    graph = projection.landscape(context, node_limit=2)
    assert graph.truncated
    assert len(graph.nodes) == 2
    keys = {n.key for n in graph.nodes}
    assert all(e.source_key in keys and e.target_key in keys for e in graph.edges)


def test_graph_viewpoint_is_opt_in_and_deep_links_do_not_disclose_other_customers():
    records, context, _, remote, _ = topology()
    app.dependency_overrides[get_db] = lambda: GraphDatabase(*records)
    app.dependency_overrides[get_principal] = lambda: principal(*PERMISSIONS)
    app.dependency_overrides[get_active_context] = lambda: context
    try:
        client = TestClient(app)
        path = f"/api/operational-graph?focus_type=asset&focus_id={remote.id}"
        assert client.get(path).status_code == 404
        assert client.get(path + "&site_viewpoint=true").status_code == 200
        app.dependency_overrides[get_active_context] = lambda: ActiveContext(None, None)
        assert client.get(path + "&site_viewpoint=true").status_code == 404
        assert client.post("/api/dependency-analysis?site_viewpoint=true", json={"focus_type": "asset", "focus_id": str(remote.id)}).status_code == 404
        app.dependency_overrides[get_active_context] = lambda: context
        remote.customer_id = uuid.uuid4()
        response = client.get(path + "&site_viewpoint=true")
        assert response.status_code == 404
        assert response.json() == {"detail": "Record not found"}
        response = client.post("/api/dependency-analysis?site_viewpoint=true", json={"focus_type": "asset", "focus_id": str(remote.id)})
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_asset_inspector_uses_interface_ip_and_authorizes_vlan():
    records, context, _, remote, _ = topology()
    network = Network(id=uuid.uuid4(), customer_id=context.customer_id, site_id=remote.site_id, name="Provider network", vlan_id=42)
    interface = AssetInterface(id=uuid.uuid4(), asset_id=remote.id, network_id=network.id, name="eth0", ip_address="192.0.2.53", is_primary=True)
    remote.ip_address = "192.0.2.99"
    site = Site(id=remote.site_id, customer_id=context.customer_id, name="Remote lab")
    _, projection = builder(*records, network, interface, site, permissions=PERMISSIONS)
    node = next(n for n in projection.landscape(context).nodes if n.entity_id == remote.id)
    assert node.contextual_ip == "192.0.2.53"
    assert node.contextual_vlan == 42
    assert node.site_name == "Remote lab"
    _, projection = builder(*records, network, interface, site, permissions=PERMISSIONS[:-1])
    node = next(n for n in projection.landscape(context).nodes if n.entity_id == remote.id)
    assert node.contextual_vlan is None


@pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")
def test_postgres_dense_landscape_is_batched_read_only_and_tenant_safe():
    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"])
    with Session(engine) as db:
        refs = []
        for row in reference_records():
            existing = db.scalar(select(type(row)).where(type(row).key == row.key))
            refs.append(existing or row)
            if existing is None: db.add(row)
        db.flush()
        workspace = Workspace(id=uuid.uuid4(), name="C2.4 test", slug=f"c24-{uuid.uuid4()}")
        db.add(workspace); db.flush()
        customer = Customer(id=uuid.uuid4(), workspace_id=workspace.id, name="C2.4 test")
        db.add(customer); db.flush()
        local = Site(id=uuid.uuid4(), customer_id=customer.id, name="Local")
        remote = Site(id=uuid.uuid4(), customer_id=customer.id, name="Remote")
        db.add_all([local, remote]); db.flush()
        services = [service(f"Service {i:02}", customer.id, refs[0], refs[1]) for i in range(40)]
        assets = [asset(f"Asset {i:03}", customer.id, local.id if i < 149 else remote.id) for i in range(150)]
        functions = [function(f"Function {i:02}", customer.id, refs[1]) for i in range(20)]
        for row in assets: row.workspace_id = workspace.id; row.asset_type = refs[2].key
        db.add_all([*services, *assets, *functions]); db.flush()
        links = [ServiceAssetDependency(id=uuid.uuid4(), customer_id=customer.id, site_id=None, service_id=services[i % 40].id, asset_id=row.id, relationship_type_id=refs[3].id, required_for_operation=True, source="manual", valid_from=NOW - timedelta(days=1)) for i, row in enumerate(assets)]
        links += [ServiceBusinessFunction(id=uuid.uuid4(), customer_id=customer.id, site_id=None, service_id=row.id, business_function_id=functions[i % 20].id, relationship_type_id=refs[5].id, valid_from=NOW - timedelta(days=1)) for i, row in enumerate(services)]
        links += [ServiceDependency(id=uuid.uuid4(), customer_id=customer.id, site_id=None, source_service_id=row.id, target_service_id=services[(i + 1) % 40].id, relationship_type_id=refs[3].id, required_for_operation=True, valid_from=NOW - timedelta(days=1)) for i, row in enumerate(services)]
        db.add_all(links); db.commit()
        queries = []
        def collect(conn, cursor, statement, parameters, context, executemany): queries.append(statement)
        event.listen(engine, "before_cursor_execute", collect)
        try:
            db.execute(text("SET TRANSACTION READ ONLY"))
            start = time.perf_counter()
            result = OperationalGraphBuilder(db, principal(*PERMISSIONS), clock=lambda: NOW).landscape(ActiveContext(customer.id, local.id))
            elapsed = time.perf_counter() - start
            assert len(result.nodes) == 210
            assert len(result.edges) == 230
            assert not result.truncated
            assert all(n.customer_id == customer.id for n in result.nodes)
            assert len(queries) < 30, len(queries)
            assert not any(q.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries)
            print(f"C2.4 PostgreSQL: 210 nodes, 230 edges, {len(queries)} statements, {elapsed:.4f}s")
            restricted = OperationalGraphBuilder(db, principal(*PERMISSIONS, customer_id=customer.id, site_id=local.id), clock=lambda: NOW).landscape(ActiveContext(customer.id, local.id))
            assert len(restricted.nodes) == 149
            assert restricted.edges == []
        finally:
            event.remove(engine, "before_cursor_execute", collect)
            db.rollback()
    engine.dispose()
