// Pure geometry shared by operational Connectivity and the Showcase skin.
// Authorization and graph eligibility belong to the backend domain projection.
export const CONNECTIVITY_NODE_WIDTH = 180;
export const CONNECTIVITY_NODE_HEIGHT = 88;
export const CONNECTIVITY_RAIL_GAP = 16;

export const CONNECTIVITY_METRICS = Object.freeze({ nodeWidth: 180, nodeHeight: 88,
  columnGap: 32, rowGap: 32, railGap: 16, groupTop: 20, groupBottom: 48,
  columns: () => 4, separatePositions: true, footprintPadding: 16 });
const nodeOrder = (a, b) => Number(a.entity_type === "disclosure") - Number(b.entity_type === "disclosure") || a.name.localeCompare(b.name) || a.key.localeCompare(b.key);
const otherEnd = (edge, key) => edge.source_key === key ? edge.target_key : edge.source_key;
const nodeWidth = (node, metrics) => node.entity_type === "disclosure" ? 60 : node.geometry_width ?? metrics.nodeWidth;
const nodeHeight = (node, metrics) => node.entity_type === "disclosure" ? 60 : node.geometry_height ?? metrics.nodeHeight;
const nodeHalfHeight = (node, metrics = CONNECTIVITY_METRICS) => nodeHeight(node, metrics) / 2;
const topologyGroups = (nodes, metrics) => metrics.groups ? metrics.groups(nodes) : connectivityPositionGroups(nodes);

// Existing operational API: focus/disclosure/viewport behavior is unchanged.
export function connectivityLayout(graph) {
  return graph.nodes.some(n => n.key === graph.focus_key) ? calculateTopologyGeometry(graph) : [];
}
export function connectivityRoutes(nodes, edges, groups) { return routeTopologyEdges(nodes, edges, groups); }
export function connectivityBounds(nodes, routes, groups) { return topologyBounds(nodes, routes, groups); }

export function topologyGraphEligibility(graph, includeNetworks = true) {
  const nodes = graph.nodes.filter(n => includeNetworks || n.entity_type === "asset");
  const keys = new Set(nodes.map(n => n.key));
  return { ...graph, nodes, edges: (graph.edges || []).filter(e =>
    (includeNetworks || e.kind !== "membership") && keys.has(e.source_key) && keys.has(e.target_key)) };
}

export function buildTopologyLayoutModel(input) {
  const graph = topologyGraphEligibility(input);
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
  // Same-rank physical chains use distance from recorded upper anchors.
  // This supplies local depth without changing a managed rank or canonical edge.
  const localDepth = new Map(nodes.map(n => [n.key, 0]));
  const visited = new Set();
  for (const node of nodes) {
    if (visited.has(node.key)) continue;
    const component = [node.key]; visited.add(node.key);
    for (let i = 0; i < component.length; i++) for (const edge of adjacent.get(component[i])) {
      const next = otherEnd(edge, component[i]);
      if (edge.topology_class !== "physical_network" || edge.platform_parent_key ||
          byKey.get(next).entity_type === "network" || byKey.get(component[i]).entity_type === "network" ||
          ranks.get(next) !== ranks.get(component[i]) || visited.has(next)) continue;
      visited.add(next); component.push(next);
    }
    const anchors = component.filter(key => adjacent.get(key).some(e =>
      (e.platform_parent_key || e.topology_class === "physical_network") && ranks.get(otherEnd(e, key)) < ranks.get(key)));
    const distances = new Map(anchors.map(key => [key, 0])), queue = [...anchors].sort();
    for (let i = 0; i < queue.length; i++) for (const edge of adjacent.get(queue[i])) {
      const next = otherEnd(edge, queue[i]);
      if (edge.topology_class !== "physical_network" || edge.platform_parent_key ||
          !component.includes(next) || distances.has(next)) continue;
      distances.set(next, distances.get(queue[i]) + 1); queue.push(next);
    }
    for (const [key, depth] of distances) localDepth.set(key, depth);
  }
  const isUpper = (a, b) => ranks.get(a) < ranks.get(b) ||
    (ranks.get(a) === ranks.get(b) && localDepth.get(a) < localDepth.get(b));
  const parent = new Map();
  for (const node of nodes) {
    const candidates = adjacent.get(node.key).filter(e => isUpper(otherEnd(e, node.key), node.key) &&
      (e.platform_parent_key || e.topology_class === "physical_network" || e.kind === "membership"));
    candidates.sort((a, b) => Number(b.platform_parent_key === otherEnd(b, node.key)) - Number(a.platform_parent_key === otherEnd(a, node.key)) ||
      ranks.get(otherEnd(b, node.key)) - ranks.get(otherEnd(a, node.key)) || localDepth.get(otherEnd(b, node.key)) - localDepth.get(otherEnd(a, node.key)) || otherEnd(a, node.key).localeCompare(otherEnd(b, node.key)));
    if (candidates.length) parent.set(node.key, otherEnd(candidates[0], node.key));
  }
  return { nodes, edges, adjacent, ranks, parent, localDepth, isUpper };
}

