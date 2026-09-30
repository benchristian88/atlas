import test from "node:test";
import assert from "node:assert/strict";
import { showcaseModel, showcaseLayout, showcaseFilename, SHOWCASE_MIN_SCALE } from "../lib/showcase.mjs";
import { showcaseFixture, id } from "./fixtures/showcase.mjs";
import { topologyPresentation, connectivityLayout } from "../lib/infrastructure-topology.mjs";

for (const size of ["small", "medium", "large"]) test(`${size}: complete, bounded, deterministic, host-local presentation`, () => {
  const data = showcaseFixture(size), before = structuredClone(data);
  const model = showcaseModel(data, id(2)), layout = showcaseLayout(model);
  assert.ok(layout.complete, layout.reason);
  assert.deepEqual(layout.representedAssetIds, data.assets.map(a => a.id).sort());
  assert.equal(new Set(layout.representedAssetIds).size, data.assets.length);
  assert.ok(layout.scale >= SHOWCASE_MIN_SCALE);
  for (const item of layout.items) {
    assert.ok(layout.x + item.x * layout.scale >= 0);
    assert.ok(layout.y + item.y * layout.scale >= 130);
    assert.ok(layout.x + (item.x + item.cardWidth) * layout.scale <= 1920);
    assert.ok(layout.y + (item.y + item.cardHeight) * layout.scale <= 1080);
  }
  for (const [index, a] of layout.items.entries()) for (const b of layout.items.slice(index + 1)) {
    assert.ok(a.x + a.cardWidth <= b.x || b.x + b.cardWidth <= a.x || a.y + a.cardHeight <= b.y || b.y + b.cardHeight <= a.y, `overlap ${a.name}/${b.name}`);
  }
  for (const route of layout.routes) for (let i = 1; i < route.points.length; i++) {
    const p = route.points[i - 1], q = route.points[i];
    assert.ok(p[0] === q[0] || p[1] === q[1]);
    for (const box of layout.items) {
      const crosses = p[0] === q[0] ? p[0] > box.x && p[0] < box.x + box.cardWidth && Math.max(p[1], q[1]) > box.y && Math.min(p[1], q[1]) < box.y + box.cardHeight : p[1] > box.y && p[1] < box.y + box.cardHeight && Math.max(p[0], q[0]) > box.x && Math.min(p[0], q[0]) < box.x + box.cardWidth;
      assert.equal(crosses, false, `route crosses ${box.name}`);
    }
  }
  assert.deepEqual(data, before);
  const shuffled = { ...data, assets: [...data.assets].reverse(), structural_edges: [...data.structural_edges].reverse() };
  assert.deepEqual(showcaseLayout(showcaseModel(shuffled, id(2))), layout);
  if (size === "small") assert.equal(layout.stage, 0);
  if (size === "large") assert.ok(layout.stage >= 1);
  if (size !== "small") {
    const categories = layout.items.filter(n => n.kind === "category" && n.name === "Media & Photos");
    assert.equal(categories.length, 2); assert.notEqual(categories[0].parent, categories[1].parent);
    for (const group of categories) for (const member of group.members) assert.equal(model.parents.get(member.key), group.parent);
    const wireless = layout.items.find(n => n.kind === "type" && n.name === "Wireless Access Point");
    assert.equal(wireless.members.length, 5); assert.equal(wireless.preview.length, 4); assert.equal(wireless.hiddenCount, 1);
    assert.equal(layout.edges.filter(e => e.source_key === wireless.key || e.target_key === wireless.key).length, 1);
    const rack = layout.items.find(n => n.name === "Rack Switch"), access = layout.items.find(n => n.name === "Access Switch A");
    assert.ok(access.y > rack.y); assert.equal(rack.position.id, access.position.id);
    for (const host of ["Platform Host A", "Platform Host B", "Physical Server A", "Physical Server B"]) assert.equal(layout.items.find(n => n.name === host)?.kind, "asset");
  }
  assert.ok(layout.footer);
});

test("all authorized categories, foreign-site defence and no unsupported edge leakage", () => {
  const data = showcaseFixture();
  data.assets.push({ ...data.assets[0], id: "hidden", site_id: id(999), name: "Secret" });
  data.structural_edges.push({ key: "hidden-edge", source_key: "asset:hidden", target_key: `asset:${data.assets[0].id}`, kind: "relationship" });
  const layout = showcaseLayout(showcaseModel(data, id(2)));
  assert.ok(layout.complete);
  assert.ok(!JSON.stringify(layout).includes("Secret"));
  assert.equal(layout.assetCount, data.assets.length - 1);
  assert.ok(layout.items.some(n => n.name === "Wireless Access Point"));
});

