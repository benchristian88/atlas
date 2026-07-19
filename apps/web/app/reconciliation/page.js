"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";

function value(value) {
  if (value === null || value === undefined) return "—";
  return typeof value === "string" ? value : JSON.stringify(value);
}

const queues = [
  { key: "knowledge", label: "Missing knowledge", knowledge: true },
  { key: "open", label: "All open", status: "open" },
  { key: "new", label: "Newly discovered", status: "open", category: "newly_discovered" },
  { key: "changed", label: "Changed", status: "open", category: "changed" },
  { key: "missing", label: "No longer observed", status: "open", category: "no_longer_observed" },
  { key: "contradictions", label: "Contradictions", status: "open", category: "contradiction" },
  { key: "duplicates", label: "Possible duplicates", status: "open", category: "possible_duplicate" },
  { key: "deferred", label: "Deferred", status: "deferred" },
  { key: "resolved", label: "Resolved", status: "resolved" },
  { key: "exception", label: "Exceptions", status: "exception" },
];

export default function ReconciliationPage() {
  const searchParams = useSearchParams();
  const { hasPermission } = useAuth();
  const workspace = useWorkspaceContext();
  const [items, setItems] = useState([]);
  const [assets, setAssets] = useState([]);
  const [linkSelections, setLinkSelections] = useState({});
  const [tab, setTab] = useState("open");
  const [category, setCategory] = useState("");
  const [gapFilters, setGapFilters] = useState({ asset_type_id: "", requirement_id: "", severity: "", requirement_level: "", status: "", assigned_user_id: "", minimum_age_days: "" });
  const [gapFilterOptions, setGapFilterOptions] = useState({ assetTypes: [], requirements: [], users: [] });
  const [loading, setLoading] = useState(true);
  const [deciding, setDeciding] = useState("");
  const [error, setError] = useState("");
  const canViewReconciliation = hasPermission("reconciliation.view");
  const canViewGaps = hasPermission("knowledge_gaps.view");
  const canView = canViewReconciliation || canViewGaps;
  const canDecide = hasPermission("reconciliation.decide");

  const load = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    setError("");
    try {
      const queue = queues.find((item) => item.key === tab) || queues[0];
      if (queue.knowledge) {
        const parameters = new URLSearchParams(Object.entries(gapFilters).filter(([, filterValue]) => filterValue !== ""));
        const gaps = canViewGaps ? await apiRequest(`/knowledge-gaps${parameters.size ? `?${parameters}` : ""}`) : [];
        if (!parameters.size) setGapFilterOptions({ assetTypes: Array.from(new Map(gaps.filter((gap) => gap.asset_type_id_snapshot).map((gap) => [gap.asset_type_id_snapshot, gap.asset_type_name || "Unavailable"])), ([id, name]) => ({ id, name })), requirements: Array.from(new Map(gaps.map((gap) => [gap.requirement_definition_id, gap.requirement_name || "Unavailable"])), ([id, name]) => ({ id, name })), users: Array.from(new Map(gaps.filter((gap) => gap.assigned_to_user_id).map((gap) => [gap.assigned_to_user_id, gap.assigned_to_name || "Unavailable"])), ([id, name]) => ({ id, name })) });
        setItems(gaps); setAssets([]); return;
      }
      const effectiveCategory = category || queue.category;
      const itemRequests = queue.status === "resolved"
        ? [apiRequest("/reconciliation-items?status=accepted"), apiRequest("/reconciliation-items?status=rejected")]
        : [apiRequest(`/reconciliation-items?status=${queue.status}${effectiveCategory ? `&category=${effectiveCategory}` : ""}`)];
      const [groups, availableAssets] = await Promise.all([
        Promise.all(itemRequests),
        canDecide ? apiRequest("/assets") : Promise.resolve([]),
      ]);
      const loaded = groups.flat();
      setItems(effectiveCategory && queue.status === "resolved" ? loaded.filter((item) => item.category === effectiveCategory) : loaded);
      setAssets(availableAssets);
    }
    catch (requestError) { setError(requestError.message || "Atlas could not load reconciliation items."); }
    finally { setLoading(false); }
  }, [canDecide, canView, canViewGaps, category, gapFilters, tab, workspace.reloadKey]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (searchParams.get("queue") === "missing-knowledge" || (!canViewReconciliation && canViewGaps)) setTab("knowledge");
  }, [canViewGaps, canViewReconciliation, searchParams]);

  if (!canView) return <AccessDenied />;

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

  async function gapAction(item, action) {
    const reason = window.prompt(action === "defer" ? "Why is this gap being deferred?" : "Why is this exception appropriate?");
    if (!reason?.trim()) return;
    const deferDate = action === "defer" ? window.prompt("Defer until (YYYY-MM-DD)") : null;
    if (action === "defer" && (!deferDate || Number.isNaN(new Date(deferDate).getTime()))) { setError("Enter a valid deferral date."); return; }
    setDeciding(item.id); setError("");
    try {
      const body = action === "defer" ? { reason: reason.trim(), deferred_until: new Date(deferDate).toISOString() } : { reason: reason.trim(), expires_at: null };
      await apiRequest(`/knowledge-gaps/${item.id}/${action}`, { method: "POST", body: JSON.stringify(body) });
      await load();
    } catch (requestError) { setError(requestError.message || "Atlas could not update this knowledge gap."); }
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
    <div className="admin-tabs" role="tablist">{queues.filter((queue) => queue.knowledge ? canViewGaps : canViewReconciliation).map((queue) => <button className={tab === queue.key ? "active" : ""} key={queue.key} onClick={() => setTab(queue.key)} role="tab" type="button">{queue.label}</button>)}</div>
    {tab !== "knowledge" && <div className="filter-bar"><label className="field"><span>Category</span><select onChange={(event) => setCategory(event.target.value)} value={category}><option value="">All categories</option><option value="newly_discovered">Newly discovered</option><option value="changed">Changed</option><option value="no_longer_observed">No longer observed</option><option value="contradiction">Contradiction</option><option value="possible_duplicate">Possible duplicate</option><option value="inferred_relationship">Inferred relationship</option></select></label></div>}
    {tab === "knowledge" && <div className="filter-bar"><label className="field"><span>Asset type</span><select onChange={(event) => setGapFilters((current) => ({ ...current, asset_type_id: event.target.value }))} value={gapFilters.asset_type_id}><option value="">All types</option>{gapFilterOptions.assetTypes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="field"><span>Requirement</span><select onChange={(event) => setGapFilters((current) => ({ ...current, requirement_id: event.target.value }))} value={gapFilters.requirement_id}><option value="">All requirements</option>{gapFilterOptions.requirements.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="field"><span>Severity</span><select onChange={(event) => setGapFilters((current) => ({ ...current, severity: event.target.value }))} value={gapFilters.severity}><option value="">All severities</option>{["critical", "high", "medium", "low"].map((item) => <option key={item}>{item}</option>)}</select></label><label className="field"><span>Level</span><select onChange={(event) => setGapFilters((current) => ({ ...current, requirement_level: event.target.value }))} value={gapFilters.requirement_level}><option value="">All levels</option>{["required", "conditional", "recommended"].map((item) => <option key={item}>{item}</option>)}</select></label><label className="field"><span>Status</span><select onChange={(event) => setGapFilters((current) => ({ ...current, status: event.target.value }))} value={gapFilters.status}><option value="">Active</option>{["open", "deferred", "exception", "resolved", "superseded"].map((item) => <option key={item}>{item}</option>)}</select></label><label className="field"><span>Assigned user</span><select onChange={(event) => setGapFilters((current) => ({ ...current, assigned_user_id: event.target.value }))} value={gapFilters.assigned_user_id}><option value="">Anyone</option>{gapFilterOptions.users.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="field"><span>Minimum age (days)</span><input min="0" onChange={(event) => setGapFilters((current) => ({ ...current, minimum_age_days: event.target.value }))} type="number" value={gapFilters.minimum_age_days} /></label><button className="text-button" onClick={() => setGapFilters({ asset_type_id: "", requirement_id: "", severity: "", requirement_level: "", status: "", assigned_user_id: "", minimum_age_days: "" })} type="button">Clear filters</button></div>}
    {error && <div className="error-banner" role="alert">{error}</div>}
    {loading ? <div className="status-banner" role="status">Loading reconciliation items…</div> : <section className="knowledge-list">
      {items.length === 0 ? <div className="empty-state detail-card">{tab === "knowledge" ? "No active knowledge gaps." : "No reconciliation items in this queue."}</div> : items.map((item) => { if (tab === "knowledge") return <article className="detail-card reconciliation-card" key={item.id}><div className="reconciliation-heading"><div><p className="eyebrow">{item.severity} · {item.requirement_level}{item.asset_type_name ? ` · ${item.asset_type_name}` : ""}</p><h2>{item.entity_name || "Asset"}</h2></div><span className="secondary-text">{item.status.replaceAll("_", " ")}</span></div><h3>{item.requirement_name || "Knowledge requirement"}</h3><p>{item.summary}</p><p className="secondary-text">First detected {new Date(item.first_detected_at).toLocaleString()} · evaluated {new Date(item.last_evaluated_at).toLocaleString()}{item.assigned_to_name ? ` · assigned to ${item.assigned_to_name}` : ""}</p>{item.remediation_hint && <p className="secondary-text">Next step: {item.remediation_hint}</p>}<div className="form-actions"><Link className="button button-secondary" href={`/assets/${item.entity_id}`}>Open asset</Link>{hasPermission("assets.edit") && <Link className="button button-secondary" href={`/assets/${item.entity_id}/edit`}>Provide information</Link>}{hasPermission("knowledge_gaps.defer") && item.status !== "exception" && <button className="button button-secondary" disabled={deciding === item.id} onClick={() => gapAction(item, "defer")} type="button">Defer</button>}{hasPermission("knowledge_gaps.exception") && item.status !== "exception" && <button className="button button-primary" disabled={deciding === item.id} onClick={() => gapAction(item, "exception")} type="button">Record exception</button>}{hasPermission("knowledge_gaps.exception") && item.status === "exception" && <button className="button button-primary" disabled={deciding === item.id} onClick={async () => { setDeciding(item.id); try { await apiRequest(`/knowledge-gaps/${item.id}/reopen`, { method: "POST", body: JSON.stringify({ reason: "Reopened from reconciliation" }) }); await load(); } catch (requestError) { setError(requestError.message); } finally { setDeciding(""); } }} type="button">Reopen</button>}</div></article>; const relationship = item.entity_type === "asset_relationship"; const candidates = assets.filter((asset) => asset.customer_id === item.customer_id && asset.site_id === item.site_id); return <article className="detail-card reconciliation-card" key={item.id}>
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
