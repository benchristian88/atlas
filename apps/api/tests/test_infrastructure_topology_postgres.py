"""Opt-in tests against a disposable Alembic-migrated PostgreSQL database."""
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.authorization import ActiveContext, Principal, ScopeGrant, get_principal
from app.database import get_db
from app.main import app
from app.models import Asset, AssetCategory, AssetInterface, AssetRelationship, AssetType, Customer, Network, Site, Workspace, UNCATEGORIZED_ID
from app.routes.topology import get_topology
from app.schemas import TopologyResponse
from app.services.infrastructure_topology import connectivity
from tests.test_administration import make_principal

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")


@pytest.fixture
def db():
    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"])
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()
    engine.dispose()


@pytest.fixture
def client(db):
    principal = make_principal("asset_types.view", "asset_types.manage", "assets.view")
    db.add(principal.user)
    db.flush()
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_category_and_docker_compose_lifecycle(client, db):
    result = client.post("/api/asset-categories", json={"key": "test_workload", "name": "Workload"})
    assert result.status_code == 201, result.text
    category = result.json()
    assert category["show_in_topology"] and category["asset_types_count"] == 0
    assert client.patch(f"/api/asset-categories/{category['id']}", json={"key": "changed"}).status_code == 422
    assert client.post("/api/asset-types", json={"key": "docker_compose", "name": "Docker Compose"}).status_code == 422
    result = client.post("/api/asset-types", json={"key": "docker_compose", "name": "Docker Compose", "category_id": category["id"]})
    assert result.status_code == 201, result.text
    asset_type = result.json()
    assert asset_type["category"] == "Workload" and asset_type["category_key"] == "test_workload"
    assert client.delete(f"/api/asset-categories/{category['id']}").status_code == 409
    updated = client.patch(f"/api/asset-categories/{category['id']}", json={"name": "Custom Workloads", "active": False, "show_in_topology": False})
    assert updated.status_code == 200 and updated.json()["asset_types_count"] == 1
    assert client.patch(f"/api/asset-types/{asset_type['id']}", json={"category_id": category["id"], "description": "Still valid"}).status_code == 200
    assert client.post("/api/asset-types", json={"key": "other_type", "name": "Other type", "category_id": category["id"]}).status_code == 422
    assert client.patch(f"/api/asset-types/{asset_type['id']}", json={"category_id": None}).status_code == 422
    result = client.patch(f"/api/asset-types/{asset_type['id']}", json={"category_id": str(UNCATEGORIZED_ID)})
    assert result.status_code == 200 and result.json()["category"] == "Uncategorized"
    assert client.delete(f"/api/asset-categories/{category['id']}").status_code == 204
    categories = client.get("/api/asset-categories").json()
    fallback = next(c for c in categories if c["key"] == "uncategorized")
    assert fallback["active"] and not fallback["show_in_topology"]
    assert client.delete(f"/api/asset-categories/{UNCATEGORIZED_ID}").status_code == 409
    assert client.patch(f"/api/asset-categories/{UNCATEGORIZED_ID}", json={"active": False}).status_code == 409
    assert client.patch(f"/api/asset-categories/{UNCATEGORIZED_ID}", json={"name": "Changed"}).status_code == 409
    assert db.scalar(select(AssetType).where(AssetType.id == uuid.UUID(asset_type["id"]))).category_id == UNCATEGORIZED_ID


def test_reference_permissions_and_scoped_manage_cannot_change_global_taxonomy(client, db):
    user = make_principal("assets.view")
    app.dependency_overrides[get_principal] = lambda: user
    assert client.get("/api/asset-categories").status_code == 403
    assert client.post("/api/asset-categories", json={"key": "custom", "name": "Custom"}).status_code == 403
    grant = ScopeGrant(assignment_id=uuid.uuid4(), role_id=uuid.uuid4(), role_name="Scoped", scope_type="customer", customer_id=uuid.uuid4(), site_id=None, permissions=frozenset({"asset_types.view", "asset_types.manage"}))
    app.dependency_overrides[get_principal] = lambda: Principal(user.user, (grant,))
    assert client.get("/api/asset-categories").status_code == 200
    assert client.post("/api/asset-categories", json={"key": "custom", "name": "Custom"}).status_code == 403


