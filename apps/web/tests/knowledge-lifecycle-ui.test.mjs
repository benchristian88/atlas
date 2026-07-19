import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

test("discovery runs expose archive filtering and safety-gated deletion", async () => {
  const page = await readFile(new URL("../app/discovery-runs/page.js", import.meta.url), "utf8");

  assert.match(page, /include_archived=\$\{includeArchived\}/);
  assert.match(page, /run\.deletion_safety\?\.allowed/);
  assert.match(page, /Deletion removes unused test evidence/);
  assert.match(page, /Archive instead/);
  assert.doesNotMatch(page, /setInterval|setTimeout/);
});

test("assertion management preserves operational data and requires a retraction reason", async () => {
  const panel = await readFile(new URL("../components/assertions-panel.js", import.meta.url), "utf8");
  const assetPage = await readFile(new URL("../app/assets/[id]/page.js", import.meta.url), "utf8");

  assert.match(panel, /deletion_safety\?\.allowed/);
  assert.match(panel, /Retraction reason \*/);
  assert.match(panel, /does not reverse or alter the current asset/);
  assert.match(panel, /source_name \|\| "Unavailable"/);
  assert.match(panel, /JSON\.stringify\(dialog\.assertion\.value_json, null, 2\)/);
  assert.match(assetPage, /current_only=false/);
  assert.match(assetPage, /<AssertionsPanel/);
});

test("assertion table remains contained and reduces columns on narrow screens", async () => {
  const styles = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");

  assert.match(styles, /\.table-scroll, \.responsive-table \{ max-width: 100%; overflow-x: auto; width: 100%; \}/);
  assert.match(styles, /\.table-card \{[^}]*max-width: 100%;[^}]*min-width: 0;/);
  assert.match(styles, /\.assertion-truncate \{[^}]*text-overflow: ellipsis;/);
  assert.match(styles, /\.assertion-source-column, \.assertion-observed-column \{ display: none; \}/);
});
