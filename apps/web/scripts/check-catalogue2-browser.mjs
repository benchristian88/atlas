// Production UI acceptance with intercepted API data. No live catalogue checks,
// deployed instances, source connections or real installations are contacted.
import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
const { chromium } = await import(pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href);
const origin = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3137";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-unified-catalogue-browser";
await mkdir(output, { recursive: true });
const manifest = JSON.parse(await readFile(new URL("../../api/tests/fixtures/local_release/manifest.json", import.meta.url), "utf8"));
const digest = manifest.distribution.bundle_digest.replace("sha256:", ""), catalogueDigest = "a".repeat(64);
const confirmed = "2026-11-05T20:30:00Z";
const release = (version = manifest.version, patch = {}) => ({ connector_id: manifest.id, version, status: "active", eligible_for_install: true,
  digest, catalogue_digest: catalogueDigest, catalogue_sequence: 2, release_asset_id: 693849044,
  manifest: { ...manifest, version }, ...patch });
const permissions = ["integrations.view", "integration_runtime.view", "integration_runtime.manage", "customers.view", "sites.view", "assets.view", "asset_types.view", "relationship_types.view"];
const bundled = { connector_id: manifest.id, name: "Proxmox VE", description: "Bundled connection probe. Inventory discovery is unavailable in this historical package.", category: "virtualization", publisher: "Atlas Impact", trust_tier: "atlas_official", version: "0.1.0", digest: "c".repeat(64), package_available: true, verification_status: "verified", state: "installable", supported_actions: ["install"] };
const planned = [
  { connector_id: "docker", name: "Docker + Compose", category: "containers", description: "Docker host and workload inventory." },
  { connector_id: "unifi-network", name: "UniFi Network", category: "networking", description: "Network device inventory." },
].map(entry => ({ ...entry, publisher: "Atlas Impact", trust_tier: "atlas_official", version: null, package_available: false, verification_status: "metadata_only", supported_actions: [], state: "unavailable" }));
const installedEntry = { connector_id: manifest.id, version: manifest.version, installed_version: manifest.version, name: manifest.display.name, description: manifest.display.description, category: manifest.display.category, publisher: manifest.publisher.name, licence: manifest.licensing.licence, trust_tier: "atlas_official", digest, source: "installed", state: "installed", package_available: true, verification_status: "verified", supported_actions: ["remove"], message: "Installed package verified locally. Available offline." };
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
const errors = [], requests = [], checks = [];
const modes = ["installed", "future", "installable", "failure", "withdrawn", "unaccepted", "unavailable", "offline-installed", "stale", "cooldown", "viewer", "scoped", "forbidden", "malformed"];
try {
  for (const theme of ["light", "dark"]) for (const accent of [null, "#2563eb", "#7c3aed"]) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on("pageerror", error => errors.push(error.message));
    let mode = "installed", active = true, statusOverride = null, refreshResult = "unchanged", holdRefresh = null, mappingResolved = false;
    function statusBody() {
      if (statusOverride) return statusOverride;
      return { trusted_remote_available: mode !== "unaccepted", sequence: mode === "future" ? 4 : 2, schema_version: "1.0", content_digest: catalogueDigest,
        accepted_at: confirmed, last_confirmed_current_at: mode === "stale" ? null : confirmed,
        refresh_state: mode === "stale" ? "failed" : "idle", last_error_code: mode === "stale" ? "source_rate_limited" : null,
        next_attempt_at: mode === "cooldown" ? "2099-01-01T00:00:00Z" : null,
        entries: [release("0.2.0", { status: "withdrawn", eligible_for_install: false }), ...(mode === "withdrawn" ? [] : [release()]),
          ...(mode === "future" ? [release("0.10.0"), release("1.0.0", { connector_id: "future-platform", manifest: { ...manifest, id: "future-platform", version: "1.0.0", display: { ...manifest.display, name: "Future Platform", description: "A newly published Connector with a long description that must wrap correctly across desktop, tablet and mobile layouts." } } })] : [])] };
    }
    await page.route("**/api/**", async route => {
      const request = route.request(), path = new URL(request.url()).pathname.replace(/^\/api/, "");
      requests.push({ path, method: request.method(), body: request.postDataJSON(), headers: request.headers() });
      let body = [], status = 200;
      const allowed = permissions.filter(p => mode !== "viewer" || p !== "integration_runtime.manage");
      if (path === "/setup/status") body = { state: "INITIALISED" };
      else if (path === "/auth/me") body = { id: "00000000-0000-4000-8000-000000000090", email: "operator@example.test", display_name: "Test operator", theme_mode: theme, accent_colour: accent, permissions: allowed, assignments: [{ scope_type: mode === "scoped" ? "customer" : "global", customer_id: "00000000-0000-4000-8000-000000000001", permissions: allowed, role_name: "Administrator" }] };
      else if (path === "/context") body = { global_access: mode !== "scoped", customers: [{ id: "00000000-0000-4000-8000-000000000001", name: "Home lab" }], sites: [] };
      else if (path === "/integration-catalogue") body = { source: "bootstrap", entries: [...(mode === "withdrawn" ? [] : [{ ...bundled, installed_version: active ? manifest.version : null }]), ...planned], installed_entries: active && mode !== "scoped" ? [installedEntry] : [] };
      else if (path === "/integration-runtime") body = { status: "healthy", packaging_mode: "docker_compose" };
      else if (path === "/integration-catalogue/status") {
        body = mode === "malformed" ? { trusted_remote_available: true } : statusBody();
        if (["unavailable", "offline-installed", "forbidden"].includes(mode)) { status = mode === "forbidden" ? 403 : 503; body = { detail: "Private provider diagnostic must not be displayed" }; }
      } else if (path === "/integration-catalogue/refresh") {
        if (holdRefresh) await holdRefresh;
        statusOverride = { ...statusBody(), next_attempt_at: "2099-01-01T00:00:00Z", ...(refreshResult === "failed" ? { refresh_state: "failed", last_error_code: "source_rate_limited" } : refreshResult === "in_progress" ? { refresh_state: "in_progress" } : {}) };
        const { entries, ...checkpoint } = statusOverride;
        body = { result: refreshResult, status: checkpoint };
      } else if (path.endsWith("/install")) {
        if (mode === "failure") { status = 409; body = { detail: { code: "remote_install_confirmation_mismatch" } }; }
        else { active = true; body = { connector_id: manifest.id, version: manifest.version, status: "active" }; }
      } else if (path === `/connector-mappings/${manifest.id}`) {
        if (request.method() === "PUT") { mappingResolved = true; assert.equal(request.postDataJSON().version, manifest.version); }
        else assert.equal(new URL(request.url()).searchParams.get("version"), manifest.version);
        body = { version: manifest.version, mappings: [{ kind: "asset", source_key: "vm", label: "Virtual machine", required: true, resolved: mappingResolved, target_key: mappingResolved ? "vm" : null }] };
      } else if (path === "/asset-types") body = [{ key: "vm", name: "Virtual machine", active: true }];
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    });
    const posts = () => requests.filter(request => request.method === "POST");
    for (const width of [1440, 1024, 800, 390]) for (mode of modes) {
      await page.setViewportSize({ width, height: 1000 });
      active = ["installed", "future", "offline-installed", "stale", "cooldown", "viewer"].includes(mode);
      statusOverride = null;
      const before = requests.length;
      await page.goto(`${origin}/integrations?tab=catalogue`);
      await page.getByRole("heading", { name: "Docker + Compose", exact: true }).waitFor();
      await page.waitForFunction(() => ![...document.querySelectorAll("main [role=status]")].some(node => /Loading/.test(node.textContent)));
      const card = page.locator(`[data-connector-id="${manifest.id}"]`);
      assert.equal(await card.count(), 1, `${mode}: one card per identity`);
      assert.equal(await page.locator('[data-connector-id="docker"]').count(), 1);
      assert.equal(await page.locator('[data-connector-id="unifi-network"]').count(), 1);
      assert.match(await page.locator('[data-connector-id="docker"]').innerText(), /Planned/);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${theme}/${width}/${mode}: overflow`);
      assert.equal(requests.slice(before).some(request => request.method === "POST"), false, "Opening the page never checks the source or installs");
      assert.doesNotMatch(await page.locator("main").innerText(), /Private provider diagnostic/);
      if (mode === "scoped") {
        assert.equal(await page.locator("#official-catalogue").count(), 0);
        assert.equal(requests.slice(before).some(request => request.path === "/integration-catalogue/status"), false);
        assert.equal(await card.locator("button, a").count(), 0);
      } else if (["installed", "offline-installed", "stale", "cooldown", "viewer"].includes(mode)) {
        assert.match(await card.innerText(), /0\.2\.2.*Installed/);
        assert.match(await card.innerText(), /Verified/);
        assert.ok((await card.innerText()).includes(manifest.display.description));
        assert.doesNotMatch(await card.innerText(), /Inventory discovery is unavailable|0\.1\.0|0\.2\.0/);
        assert.equal(await card.getByRole("button", { name: "Review installation" }).count(), 0);
        if (mode !== "viewer") assert.match(await card.getByRole("link", { name: "Resolve mappings" }).getAttribute("href"), /version=0\.2\.2/);
        else assert.equal(await card.locator("button, a").count(), 0);
        if (mode === "installed") {
          await card.getByText(/Release history and bundled/).click();
          assert.match(await card.innerText(), /Withdrawn official release/);
          assert.match(await card.innerText(), /0\.1\.0/);
          await card.getByText(/Release history and bundled/).click();
        }
      } else if (mode === "future") {
        assert.equal(await page.locator('[data-connector-id="future-platform"]').count(), 1);
        assert.match(await card.innerText(), /0\.10\.0/);
        assert.equal(await card.getByRole("button", { name: "Review package change" }).count(), 1);
        assert.match(await card.innerText(), /0\.2\.2.*Installed/);
      } else if (["unaccepted", "unavailable", "forbidden", "malformed"].includes(mode)) {
        assert.match(await card.innerText(), /0\.1\.0/);
        assert.equal(await card.getByRole("button", { name: "Install Connector", exact: true }).count(), 1);
      } else if (mode === "withdrawn") {
        assert.match(await card.innerText(), /Withdrawn/);
        assert.equal(await card.getByRole("button", { name: "Review installation" }).count(), 0);
      }
      if (mode === "cooldown") {
        assert.equal(await page.getByRole("button", { name: "Check for catalogue updates" }).isDisabled(), true);
        assert.match(await page.locator("#official-catalogue").innerText(), /Next permitted check:/);
        const beforePosts = posts().length;
        await page.getByRole("button", { name: "Reload displayed catalogue" }).click();
        await page.waitForFunction(() => ![...document.querySelectorAll("button")].some(node => node.textContent === "Reload displayed catalogue" && node.disabled));
        assert.equal(posts().length, beforePosts);
      }
      if (width === 390 && accent === null && ["installable", "failure"].includes(mode)) {
        await card.getByRole("button", { name: "Review installation" }).click();
        const dialog = page.getByRole("dialog");
        await dialog.waitFor();
        for (const value of [manifest.id, manifest.version, digest, catalogueDigest, "693849044"]) assert.ok((await dialog.innerText()).includes(value));
        const beforePosts = posts().length;
        await dialog.getByRole("button", { name: "Verify and install" }).click();
        assert.equal(posts().length, beforePosts);
        await dialog.getByRole("checkbox").check();
        await dialog.getByRole("button", { name: "Verify and install" }).click();
        if (mode === "failure") { await dialog.getByRole("alert").waitFor(); await dialog.getByRole("button", { name: "Cancel" }).click(); }
        else { await dialog.waitFor({ state: "hidden" }); await card.getByText(/Installed package verified locally/).waitFor(); }
        const sent = posts().at(-1);
        assert.deepEqual(sent.body, { source: "official", version: manifest.version, digest, catalogue_sequence: 2, catalogue_digest: catalogueDigest, release_asset_id: 693849044, confirm: "install" });
        assert.equal(sent.headers["x-atlas-customer-id"], undefined);
        assert.equal(sent.headers["x-atlas-site-id"], undefined);
      }
      const focus = page.locator("main input[type=search]");
      await focus.focus();
      assert.equal(await focus.evaluate(node => getComputedStyle(node).outlineStyle), "solid");
      if (accent === null && [1440, 390].includes(width) && ["installed", "future", "offline-installed"].includes(mode)) await page.screenshot({ path: `${output}/${width}-${theme}-${mode}.png`, fullPage: true });
      checks.push({ theme, accent, width, mode });
    }
    // Real React search/filter and mapping navigation remain tied to exact versions.
    mode = "installed"; active = true; statusOverride = null;
    await page.goto(`${origin}/integrations?tab=catalogue`);
    const card = page.locator(`[data-connector-id="${manifest.id}"]`);
    await card.waitFor();
    await page.getByRole("searchbox", { name: "Search Connectors" }).fill("proxmox");
    await page.waitForFunction(() => document.querySelectorAll("[data-connector-id]").length === 1);
    await page.getByRole("button", { name: "Clear filters" }).click();
    await page.waitForFunction(() => document.querySelectorAll("[data-connector-id]").length === 3);
    await card.getByRole("link", { name: "Resolve mappings" }).click();
    await page.getByRole("heading", { name: "Connector mappings", exact: true }).waitFor();
    await page.getByRole("combobox", { name: "Map Virtual machine" }).selectOption("vm");
    await page.getByRole("cell", { name: "Resolved", exact: true }).waitFor();
    // Check cooldown and refresh lifecycle, including duplicate submission suppression.
    for (refreshResult of ["accepted", "unchanged", "cooldown", "in_progress", "failed"]) {
      statusOverride = null;
      await page.goto(`${origin}/integrations?tab=catalogue`);
      const check = page.getByRole("button", { name: "Check for catalogue updates" });
      await check.waitFor();
      await page.waitForFunction(() => !document.querySelector('#official-catalogue button[disabled]'));
      const beforePosts = posts().length;
      let finish;
      holdRefresh = new Promise(resolve => { finish = resolve; });
      const sent = page.waitForRequest(request => new URL(request.url()).pathname.endsWith("/integration-catalogue/refresh"));
      await check.click(); await sent;
      assert.equal(await check.isDisabled(), true);
      await check.evaluate(button => { button.click(); button.click(); });
      finish(); holdRefresh = null;
      await page.waitForFunction(() => !document.querySelector('#official-catalogue button[aria-busy=true]'));
      assert.equal(posts().length, beforePosts + 1);
      assert.equal(await check.isDisabled(), true);
      const text = await page.locator("#official-catalogue").innerText();
      if (["accepted", "unchanged"].includes(refreshResult)) assert.match(text, /Freshly confirmed by this check/);
      else assert.doesNotMatch(text, /Freshly confirmed/);
      if (refreshResult === "failed") assert.match(text, /provider has temporarily limited/);
    }
    await page.close();
  }
  assert.deepEqual(errors, []);
  assert.equal(requests.filter(request => request.path === "/integration-catalogue/refresh").every(request => !request.headers["x-atlas-customer-id"] && !request.headers["x-atlas-site-id"]), true);
  await writeFile(`${output}/report.json`, JSON.stringify({ result: "passed", productionBuild: true, mockedApi: true, liveInstallation: false, checks, errors }, null, 2));
  console.log(`Unified catalogue browser acceptance: ${checks.length} viewport/theme/accent/state checks, confirmation, mappings, search, refresh and cooldown passed. ${output}/report.json`);
} finally { await browser.close(); }
