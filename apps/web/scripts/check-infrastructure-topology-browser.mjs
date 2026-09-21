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
const customer = { id: id(1), name: "Homelab", status: "active" };
const site = { id: id(2), customer_id: customer.id, name: "Home", status: "active" };
const permissions = ["service_types.view", "service_types.manage", "assets.view", "assets.create", "asset_types.view", "asset_types.manage", "customers.view", "sites.view", "networks.view", "networks.create", "networks.edit", "relationships.view", "relationship_types.view", "relationship_types.manage"];
const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aSawAAAAASUVORK5CYII=", "base64");
function fixture() {
  const categories = [{ id: id(3), key: "hardware", name: "Compute", icon_key: "server", accent_key: "blue", show_in_topology: true, active: true, sort_order: 0 }, { id: id(4), key: "workload", name: "Workload", icon_key: "cube", accent_key: "green", show_in_topology: true, active: true, sort_order: 10 }, { id: id(5), key: "uncategorized", name: "Uncategorized", icon_key: "infrastructure", accent_key: "slate", show_in_topology: false, active: true, sort_order: 100 }, ...Array.from({ length: 8 }, (_, n) => ({ id: id(6+n), key: `custom_${n}`, name: n === 0 ? "Backup" : `Custom Category ${n}`, active: true, show_in_topology: true, sort_order: 100 }))];
  const types = [{ id: id(20), key: "server", name: "Server", category_id: id(3), category: "Compute", active: true }, { id: id(21), key: "docker_compose", name: "Docker Compose", category_id: id(4), category: "Workload", active: true }, { id: id(22), key: "unknown", name: "Unknown", category_id: id(5), category: "Uncategorized", active: true }];
  types.push({ id: id(23), key: "backup_appliance", name: "Backup Appliance", category_id: id(6), category: "Backup", active: true });
  const asset = (n, name, type = "server") => ({ id: id(n), name, asset_type: type, customer_id: customer.id, site_id: site.id, status: "operational", hostname: `${name.toLowerCase().replaceAll(" ", "-")}.home`, cached_icon_url: `/api/assets/${id(n)}/icon?v=${"a".repeat(64)}` });
  const hosts = [asset(30, "PVE1"), asset(31, "PVE2"), asset(32, "PVE3"), asset(33, "PVE4")];
  const children = Array.from({ length: 25 }, (_, i) => asset(100+i, i === 1 ? "Atlas DNS" : i ? `Workload ${String(i).padStart(2,"0")}` : "AdGuard Home", "docker_compose"));
  const assets = [...hosts, asset(34,"PBS","backup_appliance"), asset(35,"Synology"), asset(36,"USW-16-poe"), asset(37,"Router"), ...children, asset(150,"Uncategorized Asset","unknown")];
  const relationships = children.map((a,i) => ({ id: id(200+i), source_asset_id: a.id, target_asset_id: hosts[i < 20 ? 0 : i < 24 ? 1 : i < 27 ? 2 : 3].id, relationship_type: "runs_on" }));
  const platform_links = relationships.map(r => ({ relationship_id: r.id, parent_id: r.target_asset_id, child_id: r.source_asset_id }));
  for (const [source, target] of [[30,36], [31,36], [36,34], [36,35], [36,37], [36,32], [36,110], [36,111], [36,112]]) relationships.push({ id: id(500+relationships.length), source_asset_id: id(source), target_asset_id: id(target), relationship_type: "connects_to" });
  const networks = ["Default", "Main", "IoT", "Apps", "Infra", "Management", ...Array.from({length: 8}, (_,i)=>`Extra ${i}`)].map((name,i) => ({ id: id(300+i), name, network_type: "vlan", icon_key: "network", accent_key: ["blue", "teal", "purple", "orange", "red", "blue"][i] || "slate", vlan_id: i===5 ? 99 : i, cidr: `10.0.${i===5?99:i}.0/24`, gateway: `10.0.${i===5?99:i}.1`, customer_id: customer.id, site_id: site.id }));
  const asset_interfaces = [{ id: id(400), asset_id: children[0].id, network_id: networks[5].id, name: "eth0", ip_address: "10.0.99.5", mac_address: "02:00:00:00:00:05", is_primary: true }, { id: id(401), asset_id: children[0].id, network_id: networks[3].id, name: "eth1", ip_address: "10.0.3.5" }];
  asset_interfaces.push({ id: id(402), asset_id: hosts[0].id, network_id: null, name: "vmbr0", ip_address: "10.0.99.21" });
  for (let i=1; i<20; i++) asset_interfaces.push({ id: id(410+i), asset_id: children[i].id, network_id: networks[5].id, name: "eth0", ip_address: `10.0.99.${100+i}` });
  assets.forEach(a => { a.ip_address = "192.0.2.254"; });
  return { categories, asset_types: types, assets, relationships, relationship_types: [{ key: "runs_on", topology_layer: "platform", name: "Runs on", source_label: "Runs on", directional: true }, { key: "connects_to", topology_layer: "physical_network", name: "Connects to", source_label: "Connects to", directional: false }], networks, asset_interfaces, customers: [customer], sites: [site], platform_links };
}
function graphFixture(data, params) {
  // Exercise the production traversal instead of maintaining a second algorithm.
  const api = fileURLToPath(new URL("../../api/", import.meta.url));
  return JSON.parse(execFileSync(process.env.ATLAS_PYTHON || `${api}.venv/bin/python`, ["-c", `
import json, sys
from app.services.infrastructure_topology import connectivity
payload = json.load(sys.stdin)
print(json.dumps(connectivity(**payload)))
`], { cwd: api, encoding: "utf8", input: JSON.stringify({ topology: data, topology_layers: params.has("topology_layers") ? params.get("topology_layers").split(",").filter(Boolean) : null, focus_id: params.get("focus_asset_id"), focus_network_id: params.get("focus_network_id"), hops: Number(params.get("hops")), show_networks: params.get("show_networks") === "true", category_ids: params.getAll("category_ids"), limit: 25 }) }));
}

async function checkIdentityContrast(page, selector = ".infrastructure-topology .presentation-icon") {
  const colours = await page.locator(selector).evaluateAll(els=>els.map(el=>{
    const style=getComputedStyle(el);
    return {foreground:style.color,background:style.backgroundColor};
  }));
  const hex = rgb=>"#" + rgb.match(/[\d.]+/g).slice(0,3).map(n=>Math.round(Number(n)).toString(16).padStart(2,"0")).join("");
  assert.ok(colours.length);
  for (const colour of colours) assert.ok(contrastRatio(hex(colour.foreground),hex(colour.background))>=4.5,JSON.stringify(colour));
}

async function checkConnectivityContrast(page) {
  const networkCount = await page.locator('[data-node-key^="network:"]').count();
  const selector = ".topology-connectivity-world .presentation-icon";
  assert.equal(await page.locator(selector).count(), networkCount);
  // Asset-only graphs use AssetIcon; the temporary filter icons are now closed.
  if (networkCount) await checkIdentityContrast(page, selector);
}

