export const DEPENDENCY_STRATEGY_LABELS = Object.freeze({
  all: "All required",
  any: "Any one is sufficient",
});

export const DEPENDENCY_REQUIREMENT_LABELS = Object.freeze({
  required: "Required",
  optional: "Optional",
});

export const FAILURE_EFFECT_LABELS = Object.freeze({
  unavailable: "Service unavailable",
  degraded: "Service degraded",
  unknown: "Unknown",
});

export function dependencySemanticsLabels(dependency = {}) {
  const requirement = dependency.dependency_requirement
    || (dependency.required_for_operation ? "required" : "optional");
  return {
    requirement: DEPENDENCY_REQUIREMENT_LABELS[requirement] || "Unknown",
    strategy: dependency.dependency_strategy
      ? (DEPENDENCY_STRATEGY_LABELS[dependency.dependency_strategy] || "Unknown")
      : null,
    failureEffect: FAILURE_EFFECT_LABELS[dependency.failure_effect || "unknown"] || "Unknown",
  };
}

// Group state is canonical once a relationship belongs to a group.
export function singletonImpactRequest(serviceId, dependency, kind, group, changes) {
  if (group) return { path: `/dependency-groups/${group.id}`, method: "PATCH", body: changes };
  return {
    path: `/services/${serviceId}/dependency-groups`, method: "POST",
    body: {
      name: `Dependency ${kind} ${dependency.id}`, strategy: "all",
      requirement: dependency.required_for_operation ? "required" : "optional",
      failure_effect: "unknown", asset_dependency_ids: [], service_dependency_ids: [],
      [kind === "asset" ? "asset_dependency_ids" : "service_dependency_ids"]: [dependency.id],
      ...changes,
    },
  };
}

export function dependencyDetail(edge) {
  const labels = dependencySemanticsLabels(edge);
  return `${labels.requirement} · If unavailable: ${labels.failureEffect}${edge.dependency_group_name ? ` · ${edge.dependency_group_name} · ${labels.strategy}` : " · Impact not classified"}`;
}
