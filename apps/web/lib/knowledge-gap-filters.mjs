export const KNOWLEDGE_GAP_SEVERITIES = ["critical", "high", "medium", "low"];
export const KNOWLEDGE_GAP_REQUIREMENT_LEVELS = ["required", "conditional", "recommended"];
export const KNOWLEDGE_GAP_STATUSES = ["open", "deferred", "exception", "resolved", "superseded"];

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function member(value, allowed) {
  return allowed.includes(value) ? value : "";
}

function uuid(value) {
  return UUID_PATTERN.test(value || "") ? value : "";
}

export function parseKnowledgeGapFilters(searchParams, pageSize = 25) {
  const rawAge = searchParams.get("minimum_age_days") || "";
  const parsedAge = Number.parseInt(rawAge, 10);
  const minimumAgeDays = /^\d+$/.test(rawAge) && parsedAge >= 0 && parsedAge <= 36500
    ? String(parsedAge)
    : "";
  const rawOffset = Number.parseInt(searchParams.get("offset") || "0", 10);
  const offset = Number.isFinite(rawOffset) && rawOffset >= 0
    ? Math.floor(rawOffset / pageSize) * pageSize
    : 0;

  return {
    assetTypeId: uuid(searchParams.get("asset_type_id")),
    requirementId: uuid(searchParams.get("requirement_id")),
    severity: member(searchParams.get("severity") || "", KNOWLEDGE_GAP_SEVERITIES),
    requirementLevel: member(searchParams.get("requirement_level") || "", KNOWLEDGE_GAP_REQUIREMENT_LEVELS),
    status: member(searchParams.get("status") || "", KNOWLEDGE_GAP_STATUSES),
    assignedUserId: uuid(searchParams.get("assigned_user_id")),
    minimumAgeDays,
    offset,
  };
}

export function knowledgeGapFiltersHref(filters) {
  const params = new URLSearchParams();
  if (filters.assetTypeId) params.set("asset_type_id", filters.assetTypeId);
  if (filters.requirementId) params.set("requirement_id", filters.requirementId);
  if (filters.severity) params.set("severity", filters.severity);
  if (filters.requirementLevel) params.set("requirement_level", filters.requirementLevel);
  if (filters.status) params.set("status", filters.status);
  if (filters.assignedUserId) params.set("assigned_user_id", filters.assignedUserId);
  if (filters.minimumAgeDays !== "") params.set("minimum_age_days", filters.minimumAgeDays);
  if (filters.offset > 0) params.set("offset", String(filters.offset));
  const query = params.toString();
  return query ? `/knowledge-gaps?${query}` : "/knowledge-gaps";
}
