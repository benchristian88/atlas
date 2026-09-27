import { dependencyGroupLabel } from "./dependency-semantics.mjs";

export const ANALYSIS_STATE_LABELS = {
  unavailable: "Unavailable",
  degraded: "Degraded",
  unknown: "Unknown",
  unaffected: "Unaffected by this scenario",
};

export const ANALYSIS_CLASSIFICATION_LABELS = {
  direct: "Direct consequence",
  downstream: "Downstream consequence",
};

export function previewUnavailable(apiRequest, focusType, focusId) {
  return apiRequest("/dependency-analysis", {
    method: "POST",
    body: JSON.stringify({ focus_type: focusType, focus_id: focusId, state: "unavailable" }),
  });
}

// Wording only: the engine's per-requirement consequence remains authoritative.
// Never describe a shielded requirement as proof that the whole Service is healthy.
export function explainDependencyReason(serviceName, reason) {
  const members = reason.members || [];
  const unavailable = members.filter(member => member.state === "unavailable").map(member => member.entity.name);
  const available = members.filter(member => member.state === "unaffected").map(member => member.entity.name);
  const requirement = reason.dependency_group_name ? dependencyGroupLabel(reason, serviceName) : "this dependency requirement";
  if (reason.satisfaction === "satisfied") return `${available.join(", ") || "An alternative provider"} can still satisfy ${requirement} in this scenario. This requirement does not affect ${serviceName}.`;
  if (reason.code === "ungrouped_consequence_unknown") return `${serviceName} depends on ${members.map(member => member.entity.name).join(", ")}, but the effect of losing this dependency has not been classified.`;
  if (reason.satisfaction !== "unsatisfied") return `Atlas cannot determine whether ${requirement} can still be met for ${serviceName} from the available dependency knowledge.`;
  const cause = members.length === 1
    ? `${unavailable[0] || members[0].entity.name} is unavailable (${reason.dependency_requirement || "recorded"} dependency)`
    : reason.dependency_strategy === "any"
      ? `none of the providers can satisfy ${requirement}`
      : `${unavailable.join(", ")} ${unavailable.length === 1 ? "is" : "are"} unavailable and ${requirement} needs all its providers`;
  if (reason.consequence === "unknown") return `${cause}. The consequence for ${serviceName} is unknown.`;
  return `${serviceName} becomes ${ANALYSIS_STATE_LABELS[reason.consequence]?.toLowerCase() || "unknown"} because ${cause}, according to the recorded dependency impact.`;
}
