// Deterministic production UI acceptance; no real package installation.
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { pathToFileURL } from "node:url";
const { chromium } = await import(pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href);
const origin = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3137";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-catalogue2-browser";
await mkdir(output, { recursive: true });
const digest = "b".repeat(64), catalogueDigest = "a".repeat(64);
const entry = { connector_id: "proxmox", version: "0.2.2", status: "active", eligible_for_install: true,
  digest, catalogue_digest: catalogueDigest, catalogue_sequence: 2, release_asset_id: 693849044,
  manifest: { display: { name: "Proxmox VE", description: "Read-only inventory" }, publisher: { name: "Atlas Impact" }, licensing: { licence: "Apache-2.0" } } };
const permissions = ["integrations.view", "integration_runtime.view", "integration_runtime.manage", "customers.view", "sites.view", "assets.view"];
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
const errors = [], requests = [];
try {
  for (const width of [1440, 390]) for (const mode of ["manager", "viewer", "withdrawn", "failure"]) {
    const page = await browser.newPage({ viewport: { width, height: 1000 } });
    page.on("pageerror", error => errors.push(error.message));
    await page.route("**/api/**", async route => {
      const request = route.request(), path = new URL(request.url()).pathname.replace(/^\/api/, "");
      let body = [], status = 200;
      const allowed = permissions.filter(p => mode !== "viewer" || p !== "integration_runtime.manage");
      if (path === "/setup/status") body = { state: "INITIALISED" };
      else if (path === "/auth/me") body = { id: "00000000-0000-4000-8000-000000000090", email: "operator@example.test", display_name: "Test operator", permissions: allowed, assignments: [{ scope_type: "global", permissions: allowed, role_name: "Administrator" }] };
      else if (path === "/context") body = { global_access: true, customers: [], sites: [] };
      else if (path === "/integration-catalogue") body = { source: "bootstrap", entries: [] };
      else if (path === "/integration-runtime") body = { status: "healthy", packaging_mode: "docker_compose" };
      else if (path === "/integration-catalogue/status") body = { trusted_remote_available: true, sequence: 2, schema_version: "1.0", content_digest: catalogueDigest, refresh_state: "idle", entries: [{ ...entry, ...(mode === "withdrawn" ? { status: "withdrawn", eligible_for_install: false } : {}) }] };
      else if (path.endsWith("/install")) {
        requests.push({ path, body: request.postDataJSON(), headers: request.headers() });
        if (mode === "failure") { status = 409; body = { detail: { code: "remote_install_confirmation_mismatch" } }; }
        else body = { connector_id: "proxmox", version: "0.2.2", status: "active" };
      }
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.goto(`${origin}/integrations?tab=catalogue`);
    const official = page.locator("#official-catalogue");
    await official.getByRole("heading", { name: "Proxmox VE", exact: true }).waitFor();
    if (["viewer", "withdrawn"].includes(mode)) assert.equal(await official.getByRole("button", { name: "Review installation" }).count(), 0);
    else {
      const before = requests.length;
      await official.getByRole("button", { name: "Review installation" }).click();
      const dialog = page.getByRole("dialog");
      await dialog.waitFor();
      assert.match(await dialog.innerText(), /0.2.2/);
      assert.match(await dialog.innerText(), new RegExp(digest));
      await dialog.getByRole("button", { name: "Verify and install" }).click();
      assert.equal(requests.length, before); // native required-checkbox validation
      await dialog.getByRole("checkbox").check();
      await dialog.getByRole("button", { name: "Verify and install" }).click();
      if (mode === "failure") await dialog.getByRole("alert").waitFor();
      else await dialog.waitFor({ state: "hidden" });
      assert.deepEqual(requests.at(-1).body, { source: "official", version: "0.2.2", digest,
        catalogue_sequence: 2, catalogue_digest: catalogueDigest, release_asset_id: 693849044, confirm: "install" });
      assert.equal(requests.at(-1).headers["x-atlas-customer-id"], undefined);
      assert.equal(requests.at(-1).headers["x-atlas-site-id"], undefined);
    }
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${width}/${mode} overflow`);
    await page.screenshot({ path: `${output}/${width}-${mode}.png`, fullPage: true });
    await page.close();
  }
  assert.deepEqual(errors, []);
  console.log("Catalogue 2 browser acceptance: 8 viewport/permission/confirmation/error scenarios passed");
} finally { await browser.close(); }
