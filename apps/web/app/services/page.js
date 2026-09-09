"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { StatusBadge } from "../../components/status-badge";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";
import { formatDuration } from "../../lib/duration.mjs";
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
  const [searchDraft, setSearchDraft] = useState(filters.search);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const canView = hasPermissionInContext("services.view", workspace.customerId, workspace.siteId);
  const canCreate = hasPermissionInContext("services.create", workspace.customerId, workspace.siteId);

  useEffect(() => setSearchDraft(filters.search), [filters.search]);
  const load = useCallback(async () => {
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
      setServices(rows);
      setSummary(counts);
      setTypes(serviceTypes);
      setLevels(criticality);
      setBusinessFunctions(functions);
    } catch (requestError) {
      setError(requestError.message || "Atlas could not load Services.");
    } finally {
      setLoading(false);
    }
  }, [canView, filterKey, workspace.reloadKey]);

  useEffect(() => { load(); }, [load]);
  if (!canView) return <AccessDenied />;
  const update = (patch) => router.push(serviceListFiltersHref({ ...filters, ...patch }));

  return <>
    <div className="page-heading-row">
      <PageHeader eyebrow="Knowledge" title="Services" description="Operational capabilities, their dependencies, ownership, recovery targets, and knowledge health." />
      {canCreate && <Link className="button button-primary" href="/services/new">Add Service</Link>}
    </div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {summary && <section className="summary-grid compact-summary-grid" aria-label="Service summary">
      <button className="asset-type-filter selector-control-text" onClick={() => router.push("/services")} type="button"><span>All Services</span><strong>{summary.total}</strong></button>
      <button className="asset-type-filter selector-control-text" onClick={() => update({ criticalityLevelId: levels.find((item) => item.key === "critical")?.id || "" })} type="button"><span>Critical</span><strong>{summary.critical}</strong></button>
      <button className="asset-type-filter selector-control-text" onClick={() => update({ attention: "missing_owner" })} type="button"><span>Missing owner</span><strong>{summary.missing_owner}</strong></button>
      <button className="asset-type-filter selector-control-text" onClick={() => update({ attention: "missing_dependencies" })} type="button"><span>Missing dependencies</span><strong>{summary.missing_dependencies}</strong></button>
      <button className="asset-type-filter selector-control-text" onClick={() => update({ attention: "missing_recovery_targets" })} type="button"><span>Missing recovery targets</span><strong>{summary.missing_recovery_targets}</strong></button>
      <button className="asset-type-filter selector-control-text" onClick={() => update({ attention: "incomplete" })} type="button"><span>Incomplete</span><strong>{summary.incomplete}</strong></button>
    </section>}
    <section className="asset-filter-panel">
      <form className="asset-list-toolbar" onSubmit={(event) => { event.preventDefault(); update({ search: searchDraft.trim() }); }}>
        <label className="field"><span>Search</span><input placeholder="Name, purpose, owner" value={searchDraft} onChange={(event) => setSearchDraft(event.target.value)} /></label>
        <label className="field"><span>Service type</span><select value={filters.serviceTypeId} onChange={(event) => update({ serviceTypeId: event.target.value })}><option value="">All types</option>{types.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="field"><span>Criticality</span><select value={filters.criticalityLevelId} onChange={(event) => update({ criticalityLevelId: event.target.value })}><option value="">All levels</option>{levels.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="field"><span>Business Function</span><select value={filters.businessFunctionId} onChange={(event) => update({ businessFunctionId: event.target.value })}><option value="">All Business Functions</option>{businessFunctions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="field"><span>Lifecycle</span><select value={filters.lifecycleStatus} onChange={(event) => update({ lifecycleStatus: event.target.value })}><option value="">All lifecycle states</option>{LIFECYCLE_STATES.map((value) => <option key={value} value={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}</select></label>
        <label className="field"><span>Operational status</span><select value={filters.operationalStatus} onChange={(event) => update({ operationalStatus: event.target.value })}><option value="">All operational states</option>{OPERATIONAL_STATES.map((value) => <option key={value} value={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}</select></label>
        {hasPermission("knowledge_gaps.view") && <label className="field"><span>Completeness</span><select value={filters.completeness} onChange={(event) => update({ completeness: event.target.value })}><option value="">All states</option><option value="critical_gaps">Critical gaps</option><option value="incomplete">Incomplete</option><option value="operationally_complete">Operationally complete</option><option value="complete">Complete</option><option value="not_evaluated">Not evaluated</option></select></label>}
        <label className="field checkbox-field"><span>Archived</span><input checked={filters.archived} type="checkbox" onChange={(event) => update({ archived: event.target.checked })} /></label>
        <button className="button button-secondary" type="submit">Apply search</button>
        <button className="text-button" onClick={() => router.push("/services")} type="button">Clear</button>
      </form>
    </section>
    <section className="table-card">
      <div className="table-meta"><span>{loading ? "Loading Services…" : `${services.length} Service${services.length === 1 ? "" : "s"}`}</span><button className="text-button" disabled={loading} onClick={load} type="button">Refresh</button></div>
      <div className="table-scroll"><table><thead><tr><th>Service</th><th>Type</th><th>Criticality</th><th>Owner</th><th>Status</th><th>Dependencies</th><th>Recovery</th><th>Completeness</th></tr></thead><tbody>
        {!loading && services.length === 0 && <tr><td className="empty-state" colSpan="8">No Services match the current filters. {canCreate && <Link href="/services/new">Create the first Service.</Link>}</td></tr>}
        {services.map((service) => <tr key={service.id}>
          <td><div className="table-cell-identity"><Link className="primary-cell" href={`/services/${service.id}`}>{service.name}</Link><small className="secondary-text">{service.purpose || "Purpose not documented"}</small></div></td>
          <td>{service.service_type_name || "Unavailable"}</td>
          <td><StatusBadge status={service.criticality_name || "Unavailable"} /></td>
          <td>{service.owner_name || "—"}</td>
          <td><StatusBadge status={service.lifecycle_status} /><small className="secondary-text">{service.operational_status}</small></td>
          <td>{service.asset_dependency_count} assets · {service.service_dependency_count} Services<small className="secondary-text">{service.business_function_count} functions</small></td>
          <td>RTO {formatDuration(service.rto_minutes)}<small className="secondary-text">RPO {formatDuration(service.rpo_minutes)}</small></td>
          <td><StatusBadge status={service.completeness_status.replaceAll("_", " ")} />{service.open_gap_count > 0 && <small className="secondary-text">{service.open_gap_count} open</small>}</td>
        </tr>)}
      </tbody></table></div>
    </section>
  </>;
}
