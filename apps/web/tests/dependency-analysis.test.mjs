import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { ANALYSIS_CLASSIFICATION_LABELS, ANALYSIS_STATE_LABELS, previewUnavailable } from "../lib/dependency-analysis.mjs";

test("Preview unavailable sends the read-only scenario contract and returns API reasons", async () => {
  const response = { results: [{ state: "unknown", reasons: [{ summary: "Consequence unknown" }] }] };
  const result = await previewUnavailable(async (path, options) => {
    assert.equal(path, "/dependency-analysis");
    assert.equal(options.method, "POST");
    assert.deepEqual(JSON.parse(options.body), { focus_type: "asset", focus_id: "asset-id", state: "unavailable" });
    return response;
  }, "asset", "asset-id");
  assert.equal(result, response);
});

test("analysis labels distinguish all supported states and consequence distances", () => {
  assert.deepEqual(ANALYSIS_STATE_LABELS, {
    unavailable: "Unavailable", degraded: "Degraded", unknown: "Unknown", unaffected: "Unaffected by this scenario",
  });
  assert.deepEqual(ANALYSIS_CLASSIFICATION_LABELS, { direct: "Direct consequence", downstream: "Downstream consequence" });
});

test("preview errors are not converted to empty successful results", async () => {
  await assert.rejects(previewUnavailable(async () => { throw new Error("Record not found"); }, "service", "hidden"), /Record not found/);
});

test("panel exposes reasons, paths, empty and truncated states with accessible existing layout", async () => {
  const panel = await readFile(new URL("../components/dependency-analysis-panel.js", import.meta.url), "utf8");
  for (const text of ["Preview unavailable", "Hypothetical scenario", "report live health", "reason.summary", "reason.members", "row.paths", "result.assumption", "result.truncated", "result.warnings", "result.results.length === 0", 'role="alert"', 'aria-live="polite"', 'aria-busy={loading}', 'disabled={loading}', 'className="dependency-list"']) {
    assert.ok(panel.includes(text), text);
  }
  assert.match(panel, /key=\{`\$\{focusType\}:\$\{focusId\}:\$\{customerId\}:\$\{siteId\}`\}/);
  assert.doesNotMatch(panel, /business_function|\.manage|\.edit|live health status|blast radius|severity/i);
});

test("Asset and Service details allow Viewers to preview without manage permission", async () => {
  for (const kind of ["assets", "services"]) {
    const page = await readFile(new URL(`../app/${kind}/[id]/page.js`, import.meta.url), "utf8");
    assert.match(page, /hasPermissionForObject\("service_dependencies.view",[^\n]+<DependencyAnalysisPanel/);
    assert.match(page, new RegExp(`focusType="${kind === "assets" ? "asset" : "service"}"`));
  }
});
