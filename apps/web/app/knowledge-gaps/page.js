"use client";

import { Button } from "../../components/button";

import Link from "next/link";
import { useEffect, useId, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { FilterPopover } from "../../components/filter-popover";
import { FilterToolbar } from "../../components/filter-toolbar";
import { PageHeader } from "../../components/page-header";
import { StatusBadge } from "../../components/status-badge";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";
import { getRequestContext } from "../../lib/context-store";
import {
  DASHBOARD_GAP_LEVEL,
  DASHBOARD_GAP_STATUS,
  KNOWLEDGE_GAP_REQUIREMENT_LEVELS,
  KNOWLEDGE_GAP_ENTITY_TYPES,
  KNOWLEDGE_GAP_LIST_LIMIT,
  KNOWLEDGE_GAP_SEVERITIES,
  KNOWLEDGE_GAP_STATUSES,
  countKnowledgeGapFilters,
  knowledgeGapFiltersHref,
  knowledgeGapRequirementRequests,
  knowledgeGapRequestPath,
  parseKnowledgeGapFilters,
  resolveKnowledgeGapRequirement,
} from "../../lib/knowledge-gap-filters.mjs";

const PAGE_SIZE = 25;
const EMPTY_OPTIONS = { assetTypes: [], requirements: [], users: [] };
const REQUIREMENT_FILTER_LABELS = { [DASHBOARD_GAP_LEVEL]: "Required or conditional" };
const STATUS_FILTER_LABELS = { "": "Active gaps", [DASHBOARD_GAP_STATUS]: "Open or deferred" };

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
          {item.site_id === null && <span className="secondary-text">Customer-wide</span>}
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
        {canDefer && item.status !== "exception" && <Button variant="secondary" disabled={deciding === item.id} onClick={() => onAction(item, "defer")} type="button">Defer</Button>}
        {canExcept && item.status !== "exception" && <Button variant="secondary" disabled={deciding === item.id} onClick={() => onAction(item, "exception")} type="button">Record exception</Button>}
        {canExcept && item.status === "exception" && <Button variant="secondary" disabled={deciding === item.id} onClick={() => onReopen(item)} type="button">Reopen</Button>}
      </div>
    </footer>
  </article>;
}

