import test from "node:test";
import assert from "node:assert/strict";
import { showcaseModel, showcaseLayout, showcaseFilename, SHOWCASE_MIN_SCALE, SHOWCASE_CONTENT_TOP, SHOWCASE_MAX_HEIGHT, SHOWCASE_MAX_WIDTH, SHOWCASE_NODE_WIDTH, SHOWCASE_NODE_HEIGHT } from "../lib/showcase.mjs";
import { showcaseFixture, showcaseRealShapeFixture, showcaseReferenceFixture, showcasePosterFixture, showcaseWideFixture, showcaseUltrawideFixture, id } from "./fixtures/showcase.mjs";
import { topologyPresentation, connectivityLayout, connectivityRoutes, connectivityPreview } from "../lib/infrastructure-topology.mjs";
import { buildTopologyLayoutModel, calculateTopologyGeometry, topologyBounds } from "../lib/topology-geometry.mjs";

function intersects(p, q, box) {
  return p[0] === q[0]
    ? p[0] > box.x && p[0] < box.x + box.cardWidth && Math.max(p[1], q[1]) > box.y && Math.min(p[1], q[1]) < box.y + box.cardHeight
    : p[1] > box.y && p[1] < box.y + box.cardHeight && Math.max(p[0], q[0]) > box.x && Math.min(p[0], q[0]) < box.x + box.cardWidth;
}
function checkPoster(data) {
  const before = structuredClone(data), model = showcaseModel(data, id(2)), layout = showcaseLayout(model);
  assert.ok(layout.complete, JSON.stringify(layout.diagnostics));
  assert.deepEqual(data, before);
  assert.deepEqual(layout.representedAssetIds, data.assets.map(a => a.id).sort());
  assert.equal(new Set(layout.representedAssetIds).size, data.assets.length);
  assert.ok(layout.sceneWidth >= 1920 && layout.sceneWidth <= SHOWCASE_MAX_WIDTH);
  assert.ok(layout.sceneHeight >= 1080 && layout.sceneHeight <= SHOWCASE_MAX_HEIGHT);
  assert.ok(layout.scale >= SHOWCASE_MIN_SCALE);
  const measured = topologyBounds(layout.geometry, Object.fromEntries(layout.routes.map(r => [r.key, r])),
    layout.items.filter(n => n.kind === "category"), { nodeWidth: SHOWCASE_NODE_WIDTH, nodeHeight: SHOWCASE_NODE_HEIGHT });
  assert.equal(layout.diagnostics.naturalContentWidth, measured.width);
  assert.equal(layout.diagnostics.naturalContentHeight, measured.height);
  assert.equal(layout.diagnostics.boundsIncludeRoutes, true);
  for (const [i, a] of layout.items.entries()) {
    assert.ok(layout.x + a.x * layout.scale >= 0);
    assert.ok(layout.y + a.y * layout.scale >= SHOWCASE_CONTENT_TOP);
    assert.ok(layout.x + (a.x + a.cardWidth) * layout.scale <= layout.sceneWidth);
    assert.ok(layout.y + (a.y + a.cardHeight) * layout.scale <= layout.sceneHeight);
    for (const b of layout.items.slice(i + 1)) assert.ok(a.x + a.cardWidth <= b.x || b.x + b.cardWidth <= a.x || a.y + a.cardHeight <= b.y || b.y + b.cardHeight <= a.y, `${a.name} overlaps ${b.name}`);
    if (a.kind === "asset") {
      assert.equal(a.cardWidth, SHOWCASE_NODE_WIDTH); assert.equal(a.cardHeight, SHOWCASE_NODE_HEIGHT);
    }
  }
  for (const route of layout.routes) for (let i = 1; i < route.points.length; i++) {
    const p = route.points[i - 1], q = route.points[i];
    assert.ok(p[0] === q[0] || p[1] === q[1]);
    for (const box of layout.items) assert.equal(intersects(p, q, box), false, `route ${route.key} crosses ${box.name}`);
    for (const [x, y] of [p, q]) {
      assert.ok(layout.x + x * layout.scale >= 0 && layout.x + x * layout.scale <= layout.sceneWidth);
      assert.ok(layout.y + y * layout.scale >= SHOWCASE_CONTENT_TOP && layout.y + y * layout.scale <= layout.sceneHeight);
    }
  }
  assert.deepEqual(layout.routes.flatMap(r => r.relationshipKeys).sort(), model.edges.map(e => e.key).sort());
  const shuffled = { ...data, assets: [...data.assets].reverse(), structural_edges: [...data.structural_edges].reverse(), asset_types: [...data.asset_types].reverse(), categories: [...data.categories].reverse() };
  assert.deepEqual(showcaseLayout(showcaseModel(shuffled, id(2))), layout);
  return { model, layout };
}

