import test from "node:test";
import assert from "node:assert/strict";
import { performance } from "node:perf_hooks";
import { presentLandscape } from "../lib/operations-experience.mjs";
import { normalizeOperationalGraph } from "../lib/operational-graph.mjs";
import { layoutLandscape, routeLandscape, landscapeGroupPath, selectedLandscapeEdges } from "../lib/landscape-layout.mjs";
import { singletonGraph, dnsGraph, denseRoutingGraph } from "./fixtures/edge-routing.mjs";
const project = (graph, width = 1200) => { const presentation = presentLandscape(graph, { expanded: ["asset", "service", "business_function"] }); const layout = layoutLandscape(presentation, width); return { presentation, layout, routes: routeLandscape(presentation, layout) }; };

test("singleton uses direct cubic sides, preserving Service→Function direction and metadata", () => {
  const { layout, routes } = project(singletonGraph);
  assert.equal(layout.groups.length, 0); assert.equal(routes.length, 2);
  const home = routes.find(route => route.key === "home"), context = routes.find(route => route.key === "smart");
  assert.deepEqual([home.sourceSide, home.targetSide], ["right", "left"]);
  assert.deepEqual([context.sourceSide, context.targetSide], ["left", "right"]);
  assert.equal(context.edge.source_key, "service:home");
  for (const route of routes) { assert.match(route.path, / C/); assert.doesNotMatch(route.path, /[HV]|NaN/); }
  assert.equal(home.edge.failure_effect, "unavailable");
  assert.equal(home.edge.dependency_group_id, "home");
  assert.equal(home.path.split(" C")[0], `M${home.source.x + layout.nodeWidth} ${home.source.y + layout.nodeHeight / 2}`);
});
test("DNS group has one smooth trunk and distinct fan-out ports; controller stays direct", () => {
  const { layout, routes } = project(dnsGraph);
  assert.equal(layout.groups.length, 1);
  const group = layout.groups[0], members = routes.filter(route => route.group);
  assert.equal(members.length, 2);
  assert.notEqual(members[0].sourcePort, members[1].sourcePort);
  for (const route of members) { assert.equal(route.source, group); assert.equal(route.sourceSide, "right"); assert.equal(route.targetSide, "left"); }
  assert.equal(routes.find(route => route.key === "control").group, undefined);
  const trunk = landscapeGroupPath(layout.positions.get(group.source_key), group, layout);
  assert.match(trunk, / C/); assert.doesNotMatch(trunk, /[HV]/);
});
test("same-lane dependencies use left anchors; shared Asset fan-in has separate ports", () => {
  const { routes } = project(denseRoutingGraph);
  const depends = routes.find(route => route.key === "proxy-dns");
  assert.deepEqual([depends.sourceSide, depends.targetSide], ["left", "left"]);
  assert.equal(depends.path.split(" C").length, 3);
  assert.equal(new Set(routes.filter(r => r.edge.target_key === "asset:udm").map(r => r.targetPort)).size, 3);
});
test("selected DNS or AdGuard traces entire HA requirement while singleton selection stays local", () => {
  const { presentation } = project(denseRoutingGraph);
  for (const selected of ["service:dns", "asset:adguard1"]) {
    const keys = selectedLandscapeEdges(presentation.edges, selected);
    assert.ok(keys.has("adguard1") && keys.has("adguard2"));
    assert.ok(!keys.has("nginx"));
  }
  assert.deepEqual([...selectedLandscapeEdges(presentation.edges, "asset:atlas")], ["control"]);
  assert.ok(selectedLandscapeEdges(presentation.edges, "", "ha").has("adguard2"));
});
test("routing is input-order independent, responsive and leaves normalization unchanged", () => {
  const original = normalizeOperationalGraph(denseRoutingGraph), snapshot = structuredClone(original);
  const wide = project(original, 1440), narrow = project(original, 390);
  assert.notEqual(wide.routes.find(r => r.key === "control").path, narrow.routes.find(r => r.key === "control").path);
  const reversed = project({ ...original, edges: [...original.edges].reverse() }, 1440);
  assert.deepEqual(wide.routes.map(r => r.path), reversed.routes.map(r => r.path));
  assert.deepEqual(original, snapshot);
  const started = performance.now();
  for (let i = 0; i < 250; i++) routeLandscape(wide.presentation, wide.layout);
  assert.ok(performance.now() - started < 2000, "bounded routing should not impede interaction");
});
