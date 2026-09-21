import topologyClasses from "./topology-classes.json" with { type: "json" };
export const TOPOLOGY_CLASSES = topologyClasses;
export function topologyClassSelection(overrides = {}) {
  const enabled = new Set();
  let changedCount = 0;
  for (const topologyClass of TOPOLOGY_CLASSES) {
    const checked = overrides[topologyClass.key] ?? topologyClass.enabled_by_default;
    if (checked) enabled.add(topologyClass.key);
    if (checked !== topologyClass.enabled_by_default) changedCount++;
  }
  return { enabled, changedCount };
}

// Presentation over authorized domain projections. No relationship semantics live here.
export const CHILD_PREVIEW_COUNT = 8;
export const CATEGORY_PREVIEW_COUNT = 6;
export const CONNECTIVITY_NODE_WIDTH = 180;
export const CONNECTIVITY_NODE_HEIGHT = 88;

// Empty overrides always resolve against the latest managed defaults.
export function topologyCategorySelection(categories, overrides = {}) {
  const enabled = new Set();
  let changedCount = 0;
  for (const category of categories) {
    const checked = overrides[category.id] ?? category.show_in_topology;
    if (checked) enabled.add(category.id);
    if (checked !== category.show_in_topology) changedCount++;
  }
  return { enabled, changedCount };
}

// Stable interface ordering; the legacy Asset IP is deliberately excluded.
export function compactInterfaceIp(interfaces) {
  const ordered = interfaces.filter(i => i.ip_address).sort((a, b) => Number(Boolean(b.is_primary)) - Number(Boolean(a.is_primary)) || (a.name || "").localeCompare(b.name || "") || a.id.localeCompare(b.id));
  const ips = [...new Set(ordered.map(i => i.ip_address))];
  return ips.length ? `${ips[0]}${ips.length > 1 ? ` +${ips.length - 1}` : ""}` : "";
}
export const byName = (a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id);
export const byNetwork = (a, b) => (a.vlan_id ?? Infinity) - (b.vlan_id ?? Infinity) || byName(a, b);
export const matchesSearch = (asset, query) => !query || [asset.name, asset.hostname, ...(asset.interface_ips || [])].filter(Boolean).join(" ").toLowerCase().includes(query.toLowerCase());

export function topologyPresentation(data, enabled) {
  const types = Object.fromEntries(data.asset_types.map(t => [t.key, t]));
  const categoryById = Object.fromEntries(data.categories.map(c => [c.id, c]));
  const networkById = Object.fromEntries(data.networks.map(n => [n.id, n]));
  const categories = data.categories.filter(c => enabled.has(c.id));
  const interfaceGroups = {};
  for (const item of data.asset_interfaces) (interfaceGroups[item.asset_id] ||= []).push(item);
  const assets = data.assets.filter(a => enabled.has(types[a.asset_type]?.category_id)).map(a => ({ ...a,
    presentation: categoryById[types[a.asset_type]?.category_id],
    interface_ips: (interfaceGroups[a.id] || []).map(i => i.ip_address).filter(Boolean),
    display_ip: compactInterfaceIp(interfaceGroups[a.id] || []),
  })).sort(byName);
  const byId = Object.fromEntries(assets.map(a => [a.id, a]));
  const links = data.platform_links.filter(l => byId[l.parent_id] && byId[l.child_id]);
  const children = Object.fromEntries(assets.map(a => [a.id, []]));
  const childIds = new Set();
  for (const link of links) {
    if (!children[link.parent_id].some(a => a.id === link.child_id)) children[link.parent_id].push(byId[link.child_id]);
    childIds.add(link.child_id);
  }
  for (const group of Object.values(children)) group.sort(byName);
  const roots = assets.filter(a => !childIds.has(a.id));
  // Retain closed cycles without pretending a member has a canonical parent.
  const visited = new Set();
  const visit = id => {
    const queue = [id];
    while (queue.length) {
      const next = queue.pop();
      if (visited.has(next)) continue;
      visited.add(next);
      queue.push(...children[next].map(a => a.id));
    }
  };
  roots.forEach(a => visit(a.id));
  const cycleRoots = new Set();
  for (const asset of assets) if (!visited.has(asset.id)) {
    roots.push(asset); cycleRoots.add(asset.id); visit(asset.id);
  }
  const interfaces = data.asset_interfaces.filter(i => byId[i.asset_id]);
  const definitions = Object.fromEntries(data.relationship_types.map(t => [t.key, t]));
  const relationships = data.relationships.filter(r => byId[r.source_asset_id] && byId[r.target_asset_id]).map(r => ({ ...r, display_label: definitions[r.relationship_type]?.source_label, directional: definitions[r.relationship_type]?.directional }));
  return { assets, byId, types, categories, children, roots, cycleRoots, interfaces, relationships, networkById, networks: [...data.networks].sort(byNetwork) };
}

