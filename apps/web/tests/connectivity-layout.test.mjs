import test from "node:test";
import assert from "node:assert/strict";
import { connectivityLayout, connectivityPreview, connectivityRail, CONNECTIVITY_NODE_WIDTH, CONNECTIVITY_NODE_HEIGHT } from "../lib/infrastructure-topology.mjs";
const fixturePositions = Object.fromEntries(["external", "security_edge", "routing", "aggregation_network", "access_network", "platform", "infrastructure", "workload", "endpoint"].map((key, sort_order) => [key, { id: key, key, name: key, sort_order, active: true }]));
const node = (key, position, distance = 1) => ({ key, entity_id: key, entity_type: "asset", name: key, topology_position: fixturePositions[position] || null, distance });
const edge = (source, target, parent = null) => ({ key: `${source}/${target}`, source_key: source, target_key: target, kind: "relationship", topology_class: parent ? "platform" : "physical_network", platform_parent_key: parent, directional: Boolean(parent) });
const layout = graph => Object.fromEntries(connectivityLayout(graph).map(n => [n.key, n]));
function noOverlap(nodes) {
  for (const [i, a] of nodes.entries()) for (const b of nodes.slice(i + 1)) assert.ok(Math.abs(a.x-b.x) >= CONNECTIVITY_NODE_WIDTH || Math.abs(a.y-b.y) >= CONNECTIVITY_NODE_HEIGHT, `${a.key} overlaps ${b.key}`);
}
function homelab() {
  const nodes = [node("e", "external"), node("f", "security_edge"), node("a", "aggregation_network"), node("s1", "access_network"), node("s2", "access_network"), ...[1,2,3].map(n => node(`h${n}`, "platform"))];
  const edges = [edge("e","f"), edge("f","a"), edge("a","s1"), edge("a","s2"), edge("s1","h1"), edge("s1","h2"), edge("s2","h3")];
  for (const [host, count] of [[1,18],[2,4],[3,3]]) for (let i=0;i<count;i++) {
    const key = `child${host}-${String(i).padStart(2,"0")}`;
    nodes.push(node(key,"workload",2)); edges.push(edge(key,`h${host}`,`h${host}`));
  }
  return { focus_key: "h1", nodes, edges };
}

test("managed positions with arbitrary names determine order, independent of focus or type keys", () => {
  const graph = { focus_key: "epsilon", nodes: [node("omega","security_edge"),node("alpha","aggregation_network"),node("zeta","platform"),node("epsilon","workload")], edges: [edge("omega","alpha"),edge("alpha","zeta"),edge("epsilon","zeta","zeta")] };
  const before = structuredClone(graph), p = layout(graph);
  assert.ok(p.omega.y < p.alpha.y && p.alpha.y < p.zeta.y && p.zeta.y < p.epsilon.y);
  assert.equal(p.epsilon.y, 0);
  assert.deepEqual(graph,before);
  graph.nodes.reverse(); graph.edges.reverse();
  assert.deepEqual(layout(graph),p);
});

test("missing bands collapse, no objects are invented, and multi-host grouping follows recorded fabric", () => {
  const small = {focus_key:"h",nodes:[node("s","access_network"),node("h","platform"),node("w","workload")],edges:[edge("s","h"),edge("w","h","h")]};
  const p=layout(small);
  assert.equal(Object.keys(p).length,3); assert.ok(p.s.y<p.h.y && p.h.y<p.w.y);
  const graph=homelab(), q=layout(graph);
  assert.equal(q.h1.y,q.h2.y); assert.equal(q.h2.y,q.h3.y);
  assert.ok(q.e.y<q.f.y && q.f.y<q.a.y && q.a.y<q.s1.y && q.s1.y<q.h1.y);
  assert.ok(q.h1.x<q.h2.x && q.h2.x<q.h3.x);
  assert.ok(Math.abs(q.h1.x-q.s1.x)<Math.abs(q.h1.x-q.s2.x));
  assert.equal(q.a.x,(q.s1.x+q.s2.x)/2);
  noOverlap(Object.values(q));
});

