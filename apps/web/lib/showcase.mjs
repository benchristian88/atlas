import { byName, orthogonalDetour } from "./infrastructure-topology.mjs";

export const SHOWCASE_WIDTH = 1920;
export const SHOWCASE_HEIGHT = 1080;
export const SHOWCASE_MIN_SCALE = 0.86; // 14px secondary text remains at least 12 logical pixels.
export const SHOWCASE_PREVIEW_COUNT = 4;
const order = (a, b) => (a.position?.sort_order ?? Infinity) - (b.position?.sort_order ?? Infinity) ||
  (a.kind === "category" && b.kind === "category" ? (a.category?.sort_order ?? 0) - (b.category?.sort_order ?? 0) : 0) || byName(a, b);
const other = (edge, key) => edge.source_key === key ? edge.target_key : edge.source_key;

// A presentation forest only. Canonical direction/hosting comes from the API;
// all remaining edges survive as cross-links, including cycles and shared hosts.
export function showcaseModel(data, siteId) {
  if (!siteId) return { error: "Select a current site to create its Showcase." };
  if (!Array.isArray(data.structural_edges)) return { error: "Showcase incomplete: structural data is unavailable. Refresh after updating the API." };
  const types = new Map(data.asset_types.map(t => [t.key, t]));
  const categories = new Map(data.categories.map(c => [c.id, c]));
  const nodes = data.assets.filter(a => a.site_id === siteId).map(asset => ({
    key: `asset:${asset.id}`, id: asset.id, name: asset.name, asset,
    type: types.get(asset.asset_type), position: types.get(asset.asset_type)?.topology_position,
    category: categories.get(types.get(asset.asset_type)?.category_id),
  })).sort(order);
  const byKey = new Map(nodes.map(n => [n.key, n]));
  const networkKeys = new Set(data.structural_edges.filter(e => e.kind === "membership" && byKey.has(e.source_key)).map(e => e.target_key));
  for (const network of data.networks || []) if (networkKeys.has(`network:${network.id}`)) {
    const node = { key: `network:${network.id}`, id: network.id, name: network.name, network };
    nodes.push(node); byKey.set(node.key, node);
  }
  const edges = data.structural_edges.filter(e => byKey.has(e.source_key) && byKey.has(e.target_key)).sort((a, b) => a.key.localeCompare(b.key));
  const adjacent = new Map(nodes.map(n => [n.key, []]));
  for (const edge of edges) {
    adjacent.get(edge.source_key).push(edge);
    if (edge.target_key !== edge.source_key) adjacent.get(edge.target_key).push(edge);
  }
  const parents = new Map(), parentEdges = new Map();
  const attach = (child, parent, edge) => {
    if (parents.has(child) || child === parent) return;
    let cursor = parent;
    while (cursor) { if (cursor === child) return; cursor = parents.get(cursor); }
    parents.set(child, parent); parentEdges.set(child, edge);
  };
  // Hosting takes priority even if managed position ordering is unconventional.
  for (const edge of edges.filter(e => e.platform_parent_key).sort((a, b) => order(byKey.get(a.platform_parent_key), byKey.get(b.platform_parent_key)) || a.key.localeCompare(b.key))) {
    attach(other(edge, edge.platform_parent_key), edge.platform_parent_key, edge);
  }
  // Walk actual physical adjacency from managed-position roots. This retains
  // hierarchy between switches at the same position, without inventing links.
  const visited = new Set();
  for (const root of [...nodes].sort(order)) {
    if (visited.has(root.key)) continue;
    const queue = [root.key]; visited.add(root.key);
    for (let i = 0; i < queue.length; i++) {
      const key = queue[i];
      const neighbours = adjacent.get(key).filter(e => !e.platform_parent_key && e.kind !== "membership").sort((a, b) => order(byKey.get(other(a, key)), byKey.get(other(b, key))) || a.key.localeCompare(b.key));
      for (const edge of neighbours) {
        const next = other(edge, key);
        if (visited.has(next)) continue;
        visited.add(next); queue.push(next); attach(next, key, edge);
      }
    }
  }
  // Membership is never used to manufacture Asset-to-Asset parentage.
  for (const node of nodes.filter(n => n.network)) {
    const candidates = adjacent.get(node.key).sort((a, b) => order(byKey.get(other(a, node.key)), byKey.get(other(b, node.key))));
    if (candidates.length) attach(node.key, other(candidates[0], node.key), candidates[0]);
  }
  const children = new Map(nodes.map(n => [n.key, []]));
  for (const [child, parent] of parents) children.get(parent).push(byKey.get(child));
  for (const group of children.values()) group.sort(order);
  return { nodes, byKey, edges, adjacent, parents, parentEdges, children,
    roots: nodes.filter(n => !parents.has(n.key)).sort(order), assetCount: nodes.filter(n => n.asset).length };
}