const accentLabel = key => key[0].toUpperCase() + key.slice(1);
const pickerTrigger = (page, label) => page.locator(".presentation-picker").getByRole("button", { name: new RegExp(`^${label} `) });
async function choosePresentation(page, label, key) {
  await pickerTrigger(page, label).click();
  const name = label === "Icon" ? PRESENTATION_ICONS.find(icon => icon.key === key).label : accentLabel(key);
  await page.getByRole("menuitemradio", { name, exact: true }).click();
  assert.equal(await page.getByRole("menu").count(), 0);
  assert.equal(await pickerTrigger(page, label).evaluate(el => el === document.activeElement), true);
}
async function checkPreview(page, icon, accent, name) {
  const preview = page.getByLabel("Presentation preview", { exact: true });
  assert.equal(await preview.locator("[data-presentation-icon]").getAttribute("data-presentation-icon"), icon);
  assert.equal(await preview.locator("[data-presentation-accent]").getAttribute("data-presentation-accent"), accent);
  assert.equal(await preview.innerText(), name);
}
async function checkCompactPicker(page, theme, width, surface) {
  assert.equal(await page.locator('.presentation-picker input[type="radio"]').count(), 0);
  assert.equal(await page.getByRole("menu").count(), 0);
  assert.equal(await page.getByText("Used for topology presentation only.", { exact: true }).count(), 1);
  const triggers = page.locator(".presentation-choice-trigger");
  const boxes = await triggers.evaluateAll(els => els.map(el => el.getBoundingClientRect().toJSON()));
  assert.equal(boxes[0].top, boxes[1].top, "Selectors share the existing desktop form grid");
  assert.ok((await page.locator(".presentation-picker").boundingBox()).height < 190, "Compact collapsed presentation section");
  await page.locator(".presentation-picker").scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${output}/${surface}-picker-edit-${theme}-${width}.png`, fullPage: true });
  for (const [label, names] of [["Icon", PRESENTATION_ICONS.map(icon => icon.label)], ["Accent", PRESENTATION_ACCENTS.map(accentLabel)]]) {
    const trigger = pickerTrigger(page, label);
    assert.equal(await trigger.getAttribute("aria-expanded"), "false");
    await trigger.focus();
    await page.keyboard.press("ArrowDown");
    const menu = page.getByRole("menu", { name: `Choose ${label.toLowerCase()}`, exact: true });
    await menu.waitFor();
    assert.deepEqual(await menu.getByRole("menuitemradio").allTextContents().then(values => values.map(value => value.replace("✓", "").trim())), names);
    assert.equal(await menu.locator('[aria-checked="true"]').count(), 1);
    assert.equal(await menu.locator('[aria-checked="true"]').evaluate(el => el === document.activeElement), true);
    assert.equal(await trigger.getAttribute("aria-expanded"), "true");
    assert.equal(await menu.getByRole("menuitemradio").first().evaluate(el => getComputedStyle(el).display), "flex", "Option icon, label and checkmark retain their layout");
    if (label === "Icon") await checkIdentityContrast(page, ".presentation-choice-menu .presentation-icon");
    const box = await menu.boundingBox();
    assert.ok(box.x >= 0 && box.x + box.width <= width && box.y >= 0 && box.y + box.height <= 1000, "Menu fits viewport");
    await page.keyboard.press("End");
    assert.equal(await menu.getByRole("menuitemradio").last().evaluate(el => el === document.activeElement), true);
    await page.keyboard.press("ArrowDown");
    assert.equal(await menu.getByRole("menuitemradio").first().evaluate(el => el === document.activeElement), true);
    await page.keyboard.press("ArrowRight");
    assert.equal(await menu.getByRole("menuitemradio").nth(1).evaluate(el => el === document.activeElement), true);
    await page.keyboard.press("Home");
    await page.keyboard.press("ArrowUp");
    assert.equal(await menu.getByRole("menuitemradio").last().evaluate(el => el === document.activeElement), true);
    await page.screenshot({ path: `${output}/${surface}-${label.toLowerCase()}-menu-${theme}-${width}.png`, fullPage: true });
    await page.keyboard.press("Escape");
    assert.equal(await menu.count(), 0);
    assert.equal(await trigger.evaluate(el => el === document.activeElement), true);
    await trigger.click();
    await page.keyboard.press("Tab");
    assert.equal(await menu.count(), 0);
    assert.equal(await page.locator(".resource-form").evaluate(el => el.contains(document.activeElement)), true);
    if (label === "Icon") assert.equal(await pickerTrigger(page, "Accent").evaluate(el => el === document.activeElement), true);
    if (label === "Accent") {
      await trigger.click();
      await page.keyboard.press("Shift+Tab");
      assert.equal(await pickerTrigger(page, "Icon").evaluate(el => el === document.activeElement), true);
    }
    await trigger.click();
    await page.locator('input[name="name"]').click();
    assert.equal(await menu.count(), 0, "Outside click dismisses menu");
  }
  // Select with the keyboard and verify the actual controlled form preview.
  await pickerTrigger(page, "Icon").focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("End");
  await page.keyboard.press("Enter");
  await pickerTrigger(page, "Accent").focus();
  await page.keyboard.press("Space");
  await page.keyboard.press("End");
  await page.keyboard.press("Space");
  await checkPreview(page, "application", "rose", await page.locator('input[name="name"]').inputValue());
}
// Evaluation is read-only diagnostics/assertions; every activation below is a
// real pointer click or keyboard input, including native label activation.
async function checkCategoryPointerInput(page, data, theme, width) {
  const filters = page.getByRole("button", { name: /^Filters(?: · \d+)?$/ });
  const panel = page.locator(".topology-filter-popover");
  const checkbox = name => panel.getByRole("checkbox", { name, exact: true });
  const row = name => panel.locator("label").filter({ has: page.getByRole("checkbox", { name, exact: true }) });
  const card = n => page.locator(`[data-platform-id="${id(n)}"]`);
  await page.getByRole("button", { name: "Platform", exact: true }).click();
  for (const expanded of [false, true]) {
    if (expanded) await page.getByRole("button", { name: "Expand Infrastructure Topology", exact: true }).click();
    await filters.click();
    const initial = await checkbox("Backup").isChecked();
    assert.equal(initial, true);
    const audit = await panel.evaluate(panel => {
      const inspect = element => {
        const box = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        const hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
        return { box: box.toJSON(), hit: hit?.outerHTML.slice(0, 300), intended: element === hit || element.contains(hit),
          pointerEvents: style.pointerEvents, zIndex: style.zIndex,
          before: getComputedStyle(element, "::before").content, after: getComputedStyle(element, "::after").content };
      };
      return { panel: inspect(panel), options: [...panel.querySelectorAll("label")].map(label => ({
        name: label.textContent, row: inspect(label), checkbox: inspect(label.querySelector("input")),
        text: inspect(label.querySelector(".presentation-identity > span:last-child")), icon: inspect(label.querySelector(".presentation-icon")),
      })) };
    });
    await writeFile(`${output}/filter-hit-test-${theme}-${width}-${expanded}.json`, JSON.stringify(audit, null, 2));
    assert.equal(audit.panel.pointerEvents, "auto");
    for (const option of audit.options) for (const part of ["row", "checkbox", "text", "icon"]) {
      assert.ok(option[part].intended, `${option.name} ${part} must receive the pointer: ${JSON.stringify(option[part])}`);
      assert.equal(option[part].pointerEvents, "auto");
      assert.ok(option[part].box.width > 0 && option[part].box.height > 0);
    }
    const backupState = async enabled => {
      assert.equal(await panel.isVisible(), true, "Inside interaction keeps the popover mounted");
      assert.equal(await checkbox("Backup").isVisible(), true);
      assert.equal(await checkbox("Backup").isChecked(), enabled);
      assert.equal(await checkbox("Backup").evaluate(input => input.matches(":checked")), enabled, "Native visible checkmark state");
      assert.equal(await filters.innerText(), enabled ? "Filters" : "Filters · 1");
      await card(34).waitFor({ state: enabled ? "visible" : "detached" });
    };
    // Start with the label/row, the path missed by the original acceptance.
    await row("Backup").click(); await backupState(!initial);
    const inputIds = await panel.getByRole("checkbox").evaluateAll(inputs => inputs.map(input => input.id));
    assert.equal(new Set(inputIds).size, data.categories.length);
    assert.ok(inputIds.every(Boolean));
    assert.equal(await row("Backup").getAttribute("for"), await checkbox("Backup").getAttribute("id"));
    await page.screenshot({ path: `${output}/filter-pointer-off-${theme}-${width}-${expanded}.png` });
    await row("Backup").click(); await backupState(initial);
    await checkbox("Backup").click(); await backupState(false);
    await checkbox("Backup").click(); await backupState(true);
    const text = row("Backup").locator(".presentation-identity > span:last-child");
    await text.click(); await backupState(false);
    await text.click(); await backupState(true);
    const bounds = await row("Backup").boundingBox();
    await row("Backup").click({ position: { x: bounds.width - 2, y: bounds.height / 2 } }); await backupState(false);
    await row("Backup").click({ position: { x: bounds.width - 2, y: bounds.height / 2 } }); await backupState(true);
    // A second category verifies icon activation and actual projection removal.
    await row("Compute").locator(".presentation-icon").click();
    assert.equal(await checkbox("Compute").isChecked(), false);
    assert.equal(await filters.innerText(), "Filters · 1");
    await card(30).waitFor({ state: "detached" });
    await row("Compute").locator(".presentation-icon").click();
    assert.equal(await checkbox("Compute").isChecked(), true);
    assert.equal(await filters.innerText(), "Filters");
    await card(30).waitFor();
    // Native Tab navigation focuses Workload then Uncategorized then Backup.
    await page.keyboard.press("Tab"); await page.keyboard.press("Tab"); await page.keyboard.press("Tab");
    assert.equal(await checkbox("Backup").evaluate(input => input === document.activeElement), true);
    await page.keyboard.press("Space"); await backupState(false);
    await page.keyboard.press("Space"); await backupState(true);
    await row("Backup").click();
    await row("Uncategorized").locator(".presentation-identity > span:last-child").click();
    assert.equal(await filters.innerText(), "Filters · 2");
    await card(150).waitFor();
    await panel.getByRole("button", { name: "Reset to defaults", exact: true }).click();
    await backupState(true);
    for (const category of data.categories) assert.equal(await checkbox(category.name).isChecked(), category.show_in_topology);
    await card(150).waitFor({ state: "detached" });
    await page.screenshot({ path: `${output}/filter-pointer-reset-${theme}-${width}-${expanded}.png` });
    // An uncovered heading inside the expanded dialog is outside the filter.
    await page.getByRole("heading", { name: "Infrastructure Topology", exact: true }).last().click();
    assert.equal(await panel.count(), 0);
    await filters.click(); await page.keyboard.press("Escape");
    assert.equal(await panel.count(), 0);
    assert.equal(await filters.evaluate(button => button === document.activeElement), true);
    await filters.click();
    await page.keyboard.press("Shift+Tab"); // First checkbox -> Filters.
    await page.keyboard.press("Shift+Tab"); // Filters -> outside the filter root.
    assert.equal(await panel.count(), 0, "Keyboard blur still dismisses after pointer use");
    if (expanded) await page.getByRole("button", { name: "Close expanded Infrastructure Topology", exact: true }).click();
  }
  await page.getByRole("button", { name: "Overview", exact: true }).click();
}

async function checkTopologyInteractions(page, data, requests, theme, width) {
  const button = name => page.getByRole("button", { name, exact: true });
  const filters = page.getByRole("button", { name: /^Filters(?: · \d+)?$/ });
  const panel = page.locator(".topology-filter-popover");
  const search = page.getByLabel("Search Assets", { exact: true });
  const expand = button("Expand Infrastructure Topology"), close = button("Close expanded Infrastructure Topology");
  const contextBefore = await page.locator(".context-selector").innerText();
  const originalUrl = page.url();
  const defaults = async () => {
    assert.equal(await filters.innerText(), "Filters");
    assert.equal(await filters.getAttribute("aria-expanded"), "false");
    await filters.click();
    for (const category of data.categories) assert.equal(await panel.getByLabel(category.name, { exact: true }).isChecked(), category.show_in_topology);
    await page.keyboard.press("Escape");
  };
  const overrides = async () => {
    await filters.click();
    await panel.getByLabel("Backup", { exact: true }).click();
    await panel.getByLabel("Uncategorized", { exact: true }).click();
    assert.equal(await filters.innerText(), "Filters · 2");
    await page.keyboard.press("Escape");
  };
  await button("Platform").click();
  const before = await page.locator(".topology-platform-grid").first().boundingBox();
  await filters.focus(); await page.keyboard.press("Enter");
  assert.equal(await filters.getAttribute("aria-expanded"), "true");
  assert.equal(await filters.getAttribute("aria-controls"), await panel.getAttribute("id"));
  assert.equal(await panel.getByRole("checkbox").count(), data.categories.length);
  assert.equal(await page.locator(".topology-category-filters").count(), 0);
  assert.equal(await panel.getByRole("checkbox").first().evaluate(el => el === document.activeElement), true);
  const box = await panel.boundingBox();
  assert.ok(box.width >= 320 && box.width <= 420 && box.x >= 0 && box.x + box.width <= width);
  assert.equal(await panel.locator(".topology-filter-options").evaluate(el => getComputedStyle(el).gridTemplateColumns.split(" ").length), 2);
  assert.equal((await page.locator(".topology-platform-grid").first().boundingBox()).y, before.y, "Opening filters does not move topology");
  const compute = panel.locator("label").filter({ has: page.getByLabel("Compute", { exact: true }) });
  assert.equal(await compute.locator('[data-presentation-icon="server"]').getAttribute("data-presentation-accent"), "blue");
  assert.ok((await compute.locator(".presentation-icon").boundingBox()).width <= 24);
  await checkIdentityContrast(page, ".topology-filter-popover .presentation-icon");
  await page.screenshot({ path: `${output}/filters-${theme}-${width}.png`, fullPage: true });
  await panel.getByLabel("Uncategorized", { exact: true }).click();
  assert.equal(await filters.innerText(), "Filters · 1");
  assert.equal(await page.locator(`[data-platform-id="${id(150)}"]`).count(), 1, "Toggles apply immediately");
  await panel.getByLabel("Uncategorized", { exact: true }).click();
  assert.equal(await filters.innerText(), "Filters");
  await panel.getByLabel("Backup", { exact: true }).click();
  await panel.getByLabel("Uncategorized", { exact: true }).click();
  await button("Reset to defaults").click();
  assert.equal(await panel.count(), 1);
  assert.equal(await filters.innerText(), "Filters");
  assert.equal(await panel.getByLabel("Backup", { exact: true }).isChecked(), true);
  assert.equal(await panel.getByLabel("Uncategorized", { exact: true }).isChecked(), false);
  await page.getByRole("heading", { name: "Infrastructure Topology", exact: true }).click(); assert.equal(await panel.count(), 0, "Outside click closes");
  await filters.click(); await page.keyboard.press("Escape");
  assert.equal(await panel.count(), 0);
  assert.equal(await filters.evaluate(el => el === document.activeElement), true);
  await filters.click(); await button("Reset to defaults").focus(); await page.keyboard.press("Tab");
  assert.equal(await panel.count(), 0, "Tab leaves the non-modal selector");
  assert.equal(await button("Refresh").evaluate(el => el === document.activeElement), true);

  const pve = page.locator(`[data-platform-id="${id(30)}"]`);
  await pve.getByRole("button", { name: "Show all 20 (+12 more)", exact: true }).click();
  await pve.locator(".topology-asset-identity").first().click();
  await search.fill("AdGuard"); await overrides();
  for (const action of [async () => { await expand.click(); await close.click(); }, async () => {
    const count = requests.filter(r => r === "/api/topology").length;
    await Promise.all([page.waitForResponse(response => new URL(response.url()).pathname === "/api/topology"), button("Refresh").click()]);
    assert.ok(requests.filter(r => r === "/api/topology").length > count);
  }]) {
    await action();
    assert.equal(await search.inputValue(), "AdGuard");
    assert.equal(await filters.innerText(), "Filters · 2");
    assert.equal(await page.locator(".topology-detail-inspector").count(), 1);
  }
  await button("Platform").click(); assert.equal(await search.inputValue(), "AdGuard", "Active tab does not reset");
  await filters.click(); await button("Overview").click();
  assert.equal(await page.locator(".topology-detail-inspector").count(), 0);
  await defaults();
  await overrides(); await expand.click(); await close.click();
  assert.equal(await filters.innerText(), "Filters · 2");
  await button("Platform").click();
  assert.equal(await search.inputValue(), "");
  assert.equal(await pve.locator(".topology-child").count(), 8);
  assert.equal(await page.locator(".topology-detail-inspector").count(), 0);
  await defaults();

  await button("Network & VLAN").click();
  const networkSearch = page.getByLabel("Search Networks and connected Assets", { exact: true });
  await page.locator(".topology-network-list").getByRole("button", { name: /^Management/ }).click();
  await networkSearch.fill("Management"); await overrides();
  await expand.click(); await close.click();
  assert.equal(await networkSearch.inputValue(), "Management");
  assert.match(await page.locator(".topology-network-heading").innerText(), /Management/);
  assert.equal(await filters.innerText(), "Filters · 2");
  await button("Platform").click(); await button("Network & VLAN").click();
  assert.equal(await networkSearch.inputValue(), "");
  assert.equal(await page.locator(".topology-network-heading").innerText(), "Default");
  await defaults();

  await button("Connectivity").click();
  const focus = page.getByLabel("Focus", { exact: true });
  const world = page.locator(".topology-connectivity-world");
  await world.waitFor();
  const defaultFocus = await focus.inputValue();
  await focus.selectOption(id(31)); await button("2 hops").click();
  await overrides(); await search.fill("PVE");
  await page.locator(`[data-node-key="asset:${id(36)}"]`).waitFor();
  await page.locator(`[data-node-key="asset:${id(36)}"]`).click();
  await page.getByLabel("Networks", { exact: true }).uncheck();
  await world.waitFor();
  const fitTransform = await world.evaluate(el => el.style.transform);
  await button("Zoom in").click();
  const zoomTransform = await world.evaluate(el => el.style.transform);
  assert.notEqual(zoomTransform, fitTransform);
  await page.locator(".topology-connectivity-viewport").evaluate(el => { el.scrollLeft += 50; el.scrollTop += 50; });
  const pan = await page.locator(".topology-connectivity-viewport").evaluate(el => [el.scrollLeft, el.scrollTop]);
  await page.waitForTimeout(50); // Let the native scroll event record the user pan.
  await expand.click();
  await filters.click(); await page.keyboard.press("Escape");
  assert.equal(await close.isVisible(), true, "First Escape dismisses only Filters");
  await close.click();
  await page.waitForFunction(expected => document.querySelector(".topology-connectivity-world")?.style.transform === expected, zoomTransform);
  assert.equal(await world.evaluate(el => el.style.transform), zoomTransform, "Expand preserves zoom");
  const restoredPan = await page.locator(".topology-connectivity-viewport").evaluate(el => [el.scrollLeft, el.scrollTop]);
  assert.ok(restoredPan.every((value, index) => Math.abs(value - pan[index]) <= 1), "Expand preserves pan");
  await Promise.all([page.waitForResponse(response => response.url().includes("/api/topology/connectivity?")), button("Refresh").click()]);
  assert.equal(await focus.inputValue(), id(31));
  assert.equal(await search.inputValue(), "PVE");
  assert.equal(await button("2 hops").getAttribute("aria-pressed"), "true");
  assert.equal(await page.getByLabel("Networks", { exact: true }).isChecked(), false);
  assert.equal(await filters.innerText(), "Filters · 2");
  assert.equal(await world.evaluate(el => el.style.transform), zoomTransform, "Refresh preserves zoom");
  assert.deepEqual(await page.locator(".topology-connectivity-viewport").evaluate(el => [el.scrollLeft, el.scrollTop]), restoredPan, "Refresh preserves pan");
  assert.equal(await page.locator('[aria-label="Topology inspector"] h2').innerText(), "USW-16-poe");
  await button("Platform").click(); await button("Connectivity").click(); await world.waitFor();
  assert.equal(await focus.inputValue(), defaultFocus);
  assert.equal(await search.inputValue(), "");
  assert.equal(await button("1 hop").getAttribute("aria-pressed"), "true");
  assert.equal(await page.getByLabel("Networks", { exact: true }).isChecked(), true);
  assert.equal(await page.locator(".topology-graph-node.is-selected:not(.is-focus)").count(), 0);
  const resetTransform = await world.evaluate(el => el.style.transform);
  await button("Fit").click(); assert.equal(await world.evaluate(el => el.style.transform), resetTransform);
  await defaults();
  // Existing intentional navigation supplies a fresh initial focus or Network.
  await button("Platform").click(); await pve.locator(".topology-asset-identity").first().click();
  await button("Focus Connectivity").click();
  assert.equal(await focus.inputValue(), id(30));
  await page.locator(`[data-node-key="asset:${id(30)}"]`).waitFor();
  await button("Platform").click(); await overrides();
  await page.locator(`[data-platform-id="${id(150)}"] .topology-asset-identity`).click();
  await button("Focus Connectivity").click();
  assert.equal(await focus.inputValue(), id(150), "Explicit navigation honours an Asset in a default-hidden category");
  await button("Platform").click(); await button("Connectivity").click();
  assert.equal(await focus.inputValue(), defaultFocus, "Ordinary tab entry discards that explicit focus");
  await button("Overview").click();
  await page.locator(".topology-network-row").filter({ hasText: /^Apps/ }).click();
  assert.equal(await page.locator(".topology-network-heading").innerText(), "Apps");
  await button("Overview").click();
  assert.equal(await page.locator(".context-selector").innerText(), contextBefore);
  assert.equal(page.url(), originalUrl, "Temporary controls do not write browser history");
  const backup = data.categories.find(category => category.name === "Backup");
  backup.show_in_topology = false;
  await Promise.all([page.waitForResponse(response => new URL(response.url()).pathname === "/api/topology"), button("Refresh").click()]);
  await button("Platform").click(); await defaults();
  backup.show_in_topology = true;
  await Promise.all([page.waitForResponse(response => new URL(response.url()).pathname === "/api/topology"), button("Refresh").click()]);
  await button("Overview").click(); await defaults();
}

async function checkTopologyHeaders(page) {
  for (const view of ["Overview", "Platform", "Network & VLAN", "Connectivity"]) {
    await page.getByRole("button", { name: view, exact: true }).click();
    for (const expanded of [false, true]) {
      if (expanded) await page.getByRole("button", { name: "Expand Infrastructure Topology", exact: true }).click();
      assert.equal(await page.getByText(/Recorded knowledge/).count(), 0, `${view}, expanded=${expanded}`);
      assert.equal(await page.locator(".topology-context").count(), 0);
      if (expanded) await page.getByRole("button", { name: "Close expanded Infrastructure Topology", exact: true }).click();
    }
  }
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  assert.equal(await page.getByRole("heading", { name: "Infrastructure Topology", exact: true }).count(), 1);
  assert.match(await page.locator(".context-selector").innerText(), /Customer.*Site/is);
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

async function checkStyleTokens(locator, expectations) {
  assert.ok(await locator.count(), "Style check has rendered elements");
  const results = await locator.evaluateAll((nodes, expectations) => nodes.flatMap(node => {
    const probe = document.createElement("span");
    node.append(probe);
    const style = getComputedStyle(node);
    const values = Object.entries(expectations).map(([property, token]) => {
      probe.style.color = `var(${token})`;
      return { element: node.className, property, actual: style[property], expected: getComputedStyle(probe).color };
    });
    probe.remove();
    return values;
  }), expectations);
  for (const result of results) assert.equal(result.actual, result.expected, `${result.element} ${result.property}`);
}

async function checkConnectivityRefocus(page, requests, theme, width) {
  const button = name => name === "Filters" ? page.locator(".topology-filter > button") : page.getByRole("button", { name, exact: true });
  const focus = page.getByLabel("Focus", { exact: true });
  const node = key => page.locator(`[data-node-key="${key}"]`);
  const world = page.locator(".topology-connectivity-world");
  const inspector = page.getByLabel("Topology inspector", { exact: true });
  const queryRequests = () => requests.filter(url => url.startsWith("/api/topology/connectivity?"));
  const adguard = `asset:${id(100)}`, pve = `asset:${id(30)}`, management = `network:${id(305)}`;
  const snapshot = () => world.evaluate(el => ({
    transform: el.style.transform,
    nodes: [...el.querySelectorAll("[data-node-key]")].map(n => [n.dataset.nodeKey, n.style.left, n.style.top]),
    pan: [el.closest(".topology-connectivity-viewport").scrollLeft, el.closest(".topology-connectivity-viewport").scrollTop],
  }));
  const waitFocus = async key => {
    await page.locator(`[data-node-key="${key}"].is-focus.is-selected`).waitFor();
    assert.equal(await focus.inputValue(), key.startsWith("asset:") ? key.slice(6) : key);
    assert.equal(await button("Focus Connectivity").count(), 0, "Focused selection has no redundant action");
  };
  const inspect = async (key, name, keyboard = false) => {
    const oldFocus = await focus.inputValue(), before = queryRequests().length, geometry = await snapshot();
    const original = await node(key).elementHandle();
    if (keyboard) { await node(key).focus(); await page.keyboard.press("Enter"); }
    else await node(key).click();
    await page.waitForTimeout(350); // Real single-click must remain inspection after the gesture settles.
    assert.equal(await inspector.locator("h2").innerText(), name);
    assert.equal(await focus.inputValue(), oldFocus);
    assert.equal(queryRequests().length, before, "Selection does not request connectivity");
    assert.deepEqual(await snapshot(), geometry, "Selection does not lay out, zoom or pan the graph");
    assert.equal(await original.evaluate(el => el.isConnected), true, "First click preserves the node for dblclick");
    assert.equal(await node(key).getAttribute("aria-pressed"), "true");
  };
  const refocus = async (key, action) => {
    const before = queryRequests().length;
    const prior = new URL(queryRequests().at(-1), base).searchParams;
    await action();
    await waitFocus(key);
    await page.waitForTimeout(100);
    assert.equal(queryRequests().length, before + 1, "Exactly one request per refocus gesture/action");
    const next = new URL(queryRequests().at(-1), base).searchParams;
    for (const parameter of ["hops", "show_networks", "category_ids"]) assert.deepEqual(next.getAll(parameter), prior.getAll(parameter), `${parameter} survives refocus`);
    const box = await node(key).boundingBox(), viewport = await page.locator(".topology-connectivity-viewport").boundingBox();
    assert.ok(Math.abs(box.x + box.width / 2 - viewport.x - viewport.width / 2) < 5, "New focus is horizontally centred");
    assert.ok(Math.abs(box.y + box.height / 2 - viewport.y - viewport.height / 2) < 5, "New focus is vertically centred");
    const fitted = await snapshot();
    await button("Fit").click();
    assert.deepEqual(await snapshot(), fitted, "Refocus already reset zoom/pan to Fit");
  };
  await waitFocus(adguard);
  await inspect(pve, "PVE1");
  await inspect(management, "Management");
  await button("2 hops").click();
  await node(`asset:${id(36)}`).waitFor();
  await button("Filters").click();
  await page.getByLabel("Backup", { exact: true }).uncheck();
  await page.keyboard.press("Escape");
  await world.waitFor();
  await page.getByLabel("Search Assets", { exact: true }).fill("AdGuard");
  await button("Zoom in").click();
  await page.locator(".topology-connectivity-viewport").evaluate(el => { el.scrollLeft += 70; el.scrollTop += 50; });
  await page.waitForTimeout(100);
  await refocus(pve, () => node(pve).dblclick());
  assert.equal(await inspector.locator("h2").innerText(), "PVE1");
  assert.equal(await button("2 hops").getAttribute("aria-pressed"), "true");
  assert.equal(await button("Filters").innerText(), "Filters · 1");
  assert.equal(await page.getByLabel("Search Assets", { exact: true }).inputValue(), "AdGuard");
  assert.equal(await node(`asset:${id(101)}`).count(), 1, "Explicit host focus admits hosted siblings");
  assert.equal(await node(`asset:${id(36)}`).count(), 1, "Switch path remains visible");
  await inspect(adguard, "AdGuard Home");
  await refocus(adguard, () => button("Focus Connectivity").click());
  await inspect(management, "Management");
  await refocus(management, () => node(management).dblclick());
  assert.equal(await inspector.locator("h2").innerText(), "Management");
  assert.equal(await node(`asset:${id(101)}`).count(), 1, "Explicit Network focus admits recorded peers");
  await page.screenshot({ path: `${output}/network-refocus-${theme}-${width}.png`, fullPage: true });
  await inspect(adguard, "AdGuard Home", true);
  await refocus(adguard, async () => { await button("Focus Connectivity").focus(); await page.keyboard.press("Enter"); });
  await inspect(management, "Management", true);
  await refocus(management, async () => { await button("Focus Connectivity").focus(); await page.keyboard.press("Space"); });
  const beforeRepeat = queryRequests().length;
  await node(management).dblclick();
  await page.waitForTimeout(100);
  assert.equal(queryRequests().length, beforeRepeat, "Double-click current focus is idempotent");
  await focus.selectOption(id(100)); await waitFocus(adguard);
  await page.getByLabel("Networks", { exact: true }).uncheck(); await world.waitFor();
  await refocus(pve, () => node(pve).dblclick());
  assert.equal(await page.getByLabel("Networks", { exact: true }).isChecked(), false);
  assert.equal(await page.locator('[data-node-key^="network:"]').count(), 0);
  // Restore initial settings for the existing presentation/geometry acceptance.
  await button("Filters").click(); await button("Reset to defaults").click(); await page.keyboard.press("Escape");
  await page.getByLabel("Search Assets", { exact: true }).fill("");
  await page.getByLabel("Networks", { exact: true }).check();
  await button("1 hop").click(); await focus.selectOption(id(100)); await waitFocus(adguard);
}

const neutralBorders = Object.fromEntries(["Top", "Right", "Bottom", "Left"].map(side => [`border${side}Color`, "--border"]));


async function checkTopologyLayers(page, data, theme, width) {
  const button = name => page.getByRole("button", { name, exact: true });
  const filters = page.locator(".topology-filter > button");
  const panel = page.locator(".topology-filter-popover");
  const layer = name => panel.getByRole("checkbox", { name, exact: true });
  const node = n => page.locator(`[data-node-key="asset:${id(n)}"]`);
  const waitGraph = async () => { await page.locator(".topology-connectivity-world").waitFor(); };
  // Real admin forms on the production bundle, with isolated persistence fixtures.
  for (const [key, name, classification] of [["connected_by_fibre", "Connected by fibre", "physical_network"], ["talks_to", "Talks to", "logical_operational"], ["paired_with", "Paired with", "other"]]) {
    await page.goto(`${base}/admin/relationship-types`);
    await button("Add Relationship type").click();
    assert.equal(await page.getByLabel(/^Topology layer/).inputValue(), "other");
    await page.getByLabel(/^Key/).fill(key);
    await page.getByLabel(/^Name/).fill(name);
    await page.getByLabel(/^Source label/).fill(name);
    await page.getByLabel(/^Target label/).fill(`Inverse ${name}`);
    await page.getByLabel(/^Topology layer/).selectOption(classification);
    await button("Create").click();
    const row = page.getByRole("row").filter({has: page.getByRole("cell", {name, exact:true})});
    await row.waitFor();
    assert.match(await row.innerText(), new RegExp(classification === "physical_network" ? "Physical / network" : classification === "logical_operational" ? "Logical / operational" : "Other"));
    await row.getByRole("button", {name:"Edit", exact:true}).click();
    assert.equal(await page.getByLabel(/^Topology layer/).inputValue(), classification);
    await page.getByLabel(/^Topology layer/).selectOption("data_resilience");
    await button("Save changes").click();
    await row.waitFor();
    assert.equal(data.relationship_types.find(r=>r.key===key).topology_layer, "data_resilience");
    await row.getByRole("button", {name:"Edit", exact:true}).click();
    await page.getByLabel(/^Topology layer/).selectOption(classification);
    await button("Save changes").click();
    await row.waitFor();
  }
  // NPM with a host, custom physical path, logical peer, Other peer and backup.
  const first = data.assets.find(a=>a.id===id(851));
  data.assets.push(...[[1300,"NPM"],[1301,"Fibre peer"],[1302,"Logical peer"],[1303,"Other peer"],[1304,"Backup peer"]].map(([n,name])=>({...first,id:id(n),name,asset_type:"server"})));
  data.relationship_types.push({key:"backs_up_to",source_label:"Backs up to",directional:true,topology_layer:"data_resilience"});
  for (const [n,key,target] of [[1310,"runs_on",30],[1311,"connected_by_fibre",1301],[1312,"talks_to",1302],[1313,"paired_with",1303],[1314,"backs_up_to",1304]]) {
    data.relationships.push({id:id(n),relationship_type:key,source_asset_id:id(1300),target_asset_id:id(target)});
  }
  data.asset_interfaces.push({id:id(1315),asset_id:id(1300),network_id:id(300),name:"eth0",ip_address:null});
  await page.goto(`${base}/topology`);
  await button("Connectivity").click();
  await page.getByLabel("Focus",{exact:true}).selectOption(id(1300));
  await node(1301).waitFor();
  assert.equal(await node(1302).count(),0);
  assert.equal(await node(1303).count(),0);
  assert.equal(await node(1304).count(),0);
  await filters.click();
  for (const [name,checked] of [["Platform / containment",true],["Physical / network",true],["Data / resilience",false],["Logical / operational",false],["Other",false]]) assert.equal(await layer(name).isChecked(),checked);
  await layer("Logical / operational").check();
  await node(1302).waitFor();
  await layer("Physical / network").uncheck();
  await node(1301).waitFor({state:"detached"});
  assert.equal(await page.locator('[data-node-key^="network:"]').count(),0);
  assert.equal(await filters.innerText(),"Filters · 2");
  await layer("Other").check(); await node(1303).waitFor();
  await layer("Data / resilience").check(); await node(1304).waitFor();
  assert.equal(await filters.innerText(),"Filters · 4");
  await page.keyboard.press("Escape");
  await button("Refresh").click(); await waitGraph();
  assert.equal(await filters.innerText(),"Filters · 4");
  await button("Expand Infrastructure Topology").click();
  assert.equal(await filters.innerText(),"Filters · 4");
  await filters.click();
  await layer("Other").uncheck(); await node(1303).waitFor({state:"detached"});
  await layer("Other").check(); await node(1303).waitFor();
  await page.screenshot({path:`${output}/relationship-layers-${theme}-${width}.png`});
  await page.keyboard.press("Escape");
  await button("Close expanded Infrastructure Topology").click();
  assert.equal(await filters.innerText(),"Filters · 4");
  await node(1302).dblclick(); await waitGraph();
  assert.equal(await filters.innerText(),"Filters · 4");
  await filters.click(); await button("Reset to defaults").click();
  assert.equal(await filters.innerText(),"Filters");
  assert.equal(await layer("Physical / network").isChecked(),true);
  assert.equal(await layer("Other").isChecked(),false);
  await layer("Other").check();
  await page.keyboard.press("Escape");
  await button("Platform").click();
  await filters.click(); assert.equal(await page.getByText("Relationship layers",{exact:true}).count(),0);
  await page.keyboard.press("Escape");
  await button("Connectivity").click(); await filters.click();
  assert.equal(await layer("Other").isChecked(),false);
  assert.equal(await filters.innerText(),"Filters");
  // Empty enabled layers must reach the API explicitly, not fall back to defaults.
  await layer("Platform / containment").uncheck();
  await layer("Physical / network").uncheck();
  await page.keyboard.press("Escape"); await waitGraph();
  assert.equal(await page.locator("[data-node-key]").count(),1);
}

const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
let checks = 0;
try {
  for (const theme of ["light", "dark"]) for (const width of [1440, 1100, 800]) {
    const data = fixture();
    const serviceType = { id: id(880), key: "application_service", name: "Application Service", active: true, requires_asset_dependency: true, sort_order: 10, in_use_count: 1, system_defined: true };
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
      if (url.pathname === "/api/relationship-types" && method === "POST") {
        const record = { ...route.request().postDataJSON(), id: id(1200 + data.relationship_types.length), system_defined: false, in_use_count: 0 };
        data.relationship_types.push(record);
        return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(record) });
      }
      if (url.pathname.startsWith("/api/relationship-types/") && method === "PATCH") {
        const record = data.relationship_types.find(r => r.id === url.pathname.split("/").at(-1));
        Object.assign(record, route.request().postDataJSON());
        return route.fulfill({ contentType: "application/json", body: JSON.stringify(record) });
      }
      if (url.pathname === `/api/service-types/${serviceType.id}` && method === "PATCH") {
        const payload = route.request().postDataJSON();
        assert.ok(!("key" in payload));
        Object.assign(serviceType, payload);
        return route.fulfill({ contentType: "application/json", body: JSON.stringify(serviceType) });
      }
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
      else if (url.pathname === "/api/relationship-types") body = data.relationship_types;
      else if (url.pathname === "/api/service-types") body = [serviceType];
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
    await page.goto(`${base}/admin/service-types`);
    const serviceRow = page.getByRole("row").filter({ hasText: "Application Service" });
    await serviceRow.waitFor();
    assert.doesNotMatch(await page.locator("main").innerText(), /Naming note|Runtime Service|Existing Assets are not migrated automatically/);
    assert.equal(await page.locator(".warning-banner").count(), 0);
    assert.equal(await page.getByRole("heading", { name: "Service types", exact: true }).count(), 1);
    assert.equal(await page.getByRole("button", { name: "Add Service type", exact: true }).count(), 1);
    assert.equal(await serviceRow.getByRole("button", { name: "Delete", exact: true }).count(), 0);
    await serviceRow.getByRole("button", { name: "Edit", exact: true }).click();
    assert.equal(await page.locator('input[name="key"]').isDisabled(), true);
    assert.equal(await page.locator('input[name="requires_asset_dependency"]').isChecked(), true);
    await page.locator('input[name="name"]').fill("Application capability");
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await page.getByRole("row").filter({ hasText: "Application capability" }).waitFor();
    await page.reload();
    await page.getByRole("row").filter({ hasText: "Application capability" }).waitFor();
    assert.equal(serviceType.key, "application_service");
    assert.equal(serviceType.requires_asset_dependency, true);
    await page.screenshot({ path: `${output}/service-types-${theme}-${width}.png`, fullPage: true });
    // Exercise administrator edits before checking all four topology surfaces.
    await page.goto(`${base}/admin/asset-categories`);
    for (const [name, icon, accent] of [["Compute", "server", "blue"], ["Workload", "cube", "green"]]) {
      const row = page.getByRole("row").filter({ has: page.getByRole("cell", {name, exact:true}) });
      await row.getByRole("button", {name:"Edit", exact:true}).click();
      if (name === "Compute") {
        await checkCompactPicker(page, theme, width, "category");
        await page.getByRole("button", {name:"Save changes", exact:true}).click();
        await page.locator(".resource-form").waitFor({state:"detached"});
        await page.reload();
        await row.getByRole("button", {name:"Edit", exact:true}).click();
        await checkPreview(page, "application", "rose", name);
        assert.equal(await pickerTrigger(page, "Icon").innerText(), "Application\n⌄");
        assert.equal(await pickerTrigger(page, "Accent").innerText(), "Rose\n⌄");
      }
      await choosePresentation(page, "Icon", icon);
      await choosePresentation(page, "Accent", accent);
      await checkPreview(page, icon, accent, name);
      await page.getByRole("button", {name:"Save changes", exact:true}).click();
      await page.locator(".resource-form").waitFor({state:"detached"});
    }
    await page.goto(`${base}/networks`);
    for (const [name, accent] of [["Management", "blue"], ["IoT", "purple"], ["Apps", "orange"], ["Infra", "red"]]) {
      const row = page.getByRole("row").filter({ has: page.getByRole("cell", {name, exact:true}) });
      await row.getByRole("button", {name:"Edit", exact:true}).click();
      if (name === "Management") {
        await checkCompactPicker(page, theme, width, "network");
        await page.getByRole("button", {name:"Save changes", exact:true}).click();
        await page.locator(".resource-form").waitFor({state:"detached"});
        await page.reload();
        await row.getByRole("button", {name:"Edit", exact:true}).click();
        await checkPreview(page, "application", "rose", name);
      }
      await choosePresentation(page, "Icon", "network");
      await choosePresentation(page, "Accent", accent);
      await checkPreview(page, "network", accent, name);
      await page.getByRole("button", {name:"Save changes", exact:true}).click();
      await page.locator(".resource-form").waitFor({state:"detached"});
    }
    await page.goto(`${base}/topology`);
    await page.getByRole("heading", { name:"Environment at a glance" }).waitFor();
    await checkTopologyHeaders(page);
    await checkCategoryPointerInput(page, data, theme, width);
    await checkTopologyInteractions(page, data, requests, theme, width);
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
    await page.getByLabel("Uncategorized", {exact:true}).click();
    assert.equal(await page.locator(".topology-metrics strong").first().innerText(), "34");
    const smallCategory = page.locator(".topology-summary-row").filter({hasText:"Uncategorized"});
    assert.equal(await smallCategory.locator(".asset-icon").count(),1);
    assert.equal(await smallCategory.locator(".topology-preview-more").count(),0);
    await page.getByLabel("Uncategorized", {exact:true}).click();
    await page.getByRole("button",{name:"Platform",exact:true}).click();
    const pve = page.locator(`[data-platform-id="${id(30)}"]`);
    assert.equal(await pve.locator(".topology-child").count(),8);
    assert.equal(await pve.getAttribute("data-presentation-accent"), "blue");
    assert.equal(await pve.locator(".topology-child").first().getAttribute("data-presentation-accent"), "green");
    assert.equal(await pve.locator(".topology-asset-identity .asset-icon").count(),9);
    assert.equal(await page.locator(".topology-platform-section > h2 [data-presentation-icon]").first().getAttribute("data-presentation-icon"), "server");
    await checkStyleTokens(page.locator(".topology-platform-card, .topology-child"), neutralBorders);
    await checkStyleTokens(page.locator(".topology-platform-section > h2"), { borderBottomColor: "--border", backgroundColor: "--identity-tint" });
    await checkStyleTokens(page.locator(".topology-child"), { backgroundColor: "--identity-tint" });
    await checkStyleTokens(page.locator(".topology-platform-section > h2 .presentation-icon"), { color: "--identity-foreground", backgroundColor: "--identity-tile" });
    assert.equal(await pve.evaluate(el => getComputedStyle(el).borderTopWidth), "2px", "Preserve card dimensions");
    for (const card of [pve, pve.locator(".topology-child").first()]) {
      const identity = card.locator(".topology-asset-identity").first();
      await identity.click();
      await checkStyleTokens(card, neutralBorders);
      assert.equal(await card.evaluate(el => getComputedStyle(el).outlineStyle), "none", "Platform selection adds no frame");
      await page.keyboard.press("Tab");
      await page.keyboard.press("Shift+Tab");
      assert.equal(await identity.evaluate(el => el.matches(":focus-visible") && getComputedStyle(el).outlineStyle !== "none"), true, "Platform keyboard focus remains visible");
      await page.getByRole("button", { name: "Close details", exact: true }).click();
    }
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
    await checkStyleTokens(page.locator(".topology-network-list button"), { borderBottomColor: "--border" });
    await checkStyleTokens(page.locator(".topology-network-list, .topology-network-detail"), neutralBorders);
    for (const name of ["Main", "IoT", "Apps", "Infra", "Default", "Management"]) {
      const network = data.networks.find(n=>n.name===name);
      const row = page.locator(".topology-network-list button").filter({has:page.locator("strong",{hasText:new RegExp(`^${name}$`)})});
      assert.equal(await row.getAttribute("data-presentation-accent"),network.accent_key);
      await row.click();
      assert.equal(await row.getAttribute("aria-current"), "true");
      await checkStyleTokens(row, { borderBottomColor: "--border", backgroundColor: "--identity-tile" });
      await checkStyleTokens(page.locator('.topology-network-list button:not([aria-current="true"])'), { backgroundColor: "--identity-tint" });
      const selectedStyle = await row.evaluate(el => {
        const css = getComputedStyle(el);
        return { outline: css.outlineStyle, shadow: css.boxShadow };
      });
      assert.equal(selectedStyle.outline, "none", "Pointer selection has no persistent outer outline");
      assert.equal(selectedStyle.shadow, "none", "Selection has no inset frame or glow");
      await page.keyboard.press("Tab");
      await page.keyboard.press("Shift+Tab");
      const focusStyle = await row.evaluate(el => {
        const css = getComputedStyle(el);
        return { focused: el.matches(":focus-visible"), outline: css.outlineStyle, width: css.outlineWidth };
      });
      assert.deepEqual(focusStyle, { focused: true, outline: "dashed", width: "3px" }, "Selected card retains keyboard focus indication");
      await checkStyleTokens(row, { outlineColor: "--text" });
      if (name === "Management") await page.screenshot({ path: `${output}/network-keyboard-focus-${theme}-${width}.png`, fullPage: true });
      await page.getByRole("heading", { name: "Infrastructure Topology", exact: true }).click();
      await checkStyleTokens(page.locator(".topology-network-heading"), { borderBottomColor: "--border", backgroundColor: "--identity-tint" });
      await checkStyleTokens(row.locator(".presentation-icon"), { color: "--identity-foreground", backgroundColor: "--identity-tile" });
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
    await page.getByLabel("Focus",{exact:true}).selectOption(id(100)).catch(async e => { await page.screenshot({ path: `${output}/failure.png` }); console.error(await page.locator("body").innerText()); throw e; });
    await page.locator(`[data-node-key="asset:${id(100)}"]`).waitFor();
    assert.equal(await page.locator("[data-node-key]").count(),4);
    await checkConnectivityRefocus(page, requests, theme, width);
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
    await checkStyleTokens(page.locator('.topology-graph-node:not(.is-focus)'), { borderTopColor: "--identity-border", backgroundColor: "--identity-tint" });
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
    await checkConnectivityContrast(page);
    await page.screenshot({ path:`${output}/adguard-two-hops-${theme}-${width}.png`,fullPage:true });
    await page.getByLabel("Focus",{exact:true}).selectOption(id(30));
    await page.getByRole("button",{name:"1 hop",exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll("[data-node-key]").length===22);
    await checkGeometry(page);
    await checkConnectivityContrast(page);
    await page.getByLabel("Focus",{exact:true}).selectOption(`network:${id(305)}`);
    await page.waitForFunction(()=>document.querySelectorAll("[data-node-key]").length===21);
    assert.equal(await page.locator(`[data-node-key="asset:${id(101)}"]`).count(),1);
    await checkGeometry(page);
    await checkConnectivityContrast(page);
    await page.locator(`[data-node-key="asset:${id(100)}"]`).click();
    assert.equal(await page.locator('[aria-label="Topology inspector"] h2').innerText(), "AdGuard Home");
    await page.getByRole("button",{name:"Focus Connectivity",exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll("[data-node-key]").length===4);
    await page.getByLabel("Focus",{exact:true}).selectOption(id(31));
    await page.getByRole("button",{name:"2 hops",exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll("[data-node-key]").length>=10);
    assert.ok(await page.locator("[data-node-key]").count()<=15);
    await checkGeometry(page);
    await checkConnectivityContrast(page);
    for (const control of ["Zoom in", "Zoom in", "Zoom out", "Fit"]) {
      await page.getByRole("button",{name:control,exact:true}).click();
      await checkGeometry(page);
    await checkConnectivityContrast(page);
    }
    if (width === 1440) assert.ok((await page.locator("[data-node-key]").first().boundingBox()).width >= 85, "Fit keeps 14-node cards readable on desktop");
    await page.screenshot({ path:`${output}/useful-two-hops-${theme}-${width}.png`,fullPage:true });
    await expand.click(); await close.waitFor();
    await checkGeometry(page);
    await checkConnectivityContrast(page);
    await page.getByRole("button", { name:"Zoom in",exact:true }).click();
    await page.locator(".topology-connectivity-viewport").evaluate(el => { el.scrollLeft += 60; el.scrollTop += 60; });
    await checkGeometry(page);
    await checkConnectivityContrast(page);
    await page.getByRole("button", { name:"Fit",exact:true }).click();
    await page.screenshot({ path:`${output}/useful-two-hops-expanded-${theme}-${width}.png`,fullPage:true });
    await close.click();
    await page.getByLabel("Focus",{exact:true}).selectOption(id(100));
    await page.waitForFunction(()=>document.querySelectorAll("[data-node-key]").length===5);
    await page.getByRole("button",{name:"Filters",exact:true}).click();
    await page.getByLabel("Compute",{exact:true}).click();
    await page.locator(`[data-node-key="asset:${id(30)}"]`).waitFor({state:"detached"});
    await page.getByLabel("Compute",{exact:true}).click();
    await page.keyboard.press("Escape");
    await page.locator(`[data-node-key="asset:${id(30)}"]`).waitFor();
    await page.getByRole("button",{name:"1 hop",exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll("[data-node-key]").length===4);
    const beforeGraphExpand = requests.filter(r => !r.includes("/icon?")).length;
    await expand.click(); await close.waitFor();
    assert.equal(requests.filter(r => !r.includes("/icon?")).length,beforeGraphExpand);
    assert.equal(await page.getByLabel("Focus",{exact:true}).inputValue(),id(100));
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
    await page.getByLabel("Focus",{exact:true}).selectOption(id(30));
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
    await choosePresentation(page, "Icon", "home");
    await choosePresentation(page, "Accent", "teal");
    await checkPreview(page, "home", "teal", "Home Automation");
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
    await checkPreview(page, "network", "blue", "Preview");
    await page.locator('input[name="name"]').fill("Custom Network");
    await choosePresentation(page, "Icon", "cloud");
    await choosePresentation(page, "Accent", "rose");
    await checkPreview(page, "cloud", "rose", "Custom Network");
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
    await page.getByLabel("Focus",{exact:true}).selectOption(id(851));
    await page.locator(`[data-node-key="network:${id(850)}"]`).waitFor();
    assert.equal(await page.locator(`[data-node-key="asset:${id(851)}"]`).getAttribute("data-presentation-accent"),"teal");
    assert.equal(await page.locator(`[data-node-key="network:${id(850)}"] [data-presentation-icon="cloud"]`).getAttribute("data-presentation-accent"),"rose");
    await checkTopologyLayers(page, data, theme, width);
    assert.deepEqual(errors,[]);
    console.log(`Passed topology and relationship layers: ${theme} ${width}px`);
    checks++; await context.close();
  }
  console.log(`Passed ${checks} topology/picker browser scenarios: Relationship Type Add/Edit defaults and persistence, custom Physical/Logical/Other traversal, layer defaults/toggles/count/reset/tab entry/refocus/expand/refresh/empty selection; Asset/Network single-click stability and double-click/inspector/keyboard refocus, exact request counts, preserved hops/filters/search/Network toggle, Fit/pan reset and Service Types edit without naming note; native filter checkbox/row/text/icon pointer clicks, hit-testing, visible checkmarks/content/count, keyboard/reset/dismissal in normal and expanded mode; compact menus, all registry options, keyboard/Escape/Tab/outside dismissal, focus return, live previews, edit/save/reload, all four normal/expanded headers without context line; category/Network form writes, Compute server/blue, Workload cube/green, Management blue then purple, IoT purple, Apps orange, Infra red, multihomed AdGuard, Home Automation home/teal, custom Network cloud/rose; light/dark at 1440, 1100 and 800px; 25-Asset preview, 20 PVE1 children, suppressed sibling/Network fan-out, genuine switch paths, direct host/Network focus, 14-node collision checks, icon/fallback containment during zoom/pan/Fit, limit notices, interface IPs, Assets cleanup and expanded-state preservation.`);
} finally { await browser.close(); }
