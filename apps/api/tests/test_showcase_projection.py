from app.services.infrastructure_topology import platform_links, structural_edges


def test_complete_projection_has_no_connectivity_cap_and_preserves_direction():
    assets = [{"id": str(i)} for i in range(160)]
    relationships = [{"id": str(i), "source_asset_id": str(i), "target_asset_id": "0", "relationship_type": "hosted_on"} for i in range(1, 160)]
    definitions = [{"key": "hosted_on", "topology_class": "platform", "source_label": "Hosted on", "directional": True}]
    edges = structural_edges(assets, relationships, definitions)
    assert len(edges) == 159
    assert all(e["platform_parent_key"] == "asset:0" for e in edges)
    assert all(e["target_key"] == "asset:0" for e in edges)
    assert platform_links(relationships) == []
    assert edges == structural_edges(list(reversed(assets)), list(reversed(relationships)), definitions)


def test_structural_classes_and_visible_membership_only():
    assets = [{"id": "a"}, {"id": "b"}]
    definitions = [{"key": key, "topology_class": value, "directional": False} for key, value in [
        ("connects", "physical_network"), ("custom", "platform"), ("depends", "logical_operational"), ("backs", "data_resilience"), ("other", "other")]]
    relationships = [{"id": key, "source_asset_id": "a", "target_asset_id": "b", "relationship_type": key} for key in ["connects", "custom", "depends", "backs", "other"]]
    relationships.append({"id": "secret", "source_asset_id": "a", "target_asset_id": "hidden", "relationship_type": "connects"})
    interfaces = [{"id": "visible", "asset_id": "a", "network_id": "n"}, {"id": "hidden", "asset_id": "a", "network_id": "secret"}, {"id": "hidden-asset", "asset_id": "hidden", "network_id": "n"}]
    edges = structural_edges(assets, relationships, definitions, [{"id": "n"}], interfaces)
    assert {e["key"] for e in edges} == {"relationship:connects", "relationship:custom", "interface:visible"}
    assert all(e["platform_parent_key"] is None for e in edges)
    assert "secret" not in str(edges)


def test_platform_semantics_cycles_and_parallel_edges_remain_explicit():
    assets = [{"id": "a"}, {"id": "b"}]
    definitions = [{"key": key, "topology_class": "platform", "directional": True} for key in ["hosts", "runs_on"]]
    relationships = [
        {"id": "1", "source_asset_id": "a", "target_asset_id": "b", "relationship_type": "hosts"},
        {"id": "2", "source_asset_id": "a", "target_asset_id": "b", "relationship_type": "runs_on"},
    ]
    edges = structural_edges(assets, relationships, definitions)
    assert len(edges) == 2
    assert [e["platform_parent_key"] for e in edges] == ["asset:a", "asset:b"]