for (const size of ["small", "medium", "large"]) test(`${size}: complete, deterministic, bounded orthogonal geometry`, () => {
  const { layout, model } = checkPoster(showcaseFixture(size));
  for (const group of layout.items.filter(n => n.kind === "category")) {
    for (const member of group.members) assert.equal(model.parents.get(member.key), group.parent);
    assert.equal(group.memberColumns, group.members.length >= 5 ? 2 : 1);
  }
  assert.equal(layout.stage, size === "large" ? 1 : 0);
  assert.ok(layout.items.filter(n => n.kind === "category").every(n => size === "large" || n.hiddenCount === 0));
});

for (const [name, fixture, count] of [["reference", showcaseReferenceFixture, 44], ["real shape", showcaseRealShapeFixture, 50]]) test(`${name}: complete 16:9, all workloads and nested hosts visible`, () => {
  const data = fixture(), { model, layout } = checkPoster(data);
  assert.equal(data.assets.length, count); assert.equal(layout.sceneWidth, 1920); assert.equal(layout.sceneHeight, 1080); assert.equal(layout.stage, 0);
  assert.equal(layout.diagnostics.collapsedGroupCount, 0);
  assert.ok(layout.items.every(n => !n.hiddenCount));
  assert.deepEqual(layout.items.flatMap(n => n.kind === "asset" ? n.members : n.preview).map(n => n.id).sort(), data.assets.map(a => a.id).sort());
  const key = name => model.nodes.find(n => n.name === name).key;
  for (const [parent, child] of [["Gateway", "Aggregation Switch"], ["Aggregation Switch", "Distribution Switch"], ["Distribution Switch", "Access Switch A"], ["Distribution Switch", "Platform Host A"], ["Distribution Switch", "Platform Host B"], ["Distribution Switch", "Platform Host C"], ["Platform Host A", "Container Host A"], ["Platform Host A", "Container Host B"], ["Container Host A", "Photo Library A"], ["Container Host B", "Auth Service B"], ["Aggregation Switch", "Physical Host A"], ["Physical Host A", "Isolated Platform A"]]) {
    assert.equal(model.parents.get(key(child)), key(parent));
    assert.equal(layout.geometry.find(n => n.key === key(child)).layout_parent_key, key(parent));
  }
  assert.equal(layout.geometry.filter(n => n.key === key("Platform Host A")).length, 1);
  assert.equal(model.children.get(key("Platform Host A")).filter(n => n.name.startsWith("Workload")).length, count === 44 ? 10 : 16);
  const connectivity = connectivityLayout({ ...model, focus_key: key("Gateway") });
  for (const node of layout.geometry) {
    const reference = connectivity.find(n => n.key === node.key);
    assert.equal(node.rank, reference.rank);
    assert.equal(node.positionDepth, reference.positionDepth);
    assert.equal(node.layout_parent_key, reference.layout_parent_key);
  }
});

test("one geometry implementation: default Connectivity is the pure engine plus focus origin", () => {
  const model = showcaseModel(showcaseReferenceFixture(), id(2));
  const graph = { nodes: model.nodes, edges: model.edges, focus_key: model.nodes[0].key };
  assert.deepEqual(connectivityLayout(graph), calculateTopologyGeometry(graph));
  const ownership = buildTopologyLayoutModel(graph);
  assert.deepEqual(ownership.parent, model.parents);
  assert.equal(calculateTopologyGeometry({ ...graph, focus_key: undefined }).length, 44);
});