export default function KnowledgeGapsPage() {
  const searchParams = useSearchParams();
  const { hasPermission, hasGlobalPermission } = useAuth();
  const workspace = useWorkspaceContext();
  const { customerId, siteId } = workspace;
  const canView = hasPermission("knowledge_gaps.view");
  const canViewAssetTypes = hasPermission("asset_types.view");
  const canViewProfiles = canViewAssetTypes && hasGlobalPermission("knowledge_requirements.view");
  const canViewUsers = hasPermission("users.view");
  const scopeHelpId = useId();
  const filters = useMemo(() => parseKnowledgeGapFilters(searchParams, PAGE_SIZE), [searchParams]);
  const { requirementId, includeCustomerWide } = filters;
  const scopeRequest = useMemo(() => ({
    omitContext: true,
    headers: {
      ...(customerId ? { "X-Atlas-Customer-ID": customerId } : {}),
      ...(siteId ? { "X-Atlas-Site-ID": siteId } : {}),
    },
  }), [customerId, siteId]);
  const optionsPath = knowledgeGapRequestPath({ includeCustomerWide });
  const optionsKey = `${workspace.reloadKey}:${optionsPath}`;
  const [refresh, setRefresh] = useState(0);
  const [result, setResult] = useState(null);
  const [loadedOptions, setLoadedOptions] = useState(null);
  const [checkedRequirement, setCheckedRequirement] = useState(null);
  const [clearedRequirementAt, setClearedRequirementAt] = useState("");
  const [deciding, setDeciding] = useState("");
  const [actionError, setActionError] = useState(null);

  const scopedOptions = loadedOptions?.key === optionsKey ? loadedOptions : null;
  const filterOptions = scopedOptions || EMPTY_OPTIONS;
  const listedRequirement = filterOptions.requirements.find((option) => option.id === requirementId);
  const checkRequirement = Boolean(scopedOptions && requirementId && !listedRequirement);
  const verifiedRequirement = checkRequirement && checkedRequirement?.options === scopedOptions &&
    checkedRequirement.id === requirementId ? checkedRequirement : null;
  const requirementPending = Boolean(requirementId && !listedRequirement && !verifiedRequirement);
  const requirementUnavailable = Boolean(verifiedRequirement?.unavailable);
  const listPath = requirementPending || requirementUnavailable ? "" : knowledgeGapRequestPath(filters);
  const dataKey = `${workspace.reloadKey}:${listPath}:${refresh}`;

  useEffect(() => {
    if (!canView || !listPath) return undefined;
    let active = true;
    async function load() {
      try {
        const items = await apiRequest(listPath, scopeRequest);
        if (active) setResult({ key: dataKey, items });
      } catch (requestError) {
        if (active) setResult({ key: dataKey, error: requestError.message || "Atlas could not load knowledge gaps." });
      }
    }
    load();
    return () => { active = false; };
  }, [canView, dataKey, listPath, scopeRequest]);

  useEffect(() => {
    if (!canView) return undefined;
    let active = true;
    setLoadedOptions(null);
    async function loadOptions() {
      const [gaps, assetTypes, users] = await Promise.all([
        apiRequest(optionsPath, scopeRequest).catch(() => []),
        canViewAssetTypes ? apiRequest("/asset-types?active_only=true").catch(() => null) : Promise.resolve([]),
        canViewUsers ? apiRequest("/users?limit=500").catch(() => []) : Promise.resolve([]),
      ]);
      const fallback = optionsFromGaps(gaps);
      let requirements = [];
      let referencesComplete = !canViewProfiles || assetTypes !== null;
      if (active && canViewProfiles && assetTypes?.length) {
        const responses = await Promise.all(
          assetTypes.map((assetType) => apiRequest(`/asset-types/${assetType.id}/knowledge-requirements`).catch(() => null)),
        );
        referencesComplete = responses.every((response) => response !== null);
        requirements = responses.filter(Boolean).flat().map((item) => ({ id: item.id, name: item.name }));
      }
      if (!active) return;
      setLoadedOptions({
        key: optionsKey,
        referencesComplete,
        assetTypes: mergeOptions(fallback.assetTypes, (assetTypes || []).map((item) => ({ id: item.id, name: item.name }))),
        requirements: mergeOptions(fallback.requirements, requirements),
        users: mergeOptions(fallback.users, users.map((item) => ({ id: item.id, name: item.display_name || item.email }))),
      });
    }
    loadOptions();
    return () => { active = false; };
  }, [canView, canViewAssetTypes, canViewProfiles, canViewUsers, optionsKey, optionsPath, scopeRequest]);

  useEffect(() => {
    if (!canView || !checkRequirement) return undefined;
    let active = true;
    // Absence from the capped options response is inconclusive. Ask the
    // scoped API about the selected requirement without the other list filters.
    Promise.allSettled(knowledgeGapRequirementRequests(requirementId, includeCustomerWide)
      .map((path) => apiRequest(path, scopeRequest))).then((responses) => {
      if (active) {
        setCheckedRequirement({
          options: scopedOptions,
          id: requirementId,
          ...resolveKnowledgeGapRequirement(responses, scopedOptions.referencesComplete),
        });
      }
    });
    return () => { active = false; };
  }, [canView, checkRequirement, requirementId, includeCustomerWide, scopeRequest, scopedOptions]);

  useEffect(() => {
    if (!canView || !requirementUnavailable) return;
    const current = getRequestContext();
    // A workspace selector or browser navigation can run before React commits
    // the next render. Only replace the entry this result was checked against.
    if (current.customerId !== customerId || current.siteId !== siteId ||
        new URLSearchParams(window.location.search).toString() !== searchParams.toString()) return;
    const href = knowledgeGapFiltersHref({ ...filters, requirementId: "", offset: 0 });
    window.history.replaceState(null, "", href);
    setClearedRequirementAt(`${workspace.reloadKey}:${href}`);
  }, [canView, requirementUnavailable, filters, customerId, siteId, searchParams, workspace.reloadKey]);

  if (!canView) return <AccessDenied />;
  const ready = Boolean(listPath) && result?.key === dataKey;
  const loadError = ready ? result.error : "";
  const error = loadError || (actionError?.key === dataKey ? actionError.message : "");
  const items = ready ? result.items || [] : [];
  const offset = Math.min(filters.offset, Math.max(0, Math.floor((items.length - 1) / PAGE_SIZE) * PAGE_SIZE));
  const visibleItems = items.slice(offset, offset + PAGE_SIZE);

  function updateFilters(patch) {
    window.history.pushState(null, "", knowledgeGapFiltersHref({ ...filters, ...patch, offset: patch.offset ?? 0 }));
  }

  async function gapAction(item, action) {
    const reason = window.prompt(action === "defer" ? "Why is this gap being deferred?" : "Why is this exception appropriate?");
    if (!reason?.trim()) return;
    const deferDate = action === "defer" ? window.prompt("Defer until (YYYY-MM-DD)") : null;
    if (action === "defer" && (!deferDate || Number.isNaN(new Date(deferDate).getTime()))) {
      setActionError({ key: dataKey, message: "Enter a valid deferral date." });
      return;
    }
    setDeciding(item.id);
    setActionError(null);
    try {
      const body = action === "defer"
        ? { reason: reason.trim(), deferred_until: new Date(deferDate).toISOString() }
        : { reason: reason.trim(), expires_at: null };
      await apiRequest(`/knowledge-gaps/${item.id}/${action}`, { method: "POST", body: JSON.stringify(body) });
      setRefresh((value) => value + 1);
    } catch (requestError) {
      setActionError({ key: dataKey, message: requestError.message || "Atlas could not update this knowledge gap." });
    } finally {
      setDeciding("");
    }
  }

  async function reopen(item) {
    setDeciding(item.id);
    setActionError(null);
    try {
      await apiRequest(`/knowledge-gaps/${item.id}/reopen`, {
        method: "POST",
        body: JSON.stringify({ reason: "Reopened from Knowledge Gaps" }),
      });
      setRefresh((value) => value + 1);
    } catch (requestError) {
      setActionError({ key: dataKey, message: requestError.message || "Atlas could not reopen this knowledge gap." });
    } finally {
      setDeciding("");
    }
  }

  const matchingFilterCount = countKnowledgeGapFilters(filters);
  const activeFilterCount = matchingFilterCount + Number(Boolean(workspace.siteId) && !filters.includeCustomerWide);
  const criticalCount = items.filter((item) => item.severity === "critical").length;
  const limitReached = items.length === KNOWLEDGE_GAP_LIST_LIMIT;
  const requirementCleared = clearedRequirementAt === `${workspace.reloadKey}:${knowledgeGapFiltersHref(filters)}`;
  const scopeLabel = workspace.siteId
    ? filters.includeCustomerWide ? "Selected Site and permitted customer-wide gaps" : "Selected Site only"
    : "All permitted gaps in this workspace";
  const requirementLabel = REQUIREMENT_FILTER_LABELS[filters.requirementLevel] || taxonomyLabel(filters.requirementLevel);
  const statusLabel = STATUS_FILTER_LABELS[filters.status] || taxonomyLabel(filters.status);
  const resetFilters = () => window.history.pushState(null, "", "/knowledge-gaps");

  return <>
    <PageHeader eyebrow="Operations" title="Knowledge Gaps" description="Complete missing, stale or insufficient knowledge required for trusted operations, topology and recovery." />
    <div className="timeline-summary">
      <FilterPopover activeCount={activeFilterCount}>
        <FilterToolbar gridClassName="knowledge-gaps-filter-grid" onSubmit={(event) => event.preventDefault()} actions={<Button disabled={activeFilterCount === 0} onClick={resetFilters}>Reset filters</Button>}>
          {workspace.siteId && <div className="knowledge-gap-scope-filter">
            <label><input aria-describedby={scopeHelpId} checked={filters.includeCustomerWide} onChange={(event) => updateFilters({ includeCustomerWide: event.target.checked })} type="checkbox" /> <strong>Include customer-wide</strong></label>
            <p className="secondary-text" id={scopeHelpId}>Show gaps from records without a Site in the selected Customer, when you have permission.</p>
          </div>}
          <label className="field"><span>Entity type</span><select onChange={(event) => updateFilters({ entityType: event.target.value, assetTypeId: event.target.value === "service" ? "" : filters.assetTypeId })} value={filters.entityType}><option value="">Assets and Services</option>{KNOWLEDGE_GAP_ENTITY_TYPES.map((item) => <option key={item} value={item}>{taxonomyLabel(item)}</option>)}</select></label>
          <label className="field"><span>Asset type</span><select onChange={(event) => updateFilters({ assetTypeId: event.target.value })} value={filters.assetTypeId}><option value="">All types</option>{filterOptions.assetTypes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label className="field"><span>Requirement</span><select onChange={(event) => updateFilters({ requirementId: event.target.value })} value={requirementId}>
            <option value="">All requirements</option>
            {requirementId && !listedRequirement && <option value={requirementId}>
              {verifiedRequirement?.option?.name || (requirementPending ? "Selected requirement (checking scope…)" : "Selected requirement (unavailable in options)")}
            </option>}
            {filterOptions.requirements.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></label>
          <label className="field"><span>Severity</span><select onChange={(event) => updateFilters({ severity: event.target.value })} value={filters.severity}><option value="">All severities</option>{KNOWLEDGE_GAP_SEVERITIES.map((item) => <option key={item} value={item}>{taxonomyLabel(item)}</option>)}</select></label>
          <label className="field"><span>Requirement level</span><select onChange={(event) => updateFilters({ requirementLevel: event.target.value })} value={filters.requirementLevel}><option value="">All levels</option><option value={DASHBOARD_GAP_LEVEL}>{REQUIREMENT_FILTER_LABELS[DASHBOARD_GAP_LEVEL]}</option>{KNOWLEDGE_GAP_REQUIREMENT_LEVELS.map((item) => <option key={item} value={item}>{taxonomyLabel(item)}</option>)}</select></label>
          <label className="field"><span>Status</span><select onChange={(event) => updateFilters({ status: event.target.value })} value={filters.status}><option value="">Active gaps</option><option value={DASHBOARD_GAP_STATUS}>{STATUS_FILTER_LABELS[DASHBOARD_GAP_STATUS]}</option>{KNOWLEDGE_GAP_STATUSES.map((item) => <option key={item} value={item}>{taxonomyLabel(item)}</option>)}</select></label>
          <label className="field"><span>Assigned user</span><select onChange={(event) => updateFilters({ assignedUserId: event.target.value })} value={filters.assignedUserId}><option value="">Anyone</option>{filterOptions.users.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label className="field"><span>Minimum age (days)</span><input inputMode="numeric" min="0" onChange={(event) => updateFilters({ minimumAgeDays: event.target.value })} placeholder="Any age" type="number" value={filters.minimumAgeDays} /></label>
        </FilterToolbar>
      </FilterPopover>
      <p>{scopeLabel} · {statusLabel}{requirementLabel && ` · ${requirementLabel}`}</p>
      {requirementCleared && <p role="status">Requirement filter cleared because it is unavailable in this scope.</p>}
    </div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {!ready && <div className="status-banner" role="status">Loading knowledge gaps…</div>}
    {ready && !loadError && <>
      <div className="timeline-summary" role="status">
        {items.length} knowledge gap{items.length === 1 ? "" : "s"}{limitReached ? " loaded" : ""}{criticalCount ? ` · ${criticalCount} critical` : ""}
        {limitReached && <div>This list loads up to {KNOWLEDGE_GAP_LIST_LIMIT} gaps. Additional records may exist.</div>}
      </div>
      <section className="knowledge-list">
      {visibleItems.length === 0 ? <div className="empty-state detail-card"><p>{matchingFilterCount > 0 ? "No knowledge gaps match the current filters." : "No active knowledge gaps in this scope."}</p>{activeFilterCount > 0 && <button className="text-button" onClick={resetFilters} type="button">Reset filters</button>}</div> : visibleItems.map((item) => <KnowledgeGapCard canDefer={hasPermission("knowledge_gaps.defer")} canEdit={hasPermission(item.entity_type === "service" ? "services.edit" : "assets.edit")} canExcept={hasPermission("knowledge_gaps.exception")} deciding={deciding} item={item} key={item.id} onAction={gapAction} onReopen={reopen} />)}
      </section>
    </>}
    {ready && items.length > PAGE_SIZE && <div className="pagination"><Button variant="secondary" disabled={offset === 0} onClick={() => updateFilters({ offset: Math.max(0, offset - PAGE_SIZE) })} type="button">Previous</Button><span>{offset + 1}–{Math.min(offset + PAGE_SIZE, items.length)} of {items.length} loaded gaps</span><Button variant="secondary" disabled={offset + PAGE_SIZE >= items.length} onClick={() => updateFilters({ offset: offset + PAGE_SIZE })} type="button">Next</Button></div>}
  </>;
}
