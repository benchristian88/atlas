"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AccessDenied } from "../../components/access-denied";
import { AssetForm } from "../../components/asset-form";
import { AssetIcon } from "../../components/asset-icon";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { StatusBadge } from "../../components/status-badge";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";
import {
  assetListFiltersHref,
  orderedAssetTypeCounts,
  parseAssetListFilters,
} from "../../lib/asset-list-filters.mjs";

const PAGE_SIZE = 30;

export default function AssetsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { hasPermission, hasPermissionForObject, hasPermissionInContext } = useAuth();
  const workspace = useWorkspaceContext();
  const filters = useMemo(() => parseAssetListFilters(searchParams, PAGE_SIZE), [searchParams]);
  const filterKey = assetListFiltersHref(filters);
  const [assets, setAssets] = useState([]);
  const [summary, setSummary] = useState({ total: 0, by_asset_type: [] });
  const [assetTypes, setAssetTypes] = useState([]);
  const [customFields, setCustomFields] = useState([]);
  const [searchDraft, setSearchDraft] = useState(filters.search);
  const [showCreate, setShowCreate] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [loadedKey, setLoadedKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const requestId = useRef(0);
  const canView = hasPermissionInContext("assets.view", workspace.customerId, workspace.siteId);
  const canCreate = hasPermissionInContext("assets.create", workspace.customerId, workspace.siteId);
  const canEdit = hasPermission("assets.edit");
  const canDelete = hasPermission("assets.delete");

  useEffect(() => { setSearchDraft(filters.search); }, [filters.search]);

  const load = useCallback(async () => {
    if (!canView) return;
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError("");
    try {
      const [assetSummary, typeRecords, fieldRecords] = await Promise.all([
        apiRequest("/assets/summary"),
        hasPermission("asset_types.view") ? apiRequest("/asset-types") : Promise.resolve([]),
        hasPermission("custom_fields.view") ? apiRequest("/custom-fields?active_only=true") : Promise.resolve([]),
      ]);
      if (requestId.current !== currentRequest) return;
      const validType = assetSummary.by_asset_type.find((item) => item.asset_type_id === filters.assetTypeId);
      const parameters = new URLSearchParams({ limit: String(PAGE_SIZE + 1), offset: String(filters.offset) });
      if (validType) parameters.set("asset_type_id", validType.asset_type_id);
      if (filters.search) parameters.set("search", filters.search);
      if (filters.completeness === "has_critical_gaps") parameters.set("has_critical_gaps", "true");
      else if (filters.completeness === "has_open_knowledge_gaps") parameters.set("has_open_knowledge_gaps", "true");
      else if (filters.completeness === "not_evaluated") parameters.set("not_evaluated", "true");
      else if (filters.completeness) parameters.set("completeness_status", filters.completeness);
      const assetRecords = await apiRequest(`/assets?${parameters}`);
      if (requestId.current !== currentRequest) return;
      setSummary(assetSummary);
      setAssetTypes(typeRecords);
      setCustomFields(fieldRecords);
      setAssets(assetRecords.slice(0, PAGE_SIZE));
      setHasMore(assetRecords.length > PAGE_SIZE);
      setLoadedKey(filterKey);
    } catch (requestError) {
      if (requestId.current !== currentRequest) return;
      setAssets([]);
      setHasMore(false);
      setLoadedKey(filterKey);
      setError(requestError.message || "Atlas could not load assets.");
    } finally {
      if (requestId.current === currentRequest) setLoading(false);
    }
  }, [canView, filterKey, filters.assetTypeId, filters.completeness, filters.offset, filters.search, hasPermission, workspace.reloadKey]);

  useEffect(() => {
    load();
    return () => { requestId.current += 1; };
  }, [load]);

  const assetTypesByKey = useMemo(() => Object.fromEntries(assetTypes.map((type) => [type.key, type])), [assetTypes]);
  const typeCounts = useMemo(() => orderedAssetTypeCounts(summary), [summary]);
  const directTypeCounts = typeCounts.slice(0, 10);
  const additionalTypeCounts = typeCounts.slice(10);
  const selectedType = typeCounts.find((item) => item.asset_type_id === filters.assetTypeId) || null;
  const selectedAdditionalType = additionalTypeCounts.find((item) => item.asset_type_id === selectedType?.asset_type_id) || null;
  const hasActiveAssetType = assetTypes.some((type) => type.active);
  const creatableSites = workspace.sites.filter((site) => hasPermissionForObject("assets.create", site.customer_id, site.id));
  const creatableCustomerIds = new Set(creatableSites.map((site) => site.customer_id));
  const creatableCustomers = workspace.customers.filter((customer) => creatableCustomerIds.has(customer.id));
  const ready = loadedKey === filterKey;
  const activeFilterCount = [selectedType, filters.completeness, filters.search].filter(Boolean).length;

  if (!canView) return <AccessDenied />;

  function updateFilters(patch) {
    router.push(assetListFiltersHref({ ...filters, ...patch, offset: patch.offset ?? 0 }));
  }

  async function createAsset(payload) {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const created = await apiRequest("/assets", { method: "POST", body: JSON.stringify(payload) });
      setShowCreate(false);
      setSuccess("Asset created. Reviewing knowledge completeness…");
      router.push(`/assets/${created.id}`);
    } catch (requestError) {
      setError(requestError.message || "Atlas could not create this asset.");
    } finally {
      setSaving(false);
    }
  }

  async function removeAsset(asset) {
    if (!window.confirm(`Delete “${asset.name}”? Relationships must be removed first and this action cannot be undone.`)) return;
    setError("");
    try {
      await apiRequest(`/assets/${asset.id}`, { method: "DELETE" });
      setSuccess("Asset deleted.");
      await load();
    } catch (requestError) {
      setError(requestError.message || "Atlas could not delete this asset.");
    }
  }

  const showActions = canEdit || canDelete;
  const columnCount = 6 + Number(hasPermission("knowledge_gaps.view")) + Number(showActions);

  return <>
    <div className="page-heading-row"><PageHeader eyebrow="Inventory" title="Assets" description="Create and maintain infrastructure within the active customer and site context." />{canCreate && <button className="button button-primary" disabled={!hasActiveAssetType} onClick={() => setShowCreate(true)} type="button">Add asset</button>}</div>
    {canCreate && !hasActiveAssetType && ready && !loading && <div className="warning-banner">No active asset types are available. Ask an administrator to activate one before creating assets.</div>}
    {ready && error && <div className="error-banner" role="alert">{error}</div>}
    {success && <div className="success-banner" role="status">{success}</div>}
    {showCreate && <section className="form-card"><div className="form-card-header"><h2>Add asset</h2><button className="icon-button" aria-label="Close form" onClick={() => setShowCreate(false)} type="button">×</button></div><AssetForm assetTypes={assetTypes} context={{ customerId: workspace.customerId, siteId: workspace.siteId }} customFieldDefinitions={customFields} customers={creatableCustomers} onCancel={() => setShowCreate(false)} onSubmit={createAsset} saving={saving} sites={creatableSites} submitLabel="Create asset" /></section>}

    <section className="asset-filter-panel" aria-label="Asset filters">
      <div className="asset-type-filters" aria-label="Filter by asset type"><button aria-pressed={!selectedType} className={`asset-type-filter selector-control-text${!selectedType ? " active" : ""}`} onClick={() => updateFilters({ assetTypeId: "" })} type="button"><span>All assets</span><strong>{summary.total}</strong></button>{directTypeCounts.map((item) => <button aria-pressed={selectedType?.asset_type_id === item.asset_type_id} className={`asset-type-filter selector-control-text${selectedType?.asset_type_id === item.asset_type_id ? " active" : ""}`} key={item.asset_type_id} onClick={() => updateFilters({ assetTypeId: item.asset_type_id })} type="button"><span>{item.asset_type_name}</span><strong>{item.count}</strong></button>)}{additionalTypeCounts.length > 0 && <label className={`asset-type-more${selectedAdditionalType ? " active" : ""}`}><span className="sr-only">More asset types</span><select aria-label="More asset types" className="selector-control-text" onChange={(event) => updateFilters({ assetTypeId: event.target.value })} value={selectedAdditionalType?.asset_type_id || ""}><option value="">More…</option>{additionalTypeCounts.map((item) => <option key={item.asset_type_id} value={item.asset_type_id}>{item.asset_type_name} ({item.count})</option>)}</select></label>}</div>
      <form className="asset-list-toolbar" onSubmit={(event) => { event.preventDefault(); updateFilters({ search: searchDraft.trim() }); }}><label className="field"><span>Search assets</span><input onChange={(event) => setSearchDraft(event.target.value)} placeholder="Name, hostname, IP, vendor or model" value={searchDraft} /></label>{hasPermission("knowledge_gaps.view") && <label className="field"><span>Completeness</span><select onChange={(event) => updateFilters({ completeness: event.target.value })} value={filters.completeness}><option value="">All completeness states</option><option value="has_critical_gaps">Has critical gaps</option><option value="has_open_knowledge_gaps">Has open gaps</option><option value="critical_gaps">Critical gaps status</option><option value="incomplete">Incomplete</option><option value="operationally_complete">Operationally complete</option><option value="complete">Complete</option><option value="exception_accepted">Exception accepted</option><option value="not_evaluated">Not evaluated</option></select></label>}<button className="button button-secondary" type="submit">Apply search</button><button className="text-button" disabled={activeFilterCount === 0} onClick={() => router.push("/assets")} type="button">Clear filters</button></form>
    </section>

    <section className="table-card" aria-label="Assets list">
      <div className="table-meta"><span>{!ready || loading ? "Loading…" : `${assets.length} shown${selectedType ? ` · ${selectedType.asset_type_name}` : ""}`}</span><button className="text-button" disabled={loading} onClick={load} type="button">Refresh</button></div>
      <div className="table-scroll"><table><thead><tr><th>Asset</th><th>Type</th><th>Customer</th><th>Site</th><th>Hostname / IP</th><th>Status</th>{hasPermission("knowledge_gaps.view") && <th>Completeness</th>}{showActions && <th>Actions</th>}</tr></thead><tbody>
        {ready && !loading && assets.length === 0 && <tr><td className="empty-state" colSpan={columnCount}>No assets match the current filters.</td></tr>}
        {ready && assets.map((asset) => { const type = assetTypesByKey[asset.asset_type]; const customer = workspace.customers.find((item) => item.id === asset.customer_id); const site = workspace.sites.find((item) => item.id === asset.site_id); const canEditAsset = canEdit && hasPermissionForObject("assets.edit", asset.customer_id, asset.site_id); const canDeleteAsset = canDelete && hasPermissionForObject("assets.delete", asset.customer_id, asset.site_id); return <tr key={asset.id}><td><Link className="asset-table-identity" href={`/assets/${asset.id}`}><AssetIcon asset={asset} assetType={type} size={38} /><span><strong>{asset.name}</strong><small>{asset.vendor || asset.model ? [asset.vendor, asset.model].filter(Boolean).join(" ") : "View documentation"}</small></span></Link></td><td>{type?.name || asset.asset_type}</td><td>{customer?.name || "Unknown"}</td><td>{site?.name || "Unknown"}</td><td><span className="mono">{asset.ip_address || asset.hostname || "—"}</span></td><td><StatusBadge status={asset.status} /></td>{hasPermission("knowledge_gaps.view") && <td><StatusBadge status={asset.completeness_status.replaceAll("_", " ")} />{asset.open_knowledge_gap_count > 0 && <small className="secondary-text">{asset.open_knowledge_gap_count} open</small>}</td>}{showActions && <td><div className="row-actions">{canEditAsset && <Link className="text-button" href={`/assets/${asset.id}/edit`}>Edit</Link>}{canDeleteAsset && <button className="text-button text-danger" onClick={() => removeAsset(asset)} type="button">Delete</button>}</div></td>}</tr>; })}
      </tbody></table></div>
    </section>
    {ready && !loading && (filters.offset > 0 || hasMore) && <div className="pagination"><button className="button button-secondary" disabled={filters.offset === 0} onClick={() => updateFilters({ offset: Math.max(0, filters.offset - PAGE_SIZE) })} type="button">Previous</button><span>Page {Math.floor(filters.offset / PAGE_SIZE) + 1}</span><button className="button button-secondary" disabled={!hasMore} onClick={() => updateFilters({ offset: filters.offset + PAGE_SIZE })} type="button">Next</button></div>}
  </>;
}