export function platformMatches(asset, children, query) {
  const queue = [asset], seen = new Set();
  while (queue.length) {
    const next = queue.pop();
    if (seen.has(next.id)) continue;
    seen.add(next.id);
    if (matchesSearch(next, query)) return true;
    queue.push(...(children[next.id] || []));
  }
  return false;
}

const nodeOrder = (a, b) => a.name.localeCompare(b.name) || a.key.localeCompare(b.key);
const otherEnd = (edge, key) => edge.source_key === key ? edge.target_key : edge.source_key;

// Only the current authorized result is eligible. No fetch, domain node, or
// relationship is created by expanding this presentation preview.
export function connectivityPreview(graph, expanded = false) {
  const keys = new Set(graph.nodes.map(n => n.key));
  const children = new Set((graph.edges || []).filter(e => e.platform_parent_key === graph.focus_key)
    .map(e => otherEnd(e, graph.focus_key)).filter(key => key !== graph.focus_key && keys.has(key)));
  const ordered = graph.nodes.filter(n => children.has(n.key)).sort(nodeOrder);
  const hidden = new Set(expanded ? [] : ordered.slice(CHILD_PREVIEW_COUNT).map(n => n.key));
  const hiddenCount = hidden.size;
  const byKey = new Map(graph.nodes.map(n => [n.key, n]));
  for (const edge of graph.edges || []) {
    if (!edge.platform_parent_key || edge.platform_parent_key === graph.focus_key) continue;
    const parent = byKey.get(edge.platform_parent_key), child = byKey.get(otherEnd(edge, edge.platform_parent_key));
    // Preserve focus, its ancestors and genuine direct neighbours. A host seen
    // along a technical path remains a summary rather than expanding its family.
    if (parent && child && child.key !== graph.focus_key && child.distance > 1 && child.distance >= parent.distance) hidden.add(child.key);
  }
  return { ...graph, hiddenCount, childCount: ordered.length,
    nodes: graph.nodes.filter(n => !hidden.has(n.key)),
    edges: (graph.edges || []).filter(e => !hidden.has(e.source_key) && !hidden.has(e.target_key)) };
}

