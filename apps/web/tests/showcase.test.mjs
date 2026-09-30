import test from "node:test";
import assert from "node:assert/strict";
import { showcaseModel, showcaseLayout, showcaseFilename, SHOWCASE_MIN_SCALE, SHOWCASE_CONTENT_TOP, SHOWCASE_MAX_HEIGHT } from "../lib/showcase.mjs";
import { showcaseFixture, showcaseRealShapeFixture, showcaseReferenceFixture, showcasePosterFixture, id } from "./fixtures/showcase.mjs";
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
    assert.ok(layout.y + item.y * layout.scale >= SHOWCASE_CONTENT_TOP);
    assert.ok(layout.x + (item.x + item.cardWidth) * layout.scale <= 1920);
    assert.ok(layout.y + (item.y + item.cardHeight) * layout.scale <= layout.sceneHeight);
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
    assert.equal(categories.length, size === "large" ? 2 : 1);
    if (size === "large") assert.notEqual(categories[0].parent, categories[1].parent);
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

test("cycles, multi-parent hosting and parallel structural connections survive Networks-off filtering", () => {
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
  assert.equal(layout.routes.filter(r => r.kind === "membership").length, 0);
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

function checkPoster(data) {
  const model = showcaseModel(data, id(2)), layout = showcaseLayout(model);
  assert.ok(layout.complete, JSON.stringify(layout.diagnostics));
  assert.equal(layout.sceneWidth, 1920);
  assert.ok(layout.sceneHeight >= 1080 && layout.sceneHeight <= SHOWCASE_MAX_HEIGHT);
  assert.ok(layout.scale >= .86);
  assert.deepEqual(layout.representedAssetIds, data.assets.map(a => a.id).sort());
  const shuffled = { ...data, assets: [...data.assets].reverse(), structural_edges: [...data.structural_edges].reverse(), asset_types: [...data.asset_types].reverse(), categories: [...data.categories].reverse() };
  assert.deepEqual(showcaseLayout(showcaseModel(shuffled, id(2))), layout);
  const boxes = [...layout.items.map(n => ({ ...n, width: n.cardWidth, height: n.cardHeight })), ...layout.positionLabels];
  if (layout.footer) boxes.push(layout.footer);
  for (const box of boxes) {
    assert.ok(layout.x + box.x * layout.scale >= 0);
    assert.ok(layout.y + box.y * layout.scale >= SHOWCASE_CONTENT_TOP);
    assert.ok(layout.x + (box.x + box.width) * layout.scale <= layout.sceneWidth);
    assert.ok(layout.y + (box.y + box.height) * layout.scale <= layout.sceneHeight);
  }
  for (const [i, a] of boxes.entries()) for (const b of boxes.slice(i + 1)) {
    if (a === layout.footer || b === layout.footer) continue;
    assert.ok(a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y, `overlap ${a.name}/${b.name}`);
  }
  for (const route of layout.routes) for (let i = 1; i < route.points.length; i++) {
    const p = route.points[i - 1], q = route.points[i];
    assert.ok(p[0] === q[0] || p[1] === q[1]);
    for (const [x, y] of [p, q]) {
      assert.ok(layout.x + x * layout.scale >= 0 && layout.x + x * layout.scale <= layout.sceneWidth);
      assert.ok(layout.y + y * layout.scale >= SHOWCASE_CONTENT_TOP && layout.y + y * layout.scale <= layout.sceneHeight);
    }
    for (const box of boxes) {
      if (box === layout.footer) continue;
      const crosses = p[0] === q[0] ? p[0] > box.x && p[0] < box.x + box.width && Math.max(p[1], q[1]) > box.y && Math.min(p[1], q[1]) < box.y + box.height : p[1] > box.y && p[1] < box.y + box.height && Math.max(p[0], q[0]) > box.x && Math.min(p[0], q[0]) < box.x + box.width;
      assert.equal(crosses, false, `route crosses ${box.name}`);
    }
  }
  assert.deepEqual(layout.routes.flatMap(r => r.relationshipKeys).sort(), data.structural_edges.filter(e => e.kind !== "membership").map(e => e.key).sort());
  for (const node of layout.items.filter(n => n.kind === "asset")) {
    assert.equal(node.cardWidth, 204); assert.equal(node.cardHeight, 44);
  }
  return { layout, model };
}

test("real homelab shape: all 50 Assets and actual nested host branches fit compactly", () => {
  const data = showcaseRealShapeFixture(), { layout, model } = checkPoster(data);
  assert.equal(data.assets.length, 50);
  assert.equal(layout.sceneHeight, 1080);
  assert.equal(layout.scale, 1, "The larger real-shape variant also fits without global shrinking");
  const byName = name => layout.items.find(n => n.name === name);
  for (const [parent, child] of [["Gateway", "Aggregation Switch"], ["Aggregation Switch", "Distribution Switch"], ["Distribution Switch", "Access Switch A"], ["Distribution Switch", "Platform Host A"], ["Platform Host A", "Container Host A"], ["Platform Host A", "Container Host B"], ["Aggregation Switch", "Physical Host A"], ["Physical Host A", "Isolated Platform A"]]) {
    assert.equal(model.parents.get(byName(child).key), byName(parent).key);
    assert.ok(byName(child).y > byName(parent).y);
  }
  for (const group of layout.items.filter(n => n.kind === "category")) for (const member of group.members) assert.equal(model.parents.get(member.key), group.parent);
  assert.equal(layout.items.filter(n => n.kind === "category" && n.name === "Media & Photos").length, 3);
  const ap = layout.items.find(n => n.kind === "type");
  assert.equal(ap.members.length, 5); assert.equal(ap.preview.length, 4); assert.equal(ap.hiddenCount, 1);
  assert.equal(layout.routes.filter(r => r.source_key === ap.key || r.target_key === ap.key).length, 1);
  assert.ok(layout.footer.width < layout.sceneWidth / 2, "Disconnected region follows its actual content");
  assert.ok(layout.positionLabels.length < layout.items.filter(n => n.kind === "asset").length);
  assert.ok(layout.positionLabels.every(label => label.height === 14));
});

test("Connectivity-shaped 44-Asset reference fits 16:9 at native scale, including the office side branch", () => {
  const data = showcaseReferenceFixture(), { layout, model } = checkPoster(data);
  assert.equal(data.assets.length, 44);
  assert.equal(layout.sceneHeight, 1080);
  assert.equal(layout.scale, 1);
  const byName = name => layout.items.find(n => n.name === name);
  assert.equal(model.parents.get(byName("Office Platform").key), byName("Access Switch A").key);
  const office = byName("Office Automation");
  assert.equal(office.kind, "asset");
  assert.equal(model.parents.get(office.key), byName("Office Platform").key);
  assert.ok(layout.items.filter(n => n.kind === "category").every(n => n.hiddenCount === 0), "All workloads fit, with no forced four-member truncation");
  assert.ok(layout.items.some(n => n.kind === "category" && n.memberColumns >= 3));
  assert.ok(layout.items.some(n => n.kind === "category" && n.memberColumns === 4));
  for (const node of layout.items.filter(n => n.kind === "asset")) assert.ok(node.members.length === 1);
});

for (const [name, data, height] of [
  ["small", showcaseFixture("small"), 1080],
  ["large grouped", showcaseFixture("large"), 1080],
  ["adaptive", showcasePosterFixture(50), 1113],
  ["near maximum", showcasePosterFixture(50, 4), 1347],
]) test(`${name}: preferred/minimal adaptive dimensions, readable complete geometry`, () => {
  const { layout } = checkPoster(data);
  assert.equal(layout.sceneHeight, height);
  if (height > 1080) {
    assert.equal(layout.diagnostics.attempts.length, 5);
    assert.ok(layout.diagnostics.attempts.every(a => a.requiredScale < .86));
    assert.ok((height - 1 - SHOWCASE_CONTENT_TOP - 32) / layout.diagnostics.sceneHeight < .86, "One pixel less height would breach the scale floor");
  }
});

test("pathological structure still refuses export and explains the fit in internal diagnostics", () => {
  const data = showcasePosterFixture(70), layout = showcaseLayout(showcaseModel(data, id(2)));
  assert.equal(layout.complete, false);
  assert.match(layout.reason, /Showcase incomplete/);
  assert.equal(layout.items, undefined, "No partial scene is returned");
  const d = layout.diagnostics;
  assert.equal(d.assetCount, 142); assert.equal(d.structuralNodeCount, 142);
  assert.equal(d.collapsedGroupCount, 0); assert.equal(d.workloadCategoryCount, 0);
  assert.equal(d.rootCount, 1); assert.equal(d.chosenPosterHeight, 1358);
  assert.equal(d.readabilityFloor, .86); assert.equal(d.failureReason, "height");
  assert.ok(d.sceneWidth > 0 && d.sceneHeight > 1358);
  assert.ok(d.requiredScale < d.readabilityFloor);
});


test("Networks off removes only logical entities/membership, with no layout reservations or input mutation", () => {
  const data = showcaseReferenceFixture(), before = structuredClone(data);
  const layout = showcaseLayout(showcaseModel(data, id(2)));
  const assetOnly = { ...data, networks: [], asset_interfaces: [], structural_edges: data.structural_edges.filter(e => e.kind !== "membership") };
  assert.deepEqual(layout, showcaseLayout(showcaseModel(assetOnly, id(2))));
  assert.deepEqual(data, before);
  assert.ok(layout.items.every(n => !n.network));
  assert.ok(layout.routes.every(e => e.kind !== "membership"));
  for (const name of ["Gateway", "Aggregation Switch", "Distribution Switch", "Access Switch A", "Physical Host A", "Isolated Platform A"]) assert.ok(layout.items.some(n => n.name === name));
  data.assets[0].name = "Default"; // Names never decide entity eligibility.
  assert.ok(showcaseLayout(showcaseModel(data, id(2))).items.some(n => n.name === "Default" && n.asset));
});

test("singleton categories stay directly under their own hosts; multiple members remain locally grouped", () => {
  const data = showcaseFixture("medium"), model = showcaseModel(data, id(2)), layout = showcaseLayout(model);
  const hosts = data.assets.filter(a => a.asset_type === "platform");
  const groups = layout.items.filter(n => n.kind === "category" && n.name === "Media & Photos");
  assert.equal(groups.length, 1);
  assert.equal(groups[0].parent, `asset:${hosts[0].id}`);
  assert.equal(groups[0].members.length, 6);
  const singleton = layout.items.find(n => n.asset?.asset_type === "media" && model.parents.get(n.key) === `asset:${hosts[1].id}`);
  assert.equal(singleton.kind, "asset");
  assert.ok(layout.routes.some(e => [e.source_key, e.target_key].includes(singleton.key) && [e.source_key, e.target_key].includes(`asset:${hosts[1].id}`)));
  assert.ok(layout.items.filter(n => n.kind === "category").every(n => n.members.length >= 2));
  const large = showcaseLayout(showcaseModel(showcaseFixture("large"), id(2)));
  for (const group of large.items.filter(n => n.kind === "category")) assert.equal(group.preview.length + group.hiddenCount, group.members.length);
});
