import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import {
  DASHBOARD_GAPS_HREF,
  countKnowledgeGapFilters,
  knowledgeGapFiltersHref,
  knowledgeGapRequirementRequests,
  knowledgeGapRequestPath,
  parseKnowledgeGapFilters,
  resolveKnowledgeGapRequirement,
} from "../lib/knowledge-gap-filters.mjs";

const ASSET_TYPE_ID = "a0877d05-048a-4c8f-a6cf-025e4b9317f5";
const REQUIREMENT_ID = "d5f3c33f-11ee-4e42-9234-0f25c96657bc";
const USER_ID = "7aa91f2c-9d2c-4874-a629-a5031208ba22";

test("knowledge-gap filters compose in the URL and survive parsing", () => {
  const href = knowledgeGapFiltersHref({
    entityType: "asset",
    assetTypeId: ASSET_TYPE_ID,
    requirementId: REQUIREMENT_ID,
    severity: "critical",
    requirementLevel: "required",
    status: "open",
    assignedUserId: USER_ID,
    minimumAgeDays: "30",
    includeCustomerWide: true,
    offset: 50,
  });

  assert.equal(href, `/knowledge-gaps?entity_type=asset&asset_type_id=${ASSET_TYPE_ID}&requirement_id=${REQUIREMENT_ID}&severity=critical&requirement_level=required&status=open&assigned_user_id=${USER_ID}&minimum_age_days=30&offset=50`);
  assert.deepEqual(parseKnowledgeGapFilters(new URL(href, "http://atlas.test").searchParams, 25), {
    entityType: "asset",
    assetTypeId: ASSET_TYPE_ID,
    requirementId: REQUIREMENT_ID,
    severity: "critical",
    requirementLevel: "required",
    status: "open",
    assignedUserId: USER_ID,
    minimumAgeDays: "30",
    includeCustomerWide: true,
    offset: 50,
  });
});

test("invalid values fall back safely and reset returns the canonical page", () => {
  const filters = parseKnowledgeGapFilters(new URLSearchParams("asset_type_id=raw-id&requirement_id=nope&severity=urgent&requirement_level=mandatory&status=missing&assigned_user_id=unknown&minimum_age_days=-2&offset=37"), 25);

  assert.deepEqual(filters, {
    entityType: "",
    assetTypeId: "",
    requirementId: "",
    severity: "",
    requirementLevel: "",
    status: "",
    assignedUserId: "",
    minimumAgeDays: "",
    includeCustomerWide: true,
    offset: 25,
  });
  assert.equal(knowledgeGapFiltersHref({ ...filters, offset: 0 }), "/knowledge-gaps");
});

test("customer-wide scope defaults on, is sent for list and support data, and persists only when off", () => {
  const defaults = parseKnowledgeGapFilters(new URLSearchParams());
  assert.equal(knowledgeGapRequestPath(defaults), "/knowledge-gaps?limit=500&include_customer_wide=true");
  const siteOnly = { ...defaults, includeCustomerWide: false, minimumAgeDays: "0", status: "open" };
  const url = new URL(knowledgeGapFiltersHref(siteOnly), "http://atlas.test");
  assert.deepEqual(parseKnowledgeGapFilters(url.searchParams), siteOnly);
  assert.equal(countKnowledgeGapFilters(siteOnly), 2);
  assert.equal(knowledgeGapRequestPath(siteOnly), "/knowledge-gaps?status=open&minimum_age_days=0&limit=500&include_customer_wide=false");
  assert.equal(knowledgeGapRequestPath({ includeCustomerWide: siteOnly.includeCustomerWide }), "/knowledge-gaps?limit=500&include_customer_wide=false");
  assert.equal(knowledgeGapFiltersHref(defaults), "/knowledge-gaps");
  assert.equal(countKnowledgeGapFilters(defaults), 0);
});

test("Dashboard drill-down requests the counted levels and statuses and can reveal recommended gaps", () => {
  const filters = parseKnowledgeGapFilters(new URL(DASHBOARD_GAPS_HREF, "http://atlas.test").searchParams);
  assert.equal(countKnowledgeGapFilters(filters), 2);
  assert.equal(knowledgeGapRequestPath(filters), "/knowledge-gaps?requirement_level=required_or_conditional&status=open_or_deferred&limit=500&include_customer_wide=true");
  assert.equal(knowledgeGapRequestPath({ ...filters, requirementLevel: "" }), "/knowledge-gaps?status=open_or_deferred&limit=500&include_customer_wide=true");
});

