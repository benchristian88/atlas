export const CHANGE_TYPES = [
  "entity_discovered",
  "entity_accepted",
  "fact_changed",
  "relationship_added",
  "relationship_removed",
  "entity_no_longer_observed",
  "entity_reobserved",
  "lifecycle_changed",
  "exception_recorded",
  "assertion_retracted",
  "knowledge_gap_opened",
  "knowledge_gap_resolved",
  "service_created",
  "service_updated",
  "service_archived",
  "service_dependency_added",
  "service_dependency_removed",
  "service_business_function_added",
  "service_business_function_removed",
  "service_criticality_changed",
  "service_recovery_target_changed",
  "service_owner_changed",
  "service_completeness_changed",
];

export const CHANGE_ENTITY_TYPES = ["asset", "asset_relationship", "service", "business_function"];
export const CHANGE_PERIODS = ["7", "30", "90", ""];

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function member(value, allowed, fallback = "") {
  return allowed.includes(value) ? value : fallback;
}

export function parseChangeFilters(searchParams, pageSize = 30) {
  const rawOffset = Number.parseInt(searchParams.get("offset") || "0", 10);
  const offset = Number.isFinite(rawOffset) && rawOffset >= 0
    ? Math.floor(rawOffset / pageSize) * pageSize
    : 0;
  const source = searchParams.get("source") || "";
  return {
    period: member(searchParams.get("period") ?? "30", CHANGE_PERIODS, "30"),
    changeType: member(searchParams.get("change_type") || "", CHANGE_TYPES),
    entityType: member(searchParams.get("entity_type") || "", CHANGE_ENTITY_TYPES),
    source: UUID_PATTERN.test(source) ? source : "",
    attentionOnly: searchParams.get("attention") === "true",
    search: (searchParams.get("search") || "").trim().slice(0, 255),
    offset,
  };
}

export function changeFiltersHref(filters) {
  const params = new URLSearchParams();
  if (filters.period !== "30") params.set("period", filters.period);
  if (filters.changeType) params.set("change_type", filters.changeType);
  if (filters.entityType) params.set("entity_type", filters.entityType);
  if (filters.source) params.set("source", filters.source);
  if (filters.attentionOnly) params.set("attention", "true");
  if (filters.search) params.set("search", filters.search.trim());
  if (filters.offset > 0) params.set("offset", String(filters.offset));
  const query = params.toString();
  return query ? `/changes?${query}` : "/changes";
}
