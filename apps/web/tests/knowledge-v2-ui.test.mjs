import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

test("changes timeline and dashboard use meaningful-change APIs", async () => {
  const changes = await readFile(new URL("../app/changes/page.js", import.meta.url), "utf8");
  const dashboard = await readFile(new URL("../app/dashboard/page.js", import.meta.url), "utf8");
  assert.match(changes, /apiRequest\(`\/changes\?/);
  assert.match(changes, /change_type/);
  assert.match(changes, /Security and access activity remains in Audit/);
  assert.match(dashboard, /\/reconciliation-items\/summary/);
  assert.match(dashboard, /\/changes\?limit=6/);
});

test("discovery UI makes complete snapshot semantics explicit", async () => {
  const simulation = await readFile(new URL("../app/discovery/simulate/page.js", import.meta.url), "utf8");
  assert.match(simulation, /is_complete_snapshot/);
  assert.match(simulation, /coverage_key/);
  assert.match(simulation, /never deleted automatically/);
  assert.match(simulation, /no_longer_observed_count/);
});

test("reconciliation exposes stable queues and absence dispositions", async () => {
  const reconciliation = await readFile(new URL("../app/reconciliation/page.js", import.meta.url), "utf8");
  for (const label of ["All open", "No longer observed", "Deferred", "Resolved", "Exceptions"]) {
    assert.match(reconciliation, new RegExp(label));
  }
  for (const disposition of ["mark_missing", "mark_inactive", "retire", "keep_active", "exception"]) {
    assert.match(reconciliation, new RegExp(disposition));
  }
});

test("asset detail defaults to knowledge summary with history and raw tabs", async () => {
  const asset = await readFile(new URL("../app/assets/[id]/page.js", import.meta.url), "utf8");
  assert.match(asset, /\/fact-history/);
  assert.match(asset, /\/knowledge-summary/);
  assert.match(asset, /\["summary", "Summary"\]/);
  assert.match(asset, /\["history", "History"\]/);
  assert.match(asset, /\["raw", "Raw assertions"\]/);
  assert.match(asset, /Accepted Atlas value/);
  assert.match(asset, /Latest source observations/);
  assert.match(asset, /Unavailable/);
});

test("raw assertions are grouped, collapsed, and filterable by knowledge status", async () => {
  const panel = await readFile(new URL("../components/assertions-panel.js", import.meta.url), "utf8");
  assert.match(panel, /<details className="assertion-group"/);
  assert.match(panel, /\["accepted", "Accepted"\]/);
  assert.match(panel, /\["source-current", "Current from source"\]/);
  assert.match(panel, /\["historical", "Historical"\]/);
  assert.match(panel, /return "Conflicting"/);
  assert.doesNotMatch(panel, /<details[^>]*open/);
});
