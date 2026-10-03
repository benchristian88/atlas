// Fixture-backed C2.5 browser regression. Start the production web build on port 3125.
import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import assert from "node:assert/strict";

const origin = process.env.ATLAS_WEB_TEST_ORIGIN || "http://127.0.0.1:3125";
const chromePath = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/private/tmp/atlas-c25-browser";
await mkdir(output, { recursive: true });
const chrome = spawn(chromePath, ["--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--remote-debugging-port=9325", `--user-data-dir=${output}/profile-${Date.now()}`, "about:blank"], { stdio: "ignore" });
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let socket;
let sequence = 0;
const pending = new Map();
const errors = [];

function call(method, params = {}) { const requestId = ++sequence; socket.send(JSON.stringify({ id: requestId, method, params })); return new Promise((resolve, reject) => pending.set(requestId, { resolve, reject })); }
async function evaluate(expression) { const result = await call("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }); if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails)); return result.result.value; }
async function until(expression) { for (let i = 0; i < 100; i++) { if (await evaluate(`Boolean(${expression})`)) return; await delay(100); } throw new Error(`Timed out: ${expression}`); }
async function clickText(text) { await evaluate(`([...document.querySelectorAll('button,a')].find(e=>e.textContent.trim()===${JSON.stringify(text)}))?.click()`); }
async function loadDocument(path) {
  // CDP navigation/reload acknowledges before replacing the old DOM. Wait for
  // the new document so assertions cannot accidentally pass against stale UI.
  await evaluate("window.__atlasSmokeOldDocument = true");
  await call(path ? "Page.navigate" : "Page.reload", path ? { url: `${origin}${path}` } : {});
  await until("!window.__atlasSmokeOldDocument && document.readyState !== 'loading'");
}
async function navigate(path) { await loadDocument(path); await until("document.querySelector('.entity-detail-page') !== null"); }
async function screenshot(name) { const image = await call("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }); await writeFile(`${output}/${name}.png`, Buffer.from(image.data, "base64")); }

try {
  let target;
  for (let i = 0; i < 80; i++) { try { const targets = await (await fetch("http://127.0.0.1:9325/json/list")).json(); target = targets.find((t) => t.type === "page"); if (target) break; } catch {} await delay(100); }
  if (!target) throw new Error("Headless Chrome did not start.");
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve) => socket.addEventListener("open", resolve, { once: true }));
  const id = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
  const customer = id(1), site = id(2), serviceId = id(10), functionId = id(20);
  let variant = "normal", mode = "light";
  const calls = [], checks = [];
  const allPermissions = ["customers.view", "sites.view", "assets.view", "services.view", "services.edit", "services.archive", "business_functions.view", "business_functions.manage", "service_dependencies.view", "service_dependencies.manage", "knowledge_gaps.view", "changes.view"];
  const service = { id: serviceId, customer_id: customer, site_id: site, name: "Home DNS", purpose: "Resolve names for the home lab.", description: "Human-curated DNS capability.", service_type_name: "Infrastructure Service", criticality_name: "High", lifecycle_status: "active", operational_status: "operational", owner_name: "Home operator", technical_contact: "On-call operator", support_group: "Home lab", rto_minutes: 60, rpo_minutes: 15, suggested_rto_minutes: 240, recovery_notes: "Restore configuration from the runbook.", backup_notes: "Configuration exported weekly.", notes: "Recorded knowledge only.", documentation_url: "https://example.test/docs", runbook_url: "https://example.test/runbook" };
  const bf = { id: functionId, customer_id: customer, site_id: site, name: "Home Connectivity", description: "Keep household devices connected.", owner_name: "Home operator", active: true, criticality_name: "High", service_count: 8, open_gap_count: 2, created_at: "2026-09-09T00:00:00Z", updated_at: "2026-09-09T01:00:00Z" };
  const complete = { summary: { completeness_status: "required_gaps", required_total: 4, required_satisfied: 3, recommended_total: 2, recommended_satisfied: 1, open_gap_count: 1, exception_count: 0 }, active_gaps: [{ id: id(80), requirement_level: "required", severity: "high", status: "open", requirement_name: "Document recovery", summary: "Recovery procedure needs review.", remediation_hint: "Review the recorded runbook." }], resolved_gaps: [] };
  const assets = [{ id: id(30), asset_id: id(31), asset_name: "AdGuard Home", asset_type: "Application", source_label: "Provided by", required_for_operation: true, dependency_group_id: id(60), dependency_group_name: "DNS providers", dependency_requirement: "required", dependency_strategy: "any", failure_effect: "unavailable" }];
  const dependencies = [{ id: id(40), source_service_id: serviceId, target_service_id: id(11), target_service_name: "External DNS", source_label: "Depends on", required_for_operation: false, failure_effect: "unknown", description: "Optional fallback." }, { id: id(41), source_service_id: id(12), source_service_name: "Reverse Proxy", target_service_id: serviceId, target_label: "Depended on by" }];
  const group = { id: id(60), name: "DNS providers", strategy: "any", requirement: "required", failure_effect: "unavailable", asset_dependency_ids: [id(30)], service_dependency_ids: [] };
  const links = Array.from({ length: 8 }, (_, i) => ({ id: id(100 + i), service_id: id(10 + i), service_name: i ? `Supporting Service ${i}` : "Home DNS", business_function_id: functionId, business_function_name: bf.name, relationship_label: "Supports", is_primary: i === 0, importance: i === 0 ? "Essential context" : null, description: i === 0 ? "Household name resolution." : null }));
  const graphNode = (type, n, name) => ({ id: id(n), key: `${type}:${id(n)}`, entity_id: id(n), entity_type: type, name, customer_id: customer, site_id: site, href: `/${type === "service" ? "services" : type === "asset" ? "assets" : "business-functions"}/${id(n)}`, required_total: 4, required_satisfied: 3, criticality_name: "High", operational_state: "operational" });
  const graph = { nodes: [graphNode("business_function", 20, bf.name), ...links.map((l, i) => graphNode("service", 10 + i, l.service_name)), graphNode("asset", 31, "AdGuard Home")], edges: [], truncated: false, warnings: [] };
  socket.addEventListener("message", async ({ data }) => {
    const message = JSON.parse(data);
    if (message.id) { const waiter = pending.get(message.id); pending.delete(message.id); if (message.error) waiter?.reject(new Error(JSON.stringify(message.error))); else waiter?.resolve(message.result); return; }
    if (message.method === "Runtime.exceptionThrown") errors.push(message.params.exceptionDetails.text);
    if (message.method !== "Fetch.requestPaused") return;
    const { requestId, request } = message.params;
    const url = new URL(request.url), path = url.pathname.replace(/^\/api/, "");
    calls.push({ path, method: request.method, body: request.postData });
    const permissions = variant === "denied" ? ["customers.view", "sites.view"] : variant === "viewer" ? allPermissions.filter((p) => !p.endsWith(".manage") && !p.endsWith(".edit") && !p.endsWith(".archive")) : allPermissions;
    let body = [], status = 200;
    if (path === "/auth/me") body = { id: id(90), display_name: "Fixture operator", email: "operator@example.test", theme_mode: mode, permissions, assignments: [{ scope_type: "global", permissions }] };
    else if (path === "/context") body = { global_access: true, customers: [{ id: customer, name: "Home lab" }], sites: [{ id: site, customer_id: customer, name: "Home" }] };
    else if (path === `/services/${serviceId}`) { body = { ...service, archived_at: variant === "archived" ? "2026-09-09T00:00:00Z" : null }; if (variant === "missing") { status = 404; body = { detail: "Service not found" }; } if (variant === "loading") await delay(700); }
    else if (path === `/business-functions/${functionId}`) { body = { ...bf, active: variant !== "archived" }; if (request.method === "PATCH") Object.assign(bf, JSON.parse(request.postData)); if (variant === "missing") { status = 404; body = { detail: "Business function not found" }; } }
    else if (path.endsWith("/asset-dependencies")) body = variant === "empty" ? [] : assets;
    else if (path.endsWith("/service-dependencies")) body = variant === "empty" ? [] : dependencies;
    else if (path.endsWith("/dependency-groups")) body = variant === "empty" ? [] : [group];
    else if (path === `/services/${serviceId}/business-functions`) body = variant === "empty" ? [] : [links[0]];
    else if (path === `/business-functions/${functionId}/services`) body = variant === "empty" ? [] : links;
    else if (path.endsWith("/completeness")) body = variant === "unevaluated" ? { summary: { ...complete.summary, required_total: 0, required_satisfied: 0, completeness_status: "not_evaluated" }, active_gaps: [], resolved_gaps: [] } : complete;
    else if (path.endsWith("/graph")) body = variant === "empty" ? { nodes: [], edges: [] } : graph;
    else if (path === "/operational-graph") { body = graph; if (variant === "metadata-error") { status = 500; body = { detail: "Metadata unavailable" }; } }
    else if (path === "/dependency-analysis") body = { focus: graph.nodes.find((n) => n.entity_type === "service"), focus_key: `service:${serviceId}`, results: [], warnings: [], truncated: false, assumption: "Fixture hypothetical scenario." };
    else if (path === "/criticality-levels") body = [{ id: id(95), name: "High", active: true }];
    else if (path === "/assets") body = [{ id: id(31), name: "AdGuard Home", asset_type: "Application" }];
    else if (path === "/services") body = [{ id: id(11), name: "External DNS" }];
    else if (path === "/business-functions") body = [bf];
    else if (path === "/relationship-types") body = [{ id: id(96), name: "Depends on" }];
    else if (path.endsWith("/history")) body = [{ id: id(97), summary: "Service knowledge updated", occurred_at: "2026-09-09T00:00:00Z" }];
    if (request.method === "PATCH" && path === `/dependency-groups/${group.id}`) Object.assign(group, JSON.parse(request.postData));
    await call("Fetch.fulfillRequest", { requestId, responseCode: status, responseHeaders: [{ name: "Content-Type", value: "application/json" }], body: Buffer.from(JSON.stringify(body)).toString("base64") });
  });
  await call("Page.enable"); await call("Runtime.enable"); await call("Fetch.enable", { patterns: [{ urlPattern: `${origin}/api/*` }] });
  await call("Page.bringToFront"); await call("Emulation.setFocusEmulationEnabled", { enabled: true });
  const servicePath = `/services/${serviceId}`, functionPath = `/business-functions/${functionId}`;
  for (mode of ["light", "dark"]) {
    for (const width of [1440, 900, 390]) {
      await call("Emulation.setDeviceMetricsOverride", { width, height: 1000, deviceScaleFactor: 1, mobile: width === 390 });
      for (const path of [servicePath, functionPath]) {
        await navigate(path);
        assert.equal(await evaluate("document.documentElement.scrollWidth <= innerWidth"), true);
        assert.equal(await evaluate("getComputedStyle(document.querySelector('.page-header h1')).fontSize"), "28px");
        assert.equal(await evaluate("getComputedStyle(document.querySelector('.ops-card')).backgroundColor"), mode === "light" ? "rgb(255, 255, 255)" : "rgb(27, 39, 46)");
        assert.equal(await evaluate("document.querySelector('.entity-detail-header [aria-label=\"Criticality: High\"]') !== null"), true);
        const href = await evaluate("[...document.querySelectorAll('.entity-detail-actions a')].find(n=>n.textContent==='View in Knowledge Graph').getAttribute('href')");
        assert.equal(new URL(href, origin).searchParams.get("focus"), `${path === servicePath ? "service" : "business_function"}:${path === servicePath ? serviceId : functionId}`);
        await evaluate("document.querySelector('.entity-detail-actions a').focus()");
        await call("Input.dispatchKeyEvent", { type: "keyDown", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9 });
        await call("Input.dispatchKeyEvent", { type: "keyUp", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9 });
        assert.equal(await evaluate("getComputedStyle(document.activeElement).outlineStyle"), "solid");
        if (path === servicePath) {
          assert.equal(await evaluate("document.querySelector('.entity-detail-header [role=meter]').getAttribute('aria-valuenow')"), "75");
          assert.ok(await evaluate("document.querySelector('.entity-detail-header').textContent.includes('Recorded: operational')"));
          for (const title of ["Supports · Business Functions", "Provided by · Assets", "Depends on · Services", "Dependents", "Dependency impact"]) assert.ok(await evaluate(`[...document.querySelectorAll('h2')].some(n=>n.textContent===${JSON.stringify(title)})`), `${title}: ${await evaluate("JSON.stringify([...document.querySelectorAll('h2')].map(n=>n.textContent))")}`);
          assert.ok(await evaluate("document.querySelector('#dependency-impact') !== null"));
          assert.ok(await evaluate("document.querySelector('#dependency-impact').textContent.includes('Any one is sufficient')"));
          assert.equal(await evaluate("document.querySelector('.entity-detail-actions a').search.includes('analysis=unavailable')"), true);
          assert.ok(await evaluate("document.body.textContent.includes('Document recovery')"));
        } else {
          assert.equal(await evaluate("document.querySelector('.entity-detail-header [role=meter], .entity-detail-header .recorded-status')"), null);
          assert.ok(await evaluate("document.querySelector('.entity-detail-header').textContent.includes('Not evaluated for Business Functions')"));
          assert.ok(await evaluate("document.querySelector('.entity-section [aria-label=\"8 relationships\"]') !== null"));
          const disclosure = "[...document.querySelectorAll('summary')].find(n=>n.textContent.startsWith('View all'))";
          await evaluate(`${disclosure}.focus()`);
          await call("Input.dispatchKeyEvent", { type: "keyDown", key: "Enter", code: "Enter", text: "\r", windowsVirtualKeyCode: 13 });
          await call("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
          await until(`${disclosure}.parentElement.open`);
          assert.equal(await evaluate("[...document.querySelectorAll('.entity-relationship-name')].filter(n=>n.getClientRects().length).length"), 9);
        }
        await evaluate("window.scrollTo(0,0)");
        await screenshot(`${path === servicePath ? "service" : "function"}-${mode}-${width}`);
        checks.push(`${path === servicePath ? "Service" : "Business Function"}: ${mode} ${width}px, header, relationships, focus, theme, no overflow`);
      }
    }
  }
  for (variant of ["empty", "unevaluated", "viewer", "archived", "metadata-error"]) {
    for (const path of [servicePath, functionPath]) {
      await navigate(path);
      if (variant === "empty") assert.ok(await evaluate(`document.body.textContent.includes(${JSON.stringify(path === servicePath ? "No providing Assets" : "No Services support this Business Function")})`));
      if (variant === "unevaluated" && path === servicePath) assert.equal(await evaluate("document.querySelector('.entity-detail-header [role=meter]')"), null);
      if (variant === "viewer") assert.equal(await evaluate("document.querySelector('.entity-edit-disclosure form')"), null);
      if (variant === "archived" && path === servicePath) assert.equal(await evaluate("[...document.querySelectorAll('.entity-detail-actions a')].some(n=>n.textContent==='Preview unavailable')"), false);
      if (variant === "metadata-error" && path === functionPath) assert.ok(await evaluate("document.body.textContent.includes('Supporting Service status and completeness could not be loaded.')"));
      checks.push(`${path}: ${variant}`);
    }
  }
  variant = "normal";
  await navigate(functionPath); await clickText("Edit");
  await until("document.querySelector('.resource-form')");
  await evaluate("{const input=document.querySelector('.resource-form input');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'Updated purpose');input.dispatchEvent(new Event('input',{bubbles:true}));}");
  await clickText("Save"); await until("!document.querySelector('.resource-form') && document.querySelector('.entity-detail-page')");
  assert.ok(calls.some((c) => c.method === "PATCH" && c.path === `/business-functions/${functionId}` && JSON.parse(c.body).name === "Updated purpose"));
  checks.push("Business Function edit/save payload retained");
  await navigate(servicePath);
  await evaluate("[...document.querySelectorAll('summary')].find(n=>n.textContent==='Advanced configuration').parentElement.open=true");
  await evaluate("[...document.querySelectorAll('summary')].find(n=>n.textContent.startsWith('DNS providers ·')).parentElement.open=true");
  await evaluate("{const select=document.querySelector('#dependency-impact details details .dependency-group-form select');select.value='all';select.dispatchEvent(new Event('change',{bubbles:true}));}");
  await evaluate("document.querySelector('#dependency-impact details details .dependency-group-form').requestSubmit()");
  await until("document.querySelector('#dependency-impact')?.textContent.includes('All required')");
  assert.ok(calls.some((c) => c.method === "PATCH" && c.path === `/dependency-groups/${group.id}` && JSON.parse(c.body).strategy === "all"));
  checks.push("Dependency group strategy edit/save payload retained");
  await navigate(servicePath);
  await clickText("Preview unavailable");
  await until("document.querySelector('.analysis-scenario')");
  assert.equal(await evaluate("new URLSearchParams(location.search).get('analysis')"), "unavailable");
  await clickText("Exit analysis");
  await until("!new URLSearchParams(location.search).has('analysis')");
  checks.push("Service link opens existing Focus analysis and Exit analysis retains focus");
  await navigate(functionPath);
  await clickText("View in Knowledge Graph");
  await until("document.querySelector('.graph-inspector h2')");
  assert.equal(await evaluate("new URLSearchParams(location.search).get('focus')"), `business_function:${functionId}`);
  assert.equal(await evaluate("new URLSearchParams(location.search).has('analysis')"), false);
  checks.push("Business Function link opens existing Focus without analysis");
  for (variant of ["denied", "missing"]) {
    for (const path of [servicePath, functionPath]) {
      const before = calls.length;
      await loadDocument(path);
      await until("document.querySelector('.error-panel, .error-banner')");
      assert.equal(await evaluate("document.querySelector('.entity-detail-page')"), null);
      assert.equal(await evaluate("document.body.textContent.includes('Home DNS') || document.body.textContent.includes('Home Connectivity')"), false);
      if (variant === "denied") assert.equal(calls.slice(before).some((c) => c.path === path), false);
      checks.push(`${path}: ${variant}, no entity disclosure`);
    }
  }
  assert.deepEqual(errors, []);
  const evidence = { count: checks.length, checks, runtimeExceptions: errors, screenshots: output, note: "Fixture API browser regression; live manual acceptance remains pending." };
  await writeFile(`${output}/evidence.json`, JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify(evidence, null, 2));
} catch (error) { if (socket?.readyState === 1) { await writeFile(`${output}/failure.txt`, await evaluate("document.body.innerText")); await screenshot("failure"); } throw error; } finally { socket?.close(); chrome.kill(); }
