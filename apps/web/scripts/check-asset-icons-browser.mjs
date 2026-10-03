// Production-build UI regression with API fixtures; no live user data is edited.
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { pathToFileURL } from "node:url";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const base = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3108";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-asset-icon-browser";
await mkdir(output, { recursive: true });
const id = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const customer = { id: id(1), name: "Homelab", status: "active" };
const site = { id: id(2), customer_id: customer.id, name: "Home", status: "active" };
const typeUrl = "https://type.example.test/default.png";
const sourceUrl = "https://external-source.example.test/asset.png";
const permissions = ["assets.view", "asset_types.view", "customers.view", "sites.view", "services.view", "business_functions.view", "service_dependencies.view", "knowledge_gaps.view", "changes.view"];
const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAfUlEQVR4nGNgGAUjHTBiExTPmfOfVha+nJKCYicTPS3HZj4TwwADJkIKXkxOBuMBccALJItp5QgmmphKLQdI5M7FyqYmYCGkgFYWD94oeIlWUFAb0Nr8UTD0ACM2wdHakJ6AiZCC0dqQ1oAJn+RobUgPwIQuMFobjgIGOgMAvBct59IvF+kAAAAASUVORK5CYII=", "base64");
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
let checks = 0;
try {
  for (const theme of ["light", "dark"]) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: theme });
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    const errors = [], external = [];
    page.on("pageerror", (error) => errors.push(error.message));
    let mode = "cached";
    let version = "a";
    const assets = () => ["AdGuard Home", "Nginx Proxy Manager", "PVE1"].map((name, i) => ({
      id: id(10 + i), name, customer_id: customer.id, site_id: site.id, asset_type: "server", status: "active", source: "manual",
      completeness_status: "not_evaluated", open_knowledge_gap_count: 0, custom_fields: [], metadata: {},
      icon_url: mode === "cleared" ? null : sourceUrl,
      cached_icon_url: ["cleared", "generic"].includes(mode) ? null : `/api/assets/${id(10 + i)}/icon?v=${version.repeat(64)}`,
      default_icon_url: mode === "generic" ? null : typeUrl,
    }));
    const graph = () => {
      const nodes = assets().map((asset) => ({ ...asset, key: `asset:${asset.id}`, entity_id: asset.id, entity_type: "asset", href: `/assets/${asset.id}` }));
      const service = { key: `service:${id(20)}`, entity_id: id(20), entity_type: "service", name: "Home DNS", href: `/services/${id(20)}`, customer_id: customer.id, site_id: site.id };
      const bf = { ...service, key: `business_function:${id(21)}`, entity_id: id(21), entity_type: "business_function", name: "Home users", href: `/business-functions/${id(21)}` };
      return { nodes: [...nodes, service, bf], edges: [...nodes.map((node, i) => ({ key: `e${i}`, edge_family: "service_asset", source_key: service.key, target_key: node.key, label: "Depends on" })), { key: "bf", edge_family: "service_business_function", source_key: service.key, target_key: bf.key, label: "Supports" }], warnings: [], truncated: false };
    };
    await page.route("https://**/*", async (route) => {
      if (route.request().url() === typeUrl) return route.fulfill({ contentType: "image/png", body: mode === "typefailed" ? "corrupt" : png });
      external.push(route.request().url());
      await route.abort();
    });
    await page.route("**/api/**", async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;
      if (path.endsWith("/icon")) {
        if (["failed", "typefailed"].includes(mode)) return route.fulfill({ status: 204 });
        if (mode === "corrupt") return route.fulfill({ contentType: "image/png", body: "corrupt" });
        return route.fulfill({ contentType: "image/png", body: png });
      }
      let body = [];
      if (path === "/api/auth/me") body = { id: id(99), display_name: "Icon tester", email: "fixture@example.test", theme_mode: theme, permissions, assignments: [{ scope_type: "global", permissions }] };
      else if (path === "/api/context") body = { customers: [customer], sites: [site], global_access: true, selected_customer_id: customer.id, selected_site_id: site.id };
      else if (path === "/api/assets") body = assets();
      else if (path === "/api/asset-types") body = [{ id: id(50), key: "server", name: "Server", default_icon_url: mode === "generic" ? null : typeUrl }];
      else if (path === "/api/assets/summary") body = { total: 3, by_asset_type: [] };
      else if (path.startsWith("/api/operational-graph")) body = graph();
      else if (path === "/api/changes") body = { items: [] };
      else if (assets().some((asset) => path === `/api/assets/${asset.id}`)) body = assets().find((asset) => path.endsWith(asset.id));
      else if (path.endsWith("/fact-history")) body = { facts: {} };
      else if (path.endsWith("/knowledge-summary")) body = { groups: [] };
      else if (path.endsWith("/completeness")) body = { summary: null, active_gaps: [], resolved_gaps: [] };
      else if (path.endsWith("/summary")) body = {};
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    });
    for (mode of ["cached", "failed", "corrupt", "cleared", "generic", "typefailed"]) {
      for (const [path, selector, size] of [["/assets", ".catalogue-identity .asset-icon", 38], [`/assets/${id(10)}`, ".entity-detail-header .asset-icon", 48], ["/knowledge-graph", ".landscape-node .asset-icon", 32], ["/dashboard", ".landscape-node .asset-icon", 32]]) {
        await page.goto(`${base}${path}`);
        const icon = page.locator(selector).first();
        try { await icon.waitFor(); } catch (error) { console.error(errors, await page.locator("body").innerText()); throw error; }
        try { await page.waitForFunction(({ selector, mode }) => {
          const box = document.querySelector(selector);
          const imgs = [...box.querySelectorAll("img")];
          const visible = imgs.filter((img) => getComputedStyle(img).opacity !== "0");
          return visible.every((img) => img.complete && img.naturalWidth > 0) && (["generic", "typefailed"].includes(mode) ? imgs.length === 0 && box.querySelector(".presentation-icon svg") : visible.some((img) => mode === "cached" ? img.src.includes("/icon?") : img.src.includes("type.example.test")));
        }, { selector, mode }); } catch (error) { console.error(await icon.evaluate(el => [...el.querySelectorAll("img")].map(img => ({ src: img.src, complete: img.complete, width: img.naturalWidth, opacity: getComputedStyle(img).opacity }))), external); throw error; }
        assert.equal(await icon.evaluate(el => [...el.querySelectorAll("img")].filter(img => getComputedStyle(img).opacity !== "0").length), ["generic", "typefailed"].includes(mode) ? 0 : 1, "Transparent icons must not reveal the generic placeholder underneath");
        const bounds = await icon.boundingBox();
        assert.equal(bounds.width, size); assert.equal(bounds.height, size);
        if (path === "/knowledge-graph" || path === "/dashboard") {
          assert.ok(await page.locator(".landscape-node .entity-service").count());
          assert.ok(await page.locator(".landscape-node .entity-business_function").count());
        }
        if (mode === "cached") await page.screenshot({ path: `${output}/${theme}-${path.startsWith("/assets/") ? "asset-detail" : path.slice(1)}.png` });
        checks++;
      }
    }
    mode = "cached"; version = "b";
    await page.goto(`${base}/assets`);
    await page.locator(`.asset-icon img[src*="v=${"b".repeat(64)}"]`).first().waitFor();
    assert.deepEqual(external, [], "Asset source must never be contacted by the browser");
    assert.deepEqual(errors, []);
    await context.close();
  }
  console.log(`${checks} browser surface/theme/fallback checks passed; URL replacement passed; no external Asset-source requests.`);
} finally { await browser.close(); }
