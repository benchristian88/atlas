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

export function connectivityLayout(graph, { width = 900 } = {}) {
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
  const cellWidth = CONNECTIVITY_NODE_WIDTH + 48, cellHeight = 168;
  const positions = new Map();
  const children = new Map(nodes.map(n => [n.key, []]));
  for (const node of nodes) if (parent.has(node.key)) children.get(parent.get(node.key)).push(node);
  const clusterKey = node => JSON.stringify([parent.get(node.key) || node.key, node.topology_position?.id || ranks.get(node.key)]);
  const clusters = new Map();
  for (const node of nodes) {
    const key = clusterKey(node);
    if (!clusters.has(key)) clusters.set(key, []);
    clusters.get(key).push(node);
  }
  const vertical = new Map();
  // Rank is ordinal. Only recorded upper neighbours impose vertical distance;
  // independent siblings never reserve empty rows in one another's branches.
  // Check every eligible upper neighbour, not just the primary horizontal anchor.
  const orderedClusters = [...clusters.values()].sort((a, b) => ranks.get(a[0].key) - ranks.get(b[0].key) || nodeOrder(a[0], b[0]));
  for (const cluster of orderedClusters) {
    const upper = cluster.flatMap(node => adjacent.get(node.key).filter(e =>
      (e.platform_parent_key || e.topology_class === "physical_network" || e.kind === "membership") &&
      ranks.get(otherEnd(e, node.key)) < ranks.get(node.key)).map(e => otherEnd(e, node.key)));
    const base = Math.max(0, ...upper.map(key => vertical.get(key).y + cellHeight));
    const leavesOnly = cluster.every(n => !children.get(n.key).length);
    const columns = Math.max(cluster.length > 12 ? 6 : 4, Math.min(8, Math.floor(width / cellWidth)));
    cluster.forEach((node, i) => {
      // A remainder control follows the real child grid; expansion is unchanged.
      const index = node.entity_type === "disclosure" ? Math.ceil(i / columns) * columns : i;
      const row = leavesOnly ? Math.floor(index / columns) : 0;
      vertical.set(node.key, { y: base + row * cellHeight, row, column: leavesOnly ? index % columns : i });
    });
  }
  const positioned = node => ({ ...node, ...vertical.get(node.key), rank: ranks.get(node.key), layout_parent_key: parent.get(node.key) || null });
  const footprint = placed => [
    ...placed.map(n => ({ left: n.x - cellWidth / 2, right: n.x + cellWidth / 2, top: n.y - 90, bottom: n.y + 64 })),
    ...connectivityPositionGroups(placed, { decoration: false }).map(g => ({ left: g.left - 8, right: g.left + g.width + 8, top: g.top, bottom: g.top + g.height })),
  ];
  // Pack actual occupied geometry, including local containers, before centring
  // ancestors. Compatible subtree contours can share columns at different Y.
  const pack = (group, separatePositions = true) => {
    const blocks = [];
    for (let i = 0; i < group.length;) {
      const current = group[i];
      if (children.get(current.key).length) { blocks.push(branch(current)); i++; continue; }
      const leaves = [];
      while (i < group.length && !children.get(group[i].key).length && clusterKey(group[i]) === clusterKey(current)) leaves.push(group[i++]);
      const firstColumn = Math.min(...leaves.map(n => vertical.get(n.key).column));
      const columns = Math.max(...leaves.map(n => vertical.get(n.key).column)) - firstColumn + 1;
      blocks.push({ width: columns * cellWidth, nodes: leaves.map(node => ({ ...positioned(node), x: (vertical.get(node.key).column - firstColumn + .5) * cellWidth })) });
    }
    let width = 0, previousPosition;
    const placed = [], occupied = [];
    for (const block of blocks) {
      const position = clusterKey(block.nodes[0]);
      let offset = separatePositions && previousPosition != null && position !== previousPosition ? width + 24 : 0;
      const rectangles = footprint(block.nodes);
      for (const a of rectangles) for (const b of occupied) {
        if (a.top < b.bottom && a.bottom > b.top) offset = Math.max(offset, b.right - a.left);
      }
      placed.push(...block.nodes.map(n => ({ ...n, x: n.x + offset })));
      occupied.push(...rectangles.map(r => ({ ...r, left: r.left + offset, right: r.right + offset })));
      width = Math.max(width, offset + block.width);
      previousPosition = position;
    }
    return { width: Math.max(cellWidth, width), nodes: placed };
  };
  const branch = node => {
    const ordered = [...children.get(node.key)].sort((a, b) => ranks.get(a.key) - ranks.get(b.key) || nodeOrder(a, b));
    const block = pack(ordered);
    return { width: block.width, nodes: [{ ...positioned(node), x: block.width / 2 }, ...block.nodes] };
  };
  const roots = nodes.filter(n => !parent.has(n.key)).sort((a, b) => ranks.get(a.key) - ranks.get(b.key) || nodeOrder(a, b));
  for (const node of pack(roots, false).nodes) positions.set(node.key, node);
  // Focus changes the viewport origin, never the branch ordering.
  const focus = positions.get(graph.focus_key), origin = { x: focus.x, y: focus.y };
  return [focus, ...nodes.filter(n => n.key !== graph.focus_key).map(n => positions.get(n.key))]
    .map(n => ({ ...n, x: n.x - origin.x, y: n.y - origin.y }));
}

