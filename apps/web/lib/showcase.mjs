import { byName } from "./infrastructure-topology.mjs";
import { topologyGraphEligibility, buildTopologyLayoutModel, calculateTopologyGeometry, routeTopologyEdges, topologyBounds } from "./topology-geometry.mjs";

export const SHOWCASE_WIDTH = 1920;
export const SHOWCASE_HEIGHT = 1080;
export const SHOWCASE_MAX_HEIGHT = 1358;
export const SHOWCASE_CONTENT_TOP = 100;
const POSTER_MARGIN = 32;
const CONTENT_WIDTH = SHOWCASE_WIDTH - POSTER_MARGIN * 2;
export const SHOWCASE_NODE_WIDTH = 124;
export const SHOWCASE_NODE_HEIGHT = 32;
export const SHOWCASE_MEMBER_WIDTH = 112;
export const SHOWCASE_MIN_SCALE = 0.86;
export const SHOWCASE_PREVIEW_COUNT = 4;
const other = (edge, key) => edge.source_key === key ? edge.target_key : edge.source_key;

// Complete current-site authorized input; no focus, traversal or preview budget.
// Parentage and ranks are exclusively Connectivity's shared geometry model.
export function showcaseModel(data, siteId) {
  if (!siteId) return { error: "Select a current site to create its Showcase." };
  if (!Array.isArray(data.structural_edges)) return { error: "Showcase incomplete: structural data is unavailable. Refresh after updating the API." };
  const types = new Map(data.asset_types.map(t => [t.key, t]));
  const categories = new Map(data.categories.map(c => [c.id, c]));
  const nodes = data.assets.filter(a => a.site_id === siteId).map(asset => ({
    key: `asset:${asset.id}`, entity_type: "asset", entity_id: asset.id, id: asset.id, name: asset.name, asset,
    type: types.get(asset.asset_type), position: types.get(asset.asset_type)?.topology_position,
    topology_position: types.get(asset.asset_type)?.topology_position,
    category: categories.get(types.get(asset.asset_type)?.category_id),
  }));
  const graph = topologyGraphEligibility({ nodes, edges: data.structural_edges }, false);
  graph.edges.sort((a, b) => a.key.localeCompare(b.key));
  const layoutModel = buildTopologyLayoutModel(graph);
  const byKey = new Map(layoutModel.nodes.map(n => [n.key, n]));
  const children = new Map(layoutModel.nodes.map(n => [n.key, []]));
  const parentEdges = new Map();
  for (const [child, parent] of layoutModel.parent) {
    children.get(parent).push(byKey.get(child));
    parentEdges.set(child, layoutModel.adjacent.get(child).find(e => other(e, child) === parent && e.platform_parent_key === parent));
  }
  return { ...graph, nodes: layoutModel.nodes, layoutModel, byKey, parents: layoutModel.parent,
    adjacent: layoutModel.adjacent, children, parentEdges,
    roots: layoutModel.nodes.filter(n => !layoutModel.parent.has(n.key)), assetCount: nodes.length };
}

