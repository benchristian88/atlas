import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { performance } from "node:perf_hooks";
import { WIDGETS, LANES, DEFAULT_FAMILIES, completenessPercent, parseGraphState, graphHref, presentLandscape, analysisOverlay, analysisState } from "../lib/operations-experience.mjs";
import { resolveSelection } from "../lib/workspace-selection.mjs";
import { recordContextOptions } from "../lib/record-context.mjs";

const focus = "service:00000000-0000-4000-8000-000000000001";
const sample = {
  nodes: [
    { key: "asset:a", name: "AdGuard", entity_type: "asset" },
    { key: focus, name: "DNS", entity_type: "service", criticality_rank: 75, open_gap_count: 2 },
    { key: "business_function:f", name: "Home", entity_type: "business_function" },
    { key: "service:proxy", name: "Proxy", entity_type: "service" },
  ],
  edges: [
    { key: "provider", edge_family: "service_asset", source_key: focus, target_key: "asset:a", label: "Provided by" },
    { key: "supports", edge_family: "service_business_function", source_key: focus, target_key: "business_function:f", label: "Supports" },
    { key: "depends", edge_family: "service_service", source_key: "service:proxy", target_key: focus, label: "Depends on" },
  ],
};

test("dashboard registry has exactly five fixed, stable widgets in product order", () => {
  assert.deepEqual(WIDGETS.map((w) => w.id), ["environment-summary", "environment-overview", "attention", "critical-services", "recent-meaningful-changes"]);
  assert.ok(Object.isFrozen(WIDGETS));
});

test("required completeness reuses the existing ratio and does not invent BF scores", () => {
  assert.equal(completenessPercent({ required_total: 4, required_satisfied: 3 }), 75);
  assert.equal(completenessPercent({ required_total: 0, required_satisfied: 0 }), 100);
  assert.equal(completenessPercent({}), null);
});

test("URL state round trips focus, depth, analysis, node and relationship filters", () => {
  const state = { focus, depth: 2, analysis: true, types: ["asset", "service"], families: ["service_asset"] };
  assert.deepEqual(parseGraphState(new URL(graphHref(state), "https://atlas.test").searchParams), state);
  assert.equal(parseGraphState(new URLSearchParams()).focus, "");
  assert.equal(parseGraphState(new URLSearchParams("depth=20&focus=malformed&analysis=unavailable")).analysis, false);
  assert.equal(parseGraphState(new URLSearchParams(`focus=${focus.replace("service", "business_function")}&analysis=unavailable`)).analysis, false);
  assert.equal(parseGraphState(new URLSearchParams("relationships=&types=")).families.length, 0);
});

test("single explicit Customer/Site is restored or deterministically selected", () => {
  const options = { customers: [{ id: "c1" }, { id: "c2" }], sites: [{ id: "s1", customer_id: "c1" }, { id: "s2", customer_id: "c1" }, { id: "s3", customer_id: "c2" }], allowGlobal: true };
  assert.deepEqual(resolveSelection(options), { customerId: "c1", siteId: "s1" });
  assert.deepEqual(resolveSelection({ ...options, preferred: { customerId: null, siteId: null } }), { customerId: "c1", siteId: "s1" });
  assert.deepEqual(resolveSelection({ ...options, preferred: { customerId: "c2", siteId: "s1" } }), { customerId: "c2", siteId: "s3" });
  assert.deepEqual(resolveSelection({ ...options, preferred: { customerId: "c1", siteId: "s2" } }), { customerId: "c1", siteId: "s2" });
  assert.deepEqual(resolveSelection({ customers: [], sites: [] }), { customerId: null, siteId: null });
});

test("customer-wide form mutations preserve record scope without changing workspace viewpoint", () => {
  assert.deepEqual(recordContextOptions("customer", null), { omitContext: true, headers: { "X-Atlas-Customer-ID": "customer" } });
  assert.equal(recordContextOptions("customer", "site").headers["X-Atlas-Site-ID"], "site");
  assert.throws(() => recordContextOptions(null, null));
});

test("three lanes retain canonical edges and secondary Service dependencies", () => {
  const view = presentLandscape(sample);
  assert.deepEqual(view.lanes.map((l) => l.type), ["business_function", "service", "asset"]);
  assert.deepEqual(view.edges.map((e) => e.label), ["Provided by", "Supports", "Depends on"]);
  assert.equal(view.edges[1].source_key, focus);
  assert.ok(!DEFAULT_FAMILIES.includes("asset_relationship"));
  assert.equal(presentLandscape(sample, { families: [] }).edges.length, 0);
  const filtered = presentLandscape(sample, { types: ["service"] });
  assert.equal(filtered.filteredNodes, 2);
  assert.equal(filtered.edges.length, 1);
});

