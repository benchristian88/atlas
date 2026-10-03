// Presentation of recorded values only; never infer operational consequences.
const groups = {
  success: ["operational", "active", "success", "completed", "connected", "running", "confirmed", "accepted", "resolved", "complete", "operationally_complete"],
  warning: ["degraded", "pending", "warning", "unreviewed", "conflicted", "conflicting", "unresolved", "needs_review", "inferred", "medium", "required", "open", "exception", "incomplete", "exception_accepted"],
  danger: ["outage", "unavailable", "inactive", "failed", "error", "stale", "rejected", "retracted", "critical", "high", "critical_gaps"],
  info: ["maintenance", "observed", "declared", "intended", "current_from_source", "low", "conditional", "recommended"],
  neutral: ["planned", "deprecated", "deleted", "draft", "unknown", "superseded", "archived", "historical", "deferred", "not_evaluated", "cancelled", "retired"],
};
export const STATUS_REGISTRY = Object.freeze(Object.fromEntries(Object.entries(groups).flatMap(([tone, states]) => states.map(value => [value, Object.freeze({ value, label: value.replaceAll("_", " ").replace(/^./, letter => letter.toUpperCase()), tone })]))));
export function resolveStatus(state) {
  const value = typeof state === "string" ? state.trim().toLowerCase().replace(/[ -]+/g, "_") : "unknown";
  return (Object.hasOwn(STATUS_REGISTRY, value) ? STATUS_REGISTRY[value] : null) || { value: "unknown", label: typeof state === "string" && state.trim() ? state.trim() : "Unknown", tone: "neutral" };
}
