import { Button } from "./button";
import { reconciliationGroups } from "../lib/reconciliation-queues.mjs";

export function ReconciliationPagination({ pageIndex, hasMore, busy, onPrevious, onNext }) {
  if (pageIndex === 0 && !hasMore) return null;
  return <nav className="pagination" aria-label="Reconciliation pages">
    <Button variant="secondary" disabled={pageIndex === 0 || busy} onClick={onPrevious} type="button">Previous</Button>
    <span>Page {pageIndex + 1}</span>
    <Button variant="secondary" disabled={!hasMore || busy} onClick={onNext} type="button">Next</Button>
  </nav>;
}

function value(value) {
  if (value === null || value === undefined) return "—";
  return typeof value === "string" ? value : JSON.stringify(value);
}

function relationshipLabel(item, current = false) {
  if (current && !item.current_relationship_id) return "No current relationship";
  const source = item.resolved_source_name || item.source_external_id || "Unresolved source";
  const target = item.resolved_target_name || item.target_external_id || "Unresolved target";
  const type = ((current ? item.current_value_json?.relationship_type : null) || item.observed_value_json?.relationship_type || "related_to").replaceAll("_", " ");
  return `${source} → ${type} → ${target}`;
}

export function ReconciliationItemCard({ item, assets = [], canDecide, deciding, linkSelections = {}, setLinkSelections, linkAsset, decide, initialFact = false }) {
  const relationship = item.entity_type === "asset_relationship";
  const candidates = assets.filter(asset => asset.customer_id === item.customer_id && asset.site_id === item.site_id);
  return <article className="detail-card reconciliation-card" aria-labelledby={`reconciliation-${item.id}`}>
        <div className="reconciliation-heading"><div><p className="eyebrow">{initialFact ? "Initial source fact" : item.category.replaceAll("_", " ")}</p><h2 id={`reconciliation-${item.id}`}>{initialFact ? item.assertion_predicate || item.observed_value_json?.field || "Source fact" : item.entity_name || item.entity_type.replaceAll("_", " ")}</h2></div><span className="secondary-text">{item.source_name || "Unknown source"} · {new Date(item.created_at).toLocaleString()}</span></div>
        {item.category === "no_longer_observed" && <p className="secondary-text">Last observed {item.last_observed_at ? new Date(item.last_observed_at).toLocaleString() : "Unavailable"}. Missing since {item.missing_since_at ? new Date(item.missing_since_at).toLocaleString() : "this snapshot"}.</p>}
        <div className="reconciliation-values"><div><span>Current</span><code>{relationship ? relationshipLabel(item, true) : value(item.current_value_json)}</code></div><div><span>Observed</span><code>{relationship ? relationshipLabel(item) : value(item.observed_value_json)}</code></div></div>
        {relationship && <div className="resolution-grid"><div><span>Source</span><strong>{item.source_resolution_status || "unresolved"}</strong><small>{item.source_external_id}</small></div><div><span>Target</span><strong>{item.target_resolution_status || "unresolved"}</strong><small>{item.target_external_id}</small></div></div>}
        {item.blocked_reason && <div className="warning-banner" role="status">{item.blocked_reason}</div>}
        {item.recommended_action && <p className="secondary-text">Recommended: {item.recommended_action}</p>}
        {canDecide && item.entity_type === "asset" && ["newly_discovered", "possible_duplicate"].includes(item.category) && <div className="reconciliation-link"><select aria-label="Existing asset to link" onChange={(event) => setLinkSelections((current) => ({ ...current, [item.id]: event.target.value }))} value={linkSelections[item.id] || ""}><option value="">Select existing asset…</option>{candidates.map((asset) => <option key={asset.id} value={asset.id}>{asset.name} · {asset.asset_type}</option>)}</select><Button variant="secondary" disabled={deciding === item.id || !linkSelections[item.id]} onClick={() => linkAsset(item)} type="button">Link asset</Button></div>}
        {canDecide && ["open", "deferred"].includes(item.status) && (item.category === "no_longer_observed" ? <div className="form-actions"><Button variant="secondary" disabled={deciding === item.id} onClick={() => decide(item, "accept", "keep_active")} type="button">Keep active</Button><Button variant="secondary" disabled={deciding === item.id} onClick={() => decide(item, "accept", "mark_inactive")} type="button">Mark inactive</Button><Button variant="secondary" disabled={deciding === item.id} onClick={() => decide(item, "accept", "retire")} type="button">Retire</Button><Button variant="secondary" disabled={deciding === item.id} onClick={() => decide(item, "accept", "exception")} type="button">Exception</Button><Button variant="primary" disabled={deciding === item.id} onClick={() => decide(item, "accept", "mark_missing")} type="button">{deciding === item.id ? "Saving…" : "Mark missing"}</Button></div> : <div className="form-actions"><Button variant="secondary" disabled={deciding === item.id} onClick={() => decide(item, "defer")} type="button">Defer</Button><Button variant="secondary" disabled={deciding === item.id} onClick={() => decide(item, "reject")} type="button">Reject</Button><Button variant="primary" disabled={deciding === item.id || Boolean(item.blocked_reason)} onClick={() => decide(item, "accept")} title={item.blocked_reason || "Accept this item"} type="button">{deciding === item.id ? "Saving…" : "Accept"}</Button></div>)}
      </article>;
}

export function ReconciliationCards({ items, relatedNewEntities = [], ...actions }) {
  return reconciliationGroups(items, relatedNewEntities).map(group => group.facts.length ?
    <section className="detail-card" key={group.entity.id} aria-label={`New entity and initial facts: ${group.entity.entity_name || group.entity.candidate_external_id}`}>
      <ReconciliationItemCard item={group.entity} {...actions} />
      <details className="assertion-group" open>
        <summary>Initial source facts ({group.facts.length} on this page)</summary>
        <p className="secondary-text">Review each fact independently. Accepting the entity does not accept its facts.</p>
        {group.facts.map(item => <ReconciliationItemCard key={item.id} item={item} initialFact {...actions} />)}
      </details>
    </section> : <ReconciliationItemCard key={group.entity.id} item={group.entity} {...actions} />);
}