function presentation(model, stage) {
  const representatives = new Map(), items = new Map();
  for (const node of model.nodes) { items.set(node.key, { ...node, kind: "asset", members: [node], children: [] }); representatives.set(node.key, node.key); }
  const typesWithChildren = new Set(model.nodes.filter(n => model.children.get(n.key).length).map(n => n.type?.key));
  for (const parent of [...model.nodes, { key: null }]) {
    const groups = new Map();
    const siblings = parent.key ? model.children.get(parent.key) : model.roots.filter(n => !model.adjacent.get(n.key).length);
    for (const child of siblings) {
      if (!child.asset || model.children.get(child.key).length) continue;
      const hosted = Boolean(parent.key && model.parentEdges.get(child.key)?.platform_parent_key === parent.key);
      // Only the managed Workload position (or an Automatic hosted leaf) is a
      // workload. Named host positions stay explicit even when currently empty.
      const workload = hosted && (!child.position || child.position.key === "workload");
      // The existing built-in access_point key is seeded at Access Network;
      // other/custom endpoint Types can use the managed Endpoint position.
      // Never collapse named host/network positions simply because they are leaves.
      const endpoint = !hosted && !typesWithChildren.has(child.type?.key) &&
        (child.position?.key === "endpoint" || child.type?.key === "access_point" || (stage >= 2 && !child.position));
      if (!workload && !endpoint) continue;
      // Shared/multihomed leaves group only with identical actual neighbours.
      const signature = model.adjacent.get(child.key).map(e => `${other(e, child.key)}:${e.kind}:${e.topology_class}:${e.platform_parent_key || ""}`).sort().join("|");
      const key = `${parent.key}/${workload ? "category" : "type"}/${workload ? child.category?.id || "uncategorized" : child.type?.key}/${signature}`;
      if (!groups.has(key)) groups.set(key, { key, parent: parent.key, kind: workload ? "category" : "type", category: child.category, type: child.type, members: [], children: [] });
      groups.get(key).members.push(child);
    }
    for (const group of groups.values()) {
      if (group.kind === "type" && group.members.length < (stage >= 2 ? 3 : 2)) continue;
      group.members.sort(byName);
      group.name = group.kind === "category" ? group.category?.name || "Uncategorized" : group.type?.name || "Assets";
      group.id = group.key;
      group.position = group.members[0].position;
      group.preview = group.members.slice(0, group.kind === "type" || stage >= 1 ? SHOWCASE_PREVIEW_COUNT : group.members.length);
      group.hiddenCount = group.members.length - group.preview.length;
      items.set(group.key, group);
      for (const member of group.members) { items.delete(member.key); representatives.set(member.key, group.key); }
    }
  }
  for (const item of items.values()) {
    const parent = item.parent || model.parents.get(item.key);
    if (parent) items.get(representatives.get(parent)).children.push(item);
  }
  for (const item of items.values()) item.children.sort(order);
  const edges = new Map();
  for (const edge of model.edges) {
    const source = representatives.get(edge.source_key), target = representatives.get(edge.target_key);
    if (source === target && edge.source_key !== edge.target_key) continue;
    const pair = edge.directional ? [source, target] : [source, target].sort();
    const key = `${pair.join("|")}/${edge.kind}/${edge.directional}`;
    if (!edges.has(key)) edges.set(key, { ...edge, key, source_key: source, target_key: target, relationshipKeys: [] });
    edges.get(key).relationshipKeys.push(edge.key);
  }
  return { items, edges: [...edges.values()], roots: [...new Set(model.roots.map(n => representatives.get(n.key)))].map(key => items.get(key)), representatives };
}

