import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { topologyPresentation, matchesSearch } from "../lib/infrastructure-topology.mjs";

const source = path => readFile(new URL(path, import.meta.url), "utf8");

test("Asset create and edit share a form with no legacy IP state, field or payload", async () => {
  const form = await source("../components/asset-form.js");
  assert.doesNotMatch(form, /ip_address|Primary IP/);
  assert.match(form, /Manage IP addresses through Interfaces/);
  for (const path of ["../app/assets/page.js", "../app/assets/[id]/edit/page.js"]) {
    const page = await source(path);
    assert.match(page, /<AssetForm/);
    assert.doesNotMatch(page, /ip_address/);
  }
});

test("Asset detail displays Interface addresses without a legacy summary or fallback", async () => {
  const page = await source("../app/assets/[id]/page.js");
  assert.doesNotMatch(page, /asset\.ip_address|Primary IP/);
  assert.match(page, /Interfaces and networks/);
  assert.match(page, /group.predicate !== "ip_address"/);
  assert.match(page, /knowledgeGroups.map/);
  assert.match(page, /item\.ip_address \|\| "No IP"/);
});

test("AdGuard interface summary and search ignore stale Asset IP even without interfaces", () => {
  const data = {
    assets: [{ id: "adguard", name: "AdGuard Home", asset_type: "server", ip_address: "192.0.2.254" }],
    asset_types: [{ key: "server", category_id: "compute" }], categories: [{ id: "compute" }],
    asset_interfaces: [
      { id: "i1", asset_id: "adguard", name: "eth1", ip_address: "192.168.5.5" },
      { id: "i0", asset_id: "adguard", name: "eth0", ip_address: "192.168.99.5", is_primary: true },
    ], networks: [], relationships: [], relationship_types: [], platform_links: [],
  };
  let asset = topologyPresentation(data, new Set(["compute"])).byId.adguard;
  assert.equal(asset.display_ip, "192.168.99.5 +1");
  for (const ip of ["192.168.99.5", "192.168.5.5"]) assert.equal(matchesSearch(asset, ip), true);
  assert.equal(matchesSearch(asset, "192.0.2.254"), false);
  for (const interfaces of [[], [{ id: "empty", asset_id: "adguard", name: "eth0", ip_address: null }]]) {
    data.asset_interfaces = interfaces;
    asset = topologyPresentation(data, new Set(["compute"])).byId.adguard;
    assert.equal(asset.display_ip, "");
    assert.equal(matchesSearch(asset, "192.0.2.254"), false);
  }
});

test("new knowledge requirements offer interface IP rules, preserving only existing legacy choices", async () => {
  const page = await source("../components/asset-knowledge-profile.js");
  assert.doesNotMatch(page.match(/const CORE_FIELDS = .*;/)[0], /ip_address/);
  assert.match(page, /alternative_field: "description"/);
  assert.match(page, /Interface has an IP address/);
  assert.match(page, /form.field === "ip_address" && <option/);
  assert.match(page, /form.alternative_field === "ip_address" && <option/);
  assert.match(page, /field: config.field \|\| config.rules\?\.\[0\]\?\.rule_config\?\.field/);
});
