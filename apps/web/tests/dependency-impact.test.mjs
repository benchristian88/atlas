import test from "node:test";
import assert from "node:assert/strict";
import { singletonImpactRequest, dependencyDetail } from "../lib/dependency-semantics.mjs";
import { normalizeOperationalGraph } from "../lib/operational-graph.mjs";
import { presentLandscape } from "../lib/operations-experience.mjs";
import { explainDependencyReason } from "../lib/dependency-analysis.mjs";
import { impactGraph } from "./fixtures/dependency-impact.mjs";

test("classification creates singleton semantics with canonical requirement and stable name", () => {
  for (const kind of ["asset", "service"]) for (const required of [true, false]) {
    const request = singletonImpactRequest("dns", { id: "provider", required_for_operation: required }, kind, null, { failure_effect: "degraded" });
    assert.equal(request.method, "POST");
    assert.equal(request.path, "/services/dns/dependency-groups");
    assert.equal(request.body.requirement, required ? "required" : "optional");
    assert.equal(request.body.failure_effect, "degraded");
    assert.equal(request.body.strategy, "all");
    assert.deepEqual(request.body[`${kind}_dependency_ids`], ["provider"]);
    assert.equal(request.body.name, `Dependency ${kind} provider`);
  }
});
test("existing singleton edit patches only chosen effect, preserving ANY and group requirement", () => {
  assert.deepEqual(singletonImpactRequest("dns", { id: "provider", required_for_operation: true }, "asset", { id: "group", strategy: "any", requirement: "optional" }, { failure_effect: "unavailable" }), { path: "/dependency-groups/group", method: "PATCH", body: { failure_effect: "unavailable" } });
});
test("mixed density fixture preserves singleton semantics, ANY, ALL, unknown and Service edges", () => {
  const graph = normalizeOperationalGraph(impactGraph);
  const sizes = Object.fromEntries(graph.edges.map(edge => [edge.key, edge.presentation_group_size]));
  assert.equal(sizes.home, 1); assert.equal(sizes.control, 1);
  assert.equal(sizes.adguard1, 2); assert.equal(sizes.adguard2, 2);
  assert.equal(sizes.storage, 2); assert.equal(sizes.compute, 2);
  assert.equal(sizes.unknown, undefined);
  const edge = graph.edges.find(e => e.key === "control");
  assert.match(dependencyDetail(edge), /Optional.*Service degraded.*Control plane/);
  assert.equal(edge.dependency_group_id, "control");
  assert.equal(edge.source_key, "service:dns");
  assert.equal(edge.target_key, "asset:atlas");
  const partial = normalizeOperationalGraph({ nodes: graph.nodes, edges: [graph.edges.find(e => e.key === "adguard1")] });
  assert.equal(partial.edges[0].presentation_group_size, 2);
  const shown = presentLandscape(graph, { limit: 2 });
  assert.ok(shown.omittedEdges > 0);
  for (const edge of shown.edges.filter(e => e.dependency_group_id === "ha")) assert.equal(edge.presentation_group_size, 2);
  assert.deepEqual(normalizeOperationalGraph(graph), graph);
});
test("natural explanations follow engine consequences without inventing whole-Service availability", () => {
  const members = [{ entity: { name: "AdGuard Home" }, state: "unavailable" }, { entity: { name: "AdGuard Home 2" }, state: "unaffected" }];
  const reason = { dependency_group_name: "DNS HA", dependency_strategy: "any", dependency_requirement: "required", consequence: "unaffected", satisfaction: "satisfied", members };
  assert.match(explainDependencyReason("DNS", reason), /AdGuard Home 2 can still satisfy DNS HA/);
  assert.doesNotMatch(explainDependencyReason("DNS", reason), /DNS remains available/);
  assert.match(explainDependencyReason("DNS", { ...reason, satisfaction: "unsatisfied", consequence: "degraded", members: members.map(m => ({ ...m, state: "unavailable" })) }), /DNS becomes degraded because none/);
  assert.match(explainDependencyReason("DNS", { ...reason, satisfaction: "unknown", code: "dependency_set_unresolved" }), /cannot determine/);
  assert.match(explainDependencyReason("Home Automation", { ...reason, satisfaction: "unsatisfied", consequence: "unavailable", members: [{ entity: { name: "homeassistant" }, state: "unavailable" }] }), /Home Automation becomes unavailable because homeassistant is unavailable/);
});