// Containers describe local siblings, never every occurrence of a position.
// Split disconnected roots, distant peers and any box enclosing unrelated cards.
export function connectivityPositionGroups(nodes, { decoration = true } = {}) {
  const candidates = new Map();
  for (const node of [...nodes].sort((a, b) => a.y - b.y || a.x - b.x || nodeOrder(a, b))) {
    if (node.entity_type !== "asset" || !node.topology_position || !node.layout_parent_key) continue;
    const key = JSON.stringify([node.layout_parent_key, node.topology_position.id]);
    if (!candidates.has(key)) candidates.set(key, []);
    candidates.get(key).push(node);
  }
  const groups = [];
  // Keep the existing clustering envelope independent of visual padding.
  const wrap = members => {
    const left = Math.min(...members.map(n => n.x)) - CONNECTIVITY_NODE_WIDTH / 2 - 16;
    const top = Math.min(...members.map(n => n.y)) - CONNECTIVITY_NODE_HEIGHT / 2 - 44;
    return { left, top, width: Math.max(...members.map(n => n.x)) + CONNECTIVITY_NODE_WIDTH / 2 + 16 - left,
      height: Math.max(...members.map(n => n.y)) + CONNECTIVITY_NODE_HEIGHT / 2 + 18 - top };
  };
  for (const [key, peers] of candidates) {
    const local = [];
    for (const node of peers) {
      const last = local.at(-1);
      const box = last && wrap([...last, node]);
      const nearby = last?.some(n => Math.abs(n.x - node.x) <= CONNECTIVITY_NODE_WIDTH + 72 && Math.abs(n.y - node.y) <= 168);
      const foreign = box && nodes.some(n => !peers.includes(n) && n.x + CONNECTIVITY_NODE_WIDTH / 2 > box.left && n.x - CONNECTIVITY_NODE_WIDTH / 2 < box.left + box.width && n.y + 44 > box.top && n.y - 44 < box.top + box.height);
      if (last && nearby && !foreign) last.push(node); else local.push([node]);
    }
    for (const members of local) {
      if (members.length < 2) continue;
      const box = wrap(members), position = members[0].topology_position;
      let hash = 0;
      for (const char of position.id) hash = (Math.imul(hash, 31) + char.charCodeAt(0)) >>> 0;
      const accents = ["blue", "teal", "purple", "amber", "cyan", "rose", "green", "slate"];
      groups.push({ ...box, key: `${key}:${members[0].key}`, parent_key: members[0].layout_parent_key, position_id: position.id, name: position.name,
        accent_key: accents[hash % accents.length], node_keys: members.map(n => n.key),
        labelWidth: Math.min(box.width - 24, 240, Math.max(80, position.name.length * 8 + 8)) });
    }
  }
  // Packing retains its established envelope; decoration never moves cards.
  if (!decoration) return groups;
  // Attach controls to an already computed local group, without adding Assets
  // to its membership/count or merging separate clusters with the same position.
  const disclosures = new Map(groups.map(group => [group.key, []]));
  for (const node of nodes.filter(n => n.entity_type === "disclosure")) {
    const eligible = groups.filter(g => g.parent_key === node.parent_key && g.position_id === node.topology_position?.id);
    const distance = group => Math.min(...nodes.filter(n => group.node_keys.includes(n.key)).map(n => Math.hypot(n.x - node.x, n.y - node.y)));
    eligible.sort((a, b) => distance(a) - distance(b) || a.key.localeCompare(b.key));
    if (eligible.length) disclosures.get(eligible[0].key).push(node);
  }
  return groups.map(group => {
    const controls = disclosures.get(group.key);
    const members = [...nodes.filter(n => group.node_keys.includes(n.key)), ...controls];
    const halfWidth = n => n.entity_type === "disclosure" ? 30 : CONNECTIVITY_NODE_WIDTH / 2;
    const left = Math.min(...members.map(n => n.x - halfWidth(n))) - 16;
    // Twenty pixels above the cards keeps the border below the source rail;
    // the footer reserves label space below cards, attached badges and controls.
    const top = Math.min(...members.map(n => n.y - nodeHalfHeight(n))) - 20;
    const width = Math.max(...members.map(n => n.x + halfWidth(n))) + 16 - left;
    const height = Math.max(...members.map(n => n.y + nodeHalfHeight(n))) + 48 - top;
    return { ...group, left, top, width, height, labelTop: height - 28,
      disclosure_keys: controls.map(n => n.key), labelWidth: Math.min(width - 24, group.labelWidth) };
  });
}

