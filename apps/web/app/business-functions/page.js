"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { EntityCatalogue, BusinessFunctionCatalogueRow } from "../../components/entity-catalogue";
import { CatalogueFilters, useCatalogueSearch } from "../../components/catalogue-filters";
import { useWorkspaceContext } from "../../components/workspace-context";
import { recordContextOptions } from "../../lib/record-context.mjs";
import { apiRequest } from "../../lib/api";

const empty = { customer_id: "", site_id: "", name: "", description: "", owner_name: "", criticality_level_id: "", active: true };

export default function BusinessFunctionsPage() {
  const { hasPermissionInContext } = useAuth(); const workspace = useWorkspaceContext();
  const [rows, setRows] = useState([]); const [levels, setLevels] = useState([]); const [form, setForm] = useState(empty); const [open, setOpen] = useState(false); const [loading, setLoading] = useState(true); const [saving, setSaving] = useState(false); const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const searchControl = useCatalogueSearch(search, setSearch);
  const loadVersion = useRef(0);
  const [showArchived, setShowArchived] = useState(false);
  const canView = hasPermissionInContext("business_functions.view", workspace.customerId, workspace.siteId); const canManage = hasPermissionInContext("business_functions.manage", workspace.customerId, workspace.siteId);
  const load = useCallback(async () => { const version = ++loadVersion.current; if (!canView) return; setLoading(true); setError(""); try { const [items, criticality] = await Promise.all([apiRequest(`/business-functions?${new URLSearchParams({ active_only: String(!showArchived), search })}`), apiRequest("/criticality-levels")]); if (version !== loadVersion.current) return; setRows(items); setLevels(criticality); } catch (requestError) { if (version === loadVersion.current) setError(requestError.message); } finally { if (version === loadVersion.current) setLoading(false); } }, [canView, workspace.reloadKey, search, showArchived]);
  useEffect(() => { load(); return () => { loadVersion.current += 1; }; }, [load]);
  useEffect(() => { setRows([]); }, [workspace.reloadKey]);
  useEffect(() => setForm((current) => ({ ...current, customer_id: workspace.customerId || current.customer_id, site_id: workspace.siteId || current.site_id })), [workspace.customerId, workspace.siteId]);
  if (!canView) return <AccessDenied />;
  async function submit(event) { event.preventDefault(); setSaving(true); setError(""); try { await apiRequest("/business-functions", { ...recordContextOptions(form.customer_id, form.site_id), method: "POST", body: JSON.stringify({ ...form, site_id: form.site_id || null, description: form.description || null, owner_name: form.owner_name || null, criticality_level_id: form.criticality_level_id || null }) }); setForm({ ...empty, customer_id: workspace.customerId || "", site_id: workspace.siteId || "" }); setOpen(false); await load(); } catch (requestError) { setError(requestError.message); } finally { setSaving(false); } }
  const matchingSites = workspace.sites.filter((site) => site.customer_id === form.customer_id);
  return <><div className="page-heading-row"><PageHeader eyebrow="Knowledge" title="Business Functions" description="Lightweight capabilities supported by one or more operational Services." />{canManage && <button className="button button-primary" onClick={() => setOpen(true)} type="button">Add Business Function</button>}</div>{error && <div className="error-banner" role="alert">{error}</div>}{open && <section className="form-card"><div className="form-card-header"><h2>Add Business Function</h2><button className="icon-button" onClick={() => setOpen(false)} type="button">×</button></div><form className="resource-form" onSubmit={submit}><div className="form-grid"><label className="field"><span>Customer *</span><select required disabled={Boolean(workspace.customerId)} value={form.customer_id} onChange={(event) => setForm({ ...form, customer_id: event.target.value, site_id: "" })}><option value="">Choose customer</option>{workspace.customers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="field"><span>Site</span><select value={form.site_id} onChange={(event) => setForm({ ...form, site_id: event.target.value })}><option value="">Customer-wide</option>{matchingSites.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="field"><span>Name *</span><input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label><label className="field"><span>Owner</span><input value={form.owner_name} onChange={(event) => setForm({ ...form, owner_name: event.target.value })} /></label><label className="field"><span>Criticality</span><select value={form.criticality_level_id} onChange={(event) => setForm({ ...form, criticality_level_id: event.target.value })}><option value="">Not set</option>{levels.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="field field-wide"><span>Description</span><textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label></div><div className="form-actions"><button className="button button-secondary" onClick={() => setOpen(false)} type="button">Cancel</button><button className="button button-primary" disabled={saving} type="submit">{saving ? "Saving…" : "Create"}</button></div></form></section>}
    <CatalogueFilters label="Search business functions" search={searchControl} activeCount={Number(showArchived)} onClear={() => { searchControl.reset(); setSearch(""); setShowArchived(false); }}>
      <div className="catalogue-advanced-grid"><label className="field checkbox-field"><span>Include archived</span><input type="checkbox" checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} /></label></div>
    </CatalogueFilters>
    <EntityCatalogue label="Business Functions" count={rows.length} loading={loading} error={error} onRefresh={load} empty="No Business Functions match the current filters.">
      {rows.map((item) => <BusinessFunctionCatalogueRow key={item.id} item={item} />)}
    </EntityCatalogue>
  </>;
}
