import test from "node:test";
import assert from "node:assert/strict";
import { routeTopologyEdges, topologyBounds, orthogonalDetour } from "../lib/topology-geometry.mjs";
import { showcaseLayout, showcaseModel, SHOWCASE_NODE_WIDTH, SHOWCASE_NODE_HEIGHT } from "../lib/showcase.mjs";
import { showcaseExteriorRoutingFixture, showcaseDenseRoutingFixture, showcaseLiveRoutingFixture, id } from "./fixtures/showcase.mjs";

const metrics = { nodeWidth: SHOWCASE_NODE_WIDTH, nodeHeight: SHOWCASE_NODE_HEIGHT, railGap: 16 };
const crosses = (p, q, r) => p[0] === q[0]
  ? p[0] > r.left && p[0] < r.right && Math.max(p[1], q[1]) > r.top && Math.min(p[1], q[1]) < r.bottom
  : p[1] > r.top && p[1] < r.bottom && Math.max(p[0], q[0]) > r.left && Math.min(p[0], q[0]) < r.right;
function checkRoutes(nodes, routes, groups) {
  const rectangles = nodes.map(n => ({ key: n.key,
    left: n.x - (n.geometry_width ?? metrics.nodeWidth) / 2 - 6, right: n.x + (n.geometry_width ?? metrics.nodeWidth) / 2 + 6,
    top: n.y - (n.geometry_height ?? metrics.nodeHeight) / 2 - 6, bottom: n.y + (n.geometry_height ?? metrics.nodeHeight) / 2 + 6 }));
  const headers = groups.map(g => ({ key: g.key, left: g.left + 10, right: g.left + 14 + g.labelWidth,
    top: g.top + g.labelTop - 2, bottom: g.top + g.labelTop + 22 }));
  for (const [key, route] of Object.entries(routes)) {
    if (route.render === false) continue;
    const edge = route.edge;
    const unrelated = groups.filter(g => !g.node_keys.includes(edge.source_key) && !g.node_keys.includes(edge.target_key))
      .map(g => ({ key: g.key, left: g.left, right: g.left + g.width, top: g.top, bottom: g.top + g.height }));
    for (let i = 1; i < route.points.length; i++) {
      const p = route.points[i - 1], q = route.points[i];
      assert.ok(p[0] === q[0] || p[1] === q[1], `${key} is orthogonal`);
      for (const rectangle of [...rectangles, ...headers, ...unrelated]) assert.equal(crosses(p, q, rectangle), false, `${key} crosses ${rectangle.key}`);
    }
  }
}
function routedWithEdges(nodes, edges, groups, options) {
  const routes = routeTopologyEdges(nodes, edges, groups, options);
  return Object.fromEntries(edges.map(edge => [edge.key, { ...routes[edge.key], edge }]));
}

test("blocked fixed port: opt-in exterior fallback changes only the route, retains canonical endpoints and expands bounds", () => {
  const nodes = [{ key: "asset:source", name: "Source", entity_type: "asset", x: 0, y: 0 },
    { key: "asset:nearby", name: "Nearby card", entity_type: "asset", x: 0, y: 42 },
    { key: "asset:target", name: "Target", entity_type: "asset", x: 200, y: 200 }];
  const edge = { key: "relationship:blocked", source_key: nodes[0].key, target_key: nodes[2].key, kind: "relationship", topology_class: "physical_network" };
  const before = structuredClone({ nodes, edge });
  let failure;
  assert.throws(() => routeTopologyEdges(nodes, [edge], [], metrics), error => {
    failure = error.routingDiagnostic; return /no clear orthogonal track/.test(error.message);
  });
  assert.deepEqual(failure.startBlockedBy, [nodes[1].key]);
  const blocker = { left: -68, right: 68, top: 20, bottom: 64 };
  assert.equal(orthogonalDetour(failure.start, failure.end, [blocker]), null, "Fixed start is inside the neighbouring card's clearance");
  const routes = routedWithEdges(nodes, [edge], [], { ...metrics, allowExteriorFallback: true });
  assert.equal(routes[edge.key].fallback_routing, "exterior");
  assert.ok(["left", "right", "top", "bottom"].includes(routes[edge.key].exterior_direction));
  assert.deepEqual(routes[edge.key].edge, edge);
  checkRoutes(nodes, routes, []);
  assert.deepEqual({ nodes, edge }, before);
  const plain = topologyBounds(nodes, {}, [], metrics), routed = topologyBounds(nodes, routes, [], metrics);
  assert.ok(routed.minY < plain.minY || routed.minX < plain.minX || routed.width > plain.width || routed.height > plain.height);
  assert.deepEqual(routedWithEdges([...nodes].reverse(), [edge], [], { ...metrics, allowExteriorFallback: true }), routes);
  const reverse = { ...edge, source_key: edge.target_key, target_key: edge.source_key };
  const reversed = routeTopologyEdges(nodes, [reverse], [], { ...metrics, allowExteriorFallback: true })[edge.key];
  assert.deepEqual(reversed.points, [...routes[edge.key].points].reverse(), "Presentation reversal preserves canonical direction");
});