// All coordinates remain in layout space. Routes are reversed only at the end
// to retain canonical arrows, independently of vertical presentation direction.
const nodeHalfHeight = node => node.entity_type === "disclosure" ? 30 : CONNECTIVITY_NODE_HEIGHT / 2;
export function connectivityRoutes(nodes, edges, groups = connectivityPositionGroups(nodes)) {
  const positions = Object.fromEntries(nodes.map(n => [n.key, n]));
  const obstacles = nodes.map(n => ({ key: n.key,
    left: n.x - (n.entity_type === "disclosure" ? 30 : CONNECTIVITY_NODE_WIDTH / 2) - 6,
    right: n.x + (n.entity_type === "disclosure" ? 30 : CONNECTIVITY_NODE_WIDTH / 2) + 6,
    top: n.y - nodeHalfHeight(n) - 6, bottom: n.y + nodeHalfHeight(n) + 6 }));
  obstacles.push(...groups.map(g => ({ key: g.key, left: g.left + 10, right: g.left + 14 + g.labelWidth,
    top: g.top + g.labelTop - 2, bottom: g.top + g.labelTop + 22 })));
  const clear = points => points.slice(1).every(([x, y], i) => {
    const [px, py] = points[i];
    return obstacles.every(r => x === px
      ? x <= r.left || x >= r.right || Math.max(y, py) <= r.top || Math.min(y, py) >= r.bottom
      : y <= r.top || y >= r.bottom || Math.max(x, px) <= r.left || Math.min(x, px) >= r.right);
  });
  const tracks = [];
  const routes = {};
  const ordered = [...edges].sort((a, b) => a.key.localeCompare(b.key));
  for (const edge of ordered) {
    const source = positions[edge.source_key], target = positions[edge.target_key];
    if (!source || !target) continue;
    const reverse = source.y > target.y || (source.y === target.y && source.key > target.key);
    const [upper, lower] = reverse ? [target, source] : [source, target];
    const sameRow = upper.y === lower.y && upper.key !== lower.key;
    const start = [upper.x, upper.y + (sameRow ? -1 : 1) * (nodeHalfHeight(upper) + 8)];
    const end = [lower.x, lower.y - nodeHalfHeight(lower) - 8];
    // Rail heights are shared by each row, outside cards and attached +N badges.
    const exitY = upper.y + (sameRow ? -1 : 1) * (nodeHalfHeight(upper) + 12);
    const entryY = lower.y - CONNECTIVITY_NODE_HEIGHT / 2 - 12;
    const simple = sameRow
      ? [start, [upper.x, entryY], [lower.x, entryY], end]
      : [start, [upper.x, exitY], [lower.x, exitY], end];
    // A direct drop is preferred for the first row, including a shared parent
    // trunk/rail. A later row or skipped band must first pass obstacle checks.
    let points = simple;
    if (!clear(simple)) {
      const candidates = [...new Set([lower.x, upper.x,
        ...obstacles.flatMap(r => [r.left - 12, r.right + 12]),
        Math.min(...obstacles.map(r => r.left)) - 32,
        Math.max(...obstacles.map(r => r.right)) + 32])];
      const options = candidates.map(x => ({ x, points: [start, [upper.x, exitY], [x, exitY], [x, entryY], [lower.x, entryY], end] }))
        .filter(option => clear(option.points));
      // Prefer short tracks; avoid coincident long tracks for distinct targets.
      // Grid rows in the same parent/column share a gutter trunk; parallel
      // records for the same endpoints can also share geometry.
      const cost = x => Math.abs(x - upper.x) + 2 * Math.abs(x - lower.x) + tracks.filter(t => t.x === x && t.target !== lower.key &&
        !(t.source === upper.key && t.column === lower.x) &&
        Math.max(t.low, Math.min(exitY, entryY)) < Math.min(t.high, Math.max(exitY, entryY))).length * 1000;
      options.sort((a, b) => cost(a.x) - cost(b.x) || a.x - b.x);
      // Common row spacing guarantees clear horizontal exits and entries; the
      // exterior candidates therefore always provide a route for this layout.
      if (!options.length) throw new Error(`Connectivity layout has no clear orthogonal track: ${edge.key}`);
      points = options[0].points;
      tracks.push({ x: options[0].x, low: Math.min(exitY, entryY), high: Math.max(exitY, entryY), target: lower.key, source: upper.key, column: lower.x });
    }
    points = points.filter((point, i) => !i || point[0] !== points[i - 1][0] || point[1] !== points[i - 1][1]);
    routes[edge.key] = { points: reverse ? points.reverse() : points };
  }
  return routes;
}

