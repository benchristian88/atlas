import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import { normalizeOperationalGraph } from "../lib/operational-graph.mjs";

test("operational graph normalization preserves namespaced API identity and semantics", () => {
  const graph = normalizeOperationalGraph({
    truncated: true,
    warnings: ["The graph reached the node limit and was truncated."],
    nodes: [
      { key: "service:s1", entity_id: "s1", entity_type: "service", name: "Atlas", href: "/services/s1" },
      { key: "asset:a1", entity_id: "a1", entity_type: "asset", name: "LXC", href: "/assets/a1" },
    ],
    edges: [
      { key: "service_asset:e1", edge_id: "e1", edge_family: "service_asset", source_key: "service:s1", target_key: "asset:a1", label: "Runs on" },
    ],
  });
  assert.equal(graph.edges[0].source.name, "Atlas");
  assert.equal(graph.edges[0].target.name, "LXC");
  assert.equal(graph.edges[0].label, "Runs on");
  assert.equal(graph.truncated, true);
});

test("legacy graph normalization derives typed keys without guessing labels or hrefs", () => {
  const graph = normalizeOperationalGraph({
    nodes: [
      { id: "same-id", entity_type: "service", name: "Service", href: "/services/same-id" },
      { id: "same-id", entity_type: "asset", name: "Asset", href: "/assets/same-id" },
    ],
    edges: [
      { id: "edge-1", edge_type: "service_asset", source_id: "same-id", target_id: "same-id", label: "Runs on" },
    ],
  });
  assert.equal(graph.nodesByKey["service:same-id"].name, "Service");
  assert.equal(graph.nodesByKey["asset:same-id"].name, "Asset");
  assert.equal(graph.edges[0].source_key, "service:same-id");
  assert.equal(graph.edges[0].target_key, "asset:same-id");
  assert.equal(graph.edges[0].label, "Runs on");
});

test("shared graph view exposes truncation and is used by current graph pages", async () => {
  const [view, servicePage, functionPage] = await Promise.all([
    readFile(new URL("../components/operational-graph-view.js", import.meta.url), "utf8"),
    readFile(new URL("../app/services/[id]/page.js", import.meta.url), "utf8"),
    readFile(new URL("../app/business-functions/[id]/page.js", import.meta.url), "utf8"),
  ]);
  assert.match(view, /normalized\.truncated/);
  assert.match(view, /role="status"/);
  assert.match(view, /edge\.label/);
  assert.match(view, /edge\.source\.href/);
  assert.doesNotMatch(view, /confidence|impact|severity/i);
  assert.match(servicePage, /<OperationalGraphView graph=\{graph\}/);
  assert.match(functionPage, /<OperationalGraphView graph=\{graph\}/);
});