function pack(blocks, maxWidth, gap) {
  if (blocks.length && blocks.every(b => b.width === blocks[0].width && b.height === blocks[0].height)) {
    const columns = Math.max(1, Math.min(blocks.length, Math.floor((maxWidth + gap) / (blocks[0].width + gap))));
    return { positions: blocks.map((block, i) => ({ block, x: (i % columns) * (block.width + gap), y: Math.floor(i / columns) * (block.height + gap) })),
      width: columns * (blocks[0].width + gap) - gap, height: Math.ceil(blocks.length / columns) * (blocks[0].height + gap) - gap };
  }
  const positions = [];
  let width = 0, height = 0;
  for (const block of blocks) {
    const xs = [...new Set([0, ...positions.map(p => p.x + p.block.width + gap)])].sort((a, b) => a - b);
    const ys = [...new Set([0, ...positions.map(p => p.y + p.block.height + gap)])].sort((a, b) => a - b);
    let placed = false;
    for (const y of ys) {
      for (const x of xs) {
        if (x && x + block.width > maxWidth) continue;
        if (positions.some(p => x < p.x + p.block.width + gap && x + block.width + gap > p.x && y < p.y + p.block.height + gap && y + block.height + gap > p.y)) continue;
        positions.push({ block, x, y }); width = Math.max(width, x + block.width); height = Math.max(height, y + block.height);
        placed = true; break;
      }
      if (placed) break;
    }
  }
  return { positions, width, height };
}

function arrange(projection, stage) {
  const gap = stage >= 3 ? 16 : 28, rail = stage >= 3 ? 30 : 44;
  const maxWidth = 1832 / (stage >= 4 ? SHOWCASE_MIN_SCALE : 1);
  const sequence = [], queue = [...projection.roots];
  for (let i = 0; i < queue.length; i++) { sequence.push(queue[i]); queue.push(...queue[i].children); }
  for (const item of sequence.reverse()) {
    item.cardWidth = item.kind === "asset" ? 236 : 276;
    item.memberTop = stage >= 4 ? 52 : 58;
    item.memberRow = stage >= 4 ? 50 : 58;
    item.cardHeight = item.kind === "asset" ? (stage >= 4 ? 86 : 94) : item.memberTop + Math.ceil(item.preview.length / 2) * item.memberRow + (item.hiddenCount ? 28 : 12);
    const childWidth = stage >= 3 && item.children.some(n => n.kind === "category") ? 552 + gap : item.children.some(n => n.kind === "type") ? 900 : maxWidth;
    const packed = pack(item.children, childWidth, gap);
    item.width = Math.max(item.cardWidth, packed.width);
    item.height = item.cardHeight + (packed.height ? rail + packed.height : 0);
    item.packed = packed;
  }
  const connected = projection.roots.filter(n => projection.edges.some(e => e.source_key === n.key || e.target_key === n.key));
  const disconnected = projection.roots.filter(n => !connected.includes(n));
  const main = pack(connected, maxWidth, gap), loose = pack(disconnected, maxWidth - 32, gap);
  const width = Math.max(main.width, loose.width ? loose.width + 32 : 0);
  const footerY = main.height ? main.height + gap : 0;
  const height = main.height + (loose.height ? (main.height ? gap : 0) + 44 + loose.height + 16 : 0);
  const place = (packed, x, y) => {
    const todo = packed.positions.map(p => ({ ...p, x: x + p.x, y: y + p.y }));
    for (let i = 0; i < todo.length; i++) {
      const { block, x: bx, y: by } = todo[i];
      block.x = bx + (block.width - block.cardWidth) / 2; block.y = by;
      for (const p of block.packed.positions) todo.push({ ...p, x: bx + (block.width - block.packed.width) / 2 + p.x, y: by + block.cardHeight + rail + p.y });
    }
  };
  place(main, (width - main.width) / 2, 0);
  place(loose, (width - loose.width) / 2, footerY + 44);
  return { width, height, items: [...projection.items.values()], edges: projection.edges,
    footer: loose.height ? { x: (width - loose.width) / 2 - 16, y: footerY, width: loose.width + 32, height: loose.height + 60 } : null };
}

