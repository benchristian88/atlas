"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { AccessDenied } from "../../../components/access-denied";
import { AssetIcon } from "../../../components/asset-icon";
import { AssertionsPanel } from "../../../components/assertions-panel";
import { useAuth } from "../../../components/auth-context";
import { PageHeader } from "../../../components/page-header";
import { StatusBadge } from "../../../components/status-badge";
import { useWorkspaceContext } from "../../../components/workspace-context";
import { apiRequest } from "../../../lib/api";

function typeAllows(type, source, target) {
  const sources = type.allowed_source_asset_type_keys || [];
  const targets = type.allowed_target_asset_type_keys || [];
  return (!sources.length || sources.includes(source.asset_type))
    && (!targets.length || targets.includes(target.asset_type));
}

function displayCustomValue(definition, value) {
  if (value === null || value === undefined || value === "") return "—";
  if (definition?.data_type === "boolean") return value ? "Yes" : "No";
  if (definition?.data_type === "dropdown") {
    return definition.options.find((option) => option.value === value)?.label || value;
  }
  return String(value);
}

function safeManagementUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function compactKnowledgeValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  return typeof value === "string" ? value : JSON.stringify(value);
}

function historyStatus(entry) {
  if (entry.retracted_at) return "Retracted";
  if (entry.confirmation_status === "rejected") return "Rejected";
  if (entry.is_accepted) return "Accepted";
  if (entry.confirmation_status === "conflicted") return "Conflicting";
  if (entry.is_source_current) return "Current from source";
  if (entry.confirmation_status === "superseded") return "Superseded";
  return "Historical";
}

