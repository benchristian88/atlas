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
export const CATEGORY_PREVIEW_COUNT = 12;

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
export function platformCardFacts(childCount, interfaceCount) {
  return [childCount > 0 ? `${childCount} child Asset${childCount === 1 ? "" : "s"}` : "",
    interfaceCount > 0 ? `${interfaceCount} interface${interfaceCount === 1 ? "" : "s"}` : ""].filter(Boolean).join(" · ");
}
export const byName = (a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id);
export const byNetwork = (a, b) => (a.vlan_id ?? Infinity) - (b.vlan_id ?? Infinity) || byName(a, b);
export const matchesSearch = (asset, query) => !query || [asset.name, asset.hostname, ...(asset.interface_ips || [])].filter(Boolean).join(" ").toLowerCase().includes(query.toLowerCase());

export function connectivitySearchResults(assets, query) {
  const term = query.trim();
  return term ? assets.filter(asset => matchesSearch(asset, term)).sort(byName).slice(0, 10) : [];
}

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

const nodeOrder = (a, b) => Number(a.entity_type === "disclosure") - Number(b.entity_type === "disclosure") || a.name.localeCompare(b.name) || a.key.localeCompare(b.key);
const otherEnd = (edge, key) => edge.source_key === key ? edge.target_key : edge.source_key;

// Only the current authorized result is eligible. No fetch, domain node, or
// relationship is created by expanding this presentation preview.
export function connectivityPreview(graph, branches = {}) {
  const byKey = new Map(graph.nodes.map(n => [n.key, n]));
  const children = new Map();
  for (const edge of graph.edges || []) {
    const parent = edge.platform_parent_key, child = otherEnd(edge, parent);
    if (!parent || !byKey.has(parent) || !byKey.has(child) || child === parent || byKey.get(child).entity_type !== "asset") continue;
    if (!children.has(parent)) children.set(parent, new Set());
    children.get(parent).add(child);
  }
  const ordered = new Map([...children].map(([parent, keys]) => [parent, [...keys].map(key => byKey.get(key)).sort(nodeOrder)]));
  const collapsible = new Set();
  for (const [parent, group] of ordered) for (const child of group) {
    // Preserve focus, ancestors and independently reached direct neighbours.
    if (child.key !== graph.focus_key && (parent === graph.focus_key ||
      (child.distance > 1 && child.distance >= byKey.get(parent).distance))) collapsible.add(child.key);
  }
  const visible = new Set(graph.nodes.filter(n => !collapsible.has(n.key)).map(n => n.key));
  // Reveal only branches with visible parents. A shared child is visible if any
  // expanded parent reveals it; cycles terminate at the bounded returned set.
  for (let round = 0; round < graph.nodes.length; round++) {
    const before = visible.size;
    for (const [parent, group] of ordered) {
      if (!visible.has(parent)) continue;
      const budget = branches[parent] === "all" ? group.length : parent === graph.focus_key || branches[parent] === "preview" ? CHILD_PREVIEW_COUNT : 0;
      group.slice(0, budget).forEach(child => visible.add(child.key));
    }
    if (visible.size === before) break;
  }
  const disclosures = {}, moreNodes = [], moreEdges = [];
  for (const [parent, group] of ordered) {
    if (!visible.has(parent)) continue;
    const hidden = group.filter(child => !visible.has(child.key));
    if (!hidden.length) continue;
    const shown = group.filter(child => visible.has(child.key));
    disclosures[parent] = { hiddenCount: hidden.length, shownCount: shown.length };
    if (!shown.length) continue;
    const key = `disclosure:${parent}`;
    moreNodes.push({ key, entity_type: "disclosure", name: "more", parent_key: parent,
      hiddenCount: hidden.length, topology_position: (shown.at(-1) || hidden[0]).topology_position });
    moreEdges.push({ key: `disclosure-edge:${parent}`, source_key: parent, target_key: key,
      platform_parent_key: parent, kind: "disclosure", directional: false });
  }
  return { ...graph, disclosures, moreNodes, moreEdges,
    nodes: graph.nodes.filter(n => visible.has(n.key)),
    edges: (graph.edges || []).filter(e => visible.has(e.source_key) && visible.has(e.target_key)) };
}

export { connectivityLayout, connectivityPositionMembership, connectivityPositionGroups, orthogonalDetour, connectivityRoutes, connectivityBounds, connectivityFit, connectivityBands, CONNECTIVITY_NODE_WIDTH, CONNECTIVITY_NODE_HEIGHT, CONNECTIVITY_RAIL_GAP } from "./topology-geometry.mjs";
