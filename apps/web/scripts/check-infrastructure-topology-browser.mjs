// Isolated browser fixtures; never writes to live Atlas knowledge.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { mkdir } from "node:fs/promises";
import { contrastRatio } from "../lib/accent-theme.mjs";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const base = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3108";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-topology-browser-results";
await mkdir(output, { recursive: true });
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const customer = { id: id(1), name: "Homelab", status: "active" };
const site = { id: id(2), customer_id: customer.id, name: "Home", status: "active" };
const permissions = ["assets.view", "assets.create", "asset_types.view", "asset_types.manage", "customers.view", "sites.view", "networks.view", "networks.create", "networks.edit", "relationships.view"];
const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aSawAAAAASUVORK5CYII=", "base64");
function fixture() {
  const categories = [{ id: id(3), key: "hardware", name: "Compute", icon_key: "server", accent_key: "blue", show_in_topology: true, active: true, sort_order: 0 }, { id: id(4), key: "workload", name: "Workload", icon_key: "cube", accent_key: "green", show_in_topology: true, active: true, sort_order: 10 }, { id: id(5), key: "uncategorized", name: "Uncategorized", icon_key: "infrastructure", accent_key: "slate", show_in_topology: false, active: true, sort_order: 100 }, ...Array.from({ length: 8 }, (_, n) => ({ id: id(6+n), key: `custom_${n}`, name: `Custom Category ${n}`, active: true, show_in_topology: true, sort_order: 100 }))];
  const types = [{ id: id(20), key: "server", name: "Server", category_id: id(3), category: "Compute", active: true }, { id: id(21), key: "docker_compose", name: "Docker Compose", category_id: id(4), category: "Workload", active: true }, { id: id(22), key: "unknown", name: "Unknown", category_id: id(5), category: "Uncategorized", active: true }];
  const asset = (n, name, type = "server") => ({ id: id(n), name, asset_type: type, customer_id: customer.id, site_id: site.id, status: "operational", hostname: `${name.toLowerCase().replaceAll(" ", "-")}.home`, cached_icon_url: `/api/assets/${id(n)}/icon?v=${"a".repeat(64)}` });
  const hosts = [asset(30, "PVE1"), asset(31, "PVE2"), asset(32, "PVE3"), asset(33, "PVE4")];
  const children = Array.from({ length: 25 }, (_, i) => asset(100+i, i === 1 ? "Atlas DNS" : i ? `Workload ${String(i).padStart(2,"0")}` : "AdGuard Home", "docker_compose"));
  const assets = [...hosts, asset(34,"PBS"), asset(35,"Synology"), asset(36,"USW-16-poe"), asset(37,"Router"), ...children, asset(150,"Uncategorized Asset","unknown")];
  const relationships = children.map((a,i) => ({ id: id(200+i), source_asset_id: a.id, target_asset_id: hosts[i < 20 ? 0 : i < 24 ? 1 : i < 27 ? 2 : 3].id, relationship_type: "runs_on" }));
  const platform_links = relationships.map(r => ({ relationship_id: r.id, parent_id: r.target_asset_id, child_id: r.source_asset_id }));
  for (const [source, target] of [[30,36], [31,36], [36,34], [36,35], [36,37], [36,32], [36,110], [36,111], [36,112]]) relationships.push({ id: id(500+relationships.length), source_asset_id: id(source), target_asset_id: id(target), relationship_type: "connects_to" });
  const networks = ["Default", "Main", "IoT", "Apps", "Infra", "Management", ...Array.from({length: 8}, (_,i)=>`Extra ${i}`)].map((name,i) => ({ id: id(300+i), name, network_type: "vlan", icon_key: "network", accent_key: ["blue", "teal", "purple", "orange", "red", "blue"][i] || "slate", vlan_id: i===5 ? 99 : i, cidr: `10.0.${i===5?99:i}.0/24`, gateway: `10.0.${i===5?99:i}.1`, customer_id: customer.id, site_id: site.id }));
  const asset_interfaces = [{ id: id(400), asset_id: children[0].id, network_id: networks[5].id, name: "eth0", ip_address: "10.0.99.5", mac_address: "02:00:00:00:00:05", is_primary: true }, { id: id(401), asset_id: children[0].id, network_id: networks[3].id, name: "eth1", ip_address: "10.0.3.5" }];
  asset_interfaces.push({ id: id(402), asset_id: hosts[0].id, network_id: null, name: "vmbr0", ip_address: "10.0.99.21" });
  for (let i=1; i<20; i++) asset_interfaces.push({ id: id(410+i), asset_id: children[i].id, network_id: networks[5].id, name: "eth0", ip_address: `10.0.99.${100+i}` });
  assets.forEach(a => { a.ip_address = "192.0.2.254"; });
  return { categories, asset_types: types, assets, relationships, relationship_types: [{ key: "runs_on", name: "Runs on", source_label: "Runs on", directional: true }, { key: "connects_to", name: "Connects to", source_label: "Connects to", directional: false }], networks, asset_interfaces, customers: [customer], sites: [site], platform_links };
}
function graphFixture(data, params) {
  // Exercise the production traversal instead of maintaining a second algorithm.
  const api = fileURLToPath(new URL("../../api/", import.meta.url));
  return JSON.parse(execFileSync(process.env.ATLAS_PYTHON || `${api}.venv/bin/python`, ["-c", `
import json, sys
from app.services.infrastructure_topology import connectivity
payload = json.load(sys.stdin)
print(json.dumps(connectivity(**payload)))
`], { cwd: api, encoding: "utf8", input: JSON.stringify({ topology: data, focus_id: params.get("focus_asset_id"), focus_network_id: params.get("focus_network_id"), hops: Number(params.get("hops")), show_networks: params.get("show_networks") === "true", category_ids: params.getAll("category_ids"), limit: 25 }) }));
}

