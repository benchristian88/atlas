import { normalizeOperationalGraph } from "./operational-graph.mjs";

export const LANES = [
  { type: "business_function", label: "Business Functions", description: "Why it matters" },
  { type: "service", label: "Services", description: "What delivers it" },
  { type: "asset", label: "Assets", description: "What implements it" },
];
export const RELATIONSHIPS = {
  service_business_function: "Supports / supported by",
  service_asset: "Provides / provided by",
  service_service: "Depends on",
  asset_relationship: "Structural Asset relationships",
};
export const DEFAULT_FAMILIES = Object.keys(RELATIONSHIPS).filter((key) => key !== "asset_relationship");
export const WIDGETS = Object.freeze([
  { id: "environment-summary", title: "Environment summary" },
  { id: "environment-overview", title: "Environment Overview" },
  { id: "attention", title: "Knowledge attention" },
  { id: "critical-services", title: "Critical Services" },
  { id: "recent-meaningful-changes", title: "Recent meaningful changes" },
]);

export function completenessPercent(node) {
  if (node?.required_total == null || node?.required_satisfied == null) return null;
  return node.required_total ? Math.round(node.required_satisfied / node.required_total * 100) : 100;
}

export function parseGraphState(params) {
  const focus = params.get("focus") || "";
  const valid = /^(asset|service|business_function):[0-9a-f-]{36}$/i.test(focus);
  return {
    focus: valid ? focus : "", depth: ["2", "3"].includes(params.get("depth")) ? Number(params.get("depth")) : 1,
    analysis: valid && !focus.startsWith("business_function:") && params.get("analysis") === "unavailable",
    types: params.has("types") ? params.get("types").split(",").filter((type) => LANES.some((lane) => lane.type === type)) : LANES.map((l) => l.type),
    families: params.has("relationships") ? params.get("relationships").split(",").filter((f) => f in RELATIONSHIPS) : DEFAULT_FAMILIES,
  };
}

export function graphHref(state = {}) {
  const params = new URLSearchParams();
  if (state.focus) params.set("focus", state.focus);
  if ([2, 3].includes(state.depth)) params.set("depth", String(state.depth));
  if (state.analysis && state.focus && !state.focus.startsWith("business_function:")) params.set("analysis", "unavailable");
  if (state.types) params.set("types", state.types.join(","));
  if (state.families) params.set("relationships", state.families.join(","));
  return `/knowledge-graph${params.size ? `?${params}` : ""}`;
}

// Connectivity is presentation-only and bidirectional, over the bounded API result.
export function projectVisibleGraph(graph, { types = LANES.map((l) => l.type), families = DEFAULT_FAMILIES, focus = "", analysis = false } = {}) {
  const normalized = normalizeOperationalGraph(graph);
  let nodes = normalized.nodes.filter((n) => n.key === focus || types.includes(n.entity_type));
  const candidates = new Set(nodes.map((n) => n.key));
  let edges = normalized.edges.filter((e) => families.includes(e.edge_family) && candidates.has(e.source_key) && candidates.has(e.target_key));
  const adjacent = new Map(nodes.map((n) => [n.key, []]));
  for (const edge of edges) {
    adjacent.get(edge.source_key).push(edge.target_key);
    adjacent.get(edge.target_key).push(edge.source_key);
  }
  // Analysis may include explanation context beyond the focused structural graph.
  if (!analysis) {
    if (focus) {
      const reachable = new Set(candidates.has(focus) ? [focus] : []);
      const queue = [...reachable];
      for (let i = 0; i < queue.length; i++) for (const key of adjacent.get(queue[i])) {
        if (!reachable.has(key)) { reachable.add(key); queue.push(key); }
      }
      nodes = nodes.filter((n) => reachable.has(n.key));
    } else {
      // Overview keeps genuinely unlinked knowledge, but not records orphaned by filters.
      const linked = new Set(normalized.edges.flatMap((e) => [e.source_key, e.target_key]));
      nodes = nodes.filter((n) => !linked.has(n.key) || adjacent.get(n.key).length);
    }
  }
  const visible = new Set(nodes.map((n) => n.key));
  edges = edges.filter((e) => visible.has(e.source_key) && visible.has(e.target_key));
  return { ...normalized, nodes, edges, nodesByKey: Object.fromEntries(nodes.map((n) => [n.key, n])) };
}