def seed_scope(db):
    workspace = Workspace(name="Topology test", slug=f"topology-{uuid.uuid4()}")
    db.add(workspace); db.flush()
    customers = [Customer(workspace_id=workspace.id, name=n) for n in ("Visible customer", "Hidden customer")]
    db.add_all(customers); db.flush()
    sites = [Site(customer_id=customers[0].id, name="Visible Site"), Site(customer_id=customers[0].id, name="Hidden Site"), Site(customer_id=customers[1].id, name="Other Customer Site")]
    db.add_all(sites); db.flush()
    assets = [Asset(workspace_id=workspace.id, customer_id=site.customer_id, site_id=site.id, name=name, asset_type="server") for site, name in ((sites[0], "AdGuard Home"), (sites[0], "PVE1"), (sites[1], "Hidden host"), (sites[2], "Other customer host"))]
    db.add_all(assets); db.flush()
    networks = [Network(customer_id=site.customer_id, site_id=site.id, name=name, network_type="vlan", vlan_id=vlan, gateway="10.0.99.1") for site, name, vlan in ((sites[0], "Management", 99), (sites[1], "Secret Network", 123), (sites[0], "Apps", 10))]
    db.add_all(networks); db.flush()
    db.add_all([AssetInterface(asset_id=assets[0].id, network_id=networks[0].id, name="eth0", ip_address="10.0.99.5"), AssetInterface(asset_id=assets[0].id, network_id=networks[1].id, name="legacy", ip_address="10.0.123.5"), AssetInterface(asset_id=assets[0].id, network_id=networks[2].id, name="eth1"), AssetInterface(asset_id=assets[2].id, network_id=networks[0].id, name="hidden-interface")])
    db.add_all([AssetRelationship(customer_id=sites[0].customer_id, site_id=sites[0].id, source_asset_id=assets[0].id, target_asset_id=target.id, relationship_type="runs_on") for target in assets[1:]])
    db.flush()
    return sites, assets, networks


def test_authorized_topology_counts_endpoints_context_and_network_non_disclosure(db):
    sites, assets, networks = seed_scope(db)
    base = make_principal("relationships.view", "networks.view", "sites.view", "customers.view")
    scoped = ScopeGrant(assignment_id=uuid.uuid4(), role_id=uuid.uuid4(), role_name="Site", scope_type="site", customer_id=sites[0].customer_id, site_id=sites[0].id, permissions=frozenset({"assets.view", "networks.view", "sites.view", "customers.view"}))
    # Global relationships permission must not disclose Assets outside assets.view.
    global_relationships = make_principal("relationships.view").grants[0]
    principal = Principal(base.user, (scoped, global_relationships))
    topology = get_topology(ActiveContext(None, None), principal, db)
    TopologyResponse.model_validate(topology)
    assert {a["id"] for a in topology["assets"]} == {a.id for a in assets[:2]}
    assert len(topology["relationships"]) == 1 and len(topology["platform_links"]) == 1
    assert len(topology["asset_interfaces"]) == 3
    assert next(i for i in topology["asset_interfaces"] if i["name"] == "legacy")["network_id"] is None
    assert networks[1].id not in {n["id"] for n in topology["networks"]}
    assert assets[2].name not in str(topology) and str(assets[2].id) not in str(topology)
    graph = connectivity(topology, assets[0].id, hops=2)
    assert len(graph["nodes"]) == 4
    assert "Secret" not in str(graph) and "10.0.99.1" not in str(graph)
    assert get_topology(ActiveContext(sites[2].customer_id, sites[2].id), principal, db)["assets"] == []
    # No Network permission means no interfaces or membership counts.
    asset_only = Principal(base.user, (ScopeGrant(assignment_id=uuid.uuid4(), role_id=uuid.uuid4(), role_name="Asset only", scope_type="global", customer_id=None, site_id=None, permissions=frozenset({"assets.view"})),))
    projection = get_topology(ActiveContext(None, None), asset_only, db)
    assert projection["networks"] == projection["asset_interfaces"] == projection["relationships"] == []