async function checkIdentityContrast(page) {
  const colours = await page.locator(".infrastructure-topology .presentation-icon").evaluateAll(els=>els.map(el=>{
    const style=getComputedStyle(el);
    return {foreground:style.color,background:style.backgroundColor};
  }));
  const hex = rgb=>"#" + rgb.match(/[\d.]+/g).slice(0,3).map(n=>Math.round(Number(n)).toString(16).padStart(2,"0")).join("");
  assert.ok(colours.length);
  for (const colour of colours) assert.ok(contrastRatio(hex(colour.foreground),hex(colour.background))>=4.5,JSON.stringify(colour));
}

async function checkGeometry(page) {
  const boxes = await page.locator("[data-node-key]").evaluateAll(nodes => nodes.map(node => {
    const b = node.getBoundingClientRect();
    return { key: node.dataset.nodeKey, x: b.x, y: b.y, right: b.right, bottom: b.bottom,
      icons: [...node.querySelectorAll(".asset-icon, .asset-icon img, .presentation-icon")].map(icon => { const r = icon.getBoundingClientRect(); return { x: r.x, y: r.y, right: r.right, bottom: r.bottom }; }) };
  }));
  for (const [i, a] of boxes.entries()) {
    for (const icon of a.icons) assert.ok(icon.x >= a.x - 1 && icon.y >= a.y - 1 && icon.right <= a.right + 1 && icon.bottom <= a.bottom + 1, `Icon outside ${a.key}`);
    for (const b of boxes.slice(i+1)) assert.ok(a.right <= b.x || b.right <= a.x || a.bottom <= b.y || b.bottom <= a.y, `Overlap ${a.key}/${b.key}`);
  }
}

