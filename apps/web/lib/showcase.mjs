import { byName, orthogonalDetour } from "./infrastructure-topology.mjs";

export const SHOWCASE_WIDTH = 1920;
export const SHOWCASE_HEIGHT = 1080;
export const SHOWCASE_MAX_HEIGHT = 1358;
export const SHOWCASE_CONTENT_TOP = 100;
const POSTER_MARGIN = 32;
const CONTENT_WIDTH = SHOWCASE_WIDTH - POSTER_MARGIN * 2;
export const SHOWCASE_NODE_WIDTH = 204;
export const SHOWCASE_NODE_HEIGHT = 44;
export const SHOWCASE_MEMBER_WIDTH = 150;
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
  // Match Connectivity's show_networks=False branch: only Asset nodes and
  // accepted Asset-to-Asset structural edges; never interface membership.
  const edges = data.structural_edges.filter(e => e.kind !== "membership" && byKey.has(e.source_key) && byKey.has(e.target_key)).sort((a, b) => a.key.localeCompare(b.key));
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
      if (group.kind === "category" && group.members.length < 2) continue;
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
    if (parent) {
      item.layoutParentKey = representatives.get(parent);
      items.get(item.layoutParentKey).children.push(item);
    }
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

// Horizontal contour packing only: Y is assigned once for the entire poster.
// A branch may use another branch's empty columns, never another Position's Y.
function pack(blocks, gap) {
  const positions = [], occupied = [];
  let width = 0;
  const groups = new Map();
  for (const block of blocks) {
    const key = block.stackKey || block.key;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(block);
  }
  for (const group of groups.values()) {
    const block = { width: Math.max(...group.map(n => n.width)), footprint: group.flatMap(n => n.footprint) };
    let x = 0;
    for (const b of block.footprint) for (const a of occupied) {
      if (b.y < a.y + a.height + gap && b.y + b.height + gap > a.y) x = Math.max(x, a.x + a.width + gap - b.x);
    }
    positions.push(...group.map(block => ({ block, x })));
    width = Math.max(width, x + block.width);
    occupied.push(...block.footprint.map(b => ({ ...b, x: b.x + x })));
  }
  return { positions, width, footprint: occupied };
}

