// Run against the local web build with intercepted API responses.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE
  ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const base = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3108";
const id = number => `00000000-0000-4000-8000-${String(number).padStart(12, "0")}`;
const customer = { id: id(1), name: "Homelab", status: "active" };
const site = { id: id(2), customer_id: customer.id, name: "Home", status: "active" };
const emptySite = { ...site, id: id(3), name: "Lab" };
const integration = { id: id(4), customer_id: customer.id, site_id: site.id, name: "Proxmox Cluster" };
const permissions = ["audit.view", "integrations.view"];
const fixture = Array.from({ length: 235 }, (_, index) => ({
  id: id(1000 - index),
  created_at: new Date(Date.UTC(2026, 10, 18, 0, 0, -Math.floor(index / 7))).toISOString(),
  actor_snapshot: index < 3 ? "Fixture reviewer" : "Fixture operator",
  customer_id: customer.id,
  site_id: site.id,
  target_id: id(5),
  target_type: "asset",
  event_type: "asset.updated",
  success: true,
  change_summary: `Fixture event ${index + 1}`,
  metadata: { name: "Recorded asset" },
}));
Object.assign(fixture[210], {
  target_id: integration.id,
  target_type: "integration",
  event_type: "integration.debug_next_run_changed",
  request_id: "fixture-request-211",
  metadata: { enabled: { before: false, after: true } },
});

const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const pageErrors = [];
  const requests = [];
  const nameRequests = [];
  let failNextRequest = false;
  let releaseSecondPage;
  const secondPageReady = new Promise(resolve => { releaseSecondPage = resolve; });
  page.on("pageerror", error => pageErrors.push(error.message));
  await page.route("**/api/**", async route => {
    const { pathname, searchParams } = new URL(route.request().url());
    let json = [];
    if (pathname === "/api/setup/status") {
      json = { state: "INITIALISED", authorized: false };
    } else if (pathname === "/api/auth/me") {
      json = { id: id(99), display_name: "Fixture operator", email: "fixture@example.test",
        permissions, assignments: [{ scope_type: "global", permissions }] };
    } else if (pathname === "/api/context") {
      json = { customers: [customer], sites: [site, emptySite], global_access: true,
        selected_customer_id: customer.id, selected_site_id: site.id };
    } else if (pathname === "/api/audit-events") {
      const query = Object.fromEntries(searchParams);
      requests.push(query);
      if (failNextRequest) {
        failNextRequest = false;
        return route.fulfill({ status: 503, json: { detail: "Fixture audit load unavailable" } });
      }
      const offset = Number(query.offset);
      if (offset === 30) await secondPageReady;
      const matches = fixture.filter(event => event.customer_id === query.customer_id && event.site_id === query.site_id
        && (!query.actor || event.actor_snapshot.includes(query.actor)));
      json = matches.slice(offset, offset + Number(query.limit));
    } else if (pathname === "/api/integrations") {
      nameRequests.push(route.request().headers());
      json = [integration];
    }
    await route.fulfill({ json });
  });

  const table = page.getByRole("region", { name: "Audit events" });
  const pager = page.getByRole("navigation", { name: "Audit log pages" });
  const previous = pager.getByRole("button", { name: "Previous" });
  const next = pager.getByRole("button", { name: "Next" });
  const details = page.getByRole("region", { name: "Audit investigation" });
  const applyFilters = page.getByRole("button", { name: "Apply filters" });
  const empty = page.getByText("No audit events match these filters.");
  async function readPage(offset, count = 30) {
    await pager.getByText(`Events ${offset + 1}–${offset + count}`, { exact: true }).waitFor();
    assert.equal(await table.getByRole("status").innerText(), `${count} events on this page`);
    return table.locator("tbody > tr > td:nth-child(6)").allTextContents();
  }

  await page.goto(`${base}/admin/audit`);
  const seen = await readPage(0);
  assert.equal(await previous.isDisabled(), true);
  await table.getByRole("button", { name: "Expand audit record" }).first().click();
  await details.getByText(fixture[0].change_summary, { exact: true }).waitFor();
  await next.click();
  await table.getByRole("status").filter({ hasText: "Loading audit events…" }).waitFor();
  releaseSecondPage();

  for (let offset = 30; offset < fixture.length; offset += 30) {
    if (offset > 30) await next.click();
    seen.push(...await readPage(offset, Math.min(30, fixture.length - offset)));
    assert.equal(await details.count(), 0);
    if (offset < 210) assert.equal(nameRequests.length, 0);
  }
  assert.deepEqual(seen, fixture.map(event => event.change_summary));
  assert.equal(seen[200], "Fixture event 201");
  assert.equal(await next.isDisabled(), true);
  const integrationRow = table.getByRole("row").filter({ hasText: "Fixture event 211" });
  await integrationRow.getByText(integration.name, { exact: true }).waitFor();
  assert.equal(nameRequests.length, 1);
  assert.equal(nameRequests[0]["x-atlas-site-id"], site.id);
  await integrationRow.getByRole("button", { name: "Expand audit record" }).click();
  const investigation = await details.innerText();
  for (const record of [customer, site, integration]) {
    assert.ok(investigation.includes(`${record.name} (current name)`));
    assert.ok(investigation.includes(record.id));
  }
  assert.ok(investigation.includes("fixture-request-211"));
  assert.equal(await details.getByRole("cell", { name: "false", exact: true }).count(), 1);
  assert.equal(await details.getByRole("cell", { name: "true", exact: true }).count(), 1);

  await page.setViewportSize({ width: 390, height: 844 });
  await pager.scrollIntoViewIfNeeded();
  const bounds = await pager.boundingBox();
  assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= 390);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), 390);
  await previous.click();
  assert.deepEqual(await readPage(180), seen.slice(180, 210));
  assert.equal(await details.count(), 0);
  await next.click();
  assert.deepEqual(await readPage(210, 25), seen.slice(210));
  assert.equal(await details.count(), 0);

  await page.getByLabel("Actor").fill("Fixture reviewer");
  await applyFilters.click();
  await table.getByRole("status").filter({ hasText: "3 events on this page" }).waitFor();
  assert.equal(await pager.count(), 0);
  assert.deepEqual(requests.at(-1), { limit: "31", offset: "0", actor: "Fixture reviewer", customer_id: customer.id, site_id: site.id });

  await page.getByLabel("Actor").fill("No one");
  await applyFilters.click();
  await empty.waitFor();
  assert.equal(await pager.count(), 0);
  await page.getByRole("button", { name: "Clear", exact: true }).click();
  assert.deepEqual(await readPage(0), seen.slice(0, 30));

  failNextRequest = true;
  await next.click();
  await page.getByRole("alert").filter({ hasText: "Fixture audit load unavailable" }).waitFor();
  assert.equal(await empty.count(), 0);
  await page.getByRole("button", { name: "Refresh" }).click();
  await readPage(30);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByLabel("Active site").selectOption(emptySite.id);
  await empty.waitFor();
  assert.equal(requests.at(-1).offset, "0");
  assert.equal(requests.at(-1).site_id, emptySite.id);
  await page.getByLabel("Active site").selectOption(site.id);
  await readPage(0);
  assert.ok(requests.every(query => query.limit === "31"));
  assert.deepEqual(pageErrors, []);
  console.log("Audit Log pagination passed at 1440 px and 390 px, including all 235 events.");
} finally {
  await browser.close();
}