def test_assets_category_filter_uses_managed_ids(client, db):
    sites, assets, _ = seed_scope(db)
    category_id = db.scalar(select(AssetType.category_id).where(AssetType.key == "server"))
    scope = f"customer_id={sites[0].customer_id}&site_id={sites[0].id}"
    response = client.get(f"/api/assets?category_id={category_id}&{scope}")
    assert response.status_code == 200
    assert {a["id"] for a in response.json()} == {str(a.id) for a in assets[:2]}
    assert client.get(f"/api/assets?category_id={UNCATEGORIZED_ID}&{scope}").json() == []


def test_interface_ip_search_scope_duplicates_and_legacy_exclusion(client, db):
    sites, assets, networks = seed_scope(db)
    assets[1].ip_address = "192.0.2.231"
    db.add(AssetInterface(asset_id=assets[0].id, name="duplicate-ip", ip_address="10.0.99.5"))
    db.add(AssetInterface(asset_id=assets[2].id, name="secret-ip", ip_address="192.0.2.232"))
    db.flush()
    # Interface presence must not become an oracle for assets-only users.
    assert client.get("/api/assets?search=10.0.99.5").json() == []
    actor = make_principal("assets.view", "networks.view")
    app.dependency_overrides[get_principal] = lambda: actor
    response = client.get("/api/assets?search=10.0.99.5&limit=1&offset=0")
    assert response.status_code == 200, response.text
    assert [a["id"] for a in response.json()] == [str(assets[0].id)]
    assert client.get("/api/assets?search=10.0.99.5&limit=1&offset=1").json() == []
    assert client.get("/api/assets?search=192.0.2.231").json() == []
    scope = f"customer_id={sites[0].customer_id}&site_id={sites[0].id}"
    assert client.get(f"/api/assets?search=192.0.2.232&{scope}").json() == []
    grant = ScopeGrant(assignment_id=uuid.uuid4(), role_id=uuid.uuid4(), role_name="Site", scope_type="site", customer_id=sites[0].customer_id, site_id=sites[0].id, permissions=frozenset({"assets.view", "networks.view"}))
    app.dependency_overrides[get_principal] = lambda: Principal(actor.user, (grant,))
    assert client.get("/api/assets?search=192.0.2.232").json() == []
    assert len(client.get("/api/assets?search=10.0.99.5").json()) == 1
    visible = client.get(f"/api/topology/connectivity?focus_network_id={networks[0].id}")
    assert visible.status_code == 200, visible.text
    assert {n["entity_id"] for n in visible.json()["nodes"]} == {str(networks[0].id), str(assets[0].id)}
    assert client.get(f"/api/topology/connectivity?focus_network_id={networks[1].id}").status_code == 404
    assert client.get(f"/api/topology/connectivity?focus_network_id={uuid.uuid4()}").status_code == 404
    assert client.get("/api/topology/connectivity").status_code == 422
    assert client.get(f"/api/topology/connectivity?focus_network_id={networks[0].id}&focus_asset_id={assets[0].id}").status_code == 422


def test_category_preview_source_count_excludes_other_sites(db):
    sites, assets, _ = seed_scope(db)
    db.add_all([Asset(workspace_id=assets[0].workspace_id, customer_id=sites[0].customer_id, site_id=sites[0].id, name=f"Visible {i:02}", asset_type="server") for i in range(23)])
    db.flush()
    actor = make_principal("assets.view")
    grant = ScopeGrant(assignment_id=uuid.uuid4(), role_id=uuid.uuid4(), role_name="Site", scope_type="site", customer_id=sites[0].customer_id, site_id=sites[0].id, permissions=frozenset({"assets.view"}))
    data = get_topology(ActiveContext(None, None), Principal(actor.user, (grant,)), db)
    assert len(data["assets"]) == 25
    assert all(a["site_id"] == sites[0].id for a in data["assets"])
    assert len(data["assets"][6:]) == 19