export function calculateTopologyGeometry(graph, options = {}, prepared = buildTopologyLayoutModel(graph)) {
  if (!graph.nodes.length) return [];
  const metrics = { ...CONNECTIVITY_METRICS, ...options };
  const halfHeight = n => nodeHalfHeight(n, metrics);
  const groupsFor = placed => topologyGroups(placed, metrics);
  const { nodes, adjacent, ranks, parent, localDepth, isUpper } = prepared;

  const positions = new Map();
  const children = new Map(nodes.map(n => [n.key, []]));
  for (const node of nodes) if (parent.has(node.key)) children.get(parent.get(node.key)).push(node);
  const clusterKey = node => JSON.stringify([parent.get(node.key) || node.key, node.topology_position?.id || ranks.get(node.key), localDepth.get(node.key), node.presentation_group_key || null]);
  const clusters = new Map();
  for (const node of nodes) {
    const key = clusterKey(node);
    if (!clusters.has(key)) clusters.set(key, []);
    clusters.get(key).push(node);
  }
  const cellWidths = new Map([...clusters].map(([key, cluster]) => [key, Math.max(...cluster.map(n => nodeWidth(n, metrics))) + metrics.columnGap]));
  const cellWidthFor = node => cellWidths.get(clusterKey(node));
  const compactClusters = new Set([...clusters].filter(([, cluster]) =>
    cluster.filter(n => n.entity_type === "asset" && n.topology_position).length >= 2
  ).map(([key]) => key));
  const vertical = new Map();
  // Rank is ordinal. Only recorded upper neighbours impose vertical distance;
  // independent siblings never reserve empty rows in one another's branches.
  // Check every eligible upper neighbour, not just the primary horizontal anchor.
  const orderedClusters = [...clusters.values()].sort((a, b) => ranks.get(a[0].key) - ranks.get(b[0].key) || localDepth.get(a[0].key) - localDepth.get(b[0].key) || nodeOrder(a[0], b[0]));
  for (const cluster of orderedClusters) {
    const upper = cluster.flatMap(node => adjacent.get(node.key).filter(e =>
      (e.platform_parent_key || e.topology_class === "physical_network" || e.kind === "membership") &&
      isUpper(otherEnd(e, node.key), node.key)).map(e => otherEnd(e, node.key)));
    const hasContainer = groupsFor(cluster.map(n => ({ ...n, x: 0, y: 0, layout_parent_key: parent.get(n.key) }))).length > 0;
    const topInset = Math.max(...cluster.map(halfHeight)) + (hasContainer ? metrics.groupTop : 0);
    const base = Math.max(0, ...upper.map(key => vertical.get(key).bottom + metrics.railGap * 2 + topInset));
    const grid = compactClusters.has(clusterKey(cluster[0])) || cluster.every(n => !children.get(n.key).length);
    const columns = metrics.columns(cluster); // Presentation metrics never choose a parent.
    cluster.forEach((node, i) => {
      // A remainder control follows the real child grid; expansion is unchanged.
      const index = node.entity_type === "disclosure" ? Math.ceil(i / columns) * columns : i;
      const row = grid ? Math.floor(index / columns) : 0;
      vertical.set(node.key, { y: base + row * (Math.max(...cluster.map(n => nodeHeight(n, metrics))) + (typeof metrics.rowGap === "function" ? metrics.rowGap(cluster) : metrics.rowGap)), row, column: grid ? index % columns : i });
    });
    const bottom = Math.max(...cluster.map(n => vertical.get(n.key).y + halfHeight(n))) + (hasContainer ? metrics.groupBottom : 0);
    for (const node of cluster) vertical.get(node.key).bottom = hasContainer ? bottom : vertical.get(node.key).y + halfHeight(node);
  }
  const positioned = node => ({ ...node, ...vertical.get(node.key), rank: ranks.get(node.key), positionDepth: localDepth.get(node.key), layout_parent_key: parent.get(node.key) || null });
  const footprint = placed => [
    ...placed.map(n => ({ left: n.x - cellWidthFor(n) / 2, right: n.x + cellWidthFor(n) / 2, top: n.y - halfHeight(n) - metrics.footprintPadding, bottom: n.y + halfHeight(n) + metrics.footprintPadding })),
    ...groupsFor(placed).map(g => ({ left: g.left - metrics.footprintPadding, right: g.left + g.width + metrics.footprintPadding, top: g.top - metrics.footprintPadding, bottom: g.top + g.height + metrics.footprintPadding })),
  ];
  // Pack actual occupied geometry, including local containers, before centring
  // ancestors. Compatible subtree contours can share columns at different Y.
  const pack = (group, separatePositions = true) => {
    const blocks = [], siblingClusters = new Map();
    for (const node of group) {
      const key = clusterKey(node);
      if (!siblingClusters.has(key)) siblingClusters.set(key, []);
      siblingClusters.get(key).push(node);
    }
    if (siblingClusters.size > 1) blocks.push(...[...siblingClusters.values()].map(peers => pack(peers, false)));
    for (let i = siblingClusters.size > 1 ? group.length : 0; i < group.length;) {
      const current = group[i];
      if (children.get(current.key).length) { blocks.push(branch(current)); i++; continue; }
      const leaves = [];
      while (i < group.length && !children.get(group[i].key).length && clusterKey(group[i]) === clusterKey(current)) leaves.push(group[i++]);
      // Managed-position cards share aligned columns. Unboxed automatic
      // nodes retain their separate entry lanes for individual routing.
      const columns = [...new Set(leaves.map(n => vertical.get(n.key).column))].sort((a, b) => a - b);
      const offsets = new Map(), laneWidths = new Map();
      let laneWidth = 0;
      for (const column of columns) {
        offsets.set(column, laneWidth);
        const rows = Math.max(...leaves.filter(n => vertical.get(n.key).column === column).map(n => vertical.get(n.key).row));
        laneWidths.set(column, cellWidthFor(current) + (compactClusters.has(clusterKey(current)) ? 0 : rows * (metrics.nodeWidth / 2 + 18)));
        laneWidth += laneWidths.get(column);
      }
      const placed = leaves.map(node => ({ ...positioned(node), layout_lane_width: laneWidths.get(vertical.get(node.key).column), x: offsets.get(vertical.get(node.key).column) + (compactClusters.has(clusterKey(current)) ? 0 : vertical.get(node.key).row * (metrics.nodeWidth / 2 + 18)) + cellWidthFor(node) / 2 }));
      const cards = placed.filter(n => n.entity_type !== "disclosure");
      const gridWidth = Math.max(...(cards.length ? cards : placed).map(n => n.x)) + cellWidthFor(current) / 2;
      if (compactClusters.has(clusterKey(current))) for (const control of placed.filter(n => n.entity_type === "disclosure")) control.x = gridWidth / 2;
      blocks.push({ width: Math.max(gridWidth, ...placed.map(n => n.x + cellWidthFor(n) / 2)), nodes: placed });
    }
    let width = 0, previousPosition;
    const placed = [], occupied = [];
    for (const block of blocks) {
      const position = clusterKey(block.nodes[0]);
      let offset = separatePositions && metrics.separatePositions && previousPosition != null && position !== previousPosition ? width + 24 : 0;
      const rectangles = footprint(block.nodes);
      for (const a of rectangles) for (const b of occupied) {
        if (a.top < b.bottom && a.bottom > b.top) offset = Math.max(offset, b.right - a.left);
      }
      placed.push(...block.nodes.map(n => ({ ...n, x: n.x + offset })));
      occupied.push(...rectangles.map(r => ({ ...r, left: r.left + offset, right: r.right + offset })));
      width = Math.max(width, offset + block.width);
      previousPosition = position;
    }
    // Expanded children do not promote a high-fan-out sibling grid back to a
    // single row. Keep its cards together above the packed descendant forest.
    // Descendants start below the complete semantic group's bottom boundary.
    for (const [key, peers] of siblingClusters) {
      if (siblingClusters.size > 1) continue;
      if (!compactClusters.has(key) || peers.length <= metrics.columns(peers) || !peers.some(n => children.get(n.key).length)) continue;
      const keys = new Set(peers.map(n => n.key));
      const descendants = placed.filter(n => {
        let ancestor = parent.get(n.key);
        while (ancestor) { if (keys.has(ancestor)) return true; ancestor = parent.get(ancestor); }
        return false;
      });
      const centre = (Math.min(...descendants.map(n => n.x)) + Math.max(...descendants.map(n => n.x))) / 2;
      for (const node of placed.filter(n => keys.has(n.key))) node.x = centre + (node.entity_type === "disclosure" ? 0 : node.column - (metrics.columns(peers) - 1) / 2) * cellWidthFor(node);
    }
    if (placed.length) {
      const left = Math.min(...placed.map(n => n.x - cellWidthFor(n) / 2));
      width = Math.max(...placed.map(n => n.x + cellWidthFor(n) / 2)) - left;
      for (const node of placed) node.x -= left;
    }
    return { width: Math.max(group.length ? Math.max(...group.map(cellWidthFor)) : metrics.nodeWidth + metrics.columnGap, width), nodes: placed };
  };
  const branch = node => {
    const ordered = [...children.get(node.key)].sort((a, b) => ranks.get(a.key) - ranks.get(b.key) || nodeOrder(a, b));
    const block = pack(ordered);
    return { width: block.width, nodes: [{ ...positioned(node), x: block.width / 2 }, ...block.nodes] };
  };
  const roots = nodes.filter(n => !parent.has(n.key)).sort((a, b) => ranks.get(a.key) - ranks.get(b.key) || nodeOrder(a, b));
  for (const node of pack(roots, false).nodes) positions.set(node.key, node);
  // Focus changes the viewport origin, never the branch ordering.
  const focus = positions.get(graph.focus_key), origin = focus ? { x: focus.x, y: focus.y } : { x: 0, y: 0 };
  return (focus ? [focus, ...nodes.filter(n => n.key !== graph.focus_key).map(n => positions.get(n.key))] : nodes.map(n => positions.get(n.key)))
    .map(n => ({ ...n, x: n.x - origin.x, y: n.y - origin.y }));
}

