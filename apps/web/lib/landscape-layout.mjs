import { landscapeGeometry } from "./landscape-geometry.mjs";

const compare = (a, b) => a.name.localeCompare(b.name) || a.key.localeCompare(b.key);

// Deterministic presentation only. Cluster Assets beside their first connected
// Service, keeping members of each requirement together. Shared Assets have one
// position and retain every incoming edge. No domain direction is rewritten.
export function layoutLandscape(presentation, width, expanded = false, compact = false) {
  const geometry = landscapeGeometry(width, expanded);
  const gutter = expanded ? 52 : 44;
  const minimumWidth = expanded ? 224 : 200;
  const nodeWidth = compact ? Math.max(222, width / 3) - 36 : Math.min(geometry.nodeWidth, Math.max(minimumWidth, (width - 32) / 3 - gutter));
  const stepX = compact ? Math.max(222, width / 3) : Math.max(geometry.stepX, nodeWidth + gutter);
  const nodeHeight = compact ? 64 : geometry.nodeHeight;
  const positions = new Map(), groups = new Map();
  const lanes = presentation.lanes;
  const services = [...lanes.find(lane => lane.type === "service").nodes];
  const assets = [...lanes.find(lane => lane.type === "asset").nodes];
  const functions = [...lanes.find(lane => lane.type === "business_function").nodes];
  const edges = presentation.edges;
  const functionsByService = new Map(services.map(node => [node.key, edges.filter(edge => edge.source_key === node.key && edge.edge_family === "service_business_function").map(edge => edge.target.name).sort().join(" ")]));
  services.sort((a, b) => (functionsByService.get(a.key) || "\uffff").localeCompare(functionsByService.get(b.key) || "\uffff") || compare(a, b));
  const rank = new Map(services.map((node, index) => [node.key, index]));
  const owner = new Map();
  for (const asset of assets) {
    const incoming = edges.filter(edge => edge.edge_family === "service_asset" && edge.target_key === asset.key).sort((a, b) => rank.get(a.source_key) - rank.get(b.source_key) || a.key.localeCompare(b.key));
    if (incoming.length) owner.set(asset.key, incoming[0]);
  }
  const rowGap = compact ? 90 : nodeHeight + 30;
  let serviceCursor = 86, nextAssetY = 86;
  for (const service of services) {
    const children = assets.filter(asset => owner.get(asset.key)?.source_key === service.key).sort((a, b) => {
      const left = owner.get(a.key), right = owner.get(b.key);
      return (left.dependency_group_id || "~").localeCompare(right.dependency_group_id || "~") || compare(a, b);
    });
    const cursor = Math.max(serviceCursor, children.length ? nextAssetY : 0);
    const groupEdges = new Map();
    if (!compact) for (const edge of edges) if (edge.source_key === service.key && edge.dependency_group_id && edge.presentation_group_size > 1) {
      if (!groupEdges.has(edge.dependency_group_id)) groupEdges.set(edge.dependency_group_id, []);
      groupEdges.get(edge.dependency_group_id).push(edge);
    }
    positions.set(service.key, { x: stepX + 12, y: cursor, node: service });
    children.forEach((asset, index) => positions.set(asset.key, { x: stepX * 2 + 12, y: cursor + index * rowGap, node: asset }));
    [...groupEdges.entries()].sort(([a], [b]) => a.localeCompare(b)).forEach(([id, members], index) => {
      const key = `dependency_group:${id}`;
      groups.set(key, { ...members[0], key, x: stepX + 38, y: cursor + nodeHeight + 12 + index * 52, width: nodeWidth - 26, height: 44, edges: members });
    });
    serviceCursor = cursor + Math.max(rowGap, groupEdges.size ? nodeHeight + 24 + groupEdges.size * 52 : 0);
    if (children.length) nextAssetY = cursor + children.length * rowGap;
  }
  let assetCursor = Math.max(86, ...[...positions.values()].filter(p => p.node.entity_type === "asset").map(p => p.y + rowGap));
  assets.filter(asset => !owner.has(asset.key)).sort(compare).forEach(asset => {
    positions.set(asset.key, { x: stepX * 2 + 12, y: assetCursor, node: asset }); assetCursor += rowGap;
  });
  const desiredFunctionY = node => {
    const linked = edges.filter(edge => edge.edge_family === "service_business_function" && edge.target_key === node.key).map(edge => positions.get(edge.source_key)?.y).filter(value => value !== undefined);
    return linked.length ? linked.reduce((sum, value) => sum + value, 0) / linked.length : 86;
  };
  let functionCursor = 86;
  functions.sort((a, b) => desiredFunctionY(a) - desiredFunctionY(b) || compare(a, b)).forEach(node => {
    const y = Math.max(functionCursor, desiredFunctionY(node));
    positions.set(node.key, { x: 12, y, node }); functionCursor = y + rowGap;
  });
  const height = Math.max(250, ...[...positions.values()].map(position => position.y + nodeHeight + 24), ...[...groups.values()].map(group => group.y + group.height + 24));
  return { nodeWidth, nodeHeight, stepX, positions, groups: [...groups.values()], width: stepX * 3, height };
}