function arrange(projection, stage) {
  const gap = stage >= 3 ? 16 : 24, rail = stage >= 3 ? 24 : 32;
  const sequence = [], queue = [...projection.roots];
  for (let i = 0; i < queue.length; i++) { sequence.push(queue[i]); queue.push(...queue[i].children); }
  const bands = new Map();
  const maxWidth = CONTENT_WIDTH / (stage >= 4 ? SHOWCASE_MIN_SCALE : 1);
  const columns = Math.floor((maxWidth + gap) / (SHOWCASE_NODE_WIDTH + gap));
  // Overflow rows stay inside their Position band; descendants inherit the row
  // so wide sibling sets can share columns without interleaving their branches.
  for (const parent of [null, ...sequence]) {
    const siblings = parent ? parent.children : projection.roots, groups = new Map();
    for (const item of siblings) {
      const key = item.position?.id || "automatic";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(item);
    }
    for (const [key, peers] of groups) for (const [i, item] of peers.entries()) {
      const stackable = !item.children.length && (item.kind !== "asset" || item.position?.key === "workload" || !item.position);
      item.wrapRow = parent?.wrapRow || 0;
      if (stackable && parent) item.stackKey = `${parent.key}/${key}/leaves`;
      else if (peers.length > columns) {
        item.wrapRow = item.wrapRow * Math.ceil(peers.length / columns) + Math.floor(i / columns);
        item.stackKey = `${parent?.key || "roots"}/${key}/column:${i % columns}`;
      }
    }
  }
  for (const item of sequence) {
    // Category size uses the full membership even when a later stage previews
    // only four members. Renderer fills the stable name/ID order row-wise.
    item.memberColumns = item.kind === "category" ? (item.members.length >= 5 ? 2 : 1) : Math.min(4, item.preview?.length || 1);
    item.memberWidth = SHOWCASE_MEMBER_WIDTH;
    item.cardWidth = item.kind === "asset" || item.memberColumns === 1 ? SHOWCASE_NODE_WIDTH : item.memberColumns * (item.memberWidth + 8) + 16;
    item.memberTop = 32;
    item.memberRow = stage >= 3 ? 28 : 32;
    item.cardHeight = item.kind === "asset" ? SHOWCASE_NODE_HEIGHT : item.memberTop + Math.ceil(item.preview.length / item.memberColumns) * item.memberRow + (item.kind === "type" || item.hiddenCount ? 26 : 8);
    const key = item.position?.id || "automatic";
    if (!bands.has(key)) bands.set(key, { key, position: item.position, items: [] });
    bands.get(key).items.push(item);
    // Reuse the cycle-safe presentation forest's explicit intra-position chain.
    const parent = projection.items.get(item.layoutParentKey);
    item.positionDepth = parent && (parent.position?.id || "automatic") === key ? parent.positionDepth + 1 : 0;
  }
  const orderedBands = [...bands.values()].sort((a, b) => (a.position?.sort_order ?? Infinity) - (b.position?.sort_order ?? Infinity) || a.key.localeCompare(b.key));
  let y = 0;
  for (const band of orderedBands) {
    band.y = y;
    // Reserve a small caption, not a Position container. Only occupied bands
    // exist, so unused managed records and gaps in sort_order cost no height.
    y += band.position ? 18 : 0;
    const depths = [...new Set(band.items.map(n => n.positionDepth))].sort((a, b) => a - b);
    for (const depth of depths) {
      const depthItems = band.items.filter(n => n.positionDepth === depth);
      for (const row of [...new Set(depthItems.map(n => n.wrapRow))].sort((a, b) => a - b)) {
        const peers = depthItems.filter(n => n.wrapRow === row), stacks = new Map();
        for (const item of peers) {
          // Workload/category leaves under one parent grow down inside this band.
          // Structural peers stay aligned, regardless of their branch height.
          const stackable = !item.children.length && (item.kind !== "asset" || item.position?.key === "workload" || !item.position);
          const key = stackable ? item.layoutParentKey || item.key : item.key;
          if (!stacks.has(key)) stacks.set(key, []);
          stacks.get(key).push(item);
        }
        let height = 0;
        for (const stack of stacks.values()) {
          let localY = 0;
          for (const item of stack.sort(order)) {
            item.y = y + localY;
            localY += item.cardHeight + rail;
          }
          height = Math.max(height, localY - rail);
        }
        y += height + rail;
      }
    }
    band.height = y - rail - band.y;
  }
  const height = y - rail;
  for (const item of [...sequence].reverse()) {
    const packed = pack(item.children, gap);
    item.width = Math.max(item.cardWidth, packed.width);
    item.packed = packed;
    item.footprint = [{ x: (item.width - item.cardWidth) / 2, y: item.y, width: item.cardWidth, height: item.cardHeight },
      ...packed.footprint.map(r => ({ ...r, x: r.x + (item.width - packed.width) / 2 }))];
  }
  const connected = projection.roots.filter(n => projection.edges.some(e => e.source_key === n.key || e.target_key === n.key));
  const disconnected = projection.roots.filter(n => !connected.includes(n));
  const main = pack(connected, gap), loose = pack(disconnected, gap);
  const width = main.width + (loose.width ? (main.width ? gap : 0) + loose.width + 24 : 0);
  const place = (packed, x) => {
    const todo = packed.positions.map(p => ({ ...p, x: x + p.x }));
    for (let i = 0; i < todo.length; i++) {
      const { block, x: bx } = todo[i];
      block.x = bx + (block.width - block.cardWidth) / 2;
      for (const p of block.packed.positions) todo.push({ ...p, x: bx + (block.width - block.packed.width) / 2 + p.x });
    }
  };
  place(main, 0);
  place(loose, main.width + (main.width ? gap : 0) + 12);
  const labels = [];
  for (const band of orderedBands) if (band.position) {
    const first = [...band.items].sort((a, b) => a.x - b.x)[0];
    labels.push({ key: `position:${band.key}`, name: band.position.name, positionId: band.key,
      x: first.x, y: band.y, width: first.cardWidth, height: 14 });
  }
  // Keep unconnected Assets in their assigned bands, in a separate side region.
  const looseTop = loose.width ? Math.min(...disconnected.map(n => n.y)) - 48 : 0;
  const looseBottom = loose.width ? Math.max(...disconnected.map(n => n.y + n.cardHeight)) + 10 : 0;
  return { width, height, items: [...projection.items.values()], edges: projection.edges, positionLabels: labels,
    positionBands: orderedBands.map(({ key, position, y, height }) => ({ key, position, y, height })),
    footer: loose.width ? { x: main.width + (main.width ? gap : 0), y: looseTop, width: loose.width + 24, height: looseBottom - looseTop } : null };
}