// Membership is semantic, including singletons. Geometry and box visibility are
// separate concerns; movement and descendant expansion never split an identity.
export function connectivityPositionMembership(nodes) {
  const groups = new Map();
  for (const node of [...nodes].sort(nodeOrder)) {
    if (node.entity_type !== "asset" || !node.topology_position || !node.layout_parent_key) continue;
    const key = JSON.stringify([node.layout_parent_key, node.topology_position.id]);
    if (!groups.has(key)) groups.set(key, { key, parent_key: node.layout_parent_key,
      position_id: node.topology_position.id, name: node.topology_position.name, node_keys: [] });
    groups.get(key).node_keys.push(node.key);
  }
  return [...groups.values()].sort((a, b) => a.key.localeCompare(b.key));
}

export function connectivityPositionGroups(nodes) {
  return connectivityPositionMembership(nodes).filter(group => group.node_keys.length >= 2).map(group => {
    const controls = nodes.filter(n => n.entity_type === "disclosure" && n.parent_key === group.parent_key && n.topology_position?.id === group.position_id).sort(nodeOrder);
    const members = [...nodes.filter(n => group.node_keys.includes(n.key)), ...controls];
    const labelWidth = Math.min(240, Math.max(80, group.name.length * 8 + 8));
    const halfWidth = n => n.entity_type === "disclosure" ? 30 : CONNECTIVITY_NODE_WIDTH / 2;
    // Reserve a footer exit lane even for a parent in the leftmost column.
    const left = Math.min(Math.min(...members.map(n => n.x - halfWidth(n))) - 16,
      Math.min(...members.map(n => n.x)) - labelWidth - 24);
    const top = Math.min(...members.map(n => n.y - nodeHalfHeight(n))) - 20;
    const width = Math.max(...members.map(n => n.x + halfWidth(n))) + 16 - left;
    const height = Math.max(...members.map(n => n.y + nodeHalfHeight(n))) + 48 - top;
    let hash = 0;
    for (const char of group.position_id) hash = (Math.imul(hash, 31) + char.charCodeAt(0)) >>> 0;
    const accents = ["blue", "teal", "purple", "amber", "cyan", "rose", "green", "slate"];
    return { ...group, left, top, width, height, labelTop: height - 28,
      accent_key: accents[hash % accents.length], disclosure_keys: controls.map(n => n.key), labelWidth: Math.min(width - 24, labelWidth) };
  });
}

