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
const officialDigest = "55533ca67e7e9a14f82961e0a8c34ad78e2596049b3db02fde787494e3975afd";
const confirmed = "2026-10-25T22:20:00Z";
const nextAttempt = "2099-01-01T00:00:00Z";
const neverChecked = { source: "github-official-catalogue-v1", trusted_remote_available: false, refresh_state: "idle", entries: [] };
const accepted = { ...neverChecked, trusted_remote_available: true, sequence: 1, schema_version: "1.0", content_digest: officialDigest, accepted_at: confirmed, last_attempt_at: confirmed, last_confirmed_current_at: confirmed, entries: [{ connector_id: "proxmox", version: "0.2.0", status: "active", source: "official", package_available: false, supported_actions: [], manifest: { display: { name: "Official Proxmox VE", description: "Cluster and host metadata", category: "virtualization" }, publisher: { name: "Atlas Impact" }, licensing: { licence: "Apache-2.0" }, distribution: { asset_uri: "https://untrusted.invalid/?signed=private" }, connection_fields: [{ key: "token_secret", default: "never-display-this" }] } }] };
function officialFixture(kind) {
  if (!kind) return structuredClone(neverChecked);
  const value = structuredClone(accepted);
  if (kind === "failed" || kind === "rate-limited") Object.assign(value, { refresh_state: "failed", last_error_code: kind === "rate-limited" ? "source_rate_limited" : "unapproved_selection_root" });
  if (["cooldown", "rate-limited"].includes(kind)) value.next_attempt_at = nextAttempt;
  if (kind === "in-progress") value.refresh_state = "in_progress";
  if (kind === "empty") value.entries = [];
  if (kind === "malformed") return { trusted_remote_available: true, entries: {} };
  if (kind === "optional") {
    value.last_confirmed_current_at = "invalid";
    value.entries = [null, { manifest: { display: { name: "Long".repeat(200), description: "Description".repeat(300) } } }];
  }
  if (kind === "hostile") Object.assign(value.entries[0], { package_available: true, supported_actions: ["install", "update", "rollback", "remove"], state: "installable", verification_status: "verified", digest, manifest: { ...value.entries[0].manifest, display: { name: '<img src=x onerror="window.executed=true">', description: '<script>window.executed=true</script>' } } });
  return value;
}
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
  ...["accepted", "failed", "rate-limited", "cooldown", "in-progress", "unavailable", "forbidden", "malformed", "optional", "empty", "hostile"].map(official => ({ name: `official-${official}`, tab: "catalogue", official })),
  { name: "official-global-viewer", tab: "catalogue", official: "accepted", officialViewer: true },
  { name: "official-scoped-runtime", tab: "catalogue", viewer: true, scopedRuntime: true },
];
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
const errors = [], checks = [], requests = [], actions = [], officialChecks = [];
try {
  for (const theme of ["light", "dark"]) for (const accent of [null, "#2563EB", "#7C3AED"]) {
    const context = await browser.newContext({ colorScheme: theme });
    const page = await context.newPage(); page.setDefaultTimeout(12000);
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error" && !message.text().startsWith("Failed to load resource:")) errors.push(message.text()); });
    let scenario = scenarios[0];
    let officialState = structuredClone(neverChecked), refreshResult = "accepted", releaseRefresh = null, releaseStatus = null, statusFailure = false;
    await page.route("**/api/**", async route => {
      const request = route.request(), path = new URL(request.url()).pathname.replace(/^\/api/, "");
      requests.push({ path, method: request.method(), scenario: scenario.name, headers: { customer: request.headers()["x-atlas-customer-id"], site: request.headers()["x-atlas-site-id"] } });
      const permissions = scenario.viewer && !scenario.scopedRuntime ? basePermissions.filter(permission => permission !== "system_settings.manage") : [...basePermissions, "integration_runtime.view", ...(!scenario.officialViewer ? ["integration_runtime.manage"] : [])];
      let body = [], status = 200;
      if (path === "/setup/status") body = { state: "INITIALISED" };
      else if (path === "/auth/me") body = { id: "00000000-0000-4000-8000-000000000090", email: "operator@example.test", display_name: "Acceptance operator", theme_mode: theme, accent_colour: accent, permissions, assignments: [{ scope_type: scenario.viewer ? "site" : "global", customer_id: customer.id, site_id: site.id, permissions, role_name: scenario.viewer ? "Viewer" : "Administrator" }] };
      else if (path === "/context") body = { global_access: !scenario.viewer, customers: [customer], sites: [site] };
      else if (path === "/integrations") body = scenario.configured ? [{ id: "00000000-0000-4000-8000-000000000004", name: "Home Proxmox", connector_id: "atlas.proxmox", customer_name: customer.name, site_name: site.name, status: "pending" }] : [];
      else if (path === "/integration-runtime") body = scenario.unavailable ? { ...healthy, status: "unavailable", last_error: "runtime_unavailable" } : healthy;
      else if (path === "/integration-catalogue/status") {
        // Snapshot before delay so navigation tests can release an older GET.
        body = structuredClone(officialState);
        if (releaseStatus) await releaseStatus;
        if (statusFailure || scenario.official === "unavailable" || scenario.official === "forbidden") { status = scenario.official === "forbidden" ? 403 : 503; body = { detail: "Unsafe provider body /var/private token=never-display-this" }; }
      }
      else if (path === "/integration-catalogue/refresh") {
        assert.equal(request.method(), "POST");
        assert.equal(new URL(request.url()).search, "");
        assert.equal(request.postData(), null);
        if (refreshResult === "network-failure") return route.abort("failed");
        if (releaseRefresh) await releaseRefresh;
        if (["accepted", "unchanged"].includes(refreshResult)) officialState = { ...structuredClone(accepted), next_attempt_at: nextAttempt };
        else officialState = { ...officialState, next_attempt_at: nextAttempt, ...(refreshResult === "failed" ? { refresh_state: "failed", last_error_code: "source_rate_limited" } : refreshResult === "in_progress" ? { refresh_state: "in_progress" } : {}) };
        // Production POST has no entries; only GET returns the projection.
        const { entries: ignored, ...checkpoint } = officialState;
        body = { result: refreshResult, status: checkpoint };
        if (refreshResult === "state-unavailable") body = { result: "failed", code: "catalogue_state_unavailable" };
        if (refreshResult === "missing-status") body = { result: "accepted" };
        if (refreshResult === "followup-unavailable") { body = { result: "accepted", status: checkpoint }; statusFailure = true; }
      }
      else if (path === "/integration-catalogue") body = { source: "bootstrap", checked_at: "2026-10-11T00:00:00Z", entries: entries.map((entry, index) => index || !scenario.state ? entry : { ...entry, version: "1.0.0", digest, bundle_digest: `sha256:${digest}`, installed_version: scenario.state === "installed" ? "1.0.0" : null, package_available: true, verification_status: scenario.state === "verification_failed" ? "failed" : "verified", state: scenario.state, message: scenario.state === "runtime_update_required" ? "This package requires a newer approved runtime baseline." : scenario.state === "incompatible" ? "This package does not support the runtime protocol." : scenario.state === "verification_failed" ? "Package verification failed; activation is blocked." : "Verified immutable Connector package.", supported_actions: scenario.state === "installable" ? ["install"] : scenario.state === "installed" ? ["remove"] : [] }) };
      else if (path.endsWith("/install") || path.startsWith("/installed-connectors/")) { actions.push({ path, method: request.method(), body: request.postDataJSON() }); body = { status: "installed" }; }
      else if (path === "/system-settings/build-info") body = { version: "0.1.0", release_channel: "beta", install_method: "development" };
      else if (path === "/system-settings/updates") body = { status: "unavailable", current_version: "0.1.0", install_method: "development" };
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    });
    for (const width of [1440, 1024, 800, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      for (scenario of scenarios) {
        officialState = officialFixture(scenario.official);
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
          assert.equal(requests.slice(requestStart).filter(request => ["/integration-catalogue", "/integration-catalogue/status", "/integration-runtime"].includes(request.path)).every(request => !request.headers.customer && !request.headers.site), true);
          const official = page.locator("#official-catalogue");
          if (scenario.viewer) {
            assert.equal(await official.count(), 0);
            assert.equal(requests.slice(requestStart).some(request => request.path === "/integration-catalogue/status"), false);
          } else {
            assert.equal(await official.count(), 1);
            assert.equal(await official.getByRole("button", { name: "Check official catalogue", exact: true }).count(), scenario.officialViewer ? 0 : 1);
            assert.equal(requests.slice(requestStart).some(request => request.path === "/integration-catalogue/refresh"), false, "page load must not check GitHub");
            assert.equal(await official.locator('a, img, script, iframe').count(), 0);
            assert.equal(await page.evaluate(() => Boolean(window.executed)), false);
            assert.doesNotMatch(await official.innerText(), /never-display-this|untrusted.invalid|Unsafe provider|\/var\/private/);
            assert.equal(await official.getByRole("button", { name: /Install|Upgrade|Rollback|Activate|Configure|Resolve mappings/i }).count(), 0);
            if (!scenario.official) assert.match(await official.innerText(), /not yet been checked/);
            else if (["unavailable", "forbidden", "malformed"].includes(scenario.official)) {
              assert.equal(await official.getByRole("alert").count(), 1);
              assert.equal(await official.getByRole("button", { name: "Check official catalogue" }).isDisabled(), true);
            } else {
              assert.match(await official.innerText(), /Sequence 1/);
              if (scenario.official === "optional") assert.match(await official.innerText(), /Last confirmed: Not recorded/);
              else if (scenario.official === "empty") assert.match(await official.innerText(), /No official connector entries/);
              else if (scenario.official === "hostile") assert.match(await official.innerText(), /<script>/);
              else assert.match(await official.innerText(), /Official Proxmox VE/);
              if (["cooldown", "in-progress", "rate-limited"].includes(scenario.official)) assert.equal(await official.getByRole("button", { name: "Check official catalogue" }).isDisabled(), true);
              if (scenario.official === "accepted") {
                await official.getByText("Official catalogue technical details", { exact: true }).click();
                assert.match(await official.innerText(), new RegExp(officialDigest));
              }
            }
          }
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
    // Exercise the real React event handlers and async lifecycle. Intercepted
    // POST results never contact GitHub or activate a package.
    await page.setViewportSize({ width: 390, height: 1000 });
    scenario = { name: "official-refresh", tab: "catalogue", official: "accepted" };
    const official = page.locator("#official-catalogue");
    const checkButton = official.getByRole("button", { name: "Check official catalogue", exact: true });
    const postCount = () => requests.filter(request => request.path === "/integration-catalogue/refresh").length;
    const localCount = () => requests.filter(request => request.path === "/integration-catalogue").length;
    for (refreshResult of ["accepted", "unchanged", "failed", "cooldown", "in_progress", "state-unavailable", "unexpected", "missing-status", "network-failure", "followup-unavailable"]) {
      officialState = refreshResult === "accepted" ? structuredClone(neverChecked) : officialFixture("accepted");
      statusFailure = false;
      await page.goto(`${origin}/integrations?tab=catalogue`);
      await checkButton.waitFor();
      await page.waitForFunction(() => !document.querySelector('#official-catalogue button[disabled]'));
      const before = postCount(), localBefore = localCount(), packageBefore = actions.length;
      const statusBefore = requests.filter(request => request.path === "/integration-catalogue/status").length;
      if (refreshResult === "accepted") {
        await page.getByRole("button", { name: "Refresh local catalogue", exact: true }).click();
        await page.waitForFunction(() => !Array.from(document.querySelectorAll('button')).some(button => button.textContent === 'Refresh local catalogue' && button.disabled));
        assert.equal(postCount(), before);
        let finish;
        releaseRefresh = new Promise(resolve => { finish = resolve; });
        await page.keyboard.press("Tab"); await checkButton.focus();
        assert.equal(await checkButton.evaluate(node => getComputedStyle(node).outlineStyle), "solid");
        const sent = page.waitForRequest(request => new URL(request.url()).pathname.endsWith("/integration-catalogue/refresh"));
        sent.catch(() => {}); // Preserve the original assertion if cleanup closes the page.
        await page.keyboard.press("Enter"); await sent;
        assert.equal(await checkButton.isDisabled(), true);
        assert.equal(await checkButton.getAttribute("aria-busy"), "true");
        assert.match(await official.getByRole("status").innerText(), /check is in progress/);
        await checkButton.evaluate(button => { button.click(); button.click(); });
        assert.equal(postCount(), before + 1);
        finish(); releaseRefresh = null;
      } else {
        await checkButton.evaluate(button => { button.click(); button.click(); });
      }
      const expected = { accepted: "Official catalogue verified and accepted.", unchanged: "Official catalogue verified; the accepted catalogue is unchanged.", failed: "The catalogue provider has temporarily limited requests.", cooldown: "Official catalogue checks are temporarily unavailable.", in_progress: "An official catalogue check is already in progress.", "state-unavailable": "Atlas could not update official catalogue status.", unexpected: "This does not establish a verification failure.", "missing-status": "This does not establish a verification failure.", "network-failure": "This does not establish a verification failure.", "followup-unavailable": "This does not establish a verification failure." }[refreshResult];
      await official.getByText(expected, { exact: false }).first().waitFor();
      await page.waitForFunction(() => !document.querySelector('#official-catalogue button[aria-busy="true"]'));
      assert.equal(postCount(), before + 1);
      assert.equal(actions.length, packageBefore);
      assert.equal(localCount(), localBefore + (refreshResult === "accepted" ? 1 : 0));
      assert.equal(requests.filter(request => request.path === "/integration-catalogue/status").length, statusBefore + (["unexpected", "missing-status", "network-failure"].includes(refreshResult) ? 0 : 1));
      assert.match(await official.innerText(), /Official Proxmox VE/);
      if (refreshResult === "failed") {
        assert.equal(await official.getByRole("alert").count(), 1);
        await official.getByText("Official catalogue technical details", { exact: true }).click();
        assert.ok((await official.innerText()).includes(await page.evaluate(value => new Date(value).toLocaleString(), confirmed)));
      }
      assert.equal(await checkButton.isDisabled(), true);
      if (refreshResult === "accepted") {
        await page.reload();
        await official.getByText("Official Proxmox VE", { exact: true }).waitFor();
        assert.match(await official.innerText(), /Sequence 1/);
        assert.equal(postCount(), before + 1);
        await page.screenshot({ path: `${output}/official-refreshed-${theme}-${accent || "default"}-390.png`, fullPage: true });
      }
      officialChecks.push({ result: refreshResult, theme, accent, exactlyOnePost: true, localIsolated: true });
    }
    statusFailure = false;
    // A late old GET must not replace state after leaving and reopening the tab.
    scenario = { name: "official-stale-status", tab: "catalogue", official: "accepted" };
    officialState = structuredClone(neverChecked);
    let finishStatus;
    releaseStatus = new Promise(resolve => { finishStatus = resolve; });
    const oldGet = page.waitForRequest(request => new URL(request.url()).pathname.endsWith("/integration-catalogue/status"));
    await page.goto(`${origin}/integrations?tab=catalogue`); await oldGet;
    await page.getByRole("navigation", { name: "Integration views" }).getByRole("link", { name: "Configured", exact: true }).click();
    await page.getByText("No configured integrations", { exact: true }).waitFor();
    officialState = officialFixture("accepted"); releaseStatus = null;
    await page.getByRole("navigation", { name: "Integration views" }).getByRole("link", { name: "Catalogue", exact: true }).click();
    await official.getByText("Official Proxmox VE", { exact: true }).waitFor();
    finishStatus();
    await official.getByRole("button", { name: "Reload official status" }).click();
    await page.waitForFunction(() => !document.querySelector('#official-catalogue button[disabled]'));
    assert.match(await official.innerText(), /Sequence 1/);
    // The same lifecycle guard applies to a slow POST when navigating away.
    officialState = officialFixture("accepted"); refreshResult = "unchanged";
    let finishRefresh;
    releaseRefresh = new Promise(resolve => { finishRefresh = resolve; });
    const oldPost = page.waitForRequest(request => new URL(request.url()).pathname.endsWith("/integration-catalogue/refresh"));
    await checkButton.click(); await oldPost;
    await page.getByRole("navigation", { name: "Integration views" }).getByRole("link", { name: "Runtime", exact: true }).click();
    await page.getByRole("heading", { name: "Integration runtime", exact: true }).waitFor();
    finishRefresh(); releaseRefresh = null;
    await page.getByRole("navigation", { name: "Integration views" }).getByRole("link", { name: "Catalogue", exact: true }).click();
    await official.getByText("Official Proxmox VE", { exact: true }).waitFor();
    assert.equal(await official.getByText("Official catalogue verified; the accepted catalogue is unchanged.", { exact: true }).count(), 0);
    officialChecks.push({ theme, accent, staleStatusIsolated: true, staleRefreshIsolated: true });
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
  assert.equal(requests.filter(request => request.path === "/integration-catalogue/refresh").every(request => !request.headers.customer && !request.headers.site), true);
  await writeFile(`${output}/report.json`, JSON.stringify({ result: "passed", productionWebBuild: true, browserApiInterception: true, liveRuntimeProof: false, checks, officialChecks, siblingComparison: true, errors, requestCount: requests.length, actions }, null, 2));
  process.stdout.write(`PASS: ${checks.length} integration scenario/theme/accent/viewport checks. ${output}/report.json\n`);
} finally { await browser.close(); }
