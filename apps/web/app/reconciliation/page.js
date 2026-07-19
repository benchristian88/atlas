"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";
import { RECONCILIATION_QUEUES, reconciliationQueueFromValue } from "../../lib/reconciliation-queues.mjs";

function value(value) {
  if (value === null || value === undefined) return "—";
  return typeof value === "string" ? value : JSON.stringify(value);
}

export default function ReconciliationPage() {
  const searchParams = useSearchParams();
  const queue = reconciliationQueueFromValue(searchParams.get("queue"));
  const { hasPermission } = useAuth();
  const workspace = useWorkspaceContext();
  const [items, setItems] = useState([]);
  const [assets, setAssets] = useState([]);
  const [linkSelections, setLinkSelections] = useState({});
  const [loading, setLoading] = useState(true);
  const [deciding, setDeciding] = useState("");
  const [error, setError] = useState("");
  const [loadedQueueKey, setLoadedQueueKey] = useState("");
  const canViewReconciliation = hasPermission("reconciliation.view");
  const canDecide = hasPermission("reconciliation.decide");
  const requestId = useRef(0);

  const load = useCallback(async () => {
    if (!canViewReconciliation) return;
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError("");
    try {
      const itemRequests = queue.status === "resolved"
        ? [apiRequest("/reconciliation-items?status=accepted"), apiRequest("/reconciliation-items?status=rejected")]
        : [apiRequest(`/reconciliation-items?status=${queue.status}${queue.category ? `&category=${queue.category}` : ""}`)];
      const [groups, availableAssets] = await Promise.all([
        Promise.all(itemRequests),
        canDecide ? apiRequest("/assets") : Promise.resolve([]),
      ]);
      if (requestId.current !== currentRequest) return;
      setLoadedQueueKey(queue.key);
      setItems(groups.flat());
      setAssets(availableAssets);
    } catch (requestError) {
      if (requestId.current !== currentRequest) return;
      setLoadedQueueKey(queue.key);
      setItems([]);
      setAssets([]);
      setError(requestError.message || "Atlas could not load reconciliation items.");
    } finally {
      if (requestId.current === currentRequest) setLoading(false);
    }
  }, [canDecide, canViewReconciliation, queue.category, queue.key, queue.status, workspace.reloadKey]);

  useEffect(() => {
    setItems([]);
    setAssets([]);
    setLinkSelections({});
    load();
    return () => { requestId.current += 1; };
  }, [load]);

  if (!canViewReconciliation) return <AccessDenied />;

  async function decide(item, action, disposition = null) {
    setDeciding(item.id);
    setError("");
    try {
      await apiRequest(`/reconciliation-items/${item.id}/${action}`, { method: "POST", body: JSON.stringify({ reason: null, disposition }) });
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

  const queueReady = loadedQueueKey === queue.key;

  return <>
    <PageHeader eyebrow="Operations" title="Reconciliation" description="Review new, changed, conflicting and no-longer-observed knowledge proposed by Atlas sources." />
    <div className="admin-tabs" role="tablist">{RECONCILIATION_QUEUES.map((candidate) => <Link aria-selected={queue.key === candidate.key} className={queue.key === candidate.key ? "active" : ""} href={candidate.href} key={candidate.key} role="tab">{candidate.label}</Link>)}</div>
    {queueReady && error && <div className="error-banner" role="alert">{error}</div>}
    {!queueReady || loading ? <div className="status-banner" role="status">Loading reconciliation items…</div> : <section className="knowledge-list">
      {items.length === 0 ? <div className="empty-state detail-card">No reconciliation items in this queue.</div> : items.map((item) => { const relationship = item.entity_type === "asset_relationship"; const candidates = assets.filter((asset) => asset.customer_id === item.customer_id && asset.site_id === item.site_id); return <article className="detail-card reconciliation-card" key={item.id}>
        <div className="reconciliation-heading"><div><p className="eyebrow">{item.category.replaceAll("_", " ")}</p><h2>{item.entity_name || item.entity_type.replaceAll("_", " ")}</h2></div><span className="secondary-text">{item.source_name || "Unknown source"} · {new Date(item.created_at).toLocaleString()}</span></div>
        {item.category === "no_longer_observed" && <p className="secondary-text">Last observed {item.last_observed_at ? new Date(item.last_observed_at).toLocaleString() : "Unavailable"}. Missing since {item.missing_since_at ? new Date(item.missing_since_at).toLocaleString() : "this snapshot"}.</p>}
        <div className="reconciliation-values"><div><span>Current</span><code>{relationship ? relationshipLabel(item, true) : value(item.current_value_json)}</code></div><div><span>Observed</span><code>{relationship ? relationshipLabel(item) : value(item.observed_value_json)}</code></div></div>
        {relationship && <div className="resolution-grid"><div><span>Source</span><strong>{item.source_resolution_status || "unresolved"}</strong><small>{item.source_external_id}</small></div><div><span>Target</span><strong>{item.target_resolution_status || "unresolved"}</strong><small>{item.target_external_id}</small></div></div>}
        {item.blocked_reason && <div className="warning-banner" role="status">{item.blocked_reason}</div>}
        {item.recommended_action && <p className="secondary-text">Recommended: {item.recommended_action}</p>}
        {canDecide && item.entity_type === "asset" && ["newly_discovered", "possible_duplicate"].includes(item.category) && <div className="reconciliation-link"><select aria-label="Existing asset to link" onChange={(event) => setLinkSelections((current) => ({ ...current, [item.id]: event.target.value }))} value={linkSelections[item.id] || ""}><option value="">Select existing asset…</option>{candidates.map((asset) => <option key={asset.id} value={asset.id}>{asset.name} · {asset.asset_type}</option>)}</select><button className="button button-secondary" disabled={deciding === item.id || !linkSelections[item.id]} onClick={() => linkAsset(item)} type="button">Link asset</button></div>}
        {canDecide && ["open", "deferred"].includes(item.status) && (item.category === "no_longer_observed" ? <div className="form-actions"><button className="button button-secondary" disabled={deciding === item.id} onClick={() => decide(item, "accept", "keep_active")} type="button">Keep active</button><button className="button button-secondary" disabled={deciding === item.id} onClick={() => decide(item, "accept", "mark_inactive")} type="button">Mark inactive</button><button className="button button-secondary" disabled={deciding === item.id} onClick={() => decide(item, "accept", "retire")} type="button">Retire</button><button className="button button-secondary" disabled={deciding === item.id} onClick={() => decide(item, "accept", "exception")} type="button">Exception</button><button className="button button-primary" disabled={deciding === item.id} onClick={() => decide(item, "accept", "mark_missing")} type="button">{deciding === item.id ? "Saving…" : "Mark missing"}</button></div> : <div className="form-actions"><button className="button button-secondary" disabled={deciding === item.id} onClick={() => decide(item, "defer")} type="button">Defer</button><button className="button button-secondary" disabled={deciding === item.id} onClick={() => decide(item, "reject")} type="button">Reject</button><button className="button button-primary" disabled={deciding === item.id || Boolean(item.blocked_reason)} onClick={() => decide(item, "accept")} title={item.blocked_reason || "Accept this item"} type="button">{deciding === item.id ? "Saving…" : "Accept"}</button></div>)}
      </article>; })}
    </section>}
  </>;
}