// The backend-projected parent is authoritative. Match all available semantic
// metadata conservatively; membership, physical and mixed relationships remain
// individual. The connector is never a domain edge or an inspector record.
function groupRelationships(group, edges) {
  const links = edges.filter(e => e.kind !== "disclosure" &&
    ((e.source_key === group.parent_key && group.node_keys.includes(e.target_key)) ||
     (e.target_key === group.parent_key && group.node_keys.includes(e.source_key))));
  if (!links.length || links.some(e => e.kind !== "relationship" || e.platform_parent_key !== group.parent_key || e.topology_class !== "platform")) return [];
  if (!group.node_keys.every(key => links.some(e => otherEnd(e, group.parent_key) === key))) return [];
  const family = e => JSON.stringify([e.relationship_type ?? e.label ?? null, e.directional, e.source_key === group.parent_key]);
  return new Set(links.map(family)).size === 1 ? links : [];
}

// All coordinates remain in layout space. Routes are reversed only at the end
// to retain canonical arrows, independently of vertical presentation direction.
// Bounded rectilinear visibility search for dense overlays when one exterior
// track is insufficient. Coordinates come only from obstacle boundaries/ports.
export function orthogonalDetour(start, end, rectangles, options = {}) {
  // Opt-in tracks use already-inflated boundaries: keep full card clearance
  // while finding narrow corridors omitted by the default 16px offset grid.
  const xs = [...new Set([start[0], end[0], ...rectangles.flatMap(r => [...(options.includeBoundaryTracks ? [r.left, r.right] : []), r.left - 16, r.right + 16])])].sort((a, b) => a - b);
  const ys = [...new Set([start[1], end[1], ...rectangles.flatMap(r => [...(options.includeBoundaryTracks ? [r.top, r.bottom] : []), r.top - 16, r.bottom + 16])])].sort((a, b) => a - b);
  const point = key => [xs[key % xs.length], ys[Math.floor(key / xs.length)]];
  const first = ys.indexOf(start[1]) * xs.length + xs.indexOf(start[0]);
  const last = ys.indexOf(end[1]) * xs.length + xs.indexOf(end[0]);
  const cost = new Map([[first, 0]]), previous = new Map(), heap = [];
  const push = item => {
    heap.push(item); let i = heap.length - 1;
    while (i > 0) { const p = (i - 1) >> 1; if (heap[p].score <= item.score) break; heap[i] = heap[p]; i = p; }
    heap[i] = item;
  };
  const pop = () => {
    const item = heap[0], tail = heap.pop();
    if (heap.length) {
      let i = 0;
      while (i * 2 + 1 < heap.length) {
        let child = i * 2 + 1;
        if (child + 1 < heap.length && heap[child + 1].score < heap[child].score) child++;
        if (tail.score <= heap[child].score) break;
        heap[i] = heap[child]; i = child;
      }
      heap[i] = tail;
    }
    return item;
  };
  push({ key: first, distance: 0, score: 0 });
  while (heap.length) {
    const current = pop();
    if (current.distance !== cost.get(current.key)) continue;
    if (current.key === last) {
      const path = [point(last)]; let key = last;
      while (previous.has(key)) { key = previous.get(key); path.push(point(key)); }
      const points = path.reverse();
      return points.filter((p, i) => !i || i === points.length - 1 ||
        !((p[0] === points[i-1][0] && p[0] === points[i+1][0]) || (p[1] === points[i-1][1] && p[1] === points[i+1][1])));
    }
    const [x, y] = point(current.key), xi = current.key % xs.length, yi = Math.floor(current.key / xs.length);
    const neighbours = [xi > 0 ? current.key - 1 : -1, xi + 1 < xs.length ? current.key + 1 : -1,
      yi > 0 ? current.key - xs.length : -1, yi + 1 < ys.length ? current.key + xs.length : -1];
    for (const key of neighbours.filter(k => k >= 0)) {
      const [nx, ny] = point(key), distance = current.distance + Math.abs(nx - x) + Math.abs(ny - y);
      if (distance >= (cost.get(key) ?? Infinity)) continue;
      const blocked = rectangles.some(r => nx === x
        ? x > r.left && x < r.right && Math.max(y, ny) > r.top && Math.min(y, ny) < r.bottom
        : y > r.top && y < r.bottom && Math.max(x, nx) > r.left && Math.min(x, nx) < r.right);
      if (blocked) continue;
      cost.set(key, distance); previous.set(key, current.key);
      push({ key, distance, score: distance + Math.abs(nx - end[0]) + Math.abs(ny - end[1]) });
    }
  }
  return null;
}


