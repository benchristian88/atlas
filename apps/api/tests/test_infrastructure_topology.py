import importlib.util
from pathlib import Path
import uuid

from fastapi import HTTPException
import pytest
from pydantic import ValidationError

from app.schemas import AssetCategoryCreate, AssetCategoryUpdate, AssetTypeCreate
from app.services.infrastructure_topology import connectivity, platform_links


def fixture_topology():
    return {
        "assets": [{"id": name, "name": name, "asset_type": "custom" if name != "hidden" else "other"} for name in ["AdGuard", "PVE1", "PVE2", "hidden"]],
        "categories": [{"id": "custom", "show_in_topology": True}, {"id": "uncategorized", "show_in_topology": False}],
        "asset_types": [{"key": "custom", "category_id": "custom"}, {"key": "other", "category_id": "uncategorized"}],
        "relationships": [
            {"id": "r1", "source_asset_id": "AdGuard", "target_asset_id": "PVE1", "relationship_type": "runs_on"},
            {"id": "r2", "source_asset_id": "PVE1", "target_asset_id": "PVE2", "relationship_type": "custom_link"},
            {"id": "r3", "source_asset_id": "PVE2", "target_asset_id": "hidden", "relationship_type": "custom_link"},
        ],
        "relationship_types": [{"key": "runs_on", "source_label": "Runs on", "directional": True}, {"key": "custom_link", "source_label": "Recorded custom connection", "directional": False}],
        "networks": [{"id": "n1", "name": "Management", "gateway": "10.0.99.1"}, {"id": "n2", "name": "Apps"}],
        "asset_interfaces": [{"id": "i1", "asset_id": "AdGuard", "network_id": "n1", "name": "eth0", "ip_address": "10.0.99.5"}, {"id": "i2", "asset_id": "AdGuard", "network_id": "n2", "name": "eth1", "ip_address": None}],
    }


def test_managed_category_contract_requires_assignment_and_immutable_keys():
    with pytest.raises(ValidationError):
        AssetTypeCreate(key="docker_compose", name="Docker Compose")
    with pytest.raises(ValidationError):
        AssetTypeCreate(key="docker_compose", name="Docker Compose", category_id=None)
    with pytest.raises(ValidationError):
        AssetCategoryUpdate(key="changed")
    assert AssetCategoryCreate(key="workload", name="Workload").show_in_topology
    assert AssetCategoryCreate(key="workload", name="Workload").active


def test_legacy_category_mapping_preserves_distinct_names_and_safe_collisions():
    path = Path(__file__).parents[1] / "migrations/versions/20260921_0019_asset_categories.py"
    spec = importlib.util.spec_from_file_location("categories_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    values = [None, "", "  ", "Network", "Networking", "network", "Network!", "Network ", "Uncategorized", "uncategorized", "99 devices", "日本語"]
    rows = migration.category_rows(values)
    assert {r[0] for r in rows} == {v for v in values if v and v.strip()}
    assert len({r[1] for r in rows}) == len(rows)
    assert len({r[2] for r in rows}) == len(rows)
    assert migration.category_rows(reversed(values)) == rows
    for _, _, key in rows:
        AssetCategoryCreate(key=key, name=key)


def test_platform_direction_comes_from_canonical_keys_not_category_or_label():
    relationships = fixture_topology()["relationships"]
    links = platform_links(relationships)
    assert links == [{"relationship_id": "r1", "parent_id": "PVE1", "child_id": "AdGuard"}]
    for key in ("hosts", "contains", "runs"):
        assert platform_links([{"id": key, "source_asset_id": "parent", "target_asset_id": "child", "relationship_type": key}])[0]["parent_id"] == "parent"
    assert platform_links([{"id": "self", "source_asset_id": "a", "target_asset_id": "a", "relationship_type": "contains"}]) == []


def test_connectivity_hops_memberships_direction_and_no_fabricated_gateway():
    t = fixture_topology()
    graph = connectivity(t, "AdGuard")
    assert {n["key"] for n in graph["nodes"]} == {"asset:AdGuard", "asset:PVE1", "network:n1", "network:n2"}
    edge = next(e for e in graph["edges"] if e["key"] == "relationship:r1")
    assert (edge["source_key"], edge["target_key"], edge["label"]) == ("asset:AdGuard", "asset:PVE1", "Runs on")
    assert next(e for e in graph["edges"] if e["key"] == "interface:i1")["label"] == "eth0 · 10.0.99.5"
    assert "asset:PVE2" in {n["key"] for n in connectivity(t, "AdGuard", hops=2)["nodes"]}
    reverse = next(e for e in connectivity(t, "PVE1")["edges"] if e["key"] == "relationship:r1")
    assert reverse == edge
    assert all(n["name"] != "10.0.99.1" for n in graph["nodes"])


def test_connectivity_defaults_overrides_non_disclosure_and_pruning():
    t = fixture_topology()
    assert "asset:hidden" not in {n["key"] for n in connectivity(t, "PVE2")["nodes"]}
    assert "asset:hidden" in {n["key"] for n in connectivity(t, "PVE2", category_ids=["custom", "uncategorized"])["nodes"]}
    assert connectivity(t, "AdGuard", category_ids=[])["nodes"] == []
    assert not any(n["entity_type"] == "network" for n in connectivity(t, "AdGuard", show_networks=False)["nodes"])
    with pytest.raises(HTTPException) as exc:
        connectivity(t, uuid.uuid4())
    assert exc.value.status_code == 404


def test_connectivity_bounded_deterministic_cycle_safe():
    t = fixture_topology()
    t["relationships"].append({"id": "cycle", "source_asset_id": "PVE2", "target_asset_id": "AdGuard", "relationship_type": "custom_link"})
    graph = connectivity(t, "AdGuard", hops=2, limit=3)
    assert len(graph["nodes"]) == 3 and graph["truncated"]
    assert len({n["key"] for n in graph["nodes"]}) == 3
    t["relationships"].reverse()
    assert connectivity(t, "AdGuard", hops=2, limit=3) == graph
    assert all(e["source_key"] in {n["key"] for n in graph["nodes"]} and e["target_key"] in {n["key"] for n in graph["nodes"]} for e in graph["edges"])


def test_dense_edge_limit_retains_paths_to_every_returned_node():
    t = fixture_topology()
    # Preserve connections to Assets even with many parallel membership edges.
    t["asset_interfaces"] = [{"id": f"i{i}", "asset_id": "AdGuard", "network_id": "n1", "name": f"eth{i}", "ip_address": None} for i in range(170)]
    graph = connectivity(t, "AdGuard", hops=2)
    assert len(graph["edges"]) == 150 and graph["truncated"]
    reached = {graph["focus_key"]}
    for _ in graph["nodes"]:
        for edge in graph["edges"]:
            if edge["source_key"] in reached or edge["target_key"] in reached:
                reached.update((edge["source_key"], edge["target_key"]))
    assert reached == {n["key"] for n in graph["nodes"]}
