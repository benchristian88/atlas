export const EDGE_FAMILY_BY_LEGACY_TYPE = Object.freeze({
  asset_asset: "asset_relationship",
  service_asset: "service_asset",
  service_service: "service_service",
  service_business_function: "service_business_function",
});

function legacyEndpointType(edgeType, endpoint) {
  if (edgeType === "asset_asset") return "asset";
  if (edgeType === "service_asset") return endpoint === "source" ? "service" : "asset";
  if (edgeType === "service_business_function") return endpoint === "source" ? "service" : "business_function";
  return "service";
}

export function normalizeOperationalGraph(graph = {}) {
  const nodes = (graph.nodes || []).map((node) => ({
    ...node,
    key: node.key || `${node.entity_type}:${node.entity_id || node.id}`,
    entity_id: node.entity_id || node.id,
  }));
  const nodesByKey = Object.fromEntries(nodes.map((node) => [node.key, node]));
  const edges = (graph.edges || []).map((edge) => {
    const family = edge.edge_family || EDGE_FAMILY_BY_LEGACY_TYPE[edge.edge_type] || edge.edge_type;
    const sourceKey = edge.source_key || `${legacyEndpointType(edge.edge_type, "source")}:${edge.source_id}`;
    const targetKey = edge.target_key || `${legacyEndpointType(edge.edge_type, "target")}:${edge.target_id}`;
    return {
      ...edge,
      key: edge.key || `${family}:${edge.edge_id || edge.id}`,
      edge_family: family,
      edge_id: edge.edge_id || edge.id,
      source_key: sourceKey,
      target_key: targetKey,
      source: nodesByKey[sourceKey] || null,
      target: nodesByKey[targetKey] || null,
    };
  }).filter((edge) => edge.source && edge.target);
  // Count distinct authorized relationships before presentation filtering. Retain
  // this size through repeated normalization so a hidden lane cannot flatten HA.
  const groupMembers = new Map();
  for (const edge of edges) if (edge.dependency_group_id) {
    const key = `${edge.source_key}:${edge.dependency_group_id}`;
    if (!groupMembers.has(key)) groupMembers.set(key, new Set());
    groupMembers.get(key).add(edge.key);
  }
  for (const edge of edges) if (edge.dependency_group_id) {
    edge.presentation_group_size = Math.max(edge.presentation_group_size || 0,
      groupMembers.get(`${edge.source_key}:${edge.dependency_group_id}`).size);
  }
  return {
    ...graph,
    nodes,
    edges,
    nodesByKey,
    truncated: Boolean(graph.truncated),
    warnings: graph.warnings || [],
  };
}