test("cycles, multi-parent hosting, membership and parallel connections are retained", () => {
  const data = showcaseFixture("small");
  const [gateway, core, host, photo, dns] = data.assets;
  data.structural_edges.push({ key: "cycle", source_key: `asset:${gateway.id}`, target_key: `asset:${host.id}`, platform_parent_key: `asset:${host.id}`, kind: "relationship", topology_class: "platform", directional: true });
  data.structural_edges.push({ key: "shared", source_key: `asset:${photo.id}`, target_key: `asset:${core.id}`, platform_parent_key: `asset:${core.id}`, kind: "relationship", topology_class: "platform", directional: true });
  data.networks.push({ id: id(400), name: "Lab Network" });
  for (const a of [photo, dns]) data.structural_edges.push({ key: `interface:${a.id}`, source_key: `asset:${a.id}`, target_key: `network:${id(400)}`, kind: "membership", topology_class: "physical_network", directional: false });
  const layout = showcaseLayout(showcaseModel(data, id(2)));
  assert.ok(layout.complete, layout.reason);
  assert.equal(layout.representedAssetIds.length, data.assets.length);
  assert.ok(layout.routes.some(r => r.relationshipKeys.includes("shared")));
  assert.ok(layout.routes.some(r => r.relationshipKeys.includes("cycle")));
  assert.equal(layout.routes.filter(r => r.kind === "membership").length, 2);
});

test("managed names and sort order, empty, missing context and unsupported fit", () => {
  const data = showcaseFixture("small");
  data.asset_types[0].topology_position.name = "My Edge";
  data.asset_types[0].topology_position.sort_order = 999;
  const layout = showcaseLayout(showcaseModel(data, id(2)));
  assert.ok(layout.complete);
  assert.equal(layout.items.find(n => n.name === "Gateway").position.name, "My Edge");
  assert.equal(showcaseLayout(showcaseModel(data, null)).complete, false);
  assert.equal(showcaseLayout(showcaseModel({ ...data, assets: [] }, id(2))).complete, false);
  assert.equal(showcaseLayout(showcaseModel({ ...data, structural_edges: undefined }, id(2))).complete, false);
  const huge = { ...data, structural_edges: [], assets: Array.from({ length: 500 }, (_, i) => ({ ...data.assets[0], id: id(2000 + i), name: `Independent router ${i}` })) };
  assert.match(showcaseLayout(showcaseModel(huge, id(2))).reason, /Showcase incomplete/);
});

test("existing Platform and Connectivity are not mutated by Showcase", () => {
  const data = showcaseFixture();
  const enabled = new Set(data.categories.map(c => c.id));
  const platform = topologyPresentation(data, enabled);
  const graph = { focus_key: `asset:${data.assets[0].id}`, nodes: data.assets.slice(0, 5).map((a, i) => ({ key: `asset:${a.id}`, name: a.name, entity_type: "asset", distance: i, topology_position: data.asset_types.find(t => t.key === a.asset_type)?.topology_position })), edges: data.structural_edges.slice(0, 4) };
  const connectivity = connectivityLayout(graph);
  showcaseLayout(showcaseModel(data, id(2)));
  assert.deepEqual(topologyPresentation(data, enabled), platform);
  assert.deepEqual(connectivityLayout(graph), connectivity);
});

test("safe deterministic filenames", () => {
  assert.equal(showcaseFilename("Ben’s Homelab"), "bens-homelab-atlas-showcase.png");
  assert.equal(showcaseFilename("../../ Café / Lab 😀"), "cafe-lab-atlas-showcase.png");
  assert.equal(showcaseFilename("💻"), "site-atlas-showcase.png");
});

test("default AP and disconnected endpoint groups retain counts; structural leaves stay named", () => {
  const data = showcaseFixture();
  const apType = data.asset_types.find(t => t.key === "ap");
  apType.key = "access_point"; apType.topology_position = data.asset_types.find(t => t.key === "switch").topology_position;
  data.assets.filter(a => a.asset_type === "ap").forEach(a => { a.asset_type = "access_point"; });
  const camera = data.assets.find(a => a.asset_type === "camera");
  data.assets.push(...Array.from({ length: 8 }, (_, i) => ({ ...camera, id: id(800 + i), name: `Loose Camera ${i}` })));
  const layout = showcaseLayout(showcaseModel(data, id(2)));
  assert.ok(layout.complete, layout.reason);
  assert.equal(layout.representedAssetIds.length, data.assets.length);
  assert.ok(layout.items.find(n => n.kind === "type" && n.type.key === "access_point"));
  const loose = layout.items.find(n => n.kind === "type" && n.members.some(m => m.name === "Loose Camera 0"));
  assert.equal(loose.members.length, 8); assert.equal(loose.hiddenCount, 4);
  assert.ok(!layout.edges.some(e => e.source_key === loose.key || e.target_key === loose.key));
  for (const a of data.assets.filter(a => ["platform", "server", "switch", "core", "gateway"].includes(a.asset_type))) assert.ok(layout.items.some(n => n.kind === "asset" && n.asset?.id === a.id));
});
