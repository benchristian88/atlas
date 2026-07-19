"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";

const PAGE_SIZE = 25;
const EMPTY_FILTERS = {
  asset_type_id: "",
  requirement_id: "",
  severity: "",
  requirement_level: "",
  status: "",
  assigned_user_id: "",
  minimum_age_days: "",
};

function optionsFromGaps(gaps) {
  return {
    assetTypes: Array.from(
      new Map(gaps.filter((gap) => gap.asset_type_id_snapshot).map((gap) => [gap.asset_type_id_snapshot, gap.asset_type_name || "Unavailable"])),
      ([id, name]) => ({ id, name }),
    ),
    requirements: Array.from(
      new Map(gaps.map((gap) => [gap.requirement_definition_id, gap.requirement_name || "Unavailable"])),
      ([id, name]) => ({ id, name }),
    ),
    users: Array.from(
      new Map(gaps.filter((gap) => gap.assigned_to_user_id).map((gap) => [gap.assigned_to_user_id, gap.assigned_to_name || "Unavailable"])),
      ([id, name]) => ({ id, name }),
    ),
  };
}

export default function KnowledgeGapsPage() {
  const { hasPermission } = useAuth();
  const workspace = useWorkspaceContext();
  const canView = hasPermission("knowledge_gaps.view");
  const [items, setItems] = useState([]);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [filterOptions, setFilterOptions] = useState({ assetTypes: [], requirements: [], users: [] });
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [deciding, setDeciding] = useState("");
  const [error, setError] = useState("");
  const requestId = useRef(0);

  const load = useCallback(async () => {
    if (!canView) return;
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError("");
    const parameters = new URLSearchParams({ limit: "500" });
    for (const [key, filterValue] of Object.entries(filters)) {
      if (filterValue !== "") parameters.set(key, filterValue);
    }
    try {
      const gaps = await apiRequest(`/knowledge-gaps?${parameters}`);
      if (requestId.current !== currentRequest) return;
      setItems(gaps);
    } catch (requestError) {
      if (requestId.current !== currentRequest) return;
      setItems([]);
      setError(requestError.message || "Atlas could not load knowledge gaps.");
    } finally {
      if (requestId.current === currentRequest) setLoading(false);
    }
  }, [canView, filters, workspace.reloadKey]);

  useEffect(() => {
    load();
    return () => { requestId.current += 1; };
  }, [load]);

  useEffect(() => {
    if (!canView) return undefined;
    let active = true;
    apiRequest("/knowledge-gaps?limit=500")
      .then((gaps) => { if (active) setFilterOptions(optionsFromGaps(gaps)); })
      .catch(() => { /* The main request provides the visible error state. */ });
    return () => { active = false; };
  }, [canView, workspace.reloadKey]);

  const visibleItems = useMemo(
    () => items.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE),
    [items, page],
  );

  if (!canView) return <AccessDenied />;

  function updateFilter(key, filterValue) {
    setPage(0);
    setFilters((current) => ({ ...current, [key]: filterValue }));
  }

  async function gapAction(item, action) {
    const reason = window.prompt(action === "defer" ? "Why is this gap being deferred?" : "Why is this exception appropriate?");
    if (!reason?.trim()) return;
    const deferDate = action === "defer" ? window.prompt("Defer until (YYYY-MM-DD)") : null;
    if (action === "defer" && (!deferDate || Number.isNaN(new Date(deferDate).getTime()))) {
      setError("Enter a valid deferral date.");
      return;
    }
    setDeciding(item.id);
    setError("");
    try {
      const body = action === "defer"
        ? { reason: reason.trim(), deferred_until: new Date(deferDate).toISOString() }
        : { reason: reason.trim(), expires_at: null };
      await apiRequest(`/knowledge-gaps/${item.id}/${action}`, { method: "POST", body: JSON.stringify(body) });
      await load();
    } catch (requestError) {
      setError(requestError.message || "Atlas could not update this knowledge gap.");
    } finally {
      setDeciding("");
    }
  }

  async function reopen(item) {
    setDeciding(item.id);
    setError("");
    try {
      await apiRequest(`/knowledge-gaps/${item.id}/reopen`, {
        method: "POST",
        body: JSON.stringify({ reason: "Reopened from Knowledge Gaps" }),
      });
      await load();
    } catch (requestError) {
      setError(requestError.message || "Atlas could not reopen this knowledge gap.");
    } finally {
      setDeciding("");
    }
  }

  return <>
    <PageHeader eyebrow="Operations" title="Knowledge Gaps" description="Complete missing, stale or insufficient knowledge required for trusted operations, topology and recovery." />
    <div className="filter-bar">
      <label className="field"><span>Asset type</span><select onChange={(event) => updateFilter("asset_type_id", event.target.value)} value={filters.asset_type_id}><option value="">All types</option>{filterOptions.assetTypes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label className="field"><span>Requirement</span><select onChange={(event) => updateFilter("requirement_id", event.target.value)} value={filters.requirement_id}><option value="">All requirements</option>{filterOptions.requirements.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label className="field"><span>Severity</span><select onChange={(event) => updateFilter("severity", event.target.value)} value={filters.severity}><option value="">All severities</option>{["critical", "high", "medium", "low"].map((item) => <option key={item}>{item}</option>)}</select></label>
      <label className="field"><span>Requirement level</span><select onChange={(event) => updateFilter("requirement_level", event.target.value)} value={filters.requirement_level}><option value="">All levels</option>{["required", "conditional", "recommended"].map((item) => <option key={item}>{item}</option>)}</select></label>
      <label className="field"><span>Status</span><select onChange={(event) => updateFilter("status", event.target.value)} value={filters.status}><option value="">Active</option>{["open", "deferred", "exception", "resolved", "superseded"].map((item) => <option key={item}>{item}</option>)}</select></label>
      <label className="field"><span>Assigned user</span><select onChange={(event) => updateFilter("assigned_user_id", event.target.value)} value={filters.assigned_user_id}><option value="">Anyone</option>{filterOptions.users.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label className="field"><span>Minimum age (days)</span><input min="0" onChange={(event) => updateFilter("minimum_age_days", event.target.value)} type="number" value={filters.minimum_age_days} /></label>
      <button className="text-button" onClick={() => { setFilters(EMPTY_FILTERS); setPage(0); }} type="button">Clear filters</button>
    </div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {loading ? <div className="status-banner" role="status">Loading knowledge gaps…</div> : <section className="knowledge-list">
      {visibleItems.length === 0 ? <div className="empty-state detail-card">No knowledge gaps match these filters.</div> : visibleItems.map((item) => <article className="detail-card reconciliation-card" key={item.id}>
        <div className="reconciliation-heading"><div><p className="eyebrow">{item.severity} · {item.requirement_level}{item.asset_type_name ? ` · ${item.asset_type_name}` : ""}</p><h2>{item.entity_name || "Asset"}</h2></div><span className="secondary-text">{item.status.replaceAll("_", " ")}</span></div>
        <h3>{item.requirement_name || "Knowledge requirement"}</h3>
        <p>{item.summary}</p>
        <p className="secondary-text">First detected {new Date(item.first_detected_at).toLocaleString()} · evaluated {new Date(item.last_evaluated_at).toLocaleString()}{item.assigned_to_name ? ` · assigned to ${item.assigned_to_name}` : ""}</p>
        {item.remediation_hint && <p className="secondary-text">Next step: {item.remediation_hint}</p>}
        <div className="form-actions"><Link className="button button-secondary" href={`/assets/${item.entity_id}`}>Open asset</Link>{hasPermission("assets.edit") && <Link className="button button-secondary" href={`/assets/${item.entity_id}/edit`}>Provide information</Link>}{hasPermission("knowledge_gaps.defer") && item.status !== "exception" && <button className="button button-secondary" disabled={deciding === item.id} onClick={() => gapAction(item, "defer")} type="button">Defer</button>}{hasPermission("knowledge_gaps.exception") && item.status !== "exception" && <button className="button button-primary" disabled={deciding === item.id} onClick={() => gapAction(item, "exception")} type="button">Record exception</button>}{hasPermission("knowledge_gaps.exception") && item.status === "exception" && <button className="button button-primary" disabled={deciding === item.id} onClick={() => reopen(item)} type="button">Reopen</button>}</div>
      </article>)}
    </section>}
    {!loading && items.length > PAGE_SIZE && <div className="pagination"><button className="button button-secondary" disabled={page === 0} onClick={() => setPage((current) => Math.max(0, current - 1))} type="button">Previous</button><span>{page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, items.length)} of {items.length}</span><button className="button button-secondary" disabled={(page + 1) * PAGE_SIZE >= items.length} onClick={() => setPage((current) => current + 1)} type="button">Next</button></div>}
  </>;
}