function routesFor(layout) {
  const items = new Map(layout.items.map(n => [n.key, n]));
  const rectangles = layout.items.map(n => ({ key: n.key, left: n.x - 4, right: n.x + n.cardWidth + 4, top: n.y - 4, bottom: n.y + n.cardHeight + 4 }));
  rectangles.push(...layout.positionLabels.map(label => ({ key: label.key, left: label.x, right: label.x + label.width, top: label.y - 2, bottom: label.y + label.height })));
  return layout.edges.map(edge => {
    const a = items.get(edge.source_key), b = items.get(edge.target_key);
    const upper = a.y <= b.y ? a : b, lower = upper === a ? b : a;
    const vertical = lower.y >= upper.y + upper.cardHeight + 12;
    const left = a.x <= b.x ? a : b, right = left === a ? b : a;
    const start = vertical ? [upper.x + upper.cardWidth / 2, upper.y + upper.cardHeight + 6] : [left.x + left.cardWidth + 6, left.y + left.cardHeight / 2];
    // A local heading captions its node. End above that caption rather than
    // detouring around it and doubling back underneath the text.
    const caption = layout.positionLabels.find(label => label.x === lower.x && label.y + 18 === lower.y);
    const end = vertical ? [lower.x + lower.cardWidth / 2, (caption?.y ?? lower.y) - 4] : [right.x - 6, right.y + right.cardHeight / 2];
    // Distribution rail just above the destination row: long edges descend
    // toward their band before making the horizontal run and short final drop.
    const band = layout.positionBands.find(band => band.key === (lower.position?.id || "automatic"));
    const mid = Math.max(start[1], lower.y - (band.position && lower.y === band.y + 18 ? 30 : 12));
    const direct = vertical ? [start, [start[0], mid], [end[0], mid], end] : [start, [start[0], end[1]], end];
    const blocked = points => points.slice(1).some((p, i) => rectangles.some(r => {
      const q = points[i];
      return p[0] === q[0] ? p[0] > r.left && p[0] < r.right && Math.max(p[1], q[1]) > r.top && Math.min(p[1], q[1]) < r.bottom : p[1] > r.top && p[1] < r.bottom && Math.max(p[0], q[0]) > r.left && Math.min(p[0], q[0]) < r.right;
    }));
    // Stacked local groups share a side trunk. Going down their centre would
    // hit the preceding card and force long detours through unrelated branches.
    const stacked = vertical && lower.stackKey && layout.items.some(n => n.key !== lower.key && n.stackKey === lower.stackKey);
    const trunks = stacked ? [lower.x - 8, lower.x + lower.cardWidth + 8].map(x =>
      [start, [x, start[1]], [x, mid], [end[0], mid], end]) : [];
    const points = [...trunks, direct].find(points => !blocked(points)) || orthogonalDetour(start, end, rectangles);
    if (!points) return { ...edge, points: null };
    return { ...edge, points, path: points.map(([x, y], i) => `${i ? "L" : "M"}${x},${y}`).join(" ") };
  });
}

function contentBounds(layout, routes) {
  let minX = 0, minY = 0, maxX = layout.width, maxY = layout.height;
  if (layout.footer) {
    minX = Math.min(minX, layout.footer.x); minY = Math.min(minY, layout.footer.y);
    maxX = Math.max(maxX, layout.footer.x + layout.footer.width); maxY = Math.max(maxY, layout.footer.y + layout.footer.height);
  }
  for (const route of routes) for (const [x, y] of route.points || []) {
    minX = Math.min(minX, x); minY = Math.min(minY, y);
    maxX = Math.max(maxX, x); maxY = Math.max(maxY, y);
  }
  return { minX, minY, width: maxX - minX, height: maxY - minY };
}

