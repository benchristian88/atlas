"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { FilterToolbar } from "../../components/filter-toolbar";
import { PageHeader } from "../../components/page-header";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";
import {
  KNOWLEDGE_GAP_REQUIREMENT_LEVELS,
  KNOWLEDGE_GAP_SEVERITIES,
  KNOWLEDGE_GAP_STATUSES,
  knowledgeGapFiltersHref,
  parseKnowledgeGapFilters,
} from "../../lib/knowledge-gap-filters.mjs";

const PAGE_SIZE = 25;

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

function mergeOptions(...groups) {
  return Array.from(
    new Map(groups.flat().filter((item) => item?.id).map((item) => [item.id, item])),
    ([, item]) => item,
  ).sort((left, right) => left.name.localeCompare(right.name));
}

function taxonomyLabel(value) {
  return value.replaceAll("_", " ");
}

export default function KnowledgeGapsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { hasPermission } = useAuth();
  const workspace = useWorkspaceContext();
  const canView = hasPermission("knowledge_gaps.view");
  const canViewAssetTypes = hasPermission("asset_types.view");
  const canViewRequirements = hasPermission("knowledge_requirements.view");
  const canViewUsers = hasPermission("users.view");
  const filters = useMemo(() => parseKnowledgeGapFilters(searchParams, PAGE_SIZE), [searchParams]);
  const dataFilterKey = knowledgeGapFiltersHref({ ...filters, offset: 0 });
  const [items, setItems] = useState([]);
  const [filterOptions, setFilterOptions] = useState({ assetTypes: [], requirements: [], users: [] });
  const [loading, setLoading] = useState(true);
  const [loadedKey, setLoadedKey] = useState("");
  const [deciding, setDeciding] = useState("");
  const [error, setError] = useState("");
  const requestId = useRef(0);

  const load = useCallback(async () => {
    if (!canView) return;
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError("");
    const parameters = new URLSearchParams({ limit: "500" });
    if (filters.assetTypeId) parameters.set("asset_type_id", filters.assetTypeId);
    if (filters.requirementId) parameters.set("requirement_id", filters.requirementId);
    if (filters.severity) parameters.set("severity", filters.severity);
    if (filters.requirementLevel) parameters.set("requirement_level", filters.requirementLevel);
    if (filters.status) parameters.set("status", filters.status);
    if (filters.assignedUserId) parameters.set("assigned_user_id", filters.assignedUserId);
    if (filters.minimumAgeDays !== "") parameters.set("minimum_age_days", filters.minimumAgeDays);
    try {
      const gaps = await apiRequest(`/knowledge-gaps?${parameters}`);
      if (requestId.current !== currentRequest) return;
      setItems(gaps);
      setLoadedKey(dataFilterKey);
    } catch (requestError) {
      if (requestId.current !== currentRequest) return;
      setItems([]);
      setLoadedKey(dataFilterKey);
      setError(requestError.message || "Atlas could not load knowledge gaps.");
    } finally {
      if (requestId.current === currentRequest) setLoading(false);
    }
  }, [canView, dataFilterKey, filters.assetTypeId, filters.assignedUserId, filters.minimumAgeDays, filters.requirementId, filters.requirementLevel, filters.severity, filters.status, workspace.reloadKey]);

  useEffect(() => {
    load();
    return () => { requestId.current += 1; };
  }, [load]);

  useEffect(() => {
    if (!canView) return undefined;
    let active = true;
    async function loadOptions() {
      const [gaps, assetTypes, users] = await Promise.all([
        apiRequest("/knowledge-gaps?limit=500").catch(() => []),
        canViewAssetTypes ? apiRequest("/asset-types?active_only=true").catch(() => []) : Promise.resolve([]),
        canViewUsers ? apiRequest("/users?limit=500").catch(() => []) : Promise.resolve([]),
      ]);
      const fallback = optionsFromGaps(gaps);
      let requirements = [];
      if (canViewRequirements && assetTypes.length) {
        const responses = await Promise.all(
          assetTypes.map((assetType) => apiRequest(`/asset-types/${assetType.id}/knowledge-requirements`).catch(() => [])),
        );
        requirements = responses.flat().map((item) => ({ id: item.id, name: item.name }));
      }
      if (!active) return;
      setFilterOptions({
        assetTypes: mergeOptions(fallback.assetTypes, assetTypes.map((item) => ({ id: item.id, name: item.name }))),
        requirements: mergeOptions(fallback.requirements, requirements),
        users: mergeOptions(fallback.users, users.map((item) => ({ id: item.id, name: item.display_name || item.email }))),
      });
    }
    loadOptions();
    return () => { active = false; };
  }, [canView, canViewAssetTypes, canViewRequirements, canViewUsers, workspace.reloadKey]);

  const visibleItems = useMemo(
    () => items.slice(filters.offset, filters.offset + PAGE_SIZE),
    [filters.offset, items],
  );

  if (!canView) return <AccessDenied />;

  function updateFilters(patch) {
    router.push(knowledgeGapFiltersHref({ ...filters, ...patch, offset: patch.offset ?? 0 }));
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

  const activeFilterCount = [
    filters.assetTypeId,
    filters.requirementId,
    filters.severity,
    filters.requirementLevel,
    filters.status,
    filters.assignedUserId,
    filters.minimumAgeDays,
  ].filter((value) => value !== "").length;
  const ready = loadedKey === dataFilterKey;
  const criticalCount = items.filter((item) => item.severity === "critical").length;

  return <>
    <PageHeader eyebrow="Operations" title="Knowledge Gaps" description="Complete missing, stale or insufficient knowledge required for trusted operations, topology and recovery." />
    <FilterToolbar className="knowledge-gaps-toolbar" gridClassName="knowledge-gaps-filter-grid" onSubmit={(event) => event.preventDefault()} actions={<><span className="secondary-text">{activeFilterCount ? `${activeFilterCount} active filter${activeFilterCount === 1 ? "" : "s"}` : "Default view"}</span><button className="text-button" disabled={activeFilterCount === 0} onClick={() => router.push("/knowledge-gaps")} type="button">Reset filters</button></>}>
      <label className="field"><span>Asset type</span><select onChange={(event) => updateFilters({ assetTypeId: event.target.value })} value={filters.assetTypeId}><option value="">All types</option>{filterOptions.assetTypes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label className="field"><span>Requirement</span><select onChange={(event) => updateFilters({ requirementId: event.target.value })} value={filters.requirementId}><option value="">All requirements</option>{filterOptions.requirements.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label className="field"><span>Severity</span><select onChange={(event) => updateFilters({ severity: event.target.value })} value={filters.severity}><option value="">All severities</option>{KNOWLEDGE_GAP_SEVERITIES.map((item) => <option key={item} value={item}>{taxonomyLabel(item)}</option>)}</select></label>
      <label className="field"><span>Requirement level</span><select onChange={(event) => updateFilters({ requirementLevel: event.target.value })} value={filters.requirementLevel}><option value="">All levels</option>{KNOWLEDGE_GAP_REQUIREMENT_LEVELS.map((item) => <option key={item} value={item}>{taxonomyLabel(item)}</option>)}</select></label>
      <label className="field"><span>Status</span><select onChange={(event) => updateFilters({ status: event.target.value })} value={filters.status}><option value="">Active gaps</option>{KNOWLEDGE_GAP_STATUSES.map((item) => <option key={item} value={item}>{taxonomyLabel(item)}</option>)}</select></label>
      <label className="field"><span>Assigned user</span><select onChange={(event) => updateFilters({ assignedUserId: event.target.value })} value={filters.assignedUserId}><option value="">Anyone</option>{filterOptions.users.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label className="field"><span>Minimum age (days)</span><input inputMode="numeric" min="0" onChange={(event) => updateFilters({ minimumAgeDays: event.target.value })} placeholder="Any age" type="number" value={filters.minimumAgeDays} /></label>
    </FilterToolbar>
    {ready && error && <div className="error-banner" role="alert">{error}</div>}
    {!ready || loading ? <div className="status-banner" role="status">Loading knowledge gaps…</div> : <>
      <div className="timeline-summary">{items.length} knowledge gap{items.length === 1 ? "" : "s"}{criticalCount ? ` · ${criticalCount} critical` : ""}</div>
      <section className="knowledge-list">
      {visibleItems.length === 0 ? <div className="empty-state detail-card"><p>No knowledge gaps match the current filters.</p>{activeFilterCount > 0 && <button className="text-button" onClick={() => router.push("/knowledge-gaps")} type="button">Reset filters</button>}</div> : visibleItems.map((item) => <article className="detail-card reconciliation-card" key={item.id}>
        <div className="reconciliation-heading"><div><p className="eyebrow">{item.severity} · {item.requirement_level}{item.asset_type_name ? ` · ${item.asset_type_name}` : ""}</p><h2>{item.entity_name || "Asset"}</h2></div><span className="secondary-text">{item.status.replaceAll("_", " ")}</span></div>
        <h3>{item.requirement_name || "Knowledge requirement"}</h3>
        <p>{item.summary}</p>
        <p className="secondary-text">First detected {new Date(item.first_detected_at).toLocaleString()} · evaluated {new Date(item.last_evaluated_at).toLocaleString()}{item.assigned_to_name ? ` · assigned to ${item.assigned_to_name}` : ""}</p>
        {item.remediation_hint && <p className="secondary-text">Next step: {item.remediation_hint}</p>}
        <div className="form-actions"><Link className="button button-secondary" href={`/assets/${item.entity_id}`}>Open asset</Link>{hasPermission("assets.edit") && <Link className="button button-secondary" href={`/assets/${item.entity_id}/edit`}>Provide information</Link>}{hasPermission("knowledge_gaps.defer") && item.status !== "exception" && <button className="button button-secondary" disabled={deciding === item.id} onClick={() => gapAction(item, "defer")} type="button">Defer</button>}{hasPermission("knowledge_gaps.exception") && item.status !== "exception" && <button className="button button-primary" disabled={deciding === item.id} onClick={() => gapAction(item, "exception")} type="button">Record exception</button>}{hasPermission("knowledge_gaps.exception") && item.status === "exception" && <button className="button button-primary" disabled={deciding === item.id} onClick={() => reopen(item)} type="button">Reopen</button>}</div>
      </article>)}
      </section>
    </>}
    {ready && !loading && items.length > PAGE_SIZE && <div className="pagination"><button className="button button-secondary" disabled={filters.offset === 0} onClick={() => updateFilters({ offset: Math.max(0, filters.offset - PAGE_SIZE) })} type="button">Previous</button><span>{filters.offset + 1}–{Math.min(filters.offset + PAGE_SIZE, items.length)} of {items.length}</span><button className="button button-secondary" disabled={filters.offset + PAGE_SIZE >= items.length} onClick={() => updateFilters({ offset: filters.offset + PAGE_SIZE })} type="button">Next</button></div>}
  </>;
}
