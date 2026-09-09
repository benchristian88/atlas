"use client";

import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AccessDenied } from "../../../components/access-denied";
import { useAuth } from "../../../components/auth-context";
import { EntityDetailHeader, EntitySection, EntityRelationshipRow, EntityRelationshipList, EntityEditDisclosure } from "../../../components/entity-detail";
import { recordContextOptions } from "../../../lib/record-context.mjs";
import { OperationalGraphView } from "../../../components/operational-graph-view";
import { apiRequest } from "../../../lib/api";

export default function BusinessFunctionDetailPage({ params }) {
  const { id } = use(params);
  const { hasPermission, hasPermissionForObject } = useAuth();
  const [item, setItem] = useState(null);
  const [links, setLinks] = useState([]);
  const [criticalityLevels, setCriticalityLevels] = useState([]);
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [serviceMetadata, setServiceMetadata] = useState([]);
  const [metadataError, setMetadataError] = useState("");
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const loadVersion = useRef(0);
  const canView = hasPermission("business_functions.view");

  const load = useCallback(async () => {
    const version = ++loadVersion.current;
    if (!canView) return;
    setLoading(true);
    setError(""); setItem(null); setMetadataError("");
    try {
      const record = await apiRequest(`/business-functions/${id}`);
      if (version !== loadVersion.current) return;
      const [serviceLinks, graphData, levels, metadata] = await Promise.all([
        apiRequest(`/business-functions/${id}/services`),
        apiRequest(`/business-functions/${id}/graph`),
        hasPermissionForObject("business_functions.manage", record.customer_id, record.site_id) ? apiRequest("/criticality-levels") : [],
        record.active ? apiRequest(`/operational-graph?focus_type=business_function&focus_id=${id}&max_depth=1&node_limit=500&edge_family=service_business_function`, recordContextOptions(record.customer_id, record.site_id)).catch(() => { if (version === loadVersion.current) setMetadataError("Supporting Service status and completeness could not be loaded."); return null; }) : null,
      ]);
      if (version !== loadVersion.current) return;
      setItem(record);
      setLinks(serviceLinks);
      setGraph(graphData);
      setCriticalityLevels(levels);
      setServiceMetadata(metadata?.nodes || []);
      if (metadata?.truncated) setMetadataError("Supporting Service metadata is bounded. Open a Service or focus it in Knowledge Graph for more detail.");
      setForm({ name: record.name, description: record.description || "", owner_name: record.owner_name || "", criticality_level_id: record.criticality_level_id || "", active: record.active });
    } catch (requestError) {
      if (version !== loadVersion.current) return;
      setError(requestError.message);
    } finally {
      if (version === loadVersion.current) setLoading(false);
    }
  }, [canView, hasPermissionForObject, id]);

  useEffect(() => { load(); return () => { loadVersion.current += 1; }; }, [load]);
  const connectedAssets = useMemo(() => graph.nodes.filter((node) => node.entity_type === "asset"), [graph.nodes]);

  if (!canView) return <AccessDenied />;
  if (loading) return <div className="status-banner">Loading Business Function…</div>;
  if (!item || item.id !== id) return <div className="error-banner" role="alert">{error || "Business Function not found."}</div>;

  const canManage = hasPermissionForObject("business_functions.manage", item.customer_id, item.site_id);
  async function save(event) {
    event.preventDefault();
    setSaving(true); setError("");
    try {
      await apiRequest(`/business-functions/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ ...form, description: form.description || null, owner_name: form.owner_name || null, criticality_level_id: form.criticality_level_id || null }),
      });
      setEditing(false);
      await load();
    } catch (requestError) {
      setError(requestError.message);
    } finally { setSaving(false); }
  }

  return <div className="operations-page entity-detail-page">
    <EntityDetailHeader type="business_function" id={id} name={item.name} description={item.description || "Business purpose has not been documented."} subtitle="Business Function · Why it matters" criticality={item.criticality_name} canGraph={item.active} actions={canManage && <button className="button button-secondary" onClick={() => setEditing(!editing)} type="button" aria-expanded={editing}>{editing ? "Cancel" : "Edit"}</button>} />
    {error && <div className="error-banner" role="alert">{error}</div>}
    {editing && <section className="form-card">
      <form className="resource-form" onSubmit={save}>
        <div className="form-grid">
          <label className="field"><span>Name *</span><input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
          <label className="field"><span>Owner</span><input value={form.owner_name} onChange={(event) => setForm({ ...form, owner_name: event.target.value })} /></label>
          <label className="field"><span>Criticality</span><select value={form.criticality_level_id} onChange={(event) => setForm({ ...form, criticality_level_id: event.target.value })}><option value="">Not set</option>{criticalityLevels.filter((level) => level.active || level.id === item.criticality_level_id).map((level) => <option key={level.id} value={level.id}>{level.name}</option>)}</select></label>
          <label className="field checkbox-field"><span>Active</span><input checked={form.active} type="checkbox" onChange={(event) => setForm({ ...form, active: event.target.checked })} /></label>
          <label className="field field-wide"><span>Description</span><textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
        </div>
        <div className="form-actions"><button className="button button-primary" disabled={saving} type="submit">{saving ? "Saving…" : "Save"}</button></div>
      </form>
    </section>}
    <EntitySection title="Overview" description="The business outcome supported by Services.">
      <div className="detail-grid">
        <div><span>Owner</span><strong>{item.owner_name || "Not recorded"}</strong></div>
        <div><span>Record lifecycle</span><strong>{item.active ? "Active" : "Inactive"}</strong></div>
        <div><span>Scope</span><strong>{item.site_id ? "Site" : "Customer-wide"}</strong></div>
        <div><span>Supporting relationships</span><strong>{links.length}</strong></div>
        <div><span>Connected Assets</span><strong>{connectedAssets.length}</strong></div>
      </div>
    </EntitySection>
    <EntitySection title="Supporting Services" description="Recorded relationships from Services to this business outcome." count={links.length}>
      {metadataError && <p role="status">{metadataError}</p>}
      {!links.length ? <p className="empty-state">No Services support this Business Function yet.</p> : <EntityRelationshipList>{links.map((link) => <EntityRelationshipRow key={link.id} type="service" name={link.service_name || "Unavailable Service"} href={`/services/${link.service_id}`} context={`${link.relationship_label} this Business Function${link.is_primary ? " · Primary" : ""}${link.importance ? ` · ${link.importance}` : ""}`} description={link.description} metadata={serviceMetadata.find((node) => node.entity_type === "service" && node.entity_id === link.service_id)} />)}</EntityRelationshipList>}
    </EntitySection>
    <EntitySection title="Knowledge quality">
      <p>Completeness is not evaluated for Business Functions. Supporting Service completeness is shown where available; it is not a Business Function score.</p>
      <p className="ops-meta">{links.length} recorded supporting relationships. Business Function availability is not evaluated.</p>
      {hasPermission("knowledge_gaps.view") && <p>Open Service knowledge gaps: <strong>{item.open_gap_count}</strong></p>}
    </EntitySection>
    {connectedAssets.length > 0 && <EntitySection title="Connected Assets through Services" description="Structural context recorded in Atlas." count={connectedAssets.length}>
      <EntityRelationshipList>{connectedAssets.map((asset) => <EntityRelationshipRow key={asset.id} type="asset" name={asset.name} href={asset.href} context={asset.subtitle || "Asset"} />)}</EntityRelationshipList>
    </EntitySection>}
    {graph.edges.length > 0 && <EntityEditDisclosure title="Recorded capability graph"><section className="ops-card"><h2>Capability graph</h2><OperationalGraphView graph={graph} /></section></EntityEditDisclosure>}
    <EntitySection title="Record information"><dl className="ops-definition"><dt>Created</dt><dd>{new Date(item.created_at).toLocaleString()}</dd><dt>Updated</dt><dd>{new Date(item.updated_at).toLocaleString()}</dd></dl></EntitySection>
  </div>;
}
