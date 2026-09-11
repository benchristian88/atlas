import test from "node:test";
import assert from "node:assert/strict";
import { DEFAULT_FAMILIES, projectVisibleGraph, presentLandscape, visibleGraphSelection, analysisOverlay } from "../lib/operations-experience.mjs";
const node = (key, name = key) => ({ key, name, entity_type: key.split(":")[0] });
const edge = (key, source_key, target_key, edge_family, extra = {}) => ({ key, source_key, target_key, edge_family, ...extra });
const focus = "service:dns";
const dns = node(focus, "DNS Resolution and Filtering"), adguard = node("asset:adguard", "AdGuard Home"), pve = node("asset:pve", "PVE1"), proxy = node("service:proxy", "Reverse Proxy and Application Publishing"), nginx = node("asset:nginx", "Nginx Proxy Manager");
const provider = edge("provider", focus, adguard.key, "service_asset"), runs = edge("runs", adguard.key, pve.key, "asset_relationship"), depends = edge("depends", proxy.key, focus, "service_service"), proxyProvider = edge("proxy-provider", proxy.key, nginx.key, "service_asset", { dependency_group_id: "core", dependency_group_name: "Core Operation", dependency_strategy: "all" });
const graph = { nodes: [dns, adguard, pve, proxy, nginx], edges: [provider, runs, depends, proxyProvider] };
const all = [...DEFAULT_FAMILIES, "asset_relationship"];
const keys = (view) => view.nodes.map((n) => n.key);
for (const depth of [1, 2]) test(`depth ${depth}: repeated Asset toggles prune before layout and preserve incoming paths`, () => {
  const input = depth === 1 ? { nodes: [dns, adguard, proxy], edges: [provider, depends] } : graph;
  const original = structuredClone(input);
  for (const families of [all, DEFAULT_FAMILIES, all, DEFAULT_FAMILIES]) {
    const result = projectVisibleGraph(input, { focus, families });
    const expected = input.nodes.filter((n) => n !== pve || families === all).map((n) => n.key);
    assert.deepEqual(keys(result), expected);
    assert.equal(result.edges.some((e) => e.key === "runs"), depth === 2 && families === all);
    const presentation = presentLandscape(input, { focus, families });
    assert.deepEqual(presentation.lanes.flatMap((l) => l.nodes.map((n) => n.key)).sort(), [...expected].sort());
    assert.deepEqual(presentation.edges, result.edges);
  }
  assert.deepEqual(input, original);
});
test("isolated focus survives all relationship and node-type filters", () => {
  const result = projectVisibleGraph(graph, { focus, families: [], types: [] });
  assert.deepEqual(keys(result), [focus]);
  assert.deepEqual(result.edges, []);
  assert.deepEqual(presentLandscape(graph, { focus, families: [], types: [] }).lanes[1].nodes.map((n) => n.key), [focus]);
});
test("alternative routes and cycles retain reachable nodes without changing direction", () => {
  const result = projectVisibleGraph({ ...graph, edges: [...graph.edges, edge("alternate", proxy.key, pve.key, "service_asset"), edge("cycle", focus, proxy.key, "service_service")] }, { focus });
  assert.deepEqual(keys(result), graph.nodes.map((n) => n.key));
  assert.equal(result.edges.find((e) => e.key === "depends").source_key, proxy.key);
});
test("disconnected components and their dependency markers are pruned even with internal edges", () => {
  const group = { dependency_group_id: "core", edges: [proxyProvider] };
  assert.equal(visibleGraphSelection(projectVisibleGraph(graph, { focus }), proxy.key, focus, group).group.edges.length, 1);
  const hidden = projectVisibleGraph(graph, { focus, families: ["service_asset"] });
  assert.deepEqual(keys(hidden), [focus, adguard.key]);
  assert.equal(visibleGraphSelection(hidden, proxy.key, focus, group).group, null);
  assert.ok(presentLandscape(graph, { focus, families: ["service_asset"] }).edges.every((e) => !e.dependency_group_id));
  const noMembers = projectVisibleGraph(graph, { focus, families: ["service_service"] });
  assert.equal(visibleGraphSelection(noMembers, proxy.key, focus, group).group, null);
  assert.ok(!keys(noMembers).includes(nginx.key));
});
test("inspector falls back from hidden selection to focus or Overview default", () => {
  assert.equal(visibleGraphSelection(projectVisibleGraph(graph, { focus, families: all }), pve.key, focus).node.key, pve.key);
  assert.equal(visibleGraphSelection(projectVisibleGraph(graph, { focus }), pve.key, focus).node.key, focus);
  assert.equal(visibleGraphSelection(projectVisibleGraph(graph), pve.key, "").node, null);
});
test("Overview preserves unlinked knowledge and visible components but removes filtered orphans", () => {
  const isolated = node("asset:unlinked");
  const result = projectVisibleGraph({ ...graph, nodes: [...graph.nodes, isolated] });
  assert.ok(keys(result).includes(isolated.key));
  assert.ok(keys(result).includes(nginx.key));
  assert.ok(!keys(result).includes(pve.key));
});
test("focus and selection are both pinned through lane disclosure", () => {
  const nodes = Array.from({ length: 12 }, (_, i) => node(`service:${i}`, String(i).padStart(2, "0")));
  const edges = nodes.slice(1).map((n) => edge(n.key, nodes[0].key, n.key, "service_service"));
  const view = presentLandscape({ nodes, edges }, { focus: nodes[11].key, selected: nodes[10].key });
  assert.ok(view.lanes[1].nodes.some((n) => n.key === nodes[11].key));
  assert.ok(view.lanes[1].nodes.some((n) => n.key === nodes[10].key));
});
test("analysis retains existing overlay context when relationship lines are filtered", () => {
  const analysis = { focus_key: focus, focus: dns, results: [{ service: proxy, paths: [{ nodes: [proxy, dns], edges: [depends] }], reasons: [] }] };
  const overlay = analysisOverlay(graph, analysis);
  const view = projectVisibleGraph(overlay, { focus, analysis: true, families: [] });
  assert.deepEqual(keys(view), keys(overlay));
  assert.deepEqual(view.edges, []);
  assert.equal(presentLandscape(overlay, { focus, analysis: true, families: [] }).lanes.flatMap((l) => l.nodes).length, graph.nodes.length);
});