// Side-centred anchors with small, explicit port offsets. Cubic controls stay
// inside the inter-lane gutter; same-lane edges bend into the left gutter.
export function landscapeEdgePath(source, target, layout, track = 0, ports = {}) {
  const sw = source.width || layout.nodeWidth, sh = source.height || layout.nodeHeight;
  const th = target.height || layout.nodeHeight;
  const y1 = source.y + sh / 2 + (ports.source || 0), y2 = target.y + th / 2 + (ports.target || 0);
  if (Math.abs(source.x - target.x) < layout.nodeWidth) {
    const bend = Math.min(34, Math.max(12, layout.stepX - layout.nodeWidth - 10));
    const rail = Math.min(source.x, target.x) - bend + track % 3 * 3;
    const midY = (y1 + y2) / 2;
    return `M${source.x} ${y1} C${rail} ${y1},${rail} ${y1},${rail} ${midY} C${rail} ${y2},${rail} ${y2},${target.x} ${y2}`;
  }
  const right = source.x < target.x;
  const x1 = source.x + (right ? sw : 0), x2 = target.x + (right ? 0 : layout.nodeWidth);
  const gap = x2 - x1;
  return `M${x1} ${y1} C${x1 + gap * .48} ${y1},${x2 - gap * .48} ${y2},${x2} ${y2}`;
}

export function landscapeGroupPath(subject, group, layout) {
  const bottom = subject.y + layout.nodeHeight;
  if (group.y - bottom <= 16) {
    const x1 = subject.x + layout.nodeWidth * .8, x2 = group.x + group.width * .8;
    const mid = (bottom + group.y) / 2;
    return `M${x1} ${bottom} C${x1} ${mid},${x2} ${mid},${x2} ${group.y}`;
  }
  // Later requirements must not run through the intervening group markers.
  const x = subject.x + layout.nodeWidth, y = bottom - 12;
  const endX = group.x + group.width, endY = group.y + 10;
  const rail = x + Math.min(24, (layout.stepX - layout.nodeWidth) / 2);
  return `M${x} ${y} C${rail} ${y},${rail} ${endY},${endX} ${endY}`;
}

// Ports are sorted by the opposite endpoint's position, then durable edge key.
// Reordering an API response or selecting a node must not reshuffle connectors.
export function routeLandscape(presentation, layout) {
  const groups = new Map(layout.groups.map(group => [group.dependency_group_id, group]));
  const routes = presentation.edges.map(edge => {
    const group = groups.get(edge.dependency_group_id);
    const source = group || layout.positions.get(edge.source_key), target = layout.positions.get(edge.target_key);
    const sameLane = Math.abs(source.x - target.x) < layout.nodeWidth;
    const right = source.x < target.x && !sameLane;
    return { key: edge.key, edge, group, source, target, sourceSide: sameLane || !right ? "left" : "right", targetSide: sameLane || right ? "left" : "right", sourcePort: 0, targetPort: 0 };
  });
  for (const end of ["source", "target"]) {
    const buckets = new Map();
    for (const route of routes) {
      const identity = end === "source" && route.group ? route.group.key : route.edge[`${end}_key`];
      const key = `${identity}:${route[`${end}Side`]}`;
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key).push(route);
    }
    for (const bucket of buckets.values()) {
      const opposite = end === "source" ? "target" : "source";
      bucket.sort((a, b) => a[opposite].y - b[opposite].y || a.key.localeCompare(b.key));
      const spread = Math.min(20, (bucket.length - 1) * 8);
      bucket.forEach((route, index) => { route[`${end}Port`] = bucket.length > 1 ? -spread / 2 + index * spread / (bucket.length - 1) : 0; });
    }
  }
  return routes.sort((a, b) => a.key.localeCompare(b.key)).map((route, index) => ({ ...route, path: landscapeEdgePath(route.source, route.target, layout, index, { source: route.sourcePort, target: route.targetPort }) }));
}

export function selectedLandscapeEdges(edges, selected, groupId = "") {
  if (groupId) return new Set(edges.filter(edge => edge.dependency_group_id === groupId).map(edge => edge.key));
  const groupIds = new Set();
  for (const edge of edges) if ((edge.source_key === selected || edge.target_key === selected) && edge.dependency_group_id) groupIds.add(edge.dependency_group_id);
  return new Set(edges.filter(edge => edge.source_key === selected || edge.target_key === selected || groupIds.has(edge.dependency_group_id)).map(edge => edge.key));
}
