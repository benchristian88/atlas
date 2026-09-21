import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { topologyCategorySelection, topologyPresentation, platformMatches, connectivityLayout, CHILD_PREVIEW_COUNT, CATEGORY_PREVIEW_COUNT, compactInterfaceIp, matchesSearch, CONNECTIVITY_NODE_WIDTH, CONNECTIVITY_NODE_HEIGHT } from "../lib/infrastructure-topology.mjs";
import { assetListFiltersHref, parseAssetListFilters } from "../lib/asset-list-filters.mjs";

function fixture() {
  const categories = [{ id: "custom", name: "Home Automation Infrastructure", show_in_topology: true }, { id: "uncategorized", name: "Uncategorized", show_in_topology: false }];
  const hosts = Array.from({ length: 4 }, (_, i) => ({ id: `host${i}`, name: `PVE${i+1}`, asset_type: "docker_compose" }));
  const children = Array.from({ length: 20 }, (_, i) => ({ id: `child${i}`, name: i ? `Workload ${i}` : "AdGuard Home", asset_type: "docker_compose" }));
  return { categories, assets: [...hosts, ...children, { id: "standalone", name: "Synology", asset_type: "docker_compose" }, { id: "unknown", name: "Uncategorized Asset", asset_type: "other" }], asset_types: [{ key: "docker_compose", name: "Docker Compose", category_id: "custom" }, { key: "other", category_id: "uncategorized" }], platform_links: children.map(a => ({ parent_id: "host0", child_id: a.id })), networks: Array.from({ length: 12 }, (_, i) => ({ id: `network${i}`, name: `Network ${i}`, vlan_id: i === 11 ? 99 : i })), asset_interfaces: [{ id: "i0", asset_id: "child0", network_id: "network0" }, { id: "i1", asset_id: "child0", network_id: "network11" }, { id: "i2", asset_id: "unknown", network_id: "network0" }], relationships: [], relationship_types: [] };
}

test("dynamic category defaults, arbitrary type, standalone Assets and 20 children", () => {
  const data = fixture(), { enabled } = topologyCategorySelection(data.categories);
  const view = topologyPresentation(data, enabled);
  assert.equal(view.assets.length, 25);
  assert.equal(view.categories[0].name, "Home Automation Infrastructure");
  assert.equal(view.roots.length, 5);
  assert.equal(view.children.host0.length, 20);
  assert.equal(view.children.host0.slice(0, CHILD_PREVIEW_COUNT).length, 8);
  assert.equal(platformMatches(view.byId.host0, view.children, "AdGuard"), true);
  assert.equal(platformMatches(view.byId.host1, view.children, "AdGuard"), false);
  assert.equal(view.interfaces.length, 2);
  assert.deepEqual(view.interfaces.map(i => i.network_id), ["network0", "network11"]);
  assert.equal(view.networks.at(-1).vlan_id, 99);
  enabled.add("uncategorized");
  assert.equal(topologyPresentation(data, enabled).assets.length, 26);
});

test("category overrides count differences only and reset against current managed defaults", () => {
  const { categories } = fixture();
  assert.deepEqual(topologyCategorySelection(categories), { enabled: new Set(["custom"]), changedCount: 0 });
  const overrides = { custom: false, uncategorized: true, removedCategory: true };
  assert.deepEqual(topologyCategorySelection(categories, overrides), { enabled: new Set(["uncategorized"]), changedCount: 2 });
  assert.equal(topologyCategorySelection(categories, { custom: true, uncategorized: false }).changedCount, 0);
  categories[0].show_in_topology = false;
  categories[1].show_in_topology = true;
  assert.deepEqual(topologyCategorySelection(categories), { enabled: new Set(["uncategorized"]), changedCount: 0 });
  assert.equal(topologyCategorySelection(categories, overrides).changedCount, 0);
  assert.deepEqual(topologyCategorySelection([], overrides), { enabled: new Set(), changedCount: 0 });
});

test("cycles remain visible and filtering a parent does not lose its child", () => {
  const data = fixture();
  data.platform_links.push({ parent_id: "child0", child_id: "host0" });
  const view = topologyPresentation(data, new Set(["custom"]));
  assert.equal(view.cycleRoots.size, 1);
  assert.equal(view.roots.length, 5);
  data.assets.find(a => a.id === "host0").asset_type = "other";
  const filtered = topologyPresentation(data, new Set(["custom"]));
  assert.ok(filtered.roots.some(a => a.id === "child0"));
});