export function visibleGraphSelection(graph, selected, focus, group) {
  const edges = group ? graph.edges.filter((e) => e.dependency_group_id === group.dependency_group_id) : [];
  return {
    node: graph.nodesByKey[selected] || graph.nodesByKey[focus] || null,
    group: edges.length ? { ...group, edges } : null,
  };
}

export function presentLandscape(graph, { types = LANES.map((l) => l.type), families = DEFAULT_FAMILIES, limit = 8, expanded = [], selected = "", quick = "all", focus = "", analysis = false } = {}) {
  const normalized = normalizeOperationalGraph(graph);
  let { nodes, edges } = projectVisibleGraph(normalized, { types, families, focus, analysis });
  if (quick !== "all") {
    const serviceKeys = new Set(nodes.filter((n) => n.entity_type === "service" && (quick === "critical" ? n.criticality_rank >= 75 : n.open_gap_count > 0)).map((n) => n.key));
    const related = new Set(serviceKeys);
    for (const e of edges) if (serviceKeys.has(e.source_key) || serviceKeys.has(e.target_key)) { related.add(e.source_key); related.add(e.target_key); }
    nodes = nodes.filter((n) => related.has(n.key));
  }
  const lanes = LANES.map((lane) => {
    const all = nodes.filter((n) => n.entity_type === lane.type).sort((a, b) => a.name.localeCompare(b.name) || a.key.localeCompare(b.key));
    let shown = expanded.includes(lane.type) ? all : all.slice(0, limit);
    const pinned = all.filter((n) => n.key === focus || n.key === selected);
    for (const node of pinned) if (!shown.includes(node)) {
      const removable = shown.findLastIndex((n) => !pinned.includes(n));
      shown = shown.filter((_, index) => index !== removable);
      shown.push(node);
    }
    return { ...lane, nodes: shown, omitted: all.length - shown.length, total: all.length };
  });
  const visible = new Set(lanes.flatMap((l) => l.nodes.map((n) => n.key)));
  const filteredKeys = new Set(nodes.map((n) => n.key));
  edges = edges.filter((e) => filteredKeys.has(e.source_key) && filteredKeys.has(e.target_key));
  const visibleEdges = edges.filter((e) => visible.has(e.source_key) && visible.has(e.target_key));
  return { lanes, edges: visibleEdges, omittedEdges: edges.length - visibleEdges.length, filteredNodes: normalized.nodes.length - nodes.length };
}

export function analysisOverlay(graph, analysis) {
  const normalized = normalizeOperationalGraph(graph);
  if (!analysis) return normalized;
  const nodes = new Map(normalized.nodes.map((n) => [n.key, n]));
  const edges = new Map(normalized.edges.map((e) => [e.key, e]));
  const add = (entity) => { if (!nodes.has(entity.key)) nodes.set(entity.key, { ...entity, entity_type: entity.key.split(":")[0] }); };
  add(analysis.focus);
  for (const row of analysis.results) {
    add(row.service);
    for (const path of row.paths) { path.nodes.forEach(add); path.edges.forEach((e) => edges.set(e.key, e)); }
    for (const reason of row.reasons) for (const member of reason.members) { add(member.entity); edges.set(member.edge.key, member.edge); }
  }
  return normalizeOperationalGraph({ ...normalized, nodes: [...nodes.values()], edges: [...edges.values()] });
}

export function analysisState(node, analysis) {
  if (!analysis || node.entity_type === "business_function") return null;
  if (node.key === analysis.focus_key) return "unavailable";
  return analysis.results.find((r) => r.service.key === node.key)?.state || null;
}
