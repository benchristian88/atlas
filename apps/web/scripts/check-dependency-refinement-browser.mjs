// Raw API fixtures deliberately have endpoint keys and provenance source text,
// never pre-resolved source/target objects. All API calls are intercepted.
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { refinementGraph } from "../tests/fixtures/dependency-refinement.mjs";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const base = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3112";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-dependency-refinement-browser";
await mkdir(output, { recursive: true });
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const customer = { id: id(1), name: "Homelab" }, site = { id: id(2), customer_id: customer.id, name: "Home" };
const permissions = ["assets.view", "services.view", "service_dependencies.view", "business_functions.view", "customers.view", "sites.view", "knowledge_gaps.view"];
const keyMap = new Map(refinementGraph.nodes.map((n, i) => [n.key, `${n.entity_type}:${id(i + 10)}`]));
const graph = { ...refinementGraph, nodes: refinementGraph.nodes.map(n => ({ ...n, key: keyMap.get(n.key), entity_id: keyMap.get(n.key).split(":")[1], customer_id: customer.id, site_id: site.id, criticality_rank: n.name === "DNS" ? 90 : 30, open_gap_count: n.name === "DNS" ? 1 : 0 })), edges: refinementGraph.edges.map((e, i) => ({ ...e, edge_id: id(i + 100), source_key: keyMap.get(e.source_key), target_key: keyMap.get(e.target_key), source: "manual" })) };
for (const n of graph.nodes) n.href = `/${n.entity_type === "service" ? "services" : n.entity_type === "asset" ? "assets" : "business-functions"}/${n.entity_id}`;
const dns = graph.nodes.find(n => n.name === "DNS"), asset = graph.nodes.find(n => n.name === "Atlas DNS");
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
let checks = 0, activePage;
try {
  for (const width of [1440, 900, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, hasTouch: width === 390, reducedMotion: "reduce" });
    const page = await context.newPage(); activePage = page; page.setDefaultTimeout(10000);
    const errors = []; page.on("pageerror", e => errors.push(e.message));
    let authenticated = true, mode = "raw";
    const requests = [];
    await page.route("**/api/**", async route => {
      const url = new URL(route.request().url()); requests.push(url.pathname + url.search);
      let body = [], status = 200;
      if (url.pathname === "/api/auth/me") {
        if (authenticated) body = { id: id(99), display_name: "Fixture tester", email: "fixture@example.test", permissions, assignments: [{ scope_type: "global", permissions }] };
        else { status = 401; body = { detail: "Not authenticated" }; }
      } else if (url.pathname === "/api/context") body = { customers: [customer], sites: [site], global_access: true, selected_customer_id: customer.id, selected_site_id: site.id };
      else if (url.pathname === "/api/dashboard/summary") body = { assets: 8, services: 5, business_functions: 2, open_knowledge_gap_count: 3 };
      else if (url.pathname.startsWith("/api/operational-graph")) {
        body = mode === "empty" ? { nodes: [], edges: [] } : mode === "partial" ? { ...graph, nodes: [...graph.nodes, null, {}], edges: [...graph.edges, null, {}, { key: "hidden", edge_family: "service_asset", source_key: dns.key, target_key: "asset:hidden", failure_effect: "unknown" }, { id: id(500), edge_type: "service_asset", source_id: dns.entity_id, target_id: asset.entity_id, label: "Managed by" }] } : graph;
      }
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    });
    const count = label => page.getByRole("link", { name: new RegExp(`^${label}`) }).locator(".ops-badge");
    await page.goto(base);
    await page.getByRole("heading", { name: "Dashboard", exact: true }).waitFor();
    await page.waitForFunction(() => document.querySelector(".widget-attention .ops-badge")?.textContent === "2");
    assert.equal(await count("Unknown dependency effects").innerText(), "2");
    assert.equal(await count("Ungrouped dependencies").innerText(), "2");
    assert.equal(await count("Knowledge gaps").innerText(), "3");
    assert.equal(await count("Critical Services with gaps").innerText(), "1"); checks += 4;
    await page.getByText("Relationships needing dependency-impact classification", { exact: true }).click();
    await page.locator('.widget-attention a[href$="#dependency-impact"]').first().waitFor();
    assert.equal(await page.locator('.widget-attention a[href$="#dependency-impact"]').count(), 2); checks++;
    await page.screenshot({ path: `${output}/dashboard-${width}.png`, fullPage: true });
    await page.reload(); await count("Unknown dependency effects").getByText("2", { exact: true }).waitFor(); checks++;
    mode = "partial";
    await page.reload(); await count("Unknown dependency effects").getByText("3", { exact: true }).waitFor();
    assert.equal(await count("Ungrouped dependencies").innerText(), "3"); checks++;
    mode = "empty";
    await page.reload(); await count("Unknown dependency effects").getByText("0", { exact: true }).waitFor();
    assert.equal(await count("Ungrouped dependencies").innerText(), "0"); checks++;
    mode = "raw";
    for (const focus of [false, true]) {
      await page.goto(`${base}/knowledge-graph${focus ? `?focus=${dns.key}&depth=2` : ""}`);
      await page.locator(".dependency-presentation").filter({ hasText: "DNS HA" }).waitFor();
      assert.equal(await page.locator(".dependency-presentation").filter({ hasText: "File Sharing Providers" }).count(), 1); checks++;
      assert.doesNotMatch(await page.locator(".landscape-canvas").innerText(), /[0-9a-f]{8}-[0-9a-f]{4}|Dependency asset|Providers 6ad/); checks++;
      if (focus) {
        await page.waitForFunction(key => {
          const viewport = document.querySelector(".landscape-viewport").getBoundingClientRect();
          const node = document.querySelector(`[data-node-key="${key}"]`).getBoundingClientRect();
          return node.left >= viewport.left - 1 && node.right <= viewport.right + 1;
        }, dns.key); checks++;
      }
      await page.locator(".graph-semantic-list > summary").click();
      const details = page.locator(".graph-semantic-list li details");
      for (let i = 0; i < await details.count(); i++) await details.nth(i).locator("summary").click();
      assert.doesNotMatch(await page.locator(".graph-semantic-list").innerText(), /[0-9a-f]{8}-[0-9a-f]{4}|Dependency asset/); checks++;
      await page.locator(".graph-semantic-list > summary").click();
      await page.screenshot({ path: `${output}/graph-${focus ? "focus-depth-2" : "overview"}-${width}.png`, fullPage: true });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)); checks++;
      await page.getByRole("button", { name: "Expand Knowledge Graph", exact: true }).click();
      await page.screenshot({ path: `${output}/graph-expanded-${focus ? "focus" : "overview"}-${width}.png`, fullPage: true });
      await page.getByRole("button", { name: "Close expanded Knowledge Graph", exact: true }).click();
    }
    assert.ok(requests.some(path => path.includes("max_depth=2"))); checks++;
    await page.getByRole("link", { name: "Dashboard", exact: true }).click();
    await count("Unknown dependency effects").getByText("2", { exact: true }).waitFor(); checks++;
    authenticated = false;
    await page.reload(); await page.waitForURL("**/login"); checks++;
    await page.goto(base); await page.waitForURL("**/login"); checks++;
    assert.deepEqual(errors, []); checks++;
    await context.close();
  }
  console.log(`${checks} dashboard/graph browser assertions passed. Screenshots: ${output}`);
} catch (error) { if (activePage) { await activePage.screenshot({ path: `${output}/failure.png`, fullPage: true }); console.error(await activePage.locator("body").innerText()); } throw error; }
finally { await browser.close(); }