function routesFor(layout) {
  const items = new Map(layout.items.map(n => [n.key, n]));
  const rectangles = layout.items.map(n => ({ key: n.key, left: n.x - 5, right: n.x + n.cardWidth + 5, top: n.y - 5, bottom: n.y + n.cardHeight + 5 }));
  return layout.edges.map(edge => {
    const a = items.get(edge.source_key), b = items.get(edge.target_key);
    const upper = a.y <= b.y ? a : b, lower = upper === a ? b : a;
    const vertical = lower.y >= upper.y + upper.cardHeight + 20;
    const left = a.x <= b.x ? a : b, right = left === a ? b : a;
    const start = vertical ? [upper.x + upper.cardWidth / 2, upper.y + upper.cardHeight + 6] : [left.x + left.cardWidth + 6, left.y + left.cardHeight / 2];
    const end = vertical ? [lower.x + lower.cardWidth / 2, lower.y - 6] : [right.x - 6, right.y + right.cardHeight / 2];
    const mid = (start[1] + end[1]) / 2;
    const direct = vertical ? [start, [start[0], mid], [end[0], mid], end] : [start, [start[0], end[1]], end];
    const blocked = points => points.slice(1).some((p, i) => rectangles.some(r => {
      const q = points[i];
      return p[0] === q[0] ? p[0] > r.left && p[0] < r.right && Math.max(p[1], q[1]) > r.top && Math.min(p[1], q[1]) < r.bottom : p[1] > r.top && p[1] < r.bottom && Math.max(p[0], q[0]) > r.left && Math.min(p[0], q[0]) < r.right;
    }));
    const points = blocked(direct) ? orthogonalDetour(start, end, rectangles) : direct;
    if (!points) return { ...edge, points: null };
    return { ...edge, points, path: points.map(([x, y], i) => `${i ? "L" : "M"}${x},${y}`).join(" ") };
  });
}

export function showcaseLayout(model) {
  if (model.error) return { complete: false, reason: model.error };
  if (!model.assetCount) return { complete: false, reason: "No Assets recorded for this site yet." };
  for (let stage = 0; stage <= 4; stage++) {
    const projection = presentation(model, stage), layout = arrange(projection, stage);
    const scale = Math.min(1, 1832 / layout.width, 900 / layout.height);
    if (scale < (stage < 4 ? 1 : SHOWCASE_MIN_SCALE)) continue;
    const routes = routesFor(layout);
    if (routes.some(r => !r.points)) return { complete: false, reason: "Showcase incomplete: this site's connections cannot be routed legibly in the fixed composition." };
    const points = routes.flatMap(r => r.points);
    const minX = Math.min(0, ...points.map(p => p[0])), maxX = Math.max(layout.width, ...points.map(p => p[0]));
    const minY = Math.min(0, ...points.map(p => p[1])), maxY = Math.max(layout.height, ...points.map(p => p[1]));
    const finalScale = Math.min(scale, 1832 / (maxX - minX), 900 / (maxY - minY));
    if (finalScale < (stage < 4 ? 1 : SHOWCASE_MIN_SCALE)) continue;
    return { ...layout, routes, complete: true, stage, scale: finalScale,
      x: (SHOWCASE_WIDTH - (maxX - minX) * finalScale) / 2 - minX * finalScale,
      y: 140 + (900 - (maxY - minY) * finalScale) / 2 - minY * finalScale,
      representedAssetIds: layout.items.flatMap(n => n.members.filter(m => m.asset).map(m => m.id)).sort(), assetCount: model.assetCount };
  }
  return { complete: false, reason: "Showcase incomplete: this site's structural branches exceed the readable 16:9 composition, even after compaction. PNG export is unavailable; no partial image will be exported." };
}

export function showcaseFilename(name) {
  const slug = String(name || "site").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[’']/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 100).replace(/-$/g, "") || "site";
  return `${slug}-atlas-showcase.png`;
}