export function connectivityBounds(nodes, routes = {}, groups = connectivityPositionGroups(nodes)) {
  const points = [...Object.values(routes).flatMap(route => route.points), ...groups.flatMap(g => [[g.left, g.top], [g.left + g.width, g.top + g.height]])];
  const minX = Math.min(0, ...nodes.map(n => n.x - CONNECTIVITY_NODE_WIDTH / 2 - 18), ...points.map(p => p[0]));
  const maxX = Math.max(0, ...nodes.map(n => n.x + CONNECTIVITY_NODE_WIDTH / 2 + 18), ...points.map(p => p[0]));
  const minY = Math.min(0, ...nodes.map(n => n.y - nodeHalfHeight(n)), ...points.map(p => p[1]));
  const maxY = Math.max(0, ...nodes.map(n => n.y + nodeHalfHeight(n) + 18), ...points.map(p => p[1]));
  return { minX, minY, width: maxX - minX, height: maxY - minY };
}

export function connectivityFit(bounds, width, height, zoom = 1) {
  const margin = 16; // Plus the existing 12px toolbar gap: 28px visually.
  const scale = Math.min(1, Math.max(1, width - margin * 2) / Math.max(1, bounds.width),
    Math.max(1, height - margin * 2) / Math.max(1, bounds.height)) * zoom;
  return { scale, canvasWidth: Math.max(width, bounds.width * scale + margin * 2),
    canvasHeight: Math.max(height, bounds.height * scale + margin * 2), top: margin };
}

// Compatibility metadata: ranks describe semantic order, not shared Y coordinates.
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
