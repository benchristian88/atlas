// Production Chrome, intercepted safe fixtures. This is not live qualification.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const origin = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3137";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-discovery-diagnostics-browser";
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
    let administrator = true, debugRequests = 0;
    const record = { id: integrationId, customer_id: customer.id, site_id: site.id, name: "Diagnostic acceptance", generic: true,
      connector_id: "fixture", connector_version: "1.0.0", credential_configured: true, configured_fields: ["credential"], enabled: true,
      discovery_configured: true, discovery_capable: true, scheduling_capable: true, status: "configured", config: { endpoint: "https://example.test" },
      schedule_preset: "manual", debug_next_run: false };
    const warning = { sequence: 17, stage: "guest_interface", result: "warning", reason_code: "interface_invalid",
      object_class: "fixture.guest", external_id: "guest/1027", parent_external_id: "node/example" };
    const run = { id: runId, integration_id: integrationId, customer_id: customer.id, site_id: site.id, source_name: record.name,
      status: "completed", completeness_status: "partial", started_at: "2026-10-18T00:00:00Z", finished_at: "2026-10-18T00:00:42Z",
      debug_enabled: true, diagnostics_summary: { available: true, counts: { processed: 179, accepted: 178, skipped: 1, warning: 1, error: 0 },
        reasons: [{ reason_code: "interface_invalid", count: 1 }], processing_errors: [] }, diagnostics_events: [warning],
      execution_provenance: { connector_id: "fixture", connector_version: "1.0.0", trigger: "manual", runtime_type: "ansible", runtime_version: "0.3.1" }, summary: {} };
    const trace = { state: "available", expires_at: "2026-10-20T00:00:00Z", events: [{ ...warning, field: "net0", encountered_type: "string", validation_rule: "interface_config" }] };
    await page.route("**/api/**", async route => {
      const request = route.request(), path = new URL(request.url()).pathname.replace(/^\/api/, "");
      const permissions = ["integrations.view", "integrations.run", "integrations.manage", "customers.view", "sites.view"];
      let body = [];
      if (path === "/setup/status") body = { state: "INITIALISED" };
      else if (path === "/auth/me") body = { id: customer.id, email: "operator@example.test", display_name: "Operator", theme_mode: theme, accent_colour: accent,
        permissions: [...permissions, ...(administrator ? ["integration_runtime.manage"] : [])], assignments: [
          { scope_type: "site", customer_id: customer.id, site_id: site.id, permissions, role_name: "Operator" },
          ...(administrator ? [{ scope_type: "global", permissions: ["integration_runtime.manage"], role_name: "Administrator" }] : [])] };
      else if (path === "/context") body = { global_access: false, customers: [customer], sites: [site] };
      else if (path === "/integration-forms") body = [{ connector_id: record.connector_id, connection_fields: [{ key: "endpoint", label: "Endpoint", type: "url", required: true, secret: false }] }];
      else if (path.endsWith("/debug-next-run")) { record.debug_next_run = request.postDataJSON().enabled; body = { debug_next_run: record.debug_next_run }; }
      else if (path.endsWith("/run")) { record.debug_next_run = false; body = run; }
      else if (path === `/integrations/${integrationId}`) body = record;
      else if (path === `/discovery-runs/${runId}/debug-trace`) { debugRequests++; assert.equal(administrator, true); if (request.method() === "DELETE") { trace.state = "deleted"; trace.events = []; } body = trace; }
      else if (path === `/discovery-runs/${runId}`) body = run;
      else if (path === "/system-settings/build-info") body = { version: "0.1.0", release_channel: "beta", install_method: "development" };
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.setViewportSize({ width, height: 1000 });
    await page.goto(`${origin}/integrations/${integrationId}`);
    const arm = page.getByRole("button", { name: "Enable debug for next discovery run", exact: true });
    await arm.waitFor(); await arm.focus();
    assert.equal(await arm.evaluate(node => getComputedStyle(node).outlineStyle), "solid");
    await arm.click(); await page.getByText("Armed", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Run Now", exact: true }).click();
    await page.getByText("Off", { exact: true }).waitFor();
    await page.goto(`${origin}/discovery-runs/${runId}`);
    await page.getByRole("heading", { name: "Diagnostics", exact: true }).waitFor();
    await page.getByText("179", { exact: true }).waitFor();
    assert.equal(debugRequests, 0);
    await page.getByText("Debug trace", { exact: true }).click();
    await page.getByText("Field: net0", { exact: true }).waitFor();
    assert.ok((await page.locator("main").innerText()).includes("Expires"));
    const table = page.getByRole("region", { name: "Debug trace events table", exact: true });
    await table.focus(); assert.equal(await table.evaluate(node => document.activeElement === node), true);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    if (!accent && [1440, 390].includes(width)) await page.screenshot({ path: `${output}/diagnostics-${theme}-${width}.png`, fullPage: true });
    await page.getByRole("button", { name: "Delete debug data", exact: true }).click();
    await page.getByText(/Debug data: deleted/).waitFor();
    assert.equal(await page.getByText("Field: net0", { exact: true }).count(), 0);
    assert.equal(await page.getByRole("heading", { name: "Diagnostics", exact: true }).count(), 1);
    administrator = false; await page.reload();
    await page.getByRole("heading", { name: "Diagnostics", exact: true }).waitFor();
    const requestsBefore = debugRequests;
    assert.equal(await page.getByText("Debug trace", { exact: true }).count(), 0);
    assert.equal(await page.getByText("179", { exact: true }).count(), 1);
    await page.goto(`${origin}/integrations/${integrationId}`);
    await page.getByRole("heading", { name: record.name, exact: true }).waitFor();
    assert.equal(await page.getByRole("button", { name: "Enable debug for next discovery run", exact: true }).count(), 0);
    assert.equal(debugRequests, requestsBefore);
    checks.push({ theme, accent, width }); await context.close();
  }
  assert.deepEqual(errors, []);
  await writeFile(`${output}/result.json`, JSON.stringify({ checks, errors }, null, 2));
  console.log(`Discovery diagnostics production Chrome acceptance: ${checks.length} combinations passed.`);
} finally { await browser.close(); }
