import test from "node:test";
import assert from "node:assert/strict";
import { showcaseNameLayout, measureShowcaseName, SHOWCASE_MAX_NODE_WIDTH, SHOWCASE_MAX_MEMBER_WIDTH } from "../lib/showcase-text.mjs";
import { showcaseLayout, showcaseModel, SHOWCASE_NODE_WIDTH, SHOWCASE_NODE_HEIGHT } from "../lib/showcase.mjs";
import { showcasePresentationRoutes, assertShowcaseRouteEndpoints, simplifyShowcaseRoute } from "../lib/showcase-routes.mjs";
import { routeTopologyEdges, buildTopologyLayoutModel } from "../lib/topology-geometry.mjs";
import { showcaseFixture, showcaseReadableFixture, showcaseExteriorRoutingFixture, id } from "./fixtures/showcase.mjs";

const common = ["USW-Aggregation", "USW-16-POE (Rack)", "US-8-60W (Office)", "Dell Server 1", "Dell Server 2",
  "Proxmox Dell 1", "Proxmox Dell 2", "AdGuard Home", "Atlas Impact", "HCR Website", "Roadcycling", "Music Assistant",
  "Nginx Proxy Manager", "Proxmox Data Center Manager", "Uptime Kuma"];
test("common Asset names are complete before ellipsis, with bounded local widths and unchanged 15px font metrics", () => {
  for (const name of common) for (const member of [false, true]) {
    const label = showcaseNameLayout(name, member);
    assert.equal(label.truncated, false, name);
    assert.equal(label.lines.join(" "), name);
    assert.ok(label.lines.length <= 2);
    assert.ok(label.width <= (member ? SHOWCASE_MAX_MEMBER_WIDTH : SHOWCASE_MAX_NODE_WIDTH));
    assert.ok(label.lines.every(line => measureShowcaseName(line) <= label.width - (member ? 28 : 44) - 2));
  }
});

test("long full names wrap to two lines; only names exceeding that capacity receive ellipsis", () => {
  const full = showcaseNameLayout("North Wing Infrastructure Monitoring", false);
  assert.equal(full.lines.length, 2); assert.equal(full.truncated, false);
  assert.equal(full.lines.join(" "), "North Wing Infrastructure Monitoring");
  assert.equal(full.height, 46);
  const veryLong = showcaseNameLayout("North Wing Infrastructure Monitoring and Recovery Coordination for All Datacentres", true);
  assert.equal(veryLong.lines.length, 2); assert.equal(veryLong.height, 40);
  assert.equal(veryLong.truncated, true); assert.ok(veryLong.lines[1].endsWith("…"));
  assert.ok(!veryLong.lines[0].includes("…"));
});

test("44-Asset two-column categories use local measured cells and supply real rectangles to unchanged ownership/Positions", () => {
  const data = showcaseReadableFixture(), before = structuredClone(data), model = showcaseModel(data, id(2)), layout = showcaseLayout(model);
  assert.ok(layout.complete, JSON.stringify(layout.diagnostics));
  assert.equal(layout.assetCount, 44); assert.equal(layout.diagnostics.visibleAssetTileCount, 44);
  assert.equal(layout.stage, 0); assert.equal(layout.diagnostics.workloadCollapseAttempted, false);
  assert.equal(layout.sceneWidth, 1920); assert.equal(layout.sceneHeight, 1080);
  assert.deepEqual(data, before);
  assert.deepEqual(model.parents, buildTopologyLayoutModel(model).parent);
  const group = layout.items.find(n => n.kind === "category" && n.members.some(m => m.name === "Proxmox Data Center Manager"));
  assert.equal(group.memberColumns, 2); assert.equal(group.memberHeight, 40); assert.equal(group.memberRow, 50);
  assert.ok(group.memberWidth > 112 && group.memberWidth <= SHOWCASE_MAX_MEMBER_WIDTH);
  for (const node of layout.geometry) {
    assert.equal(node.layout_parent_key, model.parents.get(node.key) || null);
    assert.equal(node.topology_position?.id, model.byKey.get(node.key).topology_position?.id);
    assert.equal(node.nameLayout.truncated, false, node.name);
  }
  for (const [index, member] of group.preview.entries()) {
    const node = layout.geometry.find(n => n.key === member.key);
    assert.equal(node.geometry_width, group.memberWidth); assert.equal(node.geometry_height, group.memberHeight);
    assert.equal(node.x - node.geometry_width / 2, group.x + 12 + index % 2 * (group.memberWidth + group.memberGap));
    assert.equal(node.y - node.geometry_height / 2, group.y + group.memberTop + Math.floor(index / 2) * group.memberRow);
  }
  assert.equal(assertShowcaseRouteEndpoints(layout), true);
  assert.deepEqual(layout.routes.flatMap(r => r.relationshipKeys).sort(), model.edges.map(e => e.key).sort());
});

