"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useMemo, useState } from "react";
import { AccessDenied } from "../../../components/access-denied";
import { useAuth } from "../../../components/auth-context";
import { PageHeader } from "../../../components/page-header";
import { OperationalGraphView } from "../../../components/operational-graph-view";
import { StatusBadge } from "../../../components/status-badge";
import { apiRequest } from "../../../lib/api";

export default function BusinessFunctionDetailPage({ params }) {
  const { id } = use(params);
  const { hasPermission, hasPermissionForObject } = useAuth();
  const [item, setItem] = useState(null);
  const [links, setLinks] = useState([]);
  const [criticalityLevels, setCriticalityLevels] = useState([]);
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const canView = hasPermission("business_functions.view");

  const load = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    setError("");
    try {
      const [record, serviceLinks, graphData, levels] = await Promise.all([
        apiRequest(`/business-functions/${id}`),
        apiRequest(`/business-functions/${id}/services`),
        apiRequest(`/business-functions/${id}/graph`),
        apiRequest("/criticality-levels"),
      ]);
      setItem(record);
      setLinks(serviceLinks);
      setGraph(graphData);
      setCriticalityLevels(levels);
      setForm({ name: record.name, description: record.description || "", owner_name: record.owner_name || "", criticality_level_id: record.criticality_level_id || "", active: record.active });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, [canView, id]);

  useEffect(() => { load(); }, [load]);
  const affectedAssets = useMemo(() => graph.nodes.filter((node) => node.entity_type === "asset"), [graph.nodes]);

  if (!canView) return <AccessDenied />;
  if (loading && !item) return <div className="status-banner">Loading Business Function…</div>;
  if (!item) return <div className="error-banner">{error || "Business Function not found."}</div>;

  const canManage = hasPermissionForObject("business_functions.manage", item.customer_id, item.site_id);
  async function save(event) {
    event.preventDefault();
    setError("");
    try {
      await apiRequest(`/business-functions/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ ...form, description: form.description || null, owner_name: form.owner_name || null, criticality_level_id: form.criticality_level_id || null }),
      });
      setEditing(false);
      await load();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  return <>
    <div className="page-heading-row">
      <PageHeader eyebrow="Business Function" title={item.name} description={item.description || "A lightweight capability supported by Atlas Services."} />
      {canManage && <button className="button button-secondary" onClick={() => setEditing(!editing)} type="button">{editing ? "Cancel" : "Edit"}</button>}
    </div>
    {error && <div className="error-banner">{error}</div>}
    {editing && <section className="form-card">
      <form className="resource-form" onSubmit={save}>
        <div className="form-grid">
          <label className="field"><span>Name *</span><input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
          <label className="field"><span>Owner</span><input value={form.owner_name} onChange={(event) => setForm({ ...form, owner_name: event.target.value })} /></label>
          <label className="field"><span>Criticality</span><select value={form.criticality_level_id} onChange={(event) => setForm({ ...form, criticality_level_id: event.target.value })}><option value="">Not set</option>{criticalityLevels.filter((level) => level.active || level.id === item.criticality_level_id).map((level) => <option key={level.id} value={level.id}>{level.name}</option>)}</select></label>
          <label className="field checkbox-field"><span>Active</span><input checked={form.active} type="checkbox" onChange={(event) => setForm({ ...form, active: event.target.checked })} /></label>
          <label className="field field-wide"><span>Description</span><textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
        </div>
        <div className="form-actions"><button className="button button-primary" type="submit">Save</button></div>
      </form>
    </section>}
    <section className="detail-card">
      <div className="detail-grid">
        <div><span>Owner</span><strong>{item.owner_name || "—"}</strong></div>
        <div><span>Criticality</span><strong>{item.criticality_name || "Not set"}</strong></div>
        <div><span>Status</span><StatusBadge status={item.active ? "active" : "inactive"} /></div>
        <div><span>Supporting Services</span><strong>{item.service_count}</strong></div>
        <div><span>Connected Assets</span><strong>{affectedAssets.length}</strong></div>
        <div><span>Open Service knowledge gaps</span><strong>{item.open_gap_count}</strong></div>
      </div>
    </section>
    <section className="detail-card">
      <div className="form-card-header"><div><p className="eyebrow">Support</p><h2>Services</h2></div></div>
      {links.length === 0 ? <p className="empty-state">No Services support this Business Function yet.</p> : <div className="dependency-list">{links.map((link) => <article className="dependency-row" key={link.id}><Link href={`/services/${link.service_id}`}><strong>{link.service_name || "Unavailable Service"}</strong></Link><span>{link.relationship_label}{link.is_primary ? " · Primary" : ""}</span></article>)}</div>}
    </section>
    {affectedAssets.length > 0 && <section className="detail-card">
      <div className="form-card-header"><div><p className="eyebrow">Structural context</p><h2>Connected Assets through Services</h2></div><span>{affectedAssets.length}</span></div>
      <div className="dependency-list">{affectedAssets.map((asset) => <article className="dependency-row" key={asset.id}><Link href={asset.href}><strong>{asset.name}</strong></Link><span>{asset.subtitle || "Asset"}</span></article>)}</div>
    </section>}
    {graph.edges.length > 0 && <section className="detail-card">
      <div className="form-card-header"><h2>Capability graph</h2></div>
      <OperationalGraphView graph={graph} />
    </section>}
  </>;
}
