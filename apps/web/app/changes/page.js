"use client";

import { Button } from "../../components/button";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { FilterToolbar } from "../../components/filter-toolbar";
import { PageHeader } from "../../components/page-header";
import { StatusBadge } from "../../components/status-badge";
import { TimelineEvent } from "../../components/timeline-event";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";
import {
  CHANGE_ENTITY_TYPES,
  CHANGE_TYPES,
  changeFiltersHref,
  parseChangeFilters,
} from "../../lib/change-filters.mjs";

const PAGE_SIZE = 30;

function fullValue(value) {
  if (value === null || value === undefined) return "—";
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function compactValue(value) {
  const rendered = fullValue(value).replaceAll("\n", " ");
  return rendered.length > 100 ? `${rendered.slice(0, 97)}…` : rendered;
}

function taxonomyLabel(value) {
  return (value || "unknown").replaceAll("_", " ");
}

function dateKey(value) {
  const date = new Date(value);
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

function dateHeading(value) {
  const date = new Date(value);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (dateKey(date) === dateKey(today)) return "Today";
  if (dateKey(date) === dateKey(yesterday)) return "Yesterday";
  return date.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

function groupChanges(items) {
  const groups = [];
  for (const item of items) {
    const key = dateKey(item.occurred_at);
    let group = groups.at(-1);
    if (!group || group.key !== key) {
      group = { key, label: dateHeading(item.occurred_at), items: [] };
      groups.push(group);
    }
    group.items.push(item);
  }
  return groups;
}

export default function ChangesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { hasPermission } = useAuth();
  const workspace = useWorkspaceContext();
  const filters = useMemo(() => parseChangeFilters(searchParams, PAGE_SIZE), [searchParams]);
  const [result, setResult] = useState({ items: [], total: 0, limit: PAGE_SIZE, offset: 0 });
  const [sources, setSources] = useState([]);
  const [searchDraft, setSearchDraft] = useState(filters.search);
  const [loading, setLoading] = useState(true);
  const [loadedKey, setLoadedKey] = useState("");
  const [error, setError] = useState("");
  const requestId = useRef(0);
  const canView = hasPermission("changes.view");
  const canViewSources = hasPermission("integrations.view");
  const filterKey = changeFiltersHref(filters);

  useEffect(() => { setSearchDraft(filters.search); }, [filters.search]);

  useEffect(() => {
    if (!canViewSources) return undefined;
    let active = true;
    apiRequest("/data-sources")
      .then((records) => { if (active) setSources(records); })
      .catch(() => { if (active) setSources([]); });
    return () => { active = false; };
  }, [canViewSources, workspace.reloadKey]);

  const load = useCallback(async () => {
    if (!canView) return;
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError("");
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(filters.offset) });
    if (filters.changeType) params.set("change_type", filters.changeType);
    if (filters.entityType) params.set("entity_type", filters.entityType);
    if (filters.source) params.set("data_source_id", filters.source);
    if (filters.period) params.set("date_from", new Date(Date.now() - Number(filters.period) * 86400000).toISOString());
    if (filters.attentionOnly) params.set("attention_required", "true");
    if (filters.search) params.set("search", filters.search);
    try {
      const response = await apiRequest(`/changes?${params}`);
      if (requestId.current !== currentRequest) return;
      setResult(response);
      setLoadedKey(filterKey);
    } catch (requestError) {
      if (requestId.current !== currentRequest) return;
      setResult({ items: [], total: 0, limit: PAGE_SIZE, offset: filters.offset });
      setLoadedKey(filterKey);
      setError(requestError.message || "Atlas could not load knowledge changes.");
    } finally {
      if (requestId.current === currentRequest) setLoading(false);
    }
  }, [canView, filterKey, filters.attentionOnly, filters.changeType, filters.entityType, filters.offset, filters.period, filters.search, filters.source, workspace.reloadKey]);

  useEffect(() => {
    load();
    return () => { requestId.current += 1; };
  }, [load]);

  if (!canView) return <AccessDenied />;

  function updateFilters(patch) {
    router.push(changeFiltersHref({ ...filters, ...patch, offset: patch.offset ?? 0 }));
  }

  const activeFilterCount = [filters.changeType, filters.entityType, filters.source, filters.attentionOnly, filters.search, filters.period !== "30"].filter(Boolean).length;
  const ready = loadedKey === filterKey;
  const groupedChanges = groupChanges(result.items);

  return <>
    <PageHeader eyebrow="Knowledge" title="Changes" description="Meaningful knowledge changes across Atlas. Security and access activity remains in Audit." />
    <FilterToolbar gridClassName="changes-filter-grid" onSubmit={(event) => { event.preventDefault(); updateFilters({ search: searchDraft.trim() }); }} actions={<>
      <label className="checkbox-field"><input checked={filters.attentionOnly} onChange={(event) => updateFilters({ attentionOnly: event.target.checked })} type="checkbox" /><span>Needs attention</span></label><span className="secondary-text">{activeFilterCount ? `${activeFilterCount} active filter${activeFilterCount === 1 ? "" : "s"}` : "Default view"}</span><Button variant="secondary" type="submit">Apply search</Button><button className="text-button" disabled={activeFilterCount === 0} onClick={() => router.push("/changes")} type="button">Reset filters</button>
    </>}>
        <label className="field changes-period-filter"><span>Date period</span><select onChange={(event) => updateFilters({ period: event.target.value })} value={filters.period}><option value="7">Last 7 days</option><option value="30">Last 30 days</option><option value="90">Last 90 days</option><option value="">All time</option></select></label>
        <label className="field"><span>Change type</span><select onChange={(event) => updateFilters({ changeType: event.target.value })} value={filters.changeType}><option value="">All changes</option>{CHANGE_TYPES.map((item) => <option key={item} value={item}>{taxonomyLabel(item)}</option>)}</select></label>
        <label className="field"><span>Entity type</span><select onChange={(event) => updateFilters({ entityType: event.target.value })} value={filters.entityType}><option value="">All entities</option>{CHANGE_ENTITY_TYPES.map((item) => <option key={item} value={item}>{taxonomyLabel(item)}</option>)}</select></label>
        {canViewSources && <label className="field"><span>Source</span><select onChange={(event) => updateFilters({ source: event.target.value })} value={filters.source}><option value="">All sources</option>{sources.map((source) => <option key={source.id} value={source.id}>{source.name}</option>)}</select></label>}
        <label className="field changes-search-filter"><span>Search</span><input onChange={(event) => setSearchDraft(event.target.value)} placeholder="Entity or summary" value={searchDraft} /></label>
    </FilterToolbar>
    {ready && error && <div className="error-banner" role="alert">{error}</div>}
    {!ready || loading ? <div className="status-banner" role="status">Loading changes…</div> : <>
      <div className="timeline-summary">{result.total} meaningful change{result.total === 1 ? "" : "s"}</div>
      {result.items.length === 0 ? <div className="empty-state detail-card">No meaningful changes match these filters.</div> : <section className="change-timeline" aria-label="Meaningful changes timeline">
        {groupedChanges.map((group) => <section className="change-day" key={group.key}><h2>{group.label}</h2><div className="timeline change-timeline-list">{group.items.map((change) => <TimelineEvent key={change.id}>
          <div className="timeline-event-heading"><strong>{change.summary}</strong><div className="badge-stack">{change.attention_required && <StatusBadge status="Needs review" />}{change.truth_classification && <StatusBadge status={taxonomyLabel(change.truth_classification)} />}</div></div>
          {(change.previous_value !== null || change.new_value !== null) && <div className="change-value-summary" title={`${fullValue(change.previous_value)} → ${fullValue(change.new_value)}`}><code>{compactValue(change.previous_value)}</code><span aria-hidden="true">→</span><code>{compactValue(change.new_value)}</code></div>}
          {change.change_type === "entity_no_longer_observed" && change.previous_value?.last_observed_at && <p className="timeline-event-note">Last observed: {new Date(change.previous_value.last_observed_at).toLocaleString()}</p>}
          <div className="timeline-event-meta"><span>{taxonomyLabel(change.change_type)}</span><span>{taxonomyLabel(change.entity_type)} · {change.entity_name_snapshot}</span><span>{change.source_name || "Atlas"}</span>{change.actor_display_name && <span>Actor: {change.actor_display_name}</span>}<time>{new Date(change.occurred_at).toLocaleString()}</time></div>
          {(change.previous_value !== null || change.new_value !== null || change.predicate || change.discovery_run_status || change.reconciliation_status) && <details className="timeline-event-details"><summary>Details</summary>{(change.previous_value !== null || change.new_value !== null) && <div className="change-values"><div><span>Previous</span><pre>{fullValue(change.previous_value)}</pre></div><b aria-hidden="true">→</b><div><span>New</span><pre>{fullValue(change.new_value)}</pre></div></div>}<div className="timeline-detail-meta"><span>Change type: {taxonomyLabel(change.change_type)}</span>{change.predicate && <span>Predicate: {taxonomyLabel(change.predicate)}</span>}{change.truth_classification && <span>Truth: {taxonomyLabel(change.truth_classification)}</span>}{change.discovery_run_status && <span>Discovery run: {taxonomyLabel(change.discovery_run_status)}</span>}{change.reconciliation_status && <span>Reconciliation: {taxonomyLabel(change.reconciliation_status)}</span>}</div></details>}
          <div className="timeline-event-actions">{change.links?.asset && <Link className="card-link" href={change.links.asset}>Open asset →</Link>}{change.links?.service && <Link className="card-link" href={change.links.service}>Open Service →</Link>}{change.links?.business_function && <Link className="card-link" href={change.links.business_function}>Open Business Function →</Link>}{change.links?.reconciliation && <Link className="card-link" href={change.links.reconciliation}>Review reconciliation →</Link>}{change.links?.discovery_run && <Link className="card-link" href={change.links.discovery_run}>Open discovery run →</Link>}</div>
        </TimelineEvent>)}</div></section>)}
      </section>}
    </>}
    {ready && !loading && result.total > PAGE_SIZE && <div className="pagination"><Button variant="secondary" disabled={filters.offset === 0} onClick={() => updateFilters({ offset: Math.max(0, filters.offset - PAGE_SIZE) })} type="button">Previous</Button><span>{filters.offset + 1}–{Math.min(filters.offset + PAGE_SIZE, result.total)} of {result.total}</span><Button variant="secondary" disabled={filters.offset + PAGE_SIZE >= result.total} onClick={() => updateFilters({ offset: filters.offset + PAGE_SIZE })} type="button">Next</Button></div>}
  </>;
}