// Category is local presentation after structural ownership is established.
// Identical neighbours prevent shared/multihomed leaves from being consolidated.
function categoryPresentation(model, collapse) {
  const groups = new Map();
  for (const node of model.nodes) {
    const parent = model.parents.get(node.key);
    if (!parent || model.children.get(node.key).length || model.parentEdges.get(node.key)?.platform_parent_key !== parent ||
        (node.position && node.position.key !== "workload")) continue;
    const signature = model.adjacent.get(node.key).map(e => `${other(e, node.key)}:${e.kind}:${e.topology_class}:${e.platform_parent_key || ""}`).sort().join("|");
    const key = `category:${parent}/${node.position?.id || "automatic"}/${node.category?.id || "uncategorized"}/${signature}`;
    if (!groups.has(key)) groups.set(key, { key, parent, kind: "category", name: node.category?.name || "Uncategorized",
      category: node.category, position: node.position, members: [] });
    groups.get(key).members.push(node);
  }
  const membership = new Map(), hidden = new Set();
  for (const [key, group] of groups) {
    if (group.members.length < 2) { groups.delete(key); continue; }
    group.members.sort(byName);
    // A roll-up is safe only when all member records can use one truthful
    // shared connector. Mixed semantics and multihoming stay fully explicit.
    const families = new Set(group.members.flatMap(n => model.adjacent.get(n.key).map(e =>
      JSON.stringify([e.label, e.relationship_type, e.directional, e.source_key === group.parent]))));
    const preview = collapse && families.size === 1 && group.members.every(n => model.adjacent.get(n.key).every(e =>
      e.platform_parent_key === group.parent && other(e, n.key) === group.parent));
    group.preview = preview ? group.members.slice(0, SHOWCASE_PREVIEW_COUNT) : group.members;
    group.hiddenCount = group.members.length - group.preview.length;
    group.memberColumns = group.members.length >= 5 ? 2 : 1;
    group.memberWidth = SHOWCASE_MEMBER_WIDTH;
    group.memberTop = 32; group.memberRow = 32; group.memberGap = 4;
    for (const node of group.preview) membership.set(node.key, group);
    for (const node of group.members.slice(group.preview.length)) hidden.add(node.key);
  }
  const nodes = model.nodes.filter(n => !hidden.has(n.key)).map(n => ({ ...n,
    ...(membership.has(n.key) ? { presentation_group_key: membership.get(n.key).key,
      geometry_width: SHOWCASE_MEMBER_WIDTH, geometry_height: 22 } : {}) }));
  const edges = model.edges.filter(e => !hidden.has(e.source_key) && !hidden.has(e.target_key));
  const boxes = placed => [...groups.values()].flatMap(group => {
    const members = placed.filter(n => membership.get(n.key) === group);
    if (members.length < 2) return [];
    const left = Math.min(...members.map(n => n.x - SHOWCASE_MEMBER_WIDTH / 2)) - 12;
    const top = Math.min(...members.map(n => n.y - 11)) - group.memberTop;
    const right = Math.max(...members.map(n => n.x + SHOWCASE_MEMBER_WIDTH / 2)) + 12;
    const bottom = Math.max(...members.map(n => n.y + 11)) + (group.hiddenCount ? 26 : 8);
    return [{ ...group, left, top, width: right - left, height: bottom - top,
      parent_key: group.parent, node_keys: members.map(n => n.key), disclosure_keys: [],
      labelTop: 8, labelWidth: right - left - 24 }];
  });
  // Reuse complete-site ownership/ranks even in a last-resort preview.
  const keys = new Set(nodes.map(n => n.key));
  const layoutModel = { ...model.layoutModel, nodes, edges,
    parent: new Map([...model.parents].filter(([key]) => keys.has(key))),
    adjacent: new Map(nodes.map(n => [n.key, edges.filter(e => e.source_key === n.key || e.target_key === n.key)])) };
  return { nodes, edges, layoutModel, groups, membership, boxes };
}

