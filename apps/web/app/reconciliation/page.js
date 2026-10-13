"use client";

import { Button } from "../../components/button";
import styles from "./reconciliation.module.css";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { useWorkspaceContext } from "../../components/workspace-context";
import { ReconciliationCards, ReconciliationPagination } from "../../components/reconciliation-cards";
import { apiRequest } from "../../lib/api";
import { RECONCILIATION_QUEUES, reconciliationQueueFromValue, reconciliationPagePath } from "../../lib/reconciliation-queues.mjs";

export default function ReconciliationPage() {
  const searchParams = useSearchParams();
  const queue = reconciliationQueueFromValue(searchParams.get("queue"));
  const { hasPermission } = useAuth();
  const workspace = useWorkspaceContext();
  const [items, setItems] = useState([]);
  const [relatedNewEntities, setRelatedNewEntities] = useState([]);
  const [total, setTotal] = useState(0);
  const [nextCursor, setNextCursor] = useState(null);
  const [cursors, setCursors] = useState([null]);
  const [pageIndex, setPageIndex] = useState(0);
  const [assets, setAssets] = useState([]);
  const [linkSelections, setLinkSelections] = useState({});
  const [loading, setLoading] = useState(true);
  const [deciding, setDeciding] = useState("");
  const [error, setError] = useState("");
  const [loadedQueueKey, setLoadedQueueKey] = useState("");
  const canViewReconciliation = hasPermission("reconciliation.view");
  const canDecide = hasPermission("reconciliation.decide");
  const requestId = useRef(0);

  const load = useCallback(async (cursor = null) => {
    if (!canViewReconciliation) return;
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError("");
    try {
      const [page, availableAssets] = await Promise.all([
        apiRequest(reconciliationPagePath(queue, cursor)),
        canDecide ? apiRequest("/assets") : Promise.resolve([]),
      ]);
      if (requestId.current !== currentRequest) return;
      setLoadedQueueKey(queue.key);
      setItems(page.items);
      setRelatedNewEntities(page.related_new_entities);
      setTotal(page.total);
      setNextCursor(page.next_cursor);
      setAssets(availableAssets);
    } catch (requestError) {
      if (requestId.current !== currentRequest) return;
      setLoadedQueueKey(queue.key);
      setItems([]);
      setRelatedNewEntities([]);
      setTotal(0);
      setNextCursor(null);
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
    setRelatedNewEntities([]);
    setCursors([null]);
    setPageIndex(0);
    load();
    return () => { requestId.current += 1; };
  }, [load]);

  if (!canViewReconciliation) return <AccessDenied />;

  async function decide(item, action, disposition = null) {
    setDeciding(item.id);
    setError("");
    try {
      await apiRequest(`/reconciliation-items/${item.id}/${action}`, { method: "POST", body: JSON.stringify({ reason: null, disposition }) });
      await load(cursors[pageIndex]);
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
      await load(cursors[pageIndex]);
    } catch (requestError) { setError(requestError.message || "Atlas could not link this asset."); }
    finally { setDeciding(""); }
  }

  function goToPage(index) {
    const next = index > pageIndex ? [...cursors.slice(0, pageIndex + 1), nextCursor] : cursors;
    setCursors(next);
    setPageIndex(index);
    setLinkSelections({});
    load(next[index]);
  }

  function refresh() {
    setCursors([null]);
    setPageIndex(0);
    setLinkSelections({});
    load();
  }

  const queueReady = loadedQueueKey === queue.key;

  return <>
    <PageHeader eyebrow="Operations" title="Reconciliation" description="Review new, changed, conflicting and no-longer-observed knowledge proposed by Atlas sources." actions={<Button variant="secondary" disabled={loading || Boolean(deciding)} onClick={refresh}>Refresh queue</Button>} />
    <div className="admin-tabs" role="tablist">{RECONCILIATION_QUEUES.map((candidate) => <Link aria-selected={queue.key === candidate.key} className={queue.key === candidate.key ? "active" : ""} href={candidate.href} key={candidate.key} role="tab">{candidate.label}</Link>)}</div>
    {queueReady && error && <div className="error-banner" role="alert">{error}</div>}
    {!queueReady || loading ? <div className="status-banner" role="status">Loading reconciliation items…</div> : <section className={`knowledge-list ${styles.list}`}>
      <div className="timeline-summary" role="status">{items.length} queue items on this page · {total} matching items</div>
      <p className="secondary-text">Refresh to include newer items. Related new entities are shown alongside their initial facts; each item has its own decision.</p>
      {items.length === 0 ? <div className="empty-state detail-card">No reconciliation items in this queue.</div> :
        <ReconciliationCards items={items} relatedNewEntities={relatedNewEntities} assets={assets} canDecide={canDecide} deciding={deciding} linkSelections={linkSelections} setLinkSelections={setLinkSelections} linkAsset={linkAsset} decide={decide} />}

    </section>}
    {queueReady && !loading && <ReconciliationPagination pageIndex={pageIndex} hasMore={Boolean(nextCursor)} busy={Boolean(deciding)} onPrevious={() => goToPage(pageIndex - 1)} onNext={() => goToPage(pageIndex + 1)} />}
  </>;
}
