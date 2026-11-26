// Run against an isolated production build backed by a disposable PostgreSQL
// database seeded with seed_gap_visibility and seed_gap_listing_volume from
// test_knowledge_gap_scope_postgres. Include volume_site and volume_requirement
// (the volume fixture's Site and deferred requirement IDs) in the fixture JSON.
import assert from "node:assert/strict";
import { mkdir, readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE
  ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const origin = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3104";
const output = process.env.ATLAS_BROWSER_OUTPUT;
const fixture = JSON.parse(await readFile(process.env.ATLAS_GAP_BROWSER_FIXTURE, "utf8"));
assert.ok(fixture.volume_site && fixture.volume_requirement, "A PostgreSQL listing-limit fixture is required");
await mkdir(output, { recursive: true });

const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
const drillDown = "/knowledge-gaps?requirement_level=required_or_conditional&status=open_or_deferred";
const requirementCleared = "Requirement filter cleared because it is unavailable in this scope.";
const capNotice = "This list loads up to 500 gaps. Additional records may exist.";

function gapRequest(request, site, params) {
  const url = new URL(request.url());
  return url.pathname === "/api/knowledge-gaps" &&
    request.headers()["x-atlas-customer-id"] === fixture.customer &&
    request.headers()["x-atlas-site-id"] === site &&
    Object.entries(params).every(([key, value]) => url.searchParams.get(key) === value);
}

async function checkRequirementScope(page, panel, filters, inclusion, setSite, count, gap) {
  const requirement = panel.locator('label:has(> span:text-is("Requirement")) select');
  const selected = requirement.locator("option:checked");
  const status = panel.getByLabel("Status");
  const severity = panel.getByLabel("Severity");
  const reset = panel.getByRole("button", { name: "Reset filters" });
  await page.keyboard.press("Escape");
  await setSite(fixture.site);
  await count(5);
  await filters.click();
  await status.selectOption("open");
  await requirement.selectOption({ label: "Shared purpose" });
  await gap("Shared purpose").waitFor();
  const sharedId = await requirement.inputValue();

  const started = Promise.withResolvers();
  const release = Promise.withResolvers();
  await page.route("**/api/knowledge-gaps?*", async (route) => {
    if (!gapRequest(route.request(), fixture.site, {
      include_customer_wide: "false", limit: "500", status: null, requirement_id: null,
    })) return route.continue();
    const response = await route.fetch();
    started.resolve();
    await release.promise;
    await route.fulfill({ response });
  });
  const clearedList = page.waitForRequest((request) => gapRequest(request, fixture.site, {
    include_customer_wide: "false", limit: "500", status: "open", requirement_id: null,
  }));
  await inclusion.uncheck();
  try {
    await started.promise;
    await selected.filter({ hasText: "Selected requirement (checking scope…)" }).waitFor({ state: "attached" });
    assert.equal(await requirement.inputValue(), sharedId);
    assert.equal(new URL(page.url()).searchParams.get("requirement_id"), sharedId);
  } finally {
    release.resolve();
    await page.unrouteAll({ behavior: "wait" });
  }
  await clearedList;
  await page.getByText(requirementCleared).waitFor();
  await gap("Local purpose").waitFor();
  assert.equal(await requirement.inputValue(), "");
  assert.equal(new URL(page.url()).searchParams.get("requirement_id"), null);
  assert.equal(new URL(page.url()).searchParams.get("status"), "open");

  await page.goBack();
  await gap("Shared purpose").waitFor();
  assert.equal(new URL(page.url()).searchParams.get("requirement_id"), sharedId);
  assert.equal(new URL(page.url()).searchParams.get("include_customer_wide"), null);
  await page.goForward();
  await gap("Local purpose").waitFor();
  assert.equal(new URL(page.url()).searchParams.get("requirement_id"), null);
  await page.reload();
  await gap("Local purpose").waitFor();
  await filters.click();
  assert.equal(await inclusion.isChecked(), false);
  assert.equal(await status.inputValue(), "open");
  assert.equal(await selected.textContent(), "All requirements");
  await requirement.selectOption({ label: "Local purpose" });
  const localId = await requirement.inputValue();
  await inclusion.check();
  await gap("Local purpose").waitFor();
  await inclusion.uncheck();
  await gap("Local purpose").waitFor();
  assert.equal(await requirement.inputValue(), localId);
  await severity.selectOption("high");
  await page.getByText("No knowledge gaps match the current filters.").waitFor();
  assert.equal(await requirement.inputValue(), localId);
  await severity.selectOption("");
  await gap("Local purpose").waitFor();

  // Hold one authoritative empty response from another Site until the valid
  // original selection renders again. The late check must leave it intact.
  const siblingStarted = Promise.withResolvers();
  const releaseSibling = Promise.withResolvers();
  await page.route("**/api/knowledge-gaps?*", async (route) => {
    if (!gapRequest(route.request(), fixture.sibling, {
      limit: "1", requirement_id: localId, status: "resolved",
    })) return route.continue();
    const response = await route.fetch();
    assert.deepEqual(await response.json(), []);
    siblingStarted.resolve();
    await releaseSibling.promise;
    await route.fulfill({ response });
  });
  await page.keyboard.press("Escape");
  await setSite(fixture.sibling);
  try {
    await siblingStarted.promise;
    await setSite(fixture.site);
    await gap("Local purpose").waitFor();
  } finally {
    releaseSibling.resolve();
    await page.unrouteAll({ behavior: "wait" });
  }
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  assert.equal(new URL(page.url()).searchParams.get("requirement_id"), localId);
  await setSite(fixture.sibling);
  await gap("Sibling purpose").waitFor();
  assert.equal(new URL(page.url()).searchParams.get("requirement_id"), null);
  await setSite(fixture.site);
  await gap("Local purpose").waitFor();
  await filters.click();
  await inclusion.check();
  await requirement.selectOption({ label: "Shared purpose" });
  await gap("Shared purpose").waitFor();

  // A failed check leaves the selected filter visible and removable.
  await page.route("**/api/knowledge-gaps?*", (route) => gapRequest(route.request(), fixture.site, {
    include_customer_wide: "false", limit: "1", requirement_id: sharedId, status: "superseded",
  }) ? route.fulfill({ status: 503 }) : route.continue());
  await inclusion.uncheck();
  await selected.filter({ hasText: "Selected requirement (unavailable in options)" }).waitFor({ state: "attached" });
  assert.equal(await requirement.inputValue(), sharedId);
  assert.equal(new URL(page.url()).searchParams.get("requirement_id"), sharedId);
  await page.unrouteAll({ behavior: "wait" });
  await reset.click();
  await count(5);
  assert.equal(new URL(page.url()).search, "");
  assert.equal(await inclusion.isChecked(), true);
  assert.equal(await reset.isDisabled(), true);
  console.log("Verified requirement scope reconciliation, history, reset, valid and failed checks, and delayed workspace responses");
}

async function checkListingLimit(page, site, panel, filters, summary, count, gap) {
  await page.goto(`${origin}/knowledge-gaps?include_customer_wide=false`);
  const loaded = page.waitForResponse((response) => gapRequest(response.request(), fixture.volume_site, {
    include_customer_wide: "false", limit: "500", requirement_id: null,
  }));
  await site.selectOption(fixture.volume_site);
  const rows = await (await loaded).json();
  assert.equal(rows.length, 500);
  assert.equal(rows.some((row) => row.requirement_definition_id === fixture.volume_requirement), false);
  const exact = await page.evaluate(async ({ customer, volume_site }) => {
    const response = await fetch("/api/knowledge-gaps/summary", {
      headers: { "X-Atlas-Customer-ID": customer, "X-Atlas-Site-ID": volume_site },
    });
    return response.ok ? (await response.json()).open_knowledge_gap_count : null;
  }, { customer: fixture.customer, volume_site: fixture.volume_site });
  assert.equal(exact, 501);
  await page.getByText(capNotice).waitFor();
  assert.match(await summary.textContent(), /500 knowledge gaps loaded/);
  await page.getByText("1–25 of 500 loaded gaps").waitFor();
  await page.screenshot({ path: `${output}/listing-limit-${page.viewportSize().width}.png` });
  await filters.click();
  const openRows = page.waitForResponse((response) => gapRequest(response.request(), fixture.volume_site, {
    include_customer_wide: "false", limit: "500", status: "open", severity: null,
  }));
  await panel.getByLabel("Status").selectOption("open");
  assert.equal((await (await openRows).json()).length, 500);
  await page.getByRole("button", { name: "Filters (2)" }).waitFor();
  await page.getByText(capNotice).waitFor();
  await page.getByText("1–25 of 500 loaded gaps").waitFor();
  const highRows = page.waitForResponse((response) => gapRequest(response.request(), fixture.volume_site, {
    include_customer_wide: "false", limit: "500", status: "open", severity: "high",
  }));
  await panel.getByLabel("Severity").selectOption("high");
  assert.equal((await (await highRows).json()).length, 499);
  await count(499);
  await page.getByText("1–25 of 499 loaded gaps").waitFor();
  assert.equal(await page.getByText(capNotice).count(), 0);

  // The selected requirement has no match in the 500 supporting rows. An
  // independent scoped lookup preserves it and the filtered list finds it.
  const verification = page.waitForResponse((response) => gapRequest(response.request(), fixture.volume_site, {
    include_customer_wide: "false", limit: "1", requirement_id: fixture.volume_requirement, status: null,
  }));
  await page.goto(`${origin}/knowledge-gaps?include_customer_wide=false&requirement_id=${fixture.volume_requirement}`);
  assert.equal((await (await verification).json()).length, 1);
  await count(1);
  await gap("Volume deferred requirement").waitFor();
  await filters.click();
  const requirement = panel.locator('label:has(> span:text-is("Requirement")) select');
  assert.equal(await requirement.inputValue(), fixture.volume_requirement);
  await panel.getByLabel("Status").selectOption("open");
  await page.getByText("No knowledge gaps match the current filters.").waitFor();
  assert.equal(await requirement.inputValue(), fixture.volume_requirement);
  assert.equal(await page.getByText(capNotice).count(), 0);
  console.log("Verified 499, 500 and 501 matching PostgreSQL rows, capped options, and an empty filtered result");
}

try {
  for (const [width, theme] of [[1440, "light"], [1440, "dark"], [1024, "light"], [800, "dark"], [390, "light"], [390, "dark"]]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme });
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    const errors = [];
    const calls = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (url.pathname === "/api/knowledge-gaps" || url.pathname === "/api/dashboard/summary") {
        calls.push({ path: url.pathname, params: url.searchParams, headers: request.headers() });
      }
    });
    const site = page.getByLabel("Active site");
    const filters = page.getByRole("button", { name: /^Filters/ });
    const panel = page.getByRole("region", { name: "Filters" });
    const inclusion = panel.getByRole("checkbox", { name: "Include customer-wide" });
    const reset = panel.getByRole("button", { name: "Reset filters" });
    const level = panel.getByLabel("Requirement level");
    const summary = page.locator('.timeline-summary[role="status"]');
    const gap = (label) => page.getByRole("heading", { name: label, exact: true });
    async function count(expected) {
      await summary.filter({ hasText: new RegExp(`^${expected} knowledge gap`) }).waitFor();
    }
    async function setSite(id) {
      await site.selectOption(id);
    }

    await page.goto(`${origin}/login`);
    await page.getByLabel("Email", { exact: true }).fill(fixture.login.email);
    await page.getByLabel("Password", { exact: true }).fill(fixture.login.password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.waitForURL("**/dashboard");
    await page.waitForFunction((mode) => document.documentElement.dataset.theme === mode, theme);
    const dashboardResponse = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname === "/api/dashboard/summary" && response.request().headers()["x-atlas-site-id"] === fixture.site;
    });
    // Use reload if workspace resolution already selected this Site.
    if (await site.inputValue() === fixture.site) await page.reload();
    else await setSite(fixture.site);
    const dashboard = await dashboardResponse;
    assert.equal(dashboard.status(), 200);
    assert.equal((await dashboard.json()).open_knowledge_gap_count, 3);
    assert.equal(new URL(dashboard.url()).searchParams.get("include_customer_wide"), "true");
    assert.equal(dashboard.request().headers()["x-atlas-customer-id"], fixture.customer);

    const card = page.locator(".ops-summary-item").filter({ hasText: "Knowledge Gaps" });
    await card.getByText("Required or conditional gaps that are open or deferred").waitFor();
    assert.equal(await card.locator("strong").textContent(), "3");
    assert.equal(await card.getAttribute("href"), drillDown);
    await card.click();
    await page.waitForURL(`**${drillDown}`);
    await count(3);
    for (const label of ["Shared purpose", "Shared support", "Local purpose"]) await gap(label).waitFor();
    for (const label of ["Shared recovery guidance", "Shared exception", "Sibling purpose", "Other purpose"]) {
      assert.equal(await gap(label).count(), 0);
    }
    assert.equal(await filters.textContent(), "Filters (2)");
    const requested = (scope, { level, status, severity } = {}) => calls.some((call) =>
      call.path === "/api/knowledge-gaps" && call.headers["x-atlas-customer-id"] === fixture.customer &&
      call.headers["x-atlas-site-id"] === fixture.site && call.params.get("limit") === "500" &&
      call.params.get("include_customer_wide") === String(scope) &&
      call.params.get("requirement_level") === (level || null) &&
      call.params.get("status") === (status || null) && call.params.get("severity") === (severity || null));
    assert.ok(requested(true, { level: "required_or_conditional", status: "open_or_deferred" }));
    assert.ok(requested(true));

    await filters.focus();
    await page.keyboard.press("Enter");
    await panel.waitFor();
    await page.keyboard.press("Tab");
    assert.equal(await inclusion.evaluate((element) => element === document.activeElement), true);
    assert.equal(await inclusion.isChecked(), true);
    const panelBox = await panel.boundingBox();
    assert.ok(panelBox.x >= 0 && panelBox.x + panelBox.width <= width + 1, JSON.stringify(panelBox));
    assert.ok(panelBox.y >= 0 && panelBox.y + panelBox.height <= 1000 + 1, JSON.stringify(panelBox));
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    if (width === 1440 || width === 390) await page.screenshot({ path: `${output}/filters-${width}-${theme}.png` });

    await level.selectOption("");
    await count(4);
    await gap("Shared recovery guidance").waitFor();
    await panel.getByLabel("Severity").selectOption("high");
    await count(2);
    assert.ok(requested(true, { status: "open_or_deferred", severity: "high" }));
    await panel.getByLabel("Severity").selectOption("");
    await count(4);

    await inclusion.focus();
    await page.keyboard.press("Space");
    await count(1);
    assert.equal(await inclusion.isChecked(), false);
    assert.equal(await filters.textContent(), "Filters (2)");
    assert.equal(new URL(page.url()).searchParams.get("include_customer_wide"), "false");
    assert.ok(requested(false, { status: "open_or_deferred" }));
    assert.ok(requested(false));
    assert.equal(await gap("Shared recovery guidance").count(), 0);
    await page.reload();
    await count(1);
    await filters.click();
    assert.equal(await inclusion.isChecked(), false);
    await inclusion.click();
    await count(4);
    assert.equal(await inclusion.isChecked(), true);
    assert.equal(new URL(page.url()).searchParams.has("include_customer_wide"), false);
    await page.goBack();
    await count(1);
    await page.goForward();
    await count(4);
    await reset.click();
    await count(5);
    assert.equal(new URL(page.url()).search, "");
    assert.equal(await inclusion.isChecked(), true);
    assert.equal(await filters.textContent(), "Filters");
    assert.equal(await reset.isDisabled(), true);
    await level.focus();
    await page.keyboard.press("Escape");
    await panel.waitFor({ state: "hidden" });
    assert.equal(await filters.evaluate((element) => element === document.activeElement), true);
    if (width === 1440 || width === 390) {
      await page.screenshot({ path: `${output}/list-${width}-${theme}.png`, fullPage: true });
    }

    // Delay real sibling-Site responses until after another workspace renders.
    // Distinct list and supporting-data requests are both in flight.
    const started = Promise.withResolvers();
    const release = Promise.withResolvers();
    let delayed = 0;
    await page.route("**/api/knowledge-gaps?*", async (route) => {
      if (route.request().headers()["x-atlas-site-id"] !== fixture.sibling) {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      assert.equal(response.status(), 200);
      if (++delayed === 2) started.resolve();
      await release.promise;
      await route.fulfill({ response });
    });
    await filters.click();
    await panel.getByLabel("Status").selectOption("open");
    await count(3);
    await page.keyboard.press("Escape");
    await setSite(fixture.sibling);
    await started.promise;
    await setSite(fixture.empty_site);
    await count(2);
    const lateList = page.waitForEvent("requestfinished", (request) =>
      request.headers()["x-atlas-site-id"] === fixture.sibling &&
      new URL(request.url()).searchParams.get("status") === "open");
    release.resolve();
    await lateList;
    await page.unrouteAll({ behavior: "wait" });
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.match(await summary.textContent(), /^2 knowledge gaps/);
    assert.equal(await gap("Sibling purpose").count(), 0);

    await filters.click();
    assert.equal(await panel.getByRole("option", { name: "Sibling purpose" }).count(), 0);
    await panel.getByLabel("Severity").selectOption("low");
    await page.getByText("No knowledge gaps match the current filters.").waitFor();
    await reset.click();
    await count(4);
    await inclusion.click();
    await page.getByText("No active knowledge gaps in this scope.").waitFor();
    assert.equal(await gap("Sibling purpose").count(), 0);
    await reset.click();
    await count(4);
    if ((width === 1440 && theme === "light") || (width === 390 && theme === "dark")) {
      await checkRequirementScope(page, panel, filters, inclusion, setSite, count, gap);
      await checkListingLimit(page, site, panel, filters, summary, count, gap);
    }
    assert.deepEqual(errors, []);
    await context.close();
    console.log(`Authenticated Knowledge Gaps passed at ${width}px in ${theme} mode`);
  }
} finally {
  await browser.close();
}
