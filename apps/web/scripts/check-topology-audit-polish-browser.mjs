// Isolated browser fixtures; never writes to live Atlas knowledge.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { mkdir, writeFile } from "node:fs/promises";
import { PRESENTATION_ICONS, PRESENTATION_ACCENTS } from "../lib/presentation.mjs";
import { contrastRatio } from "../lib/accent-theme.mjs";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const base = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3108";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-topology-browser-results";
await mkdir(output, { recursive: true });
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const positionSeeds = ["external", "security_edge", "routing", "aggregation_network", "access_network", "platform", "infrastructure", "workload", "endpoint"];
const position = key => key === "automatic" ? null : ({ id: id(5000 + positionSeeds.indexOf(key)), key, name: key, sort_order: positionSeeds.indexOf(key), active: true });
function resolvePositions(data) {
  for (const type of data.asset_types) type.topology_position = data.topology_positions.find(p => p.id === type.topology_position_id) || null;
}
const customer = { id: id(1), name: "Homelab", status: "active" };
const site = { id: id(2), customer_id: customer.id, name: "Home", status: "active" };
const permissions = ["service_types.view", "service_types.manage", "assets.view", "assets.create", "asset_types.view", "asset_types.manage", "customers.view", "sites.view", "networks.view", "networks.create", "networks.edit", "audit.view", "services.view", "business_functions.view", "service_dependencies.view", "relationships.view", "relationship_types.view", "relationship_types.manage"];
const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aSawAAAAASUVORK5CYII=", "base64");
function fixture() {
  const categories = [{ id: id(3), key: "hardware", name: "Compute", icon_key: "server", accent_key: "blue", show_in_topology: true, active: true, sort_order: 0 }, { id: id(4), key: "workload", name: "Workload", icon_key: "cube", accent_key: "green", show_in_topology: true, active: true, sort_order: 10 }, { id: id(5), key: "uncategorized", name: "Uncategorized", icon_key: "infrastructure", accent_key: "slate", show_in_topology: false, active: true, sort_order: 100 }, ...Array.from({ length: 8 }, (_, n) => ({ id: id(6+n), key: `custom_${n}`, name: n === 0 ? "Backup" : `Custom Category ${n}`, active: true, show_in_topology: true, sort_order: 100 }))];
  const types = [{ id: id(20), key: "server", name: "Server", topology_position_id: position("platform")?.id || null, category_id: id(3), category: "Compute", active: true }, { id: id(21), key: "docker_compose", name: "Docker Compose", topology_position_id: position("workload")?.id || null, category_id: id(4), category: "Workload", active: true }, { id: id(22), key: "unknown", name: "Unknown", category_id: id(5), category: "Uncategorized", active: true }];
  types.push({ id: id(23), key: "backup_appliance", name: "Backup Appliance", topology_position_id: position("infrastructure")?.id || null, category_id: id(6), category: "Backup", active: true });
  const asset = (n, name, type = "server") => ({ id: id(n), name, asset_type: type, customer_id: customer.id, site_id: site.id, status: "operational", hostname: `${name.toLowerCase().replaceAll(" ", "-")}.home`, cached_icon_url: `/api/assets/${id(n)}/icon?v=${"a".repeat(64)}` });
  const hosts = [asset(30, "PVE1"), asset(31, "PVE2"), asset(32, "PVE3"), asset(33, "PVE4")];
  const children = Array.from({ length: 25 }, (_, i) => asset(100+i, i === 1 ? "Atlas DNS" : i ? `Workload ${String(i).padStart(2,"0")}` : "AdGuard Home", "docker_compose"));
  types.push({ id: id(24), key: "custom_fabric", name: "Custom Fabric", category_id: id(3), category: "Compute", topology_position_id: position("access_network")?.id || null, active: true });
  const assets = [...hosts, asset(34,"PBS","backup_appliance"), asset(35,"Synology"), asset(36,"USW-16-poe","custom_fabric"), asset(37,"Router"), ...children, asset(150,"Uncategorized Asset","unknown")];
  const relationships = children.map((a,i) => ({ id: id(200+i), source_asset_id: a.id, target_asset_id: hosts[i < 20 ? 0 : i < 24 ? 1 : i < 27 ? 2 : 3].id, relationship_type: "runs_on" }));
  const platform_links = relationships.map(r => ({ relationship_id: r.id, parent_id: r.target_asset_id, child_id: r.source_asset_id }));
  for (const [source, target] of [[30,36], [31,36], [36,34], [36,35], [36,37], [36,32], [36,110], [36,111], [36,112]]) relationships.push({ id: id(500+relationships.length), source_asset_id: id(source), target_asset_id: id(target), relationship_type: "connects_to" });
  const networks = ["Default", "Main", "IoT", "Apps", "Infra", "Management", ...Array.from({length: 8}, (_,i)=>`Extra ${i}`)].map((name,i) => ({ id: id(300+i), name, network_type: "vlan", icon_key: "network", accent_key: ["blue", "teal", "purple", "orange", "red", "blue"][i] || "slate", vlan_id: i===5 ? 99 : i, cidr: `10.0.${i===5?99:i}.0/24`, gateway: `10.0.${i===5?99:i}.1`, customer_id: customer.id, site_id: site.id }));
  const asset_interfaces = [{ id: id(400), asset_id: children[0].id, network_id: networks[5].id, name: "eth0", ip_address: "10.0.99.5", mac_address: "02:00:00:00:00:05", is_primary: true }, { id: id(401), asset_id: children[0].id, network_id: networks[3].id, name: "eth1", ip_address: "10.0.3.5" }];
  asset_interfaces.push({ id: id(402), asset_id: hosts[0].id, network_id: null, name: "vmbr0", ip_address: "10.0.99.21" });
  for (let i=1; i<20; i++) asset_interfaces.push({ id: id(410+i), asset_id: children[i].id, network_id: networks[5].id, name: "eth0", ip_address: `10.0.99.${100+i}` });
  assets.forEach(a => { a.ip_address = "192.0.2.254"; });
  return { categories, asset_types: types, assets, relationships, relationship_types: [{ key: "runs_on", topology_class: "platform", name: "Runs on", source_label: "Runs on", directional: true }, { key: "connects_to", topology_class: "physical_network", name: "Connects to", source_label: "Connects to", directional: false }], networks, asset_interfaces, customers: [customer], sites: [site], platform_links };
}
function graphFixture(data, params) {
  // Exercise the production traversal instead of maintaining a second algorithm.
  const api = fileURLToPath(new URL("../../api/", import.meta.url));
  return JSON.parse(execFileSync(process.env.ATLAS_PYTHON || `${api}.venv/bin/python`, ["-c", `
import json, sys
from app.services.infrastructure_topology import connectivity
payload = json.load(sys.stdin)
print(json.dumps(connectivity(**payload)))
`], { cwd: api, encoding: "utf8", input: JSON.stringify({ topology: data, topology_classes: params.has("topology_classes") ? params.get("topology_classes").split(",").filter(Boolean) : null, focus_id: params.get("focus_asset_id"), focus_network_id: params.get("focus_network_id"), hops: Number(params.get("hops")), show_networks: params.get("show_networks") === "true", category_ids: params.getAll("category_ids") }) }));
}

