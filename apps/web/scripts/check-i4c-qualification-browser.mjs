// Production-build UI acceptance using intercepted generic API fixtures.
// This does not qualify a Proxmox source or a live deployment.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
const { chromium } = await import(pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href);
const origin = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3141";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-i4c-fixes/browser";
await mkdir(output, { recursive: true });
const customer = { id: "customer", name: "Acceptance customer" };
const site = { id: "site", customer_id: customer.id, name: "Acceptance site" };
const permissions = ["customers.view", "sites.view", "reconciliation.view", "reconciliation.decide", "integrations.view", "integrations.run"];
const categories = ["newly_discovered", "changed", "no_longer_observed", "contradiction", "possible_duplicate"];
const base = { customer_id: customer.id, site_id: site.id, entity_type: "asset", data_source_id: "source", discovery_run_id: "run", source_name: "Acceptance source", status: "open", created_at: "2026-10-13T00:00:00Z", current_value_json: null, observed_value_json: { value: "fixture" } };
const parent = { ...base, id: "new-entity", entity_name: "joomla-lab", candidate_external_id: "guest/lxc/1006", category: "newly_discovered" };
const fact = { ...parent, id: "initial-fact", category: "changed", assertion_predicate: "inventory.id", initial_entity_item_id: parent.id, observed_value_json: { field: "inventory.id", value: 1006 } };
const later = { ...fact, id: "later-fact", initial_entity_item_id: null, discovery_run_id: "later-run" };
const conflict = { ...fact, id: "conflict", category: "contradiction", initial_entity_item_id: null };
const records = [fact, later, conflict, ...Array.from({ length: 233 }, (_, index) => ({ ...base, id: `item-${index}`, entity_name: `Queue item ${index}`, candidate_external_id: `entity/${index}`, category: categories[index % 5] })), parent];
const integration = { id: "connection", name: "Acceptance connection", generic: true, connector_id: "generic-fixture", connector_version: "1.0.0", customer_id: customer.id, site_id: site.id, site_name: site.name, status: "configured", credential_configured: true, config: {}, enabled: true };
const discoveryRun = { id: "00000000-0000-4000-8000-000000000004", integration_id: "00000000-0000-4000-8000-000000000003",
  source_name: "Proxmox Cluster", customer_id: customer.id, site_id: site.id, status: "completed", completeness_status: "partial",
  is_complete_snapshot: true, coverage_key: "connector:v1:135aab-opaque-qualification-scope", started_at: "2026-10-13T00:00:00Z",
  finished_at: "2026-10-13T00:00:42Z", observation_count: 140, batch_count: 3, warning_count: 1,
  execution_provenance: { connector_id: "proxmox", connector_version: "0.2.0-i4b.2", trigger: "manual", connector_digest: "a".repeat(64) } };
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
const checks = [], errors = [];
try {
  for (const theme of ["light", "dark"]) for (const accent of [null, "#2563EB", "#7C3AED"]) for (const width of (accent ? [1440, 390] : [1440, 1024, 800, 390])) {
    const context = await browser.newContext({ colorScheme: theme, viewport: { width, height: 1000 } });
    const page = await context.newPage(); page.setDefaultTimeout(10000);
    page.on("pageerror", error => errors.push(error.message));
    let diagnostics = [{ capability: "inventory", state: "ready", path_category: "inventory" }];
    await page.route("**/api/**", async route => {
      const request = route.request(), url = new URL(request.url()), path = url.pathname.replace(/^\/api/, "");
      let body = [];
      if (path === "/setup/status") body = { state: "INITIALISED" };
      else if (path === "/auth/me") body = { id: "operator", email: "operator@example.test", display_name: "Acceptance operator", theme_mode: theme, accent_colour: accent, permissions, assignments: [{ scope_type: "global", permissions }] };
      else if (path === "/context") body = { global_access: true, customers: [customer], sites: [site] };
      else if (path === "/reconciliation-items/page") {
        assert.equal(url.searchParams.get("limit"), "50");
        const matching = records.filter(item => item.status === url.searchParams.get("status") && (!url.searchParams.get("category") || item.category === url.searchParams.get("category")));
        const start = Number(url.searchParams.get("cursor") || 0), items = matching.slice(start, start + 50);
        body = { items, total: matching.length, limit: 50, next_cursor: start + 50 < matching.length ? String(start + 50) : null, related_new_entities: items.some(item => item.initial_entity_item_id) ? [parent] : [] };
      } else if (path === "/integration-forms") body = [{ connector_id: "generic-fixture", connection_fields: [], capabilities: {} }];
      else if (path === "/discovery-runs") body = [discoveryRun];
      else if (path === "/integrations/connection") body = integration;
      else if (path === "/integrations/connection/test-connection") body = { success: true, category: "connected", source_version: "9.2.11", compatibility: "untested", capability_diagnostics: diagnostics };
      else if (path === "/system-settings/build-info") body = { version: "0.1.0", release_channel: "beta", install_method: "development" };
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.goto(`${origin}/reconciliation`);
    await page.getByText("50 queue items on this page · 237 matching items", { exact: true }).waitFor();
    const initial = page.getByRole("region", { name: "New entity and initial facts: joomla-lab" });
    await initial.getByRole("heading", { name: "joomla-lab", exact: true }).waitFor();
    assert.equal(await initial.getByRole("heading", { name: "joomla-lab", exact: true }).evaluate(node => getComputedStyle(node).textTransform), "none", "observed name casing is preserved");
    await initial.getByText("Initial source fact", { exact: true }).waitFor();
    assert.equal(await initial.getByRole("button", { name: "Accept", exact: true }).count(), 2);
    await page.locator('[aria-labelledby="reconciliation-later-fact"]').getByText("changed", { exact: true }).waitFor();
    await page.locator('[aria-labelledby="reconciliation-conflict"]').getByText("contradiction", { exact: true }).waitFor();
    const paging = page.getByRole("navigation", { name: "Reconciliation pages" });
    assert.equal(await paging.getByRole("button", { name: "Previous" }).isDisabled(), true);
    await paging.getByRole("button", { name: "Next" }).focus();
    assert.equal(await page.evaluate(() => document.activeElement.textContent), "Next");
    const overflow = await page.evaluate(() => [...document.querySelectorAll("main *")]
      .filter(element => element.getBoundingClientRect().right > innerWidth + 1)
      .slice(-12).map(element => ({ tag: element.tagName, className: element.className, right: element.getBoundingClientRect().right, minWidth: getComputedStyle(element).minWidth })));
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `no reconciliation overflow: ${JSON.stringify(overflow)}`);
    if (!accent) {
      await initial.screenshot({ path: `${output}/initial-facts-${theme}-${width}.png` });
      await paging.screenshot({ path: `${output}/paging-${theme}-${width}.png` });
    }
    await page.screenshot({ path: `${output}/reconciliation-${theme}-${width}-${accent || "default"}.png`, fullPage: true });
    for (let number = 2; number <= 5; number++) {
      await page.getByRole("navigation", { name: "Reconciliation pages" }).getByRole("button", { name: "Next" }).click();
      await page.getByText(`Page ${number}`, { exact: true }).waitFor();
    }
    await page.getByText("37 queue items on this page · 237 matching items", { exact: true }).waitFor();
    assert.equal(await page.getByRole("navigation", { name: "Reconciliation pages" }).getByRole("button", { name: "Next" }).isDisabled(), true);
    await page.getByRole("navigation", { name: "Reconciliation pages" }).getByRole("button", { name: "Previous" }).click();
    await page.getByText("Page 4", { exact: true }).waitFor();
    // A category link resets the cursor; the initial fact keeps entity context.
    await page.getByRole("tab", { name: "Changed", exact: true }).click();
    await page.getByText("49 queue items on this page · 49 matching items", { exact: true }).waitFor();
    assert.equal(await page.getByRole("navigation", { name: "Reconciliation pages" }).count(), 0);
    await page.getByText("Initial source fact", { exact: true }).waitFor();
    await page.goto(`${origin}/discovery-runs`);
    const discoveryTable = page.getByRole("table");
    await discoveryTable.getByRole("link", { name: "Proxmox Cluster", exact: true }).waitFor();
    await discoveryTable.getByText("Full scope", { exact: true }).waitFor();
    await discoveryTable.getByRole("group", { name: "Run status", exact: true }).getByText("Completed", { exact: true }).waitFor();
    await discoveryTable.getByRole("group", { name: "Completeness", exact: true }).getByText("Partial", { exact: true }).waitFor();
    const rowText = await discoveryTable.locator("tbody").innerText();
    for (const hidden of [discoveryRun.id, discoveryRun.integration_id, discoveryRun.coverage_key, discoveryRun.execution_provenance.connector_digest]) assert.equal(rowText.includes(hidden), false);
    assert.ok(rowText.includes("Proxmox · 0.2.0-i4b.2") && rowText.includes("Manual"));
    const connectorLines = await discoveryTable.locator("tbody tr td").nth(1).locator(".table-cell-identity").evaluate(node => {
      const [primary, secondary] = [...node.children].map(child => child.getBoundingClientRect());
      return secondary.top - primary.bottom;
    });
    assert.ok(connectorLines >= 3.9, "connector and trigger have an explicit line gap");
    const statusLines = await discoveryTable.locator("tbody tr td").nth(2).locator(".table-cell-identity").evaluate(node => {
      const [status, completeness] = [...node.children].map(child => child.getBoundingClientRect());
      return completeness.top - status.bottom;
    });
    assert.ok(statusLines >= 3.9, "status and completeness have an explicit line gap");
    await page.getByRole("region", { name: "Discovery runs table", exact: true }).focus();
    assert.equal(await page.evaluate(() => document.activeElement.getAttribute("aria-label")), "Discovery runs table");
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), "no Discovery page overflow");
    if (!accent) await page.screenshot({ path: `${output}/discovery-${theme}-${width}.png`, fullPage: true });
    await page.goto(`${origin}/integrations/connection`);
    await page.getByRole("button", { name: "Test Connection", exact: true }).click();
    await page.getByRole("region", { name: "Capability diagnostics" }).getByText("Ready", { exact: true }).waitFor();
    diagnostics = [{ capability: "inventory.records", state: "permission_limited", path_category: "authorization", privilege: "Inventory.Audit" }, { capability: "topology", state: "source_unavailable", path_category: "topology" }];
    await page.getByRole("button", { name: "Test Connection", exact: true }).click();
    await page.getByText("Limited", { exact: true }).waitFor();
    await page.getByText("Inventory.Audit", { exact: true }).waitFor();
    await page.getByRole("region", { name: "Capability diagnostics" }).getByText("Unavailable", { exact: true }).waitFor();
    await page.screenshot({ path: `${output}/diagnostics-${theme}-${width}-${accent || "default"}.png`, fullPage: true });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), "no horizontal page overflow");
    diagnostics = [{ capability: "/raw/acl/path", state: "ready", path_category: "inventory", raw: "unsafe-sentinel" }];
    await page.getByRole("button", { name: "Test Connection", exact: true }).click();
    await page.waitForFunction(() => !document.querySelector('[aria-label="Capability diagnostics"]'));
    assert.equal(await page.getByText("unsafe-sentinel", { exact: true }).count(), 0);
    diagnostics = undefined;
    await page.getByRole("button", { name: "Test Connection", exact: true }).click();
    await page.getByText("Connection authenticated successfully.", { exact: true }).waitFor();
    checks.push({ theme, accent, width, pagination: "237 items / five pages", discovery: "friendly source / separate lines / structured scope / distinct status and completeness", diagnostics: "ready/limited/unavailable/malformed/absent" });
    await context.close();
  }
  assert.deepEqual(errors, []);
  await writeFile(`${output}/acceptance.json`, JSON.stringify({ checks, errors }, null, 2));
  console.log(`${checks.length} production-build browser scenarios passed`);
} finally { await browser.close(); }
