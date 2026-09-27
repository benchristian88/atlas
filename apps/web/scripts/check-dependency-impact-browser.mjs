// Isolated API fixtures: this script never writes to a real Atlas backend.
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { impactGraph } from "../tests/fixtures/dependency-impact.mjs";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const base = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3112";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-dependency-impact-browser";
await mkdir(output, { recursive: true });
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const customer = { id: id(1), name: "Homelab" }, site = { id: id(2), customer_id: customer.id, name: "Home" };
const permissions = ["assets.view", "services.view", "service_dependencies.view", "service_dependencies.manage", "business_functions.view", "customers.view", "sites.view"];
const keyMap = new Map(impactGraph.nodes.map((n, i) => [n.key, `${n.entity_type}:${id(i + 10)}`]));
const graph = { ...impactGraph, nodes: impactGraph.nodes.map(n => ({ ...n, key: keyMap.get(n.key), entity_id: keyMap.get(n.key).split(":")[1], customer_id: customer.id, site_id: site.id })), edges: impactGraph.edges.map((e, i) => ({ ...e, edge_id: id(i + 100), source_key: keyMap.get(e.source_key), target_key: keyMap.get(e.target_key) })) };
for (const n of graph.nodes) n.href = `/${n.entity_type === "service" ? "services" : n.entity_type === "asset" ? "assets" : "business-functions"}/${n.entity_id}`;
const home = graph.nodes.find(n => n.name === "Home Automation"), dns = graph.nodes.find(n => n.name === "DNS"), ha = graph.nodes.find(n => n.name === "homeassistant"), adguard = graph.nodes.find(n => n.name === "AdGuard Home");
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
let checks = 0;
let activePage;
try {
  for (const width of [1440, 900, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, hasTouch: width === 390, reducedMotion: "reduce" });
    const page = await context.newPage(); activePage = page; page.setDefaultTimeout(10000);
    const errors = []; page.on("pageerror", e => errors.push(e.message));
    let groups = [{ id: "ha", name: "DNS HA", strategy: "any", requirement: "required", failure_effect: "unavailable", asset_dependency_ids: [id(102), id(103)], service_dependency_ids: [], service_id: dns.entity_id }, { id: "control", name: "Control plane", strategy: "all", requirement: "optional", failure_effect: "degraded", asset_dependency_ids: [id(104)], service_dependency_ids: [], service_id: dns.entity_id }];
    let changes = [];
    let canManage = true;
    const dependencies = (service, kind) => graph.edges.filter(e => e.source_key === service.key && e.edge_family === (kind === "asset" ? "service_asset" : "service_service")).map(e => {
      const target = graph.nodes.find(n => n.key === e.target_key);
      const group = groups.find(g => [...g.asset_dependency_ids, ...g.service_dependency_ids].includes(e.edge_id));
      return { id: e.edge_id, source_service_id: service.entity_id, asset_id: target.entity_id, target_service_id: target.entity_id, asset_name: target.name, target_service_name: target.name, source_label: e.label, required_for_operation: e.dependency_requirement === "required", dependency_group_id: group?.id || null, dependency_group_name: group?.name, dependency_requirement: group?.requirement || e.dependency_requirement, failure_effect: group?.failure_effect || "unknown", dependency_strategy: group?.strategy };
    });
    await page.route("**/api/**", async route => {
      const request = route.request(), url = new URL(request.url()), path = url.pathname.replace(/^\/api/, "");
      let body = [];
      if (path === "/auth/me") body = { id: id(99), display_name: "Fixture tester", email: "fixture@example.test", permissions: permissions.filter(p => canManage || p !== "service_dependencies.manage"), assignments: [{ scope_type: "global", permissions: permissions.filter(p => canManage || p !== "service_dependencies.manage") }] };
      else if (path === "/context") body = { customers: [customer], sites: [site], global_access: true, selected_customer_id: customer.id, selected_site_id: site.id };
      else if (request.method() === "POST" && path.endsWith("/dependency-groups")) {
        body = { ...request.postDataJSON(), id: `created-${changes.length}`, service_id: path.split("/")[2] }; groups.push(body); changes.push({ method: "POST", body });
      } else if (request.method() === "PATCH" && path.startsWith("/dependency-groups/")) {
        const group = groups.find(g => g.id === path.split("/")[2]); assert.ok(group);
        const patch = request.postDataJSON(); body = { ...group, ...patch }; groups = groups.map(g => g === group ? body : g); changes.push({ method: "PATCH", body: patch });
      } else if (path.startsWith("/operational-graph")) body = graph;
      else if (path === "/dependency-analysis") {
        const focus = graph.nodes.find(n => n.entity_id === request.postDataJSON().focus_id);
        const isHome = focus.key === ha.key, service = isHome ? home : dns;
        const edges = graph.edges.filter(e => e.source_key === service.key && (isHome ? e.key === "home" : e.dependency_group_id === "ha"));
        const reason = { key: "reason", dependency_group_name: isHome ? "Home provider" : "DNS HA", dependency_strategy: isHome ? "all" : "any", dependency_requirement: "required", failure_effect: "unavailable", satisfaction: isHome ? "unsatisfied" : "satisfied", consequence: isHome ? "unavailable" : "unaffected", code: isHome ? "set_unsatisfied" : "set_satisfied", summary: "Original engine explanation retained.", members: edges.map(e => ({ edge: e, entity: graph.nodes.find(n => n.key === e.target_key), state: e.target_key === focus.key ? "unavailable" : "unaffected" })) };
        body = { focus, focus_key: focus.key, assumption: "Hypothetical scenario over recorded knowledge.", results: [{ service, state: reason.consequence, classification: "direct", distance: 1, reasons: [reason], paths: [{ nodes: [service, focus], edges: [edges[0]] }] }], truncated: false, warnings: [] };
      } else if (path.startsWith("/services/")) {
        const parts = path.split("/"), service = graph.nodes.find(n => n.entity_id === parts[2]);
        if (service) {
          if (parts.length === 3) body = { ...service, id: service.entity_id, lifecycle_status: "active", operational_status: "unknown" };
          else if (parts[3] === "asset-dependencies") body = dependencies(service, "asset");
          else if (parts[3] === "service-dependencies") body = dependencies(service, "service");
          else if (parts[3] === "dependency-groups") body = groups.filter(g => g.service_id === service.entity_id);
          else if (parts[3] === "graph") body = { nodes: [], edges: [] };
        }
      }
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.goto(`${base}/services/${home.entity_id}`);
    const impact = page.getByRole("region", { name: "Dependency impact", exact: true });
    const singleton = impact.locator("article").filter({ has: page.getByText("homeassistant", { exact: true }) });
    await singleton.getByRole("button", { name: "Service unavailable", exact: true }).click();
    await singleton.getByRole("button", { name: "Service unavailable", exact: true, pressed: true }).waitFor();
    assert.equal(changes[0].method, "POST"); assert.equal(changes[0].body.strategy, "all"); checks++;
    await singleton.getByRole("button", { name: "Service degraded", exact: true }).focus(); await page.keyboard.press("Enter");
    await singleton.getByRole("button", { name: "Service degraded", exact: true, pressed: true }).waitFor();
    assert.deepEqual(changes.at(-1), { method: "PATCH", body: { failure_effect: "degraded" } }); checks++;
    await singleton.getByLabel("Requirement for homeassistant").selectOption("optional");
    await singleton.getByText("Optional dependency", { exact: false }).waitFor();
    assert.deepEqual(changes.at(-1).body, { requirement: "optional" }); checks++;
    await page.screenshot({ path: `${output}/service-home-${width}.png`, fullPage: true });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)); checks++;
    await impact.getByText("Combine providers for the same capability", { exact: true }).click();
    const createGroup = impact.locator("form").first();
    await createGroup.getByLabel("Unclassified provider", { exact: true }).check();
    await createGroup.getByLabel("DNS", { exact: true }).check();
    await createGroup.getByLabel("Group name (optional)").fill("Shared capability");
    await createGroup.getByRole("combobox", { name: /Requirement/ }).selectOption("optional");
    await createGroup.getByRole("button", { name: "Save dependency impact" }).click();
    await impact.getByText("Shared capability", { exact: true }).waitFor();
    assert.equal(changes.at(-1).body.asset_dependency_ids.length, 1);
    assert.equal(changes.at(-1).body.service_dependency_ids.length, 1);
    assert.equal(changes.at(-1).body.requirement, "optional"); checks++;
    await page.goto(`${base}/services/${dns.entity_id}`);
    const multi = impact.locator("article").filter({ has: page.getByText("DNS HA", { exact: true }) });
    await multi.getByLabel("How do these providers work together?").selectOption("all");
    await multi.getByText("Required · All required", { exact: true }).waitFor();
    assert.deepEqual(changes.at(-1).body, { strategy: "all" }); checks++;
    await multi.getByLabel("How do these providers work together?").selectOption("any");
    await multi.getByText("Required · Any one is sufficient", { exact: true }).waitFor();
    await impact.getByText("Advanced configuration", { exact: true }).click();
    await impact.locator("summary").filter({ hasText: "DNS HA ·" }).click();
    const advanced = impact.locator("details").filter({ has: page.locator("summary").filter({ hasText: /^DNS HA ·/ }) }).last().locator("form");
    await advanced.getByLabel("Group name (optional)").fill("DNS availability");
    await advanced.getByRole("button", { name: "Save dependency impact" }).click();
    await impact.getByText("DNS availability", { exact: true }).waitFor(); checks++;
    await page.screenshot({ path: `${output}/service-dns-${width}.png`, fullPage: true });
    for (const depth of [1, 2]) {
      await page.goto(`${base}/knowledge-graph?focus=${dns.key}&depth=${depth}`);
      await page.locator(".dependency-presentation").filter({ hasText: "DNS HA" }).waitFor();
      assert.equal(await page.locator(".dependency-presentation").filter({ hasText: "Control plane" }).count(), 0); checks++;
      await page.locator(".graph-semantic-list > summary").click();
      const control = page.locator(".graph-semantic-list li").filter({ hasText: "Atlas DNS" });
      if (width === 390) await control.locator("summary").tap(); else { await control.locator("summary").focus(); await page.keyboard.press("Enter"); }
      await control.getByText(/Optional · If unavailable: Service degraded/).waitFor(); checks++;
      await page.screenshot({ path: `${output}/graph-dns-depth-${depth}-${width}.png`, fullPage: true });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)); checks++;
    }
    await page.goto(`${base}/knowledge-graph`);
    await page.locator(".dependency-presentation").filter({ hasText: "DNS HA" }).waitFor();
    assert.equal(await page.locator(".dependency-presentation").count(), 2); checks++;
    await page.screenshot({ path: `${output}/graph-dense-${width}.png`, fullPage: true });
    for (const [focus, service, text] of [[ha, home, "Home Automation becomes unavailable because homeassistant is unavailable"], [adguard, dns, "AdGuard Home 2 can still satisfy DNS HA"]]) {
      await page.goto(`${base}/knowledge-graph?focus=${focus.key}&analysis=unavailable`);
      await page.locator(`[data-node-key="${service.key}"]`).click();
      await page.locator(".graph-inspector").getByText(text, { exact: false }).waitFor();
      await page.locator(".graph-inspector summary").filter({ hasText: "Technical details" }).click();
      await page.getByText("Original engine explanation retained.").waitFor(); checks++;
    }
    canManage = false;
    await page.goto(`${base}/services/${home.entity_id}`);
    await impact.waitFor();
    assert.equal(await impact.getByRole("button").count(), 0); checks++;
    assert.deepEqual(errors, []);
    await context.close();
  }
  console.log(`${checks} browser assertions passed; screenshots: ${output}`);
} catch (error) { if (activePage) { await activePage.screenshot({ path: `${output}/failure.png`, fullPage: true }); console.error(await activePage.locator("body").innerText()); } throw error; } finally { await browser.close(); }
