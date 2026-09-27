// Input is the normalized, authorized graph. Counts and links use the same set
// of resolvable Service dependencies; dangling records cannot imply hidden data.
export function dependencyAttention(graph) {
  if (!graph) return { unknown: undefined, ungrouped: undefined, relationships: [] };
  const dependencies = graph.edges.filter(edge => ["service_asset", "service_service"].includes(edge.edge_family) && edge.source.entity_type === "service");
  return {
    unknown: dependencies.filter(edge => !edge.failure_effect || edge.failure_effect === "unknown").length,
    ungrouped: dependencies.filter(edge => !edge.dependency_group_id).length,
    relationships: dependencies.filter(edge => !edge.dependency_group_id || !edge.failure_effect || edge.failure_effect === "unknown"),
  };
}
