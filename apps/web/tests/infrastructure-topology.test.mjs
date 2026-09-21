import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { topologyPresentation, platformMatches, connectivityLayout, CHILD_PREVIEW_COUNT } from "../lib/infrastructure-topology.mjs";
import { assetListFiltersHref, parseAssetListFilters } from "../lib/asset-list-filters.mjs";

function fixture() {
  const categories = [{ id: "custom", name: "Home Automation Infrastructure", show_in_topology: true }, { id: "uncategorized", name: "Uncategorized", show_in_topology: false }];
  const hosts = Array.from({ length: 4 }, (_, i) => ({ id: `host${i}`, name: `PVE${i+1}`, asset_type: "docker_compose" }));
  const children = Array.from({ length: 20 }, (_, i) => ({ id: `child${i}`, name: i ? `Workload ${i}` : "AdGuard Home", asset_type: "docker_compose" }));
  return { categories, assets: [...hosts, ...children, { id: "standalone", name: "Synology", asset_type: "docker_compose" }, { id: "unknown", name: "Uncategorized Asset", asset_type: "other" }], asset_types: [{ key: "docker_compose", name: "Docker Compose", category_id: "custom" }, { key: "other", category_id: "uncategorized" }], platform_links: children.map(a => ({ parent_id: "host0", child_id: a.id })), networks: Array.from({ length: 12 }, (_, i) => ({ id: `network${i}`, name: `Network ${i}`, vlan_id: i === 11 ? 99 : i })), asset_interfaces: [{ id: "i0", asset_id: "child0", network_id: "network0" }, { id: "i1", asset_id: "child0", network_id: "network11" }, { id: "i2", asset_id: "unknown", network_id: "network0" }], relationships: [], relationship_types: [] };
}

test("dynamic category defaults, arbitrary type, standalone Assets and 20 children", () => {
  const data = fixture(), enabled = new Set(data.categories.filter(c => c.show_in_topology).map(c => c.id));
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
  const graph = { focus_key: "asset:focus", nodes: [{ key: "asset:focus", name: "Focus", distance: 0 }, ...Array.from({ length: 24 }, (_, i) => ({ key: `asset:${i}`, name: `Asset ${i}`, distance: i < 8 ? 1 : 2 }))] };
  const layout = connectivityLayout(graph);
  assert.deepEqual({ x: layout[0].x, y: layout[0].y }, { x: 550, y: 550 });
  assert.equal(new Set(layout.map(n => `${n.x}/${n.y}`)).size, 25);
  assert.ok(layout.every(n => n.x >= 100 && n.x <= 1000 && n.y >= 100 && n.y <= 1000));
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
