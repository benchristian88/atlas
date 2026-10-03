export const ASSET_COMPLETENESS_FILTERS = [
  "has_critical_gaps",
  "has_open_knowledge_gaps",
  "critical_gaps",
  "incomplete",
  "operationally_complete",
  "complete",
  "exception_accepted",
  "not_evaluated",
];

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function parseAssetListFilters(searchParams, pageSize = 30) {
  const rawOffset = Number.parseInt(searchParams.get("offset") || "0", 10);
  const offset = Number.isFinite(rawOffset) && rawOffset >= 0
    ? Math.floor(rawOffset / pageSize) * pageSize
    : 0;
  const typeId = searchParams.get("asset_type_id") || "";
  const categoryId = searchParams.get("category_id") || "";
  const completeness = searchParams.get("completeness") || "";
  return {
    categoryId: UUID_PATTERN.test(categoryId) ? categoryId : "",
    assetTypeId: UUID_PATTERN.test(typeId) ? typeId : "",
    completeness: ASSET_COMPLETENESS_FILTERS.includes(completeness) ? completeness : "",
    search: (searchParams.get("search") || "").trim().slice(0, 255),
    offset,
  };
}

export function assetListFiltersHref(filters) {
  const params = new URLSearchParams();
  if (filters.categoryId) params.set("category_id", filters.categoryId);
  if (filters.assetTypeId) params.set("asset_type_id", filters.assetTypeId);
  if (filters.completeness) params.set("completeness", filters.completeness);
  if (filters.search) params.set("search", filters.search.trim());
  if (filters.offset > 0) params.set("offset", String(filters.offset));
  const query = params.toString();
  return query ? `/assets?${query}` : "/assets";
}

export function orderedAssetTypeCounts(summary) {
  return [...(summary?.by_asset_type || [])]
    .filter((item) => item.count > 0)
    .sort((left, right) => right.count - left.count || left.asset_type_name.localeCompare(right.asset_type_name));
}
