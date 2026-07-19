import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

test("asset detail renders completeness counts, grouped gaps, and reasoned actions", async () => {
  const asset = await readFile(new URL("../app/assets/[id]/page.js", import.meta.url), "utf8");
  const panel = await readFile(new URL("../components/completeness-panel.js", import.meta.url), "utf8");
  assert.match(asset, /\/completeness/);
  assert.match(asset, /CompletenessPanel/);
  for (const label of ["Required", "Conditional", "Recommended", "Exceptions", "Resolved history"]) assert.match(panel, new RegExp(label));
  assert.match(panel, /Re-evaluate/);
  assert.match(panel, /Reason \*/);
});

test("missing knowledge remains a dedicated reconciliation queue", async () => {
  const reconciliation = await readFile(new URL("../app/reconciliation/page.js", import.meta.url), "utf8");
  assert.match(reconciliation, /Missing knowledge/);
  assert.match(reconciliation, /\/knowledge-gaps/);
  assert.match(reconciliation, /Provide information/);
  assert.match(reconciliation, /Record exception/);
});

test("knowledge profile editor uses dynamic reference records and structured rules", async () => {
  const profile = await readFile(new URL("../app/admin/asset-types/[id]/knowledge-profile/page.js", import.meta.url), "utf8");
  assert.match(profile, /apiRequest\("\/asset-types"\)/);
  assert.match(profile, /apiRequest\("\/custom-fields"\)/);
  assert.match(profile, /apiRequest\("\/relationship-types"\)/);
  assert.match(profile, /relationship_type_ids/);
  assert.match(profile, /allowed_target_asset_type_ids/);
  assert.doesNotMatch(profile, /paste.*UUID/i);
});

test("dashboard and asset list consume API-computed completeness summaries", async () => {
  const dashboard = await readFile(new URL("../app/dashboard/page.js", import.meta.url), "utf8");
  const assets = await readFile(new URL("../app/assets/page.js", import.meta.url), "utf8");
  assert.match(dashboard, /open_knowledge_gap_count/);
  assert.match(dashboard, /assets_operationally_complete/);
  assert.match(assets, /has_critical_gaps/);
  assert.match(assets, /has_open_knowledge_gaps/);
  assert.match(assets, /completeness_status/);
});
