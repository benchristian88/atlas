"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { Button } from "../../components/button";
import { SearchFilterBar, useCatalogueSearch } from "../../components/catalogue-filters";
import { PageHeader } from "../../components/page-header";
import { ReconciliationEntityCard, ReconciliationPagination, ReconciliationReviewLink } from "../../components/reconciliation-cards";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";
import { RECONCILIATION_QUEUES, reconciliationQueueFromValue, reconciliationEntityPagePath, reconciliationReviewHref, reconciliationReturnHref } from "../../lib/reconciliation-queues.mjs";
import styles from "./reconciliation.module.css";

export default function ReconciliationPage() {
  const searchParams = useSearchParams();
  const paramsString = searchParams.toString();
  const queue = reconciliationQueueFromValue(searchParams.get("queue"));
  const search = searchParams.get("search") || "";
  const section = searchParams.get("section") || "";
  const cursor = searchParams.get("cursor");
  const focusId = searchParams.get("entity");
  const requestedPage = Number(searchParams.get("page"));
  const pageIndex = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 0;
  const returnHref = reconciliationReturnHref(searchParams.get("return"));
  const { hasPermission } = useAuth();
  const workspace = useWorkspaceContext();
  const canViewReconciliation = hasPermission("reconciliation.view");
  const canDecide = hasPermission("reconciliation.decide");
  const canViewAssets = hasPermission("assets.view");
  const [page, setPage] = useState(null);
  const [focusedEntity, setFocusedEntity] = useState(null);
  const [assets, setAssets] = useState([]);
  const [linkSelections, setLinkSelections] = useState({});
  const [loading, setLoading] = useState(true);
  const [deciding, setDeciding] = useState("");
  const [error, setError] = useState("");
  const [outcome, setOutcome] = useState(null);
  const requestId = useRef(0);
  const activeLoadKey = useRef("");
  const loadedKey = useRef("");
  const loadKey = JSON.stringify([queue.key, search, section, cursor, focusId, workspace.reloadKey]);
  activeLoadKey.current = loadKey;

  function updateFilters(changes) {
    const params = new URLSearchParams(paramsString);
    for (const [key, value] of Object.entries(changes)) {
      if (value) params.set(key, value); else params.delete(key);
    }
    for (const key of ["cursor", "page", "entity", "return"]) params.delete(key);
    window.history.replaceState(null, "", `/reconciliation?${params}`);
  }
  const searchControl = useCatalogueSearch(search, next => updateFilters({ search: next }), loadKey);

  const load = useCallback(async () => {
    if (!canViewReconciliation) return;
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError("");
    try {
      const [nextPage, availableAssets, focused] = await Promise.all([
        apiRequest(reconciliationEntityPagePath(queue, { cursor, search, section })),
        canDecide && canViewAssets ? apiRequest("/assets") : Promise.resolve([]),
        focusId ? apiRequest(`/reconciliation-entities/${encodeURIComponent(focusId)}`) : Promise.resolve(null),
      ]);
      if (requestId.current !== currentRequest) return;
      loadedKey.current = loadKey;
      setPage(nextPage);
      setAssets(availableAssets);
      setFocusedEntity(focused);
    } catch (requestError) {
      if (requestId.current !== currentRequest) return;
      loadedKey.current = loadKey;
      setPage(null);
      setFocusedEntity(null);
      setAssets([]);
      setError(requestError.message || "Atlas could not load entity reviews.");
    } finally {
      if (requestId.current === currentRequest) setLoading(false);
    }
  }, [canDecide, canViewAssets, canViewReconciliation, queue.key, queue.status, queue.category, cursor, search, section, focusId, workspace.reloadKey, loadKey]);

  useEffect(() => {
    setPage(null);
    setFocusedEntity(null);
    setAssets([]);
    setLinkSelections({});
    setDeciding("");
    setOutcome(null);
    load();
    return () => { requestId.current += 1; };
  }, [load]);

  useEffect(() => {
    if (!focusId || loading) return;
    const target = document.getElementById(`entity-${focusId}`);
    target?.scrollIntoView({ block: "center" });
    target?.focus({ preventScroll: true });
  }, [focusId, focusedEntity, loading]);

  if (!canViewReconciliation) return <AccessDenied />;

  async function decide(item, action, disposition = null) {
    const actionKey = loadKey;
    setDeciding(item.id);
    setError("");
    setOutcome(null);
    try {
      await apiRequest(`/reconciliation-items/${item.id}/${action}`, {
        method: "POST", body: JSON.stringify({ reason: null, disposition, expected_version: item.version }),
      });
      if (activeLoadKey.current !== actionKey) return;
      await load();
    } catch (requestError) { if (activeLoadKey.current === actionKey) setError(requestError.message || `Atlas could not ${action} this item.`); }
    finally { if (activeLoadKey.current === actionKey) setDeciding(""); }
  }

  async function acceptAll(entity) {
    const actionKey = loadKey;
    setDeciding(entity.id);
    setError("");
    setOutcome(null);
    try {
      const result = await apiRequest(`/reconciliation-entities/${entity.id}/accept`, { method: "POST", body: JSON.stringify({ items: entity.decision_items }) });
      if (activeLoadKey.current !== actionKey) return;
      setOutcome({ name: entity.name, ...result });
      await load();
    } catch (requestError) { if (activeLoadKey.current === actionKey) setError(requestError.message || "Atlas could not accept this entity's changes."); }
    finally { if (activeLoadKey.current === actionKey) setDeciding(""); }
  }

  async function linkAsset(item) {
    const actionKey = loadKey;
    const assetId = linkSelections[item.id];
    if (!assetId) return;
    setDeciding(item.id);
    setError("");
    try {
      await apiRequest(`/reconciliation-items/${item.id}/link-asset`, { method: "POST", body: JSON.stringify({ asset_id: assetId, reason: "Linked during reconciliation" }) });
      if (activeLoadKey.current !== actionKey) return;
      await load();
    } catch (requestError) { if (activeLoadKey.current === actionKey) setError(requestError.message || "Atlas could not link this asset."); }
    finally { if (activeLoadKey.current === actionKey) setDeciding(""); }
  }

  async function loadSection(entity, currentSection) {
    const actionKey = loadKey;
    setDeciding(entity.id);
    setError("");
    try {
      const params = new URLSearchParams({ section: currentSection.key, offset: String(currentSection.next_offset), status: focusId === entity.id ? "active" : queue.status });
      if (queue.category && focusId !== entity.id) params.set("category", queue.category);
      const next = await apiRequest(`/reconciliation-entities/${entity.id}/section?${params}`);
      if (activeLoadKey.current !== actionKey) return;
      const merge = record => record.id !== entity.id ? record : { ...record, sections: record.sections.map(existing => existing.key !== currentSection.key ? existing : { ...next, items: [...existing.items, ...next.items] }) };
      setPage(current => ({ ...current, entities: current.entities.map(merge) }));
      setFocusedEntity(current => current ? merge(current) : current);
    } catch (requestError) { if (activeLoadKey.current === actionKey) setError(requestError.message || "Atlas could not load more changes."); }
    finally { if (activeLoadKey.current === actionKey) setDeciding(""); }
  }

  function nextPage() {
    const params = new URLSearchParams(paramsString);
    params.set("cursor", page.next_cursor);
    params.set("page", String(pageIndex + 1));
    params.delete("entity"); params.delete("return");
    window.history.pushState(null, "", `/reconciliation?${params}`);
  }

  function previousPage() {
    const params = new URLSearchParams(paramsString);
    if (page.previous_cursor) params.set("cursor", page.previous_cursor); else params.delete("cursor");
    params.set("page", String(Math.max(0, pageIndex - 1)));
    params.delete("entity"); params.delete("return");
    window.history.pushState(null, "", `/reconciliation?${params}`);
  }

  const queueReady = loadedKey.current === loadKey;
  const entities = page?.entities || [];
  const displayed = focusedEntity && !entities.some(entity => entity.id === focusedEntity.id) ? [focusedEntity, ...entities] : entities.map(entity => focusedEntity?.id === entity.id ? focusedEntity : entity);
  const busy = Boolean(deciding);

  return <>
    <PageHeader eyebrow="Operations" title="Reconciliation" description="Review proposed knowledge by entity." actions={<Button variant="secondary" disabled={loading || busy} onClick={() => (cursor || focusId) ? updateFilters({}) : load()}>Refresh queue</Button>} />
    <div className="admin-tabs" role="tablist">{RECONCILIATION_QUEUES.map(candidate => <ReconciliationReviewLink aria-selected={queue.key === candidate.key} className={queue.key === candidate.key ? "active" : ""} href={candidate.href} key={candidate.key} role="tab">{candidate.label}</ReconciliationReviewLink>)}</div>
    <SearchFilterBar label="Search entities" search={searchControl} activeCount={section ? 1 : 0} onClear={() => { searchControl.reset(); updateFilters({ search: "", section: "" }); }} ><label className="field"><span>Review section</span><select aria-label="Review section" value={section} onChange={event => updateFilters({ section: event.target.value })}><option value="">All sections</option><option value="facts">Facts</option><option value="relationships">Relationships</option><option value="network">Network</option></select></label></SearchFilterBar>
    {returnHref && <p><ReconciliationReviewLink href={returnHref}>Return to previous entity</ReconciliationReviewLink></p>}
    {queueReady && error && <div className="error-banner" role="alert">{error}</div>}
    {outcome && <div className={`status-banner ${styles.outcome}`} role="status"><strong>{outcome.name}: {outcome.accepted.length} accepted · {outcome.already_resolved.length} already resolved · {outcome.blocked.length} waiting · {outcome.failed.length} failed</strong>
      {[...outcome.blocked, ...outcome.failed, ...outcome.already_resolved].length > 0 && <ul>{[...outcome.blocked, ...outcome.failed, ...outcome.already_resolved].map(item => <li key={item.id}>{item.label}: {item.reason}</li>)}</ul>}
    </div>}
    {!queueReady || loading ? <div className="status-banner" role="status">Loading entity reviews…</div> : page && <section className={`knowledge-list ${styles.list}`}>
      <div className="timeline-summary" role="status">{page.record_total} reconciliation records grouped into {page.entity_total} entities · {entities.length} {entities.length === 1 ? "entity" : "entities"} on this page</div>
      {focusedEntity && <p className="secondary-text">Reviewing a prerequisite and its unresolved changes. Return to continue your previous review.</p>}
      {displayed.length === 0 ? <div className="empty-state detail-card">No reconciliation items in this queue.</div> : displayed.map(entity => <ReconciliationEntityCard key={entity.id} entity={entity} focused={focusId === entity.id} assets={assets} canDecide={canDecide} busy={busy} linkSelections={linkSelections} setLinkSelections={setLinkSelections} linkAsset={linkAsset} decide={decide} acceptAll={acceptAll} loadSection={loadSection} reviewHref={target => reconciliationReviewHref(paramsString, target, entity.id)} />)}
    </section>}
    {queueReady && !loading && page && <ReconciliationPagination pageIndex={pageIndex} hasMore={Boolean(page.next_cursor)} busy={busy} onPrevious={previousPage} onNext={nextPage} />}
  </>;
}
