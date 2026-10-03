"""Presentation writes use the real existing lifecycle and authorization routes."""
import os
import uuid

import pytest

from app.authorization import Principal, ScopeGrant, get_principal
from app.main import app
from app.models import UNCATEGORIZED_ID, AssetInterface
from tests.test_administration import make_principal
from tests.test_infrastructure_topology_postgres import db, client, seed_scope

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")


def test_category_presentation_create_edit_lifecycle_and_projection(client, db):
    result = client.post("/api/asset-categories", json={"key": "home_automation", "name": "Home Automation", "icon_key": "home", "accent_key": "teal"})
    assert result.status_code == 201, result.text
    record = result.json()
    assert (record["icon_key"], record["accent_key"]) == ("home", "teal")
    url = f"/api/asset-categories/{record['id']}"
    assert client.patch(url, json={"icon_key": "cube", "accent_key": "green"}).status_code == 200
    record = client.patch(url, json={"name": "Renamed", "show_in_topology": False, "active": False}).json()
    assert (record["icon_key"], record["accent_key"]) == ("cube", "green")
    projected = next(c for c in client.get("/api/topology").json()["categories"] if c["id"] == record["id"])
    assert projected["accent_key"] == "green" and not projected["show_in_topology"]
    for field in ("icon_key", "accent_key"):
        assert client.patch(url, json={field: "arbitrary"}).status_code == 422
        assert client.post("/api/asset-categories", json={"key": "invalid", "name": "Invalid", field: "arbitrary"}).status_code == 422
    fallback = next(c for c in client.get("/api/asset-categories").json() if c["id"] == str(UNCATEGORIZED_ID))
    assert (fallback["icon_key"], fallback["accent_key"]) == ("infrastructure", "slate")
    defaults = client.post("/api/asset-categories", json={"key": "defaults", "name": "Defaults"}).json()
    assert (defaults["icon_key"], defaults["accent_key"]) == ("infrastructure", "slate")
    assert client.delete(url).status_code == 204


def test_network_presentation_defaults_edits_membership_and_scope(client, db):
    sites, assets, _ = seed_scope(db)
    principal = make_principal("networks.view", "networks.create", "networks.edit", "networks.delete", "assets.view")
    principal.user.email = "network-presentation@example.test"
    db.add(principal.user); db.flush()
    app.dependency_overrides[get_principal] = lambda: principal
    payload = {"customer_id": str(sites[0].customer_id), "site_id": str(sites[0].id), "name": "Custom Network", "network_type": "vlan", "vlan_id": 99, "cidr": "10.10.99.8/24", "gateway": "10.10.99.1"}
    response = client.post("/api/networks", json=payload)
    assert response.status_code == 201, response.text
    record = response.json()
    assert (record["icon_key"], record["accent_key"]) == ("network", "blue")
    url = f"/api/networks/{record['id']}"
    assert client.patch(url, json={"icon_key": "shield"}).json()["icon_key"] == "shield"
    result = client.patch(url, json={"accent_key": "rose"}).json()
    assert (result["icon_key"], result["accent_key"], result["vlan_id"], result["cidr"], result["gateway"]) == ("shield", "rose", 99, "10.10.99.0/24", "10.10.99.1")
    chosen = client.post("/api/networks", json={**payload, "name": "Chosen", "icon_key": "cloud", "accent_key": "purple"})
    assert chosen.status_code == 201 and chosen.json()["accent_key"] == "purple"
    for field in ("icon_key", "accent_key"):
        assert client.patch(url, json={field: "arbitrary"}).status_code == 422
        assert client.post("/api/networks", json={**payload, field: "arbitrary"}).status_code == 422
    db.add(AssetInterface(asset_id=assets[0].id, network_id=uuid.UUID(record["id"]), name="presentation-test", ip_address="10.10.99.8")); db.flush()
    assert client.delete(url).status_code == 409
    topology = client.get("/api/topology").json()
    assert next(n for n in topology["networks"] if n["id"] == record["id"])["accent_key"] == "rose"
    assert any(i["network_id"] == record["id"] and i["ip_address"] == "10.10.99.8" for i in topology["asset_interfaces"])
    scoped = Principal(principal.user, (ScopeGrant(assignment_id=uuid.uuid4(), role_id=uuid.uuid4(), role_name="Other Site", scope_type="site", customer_id=sites[1].customer_id, site_id=sites[1].id, permissions=frozenset({"assets.view", "networks.view", "networks.edit"})),))
    app.dependency_overrides[get_principal] = lambda: scoped
    assert client.get(url).status_code == 404
    assert client.patch(url, json={"accent_key": "red"}).status_code == 404
    assert record["id"] not in {n["id"] for n in client.get("/api/networks").json()}
    assert record["id"] not in {n["id"] for n in client.get("/api/topology").json()["networks"]}


def test_business_function_presentation_defaults_edits_and_scope(client, db):
    from app.presentation import default_entity_accent
    sites, _, _ = seed_scope(db)
    principal = make_principal("business_functions.view", "business_functions.manage")
    principal.user.email = "function-presentation@example.test"
    db.add(principal.user); db.flush()
    app.dependency_overrides[get_principal] = lambda: principal
    result = client.post("/api/business-functions", json={"customer_id": str(sites[0].customer_id), "site_id": str(sites[0].id), "name": "Purpose"})
    assert result.status_code == 201, result.text
    record = result.json()
    assert (record["icon_key"], record["accent_key"]) == ("home", default_entity_accent(record["id"]))
    url = f"/api/business-functions/{record['id']}"
    changed = client.patch(url, json={"icon_key": "shield", "accent_key": "rose"})
    assert changed.status_code == 200, changed.text
    renamed = client.patch(url, json={"name": "Renamed purpose"}).json()
    assert (renamed["icon_key"], renamed["accent_key"]) == ("shield", "rose")
    assert client.patch(url, json={"icon_key": "arbitrary"}).status_code == 422
    scoped = Principal(principal.user, (ScopeGrant(assignment_id=uuid.uuid4(), role_id=uuid.uuid4(), role_name="Other Site", scope_type="site", customer_id=sites[1].customer_id, site_id=sites[1].id, permissions=frozenset({"business_functions.view", "business_functions.manage"})),))
    app.dependency_overrides[get_principal] = lambda: scoped
    assert client.get(url).status_code == 404
    assert client.patch(url, json={"accent_key": "red"}).status_code == 404
    assert record["id"] not in {item["id"] for item in client.get("/api/business-functions").json()}