test("two hosted siblings share one legitimate category connector and retain both relationship identities", () => {
  const data = showcaseFixture("small");
  data.assets.find(n => n.name === "DNS Service").asset_type = "media";
  const layout = showcaseLayout(showcaseModel(data, id(2))), group = layout.items.find(n => n.kind === "category");
  assert.ok(layout.complete); assert.equal(group.members.length, 2);
  const connectors = layout.routes.filter(r => r.group_key === group.key);
  assert.equal(connectors.length, 1); assert.equal(connectors[0].relationshipKeys.length, 2);
  assert.equal(connectors[0].sourceEndpoint.key, group.key);
  assert.equal(connectors[0].targetEndpoint.key, group.parent);
  assert.equal(layout.routes.filter(r => group.node_keys.includes(r.sourceEndpoint.key)).length, 0);
  assert.equal(assertShowcaseRouteEndpoints(layout), true);
});

test("dangling fallback spur: unpoller and Homarr keep separate categories; normalize the out-and-back tail, preserving endpoints", () => {
  const data = showcaseReadableFixture(), model = showcaseModel(data, id(2));
  // Reproduce the previous fixed compact rectangles without changing the engine.
  const layout = showcaseLayout(model, { measureName: () => 0 });
  const groups = layout.items.filter(n => n.kind === "category");
  const raw = routeTopologyEdges(layout.geometry, model.edges, groups,
    { nodeWidth: SHOWCASE_NODE_WIDTH, nodeHeight: SHOWCASE_NODE_HEIGHT, railGap: 16, allowExteriorFallback: true });
  const source = model.nodes.find(n => n.name === "unpoller"), other = model.nodes.find(n => n.name === "Homarr");
  assert.notEqual(source.category.id, other.category.id);
  const edge = model.edges.find(e => e.source_key === source.key);
  assert.equal(model.byKey.get(edge.target_key).name, "Docker Inf");
  assert.equal(raw[edge.key].fallback_routing, "exterior"); assert.equal(raw[edge.key].group_key, undefined);
  assert.deepEqual(raw[edge.key].points.slice(0, 3), [[425, 408], [425, 542], [425, 508]], "Exterior route retraces the last 34px of a dead tail");
  const routes = showcasePresentationRoutes(model.edges, raw, layout.items, layout.geometry), route = routes.find(r => r.key === edge.key);
  assert.equal(route.source_key, source.key); assert.equal(route.target_key, edge.target_key);
  assert.equal(route.sourceEndpoint.key, source.key); assert.equal(route.targetEndpoint.key, edge.target_key);
  assert.ok(!route.points.some(p => p[0] === 425 && p[1] === 542));
  assert.deepEqual(route.relationshipKeys, [edge.key]); assert.deepEqual(raw[edge.key].points, route.routerPoints);
  assert.equal(assertShowcaseRouteEndpoints({ ...layout, routes }), true);
});

test("missing/hidden endpoints and stale pre-group attachments fail with relationship and endpoint diagnostics", () => {
  const layout = showcaseLayout(showcaseModel(showcaseExteriorRoutingFixture(), id(2)));
  const memberRoute = layout.routes.find(r => r.fallback_routing && r.sourceEndpoint.kind === "asset");
  const broken = structuredClone(layout);
  for (const item of broken.items) if (item.kind === "category") item.preview = item.preview.filter(n => n.key !== memberRoute.sourceEndpoint.key);
  assert.throws(() => assertShowcaseRouteEndpoints(broken), error => {
    assert.equal(error.presentationDiagnostic.relationshipKey, memberRoute.key);
    assert.equal(error.presentationDiagnostic.renderedEndpoint, memberRoute.sourceEndpoint.key);
    return /visible tile/.test(error.message);
  });
  const stale = structuredClone(layout), route = stale.routes[0];
  route.points[0] = [route.points[0][0] + 1000, route.points[0][1]];
  assert.throws(() => assertShowcaseRouteEndpoints(stale), /stale attachment/);
});

test("exterior fallback retains all visible endpoints and normalization never adds diagonal segments", () => {
  const layout = showcaseLayout(showcaseModel(showcaseExteriorRoutingFixture(), id(2)));
  assert.ok(layout.complete); assert.ok(layout.routes.some(r => r.fallback_routing === "exterior"));
  assert.equal(assertShowcaseRouteEndpoints(layout), true);
  assert.deepEqual(simplifyShowcaseRoute([[0, 0], [0, 10], [0, 30], [0, 20], [10, 20]]), [[0, 0], [0, 20], [10, 20]]);
  for (const route of layout.routes) for (let index = 1; index < route.points.length; index++) {
    const a = route.points[index - 1], b = route.points[index];
    assert.ok(a[0] === b[0] || a[1] === b[1]);
    for (const n of layout.geometry) {
      const left = n.x - n.geometry_width / 2, right = n.x + n.geometry_width / 2;
      const top = n.y - n.geometry_height / 2, bottom = n.y + n.geometry_height / 2;
      assert.equal(a[0] === b[0] ? a[0] > left && a[0] < right && Math.max(a[1], b[1]) > top && Math.min(a[1], b[1]) < bottom
        : a[1] > top && a[1] < bottom && Math.max(a[0], b[0]) > left && Math.min(a[0], b[0]) < right, false, `${route.key} crosses ${n.key}`);
    }
  }
});