// Showcase opt-in only. Keep real cards and labels protected while permitting
// an endpoint to enter/leave its own presentation container.
function safeFallbackRoute(upper, lower, connection, sourceGroup, targetGroup, start, end, obstacles, containers, metrics) {
  const occupied = [...obstacles, ...containers];
  const barriers = [...obstacles, ...containers.filter(r => r.key !== sourceGroup?.key && r.key !== targetGroup?.key)];
  const inside = (point, r) => point[0] > r.left && point[0] < r.right && point[1] > r.top && point[1] < r.bottom;
  const clear = points => points.slice(1).every((p, i) => !barriers.some(r => p[0] === points[i][0]
    ? p[0] > r.left && p[0] < r.right && Math.max(p[1], points[i][1]) > r.top && Math.min(p[1], points[i][1]) < r.bottom
    : p[1] > r.top && p[1] < r.bottom && Math.max(p[0], points[i][0]) > r.left && Math.min(p[0], points[i][0]) < r.right));
  const length = points => points.slice(1).reduce((sum, p, i) => sum + Math.abs(p[0] - points[i][0]) + Math.abs(p[1] - points[i][1]), 0);
  const ports = (node, group, preferred) => {
    const left = group ? group.left : node.x - nodeWidth(node, metrics) / 2 - 8;
    const right = group ? group.left + group.width : node.x + nodeWidth(node, metrics) / 2 + 8;
    const top = group ? group.top : node.y - nodeHalfHeight(node, metrics) - 8;
    const bottom = group ? group.top + group.height : node.y + nodeHalfHeight(node, metrics) + 8;
    const x = group ? (left + right) / 2 : node.x, y = group ? (top + bottom) / 2 : node.y;
    const xs = group ? [x, left + 24, right - 24] : [x, node.x - nodeWidth(node, metrics) / 4, node.x + nodeWidth(node, metrics) / 4];
    const ys = group ? [y, top + 24, bottom - 24] : [y, node.y - nodeHalfHeight(node, metrics) / 2, node.y + nodeHalfHeight(node, metrics) / 2];
    return [...new Map([preferred, ...xs.flatMap(x => [[x, top], [x, bottom]]), ...ys.flatMap(y => [[left, y], [right, y]])]
      .filter(p => !barriers.some(r => inside(p, r))).map(p => [p.join(","), p])).values()];
  };
  const starts = ports(upper, null, start), ends = ports(lower, connection, end);
  const pick = candidates => candidates.sort((a, b) => length(a.points) - length(b.points) ||
    JSON.stringify(a.points).localeCompare(JSON.stringify(b.points)))[0];
  // A fixed member port can land in its own group's title. Repair that port
  // locally before considering an exterior detour; keep the title an obstacle.
  const headerBlocked = obstacles.some(r => (r.key === sourceGroup?.key && inside(start, r)) ||
    (r.key === targetGroup?.key && inside(end, r)));
  if (headerBlocked) {
    const candidates = [];
    for (const from of starts) for (const to of ends) {
      const points = orthogonalDetour(from, to, barriers, { includeBoundaryTracks: true });
      if (points && clear(points)) candidates.push({ points, fallback_routing: "group-port" });
    }
    if (candidates.length) return pick(candidates);
  }
  const gutter = Math.max(16, metrics.railGap);
  const directions = [
    ["left", 0, Math.min(...occupied.map(r => r.left)) - gutter],
    ["right", 0, Math.max(...occupied.map(r => r.right)) + gutter],
    ["top", 1, Math.min(...occupied.map(r => r.top)) - gutter],
    ["bottom", 1, Math.max(...occupied.map(r => r.bottom)) + gutter],
  ];
  const candidates = [];
  for (const [direction, axis, coordinate] of directions) {
    // Cache each access leg within this edge; pairwise candidates reuse it.
    const access = port => {
      const outside = [...port]; outside[axis] = coordinate;
      const direct = [port, outside];
      return clear(direct) ? direct : orthogonalDetour(port, outside, barriers, { includeBoundaryTracks: true });
    };
    const exits = starts.map(access).filter(Boolean), entries = ends.map(access).filter(Boolean);
    for (const exit of exits) for (const entry of entries) {
      const points = [...exit, ...[...entry].reverse()];
      if (clear(points)) candidates.push({ points, fallback_routing: "exterior", exterior_direction: direction });
    }
  }
  return pick(candidates) || null;
}