test("eight-child preview, stable name/ID order, local expansion, neighbour summaries, and canonical rail direction", () => {
  const graph=homelab(), before=structuredClone(graph), preview=connectivityPreview(graph);
  assert.equal(preview.hiddenCount,10); assert.equal(preview.childCount,18);
  assert.equal(preview.nodes.filter(n=>n.key.startsWith("child1")).length,8);
  assert.equal(preview.nodes.filter(n=>n.key.startsWith("child2") || n.key.startsWith("child3")).length,0);
  assert.deepEqual(preview.nodes.filter(n=>n.key.startsWith("child1")).map(n=>n.key),Array.from({length:8},(_,i)=>`child1-0${i}`));
  const expanded=connectivityPreview(graph,true);
  assert.equal(expanded.nodes.filter(n=>n.key.startsWith("child1")).length,18);
  assert.equal(expanded.focus_key,graph.focus_key); assert.deepEqual(graph,before);
  const positions=layout(preview);
  assert.equal(new Set(Object.values(positions).filter(n=>n.key.startsWith("child1")).map(n=>n.y)).size,2);
  for(const e of preview.edges.filter(e=>e.platform_parent_key==="h1")) {
    const rail=connectivityRail(e,positions,preview.edges);
    assert.ok(rail); assert.ok(rail.points[0][1]>rail.points.at(-1)[1],"runs_on arrow ends at host above child");
  }
  noOverlap(Object.values(positions));
  graph.nodes.reverse(); graph.edges.reverse();
  assert.deepEqual(new Set(connectivityPreview(graph).nodes.map(n=>n.key)),new Set(preview.nodes.map(n=>n.key)));
});

test("Automatic uses only relationship context; neutral fallback and cycles terminate deterministically", () => {
  const graph={focus_key:"strange",nodes:[node("n","access_network"),node("strange","automatic"),node("h","platform"),node("x","automatic"),node("alone","automatic")],edges:[edge("n","strange"),edge("strange","h"),edge("x","h","h")]};
  const p=layout(graph); assert.ok(p.n.y<p.strange.y && p.strange.y<p.h.y && p.h.y<p.x.y); assert.equal(p.alone.rank,4.5);
  const tree={focus_key:"p",nodes:[node("p","automatic"),node("c","automatic")],edges:[edge("c","p","p")]};
  assert.ok(layout(tree).p.y<layout(tree).c.y);
  tree.edges.push(edge("p","c","c"));
  const cycle=layout(tree); assert.equal(cycle.p.rank,0); assert.equal(cycle.c.rank,0); noOverlap(Object.values(cycle));
});

test("Network placement uses interface membership; multihomed Assets keep position ranks", () => {
  const graph={focus_key:"h",nodes:[node("s","access_network"),node("h","platform"),node("w","workload")],edges:[edge("s","h"),edge("w","h","h")]};
  const ranks=Object.fromEntries(Object.entries(layout(graph)).map(([k,n])=>[k,n.rank]));
  for(const n of ["blue","red"]) {graph.nodes.push({...node(n,"automatic"),entity_type:"network"});for(const asset of ["s","h","w"]) graph.edges.push({...edge(asset,n),kind:"membership",topology_class:null});}
  const p=layout(graph); for(const k of ["s","h","w"]) assert.equal(p[k].rank,ranks[k]);
  assert.ok(p.blue.rank>p.s.rank && p.blue.rank<p.w.rank);
  assert.ok(graph.edges.filter(e=>e.kind==="membership").every(e=>connectivityRail(e,p,graph.edges)===null));
  noOverlap(Object.values(p));
});

test("arbitrary managed keys, rename and reorder control bands without type-name rules", async () => {
  const { connectivityBands } = await import("../lib/infrastructure-topology.mjs");
  const positions = ["Alpha", "Beta", "Gamma", "Delta"].map((name, i) => ({ id: `position-${i}`, key: `custom_${i}`, name, sort_order: i * 10, active: true }));
  const graph = { focus_key: "thing-1", nodes: positions.map((position, i) => ({ ...node(`thing-${i}`, "automatic"), name: `Thing ${i}`, topology_position: position })), edges: [edge("thing-0", "thing-1"), edge("thing-1", "thing-2"), edge("thing-2", "thing-3")] };
  const before = layout(graph);
  assert.ok(before["thing-0"].y < before["thing-1"].y && before["thing-1"].y < before["thing-2"].y && before["thing-2"].y < before["thing-3"].y);
  positions[0].sort_order = 40; positions[0].name = "Renamed"; positions[0].active = false;
  const after = layout(graph);
  assert.ok(after["thing-3"].y < after["thing-0"].y, "Inactive assignments still honor configured order");
  assert.equal(connectivityBands(Object.values(after)).at(-1).positions[0].name, "Renamed");
  const storage = { id: "storage", key: "storage_fabric", name: "Storage Fabric", sort_order: 15, active: true };
  graph.nodes.push({ ...node("custom", "automatic"), topology_position: storage });
  graph.edges.push(edge("thing-1", "custom"), edge("custom", "thing-2"));
  const custom = layout(graph);
  assert.ok(custom["thing-1"].y < custom.custom.y && custom.custom.y < custom["thing-2"].y);
  graph.topology_positions = [...positions, storage, { id: "empty", key: "unused", name: "Empty", sort_order: 16 }];
  assert.equal(connectivityBands(connectivityLayout(graph)).length, 5, "Unused positions consume no band");
  noOverlap(Object.values(custom));
});
