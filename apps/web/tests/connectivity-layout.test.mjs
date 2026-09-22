import test from "node:test";
import assert from "node:assert/strict";
import { connectivityLayout, connectivityPreview, connectivityRoutes, connectivityBounds, connectivityFit, CONNECTIVITY_NODE_WIDTH, CONNECTIVITY_NODE_HEIGHT } from "../lib/infrastructure-topology.mjs";
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
  assert.ok(q.a.x > q.s1.x && q.a.x < q.s2.x, "Upstream parent centres over the combined subtree footprint");
  noOverlap(Object.values(q));
});

test("eight-child preview, stable name/ID order, local expansion, neighbour summaries, and canonical rail direction", () => {
  const graph=homelab(), before=structuredClone(graph), preview=connectivityPreview(graph);
  assert.deepEqual(preview.disclosures.h1, {hiddenCount:10, shownCount:8});
  assert.equal(preview.moreNodes.length,1);
  assert.equal(preview.nodes.filter(n=>n.key.startsWith("child1")).length,8);
  assert.equal(preview.nodes.filter(n=>n.key.startsWith("child2") || n.key.startsWith("child3")).length,0);
  assert.deepEqual(preview.nodes.filter(n=>n.key.startsWith("child1")).map(n=>n.key),Array.from({length:8},(_,i)=>`child1-0${i}`));
  const expanded=connectivityPreview(graph,{h1:"all"});
  assert.equal(expanded.nodes.filter(n=>n.key.startsWith("child1")).length,18);
  assert.equal(expanded.focus_key,graph.focus_key); assert.deepEqual(graph,before);
  const positions=layout(preview);
  assert.equal(new Set(Object.values(positions).filter(n=>n.key.startsWith("child1")).map(n=>n.y)).size,2);
  for(const e of preview.edges.filter(e=>e.platform_parent_key==="h1")) {
    const rail=connectivityRoutes(Object.values(positions),preview.edges)[e.key];
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
  assert.ok(graph.edges.filter(e=>e.kind==="membership").every(e=>connectivityRoutes(Object.values(p),graph.edges)[e.key]));
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


test("neighbour badges expand four children and eighteen children in two local stages", () => {
  const graph = homelab(); graph.focus_key = "s1";
  const initial = connectivityPreview(graph);
  assert.deepEqual(initial.disclosures.h1, {hiddenCount:18, shownCount:0});
  assert.deepEqual(initial.disclosures.h2, {hiddenCount:4, shownCount:0});
  assert.equal(initial.moreNodes.length, 0);
  const preview = connectivityPreview(graph, {h1:"preview", h2:"preview"});
  assert.equal(preview.nodes.filter(n=>n.key.startsWith("child1")).length,8);
  assert.equal(preview.nodes.filter(n=>n.key.startsWith("child2")).length,4);
  assert.equal(preview.disclosures.h2, undefined);
  assert.equal(preview.moreNodes[0].hiddenCount,10);
  assert.equal(preview.moreNodes[0].parent_key,"h1");
  const placed = layout({...preview, nodes:[...preview.nodes,...preview.moreNodes], edges:[...preview.edges,...preview.moreEdges]});
  assert.equal(placed[preview.moreNodes[0].key].rank, fixturePositions.workload.sort_order);
  assert.ok(placed[preview.moreNodes[0].key].y >= placed["child1-07"].y);
  noOverlap(Object.values(placed));
  const expanded = connectivityPreview(graph, {h1:"all", h2:"preview"});
  assert.equal(expanded.nodes.filter(n=>n.key.startsWith("child1")).length,18);
  assert.equal(expanded.moreNodes.length,0);
  assert.equal(expanded.focus_key,"s1");
});

test("disclosure respects returned edges, duplicates, Network membership and server clipping", () => {
  const graph = homelab();
  graph.truncated = true;
  graph.nodes = graph.nodes.filter(n=>!n.key.startsWith("child1-1")); // Ten available children.
  graph.nodes.push({...node("network","automatic"),entity_type:"network"});
  graph.edges.push({...edge("h1","network"),kind:"membership"});
  graph.edges.push({...graph.edges.find(e=>e.platform_parent_key==="h1"),key:"parallel"});
  let preview = connectivityPreview(graph);
  assert.equal(preview.moreNodes[0].hiddenCount,2);
  assert.equal(preview.truncated,true);
  assert.ok(preview.nodes.some(n=>n.key==="network"));
  graph.edges = graph.edges.filter(e=>e.platform_parent_key!=="h1");
  preview = connectivityPreview(graph);
  assert.equal(preview.disclosures.h1,undefined);
  assert.equal(preview.moreNodes.length,0);
});

test("shared children and cycles cannot hide focus or promise already visible children", () => {
  const graph = homelab();
  graph.edges.push(edge("h1","child1-00","child1-00"),edge("child1-00","h2","h2"));
  const preview = connectivityPreview(graph);
  assert.ok(preview.nodes.some(n=>n.key===graph.focus_key));
  assert.deepEqual(preview.disclosures.h2,{hiddenCount:4,shownCount:1});
  assert.equal(preview.moreNodes.find(n=>n.parent_key==="h2").hiddenCount,4);
  assert.deepEqual(connectivityPreview({...graph,nodes:[...graph.nodes].reverse(),edges:[...graph.edges].reverse()}).moreNodes.sort((a,b)=>a.key.localeCompare(b.key)), [...preview.moreNodes].sort((a,b)=>a.key.localeCompare(b.key)));
});

function assertRoutes(graph) {
  const nodes = connectivityLayout(graph), routes = connectivityRoutes(nodes, graph.edges);
  noOverlap(nodes);
  for (const edge of graph.edges) {
    const points = routes[edge.key].points;
    for (let i = 1; i < points.length; i++) {
      const [x, y] = points[i], [px, py] = points[i - 1];
      assert.ok(x === px || y === py, `${edge.key} has a diagonal`);
      for (const n of nodes) {
        const halfWidth = n.entity_type === "disclosure" ? 30 : CONNECTIVITY_NODE_WIDTH / 2;
        const halfHeight = n.entity_type === "disclosure" ? 30 : CONNECTIVITY_NODE_HEIGHT / 2;
        const intersects = x === px
          ? x > n.x - halfWidth && x < n.x + halfWidth && Math.max(y, py) > n.y - halfHeight && Math.min(y, py) < n.y + halfHeight
          : y > n.y - halfHeight && y < n.y + halfHeight && Math.max(x, px) > n.x - halfWidth && Math.min(x, px) < n.x + halfWidth;
        assert.ok(!intersects, `${edge.key} intersects ${n.key}`);
      }
    }
  }
  assert.deepEqual(connectivityRoutes([...nodes].reverse(), [...graph.edges].reverse()), routes);
  return { nodes, routes };
}
const arbitrary = (key, sort_order) => ({ ...node(key, "automatic"),
  topology_position: {id:`rank-${sort_order}`, key:`rank-${sort_order}`, name:`Position ${sort_order}`, sort_order} });

test("arbitrary three-position chain is vertical, empty ranks consume no space", () => {
  const graph = { focus_key:"two", nodes:[arbitrary("one",1), arbitrary("two",20), arbitrary("three",90)], edges:[edge("one","two"),edge("two","three")] };
  const {nodes,routes} = assertRoutes(graph);
  assert.equal(new Set(nodes.map(n=>n.x)).size,1);
  for(const route of Object.values(routes)) assert.equal(new Set(route.points.map(p=>p[0])).size,1);
  const p=Object.fromEntries(nodes.map(n=>[n.key,n]));
  assert.equal(p.two.y-p.one.y,p.three.y-p.two.y);
});

test("physical fan-out shares a horizontal rail and skipped positions retain separate clear drops", () => {
  const graph={focus_key:"origin",nodes:[arbitrary("origin",5),...["b1","b2","b3"].map(k=>arbitrary(k,6))],edges:["b1","b2","b3"].map(k=>edge("origin",k))};
  let result=assertRoutes(graph);
  assert.equal(new Set(Object.values(result.routes).map(r=>r.points[1][1])).size,1);
  graph.nodes.push(arbitrary("c1",7),arbitrary("c2",7));graph.edges.push(edge("origin","c1"),edge("origin","c2"));
  result=assertRoutes(graph);
  const p=Object.fromEntries(result.nodes.map(n=>[n.key,n]));
  assert.ok(p.b1.y===p.b2.y && p.b2.y===p.b3.y && p.c1.y===p.c2.y && p.c1.y>p.b1.y);
  const tracks=Object.values(result.routes).slice(-2).map(r=>r.points.filter((point,i,ps)=>i && point[0]===ps[i-1][0] && Math.abs(point[1]-ps[i-1][1])>100).map(p=>p[0]));
  assert.ok(tracks[0].some(x=>!tracks[1].includes(x)),"Deep targets have separate vertical drops");
});

test("first eight, connected more, and all branches expanded avoid cards and centre parents", () => {
  const graph=homelab();
  graph.nodes.push(arbitrary("appliance-a",6),arbitrary("appliance-b",6));
  graph.edges.push(edge("s1","appliance-a"),edge("s1","appliance-b"));
  for(const branches of [{}, {h1:"all",h2:"all",h3:"all"}]) {
    const preview=connectivityPreview(graph,branches);
    const {nodes}=assertRoutes({...preview,nodes:[...preview.nodes,...preview.moreNodes],edges:[...preview.edges,...preview.moreEdges]});
    const host=nodes.find(n=>n.key==="h1"), children=nodes.filter(n=>n.layout_parent_key==="h1");
    assert.equal(host.x,(Math.min(...children.map(n=>n.x))+Math.max(...children.map(n=>n.x)))/2);
  }
});

test("orthogonal tracks avoid intermediate grid cards, support reverse, same-band, cycles and membership", () => {
  const graph=homelab();
  graph.edges.push(edge("child1-00","child1-17"),edge("h1","h1"),edge("h3","s1"));
  graph.nodes.push({...node("network","automatic"),entity_type:"network"});
  for(const key of ["s1","h1","h3","child1-17"])graph.edges.push({...edge(key,"network"),kind:"membership",platform_parent_key:null});
  assertRoutes(graph);
});

test("bounded dense fixture routes deterministically without card collisions", () => {
  const nodes=Array.from({length:100},(_,i)=>arbitrary(`object-${String(i).padStart(3,"0")}`,i%5));
  const edges=[];
  for(let i=0;i<100;i++) for(let offset=1;offset<=5;offset++) edges.push(edge(nodes[i].key,nodes[(i+offset*13)%100].key));
  assertRoutes({focus_key:nodes[0].key,nodes,edges});
});

test("Fit uses actual route bounds, horizontal centring and fixed screen-space top padding", () => {
  const graph=homelab(), {nodes,routes}=assertRoutes(graph);
  const bounds=connectivityBounds(nodes,routes), fit=connectivityFit(bounds,800,600);
  assert.ok(bounds.width*fit.scale<=768+1e-9 && bounds.height*fit.scale<=568+1e-9);
  assert.equal(fit.top,16);
  for(const route of Object.values(routes))for(const [x,y] of route.points) {
    assert.ok(x>=bounds.minX && x<=bounds.minX+bounds.width);
    assert.ok(y>=bounds.minY && y<=bounds.minY+bounds.height);
  }
  const small=connectivityFit({width:200,height:100},1000,800);
  assert.equal(small.scale,1);assert.equal(small.top,16);assert.equal(small.canvasWidth,1000);
  const zoom=connectivityFit(bounds,800,600,4);
  assert.ok(zoom.canvasWidth>=800 && zoom.canvasHeight>=600);assert.equal(zoom.top,16);
});