test("member port inside its own title: repair group access locally, preserving header/card obstacles", () => {
  const nodes = [{ key: "asset:source", name: "Source", entity_type: "asset", x: 0, y: 0 },
    { key: "asset:member", name: "Member", entity_type: "asset", x: 200, y: 100, geometry_width: 112, geometry_height: 22 },
    { key: "asset:peer", name: "Peer", entity_type: "asset", x: 200, y: 132, geometry_width: 112, geometry_height: 22 }];
  const group = { key: "category:members", left: 132, top: 57, width: 136, height: 94, labelTop: 8, labelWidth: 112,
    node_keys: [nodes[1].key, nodes[2].key], disclosure_keys: [] };
  const edge = { key: "relationship:group-entry", source_key: nodes[0].key, target_key: nodes[1].key, kind: "relationship", topology_class: "physical_network" };
  const before = structuredClone({ nodes, group });
  assert.throws(() => routeTopologyEdges(nodes, [edge], [group], metrics), error => {
    assert.ok(error.routingDiagnostic.endBlockedBy.includes(group.key)); return /no clear orthogonal track/.test(error.message);
  });
  const routes = routedWithEdges(nodes, [edge], [group], { ...metrics, allowExteriorFallback: true });
  assert.equal(routes[edge.key].fallback_routing, "group-port");
  assert.equal(routes[edge.key].routing_diagnostic.targetGroupKey, group.key);
  checkRoutes(nodes, routes, [group]);
  assert.deepEqual({ nodes, group }, before);
});

for (const [name, fixture, count] of [["forced exterior", showcaseExteriorRoutingFixture, 10],
  ["dense categories", showcaseDenseRoutingFixture, 39], ["realistic live shape", showcaseLiveRoutingFixture, 44]]) test(`${name}: normal routing fails, Showcase remains complete without moving Assets`, () => {
  const data = fixture(), original = structuredClone(data), model = showcaseModel(data, id(2)), layout = showcaseLayout(model);
  assert.ok(layout.complete, JSON.stringify(layout.diagnostics));
  assert.equal(layout.assetCount, count); assert.equal(layout.diagnostics.visibleAssetTileCount, count);
  assert.equal(layout.sceneWidth, 1920); assert.equal(layout.sceneHeight, 1080); assert.ok(layout.scale > 1);
  assert.equal(layout.stage, 0); assert.equal(layout.diagnostics.workloadCollapseAttempted, false);
  assert.ok(layout.diagnostics.fallbackRouteCount > 0);
  const groups = layout.items.filter(n => n.kind === "category");
  assert.throws(() => routeTopologyEdges(layout.geometry, model.edges, groups, metrics), /no clear orthogonal track/);
  const routes = routedWithEdges(layout.geometry, model.edges, groups, { ...metrics, allowExteriorFallback: true });
  checkRoutes(layout.geometry, routes, groups);
  for (const route of layout.routes) {
    assert.deepEqual(route.points, routes[route.key].points);
    assert.equal(route.source_key, routes[route.key].edge.source_key); assert.equal(route.target_key, routes[route.key].edge.target_key);
  }
  assert.deepEqual(layout.representedAssetIds, data.assets.map(n => n.id).sort());
  assert.deepEqual(layout.routes.flatMap(r => r.relationshipKeys).sort(), model.edges.map(e => e.key).sort());
  const bounds = topologyBounds(layout.geometry, routes, groups, metrics);
  assert.equal(layout.diagnostics.naturalContentWidth, bounds.width); assert.equal(layout.diagnostics.naturalContentHeight, bounds.height);
  assert.deepEqual(showcaseLayout(showcaseModel({ ...data, assets: [...data.assets].reverse(), structural_edges: [...data.structural_edges].reverse() }, id(2))), layout);
  assert.deepEqual(data, original);
});

