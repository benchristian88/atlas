"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { EntityCatalogue, ServiceCatalogueRow } from "../../components/entity-catalogue";
import { CatalogueFilters, useCatalogueSearch } from "../../components/catalogue-filters";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";
import { parseServiceListFilters, serviceListFiltersHref } from "../../lib/service-list-filters.mjs";

const LIFECYCLE_STATES = ["planned", "active", "retired"];
const OPERATIONAL_STATES = ["unknown", "operational", "degraded", "outage", "maintenance"];

export default function ServicesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const filters = useMemo(() => parseServiceListFilters(searchParams), [searchParams]);
  const filterKey = serviceListFiltersHref(filters);
  const { hasPermission, hasPermissionInContext } = useAuth();
  const workspace = useWorkspaceContext();
  const [services, setServices] = useState([]);
  const [summary, setSummary] = useState(null);
  const [types, setTypes] = useState([]);
  const [levels, setLevels] = useState([]);
  const [businessFunctions, setBusinessFunctions] = useState([]);
  const loadVersion = useRef(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const canView = hasPermissionInContext("services.view", workspace.customerId, workspace.siteId);
  const canCreate = hasPermissionInContext("services.create", workspace.customerId, workspace.siteId);

  const search = useCatalogueSearch(filters.search, (value) => router.replace(serviceListFiltersHref({ ...filters, search: value }), { scroll: false }), filterKey);
  const load = useCallback(async () => {
    const version = ++loadVersion.current;
    if (!canView) return;
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (filters.search) params.set("search", filters.search);
      if (filters.serviceTypeId) params.set("service_type_id", filters.serviceTypeId);
      if (filters.criticalityLevelId) params.set("criticality_level_id", filters.criticalityLevelId);
      if (filters.businessFunctionId) params.set("business_function_id", filters.businessFunctionId);
      if (filters.lifecycleStatus) params.set("lifecycle_status", filters.lifecycleStatus);
      if (filters.operationalStatus) params.set("operational_status", filters.operationalStatus);
      if (filters.completeness) params.set("completeness_status", filters.completeness);
      if (filters.attention) params.set("attention", filters.attention);
      if (filters.archived) params.set("archived", "true");
      const [rows, counts, serviceTypes, criticality, functions] = await Promise.all([
        apiRequest(`/services?${params}`),
        apiRequest("/services/summary"),
        apiRequest("/service-types"),
        apiRequest("/criticality-levels"),
        apiRequest("/business-functions?active_only=true"),
      ]);
      if (version !== loadVersion.current) return;
      setServices(rows);
      setSummary(counts);
      setTypes(serviceTypes);
      setLevels(criticality);
      setBusinessFunctions(functions);
    } catch (requestError) {
      if (version !== loadVersion.current) return;
      setError(requestError.message || "Atlas could not load Services.");
    } finally {
      if (version === loadVersion.current) setLoading(false);
    }
  }, [canView, filterKey, workspace.reloadKey]);

  useEffect(() => { load(); return () => { loadVersion.current += 1; }; }, [load]);
  useEffect(() => { setServices([]); setSummary(null); }, [workspace.reloadKey]);
  if (!canView) return <AccessDenied />;
  const update = (patch) => { search.cancel(); router.push(serviceListFiltersHref({ ...filters, search: search.draft.trim(), ...patch }), { scroll: false }); };
  const clear = () => { search.reset(); router.push("/services", { scroll: false }); };
  const activeCount = Object.entries(filters).filter(([key, value]) => key !== "search" && Boolean(value)).length;

  return <>
    <div className="page-heading-row">
      <PageHeader eyebrow="Knowledge" title="Services" description="Browse operational capabilities and the infrastructure and business functions they connect." />
      {canCreate && <Link className="button button-primary" href="/services/new">Add Service</Link>}
    </div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <CatalogueFilters label="Search services" search={search} activeCount={activeCount} onClear={clear} primary={
      <label className="field"><span className="sr-only">Service type</span><select value={filters.serviceTypeId} onChange={(event) => update({ serviceTypeId: event.target.value })}><option value="">All types</option>{types.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    }>
    {summary && <section className="catalogue-quick-filters" aria-label="Service summary">
      <button className="catalogue-quick-filter" aria-pressed={activeCount === 0 && !filters.search} onClick={clear} type="button"><span>All</span><strong>{summary.total}</strong></button>
      <button className="catalogue-quick-filter" aria-pressed={Boolean(filters.criticalityLevelId) && filters.criticalityLevelId === levels.find((item) => item.key === "critical")?.id} onClick={() => update({ criticalityLevelId: levels.find((item) => item.key === "critical")?.id || "" })} type="button"><span>Critical</span><strong>{summary.critical}</strong></button>
      <button className="catalogue-quick-filter" aria-pressed={filters.attention === "missing_owner"} onClick={() => update({ attention: "missing_owner" })} type="button"><span>Missing owner</span><strong>{summary.missing_owner}</strong></button>
      <button className="catalogue-quick-filter" aria-pressed={filters.attention === "missing_dependencies"} onClick={() => update({ attention: "missing_dependencies" })} type="button"><span>Missing dependencies</span><strong>{summary.missing_dependencies}</strong></button>
      <button className="catalogue-quick-filter" aria-pressed={filters.attention === "missing_recovery_targets"} onClick={() => update({ attention: "missing_recovery_targets" })} type="button"><span>Missing recovery</span><strong>{summary.missing_recovery_targets}</strong></button>
      <button className="catalogue-quick-filter" aria-pressed={filters.attention === "incomplete"} onClick={() => update({ attention: "incomplete" })} type="button"><span>Incomplete</span><strong>{summary.incomplete}</strong></button>
    </section>}
        <div className="catalogue-advanced-grid">
        <label className="field"><span>Criticality</span><select value={filters.criticalityLevelId} onChange={(event) => update({ criticalityLevelId: event.target.value })}><option value="">All levels</option>{levels.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="field"><span>Business Function</span><select value={filters.businessFunctionId} onChange={(event) => update({ businessFunctionId: event.target.value })}><option value="">All Business Functions</option>{businessFunctions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="field"><span>Lifecycle</span><select value={filters.lifecycleStatus} onChange={(event) => update({ lifecycleStatus: event.target.value })}><option value="">All lifecycle states</option>{LIFECYCLE_STATES.map((value) => <option key={value} value={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}</select></label>
        <label className="field"><span>Operational status</span><select value={filters.operationalStatus} onChange={(event) => update({ operationalStatus: event.target.value })}><option value="">All operational states</option>{OPERATIONAL_STATES.map((value) => <option key={value} value={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}</select></label>
        {hasPermission("knowledge_gaps.view") && <label className="field"><span>Completeness</span><select value={filters.completeness} onChange={(event) => update({ completeness: event.target.value })}><option value="">All states</option><option value="critical_gaps">Critical gaps</option><option value="incomplete">Incomplete</option><option value="operationally_complete">Operationally complete</option><option value="complete">Complete</option><option value="not_evaluated">Not evaluated</option></select></label>}
        <label className="field checkbox-field"><span>Archived only</span><input checked={filters.archived} type="checkbox" onChange={(event) => update({ archived: event.target.checked })} /></label>
        </div>
    </CatalogueFilters>
    <EntityCatalogue label="Services" count={services.length} loading={loading} error={error} onRefresh={load} empty={<>No Services match the current filters. {canCreate && <Link href="/services/new">Create the first Service.</Link>}</>}>
      {services.map((service) => <ServiceCatalogueRow key={service.id} service={service} />)}
    </EntityCatalogue>
  </>;
}
