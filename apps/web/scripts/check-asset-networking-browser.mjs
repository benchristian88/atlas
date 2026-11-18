// All API requests are intercepted with fixtures.
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const modulePath = process.env.ATLAS_PLAYWRIGHT_MODULE;
const { chromium } = await import(modulePath ? pathToFileURL(modulePath).href : "playwright");
const base = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3145";
const output = process.env.ATLAS_SCREENSHOT_DIR;
const id = (n) => "00000000-0000-4000-8000-" + String(n).padStart(12, "0");
const customer = { id: id(1), name: "Homelab" };
const site = { id: id(2), customer_id: customer.id, name: "Lab" };
const otherSite = { ...site, id: id(3), name: "Other site" };
const asset = {
  id: id(4), customer_id: customer.id, site_id: site.id, hostname: "atlas-lab.example.net",
  name: "Atlas lab", asset_type: "fixture", status: "active", source: "manual",
};
const assignedNetwork = { id: id(5), customer_id: customer.id, site_id: site.id, name: "Curated LAN", vlan_id: 9 };
const otherNetwork = { ...assignedNetwork, id: id(6), site_id: otherSite.id, name: "Other site LAN" };
const observed = (predicate, value, source_name, accepted_at, last_observed_at) => ({
  predicate, value, source_name, accepted_at, last_observed_at, is_accepted: Boolean(accepted_at),
});
const bridge = observed("proxmox.bridge_name", "vmbr0", "Proxmox lab", "2026-11-17T12:30:00Z", "2026-11-17T12:00:00Z");
const oldTag = observed("proxmox.vlan_tag", 4, "Proxmox lab", "2026-11-17T14:00:00Z", "2026-11-17T13:00:00Z");
const newTag = observed("proxmox.vlan_tag", 5, "Proxmox lab discovery", null, "2026-11-18T01:00:00Z");
const gap = {
  id: id(7), status: "open", requirement_level: "required", requirement_name: "Managed presence requirement",
  summary: "A required field is missing.", severity: "high", last_evaluated_at: "2026-11-17T12:00:00Z",
  details_json: { field: "hostname", value: null, configuration_invalid: false },
};
const basePermissions = ["assets.view", "assets.edit", "customers.view", "sites.view"];
const viewPermissions = ["networks.view", "knowledge_gaps.view"];
const writePermissions = ["networks.create", "networks.edit", "networks.delete"];

