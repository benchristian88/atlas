// Production-build browser acceptance with intercepted deterministic API state.
// This verifies UI behavior; backend/runtime/live deployment proofs are separate.
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const origin = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3137";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-i2-browser";
await mkdir(output, { recursive: true });
const manifest = JSON.parse(await readFile(new URL("../../api/app/integration_bootstrap/manifests/proxmox.json", import.meta.url)));
const form = { connector_id: manifest.id, version: manifest.version, name: manifest.display.name, connection_fields: manifest.connection_fields, discovery_scopes: [], capabilities: manifest.capabilities };
const customer = { id: "00000000-0000-4000-8000-000000000001", name: "Home lab" };
const site = { id: "00000000-0000-4000-8000-000000000002", customer_id: customer.id, name: "Home" };
const permissions = ["integrations.view", "integrations.manage", "integrations.run", "integration_runtime.view", "integration_runtime.manage", "customers.view", "sites.view", "asset_types.view", "relationship_types.view"];
const baseRecord = { id: "00000000-0000-4000-8000-000000000004", generic: true, name: "Home connection", connector_id: "proxmox", connector_version: "0.1.0", customer_id: customer.id, site_id: site.id, customer_name: customer.name, site_name: site.name, status: "configured", enabled: true, credential_configured: true, configured_fields: ["token_id", "token_secret"], config: { endpoint: "https://192.168.1.2:8006", tls_policy: "verify" }, selected_scopes: [], source_compatibility: "untested", source_version: "8.4" };
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
const checks = [], errors = [];
try {
  for (const theme of ["light", "dark"]) for (const accent of [null, "#2563EB", "#7C3AED"]) for (const width of [1440, 390]) {
    const context = await browser.newContext({ colorScheme: theme });
    const page = await context.newPage(); page.setDefaultTimeout(15000);
    page.on("pageerror", error => errors.push(error.message));
    let record = structuredClone(baseRecord), viewer = false, category = "connected", saved = false;
    const secret = randomBytes(24).toString("hex"), tokenId = `fixture_${randomBytes(8).toString("hex")}@pve!probe`;
    await page.route("**/api/**", async route => {
      const request = route.request(), path = new URL(request.url()).pathname.replace(/^\/api/, "");
      const allowed = viewer ? ["integrations.view", "customers.view", "sites.view"] : permissions;
      let body = [], status = 200;
      if (path === "/setup/status") body = { state: "INITIALISED" };
      else if (path === "/auth/me") body = { id: "00000000-0000-4000-8000-000000000090", email: "operator@example.test", display_name: "Acceptance operator", theme_mode: theme, accent_colour: accent, permissions: allowed, assignments: [{ scope_type: viewer ? "site" : "global", customer_id: customer.id, site_id: site.id, permissions: allowed, role_name: viewer ? "Viewer" : "Administrator" }] };
      else if (path === "/context") body = { global_access: !viewer, customers: [customer], sites: [site] };
      else if (path === "/integration-forms") body = [form];
      else if (path === "/integration-runtime") body = { status: "healthy", capabilities: { operations: ["test_connection"] }, installed_connector_count: 1 };
      else if (path === "/integration-catalogue") body = { entries: [] };
      else if (path === "/integrations" && request.method() === "GET") body = saved ? [record] : [];
      else if (path.endsWith("/test-connection")) { await new Promise(resolve => setTimeout(resolve, 300)); body = { success: category === "connected", category, source_version: category === "connected" ? "8.4" : null, compatibility: category === "connected" ? "untested" : "unknown" }; }
      else if (path === "/integrations" && request.method() === "POST") {
        const submitted = request.postDataJSON();
        assert.equal(Object.hasOwn(submitted.config, "token_secret"), false);
        assert.deepEqual(Object.keys(submitted.credentials).sort(), ["token_id", "token_secret"]);
        saved = true; body = record;
      } else if (path.endsWith("/credentials")) {
        if (request.method() === "DELETE") { record.credential_configured = false; record.configured_fields = []; record.status = "unconfigured"; record.source_version = record.source_compatibility = null; }
        else { assert.deepEqual(Object.keys(request.postDataJSON().values).sort(), ["token_id", "token_secret"]); record.credential_configured = true; record.configured_fields = ["token_id", "token_secret"]; }
        body = record;
      } else if (path === `/integrations/${record.id}`) {
        if (request.method() === "PATCH") { const update = request.postDataJSON(); assert.equal(Object.hasOwn(update, "credentials"), false); record = { ...record, ...update }; }
        body = record;
      } else if (path.startsWith("/connector-mappings/")) body = { connector_id: "fixture", version: "1.0.0", mappings: [{ source_key: "fixture.host", label: "Host", kind: "asset", required: true, resolved: false, ignored: false, target_key: null }] };
      else if (path === "/asset-types") body = [{ id: customer.id, key: "server", name: "Server", active: true }];
      else if (path === "/system-settings/build-info") body = { version: "0.1.0", release_channel: "beta", install_method: "development" };
      assert.equal(JSON.stringify(body).includes(secret), false);
      assert.equal(JSON.stringify(body).includes(tokenId), false);
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.setViewportSize({ width, height: 1000 });
    // Start on the query-selected page and use real Next links throughout.
    // The Configured link must replace the previous tab query explicitly.
    await page.goto(`${origin}/integrations?tab=catalogue`);
    const tabs = page.getByRole("navigation", { name: "Integration views" });
    for (const [label, tab] of [["Configured", "configured"], ["Catalogue", "catalogue"], ["Runtime", "runtime"], ["Configured", "configured"]]) {
      await tabs.getByRole("link", { name: label, exact: true }).click();
      await page.waitForURL(url => url.pathname === "/integrations" && url.searchParams.get("tab") === tab);
      if (tab === "configured") await page.getByText("No configured integrations", { exact: true }).waitFor();
      else await page.getByRole("heading", { name: tab === "catalogue" ? "Connector catalogue" : "Integration runtime", exact: true }).waitFor();
      assert.equal(await tabs.getByRole("link", { name: label, exact: true }).getAttribute("aria-current"), "page");
    }
    await page.goto(`${origin}/integrations`);
    await page.getByText("No configured integrations", { exact: true }).waitFor();
    if (!accent) await page.screenshot({ path: `${output}/configured-${theme}-${width}.png`, fullPage: true });
    await page.getByRole("link", { name: "Add integration", exact: true }).click();
    await page.getByLabel("Connector", { exact: true }).selectOption("proxmox");
    await page.getByLabel("Customer", { exact: true }).selectOption(customer.id);
    await page.getByLabel("Site", { exact: true }).selectOption(site.id);
    await page.getByLabel("Integration name").fill("Home connection");
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    await page.getByLabel("HTTPS endpoint").fill(record.config.endpoint);
    assert.equal(await page.getByLabel(/API token secret/).inputValue(), "");
    if (!accent && !saved) await page.screenshot({ path: `${output}/form-${theme}-${width}.png`, fullPage: true });
    await page.getByLabel(/API token ID/).fill(tokenId);
    await page.getByLabel(/API token secret/).fill(secret);
    await page.getByLabel("TLS policy").selectOption("fingerprint");
    await page.getByLabel("SHA-256 certificate fingerprint").fill("a".repeat(64));
    await page.getByLabel("TLS policy").selectOption("insecure");
    await page.getByText(/Advanced TLS exception/).waitFor();
    await page.getByLabel("TLS policy").selectOption("verify");
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    for (category of ["connected", "authentication_failed", "tls_trust_required", "runtime_unavailable"]) {
      await page.getByRole("button", { name: "Test Connection", exact: true }).click();
      await page.getByRole("button", { name: "Test Connection", exact: true }).and(page.locator('[aria-busy="true"]')).waitFor();
      const expected = { connected: "Connection authenticated successfully.", authentication_failed: "The API token was rejected.", tls_trust_required: "Certificate trust could not be verified.", runtime_unavailable: "The local runtime is unavailable." }[category];
      await page.getByRole("status").filter({ hasText: expected }).waitFor();
    }
    await page.getByRole("button", { name: "Review", exact: true }).click();
    assert.equal((await page.locator("main").innerText()).includes(secret), false);
    await page.getByRole("button", { name: "Create integration" }).click();
    await page.getByRole("heading", { name: "Credentials", exact: true }).waitFor();
    assert.equal(await page.locator('input[type="password"]').count(), 0);
    await page.getByRole("button", { name: "Replace credentials" }).click();
    assert.equal(await page.getByLabel(/API token secret/).inputValue(), "");
    await page.getByLabel(/API token ID/).fill(tokenId);
    await page.getByLabel(/API token secret/).fill(secret);
    await page.getByRole("button", { name: "Replace credentials", exact: true }).click();
    await page.getByRole("button", { name: "Clear credentials", exact: true }).waitFor();
    await page.getByRole("button", { name: "Clear credentials", exact: true }).click();
    await page.getByRole("button", { name: "Confirm clear", exact: true }).click();
    await page.getByRole("definition").filter({ hasText: "Not configured" }).first().waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.equal(await page.locator(".page-header h1").evaluate(node => getComputedStyle(node).fontSize), "28px");
    await page.keyboard.press("Tab");
    const focus = page.getByRole("link", { name: "All integrations", exact: true }); await focus.focus();
    assert.equal(await focus.evaluate(node => getComputedStyle(node).outlineStyle), "solid");
    if (!accent) await page.screenshot({ path: `${output}/detail-${theme}-${width}.png`, fullPage: true });
    await page.goto(`${origin}/integrations/mappings/fixture?version=1.0.0`);
    await page.getByRole("heading", { name: "Connector mappings", exact: true }).waitFor();
    await page.getByRole("cell", { name: "Unresolved", exact: true }).waitFor();
    assert.equal(await page.getByLabel("Map Host").count(), 1);
    if (!accent) await page.screenshot({ path: `${output}/mappings-${theme}-${width}.png`, fullPage: true });
    viewer = true;
    await page.goto(`${origin}/integrations/${record.id}`);
    await page.getByRole("heading", { name: "Home connection" }).waitFor();
    assert.equal(await page.getByRole("button", { name: "Replace credentials", exact: true }).count(), 0);
    assert.equal(await page.getByRole("button", { name: "Test Connection", exact: true }).count(), 0);
    await page.goto(`${origin}/integrations/mappings/fixture`);
    assert.equal(await page.getByLabel("Map Host").count(), 0);
    await page.goto(`${origin}/integrations?tab=runtime`);
    await page.getByRole("table", { name: "Configured integrations", exact: true }).waitFor();
    assert.equal(await tabs.getByRole("link", { name: "Runtime", exact: true }).count(), 0);
    assert.equal(await tabs.getByRole("link", { name: "Configured", exact: true }).getAttribute("aria-current"), "page");
    checks.push({ theme, accent, width, workflow: "tab-navigation/runtime-permissions/scope/configuration/TLS/probe/review/create/detail/replace/clear/mappings/viewer" });
    await context.close();
    process.stdout.write(`Checked ${theme} ${width} ${accent || "default"}\n`);
  }
  assert.deepEqual(errors, []);
  await writeFile(`${output}/report.json`, JSON.stringify({ result: "passed", productionBuild: true, interceptedApi: true, liveSourceProof: false, checks, errors }, null, 2));
  process.stdout.write(`PASS ${checks.length} complete browser workflows\n`);
} finally { await browser.close(); }