test("same-position hierarchy is shared, anchored to actual links and safe with cycles/parallel records", () => {
  const data = showcaseReferenceFixture();
  const [aggregation, distribution, access] = ["Aggregation Switch", "Distribution Switch", "Access Switch A"].map(name => data.assets.find(n => n.name === name));
  const model = showcaseModel(data, id(2)), graph = { ...model, focus_key: `asset:${aggregation.id}` };
  const placed = connectivityLayout(graph), lookup = id => placed.find(n => n.key === `asset:${id}`);
  assert.equal(lookup(access.id).rank, lookup(distribution.id).rank);
  assert.equal(lookup(access.id).positionDepth, 1); assert.ok(lookup(access.id).y > lookup(distribution.id).y);
  data.structural_edges.push({ ...data.structural_edges.find(e => e.source_key === `asset:${access.id}`), key: "parallel" });
  const a = data.assets.find(n => n.name === "Access Switch B");
  data.structural_edges.push({ key: "cycle", source_key: `asset:${access.id}`, target_key: `asset:${a.id}`, topology_class: "physical_network", kind: "relationship", directional: false });
  checkPoster(data);
});

test("Networks-off eligibility is typed; network device Assets remain and no network geometry is reserved", () => {
  const data = showcaseReferenceFixture(), before = structuredClone(data);
  const layout = showcaseLayout(showcaseModel(data, id(2)));
  assert.deepEqual(layout, showcaseLayout(showcaseModel({ ...data, networks: [], asset_interfaces: [], structural_edges: data.structural_edges.filter(e => e.kind !== "membership") }, id(2))));
  assert.deepEqual(data, before);
  assert.ok(layout.geometry.every(n => n.entity_type === "asset"));
  assert.ok(layout.routes.every(e => e.kind !== "membership"));
  data.assets[0].name = "Default";
  assert.ok(showcaseModel(data, id(2)).nodes.some(n => n.name === "Default"));
  for (const name of ["Gateway", "Aggregation Switch", "Distribution Switch", "Access Switch A"]) assert.ok(layout.items.some(n => n.name === name));
});

test("whole authorized site ignores category defaults, with defence against foreign-site endpoints", () => {
  const data = showcaseFixture();
  data.assets.push({ ...data.assets[0], id: "hidden", site_id: id(999), name: "Secret" });
  data.structural_edges.push({ key: "hidden-edge", source_key: "asset:hidden", target_key: `asset:${data.assets[0].id}`, kind: "relationship" });
  const model = showcaseModel(data, id(2)), layout = showcaseLayout(model);
  assert.ok(layout.complete); assert.ok(!JSON.stringify(layout).includes("Secret"));
  assert.equal(layout.assetCount, data.assets.length - 1);
  assert.equal(model.nodes.filter(n => n.type.key === "ap").length, 5);
});

test("canonical cycles, secondary hosting and parallel connections retain every record", () => {
  const data = showcaseFixture("small"), [gateway, core, host, photo] = data.assets;
  data.structural_edges.push({ key: "cycle", source_key: `asset:${gateway.id}`, target_key: `asset:${host.id}`, platform_parent_key: `asset:${host.id}`, kind: "relationship", topology_class: "platform", directional: true });
  data.structural_edges.push({ key: "shared", source_key: `asset:${photo.id}`, target_key: `asset:${core.id}`, platform_parent_key: `asset:${core.id}`, kind: "relationship", topology_class: "platform", directional: true });
  checkPoster(data);
});

function categoryFixture(count) {
  const data = showcaseFixture("small"), host = data.assets.find(a => a.asset_type === "platform");
  data.assets = data.assets.filter(a => !["media", "infra"].includes(a.asset_type));
  const keys = new Set(data.assets.map(a => `asset:${a.id}`));
  data.structural_edges = data.structural_edges.filter(e => keys.has(e.source_key) && keys.has(e.target_key));
  for (let i = 0; i < count; i++) {
    const asset = { ...host, id: id(3000 + i), name: `Workload ${String(i + 1).padStart(2, "0")}`, asset_type: "media" };
    data.assets.push(asset);
    data.structural_edges.push({ key: `test:${i}`, source_key: `asset:${asset.id}`, target_key: `asset:${host.id}`, platform_parent_key: `asset:${host.id}`, kind: "relationship", topology_class: "platform", directional: true });
  }
  return data;
}
for (const count of [1, 2, 4, 5, 8, 16, 20]) test(`category ${count}: singleton/one/two columns without altering topology`, () => {
  const { layout, model } = checkPoster(categoryFixture(count));
  const group = layout.items.find(n => n.kind === "category");
  if (count === 1) { assert.equal(group, undefined); return; }
  assert.equal(group.memberColumns, count < 5 ? 1 : 2); assert.equal(group.hiddenCount, 0);
  for (const [i, node] of group.preview.entries()) {
    const geometry = layout.geometry.find(n => n.key === node.key);
    assert.equal(geometry.x - group.memberWidth / 2, group.x + 12 + i % group.memberColumns * (group.memberWidth + group.memberGap));
    assert.equal(geometry.y - 11, group.y + group.memberTop + Math.floor(i / group.memberColumns) * group.memberRow);
    assert.equal(model.parents.get(node.key), group.parent);
  }
});