export function connectivityLayout(graph) {
  if (!graph.nodes.some(n => n.key === graph.focus_key)) return [];
  const nodes = [...graph.nodes].sort(nodeOrder);
  const byKey = new Map(nodes.map(n => [n.key, n]));
  const edges = (graph.edges || []).filter(e => byKey.has(e.source_key) && byKey.has(e.target_key));
  const adjacent = new Map(nodes.map(n => [n.key, edges.filter(e => e.source_key === n.key || e.target_key === n.key)]));
  const ranks = new Map(nodes.filter(n => n.entity_type !== "network" && n.topology_position != null).map(n => [n.key, n.topology_position.sort_order]));
  const configured = [...new Set(ranks.values())].sort((a, b) => a - b);
  const gaps = configured.slice(1).map((rank, i) => rank - configured[i]);
  const step = gaps.length ? Math.min(...gaps) / 2 : 1;
  const neutral = configured.length ? (configured[0] + configured.at(-1)) / 2 : 0;
  // Resolve against a snapshot each round. Cycles cannot make ranks drift, and
  // unanchored components terminate in the neutral band.
  const resolveAutomatic = () => {
    for (let round = 0; round < nodes.length; round++) {
      const inferred = [];
      for (const node of nodes) {
        if (ranks.has(node.key) || node.entity_type === "network") continue;
        const containment = [], physical = [];
        for (const edge of adjacent.get(node.key)) {
          const neighbour = otherEnd(edge, node.key), rank = ranks.get(neighbour);
          if (rank == null) continue;
          if (edge.platform_parent_key) containment.push(rank + (edge.platform_parent_key === node.key ? -step : step));
          else if (edge.topology_class === "physical_network") physical.push(rank);
        }
        const hints = containment.length ? containment : physical;
        if (hints.length) inferred.push([node.key, hints.reduce((a, b) => a + b, 0) / hints.length]);
      }
      if (!inferred.length) break;
      for (const [key, rank] of inferred) ranks.set(key, rank);
    }
  };
  resolveAutomatic();
  // An unanchored recorded containment tree still supplies relative ordering.
  // Closed cycles have no root and deliberately fall back to the neutral band.
  for (const node of nodes) if (!ranks.has(node.key) && node.entity_type !== "network") {
    const links = adjacent.get(node.key).filter(e => e.platform_parent_key);
    if (links.some(e => e.platform_parent_key === node.key) && links.every(e => e.platform_parent_key === node.key)) ranks.set(node.key, neutral);
  }
  resolveAutomatic();
  for (const node of nodes.filter(n => n.entity_type !== "network")) if (!ranks.has(node.key)) ranks.set(node.key, neutral);
  for (const node of nodes.filter(n => n.entity_type === "network")) {
    const members = adjacent.get(node.key).filter(e => e.kind === "membership").map(e => ranks.get(otherEnd(e, node.key))).filter(r => r != null);
    const low = Math.min(...members), high = Math.max(...members);
    ranks.set(node.key, members.length ? low === high ? low - step / 2 : (low + high) / 2 : neutral);
  }
  // Select a recorded upper neighbour as the primary horizontal anchor. Parent
  // projections take precedence; logical overlays never invent infrastructure.
  const parent = new Map();
  for (const node of nodes) {
    const candidates = adjacent.get(node.key).filter(e => ranks.get(otherEnd(e, node.key)) < ranks.get(node.key) &&
      (e.platform_parent_key || e.topology_class === "physical_network" || e.kind === "membership"));
    candidates.sort((a, b) => Number(b.platform_parent_key === otherEnd(b, node.key)) - Number(a.platform_parent_key === otherEnd(a, node.key)) ||
      ranks.get(otherEnd(b, node.key)) - ranks.get(otherEnd(a, node.key)) || otherEnd(a, node.key).localeCompare(otherEnd(b, node.key)));
    if (candidates.length) parent.set(node.key, otherEnd(candidates[0], node.key));
  }
  const bands = [...new Set(ranks.values())].sort((a, b) => a - b);
  const cellWidth = CONNECTIVITY_NODE_WIDTH + 36, cellHeight = CONNECTIVITY_NODE_HEIGHT + 48;
  const positions = new Map();
  let y = 0;
  for (const rank of bands) {
    const groups = new Map();
    for (const node of nodes.filter(n => ranks.get(n.key) === rank)) {
      const anchor = parent.get(node.key) || "";
      if (!groups.has(anchor)) groups.set(anchor, []);
      groups.get(anchor).push(node);
    }
    const ordered = [...groups].sort(([a], [b]) => (positions.get(a)?.x || 0) - (positions.get(b)?.x || 0) || a.localeCompare(b));
    const columnsFor = group => Math.min(group.length > 12 ? 6 : 4, group.length);
    const widths = ordered.map(([, group]) => columnsFor(group) * cellWidth);
    const total = widths.reduce((a, b) => a + b, 0) + Math.max(0, ordered.length - 1) * 36;
    let cursor = -total / 2, rows = 1;
    ordered.forEach(([anchor, group], index) => {
      const columns = columnsFor(group);
      const centre = cursor + widths[index] / 2;
      group.forEach((node, i) => positions.set(node.key, { ...node, rank, layout_parent_key: anchor || null,
        x: centre + ((i % columns) - (columns - 1) / 2) * cellWidth,
        y: y + Math.floor(i / columns) * cellHeight }));
      cursor += widths[index] + 36;
      rows = Math.max(rows, Math.ceil(group.length / columns));
    });
    y += rows * cellHeight + 48;
  }
  // Centre parents over their child groups, resolving same-band collisions with
  // a deterministic forward pass. Group widths below already reserve space.
  for (const rank of [...bands].reverse()) {
    const band = nodes.filter(n => ranks.get(n.key) === rank).map(n => positions.get(n.key));
    for (const node of band) {
      const children = [...positions.values()].filter(n => n.layout_parent_key === node.key);
      if (children.length) node.x = (Math.min(...children.map(n => n.x)) + Math.max(...children.map(n => n.x))) / 2;
    }
    const rows = new Map();
    for (const node of band) { if (!rows.has(node.y)) rows.set(node.y, []); rows.get(node.y).push(node); }
    for (const row of rows.values()) {
      row.sort((a, b) => a.x - b.x || nodeOrder(a, b));
      for (let i = 1; i < row.length; i++) row[i].x = Math.max(row[i].x, row[i - 1].x + cellWidth);
    }
  }
  // Focus changes the viewport origin, never semantic band assignment.
  const focus = positions.get(graph.focus_key), origin = { x: focus.x, y: focus.y };
  return [focus, ...nodes.filter(n => n.key !== graph.focus_key).map(n => positions.get(n.key))]
    .map(n => ({ ...n, x: n.x - origin.x, y: n.y - origin.y }));
}