@pytest.mark.parametrize("route", ["assets", "manual-assets"])
def test_legacy_ip_api_compatibility_and_interface_first_acceptance(client, db, route):
    sites, assets, _ = seed_scope(db)
    actor = make_principal("assets.view", "assets.create", "assets.edit", "networks.view", "networks.create")
    actor = Principal(app.dependency_overrides[get_principal]().user, actor.grants)
    app.dependency_overrides[get_principal] = lambda: actor
    result = client.post(f"/api/{route}", json={
        "customer_id": str(sites[0].customer_id), "site_id": str(sites[0].id),
        "name": "AdGuard Home", "asset_type": "server", "ip_address": "192.0.2.254",
    })
    assert result.status_code == 201, result.text
    record = result.json()
    assert record["ip_address"] == "192.0.2.254"
    url = f"/api/{route}/{record['id']}"
    # Ordinary web edits omit the deprecated field and preserve stored history.
    result = client.patch(url, json={"description": "Updated without legacy IP"})
    assert result.status_code == 200, result.text
    assert result.json()["ip_address"] == "192.0.2.254"
    assert client.get(url).json()["ip_address"] == "192.0.2.254"
    for name, address in (("eth0", "192.168.99.5"), ("eth1", "192.168.5.5")):
        response = client.post("/api/asset-interfaces", json={
            "asset_id": record["id"], "name": name, "ip_address": address, "is_primary": name == "eth0",
        })
        assert response.status_code == 201, response.text
        assert [a["id"] for a in client.get(f"/api/assets?search={address}").json()] == [record["id"]]
    assert client.get("/api/assets?search=192.0.2.254").json() == []
    interfaces = client.get(f"/api/asset-interfaces?asset_id={record['id']}").json()
    assert {(i["name"], i["ip_address"]) for i in interfaces} == {("eth0", "192.168.99.5"), ("eth1", "192.168.5.5")}
    # External clients retain explicit legacy updates and clearing.
    for address in ("192.0.2.253", None):
        result = client.patch(url, json={"ip_address": address})
        assert result.status_code == 200, result.text
        assert result.json()["ip_address"] == address
    assert len(client.get(f"/api/asset-interfaces?asset_id={record['id']}").json()) == 2


@pytest.mark.parametrize("term", ["AdGuard Home", "adg", "dns.homelab.test", "dns.home", "192.168.5.3", "192.168.5"])
def test_focus_finder_source_and_asset_search_fields(client, db, term):
    sites, assets, _ = seed_scope(db)
    assets[0].hostname = "dns.homelab.test"
    assets[0].ip_address = None
    db.add(AssetInterface(asset_id=assets[0].id, name="search-ip", ip_address="192.168.5.3"))
    db.flush()
    actor = make_principal("assets.view", "networks.view", "customers.view", "sites.view")
    app.dependency_overrides[get_principal] = lambda: actor
    headers = {"X-Atlas-Customer-ID": str(sites[0].customer_id), "X-Atlas-Site-ID": str(sites[0].id)}
    response = client.get("/api/assets", params={"search": term, "limit": 10}, headers=headers)
    assert response.status_code == 200, response.text
    assert [a["id"] for a in response.json()] == [str(assets[0].id)]
    source = client.get("/api/topology", headers=headers)
    assert source.status_code == 200, source.text
    assert {a["id"] for a in source.json()["assets"]} == {str(a.id) for a in assets[:2]}
    assert any(i["ip_address"] == "192.168.5.3" for i in source.json()["asset_interfaces"])