function routingFailureDetail(edge, source, target, sourceGroup, targetGroup, start, end, exitY, entryY, rectangles, candidateCount, membership, preferredPath) {
  const describe = node => ({ key: node.key, name: node.name, topologyPosition: node.topology_position?.id || null,
    topologyPositionName: node.topology_position?.name || null, topologyPositionKey: node.topology_position?.key || null, x: node.x, y: node.y });
  const inside = point => rectangles.filter(r => point[0] > r.left && point[0] < r.right && point[1] > r.top && point[1] < r.bottom).map(r => r.key);
  return { relationshipKey: edge.key, relationshipType: edge.relationship_type || edge.label || null,
    source: describe(source), target: describe(target), sourceGroupKey: membership.get(source.key)?.key || null, targetGroupKey: membership.get(target.key)?.key || null,
    startGroupKey: sourceGroup?.key || null, endGroupKey: targetGroup?.key || null,
    start, end, exitY, entryY, candidateCount,
    startBlockedBy: inside(start), endBlockedBy: inside(end),
    preferredPathRejections: preferredPath.slice(1).flatMap((point, index, tail) => {
      const previous = index ? tail[index - 1] : start;
      const blocked = rectangles.filter(r => point[0] === previous[0]
        ? point[0] > r.left && point[0] < r.right && Math.max(point[1], previous[1]) > r.top && Math.min(point[1], previous[1]) < r.bottom
        : point[1] > r.top && point[1] < r.bottom && Math.max(point[0], previous[0]) > r.left && Math.min(point[0], previous[0]) < r.right);
      return blocked.length ? [{ segment: [previous, point], obstacles: blocked }] : [];
    }),
    reason: "Fixed attachment/rail candidates and bounded visibility search could not clear card, label and container obstacles." };
}