async function run(browser, { width = 1440, theme = "dark", mode = "own", hostname = asset.hostname, gaps = [] }) {
  const page = await browser.newPage({ viewport: { width, height: 1000 }, colorScheme: theme });
  const errors = [], requests = [], writes = [];
  const interfaces = [{
    id: id(8), asset_id: asset.id, name: "eth0", ip_address: null, mac_address: "02:00:00:00:00:05",
    is_primary: false, notes: null, network_id: null, observed_facts: [bridge, oldTag, newTag],
  }, {
    id: id(9), asset_id: asset.id, name: "eth1", ip_address: "192.0.2.5", mac_address: null,
    is_primary: true, notes: "Keep", network_id: assignedNetwork.id, observed_facts: [newTag],
  }];
  let denyWrite = false;
  page.on("pageerror", (error) => errors.push(error.message));
  page.setDefaultTimeout(10000);
  await page.route("**/api/**", async (route) => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname.slice(4);
    const method = request.method();
    requests.push(path);
    let body = [], status = 200;
    if (path === "/auth/me") {
      const local = [...basePermissions, ...(mode === "asset-only" ? [] : viewPermissions),
        ...(mode === "own" ? writePermissions : [])];
      body = {
        id: id(99), display_name: "Fixture operator", email: "operator@example.test",
        theme_mode: theme, accent_colour: width === 800 ? "#2563EB" : width === 1024 ? "#7C3AED" : undefined,
        permissions: [...local, ...(mode === "other-site" ? writePermissions : [])],
        assignments: [
          { scope_type: "site", customer_id: customer.id, site_id: site.id, permissions: local },
          ...(mode === "other-site" ? [{ scope_type: "site", customer_id: customer.id, site_id: otherSite.id, permissions: writePermissions }] : []),
        ],
      };
    } else if (path === "/setup/status") body = { state: "INITIALISED" };
    else if (path === "/context") body = { global_access: false, customers: [customer], sites: [site, otherSite] };
    else if (path === "/assets/" + asset.id) body = { ...asset, hostname };
    else if (path.endsWith("/knowledge-summary")) body = { groups: [] };
    else if (path.endsWith("/fact-history")) body = { facts: {} };
    else if (path.endsWith("/completeness")) body = { active_gaps: gaps, resolved_gaps: [], summary: null };
    else if (path === "/networks") body = [assignedNetwork, otherNetwork];
    else if (path === "/asset-interfaces" && method === "GET") {
      assert.equal(url.searchParams.get("include_knowledge"), "true");
      body = interfaces.map(item => ({ ...item, assigned_network: item.network_id ? assignedNetwork : null }));
    } else if (path.startsWith("/asset-interfaces") && method !== "GET") {
      const payload = method === "DELETE" ? null : request.postDataJSON();
      writes.push({ method, payload });
      const item = interfaces.find(row => path.endsWith(row.id));
      if (denyWrite) {
        status = 403;
        body = { detail: "Permission denied" };
      } else if (method === "POST") {
        body = { ...payload, id: id(10), observed_facts: [] };
        interfaces.push(body);
        status = 201;
      } else if (method === "DELETE") {
        status = 409;
        body = { detail: "This interface is linked to retained discovery history and cannot be deleted." };
      } else if (payload.ip_address === "invalid") {
        status = 422;
        body = { detail: [{ msg: "Value error, invalid IP address" }] };
      } else {
        assert.equal(method, "PATCH");
        Object.assign(item, payload);
        const { observed_facts, ...record } = item;
        body = record;
      }
    }
    await route.fulfill({ status, json: body });
  });

  try {
    await page.goto(base + "/assets/" + asset.id);
    const card = page.getByRole("region", { name: "Networking", exact: true });
    const button = (region, name) => region.getByRole("button", { name, exact: true });
    const text = (region, value) => region.getByText(value, { exact: true });
    const terms = card.locator("dt");
    const row = (name) => card.getByRole("listitem").filter({ has: text(page, name) });
    const save = (form) => button(form, "Save").click();
    const capture = async (state) => {
      if (output && [1440, 390].includes(width)) {
        await card.screenshot({ path: join(output, "networking-" + width + "-" + state + ".png") });
      }
    };
    await card.waitFor();
    const showHostname = Boolean(hostname) || (gaps.includes(gap) && mode !== "asset-only");
    assert.equal(await text(page, "Hostname").count(), Number(showHostname));
    if (hostname) assert.equal(await text(card, hostname).count(), 1);
    if (!hostname && gaps.includes(gap) && mode !== "asset-only") await text(card, "Required, not recorded").waitFor();
    assert.ok(!requests.some(path => /requirements|reference-data/.test(path)));
    if (mode === "asset-only") {
      assert.equal(await text(card, "Interfaces").count(), 0);
      assert.equal(await card.getByRole("button").count(), 0);
      assert.ok(!requests.some(path => /^\/(networks|asset-interfaces)\b/.test(path) || path.endsWith("/completeness")));
      return;
    }

    const eth0 = row("eth0"), eth1 = row("eth1 · Primary");
    await text(eth0, "Not assigned").waitFor();
    await eth0.getByText(/^vmbr0 · VLAN tag 5$/).waitFor();
    await text(eth1, "Curated LAN · VLAN 9").waitFor();
    await text(eth1, "VLAN tag 5").waitFor();
    assert.equal(await eth0.locator("summary").count(), 1);
    assert.equal(await eth0.locator("details[open]").count(), 0);
    const newerSource = eth0.getByText(/^Proxmox lab discovery ·/);
    assert.equal(await newerSource.isVisible(), false);
    if (mode !== "own") {
      assert.equal(await button(card, "Edit").count(), 0);
      assert.equal(await button(card, "Delete").count(), 0);
      assert.equal(await button(card, "Add interface").count(), 0);
      return;
    }
    assert.deepEqual((await terms.allTextContents()).slice(0, 3), ["Hostname", "Assigned Atlas Network", "Observed Proxmox attachment"]);
    assert.match(await eth0.innerText(), /IP not recorded · MAC 02:00:00:00:00:05/);
    const positions = await eth0.locator("dt").evaluateAll(terms => terms.map(term => term.getBoundingClientRect().toJSON()));
    assert.equal(positions[0].y === positions[1].y, width > 600);
    assert.equal(await card.evaluate(el => el.scrollWidth <= el.clientWidth), true);
    await capture("summary");
    await text(eth0, "Discovery details").click();
    await newerSource.waitFor();
    assert.equal(await eth0.locator("details li").count(), 3);
    assert.equal(await text(eth0, "Accepted").count(), 2);
    await text(eth0, "Not accepted").waitFor();
    await capture("discovery");
    await text(eth0, "Discovery details").click();

    await button(eth1, "Edit").click();
    const editor = eth1.getByRole("form", { name: "Edit interface" });
    const name = editor.getByLabel("Interface name *");
    const network = editor.getByLabel("Assigned Atlas Network");
    const ip = editor.getByLabel("IP address");
    assert.equal(await name.inputValue(), "eth1");
    assert.equal(await ip.inputValue(), "192.0.2.5");
    assert.equal(await network.inputValue(), assignedNetwork.id);
    assert.equal(await editor.getByLabel("Primary interface").isChecked(), true);
    assert.equal(await editor.getByLabel("Notes").inputValue(), "Keep");
    assert.equal(await network.locator("option", { hasText: "Other site LAN" }).count(), 0);
    assert.equal(await editor.getByLabel(/Observed|VLAN tag|Bridge/).count(), 0);
    await capture("edit");
    await ip.fill("invalid");
    await save(editor);
    await text(editor.getByRole("alert"), "Value error, invalid IP address").waitFor();
    assert.equal(await ip.inputValue(), "invalid");
    await button(editor, "Cancel").click();
    assert.equal(await editor.count(), 0);
    assert.equal(writes.length, 1);

    await button(eth1, "Edit").click();
    await ip.fill("192.0.2.22");
    denyWrite = true;
    await save(editor);
    await text(editor.getByRole("alert"), "Permission denied").waitFor();
    assert.equal(await ip.inputValue(), "192.0.2.22");
    denyWrite = false;
    await save(editor);
    await text(eth1, "192.0.2.22").waitFor();
    assert.equal(await editor.count(), 0);
    assert.deepEqual(writes.at(-1), { method: "PATCH", payload: { ip_address: "192.0.2.22" } });
    await text(eth1, "Curated LAN · VLAN 9").waitFor();

    await button(eth1, "Edit").click();
    await network.selectOption("");
    await save(editor);
    await text(eth1, "Not assigned").waitFor();
    assert.deepEqual(writes.at(-1), { method: "PATCH", payload: { network_id: null } });
    await text(eth1, "VLAN tag 5").waitFor();

    await button(eth0, "Edit").click();
    const eth0Editor = eth0.getByRole("form", { name: "Edit interface" });
    await eth0Editor.getByLabel("Assigned Atlas Network").selectOption(assignedNetwork.id);
    await save(eth0Editor);
    await text(eth0, "Curated LAN · VLAN 9").waitFor();
    assert.deepEqual(writes.at(-1), { method: "PATCH", payload: { network_id: assignedNetwork.id } });

    await button(card, "Add interface").click();
    const add = card.getByRole("form", { name: "Add interface" });
    await add.getByLabel("Interface name *").fill("manual0");
    await button(add, "Add interface").click();
    await text(card, "manual0 · Primary").waitFor();
    assert.equal(writes.at(-1).method, "POST");
    assert.equal(writes.at(-1).payload.asset_id, asset.id);
    await text(row("manual0 · Primary"), "Observed attachment").waitFor();
    assert.equal(await row("manual0 · Primary").locator("details").count(), 0);

    page.once("dialog", (dialog) => dialog.dismiss());
    await button(eth0, "Delete").click();
    assert.equal(writes.at(-1).method, "POST");
    page.once("dialog", (dialog) => dialog.accept());
    await button(eth0, "Delete").click();
    await text(card.getByRole("alert"), "This interface is linked to retained discovery history and cannot be deleted.").waitFor();
    assert.equal(writes.at(-1).method, "DELETE");
    await eth0.waitFor();
    assert.equal(requests.filter(path => path === "/assets/" + asset.id).length, 1);
    assert.deepEqual(errors, []);
  } finally {
    await page.close();
  }
}

if (output) await mkdir(output, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
try {
  for (const [width, theme] of [[1440, "dark"], [1024, "light"], [800, "dark"], [390, "dark"]]) {
    await run(browser, { width, theme });
    console.log("PASS", width, theme, "layout, inline edits, validation, assignment, add and protected delete");
  }
  await run(browser, { mode: "other-site", hostname: null, gaps: [
    { ...gap, id: id(11), requirement_level: "recommended" },
    { ...gap, id: id(12), details_json: { ...gap.details_json, allowed_values: ["hostname"] } },
    { ...gap, id: id(13), details_json: { ...gap.details_json, configuration_invalid: true } },
    { ...gap, id: id(14), status: "exception" },
  ] });
  await run(browser, { mode: "other-site", hostname: "", gaps: [gap] });
  await run(browser, { mode: "asset-only" });
  console.log("PASS optional and required hostname gaps, Asset-only hostname access and wrong-site write denial");
} finally {
  await browser.close();
}