test("group inspector refreshes its members when only part of a group is filtered", () => {
  const mixed = { ...graph, edges: [...graph.edges, edge("group-service", proxy.key, focus, "service_service", { dependency_group_id: "core" })] };
  const view = projectVisibleGraph(mixed, { focus, families: ["service_service"] });
  const selection = visibleGraphSelection(view, proxy.key, focus, { dependency_group_id: "core", edges: mixed.edges });
  assert.deepEqual(selection.group.edges.map((e) => e.key), ["group-service"]);
});

test("UI uses the shared projection for layout and inspector fallback", async () => {
  const { readFile } = await import("node:fs/promises");
  const page = await readFile(new URL("../app/knowledge-graph/page.js", import.meta.url), "utf8");
  const landscape = await readFile(new URL("../components/service-landscape.js", import.meta.url), "utf8");
  assert.match(page, /visibleGraphSelection\(visibleGraph, selected, state.focus, group\)/);
  assert.match(page, /group=\{visibleGroup\}/);
  assert.match(page, /GraphInspector key=\{selectedNode\?\.key/);
  assert.doesNotMatch(page, /selectedRecord/);
  assert.match(landscape, /presentLandscape\(graph, \{[^\n]*focus: centerKey, analysis: Boolean\(analysis\)/);
  assert.match(landscape, /for \(const edge of presentation.edges\) if \(edge.dependency_group_id\)/);
});
