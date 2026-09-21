// Isolated browser acceptance: all API calls are fixtures, never live Atlas data.
import assert from "node:assert/strict";
import { pathToFileURL, fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const base = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3109";
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const customer = { id: id(1), name: "Homelab" }, site = { id: id(2), customer_id: id(1), name: "Home" };
const permissions = ["assets.view", "assets.create", "assets.edit", "asset_types.view", "customers.view", "sites.view", "networks.view", "relationships.view"];
const api = fileURLToPath(new URL("../../api", import.meta.url));
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
try {
  for (const theme of ["light", "dark"]) for (const width of [1440, 800]) {
    const asset = { id: id(3), customer_id: customer.id, site_id: site.id, name: "AdGuard Home", asset_type: "server", status: "active", source: "manual", ip_address: "192.0.2.254", metadata: {} };
    const data = {
      customers: [customer], sites: [site],
      assets: [asset, { ...asset, id: id(4), name: "Legacy only" }],
      categories: [{ id: id(5), key: "compute", name: "Compute", active: true, show_in_topology: true }],
      asset_types: [{ id: id(6), key: "server", name: "Server", category_id: id(5), active: true }],
      asset_interfaces: [
        { id: id(7), asset_id: asset.id, network_id: null, name: "eth0", ip_address: "192.168.99.5", is_primary: true },
        { id: id(8), asset_id: asset.id, network_id: null, name: "eth1", ip_address: "192.168.5.5", is_primary: false },
      ], networks: [], relationships: [], relationship_types: [], platform_links: [],
    };
    const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme });
    const page = await context.newPage(), writes = [], errors = [];
    page.on("pageerror", e => { errors.push(e.message); console.error(e.message); });
    page.setDefaultTimeout(10000);
    await page.route("**/api/**", async route => {
      const request = route.request(), url = new URL(request.url()), path = url.pathname.replace(/^\/api/, "");
      let body = [], status = 200;
      if (path === "/auth/me") body = { id: id(99), display_name: "Fixture operator", email: "fixture@example.test", theme_mode: theme, permissions, assignments: [{ scope_type: "global", permissions }] };
      else if (path === "/context") body = { global_access: true, customers: [customer], sites: [site] };
      else if (path === "/asset-types") body = data.asset_types;
      else if (path === "/asset-categories") body = data.categories;
      else if (path === "/assets/summary") body = { total: data.assets.length, by_asset_type: [{ asset_type_id: id(6), asset_type_name: "Server", count: data.assets.length }] };
      else if (path === "/assets" && request.method() === "POST") {
        const payload = request.postDataJSON(); writes.push({ method: "POST", payload });
        body = { ...payload, id: id(9), source: "manual" }; status = 201;
      } else if (path === "/assets") body = data.assets;
      else if (path === `/assets/${id(3)}` || path === `/assets/${id(4)}` || path === `/assets/${id(9)}`) {
        body = data.assets.find(a => path.endsWith(a.id)) || { ...asset, id: id(9), ip_address: null };
        if (request.method() === "PATCH") { const payload = request.postDataJSON(); writes.push({ method: "PATCH", payload }); Object.assign(body, payload); }
      } else if (path === "/asset-interfaces") body = data.asset_interfaces.filter(i => i.asset_id === url.searchParams.get("asset_id"));
      else if (path.endsWith("/knowledge-summary")) body = { groups: [{ predicate: "ip_address", label: "IP Address", cardinality: "single", accepted_values: [{ assertion_id: id(11), value: "192.0.2.254" }], latest_observations: [], source_count: 1, assertion_count: 1, historical_count: 0 }], conflict_count: 0, unresolved_count: 0 };
      else if (path.endsWith("/fact-history")) body = { facts: {} };
      else if (path === "/topology") body = data;
      else if (path === "/topology/connectivity") body = JSON.parse(execFileSync(`${api}/.venv/bin/python`, ["-c", "import json,sys; from app.services.infrastructure_topology import connectivity; print(json.dumps(connectivity(**json.load(sys.stdin))))"], { cwd: api, encoding: "utf8", input: JSON.stringify({ topology: data, focus_id: url.searchParams.get("focus_asset_id"), hops: 1, show_networks: true, limit: 25 }) }));
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.goto(`${base}/assets`);
    await page.getByRole("button", { name: "Add asset", exact: true }).click();
    assert.equal(await page.getByLabel(/Primary IP|IP address/).count(), 0);
    await page.getByLabel("Name *", { exact: true }).fill("New Asset");
    await Promise.all([
      page.waitForResponse(r => new URL(r.url()).pathname === "/api/assets" && r.request().method() === "POST"),
      page.getByRole("button", { name: "Create asset", exact: true }).click(),
    ]);
    assert.equal(writes[0]?.method, "POST");
    assert.equal(Object.hasOwn(writes[0].payload, "ip_address"), false);
    await page.goto(`${base}/assets/${asset.id}/edit`);
    await page.getByRole("heading", { name: "Edit AdGuard Home", exact: true }).waitFor();
    assert.equal(await page.getByLabel(/Primary IP|IP address/).count(), 0);
    assert.doesNotMatch(await page.locator("body").innerText(), /192\.0\.2\.254/);
    await page.getByLabel("Description", { exact: true }).fill("Updated via web");
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await page.getByRole("heading", { name: "AdGuard Home", exact: true }).waitFor();
    assert.equal(writes[1]?.method, "PATCH");
    assert.equal(Object.hasOwn(writes[1].payload, "ip_address"), false);
    assert.equal(asset.ip_address, "192.0.2.254");
    assert.doesNotMatch(await page.locator("body").innerText(), /192\.0\.2\.254|Primary IP/);
    for (const [name, address] of [["eth0", "192.168.99.5"], ["eth1", "192.168.5.5"]]) {
      assert.ok((await page.locator(".interface-row").filter({ hasText: name }).innerText()).includes(address));
    }
    await page.goto(`${base}/assets/${id(4)}`);
    await page.getByText("No interfaces yet.", { exact: true }).waitFor();
    assert.doesNotMatch(await page.locator("body").innerText(), /192\.0\.2\.254|Primary IP/);
    // An interface without an IP must also leave the legacy value hidden.
    data.asset_interfaces.push({ id: id(10), asset_id: id(4), network_id: null, name: "empty0", ip_address: null });
    await page.reload(); await page.getByText("No IP", { exact: true }).waitFor();
    assert.doesNotMatch(await page.locator("body").innerText(), /192\.0\.2\.254/);
    await page.goto(`${base}/topology`);
    await page.getByRole("button", { name: "Platform", exact: true }).click();
    assert.match(await page.locator(`[data-platform-id="${asset.id}"]`).innerText(), /192\.168\.99\.5 \+1/);
    assert.doesNotMatch(await page.locator(`[data-platform-id="${id(4)}"]`).innerText(), /192\.0\.2\.254|No IP/);
    await page.getByRole("button", { name: "Connectivity", exact: true }).click();
    await page.getByLabel("Focus Asset or Network", { exact: true }).selectOption(asset.id);
    const node = page.locator(`[data-node-key="asset:${asset.id}"]`);
    await node.waitFor();
    assert.match(await node.innerText(), /192\.168\.99\.5 \+1/);
    assert.doesNotMatch(await node.innerText(), /192\.0\.2\.254/);
    await page.getByLabel("Focus Asset or Network", { exact: true }).selectOption(id(4));
    const emptyNode = page.locator(`[data-node-key="asset:${id(4)}"]`);
    await emptyNode.waitFor();
    assert.doesNotMatch(await emptyNode.innerText(), /192\.0\.2\.254|No IP/);
    await page.goto(`${base}/assets`);
    await page.locator("table").getByText("AdGuard Home", { exact: true }).waitFor();
    assert.doesNotMatch((await page.getByRole("columnheader").allTextContents()).join(" "), /\bIP\b/);
    assert.doesNotMatch(await page.locator("table").innerText(), /192\.0\.2\.254/);
    assert.deepEqual(errors, []);
    await context.close();
    console.log(`PASS ${theme} ${width}: create/edit payloads, detail, empty interfaces, Platform, Connectivity, Assets table`);
  }
} finally { await browser.close(); }