test("fallback preserves unrelated presentation containers and refuses an endpoint buried inside another card", () => {
  const nodes = [{ key: "asset:source", name: "Source", entity_type: "asset", x: 0, y: 0 },
    { key: "asset:nearby", name: "Nearby", entity_type: "asset", x: 0, y: 42 },
    { key: "asset:target", name: "Target", entity_type: "asset", x: 300, y: 200 }];
  const group = { key: "category:unrelated", left: 100, top: 60, width: 136, height: 94, labelTop: 8, labelWidth: 112, node_keys: [], disclosure_keys: [] };
  const edge = { key: "relationship:blocked", source_key: nodes[0].key, target_key: nodes[2].key, kind: "relationship", topology_class: "physical_network" };
  const routes = routedWithEdges(nodes, [edge], [group], { ...metrics, allowExteriorFallback: true });
  assert.equal(routes[edge.key].fallback_routing, "exterior");
  checkRoutes(nodes, routes, [group]);
  nodes[1] = { ...nodes[1], x: 0, y: 0, geometry_width: 400, geometry_height: 400 };
  assert.throws(() => routeTopologyEdges(nodes, [edge], [], { ...metrics, allowExteriorFallback: true }), error => {
    assert.equal(error.routingDiagnostic.relationshipKey, edge.key);
    assert.ok(error.routingDiagnostic.startBlockedBy.includes(nodes[1].key));
    return /no clear orthogonal track/.test(error.message);
  });
});

test("successful standard routes stay identical when fallback is enabled", () => {
  const nodes = [{ key: "asset:source", name: "Source", entity_type: "asset", x: 0, y: 0 },
    { key: "asset:target", name: "Target", entity_type: "asset", x: 0, y: 100 }];
  const edge = { key: "relationship:ordinary", source_key: nodes[0].key, target_key: nodes[1].key, kind: "relationship", topology_class: "physical_network" };
  assert.deepEqual(routeTopologyEdges(nodes, [edge], [], { ...metrics, allowExteriorFallback: true }), routeTopologyEdges(nodes, [edge], [], metrics));
});

test("fallback visibility can use a narrow clear corridor omitted by default offset tracks", () => {
  const rectangles = [
    { left: -120, right: -100, top: -120, bottom: 120 },
    { left: 100, right: 120, top: -120, bottom: 120 },
    { left: -100, right: 100, top: -120, bottom: -100 },
    { left: -100, right: 100, top: 100, bottom: 120 },
    { left: -10, right: 10, top: -100, bottom: -2 },
    { left: -100, right: 40, top: 10, bottom: 30 },
    { left: 52, right: 100, top: 10, bottom: 30 },
  ];
  const start = [-50, -50], end = [75, 60];
  assert.equal(orthogonalDetour(start, end, rectangles), null);
  const points = orthogonalDetour(start, end, rectangles, { includeBoundaryTracks: true });
  assert.ok(points); assert.deepEqual(points[0], start); assert.deepEqual(points.at(-1), end);
  for (let i = 1; i < points.length; i++) for (const rectangle of rectangles) assert.equal(crosses(points[i - 1], points[i], rectangle), false);
  const length = points.slice(1).reduce((sum, p, i) => sum + Math.abs(p[0] - points[i][0]) + Math.abs(p[1] - points[i][1]), 0);
  assert.equal(length, 235, "Shortest safe path fits the corridor without changing clearance");
});
