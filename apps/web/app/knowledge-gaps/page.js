"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { FilterToolbar } from "../../components/filter-toolbar";
import { PageHeader } from "../../components/page-header";
import { StatusBadge } from "../../components/status-badge";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";
import {
  KNOWLEDGE_GAP_REQUIREMENT_LEVELS,
  KNOWLEDGE_GAP_ENTITY_TYPES,
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

function formatDate(value) {
  if (!value) return "Unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unavailable" : date.toLocaleString();
}

function KnowledgeGapCard({ canDefer, canEdit, canExcept, deciding, item, onAction, onReopen }) {
  const entityLabel = item.entity_type === "service" ? "Service" : "Asset";
  const entityName = item.entity_name || `Unavailable ${entityLabel.toLowerCase()}`;
  const requirementName = item.requirement_name || "Knowledge requirement unavailable";
  const hasAssetLink = Boolean(item.entity_id);

  return <article className={`detail-card knowledge-gap-card knowledge-gap-severity-${item.severity || "unknown"}`} aria-labelledby={`knowledge-gap-${item.id}`}>
    <header className="knowledge-gap-meta">
      <div className="badge-stack">
        <StatusBadge status={taxonomyLabel(item.severity || "unknown")} />
        <StatusBadge status={taxonomyLabel(item.requirement_level || "unknown")} />
        {item.asset_type_name && <span className="knowledge-gap-type-badge">{item.asset_type_name}</span>}
      </div>
      <StatusBadge status={taxonomyLabel(item.status || "unknown")} />
    </header>
    <div className="knowledge-gap-card-body">
      <div className="knowledge-gap-main">
        <section className="knowledge-gap-asset">
          <span className="knowledge-gap-section-label">{entityLabel} name</span>
          <h2>{entityName}</h2>
        </section>
        <section className="knowledge-gap-missing">
          <span className="knowledge-gap-section-label">Missing information</span>
          <h3 id={`knowledge-gap-${item.id}`}>{requirementName}</h3>
          <div className="knowledge-gap-details">
            <span className="knowledge-gap-section-label">Details</span>
            <p>{item.summary || "No additional details are available for this knowledge gap."}</p>
          </div>
        </section>
      </div>
      <aside className="knowledge-gap-support" aria-label={`Supporting information for ${entityName}`}>
        <section>
          <h4 className="knowledge-gap-section-label">Dates</h4>
          <dl className="knowledge-gap-dates">
            <div><dt>First detected</dt><dd>{formatDate(item.first_detected_at)}</dd></div>
            <div><dt>Last evaluated</dt><dd>{formatDate(item.last_evaluated_at)}</dd></div>
          </dl>
        </section>
        {item.assigned_to_name && <section><h4 className="knowledge-gap-section-label">Assigned to</h4><p className="knowledge-gap-supporting-value">{item.assigned_to_name}</p></section>}
        {item.remediation_hint && <section className="knowledge-gap-next-step"><h4 className="knowledge-gap-section-label">Next step</h4><p>{item.remediation_hint}</p></section>}
      </aside>
    </div>
    <footer className="knowledge-gap-actions">
      <span className="knowledge-gap-section-label">Actions</span>
      <div className="knowledge-gap-action-row">
        {hasAssetLink ? <Link className="button button-secondary" href={`/${item.entity_type === "service" ? "services" : "assets"}/${item.entity_id}`}>Open {entityLabel.toLowerCase()}</Link> : <span className="secondary-text">{entityLabel} link unavailable</span>}
        {hasAssetLink && canEdit && <Link className="button button-primary" href={`/${item.entity_type === "service" ? "services" : "assets"}/${item.entity_id}/edit`}>Provide information</Link>}
        {canDefer && item.status !== "exception" && <button className="button button-secondary" disabled={deciding === item.id} onClick={() => onAction(item, "defer")} type="button">Defer</button>}
        {canExcept && item.status !== "exception" && <button className="button button-secondary" disabled={deciding === item.id} onClick={() => onAction(item, "exception")} type="button">Record exception</button>}
        {canExcept && item.status === "exception" && <button className="button button-secondary" disabled={deciding === item.id} onClick={() => onReopen(item)} type="button">Reopen</button>}
      </div>
    </footer>
  </article>;
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
    if (filters.entityType) parameters.set("entity_type", filters.entityType);
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
  }, [canView, dataFilterKey, filters.assetTypeId, filters.assignedUserId, filters.entityType, filters.minimumAgeDays, filters.requirementId, filters.requirementLevel, filters.severity, filters.status, workspace.reloadKey]);

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
    filters.entityType,
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
      <label className="field"><span>Entity type</span><select onChange={(event) => updateFilters({ entityType: event.target.value, assetTypeId: event.target.value === "service" ? "" : filters.assetTypeId })} value={filters.entityType}><option value="">Assets and Services</option>{KNOWLEDGE_GAP_ENTITY_TYPES.map((item) => <option key={item} value={item}>{taxonomyLabel(item)}</option>)}</select></label>
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
      {visibleItems.length === 0 ? <div className="empty-state detail-card"><p>No knowledge gaps match the current filters.</p>{activeFilterCount > 0 && <button className="text-button" onClick={() => router.push("/knowledge-gaps")} type="button">Reset filters</button>}</div> : visibleItems.map((item) => <KnowledgeGapCard canDefer={hasPermission("knowledge_gaps.defer")} canEdit={hasPermission(item.entity_type === "service" ? "services.edit" : "assets.edit")} canExcept={hasPermission("knowledge_gaps.exception")} deciding={deciding} item={item} key={item.id} onAction={gapAction} onReopen={reopen} />)}
      </section>
    </>}
    {ready && !loading && items.length > PAGE_SIZE && <div className="pagination"><button className="button button-secondary" disabled={filters.offset === 0} onClick={() => updateFilters({ offset: Math.max(0, filters.offset - PAGE_SIZE) })} type="button">Previous</button><span>{filters.offset + 1}–{Math.min(filters.offset + PAGE_SIZE, items.length)} of {items.length}</span><button className="button button-secondary" disabled={filters.offset + PAGE_SIZE >= items.length} onClick={() => updateFilters({ offset: filters.offset + PAGE_SIZE })} type="button">Next</button></div>}
  </>;
}
