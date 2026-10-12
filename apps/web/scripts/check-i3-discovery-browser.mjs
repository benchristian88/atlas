// Production build, deterministic intercepted API state; no live source claims.
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const origin = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3137";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-i3-browser";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
const checks = [], errors = [];
const customer = { id: "00000000-0000-4000-8000-000000000001", name: "Home lab" };
const site = { id: "00000000-0000-4000-8000-000000000002", customer_id: customer.id, name: "Home" };
const integrationId = "00000000-0000-4000-8000-000000000003", runId = "00000000-0000-4000-8000-000000000004";
try {
  for (const theme of ["light", "dark"]) for (const accent of [null, "#2563EB", "#7C3AED"]) for (const width of [1440, 1024, 800, 390]) {
    const context = await browser.newContext({ colorScheme: theme });
    const page = await context.newPage(); page.setDefaultTimeout(15000); page.on("pageerror", error => errors.push(error.message));
    let capable = false, viewer = false;
    const unsavedSecret = randomBytes(24).toString("hex");
    let record = { id: integrationId, customer_id: customer.id, site_id: site.id, name: "Acceptance connection", generic: true,
      connector_id: "proxmox", connector_version: "0.1.0", credential_configured: true, configured_fields: ["credential"], enabled: true,
      status: "configured", config: { endpoint: "https://example.test" }, source_compatibility: "untested", source_version: "8.4", schedule_preset: "manual" };
    let run = { id: runId, integration_id: integrationId, customer_id: customer.id, site_id: site.id, source_name: record.name, status: "pending", completeness_status: "unknown",
      started_at: "2026-10-12T00:00:00Z", finished_at: null, dispatch_state: "pending", dispatch_attempts: 0, batch_count: 0, observation_count: 0, warning_count: 0, coverage_key: "fixture:inventory", is_complete_snapshot: true,
      execution_provenance: { connector_id: "i3-fixture", connector_version: "1.0.0", trigger: "manual", runtime_type: "ansible", runtime_version: "0.3.0", baseline_id: "atlas-ansible-i3-v1", baseline_version: "1.1.0", aip_version: "1.0", sdk_version: "1.1.0", connector_digest: "a".repeat(64), baseline_digest: "b".repeat(64) }, summary: {} };
    await page.route("**/api/**", async route => {
      const request = route.request(), path = new URL(request.url()).pathname.replace(/^\/api/, "");
      const permissions = ["integrations.view", "customers.view", "sites.view", ...(!viewer ? ["integrations.run", "integrations.manage"] : [])];
      let body = [];
      if (path === "/setup/status") body = { state: "INITIALISED" };
      else if (path === "/auth/me") body = { id: customer.id, email: "operator@example.test", display_name: "Operator", theme_mode: theme, accent_colour: accent, permissions, assignments: [{ scope_type: "site", customer_id: customer.id, site_id: site.id, permissions, role_name: viewer ? "Viewer" : "Operator" }] };
      else if (path === "/context") body = { global_access: false, customers: [customer], sites: [site] };
      else if (path === "/integration-forms") body = [{ connector_id: record.connector_id, connection_fields: [{ key: "endpoint", label: "Endpoint", type: "url", required: true, secret: false }, { key: "credential", label: "Credential", type: "secret", required: true, secret: true }] }];
      else if (path.endsWith("/run")) { record.current_run_id = runId; record.current_run_status = "pending"; body = run; }
      else if (path.endsWith("/schedule")) { record.schedule_preset = request.postDataJSON().preset; record.next_run_at = "2026-10-13T00:00:00Z"; body = { preset: record.schedule_preset, next_run_at: record.next_run_at }; }
      else if (path.endsWith("/cancel")) { run.status = "cancelled"; record.current_run_id = null; record.current_run_status = null; body = run; }
      else if (path === `/integrations/${integrationId}`) body = { ...record, discovery_capable: capable, scheduling_capable: capable };
      else if (path === "/discovery-runs") body = [run];
      else if (path === `/discovery-runs/${runId}`) body = run;
      else if (path === "/system-settings/build-info") body = { version: "0.1.0", release_channel: "beta", install_method: "development" };
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.setViewportSize({ width, height: 1000 });
    await page.goto(`${origin}/integrations/${integrationId}`);
    await page.getByText("Inventory discovery is unavailable in this Connector version.", { exact: true }).waitFor();
    assert.equal(await page.getByRole("button", { name: "Run Now", exact: true }).count(), 0);
    assert.equal(await page.getByLabel("Discovery schedule").count(), 0);
    assert.equal(await page.getByRole("button", { name: "Test Connection", exact: true }).count(), 1);
    capable = true; record.connector_id = "i3-fixture"; record.connector_version = "1.0.0";
    await page.reload(); await page.getByRole("button", { name: "Run Now", exact: true }).waitFor();
    await page.getByLabel("Endpoint", { exact: true }).fill("https://unsaved.example.test");
    await page.getByLabel("Discovery schedule").selectOption("daily");
    assert.equal(await page.getByLabel("Endpoint", { exact: true }).inputValue(), "https://unsaved.example.test");
    await page.getByRole("button", { name: "Run Now", exact: true }).click();
    await page.getByRole("button", { name: "Cancel run", exact: true }).waitFor();
    assert.equal(await page.getByRole("button", { name: "Run Now", exact: true }).isDisabled(), true);
    await page.getByRole("button", { name: "Replace credentials", exact: true }).click();
    await page.getByLabel(/^Credential/).fill(unsavedSecret);
    run.status = "running"; record.current_run_status = "running";
    await page.getByRole("definition").filter({ hasText: /^running$/ }).waitFor();
    assert.equal(await page.getByLabel(/^Credential/).inputValue(), unsavedSecret);
    assert.equal(await page.getByLabel("Endpoint", { exact: true }).inputValue(), "https://unsaved.example.test");
    await page.getByRole("button", { name: "Cancel replacement", exact: true }).click();
    await page.getByRole("button", { name: "Cancel run", exact: true }).click();
    await page.getByRole("button", { name: "Run Now", exact: true }).and(page.locator(":enabled")).waitFor();
    run = { ...run, status: "completed", completeness_status: "partial", finished_at: "2026-10-12T00:00:42Z", runtime_job_id: site.id, dispatch_state: "settled", dispatch_attempts: 1, batch_count: 2, observation_count: 4, warning_count: 1, summary: { reconciliation_items_created: 3 } };
    await page.getByRole("link", { name: "Run history", exact: true }).click();
    await page.getByRole("link", { name: "View", exact: true }).click();
    await page.getByRole("heading", { name: "Execution", exact: true }).waitFor();
    assert.ok((await page.locator("main").innerText()).includes("42s"));
    await page.getByText("Technical identity", { exact: true }).click();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    if (!accent) await page.screenshot({ path: `${output}/run-${theme}-${width}.png`, fullPage: true });
    run.status = "failed"; run.error_message = "source_unavailable"; record.last_error_code = run.error_message;
    await page.goto(`${origin}/integrations/${integrationId}`); await page.getByText("Discovery: source unavailable", { exact: true }).waitFor();
    const focus = page.getByRole("button", { name: "Run Now", exact: true }); await focus.focus();
    assert.equal(await focus.evaluate(node => getComputedStyle(node).outlineStyle), "solid");
    viewer = true; await page.reload(); await page.getByRole("heading", { name: "Acceptance connection", exact: true }).waitFor();
    assert.equal(await page.getByRole("button", { name: "Run Now", exact: true }).count(), 0);
    assert.equal(await page.getByLabel("Discovery schedule").count(), 0);
    assert.equal((await page.locator("main").innerText()).includes(unsavedSecret), false);
    checks.push({ theme, accent, width }); await context.close();
  }
  assert.deepEqual(errors, []);
  await writeFile(`${output}/result.json`, JSON.stringify({ checks, errors }, null, 2));
  console.log(`I3 production browser acceptance: ${checks.length} theme/accent/width combinations passed.`);
} finally { await browser.close(); }
