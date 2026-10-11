// I1 visual acceptance against the production Next build. Deterministic API
// fixtures exercise unreleased and future verified package states, without
// installing code or creating source connections. Live deployment acceptance
// is recorded separately; this script does not prove runtime networking.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const origin = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3137";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-i1-ui-browser";
await mkdir(output, { recursive: true });
const digest = "a".repeat(64);
const customer = { id: "00000000-0000-4000-8000-000000000001", name: "Home lab" };
const site = { id: "00000000-0000-4000-8000-000000000002", customer_id: customer.id, name: "Home" };
const entries = [
  { connector_id: "atlas.proxmox", name: "Proxmox VE", description: "Cluster, node, VM, container, storage and network inventory.", category: "Virtualisation", icon_key: "server", accent_key: "blue" },
  { connector_id: "atlas.docker", name: "Docker + Compose", description: "Engine, Compose project, container, network and volume inventory.", category: "Containers", icon_key: "application", accent_key: "cyan" },
  { connector_id: "atlas.unifi", name: "UniFi Network", description: "Gateway, switch, access point and network inventory.", category: "Networking", icon_key: "network", accent_key: "purple" },
].map(entry => ({ ...entry, publisher: "Atlas Impact", trust_tier: "atlas_official", version: null, installed_version: null, licence: "Apache-2.0", package_available: false, verification_status: "metadata_only", state: "unavailable", message: "The executable Connector bundle has not been released.", supported_actions: [] }));
const healthy = { status: "healthy", runtime_version: "0.1.0", protocol_version: "1", baseline_id: "atlas-ansible-i1-v1", baseline_digest: digest, packaging_mode: "docker_compose", ansible_core_version: "2.19.0", ansible_runner_version: "2.4.1", last_checked_at: "2026-10-11T00:00:00Z", last_error: null, capabilities: ["health", "verified_package_activation"], installed_connector_count: 0 };
const basePermissions = ["integrations.view", "customers.view", "sites.view", "assets.view", "service_types.view", "system_settings.manage"];
const scenarios = [
  { name: "configured-empty", tab: "configured" },
  { name: "configured-existing", tab: "configured", configured: true },
  { name: "catalogue-offline", tab: "catalogue" },
  { name: "runtime-healthy", tab: "runtime" },
  { name: "runtime-unavailable", tab: "runtime", unavailable: true },
  { name: "catalogue-installable", tab: "catalogue", state: "installable" },
  { name: "catalogue-installed", tab: "catalogue", state: "installed" },
  { name: "catalogue-runtime-update", tab: "catalogue", state: "runtime_update_required" },
  { name: "catalogue-incompatible", tab: "catalogue", state: "incompatible" },
  { name: "catalogue-verification-failed", tab: "catalogue", state: "verification_failed" },
  { name: "catalogue-viewer", tab: "catalogue", state: "installable", viewer: true },
];
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
const errors = [], checks = [], requests = [], actions = [];
try {
  for (const theme of ["light", "dark"]) for (const accent of [null, "#2563EB", "#7C3AED"]) {
    const context = await browser.newContext({ colorScheme: theme });
    const page = await context.newPage(); page.setDefaultTimeout(12000);
    page.on("pageerror", error => errors.push(error.message));
    let scenario = scenarios[0];
    await page.route("**/api/**", async route => {
      const request = route.request(), path = new URL(request.url()).pathname.replace(/^\/api/, "");
      requests.push({ path, method: request.method(), scenario: scenario.name, headers: { customer: request.headers()["x-atlas-customer-id"], site: request.headers()["x-atlas-site-id"] } });
      const permissions = scenario.viewer ? basePermissions.filter(permission => permission !== "system_settings.manage") : [...basePermissions, "integration_runtime.view", "integration_runtime.manage"];
      let body = [], status = 200;
      if (path === "/setup/status") body = { state: "INITIALISED" };
      else if (path === "/auth/me") body = { id: "00000000-0000-4000-8000-000000000090", email: "operator@example.test", display_name: "Acceptance operator", theme_mode: theme, accent_colour: accent, permissions, assignments: [{ scope_type: scenario.viewer ? "site" : "global", customer_id: customer.id, site_id: site.id, permissions, role_name: scenario.viewer ? "Viewer" : "Administrator" }] };
      else if (path === "/context") body = { global_access: !scenario.viewer, customers: [customer], sites: [site] };
      else if (path === "/integrations") body = scenario.configured ? [{ id: "00000000-0000-4000-8000-000000000004", name: "Home Proxmox", connector_id: "atlas.proxmox", customer_name: customer.name, site_name: site.name, status: "pending" }] : [];
      else if (path === "/integration-runtime") body = scenario.unavailable ? { ...healthy, status: "unavailable", last_error: "runtime_unavailable" } : healthy;
      else if (path === "/integration-catalogue") body = { source: "bootstrap", checked_at: "2026-10-11T00:00:00Z", entries: entries.map((entry, index) => index || !scenario.state ? entry : { ...entry, version: "1.0.0", digest, bundle_digest: `sha256:${digest}`, installed_version: scenario.state === "installed" ? "1.0.0" : null, package_available: true, verification_status: scenario.state === "verification_failed" ? "failed" : "verified", state: scenario.state, message: scenario.state === "runtime_update_required" ? "This package requires a newer approved runtime baseline." : scenario.state === "incompatible" ? "This package does not support the runtime protocol." : scenario.state === "verification_failed" ? "Package verification failed; activation is blocked." : "Verified immutable Connector package.", supported_actions: scenario.state === "installable" ? ["install"] : scenario.state === "installed" ? ["remove"] : [] }) };
      else if (path.endsWith("/install") || path.startsWith("/installed-connectors/")) { actions.push({ path, method: request.method(), body: request.postDataJSON() }); body = { status: "installed" }; }
      else if (path === "/system-settings/build-info") body = { version: "0.1.0", release_channel: "beta", install_method: "development" };
      else if (path === "/system-settings/updates") body = { status: "unavailable", current_version: "0.1.0", install_method: "development" };
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    });
    for (const width of [1440, 1024, 800, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      for (scenario of scenarios) {
        const requestStart = requests.length;
        await page.goto(`${origin}/integrations${scenario.tab === "configured" ? "" : `?tab=${scenario.tab}`}`);
        await page.getByRole("heading", { name: "Integrations", exact: true }).waitFor();
        await page.getByRole("navigation", { name: "Integration views" }).waitFor();
        await page.waitForFunction(() => !Array.from(document.querySelectorAll("main [role=status]")).some(node => /Loading|Checking runtime/.test(node.textContent)));
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${scenario.name} ${theme} ${width} overflow`);
        assert.equal(await page.locator(".page-header h1").evaluate(node => getComputedStyle(node).fontSize), "28px");
        const text = await page.locator("main").innerText();
        assert.doesNotMatch(text, /Windmill|Test connection|Run now|Configure Connector|control.secret|localhost|\/var\/lib/i);
        if (scenario.tab === "catalogue") {
          assert.equal(await page.getByRole("heading", { name: "Proxmox VE", exact: true }).count(), 1);
          assert.equal(await page.getByRole("heading", { name: "Docker + Compose", exact: true }).count(), 1);
          assert.equal(await page.getByRole("heading", { name: "UniFi Network", exact: true }).count(), 1);
          assert.match(text, /Atlas official/);
          if (!scenario.state) assert.match(text, /Bundle not released/i);
          if (scenario.state === "runtime_update_required") assert.match(text, /Runtime update required/i);
          if (scenario.state === "incompatible") assert.match(text, /Incompatible/);
          if (scenario.state === "verification_failed") assert.match(text, /Verification failed/i);
          assert.equal(await page.getByRole("button", { name: "Install Connector", exact: true }).count(), scenario.state === "installable" && !scenario.viewer ? 1 : 0);
          assert.equal(await page.getByRole("button", { name: "Remove package", exact: true }).count(), scenario.state === "installed" ? 1 : 0);
          if (scenario.viewer) { assert.equal(await page.getByRole("link", { name: "Runtime", exact: true }).count(), 0); assert.equal(requests.slice(requestStart).some(request => request.path === "/integration-runtime"), false); }
          assert.equal(requests.slice(requestStart).filter(request => ["/integration-catalogue", "/integration-runtime"].includes(request.path)).every(request => !request.headers.customer && !request.headers.site), true);
          if (scenario.state === "installable" && !scenario.viewer && width === 1440 && accent === null && theme === "light") {
            await page.getByRole("button", { name: "Install Connector", exact: true }).click();
            await page.getByRole("status").filter({ hasText: "package activated" }).waitFor();
            assert.deepEqual(actions.at(-1), { path: "/integration-catalogue/atlas.proxmox/install", method: "POST", body: { version: "1.0.0", digest } });
          }
        } else if (scenario.tab === "runtime") {
          assert.match(text, /Atlas Ansible Runtime/);
          if (scenario.unavailable) assert.match(text, /Accepted Atlas knowledge remains available/);
          await page.getByText("Technical details", { exact: true }).click();
          assert.match(await page.locator("main").innerText(), new RegExp(digest));
        } else assert.match(text, scenario.configured ? /Home Proxmox/ : /No configured integrations/);
        const focus = page.locator("main a, main button:not([disabled]), main summary, main input").filter({ visible: true }).first();
        await page.keyboard.press("Tab"); await focus.focus();
        assert.equal(await focus.evaluate(node => getComputedStyle(node).outlineStyle), "solid");
        if (accent === null && [1440, 390].includes(width)) await page.screenshot({ path: `${output}/${scenario.name}-${theme}-${width}.png`, fullPage: true });
        checks.push({ scenario: scenario.name, theme, accent, width });
      }
    }
    // Compare the actual composed shared surfaces with the production System
    // Settings page under the same theme and accent, then retain a sibling image.
    scenario = scenarios[2];
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(`${origin}/integrations?tab=catalogue`);
    await page.getByRole("heading", { name: "Proxmox VE", exact: true }).waitFor();
    const surface = await page.locator("main .surface").first().evaluate(node => { const style = getComputedStyle(node); return Object.fromEntries(["paddingTop", "borderRadius", "backgroundColor", "borderColor"].map(key => [key, style[key]])); });
    await page.goto(`${origin}/admin/system-settings`);
    await page.getByRole("heading", { name: "General", exact: true }).waitFor();
    const sibling = await page.locator('[aria-labelledby="settings-general"]').evaluate(node => { const style = getComputedStyle(node); return Object.fromEntries(["paddingTop", "borderRadius", "backgroundColor", "borderColor"].map(key => [key, style[key]])); });
    assert.deepEqual(surface, sibling);
    if (accent === null) await page.screenshot({ path: `${output}/system-settings-sibling-${theme}.png`, fullPage: true });
    await context.close();
    process.stdout.write(`Checked ${theme}, ${accent || "default"}: ${scenarios.length * 4} integration states and System Settings surfaces\n`);
  }
  assert.deepEqual(errors, []);
  await writeFile(`${output}/report.json`, JSON.stringify({ result: "passed", productionWebBuild: true, browserApiInterception: true, liveRuntimeProof: false, checks, siblingComparison: true, errors, requestCount: requests.length, actions }, null, 2));
  process.stdout.write(`PASS: ${checks.length} integration scenario/theme/accent/viewport checks. ${output}/report.json\n`);
} finally { await browser.close(); }
