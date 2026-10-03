import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { singletonGraph, dnsGraph, denseRoutingGraph } from "../tests/fixtures/edge-routing.mjs";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const base = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3112";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-edge-routing-browser";
await mkdir(output, { recursive: true });
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const customer = { id: id(1), name: "Homelab" }, site = { id: id(2), customer_id: customer.id, name: "Home" };
const permissions = ["assets.view", "services.view", "service_dependencies.view", "business_functions.view", "customers.view", "sites.view"];
const keys = new Map(denseRoutingGraph.nodes.map((node, index) => [node.key, `${node.entity_type}:${id(index + 10)}`]));
const convert = graph => ({ ...graph, nodes: graph.nodes.map(node => ({ ...node, key: keys.get(node.key), entity_id: keys.get(node.key).split(":")[1], customer_id: customer.id, site_id: site.id })), edges: graph.edges.map(edge => ({ ...edge, source_key: keys.get(edge.source_key), target_key: keys.get(edge.target_key) })) });
const fixtures = { ha: convert({ ...dnsGraph, nodes: dnsGraph.nodes.filter(node => node.key !== "asset:atlas"), edges: dnsGraph.edges.filter(edge => edge.key !== "control") }), singleton: convert(singletonGraph), dns: convert(dnsGraph), dense: convert(denseRoutingGraph) };
// Bounded structural fixture response, not a replacement for backend traversal.
function neighborhood(graph, focus, depth) {
  if (!focus) return graph;
  const seen = new Set([focus]); let frontier = [focus];
  for (let i = 0; i < depth; i++) {
    const next = new Set();
    for (const edge of graph.edges) {
      if (frontier.includes(edge.source_key) && !seen.has(edge.target_key)) next.add(edge.target_key);
      if (frontier.includes(edge.target_key) && !seen.has(edge.source_key)) next.add(edge.source_key);
    }
    next.forEach(key => seen.add(key)); frontier = [...next];
  }
  return { ...graph, nodes: graph.nodes.filter(node => seen.has(node.key)), edges: graph.edges.filter(edge => seen.has(edge.source_key) && seen.has(edge.target_key)) };
}
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
let activePage, checks = 0;
try {
  for (const theme of ["light", "dark"]) for (const width of [1440, 900, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, hasTouch: width === 390, colorScheme: theme, reducedMotion: "reduce" });
    const page = await context.newPage(); activePage = page; page.setDefaultTimeout(10000);
    const errors = []; page.on("pageerror", error => errors.push(error.message));
    let fixture = "singleton";
    await page.route("**/api/**", async route => {
      const url = new URL(route.request().url()); let body = [];
      if (url.pathname === "/api/auth/me") body = { id: id(99), email: "fixture@example.test", display_name: "Routing tester", theme_mode: theme, permissions, assignments: [{ scope_type: "global", permissions }] };
      else if (url.pathname === "/api/context") body = { customers: [customer], sites: [site], global_access: true, selected_customer_id: customer.id, selected_site_id: site.id };
      else if (url.pathname.startsWith("/api/operational-graph")) body = neighborhood(fixtures[fixture], url.searchParams.has("focus_id") ? `${url.searchParams.get("focus_type")}:${url.searchParams.get("focus_id")}` : "", Number(url.searchParams.get("max_depth") || 3));
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    });
    const node = key => page.locator(`[data-node-key="${keys.get(key)}"]`);
    const edge = key => page.locator(`path[data-edge-key="${key}"]`);
    const anchors = async () => {
      const targets = Object.fromEntries(fixtures[fixture].edges.map(edge => [edge.key, edge.target_key]));
      const failures = await page.evaluate(targets => [...document.querySelectorAll("path[data-edge-key]")].flatMap(path => {
        const target = document.querySelector(`[data-node-key="${targets[path.dataset.edgeKey]}"]`);
        const end = path.getPointAtLength(path.getTotalLength());
        const point = new DOMPoint(end.x, end.y).matrixTransform(path.getScreenCTM());
        const bounds = target.getBoundingClientRect();
        return Math.min(Math.abs(point.x - bounds.left), Math.abs(point.x - bounds.right)) > 1.5 || point.y < bounds.top || point.y > bounds.bottom ? [path.dataset.edgeKey] : [];
      }), targets);
      assert.deepEqual(failures, []); checks++;
    };
    for (const depth of [1, 2]) {
      await page.goto(`${base}/knowledge-graph?focus=${keys.get("service:home")}&depth=${depth}`);
      await edge("home").waitFor({ state: "attached" });
      assert.equal(await page.locator(".dependency-presentation").count(), 0);
      assert.equal(await page.locator("path[data-edge-key]").count(), 2);
      assert.match(await edge("home").getAttribute("d"), / C/); checks++;
      await anchors();
      await page.screenshot({ path: `${output}/${theme}-${width}-singleton-depth-${depth}.png`, fullPage: true });
    }
    fixture = "ha";
    await page.goto(`${base}/knowledge-graph?focus=${keys.get("service:dns")}`);
    await page.locator('[data-group-id="ha"]').waitFor();
    assert.equal(await page.locator(".dependency-presentation").count(), 1);
    assert.equal(await edge("control").count(), 0); checks++;
    await anchors();
    await page.screenshot({ path: `${output}/${theme}-${width}-ha-pair.png`, fullPage: true });
    fixture = "dns";
    await page.goto(`${base}/knowledge-graph?focus=${keys.get("service:dns")}`);
    await page.locator('[data-group-id="ha"]').waitFor();
    assert.equal(await page.locator(".dependency-presentation").count(), 1);
    assert.equal(await page.locator("path[data-group-connector]").count(), 1);
    assert.match(await edge("adguard1").getAttribute("d"), / C/);
    assert.notEqual((await edge("adguard1").getAttribute("d")).split(" C")[0], (await edge("adguard2").getAttribute("d")).split(" C")[0]); checks++;
    await node("asset:adguard1").click();
    assert.match(await edge("adguard2").getAttribute("class"), /selected-relationship/);
    assert.match(await edge("control").getAttribute("class"), /background-relationship/); checks++;
    await node("asset:atlas").click();
    assert.match(await edge("control").getAttribute("class"), /selected-relationship/);
    assert.match(await edge("adguard1").getAttribute("class"), /background-relationship/); checks++;
    await page.locator('[data-group-id="ha"]').click();
    assert.match(await edge("adguard1").getAttribute("class"), /selected-relationship/);
    assert.match(await page.locator("path[data-group-connector]").getAttribute("class"), /selected-relationship/); checks++;
    await node("service:dns").click(); await anchors();
    await page.screenshot({ path: `${output}/${theme}-${width}-dns.png`, fullPage: true });
    await page.locator(".graph-semantic-list > summary").click();
    const control = page.locator(".graph-semantic-list li").filter({ hasText: "Atlas DNS" });
    if (width === 390) await control.locator("summary").tap(); else { await control.locator("summary").focus(); await page.keyboard.press("Enter"); }
    await control.getByText(/Optional · If unavailable: Service degraded/).waitFor(); checks++;
    fixture = "dense";
    await page.goto(`${base}/knowledge-graph?focus=${keys.get("service:dns")}&depth=2`);
    await node("service:proxy").waitFor(); await anchors();
    await page.getByRole("button", { name: "Expand Knowledge Graph", exact: true }).click();
    const before = performance.now();
    await page.getByRole("button", { name: "Depth 3", exact: true }).click();
    await node("service:firewall").waitFor(); await anchors();
    await node("service:dns").click();
    await page.getByRole("button", { name: "Fit", exact: true }).click(); await anchors();
    await page.screenshot({ path: `${output}/${theme}-${width}-dense-depth-3-fit.png`, fullPage: true });
    await page.getByRole("button", { name: "Zoom in", exact: true }).click(); await anchors();
    await page.getByRole("button", { name: "Zoom out", exact: true }).click(); await anchors();
    const previousWidth = await page.locator(".landscape-viewport").evaluate(element => element.clientWidth);
    await page.setViewportSize({ width: width === 390 ? 900 : 1200, height: 850 });
    await page.waitForFunction(old => document.querySelector(".landscape-viewport").clientWidth !== old, previousWidth);
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await anchors(); checks++;
    await page.getByRole("button", { name: "Overview", exact: true }).click();
    await node("service:home").waitFor(); await anchors();
    console.log(`${theme} ${width}px: depth/select/Fit/zoom/resize/Overview sequence ${Math.round(performance.now() - before)}ms`);
    assert.deepEqual(errors, []); checks++;
    await context.close();
  }
  console.log(`${checks} routing browser checks passed. Screenshots: ${output}`);
} catch (error) { if (activePage) { await activePage.screenshot({ path: `${output}/failure.png`, fullPage: true }); console.error(await activePage.locator("body").innerText()); } throw error; }
finally { await browser.close(); }
