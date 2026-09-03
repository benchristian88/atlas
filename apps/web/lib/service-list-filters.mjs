export function parseServiceListFilters(searchParams) {
  return {
    search: searchParams.get("search") || "",
    serviceTypeId: searchParams.get("service_type_id") || "",
    criticalityLevelId: searchParams.get("criticality_level_id") || "",
    businessFunctionId: searchParams.get("business_function_id") || "",
    lifecycleStatus: searchParams.get("lifecycle_status") || "",
    operationalStatus: searchParams.get("operational_status") || "",
    completeness: searchParams.get("completeness") || "",
    attention: searchParams.get("attention") || "",
    archived: searchParams.get("archived") === "true",
  };
}

export function serviceListFiltersHref(filters) {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.serviceTypeId) params.set("service_type_id", filters.serviceTypeId);
  if (filters.criticalityLevelId) params.set("criticality_level_id", filters.criticalityLevelId);
  if (filters.businessFunctionId) params.set("business_function_id", filters.businessFunctionId);
  if (filters.lifecycleStatus) params.set("lifecycle_status", filters.lifecycleStatus);
  if (filters.operationalStatus) params.set("operational_status", filters.operationalStatus);
  if (filters.completeness) params.set("completeness", filters.completeness);
  if (filters.attention) params.set("attention", filters.attention);
  if (filters.archived) params.set("archived", "true");
  const query = params.toString();
  return query ? `/services?${query}` : "/services";
}