@pytest.mark.parametrize("scope", ["context", "grant"])
def test_focus_finder_non_disclosure_by_name_hostname_and_ip(client, db, scope):
    sites, assets, _ = seed_scope(db)
    for index, asset in enumerate(assets):
        asset.hostname = f"host-{index}.private.test"
        db.add(AssetInterface(asset_id=asset.id, name="search", ip_address=f"192.168.5.{index + 1}"))
    db.flush()
    actor = make_principal("assets.view", "networks.view", "customers.view", "sites.view")
    headers = {}
    if scope == "grant":
        actor = Principal(actor.user, (ScopeGrant(assignment_id=uuid.uuid4(), role_id=uuid.uuid4(), role_name="Site", scope_type="site", customer_id=sites[0].customer_id, site_id=sites[0].id, permissions=frozenset({"assets.view", "networks.view", "customers.view", "sites.view"})),))
    else:
        headers = {"X-Atlas-Customer-ID": str(sites[0].customer_id), "X-Atlas-Site-ID": str(sites[0].id)}
    app.dependency_overrides[get_principal] = lambda: actor
    for index in [2, 3]:
        for term in [assets[index].name, assets[index].hostname, f"192.168.5.{index + 1}", "no-such-asset"]:
            response = client.get("/api/assets", params={"search": term}, headers=headers)
            assert response.status_code == 200, response.text
            assert response.json() == []
        projection = client.get("/api/topology", headers=headers)
        assert projection.status_code == 200, projection.text
        assert assets[index].name not in projection.text
        assert assets[index].hostname not in projection.text
        assert f"192.168.5.{index + 1}" not in projection.text
        response = client.get("/api/topology/connectivity", params={"focus_asset_id": str(assets[index].id)}, headers=headers)
        assert response.status_code == 404


@pytest.mark.parametrize("child_count", [18, 120])
@pytest.mark.parametrize("hops", [2, 3])
def test_connectivity_api_capacity_and_child_counts_respect_scope(client, db, child_count, hops):
    sites, assets, _ = seed_scope(db)
    parent = assets[1]
    children = [Asset(workspace_id=parent.workspace_id, customer_id=parent.customer_id,
        site_id=parent.site_id, asset_type="server", name=f"Workload {i:03}") for i in range(child_count - 1)]
    db.add_all(children); db.flush()
    # Even global relationship permission cannot disclose hidden child endpoints.
    db.add_all([AssetRelationship(customer_id=parent.customer_id, site_id=parent.site_id,
        source_asset_id=child.id, target_asset_id=parent.id, relationship_type="runs_on")
        for child in children + assets[2:]])
    db.flush()
    actor = make_principal("relationships.view")
    scoped = ScopeGrant(assignment_id=uuid.uuid4(), role_id=uuid.uuid4(), role_name="Site",
        scope_type="site", customer_id=parent.customer_id, site_id=parent.site_id,
        permissions=frozenset({"assets.view", "networks.view"}))
    app.dependency_overrides[get_principal] = lambda: Principal(actor.user, (*actor.grants, scoped))
    url = f"/api/topology/connectivity?focus_asset_id={parent.id}&hops={hops}"
    response = client.get(url)
    assert response.status_code == 200, response.text
    graph = response.json()
    assert graph["node_limit"] == 100 and graph["edge_limit"] == 500
    focus = next(n for n in graph["nodes"] if n["key"] == graph["focus_key"])
    assert focus["eligible_child_count"] == child_count
    assert focus["returned_child_count"] == min(child_count, 99)
    assert graph["truncated"] == (child_count > 99)
    assert len(graph["nodes"]) <= 100 and len(graph["edges"]) <= 500
    assert all(str(a.id) not in str(graph) for a in assets[2:])
    filtered = client.get(url + "&topology_classes=physical_network").json()
    assert filtered["nodes"][0]["eligible_child_count"] == 0
    assert client.get(url + "&limit=101").status_code == 422
    assert client.get(url + "&limit=25").json()["node_limit"] == 25
    assert client.get(f"/api/topology/connectivity?focus_asset_id={assets[2].id}").status_code == 404