export default function AssetDetailPage() {
  const { id } = useParams();
  const searchParams = useSearchParams();
  const { hasPermission, hasPermissionForObject } = useAuth();
  const workspace = useWorkspaceContext();
  const [asset, setAsset] = useState(null);
  const [assets, setAssets] = useState([]);
  const [assetTypes, setAssetTypes] = useState([]);
  const [customDefinitions, setCustomDefinitions] = useState([]);
  const [relationshipTypes, setRelationshipTypes] = useState([]);
  const [relationships, setRelationships] = useState([]);
  const [networks, setNetworks] = useState([]);
  const [interfaces, setInterfaces] = useState([]);
  const [assertions, setAssertions] = useState([]);
  const [factHistory, setFactHistory] = useState({});
  const [knowledgeSummary, setKnowledgeSummary] = useState(null);
  const [knowledgeTab, setKnowledgeTab] = useState("summary");
  const [relationshipForm, setRelationshipForm] = useState({ target_asset_id: "", relationship_type: "", notes: "" });
  const [interfaceForm, setInterfaceForm] = useState({ name: "eth0", network_id: "", ip_address: "", mac_address: "", is_primary: true, notes: "" });
  const [showRelationshipForm, setShowRelationshipForm] = useState(false);
  const [showInterfaceForm, setShowInterfaceForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const canView = hasPermission("assets.view");

  const load = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    setError("");
    try {
      const current = await apiRequest(`/assets/${id}`);
      const mayViewRelationships = hasPermissionForObject(
        "relationships.view",
        current.customer_id,
        current.site_id,
      );
      const mayViewNetworks = hasPermissionForObject(
        "networks.view",
        current.customer_id,
        current.site_id,
      );
      const [allAssets, types, fields, edges, relationTypes, allNetworks, assetInterfaces, assetAssertions, history, summary] = await Promise.all([
        mayViewRelationships ? apiRequest("/assets") : Promise.resolve([]),
        hasPermission("asset_types.view") ? apiRequest("/asset-types") : Promise.resolve([]),
        hasPermission("custom_fields.view") ? apiRequest("/custom-fields") : Promise.resolve([]),
        mayViewRelationships ? apiRequest(`/asset-relationships?asset_id=${id}`) : Promise.resolve([]),
        hasPermission("relationship_types.view") ? apiRequest("/relationship-types") : Promise.resolve([]),
        mayViewNetworks ? apiRequest("/networks") : Promise.resolve([]),
        mayViewNetworks ? apiRequest(`/asset-interfaces?asset_id=${id}`) : Promise.resolve([]),
        apiRequest(`/assertions?subject_type=asset&subject_id=${id}&current_only=false`),
        apiRequest(`/assets/${id}/fact-history`),
        apiRequest(`/assets/${id}/knowledge-summary`),
      ]);
      setAsset(current);
      setAssets(allAssets);
      setAssetTypes(types);
      setCustomDefinitions(fields);
      setRelationships(edges);
      setRelationshipTypes(relationTypes);
      setNetworks(allNetworks);
      setInterfaces(assetInterfaces);
      setAssertions(assetAssertions);
      setFactHistory(history.facts || {});
      setKnowledgeSummary(summary);
    } catch (requestError) {
      setError(requestError.message || "Atlas could not load this asset.");
    } finally {
      setLoading(false);
    }
  }, [canView, hasPermission, hasPermissionForObject, id]);

  useEffect(() => { load(); }, [load]);
  const assetTypesByKey = useMemo(() => Object.fromEntries(assetTypes.map((type) => [type.key, type])), [assetTypes]);
  const assetsById = useMemo(() => Object.fromEntries(assets.map((item) => [item.id, item])), [assets]);
  const networksById = useMemo(() => Object.fromEntries(networks.map((item) => [item.id, item])), [networks]);
  if (!canView) return <AccessDenied />;
  if (loading) return <div className="status-banner" role="status">Loading asset…</div>;
  if (!asset) return <div className="error-banner" role="alert">{error || "Asset not found."}</div>;

  const customer = workspace.customers.find((item) => item.id === asset.customer_id);
  const site = workspace.sites.find((item) => item.id === asset.site_id);
  const assetType = assetTypesByKey[asset.asset_type];
  const managementUrl = safeManagementUrl(asset.metadata?.management_url);
  const sameSiteAssets = assets.filter((item) => item.id !== asset.id && item.customer_id === asset.customer_id && item.site_id === asset.site_id);
  const selectedTarget = sameSiteAssets.find((item) => item.id === relationshipForm.target_asset_id);
  const allowedRelationshipTypes = selectedTarget
    ? relationshipTypes.filter((type) => type.active && typeAllows(type, asset, selectedTarget))
    : relationshipTypes.filter((type) => type.active && (!(type.allowed_source_asset_type_keys || []).length || type.allowed_source_asset_type_keys.includes(asset.asset_type)));
  const availableNetworks = networks.filter((network) => network.customer_id === asset.customer_id && (!network.site_id || network.site_id === asset.site_id));
  const canEdit = hasPermissionForObject("assets.edit", asset.customer_id, asset.site_id);
  const canViewRelationships = hasPermissionForObject(
    "relationships.view",
    asset.customer_id,
    asset.site_id,
  );
  const canViewNetworks = hasPermissionForObject(
    "networks.view",
    asset.customer_id,
    asset.site_id,
  );
  const canCreateRelationship = hasPermissionForObject(
    "relationships.create",
    asset.customer_id,
    asset.site_id,
  );
  const canDeleteRelationship = hasPermissionForObject(
    "relationships.delete",
    asset.customer_id,
    asset.site_id,
  );
  const canCreateInterface = hasPermissionForObject(
    "networks.create",
    asset.customer_id,
    asset.site_id,
  );
  const canDeleteInterface = hasPermissionForObject(
    "networks.delete",
    asset.customer_id,
    asset.site_id,
  );
  const canDeleteAssertions = hasPermissionForObject(
    "assertions.delete",
    asset.customer_id,
    asset.site_id,
  );
  const canRetractAssertions = hasPermissionForObject(
    "assertions.retract",
    asset.customer_id,
    asset.site_id,
  );

  async function createRelationship(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await apiRequest("/asset-relationships", { method: "POST", body: JSON.stringify({ source_asset_id: asset.id, target_asset_id: relationshipForm.target_asset_id, relationship_type: relationshipForm.relationship_type, notes: relationshipForm.notes || null }) });
      setRelationshipForm({ target_asset_id: "", relationship_type: "", notes: "" });
      setShowRelationshipForm(false);
      await load();
    } catch (requestError) { setError(requestError.message || "Atlas could not create this relationship."); }
    finally { setSaving(false); }
  }

  async function removeRelationship(edge) {
    if (!window.confirm(`Delete the ${edge.relationship_type} relationship?`)) return;
    try { await apiRequest(`/asset-relationships/${edge.id}`, { method: "DELETE" }); await load(); }
    catch (requestError) { setError(requestError.message); }
  }

  async function createInterface(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await apiRequest("/asset-interfaces", { method: "POST", body: JSON.stringify({ asset_id: asset.id, network_id: interfaceForm.network_id || null, name: interfaceForm.name, ip_address: interfaceForm.ip_address || null, mac_address: interfaceForm.mac_address || null, is_primary: interfaceForm.is_primary, notes: interfaceForm.notes || null }) });
      setInterfaceForm({ name: "eth0", network_id: "", ip_address: "", mac_address: "", is_primary: false, notes: "" });
      setShowInterfaceForm(false);
      await load();
    } catch (requestError) { setError(requestError.message || "Atlas could not create this interface."); }
    finally { setSaving(false); }
  }

  async function removeInterface(item) {
    if (!window.confirm(`Delete interface “${item.name}”?`)) return;
    try { await apiRequest(`/asset-interfaces/${item.id}`, { method: "DELETE" }); await load(); }
    catch (requestError) { setError(requestError.message); }
  }

  async function refreshAssertions() {
    try {
      const [nextAssertions, history, summary] = await Promise.all([
        apiRequest(`/assertions?subject_type=asset&subject_id=${id}&current_only=false`),
        apiRequest(`/assets/${id}/fact-history`),
        apiRequest(`/assets/${id}/knowledge-summary`),
      ]);
      setAssertions(nextAssertions);
      setFactHistory(history.facts || {});
      setKnowledgeSummary(summary);
    } catch (requestError) {
      setError(requestError.message || "Atlas could not refresh asset assertions.");
    }
  }

  return (
    <>
      <div className="page-heading-row"><div className="asset-detail-heading"><AssetIcon asset={{ ...asset, icon_url: asset.icon_url || asset.resolved_icon_url }} assetType={assetType} alt="" size={58} /><PageHeader eyebrow="Asset detail" title={asset.name} description={`${customer?.name || "Unknown customer"} / ${site?.name || "Unknown site"}`} /></div>{canEdit && <Link className="button button-secondary" href={`/assets/${id}/edit`}>Edit asset</Link>}</div>
      {searchParams.get("updated") === "1" && <div className="success-banner" role="status">Asset updated successfully.</div>}
      {error && <div className="error-banner" role="alert">{error}</div>}
      <section className="detail-card"><div className="detail-grid">
        <div><span>Status</span><strong><StatusBadge status={asset.status} /></strong></div><div><span>Type</span><strong>{assetType?.name || asset.asset_type}</strong></div><div><span>Source</span><strong>{asset.source}</strong></div>
        <div><span>Vendor</span><strong>{asset.vendor || "—"}</strong></div><div><span>Model</span><strong>{asset.model || "—"}</strong></div><div><span>Hostname</span><strong>{asset.hostname || "—"}</strong></div>
        <div><span>Primary IP</span><strong className="mono">{asset.ip_address || "—"}</strong></div><div><span>Management</span><strong>{managementUrl ? <a className="card-link" href={managementUrl} rel="noreferrer" target="_blank">Open management URL</a> : "—"}</strong></div><div><span>Tags</span><strong>{(asset.metadata?.tags || []).join(", ") || "—"}</strong></div>
        <div className="detail-span"><span>Description</span><strong>{asset.description || "—"}</strong></div>
      </div></section>

      {Object.keys(asset.custom_fields || {}).length > 0 && <section className="detail-card"><div className="form-card-header"><h2>Custom enrichment</h2></div><div className="detail-grid">{Object.entries(asset.custom_fields).map(([key, value]) => { const definition = customDefinitions.find((item) => item.key === key); return <div key={key}><span>{definition?.name || key}</span><strong>{displayCustomValue(definition, value)}</strong></div>; })}</div></section>}

      {canViewNetworks && <section className="form-card"><div className="form-card-header"><h2>Interfaces and networks</h2>{canCreateInterface && !showInterfaceForm && <button className="button button-primary" onClick={() => setShowInterfaceForm(true)} type="button">Add interface</button>}</div>
        {showInterfaceForm && <form onSubmit={createInterface}><div className="form-grid"><label className="field"><span>Interface name *</span><input required value={interfaceForm.name} onChange={(event) => setInterfaceForm({ ...interfaceForm, name: event.target.value })} /></label><label className="field"><span>Network / VLAN</span><select value={interfaceForm.network_id} onChange={(event) => setInterfaceForm({ ...interfaceForm, network_id: event.target.value })}><option value="">Unassigned</option>{availableNetworks.map((network) => <option key={network.id} value={network.id}>{network.vlan_id !== null ? `VLAN ${network.vlan_id} — ` : ""}{network.name}</option>)}</select></label><label className="field"><span>IP address</span><input value={interfaceForm.ip_address} onChange={(event) => setInterfaceForm({ ...interfaceForm, ip_address: event.target.value })} /></label><label className="field"><span>MAC address</span><input value={interfaceForm.mac_address} onChange={(event) => setInterfaceForm({ ...interfaceForm, mac_address: event.target.value })} /></label><label className="field checkbox-field"><input checked={interfaceForm.is_primary} onChange={(event) => setInterfaceForm({ ...interfaceForm, is_primary: event.target.checked })} type="checkbox" /><span>Primary interface</span></label><label className="field field-wide"><span>Notes</span><textarea value={interfaceForm.notes} onChange={(event) => setInterfaceForm({ ...interfaceForm, notes: event.target.value })} /></label></div><div className="form-actions"><button className="button button-secondary" onClick={() => setShowInterfaceForm(false)} type="button">Cancel</button><button className="button button-primary" disabled={saving} type="submit">Add interface</button></div></form>}
        <div className="interface-list">{interfaces.length === 0 ? <p className="secondary-text">No interfaces yet.</p> : interfaces.map((item) => <div className="interface-row" key={item.id}><div><strong>{item.name}{item.is_primary ? " · Primary" : ""}</strong><span>{item.ip_address || "No IP"}{item.mac_address ? ` · ${item.mac_address}` : ""}</span><span>{networksById[item.network_id]?.name || "Unassigned network"}</span></div>{canDeleteInterface && <button className="text-button text-danger" onClick={() => removeInterface(item)} type="button">Delete</button>}</div>)}</div>
      </section>}

      {canViewRelationships && <><section className="form-card"><div className="form-card-header"><h2>Relationships</h2>{canCreateRelationship && relationshipTypes.length > 0 && !showRelationshipForm && <button className="button button-primary" onClick={() => setShowRelationshipForm(true)} type="button">Add relationship</button>}</div>
        {showRelationshipForm && <form onSubmit={createRelationship}><div className="form-grid"><label className="field"><span>Source</span><input disabled value={asset.name} /></label><label className="field"><span>Target asset *</span><select required value={relationshipForm.target_asset_id} onChange={(event) => setRelationshipForm({ ...relationshipForm, target_asset_id: event.target.value, relationship_type: "" })}><option value="">Select same-site asset</option>{sameSiteAssets.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="field"><span>Relationship type *</span><select required value={relationshipForm.relationship_type} onChange={(event) => setRelationshipForm({ ...relationshipForm, relationship_type: event.target.value })}><option value="">Select relationship</option>{allowedRelationshipTypes.map((type) => <option key={type.key} value={type.key}>{type.name}</option>)}</select></label><label className="field field-wide"><span>Notes</span><textarea value={relationshipForm.notes} onChange={(event) => setRelationshipForm({ ...relationshipForm, notes: event.target.value })} /></label></div><div className="form-actions"><button className="button button-secondary" onClick={() => setShowRelationshipForm(false)} type="button">Cancel</button><button className="button button-primary" disabled={saving} type="submit">Add relationship</button></div></form>}
      </section><section className="table-card"><div className="table-meta"><span>{relationships.length} relationships</span></div>{relationships.length === 0 ? <p className="empty-state">No relationships yet.</p> : <div className="relationship-list">{relationships.map((edge) => { const type = relationshipTypes.find((item) => item.key === edge.relationship_type); return <div className="relationship-row" key={edge.id}><span><strong>{edge.source_asset_name || assetsById[edge.source_asset_id]?.name || "Unknown"}</strong> → {type?.name || edge.relationship_type} → <strong>{edge.target_asset_name || assetsById[edge.target_asset_id]?.name || "Unknown"}</strong>{edge.notes ? ` — ${edge.notes}` : ""}</span>{canDeleteRelationship && <button className="text-button text-danger" onClick={() => removeRelationship(edge)} type="button">Delete</button>}</div>; })}</div>}</section></>}

      <section className="knowledge-card"><div className="form-card-header"><div><p className="eyebrow">Knowledge</p><h2>Asset knowledge</h2></div>{knowledgeSummary && (knowledgeSummary.conflict_count > 0 || knowledgeSummary.unresolved_count > 0) && <StatusBadge status="Needs review" />}</div><div className="knowledge-tabs" role="tablist" aria-label="Asset knowledge views">{[["summary", "Summary"], ["history", "History"], ["raw", "Raw assertions"]].map(([value, label]) => <button aria-selected={knowledgeTab === value} className={knowledgeTab === value ? "active" : ""} key={value} onClick={() => setKnowledgeTab(value)} role="tab" type="button">{label}</button>)}</div>
        {knowledgeTab === "summary" && (!knowledgeSummary || knowledgeSummary.groups.length === 0 ? <p className="empty-state">No sourced knowledge is linked to this asset yet.</p> : <div className="knowledge-summary-grid">{knowledgeSummary.groups.map((item) => <article className={`knowledge-summary-item${item.conflict || item.unresolved ? " knowledge-conflict" : ""}`} key={item.predicate}><div className="knowledge-summary-heading"><div><span className="secondary-text">{item.cardinality === "multi" ? "Multiple values" : "Single value"}</span><h3>{item.label}</h3></div>{item.conflict ? <StatusBadge status="Conflicting" /> : item.unresolved ? <StatusBadge status="Unresolved" /> : item.accepted ? <StatusBadge status="Accepted" /> : <StatusBadge status="Observed" />}</div><div className="knowledge-accepted"><span>Accepted Atlas value</span>{item.accepted_values.length ? item.accepted_values.map((entry) => <strong title={compactKnowledgeValue(entry.value)} key={entry.assertion_id}>{compactKnowledgeValue(entry.value)}</strong>) : <strong>Not selected</strong>}</div><div className="knowledge-observations"><span>Latest source observations</span>{item.latest_observations.length ? item.latest_observations.map((entry) => <div key={entry.assertion_id}><code title={compactKnowledgeValue(entry.value)}>{compactKnowledgeValue(entry.value)}</code><small>{entry.source_name || "Unavailable"}</small></div>) : <p className="secondary-text">No active observations</p>}</div><footer>{item.source_count} active source{item.source_count === 1 ? "" : "s"} · {item.assertion_count} assertion{item.assertion_count === 1 ? "" : "s"} · {item.historical_count} historical · {item.last_observed_at ? `Observed ${new Date(item.last_observed_at).toLocaleString()}` : "Never observed"}</footer></article>)}</div>)}
        {knowledgeTab === "history" && (Object.keys(factHistory).length === 0 ? <p className="empty-state">No sourced fact history yet.</p> : <div className="knowledge-timeline">{Object.entries(factHistory).flatMap(([predicate, entries]) => entries.map((entry) => ({ ...entry, predicate }))).sort((left, right) => new Date(right.last_observed_at || 0) - new Date(left.last_observed_at || 0)).map((entry) => <article key={entry.assertion_id}><div className="knowledge-timeline-marker" /><div><div className="knowledge-timeline-heading"><strong>{entry.predicate.replaceAll("_", " ")}</strong><StatusBadge status={historyStatus(entry)} /></div><p><code>{compactKnowledgeValue(entry.value)}</code> from {entry.source_name || "Unavailable"}</p><small>{entry.last_observed_at ? new Date(entry.last_observed_at).toLocaleString() : "Time unavailable"} · {entry.truth_classification || "Unknown truth classification"}</small></div></article>)}</div>)}
        {knowledgeTab === "raw" && <AssertionsPanel assertions={assertions} assetsById={assetsById} canDelete={canDeleteAssertions} canRetract={canRetractAssertions} onChanged={refreshAssertions} />}
      </section>
    </>
  );
}