test("progressive disclosure counts supplied records and preserves focused item", () => {
  const nodes = Array.from({ length: 30 }, (_, i) => ({ key: `asset:${i}`, entity_type: "asset", name: `Host ${String(i).padStart(2, "0")}` }));
  const collapsed = presentLandscape({ nodes }, { limit: 5, selected: "asset:29" });
  assert.equal(collapsed.lanes[2].omitted, 25);
  assert.ok(collapsed.lanes[2].nodes.some((n) => n.key === "asset:29"));
  assert.equal(presentLandscape({ nodes }, { expanded: ["asset"] }).lanes[2].omitted, 0);
  assert.equal(presentLandscape({ nodes: nodes.slice(0, 3) }).lanes[2].total, 3);
});

test("quick filters use recorded criticality and gaps only", () => {
  assert.equal(presentLandscape(sample, { quick: "critical" }).lanes[1].total, 2);
  assert.equal(presentLandscape(sample, { quick: "gaps" }).lanes[2].total, 1);
  assert.equal(presentLandscape({ nodes: sample.nodes.map((n) => ({ ...n, criticality_rank: 0 })), edges: sample.edges }, { quick: "critical" }).lanes[1].total, 0);
});

for (const state of ["unavailable", "degraded", "unknown", "unaffected"]) test(`analysis ${state} is an API overlay, preserves identity and excludes BF availability`, () => {
  const analysis = { focus_key: "asset:a", focus: sample.nodes[0], results: [{ service: sample.nodes[1], state, paths: [{ nodes: [sample.nodes[0], sample.nodes[1]], edges: [sample.edges[0]] }], reasons: [] }] };
  const overlay = analysisOverlay(sample, analysis);
  assert.equal(analysisState(overlay.nodesByKey[focus], analysis), state);
  assert.equal(analysisState(overlay.nodesByKey["business_function:f"], analysis), null);
  assert.equal(analysisState(overlay.nodesByKey["service:proxy"], analysis), null);
  assert.equal(overlay.edges[0].source_key, focus);
  assert.equal(overlay.nodesByKey[focus].criticality_rank, 75);
});

test("dense presentation stays deterministic without shrinking nodes to hide records", () => {
  const nodes = LANES.flatMap((lane, index) => Array.from({ length: [20, 40, 150][index] }, (_, i) => ({ key: `${lane.type}:${i}`, entity_type: lane.type, name: `Entity ${i}` })));
  const edges = Array.from({ length: 300 }, (_, i) => ({ key: `edge:${i}`, edge_family: "service_asset", source_key: `service:${i % 40}`, target_key: `asset:${i % 150}`, label: "Provided by" }));
  const started = performance.now();
  const first = presentLandscape({ nodes, edges });
  const second = presentLandscape({ nodes: [...nodes].reverse(), edges });
  assert.deepEqual(first, second);
  assert.equal(first.lanes.reduce((n, l) => n + l.omitted, 0), 186);
  assert.equal(presentLandscape({ nodes, edges }, { expanded: LANES.map((l) => l.type) }).edges.length, 300);
  console.log(`C2.4 presentation: 210 nodes / 300 edges, two layouts ${(performance.now() - started).toFixed(2)}ms`);
});

test("reachable UI provides keyboard nodes, inspector semantics, scenario labels, and bounded search", async () => {
  const read = (path) => readFile(new URL(path, import.meta.url), "utf8");
  const [page, landscape, inspector, dashboard, primitives, css] = await Promise.all([read("../app/knowledge-graph/page.js"), read("../components/service-landscape.js"), read("../components/graph-inspector.js"), read("../app/dashboard/page.js"), read("../components/operations-primitives.js"), read("../app/globals.css")]);
  assert.match(page, /site_viewpoint=true/);
  assert.match(page, /Find in graph/);
  assert.match(page, /limit=8/);
  assert.match(page, /Exit analysis/);
  assert.match(landscape, /aria-pressed/);
  assert.match(landscape, /Recorded relationships in this view/);
  assert.match(landscape, /ALL REQUIRED/);
  assert.match(landscape, /ANY ONE/);
  assert.match(inspector, /Contextual IP/);
  assert.match(inspector, /Contextual VLAN/);
  assert.match(inspector, /Not evaluated for Business Functions/);
  assert.match(inspector, /reason.summary/);
  assert.match(inspector, /result.distance/);
  assert.match(primitives, /Recorded status:/);
  assert.match(primitives, /role="meter"/);
  assert.match(dashboard, /Build your service landscape/);
  assert.match(dashboard, /role="alert"/);
  assert.match(dashboard, /role="status"/);
  assert.doesNotMatch(page, /minimap|layout selector|force.directed/i);
  assert.match(css, /prefers-reduced-motion/);
  assert.match(css, /:root\[data-theme="dark"\]/);
  assert.match(css, /focus-visible/);
});

test("depth 3 Focus URLs round trip without adding expanded display state", () => {
  const state = { focus, depth: 3, analysis: true, types: ["asset", "service"], families: ["service_asset", "asset_relationship"] };
  assert.deepEqual(parseGraphState(new URL(graphHref(state), "https://atlas.test").searchParams), state);
  assert.equal(parseGraphState(new URLSearchParams("depth=4")).depth, 1);
  assert.ok(!graphHref(state).includes("expanded"));
});