// Orthogonal platform rails share a short trunk. Later grid rows use lanes in
// card gutters, never long diagonals through the cards. Canonical arrow direction
// is retained by reversing geometry only when the recorded source is the child.
export function connectivityRail(edge, positions, edges) {
  const parent = positions[edge.platform_parent_key];
  if (!parent) return null;
  const child = positions[otherEnd(edge, parent.key)];
  const siblings = edges.filter(e => e.platform_parent_key === parent.key).map(e => positions[otherEnd(e, parent.key)]).filter(n => n && n.y > parent.y);
  if (!child || child.y <= parent.y || siblings.length < 3) return null;
  const firstY = Math.min(...siblings.map(n => n.y));
  const railY = firstY - CONNECTIVITY_NODE_HEIGHT / 2 - 32;
  const laneX = child.x - CONNECTIVITY_NODE_WIDTH / 2 - 14;
  const entryY = child.y - CONNECTIVITY_NODE_HEIGHT / 2 - 14;
  const points = [[parent.x, parent.y + CONNECTIVITY_NODE_HEIGHT / 2 + 3], [parent.x, railY], [laneX, railY], [laneX, entryY], [child.x, entryY], [child.x, child.y - CONNECTIVITY_NODE_HEIGHT / 2 - 3]];
  return { points: edge.source_key === parent.key ? points : points.reverse(), labelX: child.x, labelY: entryY - 4 };
}

// Only occupied bands are returned. Metadata stays attached to durable managed
// positions, including inactive assignments, for future background rendering.
export function connectivityBands(layout) {
  const bands = new Map();
  for (const node of layout) {
    if (!bands.has(node.rank)) bands.set(node.rank, { rank: node.rank, positions: [], node_keys: [] });
    const band = bands.get(node.rank);
    band.node_keys.push(node.key);
    if (node.topology_position && !band.positions.some(p => p.id === node.topology_position.id)) {
      band.positions.push({ ...node.topology_position });
    }
  }
  return [...bands.values()].sort((a, b) => a.rank - b.rank);
}
