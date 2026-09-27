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
export function singletonImpactRequest(serviceId, dependency, kind, group, changes, context = {}) {
  if (group) return { path: `/dependency-groups/${group.id}`, method: "PATCH", body: changes };
  return {
    path: `/services/${serviceId}/dependency-groups`, method: "POST",
    body: {
      name: availableDependencyName(`${friendlyContext(context.serviceName)} — ${friendlyContext(dependency.name || dependency.asset_name || dependency.target_service_name || "Provider")}`, context.groups), strategy: "all",
      requirement: dependency.required_for_operation ? "required" : "optional",
      failure_effect: "unknown", asset_dependency_ids: [], service_dependency_ids: [],
      [kind === "asset" ? "asset_dependency_ids" : "service_dependency_ids"]: [dependency.id],
      ...changes,
    },
  };
}

export function dependencyDetail(edge) {
  const labels = dependencySemanticsLabels(edge);
  return `${labels.requirement} · If unavailable: ${labels.failureEffect}${edge.dependency_group_name ? ` · ${dependencyGroupLabel(edge)} · ${labels.strategy}` : " · Impact not classified"}`;
}


const UUID_TEXT = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
function friendlyContext(value) {
  return typeof value === "string" && value.trim() && !UUID_TEXT.test(value) ? value.trim() : "Service";
}

// Display-only fallback for historical generated names. Never rewrite history
// or overwrite a deliberate readable name when simply presenting a group.
export function dependencyGroupLabel(group = {}, serviceName) {
  const name = group.dependency_group_name || group.name;
  if (name && !UUID_TEXT.test(name) && !/^Dependency (asset|service) (?:[0-9]+|[0-9a-f_-]{16,})$/i.test(name) && !/^Providers (?:[0-9a-f_-]{16,}\s*)+$/i.test(name)) return name;
  return `${friendlyContext(serviceName || group.source?.name)} Providers`;
}

export function availableDependencyName(base, groups = []) {
  const stem = friendlyContext(base).slice(0, 240);
  const existing = new Set(groups.map(group => group.name.toLocaleLowerCase()));
  let candidate = stem;
  for (let suffix = 2; existing.has(candidate.toLocaleLowerCase()); suffix++) candidate = `${stem} (${suffix})`;
  return candidate;
}
