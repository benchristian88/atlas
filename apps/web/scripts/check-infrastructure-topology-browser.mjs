// Isolated browser fixtures; never writes to live Atlas knowledge.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { mkdir } from "node:fs/promises";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const base = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3108";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-topology-browser-results";
await mkdir(output, { recursive: true });
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const customer = { id: id(1), name: "Homelab", status: "active" };
const site = { id: id(2), customer_id: customer.id, name: "Home", status: "active" };
const permissions = ["assets.view", "assets.create", "asset_types.view", "asset_types.manage", "customers.view", "sites.view", "networks.view", "relationships.view"];
const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aSawAAAAASUVORK5CYII=", "base64");
function fixture() {
  const categories = [{ id: id(3), key: "hardware", name: "Infrastructure", show_in_topology: true, active: true, sort_order: 0 }, { id: id(4), key: "workload", name: "Workload", show_in_topology: true, active: true, sort_order: 10 }, { id: id(5), key: "uncategorized", name: "Uncategorized", show_in_topology: false, active: true, sort_order: 100 }, ...Array.from({ length: 8 }, (_, n) => ({ id: id(6+n), key: `custom_${n}`, name: `Custom Category ${n}`, active: true, show_in_topology: true, sort_order: 100 }))];
  const types = [{ id: id(20), key: "server", name: "Server", category_id: id(3), category: "Infrastructure", active: true }, { id: id(21), key: "docker_compose", name: "Docker Compose", category_id: id(4), category: "Workload", active: true }, { id: id(22), key: "unknown", name: "Unknown", category_id: id(5), category: "Uncategorized", active: true }];
  const asset = (n, name, type = "server") => ({ id: id(n), name, asset_type: type, customer_id: customer.id, site_id: site.id, status: "operational", hostname: `${name.toLowerCase().replaceAll(" ", "-")}.home`, cached_icon_url: `/api/assets/${id(n)}/icon?v=${"a".repeat(64)}` });
  const hosts = [asset(30, "PVE1"), asset(31, "PVE2"), asset(32, "PVE3"), asset(33, "PVE4")];
  const children = Array.from({ length: 30 }, (_, i) => asset(100+i, i ? `Workload ${String(i).padStart(2,"0")}` : "AdGuard Home", "docker_compose"));
  const assets = [...hosts, asset(34,"PBS"), asset(35,"Synology"), asset(36,"Switch"), asset(37,"Router"), ...children, asset(150,"Uncategorized Asset","unknown")];
  const relationships = children.map((a,i) => ({ id: id(200+i), source_asset_id: a.id, target_asset_id: hosts[i < 20 ? 0 : i < 24 ? 1 : i < 27 ? 2 : 3].id, relationship_type: "runs_on" }));
  const networks = ["Default", "Main", "IoT", "Apps", "Infra", "Management", ...Array.from({length: 8}, (_,i)=>`Extra ${i}`)].map((name,i) => ({ id: id(300+i), name, vlan_id: i===5 ? 99 : i, cidr: `10.0.${i===5?99:i}.0/24`, gateway: `10.0.${i===5?99:i}.1`, customer_id: customer.id, site_id: site.id }));
  const asset_interfaces = [{ id: id(400), asset_id: children[0].id, network_id: networks[5].id, name: "eth0", ip_address: "10.0.99.5", mac_address: "02:00:00:00:00:05", is_primary: true }, { id: id(401), asset_id: children[0].id, network_id: networks[3].id, name: "eth1", ip_address: "10.0.3.5" }];
  return { categories, asset_types: types, assets, relationships, relationship_types: [{ key: "runs_on", name: "Runs on", source_label: "Runs on", directional: true }], networks, asset_interfaces, customers: [customer], sites: [site], platform_links: relationships.map(r => ({ relationship_id: r.id, parent_id: r.target_asset_id, child_id: r.source_asset_id })) };
}
function graphFixture(data, params) {
  const focus = params.get("focus_asset_id"), depth = Number(params.get("hops")), networks = params.get("show_networks") === "true";
  const categoryIds = params.getAll("category_ids");
  const assets = data.assets.filter(a => categoryIds.includes(data.asset_types.find(t => t.key === a.asset_type).category_id));
  const keys = new Set(assets.map(a=>`asset:${a.id}`));
  const edges = data.relationships.filter(r => keys.has(`asset:${r.source_asset_id}`) && keys.has(`asset:${r.target_asset_id}`)).map(r => ({ key: `relationship:${r.id}`, source_key: `asset:${r.source_asset_id}`, target_key: `asset:${r.target_asset_id}`, kind: "relationship", label: "Runs on", directional: true }));
  if (networks) for (const i of data.asset_interfaces.filter(i => keys.has(`asset:${i.asset_id}`))) edges.push({ key: `interface:${i.id}`, source_key: `asset:${i.asset_id}`, target_key: `network:${i.network_id}`, label: [i.name,i.ip_address].filter(Boolean).join(" · "), kind: "membership", directional: false });
  const distance = new Map([[`asset:${focus}`,0]]);
  for (let d=0; d<depth; d++) for (const e of edges) {
    if (distance.get(e.source_key) === d && !distance.has(e.target_key)) distance.set(e.target_key,d+1);
    if (distance.get(e.target_key) === d && !distance.has(e.source_key)) distance.set(e.source_key,d+1);
  }
  const nodes = [...distance].slice(0,25).map(([key,d]) => { const [entity_type, entity_id] = key.split(":"); return { key, entity_type, entity_id, distance: d, name: (entity_type === "asset" ? assets : data.networks).find(n=>n.id === entity_id).name }; });
  const visible = new Set(nodes.map(n=>n.key));
  return { focus_key: `asset:${focus}`, nodes, edges: edges.filter(e=>visible.has(e.source_key)&&visible.has(e.target_key)), truncated: distance.size >25 };
}
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
let checks = 0;
try {
  for (const theme of ["light", "dark"]) for (const width of [1440, 1100, 800]) {
    const data = fixture();
    const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme, reducedMotion: "reduce" });
    const page = await context.newPage(), errors = [], requests = [];
    page.setDefaultTimeout(10000);
    page.on("pageerror",e=>{ errors.push(e.message); console.error(e.message); });
    await page.route("**/api/**", async route => {
      const url = new URL(route.request().url()); requests.push(url.pathname+url.search);
      if (url.pathname.endsWith("/icon")) return route.fulfill({ contentType: "image/png", body: png });
      const method = route.request().method();
      if (url.pathname === "/api/asset-categories" && method === "POST") {
        const payload = route.request().postDataJSON();
        const created = { ...payload, id: id(800), asset_types_count: 0 };
        data.categories.push(created);
        return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(created) });
      }
      if (url.pathname === `/api/asset-categories/${id(800)}` && method === "PATCH") {
        const payload = route.request().postDataJSON();
        assert.ok(!("key" in payload), "Category key stays immutable in edits");
        const record = data.categories.find(c => c.id === id(800));
        Object.assign(record, payload);
        return route.fulfill({ contentType: "application/json", body: JSON.stringify(record) });
      }
      if (url.pathname === `/api/asset-categories/${id(800)}` && method === "DELETE") {
        data.categories = data.categories.filter(c => c.id !== id(800));
        return route.fulfill({ status: 204 });
      }
      if (url.pathname === "/api/asset-types" && method === "POST") {
        const payload = route.request().postDataJSON();
        assert.ok(payload.category_id && !("category" in payload));
        const created = { ...payload, id: id(801), category: data.categories.find(c=>c.id===payload.category_id).name, in_use_count: 0 };
        data.asset_types.push(created);
        return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(created) });
      }
      let body = [];
      if (url.pathname === "/api/auth/me") body = { id: id(999), display_name: "Topology fixture", email: "fixture@example.test", theme_mode: theme, permissions, assignments: [{ scope_type: "global", permissions }] };
      else if (url.pathname === "/api/context") body = { customers: [customer], sites: [site], global_access: true, selected_customer_id: customer.id, selected_site_id: site.id };
      else if (url.pathname === "/api/topology") body = data;
      else if (url.pathname === "/api/topology/connectivity") body = graphFixture(data,url.searchParams);
      else if (url.pathname === "/api/asset-categories") body = data.categories;
      else if (url.pathname === "/api/asset-types") body = data.asset_types;
      else if (url.pathname === "/api/assets/summary") body = { total: data.assets.length, by_asset_type: data.asset_types.map(t=>({ asset_type_id:t.id, asset_type_name:t.name, count:data.assets.filter(a=>a.asset_type===t.key).length })) };
      else if (url.pathname === "/api/assets") body = data.assets.filter(a=> !url.searchParams.get("category_id") || data.asset_types.find(t=>t.key===a.asset_type)?.category_id === url.searchParams.get("category_id")).slice(0,31);
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.goto(`${base}/topology`);
    await page.getByRole("heading", { name:"Environment at a glance" }).waitFor();
    assert.equal(await page.locator(".topology-metrics strong").first().innerText(), "38");
    assert.equal(await page.locator(".topology-summary-row").count(), 10);
    await page.getByRole("button",{name:"Filters",exact:true}).click();
    await page.getByLabel("Uncategorized", {exact:true}).check();
    assert.equal(await page.locator(".topology-metrics strong").first().innerText(), "39");
    await page.getByLabel("Uncategorized", {exact:true}).uncheck();
    await page.getByRole("button",{name:"Platform",exact:true}).click();
    const pve = page.locator(`[data-platform-id="${id(30)}"]`);
    assert.equal(await pve.locator(".topology-child").count(),8);
    await pve.getByRole("button",{name:"Show all 20 (+12 more)",exact:true}).click();
    assert.equal(await pve.locator(".topology-child").count(),20);
    await pve.getByRole("button",{name:"Show fewer",exact:true}).click();
    const platformGeometry = await page.locator(".topology-platform-card").evaluateAll(nodes=>nodes.map(n=>({top:n.getBoundingClientRect().top,left:n.getBoundingClientRect().left})));
    assert.ok(new Set(platformGeometry.map(n=>Math.round(n.top))).size >1,"Cards wrap into multiple rows");
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),"No page horizontal scroll");
    await page.getByLabel("Search Assets",{exact:true}).fill("AdGuard");
    assert.equal(await page.locator(".topology-platform-card").count(),1);
    await page.getByLabel("Search Assets",{exact:true}).fill("Workload 19");
    assert.match(await pve.locator(".topology-children").innerText(), /Workload 19/);
    await page.getByLabel("Search Assets",{exact:true}).fill("");
    const expand = page.getByRole("button",{name:"Expand Infrastructure Topology",exact:true});
    const close = page.getByRole("button",{name:"Close expanded Infrastructure Topology",exact:true});
    const beforeExpand = requests.length;
    await expand.click(); await close.waitFor();
    assert.equal(await page.locator("dialog").evaluate(el=>el.matches(":modal")),true);
    assert.equal(await page.evaluate(()=>document.body.style.position),"fixed");
    assert.equal(requests.length,beforeExpand);
    await page.screenshot({ path:`${output}/platform-${theme}-${width}.png`,fullPage:true });
    await page.keyboard.press("Escape"); await expand.waitFor();
    assert.equal(await page.evaluate(()=>document.body.style.position),"");
    await page.getByRole("button",{name:"Network & VLAN",exact:true}).click();
    assert.equal(await page.locator(".topology-network-list button").count(),14);
    await page.locator(".topology-network-list").getByRole("button",{name:/Management/}).click();
    assert.match(await page.locator(".topology-network-detail").innerText(),/10.0.99.5/);
    assert.match(await page.locator(".topology-network-detail").innerText(),/eth0/);
    await page.locator(".topology-network-list").getByRole("button",{name:/^Apps/}).click();
    assert.match(await page.locator(".topology-network-detail").innerText(),/AdGuard Home/);
    assert.match(await page.locator(".topology-network-detail").innerText(),/10.0.3.5/);
    await expand.click(); await close.waitFor();
    assert.match(await page.locator(".topology-network-detail").innerText(),/10.0.3.5/);
    await close.click();
    await page.getByRole("button",{name:"Connectivity",exact:true}).click();
    await page.getByLabel("Focus Asset",{exact:true}).selectOption(id(100)).catch(async e => { await page.screenshot({ path: `${output}/failure.png` }); console.error(await page.locator("body").innerText()); throw e; });
    await page.locator(`[data-node-key="asset:${id(100)}"]`).waitFor();
    assert.equal(await page.locator("[data-node-key]").count(),4);
    await page.locator(`[data-node-key="asset:${id(30)}"]`).click();
    assert.equal(await page.locator('[aria-label="Topology inspector"] h2').innerText(),"PVE1");
    assert.equal(await page.getByRole("link",{name:"Open Asset",exact:true}).getAttribute("href"),`/assets/${id(30)}`);
    assert.equal(await page.getByRole("link",{name:"View in Knowledge Graph",exact:true}).getAttribute("href"),`/knowledge-graph?focus=asset:${id(30)}&depth=1`);
    await page.getByRole("button",{name:"2 hops",exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll("[data-node-key]").length>4);
    assert.ok(await page.locator("[data-node-key]").count()<=25);
    await page.getByLabel("Infrastructure",{exact:true}).uncheck();
    await page.locator(`[data-node-key="asset:${id(30)}"]`).waitFor({state:"detached"});
    await page.getByLabel("Infrastructure",{exact:true}).check();
    await page.locator(`[data-node-key="asset:${id(30)}"]`).waitFor();
    await page.getByRole("button",{name:"1 hop",exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll("[data-node-key]").length===4);
    const beforeGraphExpand = requests.length;
    await expand.click(); await close.waitFor();
    assert.equal(requests.length,beforeGraphExpand);
    assert.equal(await page.getByLabel("Focus Asset",{exact:true}).inputValue(),id(100));
    const focusBox = await page.locator(`[data-node-key="asset:${id(100)}"]`).boundingBox();
    const canvasBox = await page.locator(".topology-connectivity-viewport").boundingBox();
    assert.ok(focusBox.y + focusBox.height < 1000, "Focused Asset stays in the viewport");
    assert.ok(Math.abs(focusBox.x + focusBox.width / 2 - (canvasBox.x + canvasBox.width / 2)) < 5, "Focus remains horizontally centred");
    assert.ok(Math.abs(focusBox.y + focusBox.height / 2 - (canvasBox.y + canvasBox.height / 2)) < 5, "Focus remains vertically centred");
    assert.ok(requests.some(r => r.includes("/icon?v=")), "Shared cached icons are requested");
    await page.screenshot({ path:`${output}/connectivity-${theme}-${width}.png`,fullPage:true });
    await close.click();
    assert.deepEqual(errors,[]);
    // Managed dropdown, including an inactive currently assigned category.
    data.categories.find(c=>c.id===id(4)).active = false;
    await page.goto(`${base}/admin/asset-types`);
    const row = page.getByRole("row").filter({hasText:"Docker Compose"});
    await row.getByRole("button",{name:"Edit",exact:true}).click();
    assert.equal(await page.locator('select[name="category_id"]').inputValue(),id(4));
    assert.equal(await page.locator('input[name="category"]').count(),0);
    assert.equal(await page.locator('select[name="category_id"] option:checked').innerText(),"Workload");
    await page.goto(`${base}/assets`);
    await page.getByLabel("Asset Category",{exact:true}).selectOption(id(4));
    await page.waitForURL(/category_id=/);
    assert.equal(await page.getByLabel("Asset Category",{exact:true}).inputValue(),id(4));
    assert.deepEqual(errors,[]);
    // Exercise category and type form submissions; API invariants are separately
    // covered against PostgreSQL rather than being entrusted to this fixture.
    data.asset_types = data.asset_types.filter(t => t.key !== "docker_compose");
    data.categories.find(c=>c.id===id(4)).active = true;
    await page.goto(`${base}/admin/asset-types`);
    await page.getByRole("button", { name: "Add Asset type", exact: true }).click();
    await page.locator('input[name="key"]').fill("docker_compose");
    await page.locator('input[name="name"]').fill("Docker Compose");
    assert.equal(await page.locator('select[name="category_id"]').evaluate(el=>el.checkValidity()), false);
    await page.locator('select[name="category_id"]').selectOption(id(4));
    await page.getByRole("button", { name: "Create", exact: true }).click();
    await page.getByRole("row").filter({hasText:"Docker Compose"}).waitFor();
    await page.goto(`${base}/admin/asset-categories`);
    await page.getByRole("button", { name: "Add Asset category", exact: true }).click();
    await page.locator('input[name="key"]').fill("custom_workload");
    await page.locator('input[name="name"]').fill("Custom Workload");
    await page.locator('input[name="show_in_topology"]').uncheck();
    await page.getByRole("button", { name: "Create", exact: true }).click();
    const categoryRow = page.getByRole("row").filter({hasText:"Custom Workload"});
    await categoryRow.waitFor();
    assert.match(await categoryRow.innerText(), /Available in Filters/);
    await categoryRow.getByRole("button", {name:"Edit",exact:true}).click();
    assert.equal(await page.locator('input[name="key"]').isDisabled(),true);
    await page.locator('input[name="active"]').uncheck();
    await page.locator('input[name="show_in_topology"]').check();
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await page.waitForFunction(()=>[...document.querySelectorAll("tr")].some(r=>r.innerText.includes("Custom Workload")&&r.innerText.includes("Inactive")));
    assert.match(await categoryRow.innerText(), /By default/);
    page.once("dialog", dialog=>dialog.accept());
    await categoryRow.getByRole("button", {name:"Delete",exact:true}).click();
    await categoryRow.waitFor({state:"detached"});
    assert.equal(await page.getByRole("row").filter({hasText:"Uncategorized"}).getByRole("button", {name:"Delete",exact:true}).isDisabled(),true);
    assert.deepEqual(errors,[]);
    checks++; await context.close();
  }
  console.log(`Passed ${checks} topology browser scenarios: light/dark at 1440, 1100 and 800px; 20 children, four hosts, 14 Networks, VLAN 99, AdGuard focus, filters, icons, inspector links, managed dropdown, Assets category filter and expanded-state preservation.`);
} finally { await browser.close(); }
