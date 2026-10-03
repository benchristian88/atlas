"use client";

import { Button, IconButton } from "../../components/button";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AccessDenied } from "../../components/access-denied";
import { AssetForm } from "../../components/asset-form";
import { AssetCatalogueRow, EntityCatalogue } from "../../components/entity-catalogue";
import { CatalogueFilters, useCatalogueSearch } from "../../components/catalogue-filters";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
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
  const [categories, setCategories] = useState([]);
  const [assetTypes, setAssetTypes] = useState([]);
  const [customFields, setCustomFields] = useState([]);
  const search = useCatalogueSearch(filters.search, value => router.replace(assetListFiltersHref({ ...filters, search: value, offset: 0 }), { scroll: false }), filterKey);
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


  const load = useCallback(async () => {
    if (!canView) return;
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError("");
    try {
      const [assetSummary, typeRecords, fieldRecords, categoryRecords] = await Promise.all([
        apiRequest("/assets/summary"),
        hasPermission("asset_types.view") ? apiRequest("/asset-types") : Promise.resolve([]),
        hasPermission("custom_fields.view") ? apiRequest("/custom-fields?active_only=true") : Promise.resolve([]),
        hasPermission("asset_types.view") ? apiRequest("/asset-categories") : Promise.resolve([]),
      ]);
      if (requestId.current !== currentRequest) return;
      const validType = assetSummary.by_asset_type.find((item) => item.asset_type_id === filters.assetTypeId);
      const parameters = new URLSearchParams({ limit: String(PAGE_SIZE + 1), offset: String(filters.offset) });
      if (validType) parameters.set("asset_type_id", validType.asset_type_id);
      if (filters.categoryId) parameters.set("category_id", filters.categoryId);
      if (filters.search) parameters.set("search", filters.search);
      if (filters.completeness === "has_critical_gaps") parameters.set("has_critical_gaps", "true");
      else if (filters.completeness === "has_open_knowledge_gaps") parameters.set("has_open_knowledge_gaps", "true");
      else if (filters.completeness === "not_evaluated") parameters.set("not_evaluated", "true");
      else if (filters.completeness) parameters.set("completeness_status", filters.completeness);
      const assetRecords = await apiRequest(`/assets?${parameters}`);
      if (requestId.current !== currentRequest) return;
      setSummary(assetSummary);
      setAssetTypes(typeRecords);
      setCategories(categoryRecords);
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
  }, [canView, filterKey, filters.assetTypeId, filters.categoryId, filters.completeness, filters.offset, filters.search, hasPermission, workspace.reloadKey]);

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
  const activeFilterCount = [selectedType, filters.categoryId, filters.completeness].filter(Boolean).length;

  if (!canView) return <AccessDenied />;

  function updateFilters(patch) {
    search.cancel();
    router.push(assetListFiltersHref({ ...filters, search: search.draft.trim(), ...patch, offset: patch.offset ?? 0 }));
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


  return <>
    <PageHeader eyebrow="Inventory" title="Assets" description="Create and maintain infrastructure within the active customer and site context." actions={<>{canCreate && <Button variant="primary" disabled={!hasActiveAssetType} onClick={() => setShowCreate(true)} type="button">Add asset</Button>}</>} />
    {canCreate && !hasActiveAssetType && ready && !loading && <div className="warning-banner">No active asset types are available. Ask an administrator to activate one before creating assets.</div>}
    {ready && error && <div className="error-banner" role="alert">{error}</div>}
    {success && <div className="success-banner" role="status">{success}</div>}
    {showCreate && <section className="form-card"><div className="form-card-header"><h2>Add asset</h2><IconButton onClick={() => setShowCreate(false)} type="button" label="Close form" icon="close" /></div><AssetForm assetTypes={assetTypes} context={{ customerId: workspace.customerId, siteId: workspace.siteId }} customFieldDefinitions={customFields} customers={creatableCustomers} onCancel={() => setShowCreate(false)} onSubmit={createAsset} saving={saving} sites={creatableSites} submitLabel="Create asset" /></section>}

    <CatalogueFilters label="Search assets" search={search} activeCount={activeFilterCount} onClear={() => { search.reset(); router.push("/assets"); }} quickFilters={
      <div className="asset-type-filters" aria-label="Filter by asset type"><button aria-pressed={!selectedType} className={`asset-type-filter selector-control-text${!selectedType ? " active" : ""}`} onClick={() => updateFilters({ assetTypeId: "" })} type="button"><span>All assets</span><strong>{summary.total}</strong></button>{directTypeCounts.map((item) => <button aria-pressed={selectedType?.asset_type_id === item.asset_type_id} className={`asset-type-filter selector-control-text${selectedType?.asset_type_id === item.asset_type_id ? " active" : ""}`} key={item.asset_type_id} onClick={() => updateFilters({ assetTypeId: item.asset_type_id })} type="button"><span>{item.asset_type_name}</span><strong>{item.count}</strong></button>)}{additionalTypeCounts.length > 0 && <label className={`asset-type-more${selectedAdditionalType ? " active" : ""}`}><span className="sr-only">More asset types</span><select aria-label="More asset types" className="selector-control-text" onChange={(event) => updateFilters({ assetTypeId: event.target.value })} value={selectedAdditionalType?.asset_type_id || ""}><option value="">More…</option>{additionalTypeCounts.map((item) => <option key={item.asset_type_id} value={item.asset_type_id}>{item.asset_type_name} ({item.count})</option>)}</select></label>}</div>
    } primary={<label className="field"><span className="sr-only">Asset type</span><select value={selectedType?.asset_type_id || ""} onChange={event => updateFilters({ assetTypeId: event.target.value })}><option value="">All types</option>{typeCounts.map(item => <option key={item.asset_type_id} value={item.asset_type_id}>{item.asset_type_name}</option>)}</select></label>}>
      <div className="catalogue-advanced-grid"><label className="field"><span>Asset Category</span><select aria-label="Asset Category" value={filters.categoryId} onChange={(event) => updateFilters({ categoryId: event.target.value })}><option value="">All categories</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}{category.active ? "" : " (inactive)"}</option>)}</select></label>{hasPermission("knowledge_gaps.view") && <label className="field"><span>Completeness</span><select onChange={(event) => updateFilters({ completeness: event.target.value })} value={filters.completeness}><option value="">All completeness states</option><option value="has_critical_gaps">Has critical gaps</option><option value="has_open_knowledge_gaps">Has open gaps</option><option value="critical_gaps">Critical gaps status</option><option value="incomplete">Incomplete</option><option value="operationally_complete">Operationally complete</option><option value="complete">Complete</option><option value="exception_accepted">Exception accepted</option><option value="not_evaluated">Not evaluated</option></select></label>}</div>
    </CatalogueFilters>
    <EntityCatalogue label="Assets" count={assets.length} loading={loading} error={ready ? error : ""} onRefresh={load} empty="No assets match the current filters.">
      {assets.map(asset => <AssetCatalogueRow key={asset.id} asset={asset} assetType={assetTypesByKey[asset.asset_type]} category={categories.find(category => category.id === assetTypesByKey[asset.asset_type]?.category_id)} customer={workspace.customers.find(item => item.id === asset.customer_id)} site={workspace.sites.find(item => item.id === asset.site_id)} canViewCompleteness={hasPermission("knowledge_gaps.view")} actions={<>
        {canEdit && hasPermissionForObject("assets.edit", asset.customer_id, asset.site_id) && <Link className="text-button" href={`/assets/${asset.id}/edit`}>Edit</Link>}
        {canDelete && hasPermissionForObject("assets.delete", asset.customer_id, asset.site_id) && <button className="text-button text-danger" onClick={() => removeAsset(asset)} type="button">Delete</button>}
      </>} />)}
    </EntityCatalogue>
    {ready && !loading && (filters.offset > 0 || hasMore) && <div className="pagination"><Button variant="secondary" disabled={filters.offset === 0} onClick={() => updateFilters({ offset: Math.max(0, filters.offset - PAGE_SIZE) })} type="button">Previous</Button><span>Page {Math.floor(filters.offset / PAGE_SIZE) + 1}</span><Button variant="secondary" disabled={!hasMore} onClick={() => updateFilters({ offset: filters.offset + PAGE_SIZE })} type="button">Next</Button></div>}
  </>;
}