test("managed position names/gaps never move branches; custom order matches Connectivity", () => {
  const data = showcaseReferenceFixture(), before = showcaseLayout(showcaseModel(data, id(2)));
  for (const type of data.asset_types) if (type.topology_position) { type.topology_position.sort_order *= 100; type.topology_position.name = `Managed ${type.topology_position.id}`; }
  data.asset_types.push({ key: "unused", topology_position: { id: id(888), name: "Unused", sort_order: 1500 } });
  const { layout } = checkPoster(data);
  assert.deepEqual(layout.geometry.map(n => [n.key, n.x, n.y]), before.geometry.map(n => [n.key, n.x, n.y]));
  data.asset_types.find(t => t.key === "server").topology_position.sort_order = 99999;
  const model = showcaseModel(data, id(2));
  assert.deepEqual(model.parents, buildTopologyLayoutModel(model).parent);
});

test("enormous workload group collapses only after attempting the complete geometry", () => {
  const data = categoryFixture(200), { layout } = checkPoster(data);
  assert.equal(layout.stage, 1); assert.equal(layout.diagnostics.attempts[0].stage, 0);
  assert.equal(layout.diagnostics.attempts[0].failureReason, "height");
  const group = layout.items.find(n => n.kind === "category");
  assert.equal(group.preview.length, 4); assert.equal(group.hiddenCount, 196);
});

test("missing/empty context and pathological structures refuse partial export", () => {
  const data = showcaseFixture("small");
  assert.equal(showcaseLayout(showcaseModel(data, null)).complete, false);
  assert.equal(showcaseLayout(showcaseModel({ ...data, assets: [] }, id(2))).complete, false);
  assert.equal(showcaseLayout(showcaseModel({ ...data, structural_edges: undefined }, id(2))).complete, false);
  const layout = showcaseLayout(showcaseModel(showcasePosterFixture(90), id(2)));
  assert.equal(layout.complete, false); assert.match(layout.reason, /Showcase incomplete/); assert.equal(layout.items, undefined);
  assert.equal(layout.diagnostics.failureReason, "width and height");
});

test("Platform content and Connectivity disclosure/inspector inputs remain unchanged", () => {
  const data = showcaseFixture(), enabled = new Set(data.categories.map(c => c.id));
  const platform = topologyPresentation(data, enabled), model = showcaseModel(data, id(2));
  const graph = { ...model, focus_key: model.nodes.find(n => n.name === "Platform Host A").key,
    nodes: model.nodes.map(n => ({ ...n, distance: 2 })) };
  const preview = connectivityPreview(graph), connectivity = connectivityLayout(graph), routes = connectivityRoutes(connectivity, graph.edges);
  showcaseLayout(model);
  assert.deepEqual(topologyPresentation(data, enabled), platform);
  assert.deepEqual(connectivityPreview(graph), preview); assert.deepEqual(connectivityLayout(graph), connectivity);
  assert.deepEqual(connectivityRoutes(connectivity, graph.edges), routes);
});

test("safe deterministic filenames", () => {
  assert.equal(showcaseFilename("Ben’s Homelab"), "bens-homelab-atlas-showcase.png");
  assert.equal(showcaseFilename("../../ Café / Lab 😀"), "cafe-lab-atlas-showcase.png");
  assert.equal(showcaseFilename("💻"), "site-atlas-showcase.png");
});

test("taller fallback remains minimal and complete after trying 16:9", async () => {
  const { showcaseTallFixture } = await import("./fixtures/showcase.mjs");
  const { layout } = checkPoster(showcaseTallFixture(60));
  assert.equal(layout.stage, 0); assert.ok(layout.sceneHeight > 1080);
  assert.equal(layout.sceneHeight, Math.ceil(layout.diagnostics.sceneHeight * SHOWCASE_MIN_SCALE + SHOWCASE_CONTENT_TOP + 32));
  assert.ok(layout.items.every(n => !n.hiddenCount));
});

