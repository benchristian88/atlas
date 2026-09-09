// Optional local acceptance smoke check; no browser dependency or production data.
// Start Next on port 3104, then run with Node 22+ and Chrome installed.
import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import assert from "node:assert/strict";

const origin = process.env.ATLAS_WEB_TEST_ORIGIN || "http://127.0.0.1:3104";
const chromePath = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/private/tmp/atlas-c24-browser";
await mkdir(output, { recursive: true });
const chrome = spawn(chromePath, ["--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--remote-debugging-port=9324", `--user-data-dir=${output}/profile-${Date.now()}`, "about:blank"], { stdio: "ignore" });
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let socket;
let sequence = 0;
const pending = new Map();
const errors = [];
let variant = "normal";
let calls = [];
const id = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const customer = id(1), site = id(2), remote = id(3);
const permissions = ["customers.view", "sites.view", "assets.view", "services.view", "services.create", "business_functions.view", "service_dependencies.view", "knowledge_gaps.view", "changes.view", "networks.view"];
const node = (type, number, name, extra = {}) => ({ key: `${type}:${id(number)}`, entity_type: type, entity_id: id(number), id: id(number), customer_id: customer, site_id: type === "asset" ? site : null, name, href: `/${type === "business_function" ? "business-functions" : type === "service" ? "services" : "assets"}/${id(number)}`, criticality_rank: type === "service" ? 75 : null, criticality_name: type === "service" ? "High" : null, operational_state: type === "service" ? "operational" : null, lifecycle_state: "active", completeness_status: "incomplete", required_total: type === "business_function" ? null : 4, required_satisfied: type === "business_function" ? null : 3, open_gap_count: 1, ...extra });
const dns = node("service", 10, "DNS Resolution and Filtering");
const proxy = node("service", 11, "Reverse Proxy and Application Publishing");
const provider = node("asset", 20, "AdGuard Home", { site_id: remote, site_name: "Remote lab", contextual_ip: "192.0.2.53", contextual_vlan: 42 });
const bf = node("business_function", 30, "Home Lab Users");
const host = node("asset", 21, "PVE1");
const edge = (key, family, source, target, group = null) => ({ key, edge_family: family, source_key: source.key, target_key: target.key, label: family === "service_business_function" ? "Supports" : family === "asset_relationship" ? "Runs on" : "Depends on", dependency_group_id: group, dependency_group_name: group ? "Core Operation" : null, dependency_requirement: "required", dependency_strategy: group ? "all" : null, failure_effect: "unavailable" });
const e1 = edge("provider", "service_asset", dns, provider, id(70));
const e2 = edge("dependent", "service_service", proxy, dns, id(71));
const base = { focus_key: "", nodes: [bf, dns, proxy, provider, host], edges: [e1, e2, edge("support", "service_business_function", dns, bf), edge("structural", "asset_relationship", provider, host)], truncated: false, warnings: [] };
const dense = { ...base, nodes: [...base.nodes, ...Array.from({ length: 38 }, (_, i) => node("service", 100 + i, `Service ${i}`)), ...Array.from({ length: 148 }, (_, i) => node("asset", 200 + i, `Asset ${i}`)), ...Array.from({ length: 19 }, (_, i) => node("business_function", 500 + i, `Function ${i}`))] };
const denseServices = dense.nodes.filter((n) => n.entity_type === "service");
const denseAssets = dense.nodes.filter((n) => n.entity_type === "asset");
const denseFunctions = dense.nodes.filter((n) => n.entity_type === "business_function");
dense.edges = [
  ...denseAssets.map((n, i) => edge(`dense-provider:${i}`, "service_asset", denseServices[i % 40], n)),
  ...denseServices.map((n, i) => edge(`dense-support:${i}`, "service_business_function", n, denseFunctions[i % 20])),
  ...denseServices.map((n, i) => edge(`dense-cycle:${i}`, "service_service", n, denseServices[(i + 1) % 40])),
];
const path = { nodes: [provider, dns, proxy], edges: [e1, e2] };
const scenario = { focus_key: provider.key, focus: provider, assumption: "Hypothetical consequences in recorded knowledge.", results: [{ service: dns, state: "unavailable", distance: 1, classification: "direct", paths: [{ nodes: [provider, dns], edges: [e1] }], reasons: [{ key: "r1", dependency_group_name: "DNS Provider", dependency_requirement: "required", dependency_strategy: "all", failure_effect: "unavailable", summary: "The required dependency set is unsatisfied.", members: [{ entity: provider, state: "unavailable", edge: e1 }] }] }, { service: proxy, state: "unavailable", distance: 2, classification: "downstream", paths: [path], reasons: [{ key: "r2", dependency_group_name: "Core Operation", dependency_requirement: "required", dependency_strategy: "all", failure_effect: "unavailable", summary: "DNS is unavailable and all dependencies are required.", members: [{ entity: dns, state: "unavailable", edge: e2 }] }] }], warnings: [], truncated: false };
function call(method, params = {}) { const requestId = ++sequence; socket.send(JSON.stringify({ id: requestId, method, params })); return new Promise((resolve, reject) => pending.set(requestId, { resolve, reject })); }
async function evaluate(expression) { const result = await call("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }); if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails)); return result.result.value; }
async function until(expression) { for (let i = 0; i < 100; i++) { if (await evaluate(`Boolean(${expression})`)) return; await delay(100); } throw new Error(`Timed out: ${expression}`); }
async function clickText(text) { await evaluate(`([...document.querySelectorAll('button,a')].find(e=>e.textContent.trim()===${JSON.stringify(text)}))?.click()`); }
async function navigate(path) { await call("Page.navigate", { url: `${origin}${path}` }); await until("document.querySelector('.operations-page') !== null"); }
async function screenshot(name) { const image = await call("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }); await writeFile(`${output}/${name}.png`, Buffer.from(image.data, "base64")); }
try {
  let target;
  for (let i = 0; i < 80; i++) { try { const targets = await (await fetch("http://127.0.0.1:9324/json/list")).json(); target = targets.find((t) => t.type === "page"); if (target) break; } catch {} await delay(100); }
  if (!target) throw new Error("Headless Chrome did not start.");
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve) => socket.addEventListener("open", resolve, { once: true }));
  socket.addEventListener("message", async ({ data }) => {
    const message = JSON.parse(data);
    if (message.id) { const waiter = pending.get(message.id); pending.delete(message.id); if (message.error) waiter?.reject(new Error(JSON.stringify(message.error))); else waiter?.resolve(message.result); return; }
    if (message.method === "Runtime.exceptionThrown") errors.push(message.params.exceptionDetails.text);
    if (message.method !== "Fetch.requestPaused") return;
    const { requestId, request } = message.params;
    const url = new URL(request.url);
    if (!url.pathname.startsWith("/api/")) { await call("Fetch.continueRequest", { requestId }); return; }
    calls.push({ path: url.pathname, query: url.search, headers: request.headers });
    let body = {}, status = 200;
    if (url.pathname === "/api/auth/me") body = { id: id(90), email: "fixture@example.test", display_name: "Fixture Operator", permissions, assignments: [{ scope_type: "global", permissions }] };
    else if (url.pathname === "/api/context") body = { global_access: true, customers: [{ id: customer, name: "Home Lab" }], sites: [{ id: site, customer_id: customer, name: "Local lab" }, { id: remote, customer_id: customer, name: "Remote lab" }] };
    else if (url.pathname === "/api/dashboard/summary") body = { assets: 3, services: 2, business_functions: 1, open_knowledge_gap_count: 2 };
    else if (url.pathname === "/api/changes") body = { items: [{ id: id(80), summary: "Dependency behaviour updated", entity_name_snapshot: dns.name, occurred_at: "2026-09-09T01:00:00Z" }] };
    else if (url.pathname.startsWith("/api/operational-graph")) {
      if (variant === "error") { status = 500; body = { detail: "Fixture graph error" }; }
      else if (variant === "empty") body = { ...base, nodes: [], edges: [] };
      else if (variant === "partial") body = { ...base, edges: [] };
      else body = variant === "dense" ? dense : base;
      if (variant === "loading") await delay(800);
    } else if (url.pathname === "/api/dependency-analysis") body = scenario;
    else if (["/api/assets", "/api/services", "/api/business-functions"].includes(url.pathname)) body = [provider, dns, proxy, bf].filter((n) => url.pathname.includes(n.entity_type === "business_function" ? "business-functions" : n.entity_type));
    await call("Fetch.fulfillRequest", { requestId, responseCode: status, responseHeaders: [{ name: "Content-Type", value: "application/json" }], body: Buffer.from(JSON.stringify(body)).toString("base64") });
  });
  await call("Page.enable"); await call("Page.bringToFront"); await call("Emulation.setFocusEmulationEnabled", { enabled: true }); await call("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }] }); await call("Runtime.enable"); await call("Fetch.enable", { patterns: [{ urlPattern: `${origin}/api/*` }] });
  await call("Emulation.setDeviceMetricsOverride", { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
  await navigate("/dashboard");
  await until("document.querySelectorAll('.landscape-node').length > 0");
  assert.equal(await evaluate("document.querySelectorAll('.ops-summary-item').length"), 4);
  assert.equal(await evaluate("document.querySelectorAll('[data-widget-id]').length"), 5);
  assert.equal(await evaluate("[...document.querySelectorAll('.context-selector option')].some(n=>n.textContent==='All sites'||n.textContent==='All customers')"), false);
  assert.equal(await evaluate("document.querySelectorAll('.critical-service-card [role=meter]').length"), 2);
  await screenshot("dashboard-light-desktop");
  await evaluate("document.querySelector('.landscape-node').click()");
  await until("location.pathname==='/knowledge-graph' && new URLSearchParams(location.search).has('focus') && document.querySelector('.graph-inspector h2')");
  await navigate(`/knowledge-graph?focus=${provider.key}`);
  await until("document.querySelector('.graph-inspector')?.textContent.includes('192.0.2.53')");
  assert.ok(await evaluate("document.querySelector('.graph-inspector').textContent.includes('Remote lab')"));
  await evaluate("document.querySelector('.dependency-presentation').click()");
  await until("document.querySelector('.graph-inspector').textContent.includes('Visible members')");
  await evaluate(`document.querySelector('[data-node-key="${provider.key}"]').click()`);
  await clickText("Preview unavailable");
  await until("document.querySelector('.analysis-scenario') && document.querySelectorAll('.analysis-unavailable').length>=3");
  await evaluate(`document.querySelector('[data-node-key="${proxy.key}"]').focus()`);
  await call("Input.dispatchKeyEvent", { type: "keyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
  await call("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
  await until("document.querySelector('.graph-inspector').textContent.includes('Downstream consequence')");
  assert.ok(await evaluate("document.querySelector('.graph-inspector').textContent.includes('2 hops')"));
  assert.equal(await evaluate("document.querySelector('.entity-business_function.landscape-node').textContent.includes('UNAVAILABLE')"), false);
  await screenshot("graph-analysis-light-desktop");
  await clickText("Exit analysis");
  await until("!new URLSearchParams(location.search).has('analysis')");
  await call("Page.reload");
  await until(`document.querySelector('.graph-inspector h2')?.textContent===${JSON.stringify(provider.name)}`);
  await clickText("Filters"); await until("document.querySelector('.graph-filters')");
  await evaluate("[...document.querySelectorAll('.graph-filters label')].find(n=>n.textContent.includes('Structural Asset')).querySelector('input').click()");
  await until("location.search.includes('asset_relationship')");
  await evaluate("const el=document.getElementById('graph-find');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,'DNS');el.dispatchEvent(new Event('input',{bubbles:true}));");
  await until("document.querySelectorAll('.graph-search-results li').length>0");
  await evaluate("[...document.querySelectorAll('.graph-search-results button')].find(n=>n.textContent.includes('DNS Resolution')).click()");
  await until(`location.search.includes(encodeURIComponent(${JSON.stringify(dns.key)}))`);
  await clickText("2");
  await until("new URLSearchParams(location.search).get('depth')==='2'");
  await evaluate("history.back()");
  await until("new URLSearchParams(location.search).get('depth')!=='2'");
  await evaluate("history.forward()");
  await until("new URLSearchParams(location.search).get('depth')==='2'");
  variant = "dense";
  const start = performance.now();
  await navigate("/knowledge-graph");
  await until("document.querySelectorAll('.landscape-more').length===3");
  const renderMs = performance.now() - start;
  assert.equal(await evaluate("document.querySelectorAll('.landscape-node').length"), 24);
  await evaluate("[...document.querySelectorAll('.landscape-more')].find(n=>n.textContent.includes('assets')).click()");
  await until("document.querySelectorAll('.landscape-node.entity-asset').length===150");
  await clickText("Fit");
  await screenshot("graph-dense-light-desktop");
  await call("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "dark" }] });
  await screenshot("graph-dense-dark-desktop");
  await navigate("/dashboard"); await until("document.querySelectorAll('.landscape-node').length>0");
  await screenshot("dashboard-dark-desktop");
  for (const width of [900, 390]) {
    await call("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: width === 390 });
    await screenshot(`dashboard-dark-${width}`);
    assert.equal(await evaluate("document.documentElement.scrollWidth <= innerWidth"), true);
    await navigate(`/knowledge-graph?focus=${dns.key}`); await until("document.querySelector('.graph-inspector h2')");
    await screenshot(`graph-dark-${width}`);
    assert.equal(await evaluate("document.documentElement.scrollWidth <= innerWidth"), true);
    await navigate("/dashboard"); await until("document.querySelectorAll('.landscape-node').length>0");
  }
  for (const state of ["empty", "partial", "error", "loading"]) {
    variant = state; await navigate("/dashboard");
    await until(state === "error" ? "document.querySelector('[role=alert]')" : state === "loading" ? "document.body.textContent.includes('Loading service landscape')" : "document.body.textContent.includes('Build your service landscape')");
    await screenshot(`dashboard-${state}`);
  }
  assert.deepEqual(errors, []);
  const evidence = { checks: "Dashboard, navigation, keyboard selection, Focus, refresh, filters, Find, analysis/explanation, disclosure, Fit, dark/light, desktop/tablet/mobile, empty/partial/error/loading", dense: { nodes: 210, edges: dense.edges.length, initialVisibleNodes: 24, navigationToNodesMs: Math.round(renderMs) }, screenshots: output, runtimeExceptions: errors, scopeHeadersPresent: calls.filter((c) => c.path === "/api/operational-graph/landscape").every((c) => Object.keys(c.headers).some((h) => h.toLowerCase() === "x-atlas-customer-id")) };
  await writeFile(`${output}/evidence.json`, JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify(evidence, null, 2));
} catch (error) { if (socket?.readyState === 1) { await writeFile(`${output}/failure.txt`, await evaluate("document.body.innerText")); await screenshot("failure"); } throw error; } finally { socket?.close(); chrome.kill(); }