export function showcaseLayout(model) {
  if (model.error) return { complete: false, reason: model.error };
  if (!model.assetCount) return { complete: false, reason: "No Assets recorded for this site yet." };
  const attempts = [];
  const finish = (candidate, posterHeight, scale) => {
    const { layout, bounds, diagnostic, stage } = candidate;
    const contentHeight = posterHeight - SHOWCASE_CONTENT_TOP - POSTER_MARGIN;
    return { ...layout, complete: true, stage, scale, sceneWidth: SHOWCASE_WIDTH, sceneHeight: posterHeight,
      x: (SHOWCASE_WIDTH - bounds.width * scale) / 2 - bounds.minX * scale,
      y: SHOWCASE_CONTENT_TOP + (contentHeight - bounds.height * scale) / 2 - bounds.minY * scale,
      representedAssetIds: layout.items.flatMap(n => n.members.map(m => m.id)).sort(), assetCount: model.assetCount,
      diagnostics: { ...diagnostic, chosenPosterHeight: posterHeight, requiredScale: scale, failureReason: null, attempts } };
  };
  // Always attempt all Assets first. A 40–50 Asset site never uses roll-ups.
  // Taller complete posters precede the last-resort enormous-site preview.
  for (const stage of model.assetCount > 100 ? [0, 1] : [0]) {
    const projection = categoryPresentation(model, stage > 0);
    const metrics = { nodeWidth: SHOWCASE_NODE_WIDTH, nodeHeight: SHOWCASE_NODE_HEIGHT,
      columnGap: 4, rowGap: cluster => cluster[0].presentation_group_key ? 10 : 32, railGap: 16, footprintPadding: 4, groupTop: 32, groupBottom: stage ? 26 : 8,
      groups: projection.boxes, columns: cluster => projection.membership.get(cluster[0].key)?.memberColumns || (cluster.every(n => !model.children.get(n.key).length) ? 1 : 4) };
    metrics.separatePositions = false;
    const geometry = calculateTopologyGeometry(projection, metrics, projection.layoutModel);
    const boxes = projection.boxes(geometry), grouped = new Set(boxes.flatMap(g => g.node_keys));
    const items = [
      ...geometry.filter(n => !grouped.has(n.key)).map(n => ({ ...n, kind: "asset", members: [model.byKey.get(n.key)],
        x: n.x - SHOWCASE_NODE_WIDTH / 2, y: n.y - SHOWCASE_NODE_HEIGHT / 2,
        cardWidth: SHOWCASE_NODE_WIDTH, cardHeight: SHOWCASE_NODE_HEIGHT, layoutParentKey: n.layout_parent_key })),
      ...boxes.map(g => ({ ...g, x: g.left, y: g.top, cardWidth: g.width, cardHeight: g.height, layoutParentKey: g.parent })),
    ].sort((a, b) => a.key.localeCompare(b.key));
    const diagnostic = { stage, assetCount: model.assetCount, structuralNodeCount: items.filter(n => n.kind === "asset").length,
      collapsedGroupCount: boxes.filter(g => g.hiddenCount).length, workloadCategoryCount: boxes.length,
      rootCount: model.roots.length, readabilityFloor: SHOWCASE_MIN_SCALE, chosenPosterHeight: SHOWCASE_HEIGHT, failureReason: null };
    attempts.push(diagnostic);
    const initialBounds = topologyBounds(geometry, {}, boxes, metrics);
    Object.assign(diagnostic, { sceneWidth: initialBounds.width, sceneHeight: initialBounds.height,
      requiredScale: Math.min(1, CONTENT_WIDTH / initialBounds.width,
        (SHOWCASE_HEIGHT - SHOWCASE_CONTENT_TOP - POSTER_MARGIN) / initialBounds.height) });
    if (CONTENT_WIDTH / initialBounds.width < SHOWCASE_MIN_SCALE) { diagnostic.failureReason = "width"; continue; }
    if ((SHOWCASE_MAX_HEIGHT - SHOWCASE_CONTENT_TOP - POSTER_MARGIN) / initialBounds.height < SHOWCASE_MIN_SCALE) {
      diagnostic.failureReason = "height"; continue;
    }
    let routed;
    try { routed = routeTopologyEdges(geometry, projection.edges, boxes, metrics); }
    catch (error) { diagnostic.failureReason = "routing"; diagnostic.routingError = error.message; continue; }
    const routes = projection.edges.filter(e => routed[e.key]?.render !== false).map(edge => {
      const route = routed[edge.key], group = boxes.find(g => g.key === route.group_key);
      const relationshipKeys = group ? model.edges.filter(e =>
        e.platform_parent_key === group.parent && group.members.some(n => n.key === other(e, group.parent))).map(e => e.key) : [edge.key];
      return { ...edge, ...route, relationshipKeys,
        path: route.points.map(([x, y], i) => `${i ? "L" : "M"}${x},${y}`).join(" ") };
    });
    const bounds = topologyBounds(geometry, routed, boxes, metrics);
    const scale = Math.min(1, CONTENT_WIDTH / bounds.width, (SHOWCASE_HEIGHT - SHOWCASE_CONTENT_TOP - POSTER_MARGIN) / bounds.height);
    Object.assign(diagnostic, { sceneWidth: bounds.width, sceneHeight: bounds.height, requiredScale: scale });
    const candidate = { layout: { items, routes, edges: model.edges, geometry, positionLabels: [], footer: null }, bounds, diagnostic, stage };
    if (scale >= SHOWCASE_MIN_SCALE) return finish(candidate, SHOWCASE_HEIGHT, scale);
    diagnostic.failureReason = CONTENT_WIDTH / bounds.width < SHOWCASE_MIN_SCALE ? "width" : "height";
    const posterHeight = Math.max(SHOWCASE_HEIGHT, Math.ceil(bounds.height * SHOWCASE_MIN_SCALE + SHOWCASE_CONTENT_TOP + POSTER_MARGIN));
    if (CONTENT_WIDTH / bounds.width >= SHOWCASE_MIN_SCALE && posterHeight <= SHOWCASE_MAX_HEIGHT) {
      // Complete representation takes priority over previews at any allowed height.
      return finish(candidate, posterHeight, Math.min(1, CONTENT_WIDTH / bounds.width,
        (posterHeight - SHOWCASE_CONTENT_TOP - POSTER_MARGIN) / bounds.height));
    }
  }
  const diagnostic = attempts.at(-1);
  return { complete: false, reason: "Showcase incomplete: this site's structure exceeds the readable poster size, even after compaction. No partial image will be exported.",
    diagnostics: { ...diagnostic, chosenPosterHeight: SHOWCASE_MAX_HEIGHT, attempts } };
}

export function showcaseFilename(name) {
  const slug = String(name || "site").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[’']/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 100).replace(/-$/g, "") || "site";
  return `${slug}-atlas-showcase.png`;
}
