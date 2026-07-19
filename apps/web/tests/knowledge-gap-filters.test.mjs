import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import {
  knowledgeGapFiltersHref,
  parseKnowledgeGapFilters,
} from "../lib/knowledge-gap-filters.mjs";

const ASSET_TYPE_ID = "a0877d05-048a-4c8f-a6cf-025e4b9317f5";
const REQUIREMENT_ID = "d5f3c33f-11ee-4e42-9234-0f25c96657bc";
const USER_ID = "7aa91f2c-9d2c-4874-a629-a5031208ba22";

test("knowledge-gap filters compose in the URL and survive parsing", () => {
  const href = knowledgeGapFiltersHref({
    assetTypeId: ASSET_TYPE_ID,
    requirementId: REQUIREMENT_ID,
    severity: "critical",
    requirementLevel: "required",
    status: "open",
    assignedUserId: USER_ID,
    minimumAgeDays: "30",
    offset: 50,
  });

  assert.equal(href, `/knowledge-gaps?asset_type_id=${ASSET_TYPE_ID}&requirement_id=${REQUIREMENT_ID}&severity=critical&requirement_level=required&status=open&assigned_user_id=${USER_ID}&minimum_age_days=30&offset=50`);
  assert.deepEqual(parseKnowledgeGapFilters(new URL(href, "http://atlas.test").searchParams, 25), {
    assetTypeId: ASSET_TYPE_ID,
    requirementId: REQUIREMENT_ID,
    severity: "critical",
    requirementLevel: "required",
    status: "open",
    assignedUserId: USER_ID,
    minimumAgeDays: "30",
    offset: 50,
  });
});

test("invalid values fall back safely and reset returns the canonical page", () => {
  const filters = parseKnowledgeGapFilters(new URLSearchParams("asset_type_id=raw-id&requirement_id=nope&severity=urgent&requirement_level=mandatory&status=missing&assigned_user_id=unknown&minimum_age_days=-2&offset=37"), 25);

  assert.deepEqual(filters, {
    assetTypeId: "",
    requirementId: "",
    severity: "",
    requirementLevel: "",
    status: "",
    assignedUserId: "",
    minimumAgeDays: "",
    offset: 25,
  });
  assert.equal(knowledgeGapFiltersHref({ ...filters, offset: 0 }), "/knowledge-gaps");
});

test("Knowledge Gaps reuses the shared Changes toolbar with URL-backed controls", async () => {
  const [page, changes, toolbar, styles] = await Promise.all([
    readFile(new URL("../app/knowledge-gaps/page.js", import.meta.url), "utf8"),
    readFile(new URL("../app/changes/page.js", import.meta.url), "utf8"),
    readFile(new URL("../components/filter-toolbar.js", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
  ]);

  assert.match(page, /<FilterToolbar/);
  assert.match(changes, /<FilterToolbar/);
  assert.match(toolbar, /filter-toolbar-grid/);
  for (const label of ["Asset type", "Requirement", "Severity", "Requirement level", "Status", "Assigned user", "Minimum age (days)"]) {
    assert.ok(page.includes(`<span>${label}</span>`));
  }
  assert.match(page, /router\.push\(knowledgeGapFiltersHref/);
  assert.match(page, /offset: patch\.offset \?\? 0/);
  assert.match(page, /apiRequest\("\/asset-types\?active_only=true"\)/);
  assert.match(page, /knowledge-requirements/);
  assert.match(page, /apiRequest\("\/users\?limit=500"\)/);
  assert.match(page, /Reset filters/);
  assert.match(page, /No knowledge gaps match the current filters\./);
  assert.doesNotMatch(page, /className="filter-bar"/);
  assert.match(styles, /\.knowledge-gaps-filter-grid \{[^}]*grid-template-columns:/);
  assert.match(styles, /\.changes-filter-grid, \.knowledge-gaps-filter-grid \{[^}]*repeat\(2/);
});
