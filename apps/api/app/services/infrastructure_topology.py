"""Read-only projections of already-authorized infrastructure records.

Relationship keys below are the canonical built-in taxonomy (migration 0004),
not display labels or Asset categories. Unknown/custom relationships still
appear in Connectivity, but do not acquire invented containment semantics.
"""
from collections import defaultdict, deque

from fastapi import HTTPException

PLATFORM_PARENT_ENDPOINT = {
    "runs_on": "target", "member_of": "target",
    "hosts": "source", "contains": "source", "runs": "source",
}


def platform_links(relationships):
    links = []
    for edge in relationships:
        endpoint = PLATFORM_PARENT_ENDPOINT.get(edge["relationship_type"])
        if endpoint:
            parent, child = (edge["source_asset_id"], edge["target_asset_id"]) if endpoint == "source" else (edge["target_asset_id"], edge["source_asset_id"])
            if parent != child:
                links.append({"relationship_id": edge["id"], "parent_id": parent, "child_id": child})
    return links


def connectivity(topology, focus_id, hops=1, category_ids=None, show_networks=True, limit=25, focus_network_id=None):
    """Bounded, path-aware neighbourhood over authorized records only."""
    if hops not in (1, 2) or not 1 <= limit <= 60:
        raise HTTPException(422, "Connectivity requires 1 or 2 hops and a limit of 1–60")
    focus_id = str(focus_id)
    assets = {str(a["id"]): a for a in topology["assets"]}
    networks = {str(n["id"]): n for n in topology["networks"]}
    if focus_network_id is not None:
        focus = f"network:{focus_network_id}"
        if str(focus_network_id) not in networks:
            raise HTTPException(404, "Network not found")
    else:
        focus = f"asset:{focus_id}"
        if focus_id not in assets:
            raise HTTPException(404, "Asset not found")
    types = {t["key"]: t for t in topology["asset_types"]}
    enabled = {str(c["id"]) for c in topology["categories"] if c["show_in_topology"]} if category_ids is None else set(map(str, category_ids))
    assets = {key: a for key, a in assets.items() if str(types[a["asset_type"]]["category_id"]) in enabled}
    if (focus_network_id is None and focus_id not in assets) or (focus_network_id is not None and not show_networks):
        return {"nodes": [], "edges": [], "truncated": False, "focus_key": focus}
    nodes = {f"asset:{key}": {"key": f"asset:{key}", "entity_type": "asset", "entity_id": key, "name": a["name"]} for key, a in assets.items()}
    definitions = {t["key"]: t for t in topology["relationship_types"]}
    edges = []
    parents = {f"relationship:{link['relationship_id']}": f"asset:{link['parent_id']}" for link in platform_links(topology["relationships"])}
    for edge in topology["relationships"]:
        source, target = str(edge["source_asset_id"]), str(edge["target_asset_id"])
        if source in assets and target in assets:
            definition = definitions[edge["relationship_type"]]
            edges.append({"key": f"relationship:{edge['id']}", "source_key": f"asset:{source}", "target_key": f"asset:{target}",
                          "label": definition["source_label"], "kind": "relationship", "directional": definition["directional"]})
    if show_networks:
        for key, network in networks.items():
            nodes[f"network:{key}"] = {"key": f"network:{key}", "entity_type": "network", "entity_id": key, "name": network["name"]}
        for interface in topology["asset_interfaces"]:
            asset_id, network_id = str(interface["asset_id"]), str(interface["network_id"])
            if asset_id not in assets or network_id not in networks:
                continue
            key = f"network:{network_id}"
            nodes[key] = {"key": key, "entity_type": "network", "entity_id": network_id, "name": networks[network_id]["name"]}
            label = " · ".join(filter(None, (interface["name"], interface["ip_address"])))
            edges.append({"key": f"interface:{interface['id']}", "source_key": f"asset:{asset_id}", "target_key": key,
                          "label": label, "kind": "membership", "directional": False})
    adjacency = defaultdict(list)
    for edge in edges:
        adjacency[edge["source_key"]].append((edge["target_key"], edge))
        adjacency[edge["target_key"]].append((edge["source_key"], edge))
    distances = {focus: 0}
    branches = {focus: None}
    # Arrival state matters: a parallel technical connection may legitimately
    # permit expansion that a child->parent or member->network path suppresses.
    queue = deque([(focus, None, 0)])
    visited = {(focus, None)}
    tree_pairs = set()
    truncated = False
    while queue:
        current, arrival, depth = queue.popleft()
        if depth >= hops:
            continue
        for key, edge in sorted(adjacency[current], key=lambda item: (nodes[item[0]]["name"], item[0], item[1]["key"])):
            parent = parents.get(edge["key"])
            if arrival == "parent" and parent == current:
                continue
            if arrival == "network" and edge["kind"] == "membership":
                continue
            next_arrival = "network" if edge["kind"] == "membership" and nodes[key]["entity_type"] == "network" else "parent" if parent == key else None
            if key not in distances:
                if len(distances) >= limit:
                    truncated = True
                    continue
                distances[key] = depth + 1
                branches[key] = current
                tree_pairs.add(frozenset((current, key)))
            state = (key, next_arrival)
            if state not in visited:
                visited.add(state)
                queue.append((key, next_arrival, depth + 1))
    selected_edges = [e for e in sorted(edges, key=lambda e: e["key"]) if e["source_key"] in distances and e["target_key"] in distances]
    # Retain one edge for every BFS discovery before clipping dense parallels.
    tree_edges, other_edges = [], []
    for edge in selected_edges:
        pair = frozenset((edge["source_key"], edge["target_key"]))
        if pair in tree_pairs:
            tree_edges.append(edge)
            tree_pairs.remove(pair)
        else:
            other_edges.append(edge)
    # Dense/multi-interface neighbourhoods also have an explicit edge bound.
    truncated = truncated or len(selected_edges) > 150
    return {"focus_key": focus, "nodes": [{**nodes[k], "distance": depth, "parent_key": branches[k]} for k, depth in distances.items()],
            "edges": sorted((tree_edges + other_edges)[:150], key=lambda e: e["key"]), "truncated": truncated}