export function showcaseLayout(model) {
  if (model.error) return { complete: false, reason: model.error };
  if (!model.assetCount) return { complete: false, reason: "No Assets recorded for this site yet." };
  const attempts = [], candidates = [];
  const finish = (candidate, posterHeight, scale) => {
    const { layout, routes, bounds, diagnostic, stage } = candidate;
    const contentHeight = posterHeight - SHOWCASE_CONTENT_TOP - POSTER_MARGIN;
    return { ...layout, routes, complete: true, stage, scale, sceneWidth: SHOWCASE_WIDTH, sceneHeight: posterHeight,
      x: (SHOWCASE_WIDTH - bounds.width * scale) / 2 - bounds.minX * scale,
      y: SHOWCASE_CONTENT_TOP + (contentHeight - bounds.height * scale) / 2 - bounds.minY * scale,
      representedAssetIds: layout.items.flatMap(n => n.members.filter(m => m.asset).map(m => m.id)).sort(), assetCount: model.assetCount,
      diagnostics: { ...diagnostic, chosenPosterHeight: posterHeight, requiredScale: scale, failureReason: null, attempts } };
  };
  // Prefer 16:9 across all normal compaction stages before adding poster height.
  for (let stage = 0; stage <= 4; stage++) {
    const projection = presentation(model, stage), layout = arrange(projection, stage);
    const diagnostic = { stage, assetCount: model.assetCount,
      structuralNodeCount: layout.items.filter(n => n.kind === "asset" && n.asset).length,
      collapsedGroupCount: layout.items.filter(n => n.kind !== "asset").length,
      workloadCategoryCount: layout.items.filter(n => n.kind === "category").length,
      rootCount: model.roots.length, sceneWidth: layout.width, sceneHeight: layout.height,
      chosenPosterHeight: SHOWCASE_HEIGHT, requiredScale: Math.min(1, CONTENT_WIDTH / layout.width, (SHOWCASE_HEIGHT - SHOWCASE_CONTENT_TOP - POSTER_MARGIN) / layout.height),
      readabilityFloor: SHOWCASE_MIN_SCALE, failureReason: null };
    attempts.push(diagnostic);
    // Reject only impossible geometry before routing; use measured route extents
    // for the final fit, including any external obstacle detours.
    if (CONTENT_WIDTH / layout.width < SHOWCASE_MIN_SCALE) { diagnostic.failureReason = "width"; continue; }
    if ((SHOWCASE_MAX_HEIGHT - SHOWCASE_CONTENT_TOP - POSTER_MARGIN) / layout.height < SHOWCASE_MIN_SCALE) { diagnostic.failureReason = "height"; continue; }
    const routes = routesFor(layout);
    if (routes.some(r => !r.points)) { diagnostic.failureReason = "routing"; continue; }
    const bounds = contentBounds(layout, routes);
    const widthScale = Math.min(1, CONTENT_WIDTH / bounds.width);
    const scale = Math.min(widthScale, (SHOWCASE_HEIGHT - SHOWCASE_CONTENT_TOP - POSTER_MARGIN) / bounds.height);
    Object.assign(diagnostic, { sceneWidth: bounds.width, sceneHeight: bounds.height, requiredScale: scale });
    if (widthScale < SHOWCASE_MIN_SCALE) { diagnostic.failureReason = "width"; continue; }
    const candidate = { layout, routes, bounds, diagnostic, stage };
    if (scale >= (stage < 4 ? 1 : SHOWCASE_MIN_SCALE)) return finish(candidate, SHOWCASE_HEIGHT, scale);
    diagnostic.failureReason = "height";
    candidates.push(candidate);
  }
  // The minimum integer height that respects the unchanged readability floor.
  // Height cannot rescue a scene whose width already requires illegible scale.
  const adaptive = candidates.map(candidate => ({ ...candidate,
    posterHeight: Math.max(SHOWCASE_HEIGHT, Math.ceil(candidate.bounds.height * SHOWCASE_MIN_SCALE + SHOWCASE_CONTENT_TOP + POSTER_MARGIN)) }))
    .filter(c => c.posterHeight <= SHOWCASE_MAX_HEIGHT)
    .sort((a, b) => a.posterHeight - b.posterHeight || a.stage - b.stage)[0];
  if (adaptive) {
    const scale = Math.min(1, CONTENT_WIDTH / adaptive.bounds.width, (adaptive.posterHeight - SHOWCASE_CONTENT_TOP - POSTER_MARGIN) / adaptive.bounds.height);
    return finish(adaptive, adaptive.posterHeight, scale);
  }
  const diagnostic = attempts.at(-1);
  return { complete: false,
    reason: "Showcase incomplete: this site's structure exceeds the readable poster size, even after compaction. No partial image will be exported.",
    diagnostics: { ...diagnostic, chosenPosterHeight: SHOWCASE_MAX_HEIGHT,
      requiredScale: Math.min(1, CONTENT_WIDTH / diagnostic.sceneWidth, (SHOWCASE_MAX_HEIGHT - SHOWCASE_CONTENT_TOP - POSTER_MARGIN) / diagnostic.sceneHeight), attempts } };
}

export function showcaseFilename(name) {
  const slug = String(name || "site").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[’']/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 100).replace(/-$/g, "") || "site";
  return `${slug}-atlas-showcase.png`;
}
