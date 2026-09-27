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

// Route same-lane dependencies along a separate left gutter, reserving the
// right gutter for Service→Asset connectors. Endpoints keep semantic direction.
export function landscapeEdgePath(source, target, layout, track = 0) {
  const sourceWidth = source.width || layout.nodeWidth;
  const sourceHeight = source.height || layout.nodeHeight;
  const targetHeight = target.height || layout.nodeHeight;
  const y1 = source.y + sourceHeight / 2, y2 = target.y + targetHeight / 2;
  const offset = 12 + track % 4 * 6;
  if (Math.abs(source.x - target.x) < layout.nodeWidth) {
    const rail = Math.min(source.x, target.x) - offset;
    return `M${source.x} ${y1} H${rail} V${y2} H${target.x}`;
  }
  const right = source.x < target.x;
  const x1 = source.x + (right ? sourceWidth : 0), x2 = target.x + (right ? 0 : layout.nodeWidth);
  const rail = right ? Math.min(x2 - 10, x1 + offset) : Math.max(x2 + 10, x1 - offset);
  return `M${x1} ${y1} H${rail} V${y2} H${x2}`;
}