test("requirement verification requests only the selected requirement and scope, across active and historical gaps", () => {
  const paths = knowledgeGapRequirementRequests(REQUIREMENT_ID, false);
  const params = paths.map((path) => Object.fromEntries(new URL(path, "https://atlas.test").searchParams));
  assert.deepEqual(params, ["", "resolved", "superseded"].map((status) => ({
    requirement_id: REQUIREMENT_ID,
    ...(status ? { status } : {}),
    limit: "1",
    include_customer_wide: "false",
  })));
});

test("requirement verification clears only on confirmed absence", () => {
  const empty = { status: "fulfilled", value: [] };
  const failed = { status: "rejected", reason: new Error("Request failed") };
  const historical = {
    status: "fulfilled",
    value: [{ requirement_definition_id: REQUIREMENT_ID, requirement_name: "Reviewed purpose" }],
  };
  assert.deepEqual(resolveKnowledgeGapRequirement([empty, empty, empty], true), { unavailable: true });
  assert.deepEqual(resolveKnowledgeGapRequirement([empty, empty, empty], false), { unavailable: false });
  assert.deepEqual(resolveKnowledgeGapRequirement([empty, failed, empty], true), { unavailable: false });
  assert.deepEqual(resolveKnowledgeGapRequirement([empty, historical, failed], false), {
    option: { id: REQUIREMENT_ID, name: "Reviewed purpose" },
  });
});

test("Knowledge Gaps reuses the shared Changes toolbar with URL-backed controls", async () => {
  const [page, changes, toolbar, styles] = await Promise.all([
    readFile(new URL("../app/knowledge-gaps/page.js", import.meta.url), "utf8"),
    readFile(new URL("../app/changes/page.js", import.meta.url), "utf8"),
    readFile(new URL("../components/filter-toolbar.js", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
  ]);

  assert.match(page, /<FilterToolbar/);
  assert.match(page, /<FilterPopover/);
  assert.match(changes, /<FilterToolbar/);
  assert.match(toolbar, /filter-toolbar-grid/);
  for (const label of ["Entity type", "Asset type", "Requirement", "Severity", "Requirement level", "Status", "Assigned user", "Minimum age (days)"]) {
    assert.ok(page.includes(`<span>${label}</span>`));
  }
  assert.match(page, /window\.history\.pushState\(null, "", knowledgeGapFiltersHref/);
  assert.match(page, /offset: patch\.offset \?\? 0/);
  assert.match(page, /apiRequest\("\/asset-types\?active_only=true"\)/);
  assert.match(page, /knowledge-requirements/);
  assert.match(page, /apiRequest\("\/users\?limit=500"\)/);
  assert.match(page, /Reset filters/);
  assert.match(page, /No knowledge gaps match the current filters\./);
  assert.match(page, /No active knowledge gaps in this scope\./);
  assert.doesNotMatch(page, /className="filter-bar"/);
  assert.match(styles, /\.knowledge-gaps-filter-grid \{[^}]*grid-template-columns:/);
  assert.match(styles, /\.changes-filter-grid, \.knowledge-gaps-filter-grid \{[^}]*repeat\(2/);
});

test("Knowledge Gap cards emphasize missing information with compact responsive actions", async () => {
  const [page, styles] = await Promise.all([
    readFile(new URL("../app/knowledge-gaps/page.js", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
  ]);

  for (const label of ["entityLabel", "Missing information", "Details", "Dates", "First detected", "Last evaluated", "Next step", "Actions"]) {
    assert.ok(page.includes(label));
  }
  assert.match(page, /function KnowledgeGapCard/);
  assert.match(page, /<StatusBadge status=\{taxonomyLabel\(item\.severity/);
  assert.match(page, /<StatusBadge status=\{taxonomyLabel\(item\.status/);
  assert.match(page, /Provide information/);
  const actionStart = page.indexOf("<footer className=\"knowledge-gap-actions\">");
  const actionMarkup = page.slice(actionStart, page.indexOf("</footer>", actionStart));
  assert.ok(actionMarkup.indexOf("Open {entityLabel.toLowerCase()}") < actionMarkup.indexOf("Provide information"));
  assert.ok(actionMarkup.indexOf("Provide information") < actionMarkup.indexOf("Defer"));
  assert.ok(actionMarkup.indexOf("Defer") < actionMarkup.indexOf("Record exception"));
  assert.match(page, /link unavailable/);
  assert.match(styles, /\.knowledge-gap-action-row \{[^}]*flex-wrap: wrap;/);
  assert.match(styles, /\.knowledge-gap-card-body \{[^}]*minmax\(0, 1\.5fr\)/);
  assert.match(styles, /\.knowledge-gap-missing h3 \{[^}]*overflow-wrap: anywhere;/);
  assert.match(styles, /@media \(max-width: 700px\)[\s\S]*\.knowledge-gap-card-body \{ grid-template-columns: 1fr; \}/);
});