const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
let checks = 0;
try {
  for (const theme of ["light", "dark"]) for (const width of [1440, 1100, 800]) {
    const data = fixture();
    data.categories.slice(0,2).forEach(c=>{ c.icon_key="infrastructure"; c.accent_key="slate"; });
    data.networks.slice(0,6).forEach(n=>{ n.accent_key="blue"; });
    const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme, reducedMotion: "reduce" });
    const page = await context.newPage(), errors = [], requests = [];
    page.setDefaultTimeout(10000);
    page.on("pageerror",e=>{ errors.push(e.message); console.error(e.message); });
    await page.route("**/api/**", async route => {
      const url = new URL(route.request().url()); requests.push(url.pathname+url.search);
      if (url.pathname.endsWith("/icon")) return url.pathname.includes(id(31)) ? route.fulfill({ status: 404, body: "" }) : route.fulfill({ contentType: "image/png", body: png });
      const method = route.request().method();
      if (url.pathname === "/api/asset-categories" && method === "POST") {
        const payload = route.request().postDataJSON();
        const created = { ...payload, id: id(800), asset_types_count: 0 };
        data.categories.push(created);
        return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(created) });
      }
      if (url.pathname.startsWith("/api/asset-categories/") && method === "PATCH") {
        const payload = route.request().postDataJSON();
        assert.ok(!("key" in payload), "Category key stays immutable in edits");
        const record = data.categories.find(c => c.id === url.pathname.split("/").at(-1));
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
        const created = { ...payload, id: id(801 + data.asset_types.length), category: data.categories.find(c=>c.id===payload.category_id).name, in_use_count: 0 };
        data.asset_types.push(created);
        return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(created) });
      }
      if (url.pathname.startsWith("/api/networks/") && method === "PATCH") {
        const record = data.networks.find(n => n.id === url.pathname.split("/").at(-1));
        Object.assign(record, route.request().postDataJSON());
        return route.fulfill({ contentType:"application/json", body:JSON.stringify(record) });
      }
      if (url.pathname === "/api/networks" && method === "POST") {
        const record = {...route.request().postDataJSON(), id:id(850)};
        data.networks.push(record);
        return route.fulfill({status:201, contentType:"application/json", body:JSON.stringify(record)});
      }
      let body = [];
      if (url.pathname === "/api/auth/me") body = { id: id(999), display_name: "Topology fixture", email: "fixture@example.test", theme_mode: theme, permissions, assignments: [{ scope_type: "global", permissions }] };
      else if (url.pathname === "/api/context") body = { customers: [customer], sites: [site], global_access: true, selected_customer_id: customer.id, selected_site_id: site.id };
      else if (url.pathname === "/api/topology") body = data;
      else if (url.pathname === "/api/topology/connectivity") body = graphFixture(data,url.searchParams);
      else if (url.pathname === "/api/networks") body = data.networks;
      else if (url.pathname === "/api/customers") body = [customer];
      else if (url.pathname === "/api/sites") body = [site];
      else if (url.pathname === "/api/asset-categories") body = data.categories;
      else if (url.pathname === "/api/asset-types") body = data.asset_types;
      else if (url.pathname === "/api/assets/summary") body = { total: data.assets.length, by_asset_type: data.asset_types.map(t=>({ asset_type_id:t.id, asset_type_name:t.name, count:data.assets.filter(a=>a.asset_type===t.key).length })) };
      else if (url.pathname === "/api/assets") body = data.assets.filter(a=> !url.searchParams.get("category_id") || data.asset_types.find(t=>t.key===a.asset_type)?.category_id === url.searchParams.get("category_id")).slice(0,31);
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    });
    // Exercise administrator edits before checking all four topology surfaces.
    await page.goto(`${base}/admin/asset-categories`);
    for (const [name, icon, accent] of [["Compute", "server", "blue"], ["Workload", "cube", "green"]]) {
      const row = page.getByRole("row").filter({ has: page.getByRole("cell", {name, exact:true}) });
      await row.getByRole("button", {name:"Edit", exact:true}).click();
      await page.locator(`input[name="icon_key"][value="${icon}"]`).check();
      await page.locator(`input[name="accent_key"][value="${accent}"]`).check();
      await page.getByRole("button", {name:"Save changes", exact:true}).click();
      await page.locator(".resource-form").waitFor({state:"detached"});
    }
    await page.goto(`${base}/networks`);
    for (const [name, accent] of [["Management", "blue"], ["IoT", "purple"], ["Apps", "orange"], ["Infra", "red"]]) {
      const row = page.getByRole("row").filter({ has: page.getByRole("cell", {name, exact:true}) });
      await row.getByRole("button", {name:"Edit", exact:true}).click();
      await page.locator('input[name="icon_key"][value="network"]').check();
      await page.locator(`input[name="accent_key"][value="${accent}"]`).check();
      await page.getByRole("button", {name:"Save changes", exact:true}).click();
      await page.locator(".resource-form").waitFor({state:"detached"});
    }
    await page.goto(`${base}/topology`);
    await page.getByRole("heading", { name:"Environment at a glance" }).waitFor();
    assert.equal(await page.locator(".topology-metrics strong").first().innerText(), "33");
    assert.equal(await page.locator(".topology-summary-row").count(), 10);
    const workloadSummary = page.locator(".topology-summary-row").filter({ has: page.getByRole("link", {name:"View all Workload Assets", exact:true}) });
    assert.match(await workloadSummary.innerText(), /25 Assets/);
    assert.equal(await workloadSummary.getAttribute("data-presentation-accent"), "green");
    assert.equal(await workloadSummary.locator("[data-presentation-icon]").getAttribute("data-presentation-icon"), "cube");
    assert.deepEqual(await page.locator(".topology-metrics [data-presentation-accent]").evaluateAll(els=>els.map(el=>el.dataset.presentationAccent)), ["blue","cyan","teal","purple"]);
    await checkIdentityContrast(page);
    await page.screenshot({path:`${output}/overview-${theme}-${width}.png`,fullPage:true});
    assert.equal(await workloadSummary.locator(".asset-icon").count(), 6);
    assert.equal(await workloadSummary.locator(".topology-preview-more").innerText(), "+19");
    assert.equal(await page.getByRole("button", { name:"Close details", exact:true }).count(), 0);
    const preview = workloadSummary.getByRole("link", {name:"Open AdGuard Home",exact:true});
    assert.equal(await preview.getAttribute("href"), `/assets/${id(100)}`);
    // Check native navigation without depending on unrelated Asset detail fixtures.
    await page.route(`**/assets/${id(100)}`, route => route.fulfill({ contentType:"text/html", body:"<h1>Asset destination</h1>" }));
    await preview.click(); await page.waitForURL(`**/assets/${id(100)}`);
    await page.goBack(); await page.getByRole("heading", { name:"Environment at a glance" }).waitFor();
    assert.equal(await page.locator(".topology-detail-inspector").count(), 0);
    assert.equal(await page.getByRole("link", { name:/^0 more / }).count(), 0);
    assert.equal(await workloadSummary.getByRole("link", {name:"View all Workload Assets",exact:true}).getAttribute("href"), `/assets?category_id=${id(4)}`);
    const navigation = page.getByRole("link", {name:"Topology",exact:true});
    assert.equal(await navigation.getAttribute("href"), "/topology");
    assert.equal(await navigation.locator("span").evaluate(el => { const range = document.createRange(); range.selectNodeContents(el); return range.getClientRects().length; }), 1, "Sidebar label stays on one line");
    assert.equal(await page.getByRole("heading", {name:"Infrastructure Topology",exact:true}).count(), 1);
    await page.getByRole("button",{name:"Filters",exact:true}).click();
    await page.getByLabel("Uncategorized", {exact:true}).check();
    assert.equal(await page.locator(".topology-metrics strong").first().innerText(), "34");
    const smallCategory = page.locator(".topology-summary-row").filter({hasText:"Uncategorized"});
    assert.equal(await smallCategory.locator(".asset-icon").count(),1);
    assert.equal(await smallCategory.locator(".topology-preview-more").count(),0);
    await page.getByLabel("Uncategorized", {exact:true}).uncheck();
    await page.getByRole("button",{name:"Platform",exact:true}).click();
    const pve = page.locator(`[data-platform-id="${id(30)}"]`);
    assert.equal(await pve.locator(".topology-child").count(),8);
    assert.equal(await pve.getAttribute("data-presentation-accent"), "blue");
    assert.equal(await pve.locator(".topology-child").first().getAttribute("data-presentation-accent"), "green");
    assert.equal(await pve.locator(".topology-asset-identity .asset-icon").count(),9);
    assert.equal(await page.locator(".topology-platform-section > h2 [data-presentation-icon]").first().getAttribute("data-presentation-icon"), "server");
    assert.match(await pve.innerText(), /10.0.99.21/);
    assert.match(await pve.locator(".topology-child").filter({hasText:"AdGuard Home"}).innerText(), /10.0.99.5 \+1/);
    assert.doesNotMatch(await pve.innerText(), /192.0.2.254/);
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
    assert.equal(await expand.innerText(), "");
    assert.equal(await expand.getAttribute("title"), "Expand Infrastructure Topology");
    assert.equal(await expand.locator("svg").count(), 1);
    const beforeExpand = requests.filter(r => !r.includes("/icon?")).length;
    await expand.click(); await close.waitFor();
    assert.equal(await page.locator("dialog").evaluate(el=>el.matches(":modal")),true);
    assert.equal(await page.evaluate(()=>document.body.style.position),"fixed");
    assert.equal(requests.filter(r => !r.includes("/icon?")).length,beforeExpand);
    await page.screenshot({ path:`${output}/platform-${theme}-${width}.png`,fullPage:true });
    await page.keyboard.press("Escape"); await expand.waitFor();
    assert.equal(await page.evaluate(()=>document.body.style.position),"");
    await page.getByRole("button",{name:"Network & VLAN",exact:true}).click();
    assert.equal(await page.locator(".topology-network-list button").count(),14);
    for (const name of ["Main", "IoT", "Apps", "Infra", "Default", "Management"]) {
      const network = data.networks.find(n=>n.name===name);
      const row = page.locator(".topology-network-list button").filter({has:page.locator("strong",{hasText:new RegExp(`^${name}$`)})});
      assert.equal(await row.getAttribute("data-presentation-accent"),network.accent_key);
      await row.click();
      assert.equal(await page.locator(".topology-network-heading").getAttribute("data-presentation-accent"),network.accent_key);
      assert.match(await page.locator(".topology-network-detail").innerText(),new RegExp(network.cidr.replaceAll(".","\\.")));
    }
    await page.screenshot({path:`${output}/networks-${theme}-${width}.png`,fullPage:true});
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
    await page.getByLabel("Focus Asset or Network",{exact:true}).selectOption(id(100)).catch(async e => { await page.screenshot({ path: `${output}/failure.png` }); console.error(await page.locator("body").innerText()); throw e; });
    await page.locator(`[data-node-key="asset:${id(100)}"]`).waitFor();
    assert.equal(await page.locator("[data-node-key]").count(),4);
    const adguardNode = page.locator(`[data-node-key="asset:${id(100)}"]`);
    assert.equal(await adguardNode.getAttribute("data-presentation-accent"), "green");
    assert.equal(await adguardNode.locator(".asset-icon").count(), 1);
    assert.ok(await adguardNode.locator(`img[src*="${id(100)}/icon"]`).count());
    assert.equal(await page.locator(`[data-node-key="asset:${id(30)}"]`).getAttribute("data-presentation-accent"),"blue");
    assert.equal(await page.locator(`[data-node-key="network:${id(305)}"]`).getAttribute("data-presentation-accent"),"blue");
    assert.equal(await page.locator(`[data-node-key="network:${id(303)}"]`).getAttribute("data-presentation-accent"),"orange");
    assert.match(await page.locator(`[data-node-key="network:${id(305)}"]`).innerText(),/VLAN 99.*10.0.99.0\/24/s);
    assert.equal(await page.locator('.topology-connectivity-world line[stroke-dasharray="6 5"]').count(),2);
    assert.equal(await page.locator('.topology-connectivity-world line[stroke="var(--muted)"]').count(),1);
    assert.equal(await adguardNode.evaluate(el=>getComputedStyle(el).borderWidth),"2px");
    assert.notEqual(await adguardNode.evaluate(el=>getComputedStyle(el).boxShadow),"none");
    // A multihomed Asset stays green when a Network accent changes on reload.
    data.networks.find(n=>n.id===id(305)).accent_key = "purple";
    await page.getByRole("button",{name:"Refresh",exact:true}).click();
    await page.locator(`[data-node-key="network:${id(305)}"][data-presentation-accent="purple"]`).waitFor();
    assert.equal(await adguardNode.getAttribute("data-presentation-accent"),"green");
    assert.equal(await page.locator('.topology-connectivity-world g[data-presentation-accent="purple"] line[stroke-dasharray]').count(),1);
    await page.locator(`[data-node-key="asset:${id(30)}"]`).click();
    assert.equal(await page.locator('[aria-label="Topology inspector"] h2').innerText(),"PVE1");
    assert.equal(await page.getByRole("link",{name:"Open Asset",exact:true}).getAttribute("href"),`/assets/${id(30)}`);
    assert.equal(await page.getByRole("link",{name:"View in Knowledge Graph",exact:true}).getAttribute("href"),`/knowledge-graph?focus=asset:${id(30)}&depth=1`);
    await page.getByRole("button",{name:"2 hops",exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll("[data-node-key]").length>4);
    assert.equal(await page.locator("[data-node-key]").count(),5);
    assert.equal(await page.locator(`[data-node-key="asset:${id(36)}"]`).count(),1);
    assert.equal(await page.locator(`[data-node-key="asset:${id(101)}"]`).count(),0);
    await checkGeometry(page);
    await checkIdentityContrast(page);
    await page.screenshot({ path:`${output}/adguard-two-hops-${theme}-${width}.png`,fullPage:true });
    await page.getByLabel("Focus Asset or Network",{exact:true}).selectOption(id(30));
    await page.getByRole("button",{name:"1 hop",exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll("[data-node-key]").length===22);
    await checkGeometry(page);
    await checkIdentityContrast(page);
    await page.getByLabel("Focus Asset or Network",{exact:true}).selectOption(`network:${id(305)}`);
    await page.waitForFunction(()=>document.querySelectorAll("[data-node-key]").length===21);
    assert.equal(await page.locator(`[data-node-key="asset:${id(101)}"]`).count(),1);
    await checkGeometry(page);
    await checkIdentityContrast(page);
    await page.locator(`[data-node-key="asset:${id(100)}"]`).click();
    assert.equal(await page.locator('[aria-label="Topology inspector"] h2').innerText(), "AdGuard Home");
    await page.getByRole("button",{name:"Focus Connectivity",exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll("[data-node-key]").length===4);
    await page.getByLabel("Focus Asset or Network",{exact:true}).selectOption(id(31));
    await page.getByRole("button",{name:"2 hops",exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll("[data-node-key]").length>=10);
    assert.ok(await page.locator("[data-node-key]").count()<=15);
    await checkGeometry(page);
    await checkIdentityContrast(page);
    for (const control of ["Zoom in", "Zoom in", "Zoom out", "Fit"]) {
      await page.getByRole("button",{name:control,exact:true}).click();
      await checkGeometry(page);
    await checkIdentityContrast(page);
    }
    if (width === 1440) assert.ok((await page.locator("[data-node-key]").first().boundingBox()).width >= 85, "Fit keeps 14-node cards readable on desktop");
    await page.screenshot({ path:`${output}/useful-two-hops-${theme}-${width}.png`,fullPage:true });
    await expand.click(); await close.waitFor();
    await checkGeometry(page);
    await checkIdentityContrast(page);
    await page.getByRole("button", { name:"Zoom in",exact:true }).click();
    await page.locator(".topology-connectivity-viewport").evaluate(el => { el.scrollLeft += 60; el.scrollTop += 60; });
    await checkGeometry(page);
    await checkIdentityContrast(page);
    await page.getByRole("button", { name:"Fit",exact:true }).click();
    await page.screenshot({ path:`${output}/useful-two-hops-expanded-${theme}-${width}.png`,fullPage:true });
    await close.click();
    await page.getByLabel("Focus Asset or Network",{exact:true}).selectOption(id(100));
    await page.waitForFunction(()=>document.querySelectorAll("[data-node-key]").length===5);
    await page.getByLabel("Compute",{exact:true}).uncheck();
    await page.locator(`[data-node-key="asset:${id(30)}"]`).waitFor({state:"detached"});
    await page.getByLabel("Compute",{exact:true}).check();
    await page.locator(`[data-node-key="asset:${id(30)}"]`).waitFor();
    await page.getByRole("button",{name:"1 hop",exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll("[data-node-key]").length===4);
    const beforeGraphExpand = requests.filter(r => !r.includes("/icon?")).length;
    await expand.click(); await close.waitFor();
    assert.equal(requests.filter(r => !r.includes("/icon?")).length,beforeGraphExpand);
    assert.equal(await page.getByLabel("Focus Asset or Network",{exact:true}).inputValue(),id(100));
    const focusBox = await page.locator(`[data-node-key="asset:${id(100)}"]`).boundingBox();
    const canvasBox = await page.locator(".topology-connectivity-viewport").boundingBox();
    assert.ok(focusBox.y + focusBox.height < 1000, "Focused Asset stays in the viewport");
    assert.ok(Math.abs(focusBox.x + focusBox.width / 2 - (canvasBox.x + canvasBox.width / 2)) < 5, "Focus remains horizontally centred");
    assert.ok(Math.abs(focusBox.y + focusBox.height / 2 - (canvasBox.y + canvasBox.height / 2)) < 5, "Focus remains vertically centred");
    assert.ok(requests.some(r => r.includes("/icon?v=")), "Shared cached icons are requested");
    await page.screenshot({ path:`${output}/connectivity-${theme}-${width}.png`,fullPage:true });
    await close.click();
    assert.deepEqual(errors,[]);
    // Dense recorded results communicate the safety cap without shrinking it.
    for (let n=0; n<10; n++) {
      const asset = { ...data.assets[0], id:id(900+n), name:`Extra child ${n}`, cached_icon_url:null };
      data.assets.push(asset);
      data.relationships.push({ id:id(950+n), source_asset_id:asset.id, target_asset_id:id(30), relationship_type:"runs_on" });
    }
    await page.getByRole("button", { name:"Refresh",exact:true }).click();
    await page.getByLabel("Focus Asset or Network",{exact:true}).selectOption(id(30));
    await page.waitForFunction(()=>document.querySelectorAll("[data-node-key]").length===25);
    assert.match(await page.getByRole("status").innerText(), /Result limited/);
    await page.getByRole("button", { name:"Overview",exact:true }).click();
    assert.equal(await page.locator(".topology-detail-inspector").count(),0);
    assert.equal(await page.getByRole("button", { name:"Close details",exact:true }).count(),0);
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
    assert.doesNotMatch(await page.locator("table").innerText(), /192.0.2.254|Hostname \/ IP/);
    assert.equal(await page.getByRole("columnheader", {name:"Hostname",exact:true}).count(),1);
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
    // Custom administrator taxonomy is immediately usable without label rules.
    await page.getByRole("button", {name:"Add Asset category", exact:true}).click();
    await page.locator('input[name="key"]').fill("home_automation");
    await page.locator('input[name="name"]').fill("Home Automation");
    await page.locator('input[name="icon_key"][value="home"]').check();
    await page.locator('input[name="accent_key"][value="teal"]').check();
    await page.screenshot({path:`${output}/category-picker-${theme}-${width}.png`,fullPage:true});
    await page.getByRole("button", {name:"Create", exact:true}).click();
    await page.getByRole("row").filter({hasText:"Home Automation"}).waitFor();
    await page.goto(`${base}/admin/asset-types`);
    await page.getByRole("button", {name:"Add Asset type", exact:true}).click();
    await page.locator('input[name="key"]').fill("home_device");
    await page.locator('input[name="name"]').fill("Home Device");
    await page.locator('select[name="category_id"]').selectOption(id(800));
    await page.getByRole("button", {name:"Create", exact:true}).click();
    await page.getByRole("row").filter({hasText:"Home Device"}).waitFor();
    data.assets.push({...data.assets[0], id:id(851), name:"Home Assistant", asset_type:"home_device"});
    await page.goto(`${base}/networks`);
    await page.getByRole("button", {name:"Add Network", exact:true}).click();
    assert.equal(await page.locator('input[name="icon_key"][value="network"]').isChecked(),true);
    assert.equal(await page.locator('input[name="accent_key"][value="blue"]').isChecked(),true);
    await page.locator('input[name="name"]').fill("Custom Network");
    await page.locator('input[name="icon_key"][value="cloud"]').check();
    await page.locator('input[name="accent_key"][value="rose"]').check();
    await page.getByRole("button", {name:"Create", exact:true}).click();
    const customNetwork = page.getByRole("row").filter({hasText:"Custom Network"});
    await customNetwork.waitFor();
    assert.equal(await customNetwork.locator('[data-presentation-icon="cloud"]').getAttribute("data-presentation-accent"),"rose");
    data.asset_interfaces.push({id:id(852),asset_id:id(851),network_id:id(850),name:"eth0",ip_address:null});
    await page.goto(`${base}/topology`);
    const homeSummary = page.locator(".topology-summary-row").filter({hasText:"Home Automation"});
    await homeSummary.waitFor();
    assert.equal(await homeSummary.getAttribute("data-presentation-accent"),"teal");
    assert.equal(await homeSummary.locator('[data-presentation-icon="home"]').count(),1);
    assert.equal(await homeSummary.locator(".asset-icon").count(),1);
    await page.getByRole("button",{name:"Platform",exact:true}).click();
    assert.equal(await page.locator(`[data-platform-id="${id(851)}"]`).getAttribute("data-presentation-accent"),"teal");
    await page.getByRole("button",{name:"Network & VLAN",exact:true}).click();
    await page.locator(".topology-network-list button").filter({hasText:"Custom Network"}).click();
    assert.equal(await page.locator(".topology-network-heading").getAttribute("data-presentation-accent"),"rose");
    await page.getByRole("button",{name:"Connectivity",exact:true}).click();
    await page.getByLabel("Focus Asset or Network",{exact:true}).selectOption(id(851));
    await page.locator(`[data-node-key="network:${id(850)}"]`).waitFor();
    assert.equal(await page.locator(`[data-node-key="asset:${id(851)}"]`).getAttribute("data-presentation-accent"),"teal");
    assert.equal(await page.locator(`[data-node-key="network:${id(850)}"] [data-presentation-icon="cloud"]`).getAttribute("data-presentation-accent"),"rose");
    assert.deepEqual(errors,[]);
    checks++; await context.close();
  }
  console.log(`Passed ${checks} topology identity browser scenarios: category/Network form writes, Compute server/blue, Workload cube/green, Management blue then purple, IoT purple, Apps orange, Infra red, multihomed AdGuard, Home Automation home/teal, custom Network cloud/rose; light/dark at 1440, 1100 and 800px; 25-Asset preview, 20 PVE1 children, suppressed sibling/Network fan-out, genuine switch paths, direct host/Network focus, 14-node collision checks, icon/fallback containment during zoom/pan/Fit, limit notices, interface IPs, Assets cleanup and expanded-state preservation.`);
} finally { await browser.close(); }
