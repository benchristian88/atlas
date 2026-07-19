"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";

const PAGE_SIZE = 30;

function display(value) {
  if (value === null || value === undefined) return "—";
  return typeof value === "string" ? value : JSON.stringify(value);
}

export default function ChangesPage() {
  const { hasPermission } = useAuth();
  const workspace = useWorkspaceContext();
  const [result, setResult] = useState({ items: [], total: 0, limit: PAGE_SIZE, offset: 0 });
  const [type, setType] = useState("");
  const [entityType, setEntityType] = useState("");
  const [period, setPeriod] = useState("30");
  const [attentionOnly, setAttentionOnly] = useState(false);
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const canView = hasPermission("changes.view");

  const load = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    setError("");
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
    if (type) params.set("change_type", type);
    if (entityType) params.set("entity_type", entityType);
    if (period) params.set("date_from", new Date(Date.now() - Number(period) * 86400000).toISOString());
    if (attentionOnly) params.set("attention_required", "true");
    if (appliedSearch) params.set("search", appliedSearch);
    try { setResult(await apiRequest(`/changes?${params}`)); }
    catch (requestError) { setError(requestError.message || "Atlas could not load knowledge changes."); }
    finally { setLoading(false); }
  }, [appliedSearch, attentionOnly, canView, entityType, offset, period, type, workspace.reloadKey]);

  useEffect(() => { load(); }, [load]);
  if (!canView) return <AccessDenied />;

  return <>
    <PageHeader eyebrow="Knowledge" title="Changes" description="A timeline of meaningful changes to Atlas knowledge. Security and access activity remains in Audit." />
    <form className="filter-bar" onSubmit={(event) => { event.preventDefault(); setOffset(0); setAppliedSearch(search.trim()); }}>
      <label className="field"><span>Change type</span><select value={type} onChange={(event) => { setType(event.target.value); setOffset(0); }}><option value="">All changes</option><option value="entity_discovered">Entity discovered</option><option value="entity_accepted">Entity accepted</option><option value="fact_changed">Fact changed</option><option value="relationship_added">Relationship added</option><option value="relationship_removed">Relationship removed</option><option value="entity_no_longer_observed">No longer observed</option><option value="entity_reobserved">Reobserved</option><option value="lifecycle_changed">Lifecycle changed</option><option value="exception_recorded">Exception recorded</option><option value="assertion_retracted">Assertion retracted</option></select></label>
      <label className="field"><span>Entity type</span><select value={entityType} onChange={(event) => { setEntityType(event.target.value); setOffset(0); }}><option value="">All entities</option><option value="asset">Assets</option><option value="asset_relationship">Relationships</option></select></label>
      <label className="field"><span>Period</span><select value={period} onChange={(event) => { setPeriod(event.target.value); setOffset(0); }}><option value="7">Last 7 days</option><option value="30">Last 30 days</option><option value="90">Last 90 days</option><option value="">All time</option></select></label>
      <label className="field checkbox-field"><input checked={attentionOnly} onChange={(event) => { setAttentionOnly(event.target.checked); setOffset(0); }} type="checkbox" /><span>Needs attention</span></label>
      <label className="field"><span>Search</span><input onChange={(event) => setSearch(event.target.value)} placeholder="Entity or summary" value={search} /></label>
      <button className="button button-secondary" type="submit">Apply</button>
    </form>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {loading ? <div className="status-banner" role="status">Loading changes…</div> : <section className="change-timeline">
      {result.items.length === 0 ? <div className="empty-state detail-card">No meaningful changes match these filters.</div> : result.items.map((change) => <article className="detail-card change-entry" key={change.id}>
        <div className="reconciliation-heading"><div><p className="eyebrow">{change.change_type.replaceAll("_", " ")}{change.attention_required ? " · Needs attention" : ""}</p><h2>{change.entity_name_snapshot}</h2></div><time className="secondary-text">{new Date(change.occurred_at).toLocaleString()}</time></div>
        <p>{change.summary}</p>
        {(change.previous_value_json !== null || change.new_value_json !== null) && <div className="change-values"><span>{display(change.previous_value_json)}</span><b aria-hidden="true">→</b><span>{display(change.new_value_json)}</span></div>}
        <div className="change-meta"><span>{change.source_name || "Atlas"}</span>{change.predicate && <span>{change.predicate}</span>}{change.entity_type === "asset" && change.entity_id && <Link className="card-link" href={`/assets/${change.entity_id}`}>View asset →</Link>}</div>
      </article>)}
    </section>}
    {!loading && result.total > PAGE_SIZE && <div className="pagination"><button className="button button-secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} type="button">Previous</button><span>{offset + 1}–{Math.min(offset + PAGE_SIZE, result.total)} of {result.total}</span><button className="button button-secondary" disabled={offset + PAGE_SIZE >= result.total} onClick={() => setOffset(offset + PAGE_SIZE)} type="button">Next</button></div>}
  </>;
}