const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [], requests = [];
  page.on("pageerror", error => errors.push(error.message));
  const data = fixture();
  data.assets.forEach(asset => { delete asset.cached_icon_url; });
  data.topology_positions = positionSeeds.map(position); resolvePositions(data);
  // Exactly seventeen workload previews and an eighteen-child parent.
  data.assets = data.assets.filter(a => a.asset_type !== "docker_compose" || Number(a.id.slice(-12)) < 117);
  data.assets.push({ ...data.assets.find(a => a.id === id(100)), id: id(118), name: "Nested host", asset_type: "server" });
  data.platform_links = data.platform_links.filter(l => data.assets.some(a => a.id === l.child_id));
  data.platform_links.push({ relationship_id:id(900), parent_id:id(30), child_id:id(118) }, { relationship_id:id(901),parent_id:id(118),child_id:id(31) });
  for (const [parent, children] of [[32,[100,101]], [33,[102,103,104,105]], [31,[106]]]) for (const child of children) data.platform_links.push({relationship_id:`fixture-${parent}-${child}`,parent_id:id(parent),child_id:id(child)});
  data.relationships = data.relationships.filter(r => data.assets.some(a => a.id === r.source_asset_id) && data.assets.some(a => a.id === r.target_asset_id));
  data.asset_interfaces = data.asset_interfaces.filter(i => data.assets.some(a => a.id === i.asset_id));
  [100,2,20,9].forEach((n,index) => { data.asset_interfaces[index] = { ...data.asset_interfaces[index], network_id:id(305), ip_address:`10.0.0.${n}` }; });
  for (let count = 1; count <= 5; count++) {
    data.categories.push({ id:id(600+count), key:`grid_${count}`, name:`Grid ${count}`, active:true, show_in_topology:true });
    data.asset_types.push({ id:id(610+count), key:`grid_${count}`, name:`Grid ${count}`, category_id:id(600+count), active:true });
    for (let i=0; i<count; i++) data.assets.push({ id:id(650+count*10+i), name:`Parent ${count}-${i}`, asset_type:`grid_${count}`, customer_id:customer.id, site_id:site.id, status:"operational" });
  }
  for (const child of [102,103,104,105]) data.platform_links.push({relationship_id:`height-${child}`,parent_id:id(690),child_id:id(child)});
  const kgNode = (n, type, name) => ({ key:`${type}:${id(n)}`, entity_id:id(n), entity_type:type, name, href:`/assets/${id(n)}`, customer_id:customer.id, site_id:site.id });
  const kgNodes = [kgNode(800,"business_function","Home operations"), kgNode(801,"service","Name resolution"), kgNode(30,"asset","PVE1"), ...Array.from({length: 8}, (_, i) => kgNode(820+i, "asset", `Graph Asset ${i+1}`))];
  await page.route("**/api/**", async route => {
    const url = new URL(route.request().url()); requests.push(url.pathname + url.search);
    if (url.pathname.endsWith("/icon")) return route.fulfill({contentType:"image/png",body:png});
    let body = [];
    if (url.pathname === "/api/auth/me") body = {id:id(99),display_name:"Investigator",email:"fixture@example.test",permissions,assignments:[{scope_type:"global",permissions}]};
    else if (url.pathname === "/api/context") body = {customers:[customer],sites:[site],global_access:true,selected_customer_id:customer.id,selected_site_id:site.id};
    else if (url.pathname === "/api/topology") body = data;
    else if (url.pathname === "/api/topology/connectivity") body = graphFixture(data,url.searchParams);
    else if (url.pathname.startsWith("/api/operational-graph")) body = {nodes:kgNodes,edges:[{key:"bf",source_key:kgNodes[0].key,target_key:kgNodes[1].key,edge_family:"service_business_function",label:"Supported by"},{key:"svc",source_key:kgNodes[1].key,target_key:kgNodes[2].key,edge_family:"service_asset",label:"Depends on"},{key:"asset-link",source_key:kgNodes[3].key,target_key:kgNodes[4].key,edge_family:"asset_relationship",label:"Depends on"}],truncated:false,warnings:[]};
    else if (url.pathname === "/api/audit-events") body = [1,2].map(n => ({id:id(950+n),created_at:"2026-09-23T01:00:00Z",actor_snapshot:"Operator",event_type:"asset.updated",target_type:"asset",target_id:id(30),customer_id:customer.id,site_id:site.id,success:true,change_summary:"Updated recorded Asset details",metadata:{name:{from:"Old host",to:"PVE1"},active:{before:true,after:false},added:{after:"New value"},removed:{before:"Previous value"},api_token:"[redacted]"}}));
    await route.fulfill({contentType:"application/json",body:JSON.stringify(body)});
  });
  const shot = async name => page.screenshot({path:`${output}/${name}.png`,fullPage:true});
  await page.goto(`${base}/topology`);
  const workload = page.locator('.topology-summary-row').filter({hasText:"Workload"});
  await workload.waitFor();
  assert.equal(await workload.locator('.topology-summary-icons a:not(.topology-preview-more)').count(),12);
  assert.equal(await workload.locator('.topology-preview-more').innerText(),"+5");
  assert.match(await workload.locator('.topology-preview-more').getAttribute('href'),/category/);
  assert.equal(await page.getByRole('button',{name:'Expand Infrastructure Topology',exact:true}).count(),0);
  await shot('01-overview-12-plus-5');
  await page.getByRole('button',{name:'Platform',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Expand Infrastructure Topology',exact:true}).count(),0);
  const checkGrid = async (columns) => {
    const rows = await page.locator('.topology-platform-grid').evaluateAll(grids => grids.flatMap(grid => {
      const rows = new Map();
      for (const card of grid.children) {
        const rect=card.getBoundingClientRect(), key=Math.round(rect.top);
        if(!rows.has(key))rows.set(key,[]);
        rows.get(key).push({height:rect.height,children:card.querySelectorAll('.topology-child').length,scroll:card.scrollHeight,client:card.clientHeight});
      }
      return [...rows.values()];
    }));
    for(const row of rows) {
      assert.ok(row.every(card=>Math.abs(card.height-row[0].height)<1),'equal heights within each row');
      assert.ok(row.every(card=>card.scroll<=card.client+1),'no card content clipping');
      if(row.every(card=>card.children===0))assert.ok(row[0].height<220,'childless row has no reserved preview space');
    }
    assert.ok(rows.some(row=>row.some(card=>card.children>0)&&row.some(card=>card.children===0)),'mixed content shares row height');
    for (let count=1; count<=5; count++) {
      const grid = page.locator('.topology-platform-section').filter({has:page.getByRole('heading',{name:`Grid ${count} ${count}`,exact:true})}).locator('.topology-platform-grid');
      const dimensions = await grid.evaluate(el => ({ width:el.clientWidth, tracks:getComputedStyle(el).gridTemplateColumns.split(' ').map(parseFloat), cards:[...el.children].map(c=>({width:c.getBoundingClientRect().width, left:c.offsetLeft, top:c.offsetTop})) }));
      assert.equal(dimensions.tracks.length,columns);
      assert.equal(dimensions.cards.length,count);
      for (const card of dimensions.cards) assert.ok(Math.abs(card.width-(dimensions.width-16*(columns-1))/columns)<1);
      if(count>columns) assert.equal(dimensions.cards[columns].left,dimensions.cards[0].left);
    }
  };
  // The same browser width gives four tracks without details and three with it.
  await page.setViewportSize({width:1800,height:1000});
  await page.getByRole('button',{name:'Hide details panel'}).click();
  await checkGrid(4);
  await shot('11-platform-four-columns-single-and-multiple');
  await page.locator('.topology-toolbar').screenshot({path:`${output}/21-platform-toolbar.png`});
  await page.locator('.topology-platform-section').filter({has:page.getByRole('heading',{name:'Backup 1',exact:true})}).screenshot({path:`${output}/22-backup-compact.png`});
  await page.locator('.topology-platform-section').filter({has:page.getByRole('heading',{name:'Compute 6',exact:true})}).screenshot({path:`${output}/23-mixed-and-compact-rows.png`});
  await page.locator('.topology-platform-section').filter({has:page.getByRole('heading',{name:'Grid 4 4',exact:true})}).screenshot({path:`${output}/24-one-populated-card.png`});
  await page.locator('.topology-platform-section').filter({has:page.getByRole('heading',{name:'Grid 1 1',exact:true})}).screenshot({path:`${output}/15-platform-single-four.png`});
  await page.locator('.topology-platform-section').filter({has:page.getByRole('heading',{name:'Grid 5 5',exact:true})}).screenshot({path:`${output}/16-platform-five-four.png`});
  await page.getByRole('button',{name:'Show details panel'}).click();
  await checkGrid(3);
  await page.locator(`[data-platform-id="${id(30)}"] > .topology-asset-identity`).click();
  await shot('12-platform-three-columns-inspector');
  await page.locator('.topology-platform-section').filter({has:page.getByRole('heading',{name:'Grid 1 1',exact:true})}).screenshot({path:`${output}/17-platform-single-three.png`});
  await page.setViewportSize({width:1440,height:1000});
  await checkGrid(2);
  await page.getByRole('button',{name:'Hide details panel'}).click();
  await checkGrid(3);
  await page.setViewportSize({width:1100,height:1000});
  await checkGrid(2);
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Show details panel'}).click();
  const parent = page.locator(`[data-platform-id="${id(30)}"]`);
  assert.equal(await parent.locator('.topology-child').count(),4);
  for (const [n,count] of [[32,2],[33,4],[35,0]]) assert.equal(await page.locator(`[data-platform-id="${id(n)}"] .topology-child`).count(),count);
  await parent.locator(':scope > .topology-asset-identity').click();
  await page.getByRole('link',{name:'Open Asset',exact:true}).waitFor();
  assert.equal(await page.locator('.topology-detail-inspector').count(),0);
  await shot('02-platform-inspector-four-children');
  await parent.screenshot({path:`${output}/09-platform-child-preview.png`});
  await page.getByRole('button',{name:'Hide details panel'}).click();
  await parent.locator('.topology-child .topology-asset-identity').first().click();
  await page.getByRole('button',{name:'Show details panel'}).click();
  assert.match(await page.locator('.graph-inspector h2').innerText(),/AdGuard/);
  await parent.getByRole('button',{name:'+14 more',exact:true}).click();
  assert.equal(await parent.locator('.topology-child').count(),18);
  await parent.getByRole('button',{name:'View platform (1)',exact:true}).click();
  assert.equal(await page.locator(`[data-platform-id="${id(118)}"] .topology-child`).count(),1);
  await page.getByRole('button',{name:'View platform (1)',exact:true}).click();
  assert.equal(await page.locator(`[data-platform-id="${id(31)}"] .topology-child`).count(),1);
  await page.getByRole('button',{name:'Network & VLAN',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Expand Infrastructure Topology',exact:true}).count(),0);
  await page.locator('.topology-toolbar').screenshot({path:`${output}/25-networks-toolbar.png`});
  await page.locator('.topology-network-list button').filter({hasText:'Management'}).click();
  await page.getByRole('button',{name:'IP address',exact:true}).click();
  const ips = await page.locator('.topology-network-detail tbody tr td:nth-child(3)').allTextContents();
  assert.deepEqual(ips.slice(0,4),['10.0.0.2','10.0.0.9','10.0.0.20','10.0.0.100']);
  await page.getByRole('button',{name:'IP address ↑',exact:true}).click();
  assert.equal(await page.locator('.topology-network-detail th[aria-sort="descending"]').innerText(),'IP address ↓');
  await page.getByRole('button',{name:'Name',exact:true}).click();
  assert.match(await page.locator('.topology-network-detail tbody button').first().innerText(),/AdGuard/);
  await page.getByRole('button',{name:'Name ↑',exact:true}).click();
  assert.match(await page.locator('.topology-network-detail tbody button').first().innerText(),/Workload 16/);
  await page.getByRole('button',{name:'IP address',exact:true}).click();
  await page.locator('.topology-network-detail tbody button').first().click();
  await shot('03-network-inspector-sorted-ips');
  await page.locator('.topology-network-detail').screenshot({path:`${output}/10-network-ip-sort.png`});
  await page.getByRole('button',{name:'Hide details panel'}).click();
  await page.locator('.topology-network-detail tbody button').nth(1).click();
  await page.getByRole('button',{name:'Show details panel'}).click();
  await page.getByRole('button',{name:'Connectivity',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Expand Infrastructure Topology',exact:true}).count(),1);
  await page.locator('.topology-toolbar').screenshot({path:`${output}/26-connectivity-toolbar.png`});
  assert.equal(await page.getByRole('button',{name:'3 hops',exact:true}).count(),0);
  await page.getByRole('button',{name:'Expand Infrastructure Topology',exact:true}).click();
  await page.getByRole('button',{name:'3 hops',exact:true}).click();
  await page.waitForFunction(() => document.querySelector('.topology-connectivity-viewport'));
  assert.ok(requests.some(url=>url.includes('hops=3')));
  await shot('04-connectivity-three-hops');
  await page.getByRole('button',{name:'Close expanded Infrastructure Topology',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'2 hops',exact:true}).getAttribute('aria-pressed'),'true');
  for (const destination of ['Overview','Platform','Network & VLAN']) {
    await page.getByRole('button',{name:'Connectivity',exact:true}).click();
    await page.getByRole('button',{name:'Expand Infrastructure Topology',exact:true}).click();
    await page.getByRole('button',{name:destination,exact:true}).click();
    assert.equal(await page.locator('dialog').evaluate(el=>el.matches(':modal')),false);
    assert.equal(await page.getByRole('button',{name:'Expand Infrastructure Topology',exact:true}).count(),0);
    assert.equal(await page.getByRole('button',{name:'Close expanded Infrastructure Topology',exact:true}).count(),0);
    assert.equal(await page.evaluate(()=>document.body.style.position),'');
  }
  await page.goto(`${base}/knowledge-graph?types=business_function,service,asset&relationships=service_business_function,service_asset,service_service,asset_relationship`);
  const geometry = () => page.locator('.landscape-viewport').evaluate(el => {
    const canvas=el.querySelector('.landscape-canvas'), card=canvas.querySelector('.landscape-node');
    const bounds=canvas.getBoundingClientRect(), viewport=el.getBoundingClientRect();
    return {width:el.clientWidth,height:el.clientHeight,contentWidth:bounds.width,contentHeight:bounds.height,top:bounds.top-viewport.top,scrollTop:el.scrollTop,scrollHeight:el.scrollHeight,zoom:Number(canvas.style.transform.match(/[\d.]+/)[0]),lane:parseFloat(canvas.querySelector('.landscape-lane').style.width),cardWidth:card.getBoundingClientRect().width,cardHeight:card.getBoundingClientRect().height};
  });
  const checkRouting = async () => {
    const endpoints = await page.locator('.landscape-canvas').evaluate((canvas, keys) => {
      const path=canvas.querySelector('.landscape-connectors > path');
      const start=path.getPointAtLength(0).matrixTransform(path.getScreenCTM());
      const end=path.getPointAtLength(path.getTotalLength()).matrixTransform(path.getScreenCTM());
      const source=canvas.querySelector(`[data-node-key="${keys[0]}"]`).getBoundingClientRect();
      const target=canvas.querySelector(`[data-node-key="${keys[1]}"]`).getBoundingClientRect();
      return { startX:start.x, startY:start.y, endX:end.x, endY:end.y, source:source.toJSON(), target:target.toJSON() };
    },kgNodes.slice(0,2).map(n=>n.key));
    const contained = await page.locator('.landscape-canvas').evaluate(canvas => {
      const width=parseFloat(canvas.style.width);
      return [...canvas.querySelectorAll('.landscape-connectors > path')].every(path => {
        const bounds=path.getBBox();
        return bounds.x>=0 && bounds.x+bounds.width<=width;
      });
    });
    assert.ok(contained, 'relationship curves remain inside current canvas bounds');
    assert.ok(Math.abs(endpoints.startX-endpoints.source.right)<1);
    assert.ok(Math.abs(endpoints.endX-endpoints.target.left)<1);
    assert.ok(endpoints.startY> endpoints.source.top && endpoints.startY<endpoints.source.bottom);
    assert.ok(endpoints.endY> endpoints.target.top && endpoints.endY<endpoints.target.bottom);
  };
  const defaultView = async () => {
    await page.waitForFunction(() => {
      const el=document.querySelector('.landscape-viewport'), canvas=el?.querySelector('.landscape-canvas');
      return canvas?.style.transform==='scale(1)' && Math.abs(parseFloat(canvas.style.width)-Math.max(el.clientWidth-32,el.closest('.landscape-expanded') ? 744 : 672))<1;
    });
    await checkRouting();
    return geometry();
  };
  const fitted = async () => {
    await page.waitForFunction(() => {
      const el=document.querySelector('.landscape-viewport'), canvas=el?.querySelector('.landscape-canvas');
      if(!canvas)return false;
      const expected=Math.min(1.5,Math.max(.1,Math.min((el.clientWidth-32)/parseFloat(canvas.style.width),(el.clientHeight-32)/parseFloat(canvas.style.height))));
      return Math.abs(Number(canvas.style.transform.match(/[\d.]+/)[0])-expected)<.001;
    });
    await checkRouting();
    const result=await geometry();
    assert.ok(result.contentWidth<=result.width && result.contentHeight<=result.height);
    assert.equal(await page.locator('.landscape-zoom span').innerText(),`${Math.round(result.zoom*100)}%`);
    return result;
  };
  const embedded=await defaultView();
  assert.ok(embedded.cardWidth>=200 && embedded.cardHeight>=64);
  assert.ok(embedded.contentHeight>embedded.height);
  assert.equal(embedded.top,16);
  await shot('13-knowledge-embedded');
  await page.locator('[data-node-key]').first().click();
  const selection=await page.locator('.graph-inspector h2').innerText();
  const pageScroll=await page.evaluate(()=>window.scrollY);
  await page.locator('.landscape-viewport').evaluate(el=>el.scrollTop=400);
  assert.equal((await geometry()).scrollTop,400);
  assert.equal((await geometry()).cardWidth,embedded.cardWidth);
  assert.equal(await page.evaluate(()=>window.scrollY),pageScroll);
  await shot('18-knowledge-scrolled');
  await page.getByRole('button',{name:'+ 1 more assets',exact:true}).click();
  const disclosed=await geometry();
  assert.ok(disclosed.scrollHeight>embedded.scrollHeight);
  assert.equal(disclosed.cardWidth,embedded.cardWidth);
  assert.equal(disclosed.zoom,embedded.zoom);
  await shot('19-knowledge-disclosed');
  // Keyboard focus scrolls a lower card into the existing canvas viewport.
  const last=page.locator('[data-node-key]').last();
  await last.focus();
  await last.press('Enter');
  assert.equal(await last.getAttribute('aria-pressed'),'true');
  await page.getByRole('button',{name:'Fit',exact:true}).click();
  assert.ok((await fitted()).zoom<1);
  await page.reload();
  assert.equal((await defaultView()).cardWidth,embedded.cardWidth);
  await page.locator('[data-node-key]').first().click();
  await page.getByRole('button',{name:'Expand Knowledge Graph',exact:true}).click();
  const expanded=await defaultView();
  assert.ok(expanded.cardWidth>embedded.cardWidth);
  assert.ok(expanded.cardHeight>embedded.cardHeight);
  assert.ok(expanded.contentHeight>expanded.height);
  assert.equal(expanded.top,16);
  await shot('05-knowledge-visible');
  await page.locator('.landscape-viewport').evaluate(el=>el.scrollTop=200);
  await page.getByRole('button',{name:'Hide details panel'}).click();
  const hidden=await defaultView();
  assert.ok(hidden.width>expanded.width && hidden.lane>expanded.lane);
  assert.equal(hidden.cardWidth,expanded.cardWidth);
  assert.equal(hidden.scrollTop,200);
  await page.locator('.landscape-viewport').evaluate(el=>el.scrollTop=0);
  await shot('06-knowledge-hidden');
  await page.getByRole('button',{name:'Zoom out',exact:true}).click();
  const zoom=(await geometry()).zoom;
  await page.locator('[data-node-key]').first().click();
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  assert.equal((await geometry()).zoom,zoom);
  await page.getByRole('button',{name:'Fit',exact:true}).click();
  await fitted();
  await shot('20-knowledge-explicit-fit');
  await page.getByRole('button',{name:'Show details panel'}).click();
  await defaultView();
  assert.equal(await page.locator('.graph-inspector h2').innerText(),selection);
  await page.setViewportSize({width:1100,height:800});
  await defaultView();
  await page.setViewportSize({width:1440,height:1000});
  await defaultView();
  await page.getByRole('button',{name:'Zoom in',exact:true}).click();
  await page.getByRole('button',{name:'Close expanded Knowledge Graph',exact:true}).click();
  const returned=await defaultView();
  assert.equal(returned.cardWidth,embedded.cardWidth);
  assert.equal(returned.zoom,embedded.zoom);
  assert.equal(returned.top,16);
  await shot('14-knowledge-returned-embedded');
  await page.goto(`${base}/admin/audit`);
  await page.getByRole('button',{name:'Expand audit record'}).first().waitFor();
  await shot('07-audit-collapsed');
  await page.getByRole('button',{name:'Expand audit record'}).first().click();
  await page.getByRole('button',{name:'Expand audit record'}).first().click();
  assert.equal(await page.getByRole('region',{name:'Audit investigation'}).count(),2);
  assert.equal(await page.getByRole('cell',{name:'Added',exact:true}).count(),2);
  await shot('08-audit-expanded-diffs');
  await page.getByRole('button',{name:'Collapse audit record'}).first().click();
  assert.equal(await page.getByRole('region',{name:'Audit investigation'}).count(),1);
  assert.deepEqual(errors,[]);
  console.log('All seven UI-polish browser acceptance areas passed.');
} finally { await browser.close(); }
