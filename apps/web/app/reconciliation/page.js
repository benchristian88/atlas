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
  const [loading, setLoading] = useState(true);
  const [deciding, setDeciding] = useState("");
  const [error, setError] = useState("");
  const canView = hasPermission("assets.view");
  const canDecide = hasPermission("assets.edit");

  const load = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    setError("");
    try { setItems(await apiRequest("/reconciliation-items?status=open")); }
    catch (requestError) { setError(requestError.message || "Atlas could not load reconciliation items."); }
    finally { setLoading(false); }
  }, [canView, workspace.reloadKey]);

  useEffect(() => { load(); }, [load]);

  if (!canView) return <AccessDenied />;

  async function decide(item, action) {
    setDeciding(item.id);
    setError("");
    try {
      await apiRequest(`/reconciliation-items/${item.id}/${action}`, { method: "POST", body: JSON.stringify({ reason: null }) });
      await load();
    } catch (requestError) { setError(requestError.message || `Atlas could not ${action} this item.`); }
    finally { setDeciding(""); }
  }

  return <>
    <PageHeader eyebrow="Operations" title="Reconciliation" description="Review discovered knowledge before it changes Atlas’s operational model." />
    {error && <div className="error-banner" role="alert">{error}</div>}
    {loading ? <div className="status-banner" role="status">Loading reconciliation items…</div> : <section className="knowledge-list">
      {items.length === 0 ? <div className="empty-state detail-card">No open reconciliation items.</div> : items.map((item) => <article className="detail-card reconciliation-card" key={item.id}>
        <div className="reconciliation-heading"><div><p className="eyebrow">{item.category.replaceAll("_", " ")}</p><h2>{item.entity_type.replaceAll("_", " ")}</h2></div><span className="secondary-text">{item.source_name || "Unknown source"} · {new Date(item.created_at).toLocaleString()}</span></div>
        <div className="reconciliation-values"><div><span>Current</span><code>{value(item.current_value_json)}</code></div><div><span>Observed</span><code>{value(item.observed_value_json)}</code></div></div>
        {item.recommended_action && <p className="secondary-text">Recommended: {item.recommended_action}</p>}
        {canDecide && <div className="form-actions"><button className="button button-secondary" disabled={deciding === item.id} onClick={() => decide(item, "defer")} type="button">Defer</button><button className="button button-secondary" disabled={deciding === item.id} onClick={() => decide(item, "reject")} type="button">Reject</button><button className="button button-primary" disabled={deciding === item.id} onClick={() => decide(item, "accept")} type="button">{deciding === item.id ? "Saving…" : "Accept"}</button></div>}
      </article>)}
    </section>}
  </>;
}
