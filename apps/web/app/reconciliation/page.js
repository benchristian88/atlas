"use client";

import { useCallback, useEffect, useState } from "react";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";

function value(value) {
  if (value === null || value === undefined) return "—";
  return typeof value === "string" ? value : JSON.stringify(value);
}

export default function ReconciliationPage() {
  const { hasPermission } = useAuth();
  const workspace = useWorkspaceContext();
  const [items, setItems] = useState([]);
  const [assets, setAssets] = useState([]);
  const [linkSelections, setLinkSelections] = useState({});
  const [loading, setLoading] = useState(true);
  const [deciding, setDeciding] = useState("");
  const [error, setError] = useState("");
  const canView = hasPermission("assets.view");
  const canDecide = hasPermission("assets.edit");

  const load = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    setError("");
    try {
      const [openItems, availableAssets] = await Promise.all([
        apiRequest("/reconciliation-items?status=open"),
        canDecide ? apiRequest("/assets") : Promise.resolve([]),
      ]);
      setItems(openItems);
      setAssets(availableAssets);
    }
    catch (requestError) { setError(requestError.message || "Atlas could not load reconciliation items."); }
    finally { setLoading(false); }
  }, [canDecide, canView, workspace.reloadKey]);

  useEffect(() => { load(); }, [load]);

  if (!canView) return <AccessDenied />;

  async function decide(item, action) {
    setDeciding(item.id);
    setError("");
    try {
      await apiRequest(`/reconciliation-items/${item.id}/${action}`, { method: "POST", body: JSON.stringify({ reason: null }) });
      await load();
    } catch (requestError) {
      const blocked = requestError.details?.blocked_reason;
      setError(blocked ? `${requestError.message}. ${blocked}` : requestError.message || `Atlas could not ${action} this item.`);
    }
    finally { setDeciding(""); }
  }

  async function linkAsset(item) {
    const assetId = linkSelections[item.id];
    if (!assetId) { setError("Select an existing asset to link."); return; }
    setDeciding(item.id);
    setError("");
    try {
      await apiRequest(`/reconciliation-items/${item.id}/link-asset`, {
        method: "POST",
        body: JSON.stringify({ asset_id: assetId, reason: "Linked during reconciliation" }),
      });
      await load();
    } catch (requestError) { setError(requestError.message || "Atlas could not link this asset."); }
    finally { setDeciding(""); }
  }

  function relationshipLabel(item, current = false) {
    if (current && !item.current_relationship_id) return "No current relationship";
    const source = item.resolved_source_name || item.source_external_id || "Unresolved source";
    const target = item.resolved_target_name || item.target_external_id || "Unresolved target";
    const type = ((current ? item.current_value_json?.relationship_type : null) || item.observed_value_json?.relationship_type || "related_to").replaceAll("_", " ");
    return `${source} → ${type} → ${target}`;
  }

  return <>
    <PageHeader eyebrow="Operations" title="Reconciliation" description="Review discovered knowledge before it changes Atlas’s operational model." />
    {error && <div className="error-banner" role="alert">{error}</div>}
    {loading ? <div className="status-banner" role="status">Loading reconciliation items…</div> : <section className="knowledge-list">
      {items.length === 0 ? <div className="empty-state detail-card">No open reconciliation items.</div> : items.map((item) => { const relationship = item.entity_type === "asset_relationship"; const candidates = assets.filter((asset) => asset.customer_id === item.customer_id && asset.site_id === item.site_id); return <article className="detail-card reconciliation-card" key={item.id}>
        <div className="reconciliation-heading"><div><p className="eyebrow">{item.category.replaceAll("_", " ")}</p><h2>{item.entity_type.replaceAll("_", " ")}</h2></div><span className="secondary-text">{item.source_name || "Unknown source"} · {new Date(item.created_at).toLocaleString()}</span></div>
        <div className="reconciliation-values"><div><span>Current</span><code>{relationship ? relationshipLabel(item, true) : value(item.current_value_json)}</code></div><div><span>Observed</span><code>{relationship ? relationshipLabel(item) : value(item.observed_value_json)}</code></div></div>
        {relationship && <div className="resolution-grid"><div><span>Source</span><strong>{item.source_resolution_status || "unresolved"}</strong><small>{item.source_external_id}</small></div><div><span>Target</span><strong>{item.target_resolution_status || "unresolved"}</strong><small>{item.target_external_id}</small></div></div>}
        {item.blocked_reason && <div className="warning-banner" role="status">{item.blocked_reason}</div>}
        {item.recommended_action && <p className="secondary-text">Recommended: {item.recommended_action}</p>}
        {canDecide && item.entity_type === "asset" && ["newly_discovered", "possible_duplicate"].includes(item.category) && <div className="reconciliation-link"><select aria-label="Existing asset to link" onChange={(event) => setLinkSelections((current) => ({ ...current, [item.id]: event.target.value }))} value={linkSelections[item.id] || ""}><option value="">Select existing asset…</option>{candidates.map((asset) => <option key={asset.id} value={asset.id}>{asset.name} · {asset.asset_type}</option>)}</select><button className="button button-secondary" disabled={deciding === item.id || !linkSelections[item.id]} onClick={() => linkAsset(item)} type="button">Link asset</button></div>}
        {canDecide && <div className="form-actions"><button className="button button-secondary" disabled={deciding === item.id} onClick={() => decide(item, "defer")} type="button">Defer</button><button className="button button-secondary" disabled={deciding === item.id} onClick={() => decide(item, "reject")} type="button">Reject</button><button className="button button-primary" disabled={deciding === item.id || Boolean(item.blocked_reason)} onClick={() => decide(item, "accept")} title={item.blocked_reason || "Accept this item"} type="button">{deciding === item.id ? "Saving…" : "Accept"}</button></div>}
      </article>; })}
    </section>}
  </>;
}
