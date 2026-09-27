import test from "node:test";
import assert from "node:assert/strict";
import { normalizeOperationalGraph } from "../lib/operational-graph.mjs";
import { dependencyAttention } from "../lib/dependency-attention.mjs";
import { impactGraph } from "./fixtures/dependency-impact.mjs";

test("raw API graph resolves endpoint keys, not provenance source, before Attention renders", () => {
  const raw = structuredClone(impactGraph);
  raw.edges.forEach(edge => { edge.source = "manual"; });
  const normalized = normalizeOperationalGraph(raw);
  const attention = dependencyAttention(normalized);
  assert.equal(attention.unknown, 1);
  assert.equal(attention.ungrouped, 1);
  assert.deepEqual(attention.relationships.map(edge => [edge.source.name, edge.target.name]), [["Home Automation", "Unclassified provider"]]);
  assert.equal(raw.edges[0].source, "manual");
});
test("empty and pending attention data are distinct without undefined name access", () => {
  assert.deepEqual(dependencyAttention(normalizeOperationalGraph({})), { unknown: 0, ungrouped: 0, relationships: [] });
  assert.deepEqual(dependencyAttention(null), { unknown: undefined, ungrouped: undefined, relationships: [] });
});
test("legacy keys and absent effects remain Unknown; dangling/inaccessible endpoints are excluded", () => {
  const legacy = { nodes: [{ id: "s", entity_type: "service", name: "DNS" }, { id: "a", entity_type: "asset", name: "Provider" }, null, {}], edges: [
    { id: "valid", edge_type: "service_asset", source_id: "s", target_id: "a", required_for_operation: false },
    { id: "hidden", edge_type: "service_asset", source_id: "s", target_id: "hidden", failure_effect: "unknown" },
    null, {},
  ] };
  const graph = normalizeOperationalGraph(legacy);
  const result = dependencyAttention(graph);
  assert.equal(graph.nodes.length, 2); assert.equal(graph.edges.length, 1);
  assert.equal(result.unknown, 1); assert.equal(result.ungrouped, 1);
  assert.equal(result.relationships[0].target.name, "Provider");
  assert.equal(result.relationships[0].source.entity_id, "s");
});
test("classified singleton and multi-member edges do not inflate attention counts", () => {
  const graph = normalizeOperationalGraph(impactGraph);
  const complete = { ...graph, edges: graph.edges.filter(edge => edge.key !== "unknown") };
  assert.deepEqual(dependencyAttention(complete), { unknown: 0, ungrouped: 0, relationships: [] });
});
