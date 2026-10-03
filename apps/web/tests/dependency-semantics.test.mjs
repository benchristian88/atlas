import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import {
  DEPENDENCY_STRATEGY_LABELS,
  FAILURE_EFFECT_LABELS,
  dependencySemanticsLabels,
} from "../lib/dependency-semantics.mjs";

test("dependency semantics use plain homelab wording and preserve Unknown", () => {
  assert.equal(DEPENDENCY_STRATEGY_LABELS.all, "All required");
  assert.equal(DEPENDENCY_STRATEGY_LABELS.any, "Any one is sufficient");
  assert.equal(FAILURE_EFFECT_LABELS.unknown, "Unknown");
  assert.deepEqual(dependencySemanticsLabels({ required_for_operation: false }), {
    requirement: "Optional",
    strategy: null,
    failureEffect: "Unknown",
  });
});

test("Service detail exposes editable semantics only with dependency management", async () => {
  const page = await readFile(new URL("../components/dependency-impact.js", import.meta.url), "utf8");
  assert.match(page, /Dependency impact/);
  assert.match(page, /Any one is sufficient/);
  assert.match(page, /FAILURE_EFFECT_LABELS/);
  assert.match(page, /Unknown/);
  assert.match(page, /canManage/);
  assert.match(page, /dependency-groups/);
});
