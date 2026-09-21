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
        "relationship_types": [{"key": "runs_on", "topology_class": "platform", "source_label": "Runs on", "directional": True}, {"key": "custom_link", "topology_class": "physical_network", "source_label": "Recorded custom connection", "directional": False}],
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
    t["asset_interfaces"] = [{"id": f"i{i}", "asset_id": "AdGuard", "network_id": "n1", "name": f"eth{i}", "ip_address": None} for i in range(520)]
    graph = connectivity(t, "AdGuard", hops=2)
    assert len(graph["edges"]) == 500 and graph["truncated"]
    reached = {graph["focus_key"]}
    for _ in graph["nodes"]:
        for edge in graph["edges"]:
            if edge["source_key"] in reached or edge["target_key"] in reached:
                reached.update((edge["source_key"], edge["target_key"]))
    assert reached == {n["key"] for n in graph["nodes"]}


def homelab_topology():
    t = fixture_topology()
    siblings = ["Grafana", "Authentik", "Immich", "NPM", "Paperless"] + [f"Workload {i:02}" for i in range(14)]
    t["assets"] += [{"id": name, "name": name, "asset_type": "custom"} for name in siblings + ["USW-16-poe"]]
    for i, name in enumerate(siblings):
        key = ["runs_on", "member_of", "hosts", "contains", "runs"][i % 5]
        source, target = (name, "PVE1") if key in ("runs_on", "member_of") else ("PVE1", name)
        t["relationships"].append({"id": f"sibling{i}", "source_asset_id": source, "target_asset_id": target, "relationship_type": key})
        t["asset_interfaces"].append({"id": f"peer{i}", "asset_id": name, "network_id": "n1", "name": "eth0", "ip_address": None})
    t["relationships"].append({"id": "switch", "source_asset_id": "PVE1", "target_asset_id": "USW-16-poe", "relationship_type": "connects_to"})
    for key in ("member_of", "hosts", "contains", "runs", "connects_to"):
        t["relationship_types"].append({"key": key, "topology_class": "physical_network" if key == "connects_to" else "platform", "source_label": key, "directional": True})
    return t, siblings


def test_child_focus_suppresses_siblings_and_network_peers_but_preserves_technical_paths():
    t, siblings = homelab_topology()
    graph = connectivity(t, "AdGuard", hops=2)
    keys = {n["key"] for n in graph["nodes"]}
    assert keys == {"asset:AdGuard", "asset:PVE1", "asset:PVE2", "asset:USW-16-poe", "network:n1", "network:n2"}
    assert not graph["truncated"]  # Deliberate semantic pruning is not cap clipping.
    switch = next(n for n in graph["nodes"] if n["key"] == "asset:USW-16-poe")
    assert switch["distance"] == 2 and switch["parent_key"] == "asset:PVE1"
    t["relationships"].reverse()
    t["asset_interfaces"].reverse()
    assert connectivity(t, "AdGuard", hops=2) == graph


def test_explicit_host_and_network_focus_show_direct_children_and_members():
    t, siblings = homelab_topology()
    host = connectivity(t, "PVE1", hops=1)
    assert {f"asset:{n}" for n in siblings + ["AdGuard"]} <= {n["key"] for n in host["nodes"]}
    network = connectivity(t, None, hops=1, focus_network_id="n1")
    assert {n["key"] for n in network["nodes"]} == {f"asset:{n}" for n in siblings + ["AdGuard"]} | {"network:n1"}
    assert connectivity(t, None, focus_network_id="n1", limit=5)["truncated"]
    assert connectivity(t, None, focus_network_id="n1", show_networks=False)["nodes"] == []
    with pytest.raises(HTTPException) as exc:
        connectivity(t, None, focus_network_id="inaccessible")
    assert exc.value.status_code == 404


def test_parallel_technical_path_can_reach_peer_even_if_containment_path_cannot():
    t, _ = homelab_topology()
    t["relationships"].append({"id": "parallel", "source_asset_id": "AdGuard", "target_asset_id": "PVE1", "relationship_type": "connects_to"})
    assert "asset:Grafana" in {n["key"] for n in connectivity(t, "AdGuard", hops=2, limit=60)["nodes"]}


def capacity_topology(child_count=18):
    t = fixture_topology()
    names = ["parent"] + [f"A infrastructure {i}" for i in range(8)] + [f"Workload {i:03}" for i in range(child_count)]
    t["assets"] = [{"id": name, "name": name, "asset_type": "custom"} for name in names]
    t["relationships"] = [{"id": name, "source_asset_id": name, "target_asset_id": "parent",
        "relationship_type": "runs_on" if name.startswith("Workload") else "custom_link"} for name in names[1:]]
    t["asset_interfaces"] = []
    return t


def test_homelab_capacity_reproduces_old_loss_and_returns_all_eighteen_children():
    t = capacity_topology()
    old = connectivity(t, "parent", hops=2, limit=25)
    assert old["truncated"] and sum(n["name"].startswith("Workload") for n in old["nodes"]) == 16
    graph = connectivity(t, "parent", hops=2)
    assert len(graph["nodes"]) == 27 and not graph["truncated"]
    assert graph["node_limit"] == 100 and graph["edge_limit"] == 500
    parent = next(n for n in graph["nodes"] if n["name"] == "parent")
    assert parent["eligible_child_count"] == parent["returned_child_count"] == 18


def test_large_branch_is_bounded_and_counts_only_returned_children_as_expandable():
    t = capacity_topology(120)
    graph = connectivity(t, "parent", hops=2)
    assert len(graph["nodes"]) == 100 and graph["truncated"]
    parent = next(n for n in graph["nodes"] if n["name"] == "parent")
    assert parent["eligible_child_count"] == 120 and parent["returned_child_count"] == 91
    t["assets"].reverse(); t["relationships"].reverse()
    assert connectivity(t, "parent", hops=2) == graph
    with pytest.raises(HTTPException):
        connectivity(t, "parent", limit=101)
    filtered = connectivity(t, "parent", topology_classes=["physical_network"])
    assert all(n["eligible_child_count"] == n["returned_child_count"] == 0 for n in filtered["nodes"])
    assert not filtered["truncated"]


def test_child_metadata_respects_categories_classes_and_deduplicates_canonical_links():
    t = capacity_topology()
    t["assets"][9]["asset_type"] = "other"
    t["relationships"].append({**t["relationships"][9], "id": "parallel"})
    parent = next(n for n in connectivity(t, "parent")["nodes"] if n["key"] == "asset:parent")
    assert parent["eligible_child_count"] == parent["returned_child_count"] == 17
    parent = next(n for n in connectivity(t, "parent", category_ids=["custom", "uncategorized"])["nodes"] if n["key"] == "asset:parent")
    assert parent["eligible_child_count"] == parent["returned_child_count"] == 18
    graph = connectivity(t, "parent", topology_classes=["physical_network"])
    assert all(n["eligible_child_count"] == n["returned_child_count"] == 0 for n in graph["nodes"])