export function routeTopologyEdges(nodes, edges, groups, options = {}) {
  const metrics = { ...CONNECTIVITY_METRICS, ...options };
  groups ??= topologyGroups(nodes, metrics);
  const halfHeight = n => nodeHalfHeight(n, metrics);
  const positions = Object.fromEntries(nodes.map(n => [n.key, n]));
  const obstacles = nodes.map(n => ({ key: n.key,
    left: n.x - (n.entity_type === "disclosure" ? 30 : nodeWidth(n, metrics) / 2) - 6,
    right: n.x + (n.entity_type === "disclosure" ? 30 : nodeWidth(n, metrics) / 2) + 6,
    top: n.y - halfHeight(n) - 6, bottom: n.y + halfHeight(n) + 6 }));
  obstacles.push(...groups.map(g => ({ key: g.key, left: g.left + 10, right: g.left + 14 + g.labelWidth,
    top: g.top + g.labelTop - 2, bottom: g.top + g.labelTop + 22 })));
  const containerByNode = new Map(groups.flatMap(g => [...g.node_keys, ...g.disclosure_keys].map(key => [key, g])));
  const containers = groups.map(g => ({ key: g.key, left: g.left, right: g.left + g.width, top: g.top, bottom: g.top + g.height }));
  let sourceGroup, targetGroup;
  const clear = points => points.slice(1).every(([x, y], i) => {
    const [px, py] = points[i];
    const barriers = [...obstacles, ...containers.filter(r => {
      if (r.key === sourceGroup?.key && r.key === targetGroup?.key) return false;
      return !(x === px && ((i === 0 && r.key === sourceGroup?.key) || (i === points.length - 2 && r.key === targetGroup?.key)));
    })];
    return barriers.every(r => x === px
      ? x <= r.left || x >= r.right || Math.max(y, py) <= r.top || Math.min(y, py) >= r.bottom
      : y <= r.top || y >= r.bottom || Math.max(x, px) <= r.left || Math.min(x, px) >= r.right);
  });
  const tracks = [];
  const routes = {};
  const connectionByEdge = new Map();
  for (const group of groups) {
    const links = groupRelationships(group, edges);
    if (!links.length || !positions[group.parent_key] || positions[group.parent_key].y >= group.top) continue;
    for (const link of [...links, ...edges.filter(e => e.kind === "disclosure" && group.disclosure_keys.includes(e.target_key))]) connectionByEdge.set(link.key, group);
  }
  const renderedGroups = new Set();
  const ordered = [...edges].sort((a, b) => a.key.localeCompare(b.key));
  for (const edge of ordered) {
    const source = positions[edge.source_key], target = positions[edge.target_key];
    if (!source || !target) continue;
    const reverse = source.y > target.y || (source.y === target.y && source.key > target.key);
    const [upper, actualLower] = reverse ? [target, source] : [source, target];
    const connection = connectionByEdge.get(edge.key);
    const lower = connection ? { ...actualLower,
      x: Math.max(connection.left + 24, Math.min(connection.left + connection.width - 24, upper.x)),
      y: connection.top + halfHeight(actualLower) + 8 } : actualLower;
    sourceGroup = containerByNode.get(upper.key); targetGroup = containerByNode.get(lower.key);
    const sameGroup = sourceGroup && sourceGroup === targetGroup;
    const sameRow = upper.y === lower.y && upper.key !== lower.key;
    const start = [upper.x, upper.y + (sameRow ? -1 : 1) * (halfHeight(upper) + 8)];
    const end = [lower.x, lower.y - halfHeight(lower) - 8];
    // External rails sit in reserved whitespace, never inside either group.
    const exitY = sameGroup ? upper.y + (sameRow ? -1 : 1) * (halfHeight(upper) + 12)
      : sameRow ? (sourceGroup?.top ?? upper.y - halfHeight(upper)) - metrics.railGap
      : (sourceGroup ? sourceGroup.top + sourceGroup.height : upper.y + halfHeight(upper)) + metrics.railGap;
    const entryY = sameGroup ? lower.y - halfHeight(lower) - 12
      : (targetGroup?.top ?? lower.y - halfHeight(lower)) - metrics.railGap;
    const simple = sameRow
      ? [start, [upper.x, entryY], [lower.x, entryY], end]
      : [start, [upper.x, exitY], [lower.x, exitY], end];
    // A direct drop is preferred for the first row, including a shared parent
    // trunk/rail. A later row or skipped band must first pass obstacle checks.
    let points = simple, internalRouting = false, fallback;
    if (!clear(simple)) {
      const candidates = [...new Set([lower.x, upper.x,
        ...[...obstacles, ...containers].flatMap(r => [r.left - 16, r.right + 16]),
        Math.min(...obstacles.map(r => r.left)) - 32,
        Math.max(...obstacles.map(r => r.right)) + 32])];
      const options = candidates.map(x => ({ x, points: [start, [upper.x, exitY], [x, exitY], [x, entryY], [lower.x, entryY], end] }))
        .filter(option => clear(option.points));
      // Prefer short tracks; avoid coincident long tracks for distinct targets.
      // Parallel records for the same endpoints may share geometry.
      const cost = x => Math.abs(x - upper.x) + 2 * Math.abs(x - lower.x) + tracks.filter(t => t.x === x && t.target !== lower.key &&
        !(t.source === upper.key && t.column === lower.x) &&
        Math.max(t.low, Math.min(exitY, entryY)) < Math.min(t.high, Math.max(exitY, entryY))).length * 1000;
      options.sort((a, b) => cost(a.x) - cost(b.x) || a.x - b.x);
      if (options.length) {
        points = options[0].points;
        tracks.push({ x: options[0].x, low: Math.min(exitY, entryY), high: Math.max(exitY, entryY), target: lower.key, source: upper.key, column: lower.x });
      } else {
        const detour = orthogonalDetour([upper.x, exitY], [lower.x, entryY],
          [...obstacles, ...containers.filter(r => !(sameGroup && r.key === sourceGroup.key))]);
        if (detour && clear([start, ...detour, end])) points = [start, ...detour, end];
        else {
          // An individual overlay can terminate inside a dense grid. Route
          // through its card gaps; unrelated containers remain obstacles.
          const internal = orthogonalDetour(start, end, [...obstacles,
            ...containers.filter(r => r.key !== sourceGroup?.key && r.key !== targetGroup?.key)]);
          if (internal) { points = internal; internalRouting = true; }
          else {
            const detail = routingFailureDetail(edge, source, target, sourceGroup, targetGroup, start, end, exitY, entryY,
              [...obstacles, ...containers.filter(r => r.key !== sourceGroup?.key && r.key !== targetGroup?.key)], candidates.length, containerByNode, simple);
            if (metrics.allowExteriorFallback) fallback = safeFallbackRoute(upper, actualLower, connection, sourceGroup, targetGroup,
              start, end, obstacles, containers, metrics);
            if (!fallback) {
              const error = new Error(`Connectivity layout has no clear orthogonal track: ${edge.key}`);
              error.routingDiagnostic = detail;
              throw error;
            }
            points = fallback.points;
            fallback.diagnostic = detail;
          }
        }
      }
    }
    points = points.filter((point, i) => !i || point[0] !== points[i - 1][0] || point[1] !== points[i - 1][1]);
    routes[edge.key] = { points: reverse ? points.reverse() : points,
      ...(internalRouting ? { internal_routing: true } : {}),
      ...(fallback ? { fallback_routing: fallback.fallback_routing,
        ...(fallback.exterior_direction ? { exterior_direction: fallback.exterior_direction } : {}),
        routing_diagnostic: fallback.diagnostic } : {}),
      ...(connection ? { group_key: connection.key, member_keys: connection.node_keys,
        render: !renderedGroups.has(connection.key) } : {}) };
    if (connection) renderedGroups.add(connection.key);
  }
  return routes;
}

export function topologyBounds(nodes, routes = {}, groups, options = {}) {
  const metrics = { ...CONNECTIVITY_METRICS, ...options };
  groups ??= topologyGroups(nodes, metrics);
  const points = [...Object.values(routes).flatMap(route => route.points), ...groups.flatMap(g => [[g.left, g.top], [g.left + g.width, g.top + g.height]])];
  const minX = Math.min(0, ...nodes.map(n => n.x - nodeWidth(n, metrics) / 2 - 18), ...points.map(p => p[0]));
  const maxX = Math.max(0, ...nodes.map(n => n.x + nodeWidth(n, metrics) / 2 + 18), ...points.map(p => p[0]));
  const minY = Math.min(0, ...nodes.map(n => n.y - nodeHalfHeight(n, metrics)), ...points.map(p => p[1]));
  const maxY = Math.max(0, ...nodes.map(n => n.y + nodeHalfHeight(n, metrics) + 18), ...points.map(p => p[1]));
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