test("small site keeps preferred 1920×1080 dimensions", () => {
  const { layout } = checkPoster(showcaseFixture("small"));
  assert.equal(layout.sceneWidth, 1920); assert.equal(layout.sceneHeight, 1080);
});

for (const [name, branches] of [["wide", 18], ["near 2.8:1", 23]]) test(`${name}: complete measured minimum width, unchanged Connectivity ownership`, () => {
  const data = branches === 23 ? showcaseUltrawideFixture() : showcaseWideFixture(branches), { layout, model } = checkPoster(data), d = layout.diagnostics;
  assert.ok(d.initialRequiredScale < SHOWCASE_MIN_SCALE);
  assert.ok(layout.sceneWidth > 1920); assert.equal(layout.sceneHeight, 1080);
  assert.equal(layout.sceneWidth, Math.ceil(d.naturalContentWidth * SHOWCASE_MIN_SCALE + 64));
  assert.ok((layout.sceneWidth - 1 - 64) / d.naturalContentWidth < SHOWCASE_MIN_SCALE, "One fewer pixel would violate the floor");
  assert.equal(layout.stage, 0); assert.equal(d.workloadCollapseAttempted, false);
  assert.equal(d.collapsedGroupCount, 0); assert.equal(d.visibleAssetTileCount, data.assets.length);
  assert.equal(d.componentCount, Math.ceil(branches / 4) + 1); assert.equal(d.rootCount, d.componentCount);
  assert.equal(d.finalScale, layout.scale); assert.equal(d.chosenPosterWidth, layout.sceneWidth);
  assert.equal(d.chosenPosterHeight, layout.sceneHeight); assert.equal(d.failureReason, null);
  assert.ok(layout.geometry.every(n => n.entity_type === "asset"));
  assert.ok(layout.routes.every(e => e.kind !== "membership"));
  const connectivity = connectivityLayout({ ...model, focus_key: model.nodes[0].key });
  for (const node of layout.geometry) {
    const reference = connectivity.find(n => n.key === node.key);
    assert.equal(node.rank, reference.rank); assert.equal(node.positionDepth, reference.positionDepth);
    assert.equal(node.layout_parent_key, reference.layout_parent_key);
  }
  if (branches === 23) assert.ok(layout.sceneWidth / layout.sceneHeight > 2.79);
});

test("both dimensions adapt independently before enormous-site collapse", () => {
  const { layout } = checkPoster(showcaseWideFixture(18, 70)), d = layout.diagnostics;
  assert.ok(layout.sceneWidth > 1920); assert.ok(layout.sceneHeight > 1080);
  assert.equal(layout.sceneWidth, Math.ceil(d.naturalContentWidth * SHOWCASE_MIN_SCALE + 64));
  assert.equal(layout.sceneHeight, Math.ceil(d.naturalContentHeight * SHOWCASE_MIN_SCALE + SHOWCASE_CONTENT_TOP + 32));
  assert.equal(layout.stage, 0); assert.equal(d.workloadCollapseAttempted, false);
  assert.equal(d.visibleAssetTileCount, layout.assetCount);
  assert.ok(layout.items.every(n => !n.hiddenCount));
});

test("normal-size forest beyond the maximum width refuses export without collapse", () => {
  const data = showcaseWideFixture(28), layout = showcaseLayout(showcaseModel(data, id(2))), d = layout.diagnostics;
  assert.equal(data.assets.length, 93); assert.equal(layout.complete, false); assert.equal(layout.items, undefined);
  assert.equal(d.chosenPosterWidth, SHOWCASE_MAX_WIDTH); assert.equal(d.chosenPosterHeight, 1080);
  assert.equal(d.failureReason, "width"); assert.equal(d.workloadCollapseAttempted, false);
  assert.equal(d.attempts.length, 1); assert.ok(d.finalScale < SHOWCASE_MIN_SCALE);
  assert.ok(d.naturalContentWidth * SHOWCASE_MIN_SCALE + 64 > SHOWCASE_MAX_WIDTH);
});
