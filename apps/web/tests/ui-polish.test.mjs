import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import {
  assetListFiltersHref,
  orderedAssetTypeCounts,
  parseAssetListFilters,
} from "../lib/asset-list-filters.mjs";
import {
  changeFiltersHref,
  parseChangeFilters,
} from "../lib/change-filters.mjs";

test("Changes filters have canonical query state and safe invalid fallbacks", () => {
  const parsed = parseChangeFilters(new URLSearchParams("period=90&change_type=fact_changed&entity_type=asset&attention=true&search=docker&offset=61"), 30);
  assert.deepEqual(parsed, {
    period: "90",
    changeType: "fact_changed",
    entityType: "asset",
    source: "",
    attentionOnly: true,
    search: "docker",
    offset: 60,
  });
  assert.equal(changeFiltersHref(parsed), "/changes?period=90&change_type=fact_changed&entity_type=asset&attention=true&search=docker&offset=60");
  const invalid = parseChangeFilters(new URLSearchParams("period=never&change_type=nope&entity_type=nope&source=nope&offset=-1"), 30);
  assert.equal(changeFiltersHref(invalid), "/changes");
});

test("Changes uses a compact grouped shared timeline and complete action metadata", async () => {
  const page = await readFile(new URL("../app/changes/page.js", import.meta.url), "utf8");
  const styles = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.match(page, /groupChanges/);
  assert.match(page, /<TimelineEvent/);
  assert.match(page, /actor_display_name/);
  assert.match(page, /truth_classification/);
  assert.match(page, /Review reconciliation/);
  assert.match(page, /Open discovery run/);
  assert.match(page, /Reset filters/);
  assert.match(styles, /\.filter-toolbar/);
  assert.match(styles, /\.change-timeline-list/);
  assert.match(styles, /word-break: break-word/);
});

test("Asset Type counts are ordered deterministically and filters compose in the URL", () => {
  const ordered = orderedAssetTypeCounts({ by_asset_type: [
    { asset_type_id: "3", asset_type_name: "Switch", count: 2 },
    { asset_type_id: "2", asset_type_name: "Container", count: 4 },
    { asset_type_id: "1", asset_type_name: "Application", count: 4 },
    { asset_type_id: "4", asset_type_name: "Unused", count: 0 },
  ] });
  assert.deepEqual(ordered.map((item) => item.asset_type_name), ["Application", "Container", "Switch"]);

  const typeId = "a0877d05-048a-4c8f-a6cf-025e4b9317f5";
  const href = assetListFiltersHref({ assetTypeId: typeId, completeness: "incomplete", search: "docker", offset: 30 });
  assert.equal(href, `/assets?asset_type_id=${typeId}&completeness=incomplete&search=docker&offset=30`);
  assert.deepEqual(parseAssetListFilters(new URL(href, "http://atlas.test").searchParams, 30), {
    assetTypeId: typeId,
    categoryId: "",
    completeness: "incomplete",
    search: "docker",
    offset: 30,
  });
});

test("Assets exposes ten direct selectors, accessible More, and scoped summary data", async () => {
  const [page, topology, styles] = await Promise.all([
    readFile(new URL("../app/assets/page.js", import.meta.url), "utf8"),
    readFile(new URL("../app/topology/page.js", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
  ]);
  assert.match(page, /apiRequest\("\/assets\/summary"\)/);
  assert.match(page, /typeCounts\.slice\(0, 10\)/);
  assert.match(page, /typeCounts\.slice\(10\)/);
  assert.match(page, /aria-pressed/);
  assert.match(page, /aria-label="More asset types"/);
  assert.match(page, /No assets match the current filters\./);
  assert.match(page, /Clear filters/);
  assert.match(page, /asset-type-filter selector-control-text/);
  assert.match(page, /<select aria-label="More asset types" className="selector-control-text"/);
  assert.match(topology, /button selector-control-text/);
  assert.match(styles, /\.selector-control-text \{[^}]*font-size: 13px;[^}]*font-weight: 650;[^}]*line-height: normal;/);
  assert.match(styles, /\.asset-type-filter \{[^}]*min-height: 36px;/);
});

test("System navigation retires Administration while preserving deep links", async () => {
  const navigation = await readFile(new URL("../lib/system-navigation.mjs", import.meta.url), "utf8");
  const landing = await readFile(new URL("../app/admin/page.js", import.meta.url), "utf8");
  assert.doesNotMatch(navigation, /id: "administration"/);
  assert.match(navigation, /href: "\/admin\/system-settings"/);
  assert.match(landing, /router\.replace\(destination\)/);
  assert.doesNotMatch(landing, /Open section/);
});
