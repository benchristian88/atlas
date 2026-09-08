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
