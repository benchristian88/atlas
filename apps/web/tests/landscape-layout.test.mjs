import test from "node:test";
import assert from "node:assert/strict";
import { presentLandscape } from "../lib/operations-experience.mjs";
import { layoutLandscape, landscapeEdgePath } from "../lib/landscape-layout.mjs";
import { dependencyGroupLabel, dependencyDetail, availableDependencyName, singletonImpactRequest } from "../lib/dependency-semantics.mjs";
import { impactGraph } from "./fixtures/dependency-impact.mjs";

const uuid = "6ad9f820-4884-47b9-b6f5-123456789012";
test("historical generated names have domain labels while authored names remain intact", () => {
  for (const name of [`Providers ${uuid}`, `Dependency asset ${uuid}`, `Dependency service ${uuid}`, uuid]) {
    assert.equal(dependencyGroupLabel({ name }, "DNS"), "DNS Providers");
    assert.doesNotMatch(dependencyDetail({ dependency_group_name: name, source: { name: "DNS" }, dependency_requirement: "required", failure_effect: "unavailable", dependency_strategy: "all" }), /6ad9f820|Dependency asset|Dependency service/);
  }
  assert.equal(dependencyGroupLabel({ name: "DNS HA" }, "DNS"), "DNS HA");
  assert.equal(dependencyGroupLabel({ name: "Dependency service Storage" }, "DNS"), "Dependency service Storage");
  assert.equal(availableDependencyName("DNS Providers", [{ name: "DNS Providers" }, { name: "DNS Providers (2)" }]), "DNS Providers (3)");
  const request = singletonImpactRequest(uuid, { id: uuid, name: "AdGuard", required_for_operation: true }, "asset", null, { failure_effect: "unavailable" }, { serviceName: "DNS", groups: [] });
  assert.equal(request.body.name, "DNS — AdGuard");
});
test("dense layout clusters group members, preserves edges and avoids card/group collisions", () => {
  const presentation = presentLandscape(impactGraph, { expanded: ["service", "asset", "business_function"] });
  const snapshot = structuredClone(presentation);
  for (const width of [390, 900, 1440]) {
    const layout = layoutLandscape(presentation, width);
    assert.equal(layout.positions.size, impactGraph.nodes.length);
    assert.equal(layout.groups.length, 2);
    const boxes = [...layout.positions.values()].map(p => ({ ...p, width: layout.nodeWidth, height: layout.nodeHeight })).concat(layout.groups);
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j];
      assert.ok(a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y, `overlap ${a.node?.name || a.key} / ${b.node?.name || b.key}`);
    }
    const adguard1 = layout.positions.get("asset:adguard1"), adguard2 = layout.positions.get("asset:adguard2");
    assert.equal(Math.abs(adguard1.y - adguard2.y), layout.nodeHeight + 30);
    assert.ok(layout.height < 1000);
    const path = landscapeEdgePath(layout.positions.get("service:proxy"), layout.positions.get("service:dns"), layout);
    assert.ok(!path.includes("NaN"));
    assert.deepEqual(layout, layoutLandscape(presentation, width));
  }
  assert.deepEqual(presentation, snapshot);
});

test("realistic Overview/depth-2 fixture reduces between-lane inversions versus alphabetical placement", async () => {
  const { refinementGraph } = await import("./fixtures/dependency-refinement.mjs");
  const presentation = presentLandscape(refinementGraph, { expanded: ["service", "asset", "business_function"] });
  const layout = layoutLandscape(presentation, 1100);
  assert.equal(presentation.lanes[0].nodes.length, 2);
  assert.equal(presentation.lanes[1].nodes.length, 5);
  const alphaRank = new Map(presentation.lanes.flatMap(lane => lane.nodes.map((node, i) => [node.key, i])));
  const dependencyEdges = presentation.edges.filter(edge => edge.edge_family === "service_asset");
  const inversions = rank => dependencyEdges.reduce((sum, a, i) => sum + dependencyEdges.slice(i + 1).filter(b => (rank(a.source_key) - rank(b.source_key)) * (rank(a.target_key) - rank(b.target_key)) < 0).length, 0);
  assert.ok(inversions(key => layout.positions.get(key).y) < inversions(key => alphaRank.get(key)));
  assert.equal(layout.positions.size, refinementGraph.nodes.length);
});