test("radial layout centres focus and remains deterministic with 25 nodes", () => {
  const graph = { focus_key: "asset:focus", nodes: [{ key: "asset:focus", name: "Focus", distance: 0 }, ...Array.from({ length: 24 }, (_, i) => ({ key: `asset:${i}`, name: `Asset ${i}`, distance: i < 8 ? 1 : 2, parent_key: i < 8 ? "asset:focus" : `asset:${i % 8}` }))] };
  const layout = connectivityLayout(graph);
  assert.deepEqual({ x: layout[0].x, y: layout[0].y }, { x: 0, y: 0 });
  assert.equal(new Set(layout.map(n => `${n.x}/${n.y}`)).size, 25);
  for (const [i, a] of layout.entries()) for (const b of layout.slice(i + 1)) {
    assert.ok(Math.abs(a.x - b.x) >= CONNECTIVITY_NODE_WIDTH || Math.abs(a.y - b.y) >= CONNECTIVITY_NODE_HEIGHT, `${a.key} overlaps ${b.key}`);
  }
  for (const n of layout.filter(n => n.distance === 2)) {
    const parent = layout.find(p => p.key === n.parent_key);
    assert.ok(n.x * parent.x + n.y * parent.y > 0, "Second hop shares its parent sector");
  }
  graph.nodes.reverse();
  assert.deepEqual(connectivityLayout(graph), layout);
});

test("managed category filter composes with existing Assets filters", () => {
  const categoryId = "a0877d05-048a-4c8f-a6cf-025e4b9317f5";
  const href = assetListFiltersHref({ categoryId, search: "compose", offset: 30 });
  assert.equal(parseAssetListFilters(new URL(href, "http://atlas.test").searchParams).categoryId, categoryId);
});

test("category form uses required managed choices and retains inactive current assignment", async () => {
  const form = await readFile(new URL("../app/admin/asset-types/page.js", import.meta.url), "utf8");
  assert.match(form, /name: "category_id", label: "Category", type: "select", required: true/);
  assert.match(form, /category.active \|\| category.id === form.category_id/);
  assert.match(form, /endpoint: "\/asset-categories"/);
  assert.doesNotMatch(form, /name: "category",|category: form.category/);
});


test("category preview is six of 25 and interface IP display is deterministic", () => {
  const data = fixture();
  const view = topologyPresentation(data, new Set(["custom"]));
  assert.equal(view.assets.length, 25);
  assert.equal(view.assets.slice(0, CATEGORY_PREVIEW_COUNT).length, 6);
  assert.equal(view.assets.length - CATEGORY_PREVIEW_COUNT, 19);
  assert.equal(compactInterfaceIp([]), "");
  const ips = [{ id: "b", name: "eth1", ip_address: "192.168.3.53" }, { id: "a", name: "eth0", ip_address: "192.168.99.21" }];
  assert.equal(compactInterfaceIp(ips.slice(0, 1)), "192.168.3.53");
  assert.equal(compactInterfaceIp(ips), "192.168.99.21 +1");
  assert.equal(compactInterfaceIp([...ips].reverse()), "192.168.99.21 +1");
  ips[0].is_primary = true;
  assert.equal(compactInterfaceIp(ips), "192.168.3.53 +1");
  assert.equal(compactInterfaceIp([...ips, { ...ips[0], id: "duplicate" }]), "192.168.3.53 +1");
  data.assets[0].ip_address = "192.0.2.111";
  data.asset_interfaces.push({ id: "ip", asset_id: data.assets[0].id, name: "eth0", ip_address: "192.0.2.222" });
  const asset = topologyPresentation(data, new Set(["custom"])).byId[data.assets[0].id];
  assert.equal(asset.display_ip, "192.0.2.222");
  assert.equal(matchesSearch(asset, "192.0.2.222"), true);
  assert.equal(matchesSearch(asset, "192.0.2.111"), false);
});

test("Assets table excludes legacy IP and both graphs use the same expand icon", async () => {
  const assets = await readFile(new URL("../app/assets/page.js", import.meta.url), "utf8");
  assert.doesNotMatch(assets, /asset\.ip_address|Hostname \/ IP/);
  for (const path of ["topology", "knowledge-graph"]) {
    const page = await readFile(new URL(`../app/${path}/page.js`, import.meta.url), "utf8");
    assert.match(page, /graph-icon-button/);
    assert.match(page, /NavigationIcon name="expand"/);
  }
});


test("shared topology header omits redundant context in normal and expanded views", async () => {
  const page = await readFile(new URL("../app/topology/page.js", import.meta.url), "utf8");
  assert.doesNotMatch(page, /Recorded knowledge|topology-context/);
  assert.match(page, /Infrastructure Topology/);
  assert.match(page, /ExpandedGraphSurface/);
});

test("relationship layer registry has safe defaults, independent overrides and reset", async () => {
  const { TOPOLOGY_LAYERS, topologyLayerSelection } = await import("../lib/infrastructure-topology.mjs");
  assert.equal(TOPOLOGY_LAYERS.length, 5);
  assert.deepEqual([...topologyLayerSelection().enabled], ["platform", "physical_network"]);
  const layers = topologyLayerSelection({ physical_network: false, logical_operational: true });
  assert.equal(layers.changedCount, 2);
  assert.deepEqual([...layers.enabled], ["platform", "logical_operational"]);
  assert.equal(layers.changedCount + topologyCategorySelection(fixture().categories, { uncategorized: true }).changedCount, 3);
  assert.equal(topologyLayerSelection({ platform: true, other: false }).changedCount, 0);
  assert.equal(topologyLayerSelection({}).changedCount, 0);
  assert.equal(topologyLayerSelection(Object.fromEntries(TOPOLOGY_LAYERS.map(l => [l.key, false]))).enabled.size, 0);
});
