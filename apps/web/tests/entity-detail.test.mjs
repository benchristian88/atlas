import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { graphHref, parseGraphState } from "../lib/operations-experience.mjs";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("detail navigation round-trips Focus and unavailable analysis without changing semantics", () => {
  const id = "00000000-0000-4000-8000-000000000010";
  for (const type of ["service", "business_function"]) {
    const state = parseGraphState(new URL(graphHref({ focus: `${type}:${id}`, analysis: true }), "https://atlas.test").searchParams);
    assert.equal(state.focus, `${type}:${id}`);
    assert.equal(state.analysis, type === "service");
    assert.equal(state.depth, 1);
  }
});

test("shared detail contract uses existing operational primitives and accessible native disclosure", async () => {
  const source = await read("components/entity-detail.js");
  assert.match(source, /import \{ CompletenessLine, EntityMark, RecordedStatus \}/);
  assert.match(source, /aria-label="Breadcrumb"/);
  assert.match(source, /aria-current="page"/);
  assert.match(source, /<details[^>]+><summary>View all/);
  assert.match(source, /rows.slice\(limit\)/);
  assert.match(source, /aria-label=\{`Open \$\{name\}`\}/);
  assert.match(source, /type === "service" && <span className="entity-recorded-state"/);
});

test("Service detail keeps provenance, recovery, completeness actions and typed mutation routes", async () => {
  const page = await read("app/services/[id]/page.js");
  for (const action of ["AssertionsPanel", "TimelineEvent", "CompletenessPanel compact", "canDefer", "canExcept", "canEvaluate", "recovery_notes", "backup_notes", "runbook_url", "documentation_url", "addAsset", "addService", "addFunction", "addDependencyGroup", "updateDependencyRequirement"]) assert.ok(page.includes(action), action);
  assert.match(page, /dependency\.target_label \|\| "Recorded incoming dependency"/);
  assert.match(page, /dependency\.source_service_id === id/);
  assert.match(page, /Operational consequence unknown/);
  assert.match(page, /If unsatisfied/);
  assert.doesNotMatch(page, /<DependencyAnalysisPanel/);
});

test("Business Function keeps stored criticality and lifecycle distinct from Service status and completeness", async () => {
  const page = await read("app/business-functions/[id]/page.js");
  assert.match(page, /criticality=\{item.criticality_name\}/);
  assert.match(page, /Record lifecycle/);
  assert.match(page, /Completeness is not evaluated for Business Functions/);
  assert.doesNotMatch(page, /state=\{|operational_status|health_score/);
  assert.match(page, /recordContextOptions\(record.customer_id, record.site_id\)/);
  assert.match(page, /metadata\?\.truncated/);
});

test("detail loads discard stale responses and never render a previous route's record", async () => {
  for (const [route, record] of [["services", "service"], ["business-functions", "item"]]) {
    const page = await read(`app/${route}/[id]/page.js`);
    assert.match(page, /version !== loadVersion.current/);
    assert.ok(page.includes(`${record}.id !== id`));
    assert.match(page, /if \(!canView\) return <AccessDenied/);
    assert.match(page, /role="alert"/);
  }
});

test("compact completeness is opt-in and uses the existing accessible meter", async () => {
  const panel = await read("components/completeness-panel.js");
  assert.match(panel, /compact = false/);
  assert.match(panel, /compact \? <CompletenessLine node=\{summary.completeness_status === "not_evaluated" \? null : summary\}/);
  const styles = await read("app/globals.css");
  assert.match(styles, /\.entity-detail-page[^}]+var\(--ops-radius\)/);
  assert.match(styles, /\.entity-detail-page :is\(a, button, summary, select, input, textarea\):focus-visible/);
});
