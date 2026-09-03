import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import { durationToMinutes, formatDuration, minutesToDuration } from "../lib/duration.mjs";
import { parseServiceListFilters, serviceListFiltersHref } from "../lib/service-list-filters.mjs";

test("Service recovery duration controls preserve exact minute values", () => {
  assert.equal(durationToMinutes("4", "hours"), 240);
  assert.equal(durationToMinutes("2", "days"), 2880);
  assert.equal(durationToMinutes("0", "minutes"), 0);
  assert.deepEqual(minutesToDuration(90), { value: "90", unit: "minutes" });
  assert.equal(formatDuration(2880), "2 days");
});

test("Service filters round-trip through URL state", () => {
  const href = serviceListFiltersHref({ search: "dns", serviceTypeId: "type-1", criticalityLevelId: "", lifecycleStatus: "active", operationalStatus: "", completeness: "critical_gaps", archived: false });
  const parsed = parseServiceListFilters(new URL(`https://atlas.test${href}`).searchParams);
  assert.equal(parsed.search, "dns");
  assert.equal(parsed.serviceTypeId, "type-1");
  assert.equal(parsed.lifecycleStatus, "active");
  assert.equal(parsed.completeness, "critical_gaps");
});

test("C1 pages use selectors, typed dependency APIs, and Service completeness", async () => {
  const detail = await readFile(new URL("../app/services/[id]/page.js", import.meta.url), "utf8");
  const form = await readFile(new URL("../components/service-form.js", import.meta.url), "utf8");
  const businessFunctions = await readFile(new URL("../app/business-functions/page.js", import.meta.url), "utf8");
  assert.match(detail, /service-asset-dependencies/);
  assert.match(detail, /service-dependencies/);
  assert.match(detail, /service-business-functions/);
  assert.match(detail, /entityType="service"/);
  assert.doesNotMatch(detail, /Enter.*UUID/i);
  assert.match(form, /Suggested default|suggested default/);
  assert.match(businessFunctions, /Supporting Services|Business Functions/);
});

test("Dashboard spacing and knowledge-list descriptions use the requested stacked layout", async () => {
  const [dashboard, services, businessFunctions, styles] = await Promise.all([
    readFile(new URL("../app/dashboard/page.js", import.meta.url), "utf8"),
    readFile(new URL("../app/services/page.js", import.meta.url), "utf8"),
    readFile(new URL("../app/business-functions/page.js", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
  ]);

  assert.match(dashboard, /className="summary-grid dashboard-summary-grid"/);
  assert.match(services, /className="table-cell-identity"/);
  assert.match(businessFunctions, /className="table-cell-identity"/);
  assert.match(businessFunctions, /<small className="secondary-text">\{item\.description/);
  assert.match(styles, /\.dashboard-summary-grid \{ margin-bottom: 20px; \}/);
  assert.match(styles, /\.table-cell-identity \{ display: grid; gap: 4px; min-width: 0; \}/);
});
