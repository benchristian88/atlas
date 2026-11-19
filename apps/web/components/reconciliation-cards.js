import { Button } from "./button";
import { reconciliationGroups } from "../lib/reconciliation-queues.mjs";
import { EntityIdentity } from "./entity-identity";
import { StatusBadge } from "./status-badge";
import { NavigationIcon } from "./navigation-icon.mjs";

// This page fetches its review data on the client. Next's integrated History
// API keeps query navigation, refresh and Back in sync without an RSC request.
export function ReconciliationReviewLink({ href, children, ...props }) {
  return <a {...props} href={href} onClick={event => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    window.history.pushState(null, "", href);
  }}>{children}</a>;
}

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

function ReviewBlockers({ item, reviewHref }) {
  if (!item.blocked_reason || !["open", "deferred"].includes(item.status)) return null;
  return <div className="review-blocked" role="status">
    <span>Waiting — {item.blocked_reason}</span>
    {item.blockers?.filter(blocker => blocker.entity_id).map(blocker => <ReconciliationReviewLink key={`${blocker.item_id}-${blocker.name}`} href={reviewHref(blocker.entity_id)}>Review {blocker.name}</ReconciliationReviewLink>)}
  </div>;
}

function ReviewActions({ item, decide, busy, parent = false }) {
  if (!["open", "deferred"].includes(item.status) || !item.can_reject) return null;
  if (item.category === "no_longer_observed") return <div className="form-actions">
    {[['keep_active', 'Keep active'], ['mark_inactive', 'Mark inactive'], ['retire', 'Retire'], ['exception', 'Exception'], ['mark_missing', 'Mark missing']].map(([disposition, label]) =>
      <Button key={disposition} variant="secondary" type="button" disabled={busy} onClick={() => decide(item, "accept", disposition)}>{label}</Button>)}
    <Button variant="secondary" disabled={busy} onClick={() => decide(item, "reject")}>Reject</Button>
    {item.can_defer && <Button variant="quiet" disabled={busy} onClick={() => decide(item, "defer")}>Defer</Button>}
  </div>;
  return <div className="form-actions">
    <Button variant="primary" type="button" disabled={busy || !item.can_accept} title={item.blocked_reason || undefined} onClick={() => decide(item, "accept")}>{parent && item.entity_type === "asset" ? "Accept asset" : item.entity_type === "asset_interface" && item.category === "changed" && item.assertion_predicate === "configuration" ? "Accept interface changes" : "Accept"}</Button>
    <Button variant="secondary" type="button" disabled={busy || !item.can_reject} onClick={() => decide(item, "reject")}>Reject</Button>
    <Button variant="quiet" type="button" disabled={busy || !item.can_defer} onClick={() => decide(item, "defer")}>Defer</Button>
  </div>;
}

function ProposedValue({ item }) {
  if (item.entity_type === "asset_relationship") return item.current ? <p className="secondary-text">Current: {value(item.current)}</p> : null;
  if (item.proposed && typeof item.proposed === "object" && !Array.isArray(item.proposed)) {
    return <>{item.current && typeof item.current === "object" && <div><p className="secondary-text">Accepted configuration</p><dl className="review-fields">{Object.entries(item.current).filter(([key]) => !["asset_id", "asset_external_id", "network_external_id"].includes(key)).map(([key, field]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{value(field)}</dd></div>)}</dl><p className="secondary-text">Observed configuration awaiting review</p></div>}<dl className="review-fields">{Object.entries(item.proposed).filter(([key, field]) => field !== null && !["asset_id", "network_id", "asset_external_id", "network_external_id", "facts", "interfaces"].includes(key)).map(([key, field]) =>
      <div key={key}><dt>{({ ip_address: "IP address", mac_address: "MAC address", is_primary: "Primary" })[key] || key.replaceAll("_", " ")}</dt><dd>{value(field)}</dd></div>)}</dl>
    </>;
  }
  return <div className="review-value">{item.current !== null && item.current !== undefined && <><span className="secondary-text">{value(item.current)}</span><span aria-label="changes to"> → </span></>}<span>{value(item.proposed)}</span></div>;
}

function ReviewProvenance({ item }) {
  return <details className="review-provenance"><summary>Evidence and details</summary>
    <dl className="review-fields">
      <div><dt>Source</dt><dd>{item.source_name || "Unknown source"}</dd></div>
      {item.last_observed_at && <div><dt>Last observed</dt><dd>{new Date(item.last_observed_at).toLocaleString()}</dd></div>}
      {item.entity_type === "source_identity" ? item.discovery_run_id && <div><dt>Discovery run</dt><dd><code>{item.discovery_run_id}</code></dd></div>
        : <div><dt>Source key</dt><dd><code>{item.assertion_predicate}</code></dd></div>}
      <div><dt>External identity</dt><dd><code>{item.candidate_external_id || "—"}</code></dd></div>
      <div><dt>Reconciliation record</dt><dd><code>{item.id}</code></dd></div>
    </dl>
    {item.entity_type !== "source_identity" && <div className="reconciliation-values"><div><span>Current</span><code>{value(item.current_value_json)}</code></div><div><span>Observed</span><code>{value(item.observed_value_json)}</code></div></div>}
  </details>;
}

function GuestIdentityEvidence({ item }) {
  const prior = item.current;
  const observed = item.proposed;
  return <div className="reconciliation-values review-identity-evidence">
    <div>
      <h3>Retired Asset at first hold</h3>
      <p>{prior.name} · {prior.lifecycle_status}</p>
      {prior.interfaces?.length > 0 && <ul>{prior.interfaces.map((nic, index) =>
        <li key={index}>{[nic.name, nic.mac_address, nic.ip_address, nic.assigned_network && `Assigned Network ${nic.assigned_network}`].filter(Boolean).join(" · ")}</li>)}</ul>}
      {prior.more_interfaces && <p>Additional accepted Interfaces appear on the Asset detail page.</p>}
      {prior.relationships?.length > 0 && <ul>{prior.relationships.map((edge, index) =>
        <li key={index}>{edge.type} → {edge.target}</li>)}</ul>}
      {prior.more_relationships && <p>Additional accepted relationships appear on the Asset detail page.</p>}
    </div>
    <div>
      <h3>Latest source evidence</h3>
      <p>{observed.name || "Only Interface or relationship evidence was received for this key."}</p>
      {observed.interfaces.length > 0 && <ul>{observed.interfaces.map(nic =>
        <li key={nic.external_id}>{[nic.name, nic.mac_address, nic.ip_address, nic.network_external_id && `Observed Network ${nic.network_external_id}`].filter(Boolean).join(" · ")}</li>)}</ul>}
      {observed.relationships.length > 0 && <ul>{observed.relationships.map(edge =>
        <li key={edge.external_id}>{edge.source.external_id} → {edge.relationship_class.split(".").pop().replaceAll("_", " ")} → {edge.target.external_id}</li>)}</ul>}
      {observed.asset_interface_count > observed.interfaces.length && <p>{observed.asset_interface_count} held Interface observations.</p>}
      {observed.relationship_count > observed.relationships.length && <p>{observed.relationship_count} held relationship observations.</p>}
    </div>
  </div>;
}

export function TechnicalIdentityLink({ item, busy, technicalChoices = {}, loadTechnicalChoices, linkSelections = {}, setLinkSelections, linkTechnical }) {
  if (!item.technical_identity || !["open", "deferred"].includes(item.status)) return null;
  const kind = item.entity_type === "asset_interface" ? "interface" : "network";
  const choices = technicalChoices[item.id];
  const candidates = (choices?.items || []).filter(candidate => kind === "interface" ? candidate.asset_id === item.link_asset_id : candidate.customer_id === item.customer_id && candidate.site_id === item.site_id);
  const selected = candidates.some(candidate => candidate.id === linkSelections[item.id]);
  return <details className="review-provenance" onToggle={event => {
    if (event.currentTarget.open && item.can_link_technical && !choices) loadTechnicalChoices?.(item, 0);
  }}><summary>Link existing {kind}</summary>
    <p className="secondary-text">Linking preserves accepted configuration. Review observed changes separately. An existing name requires an explicit link; names alone do not establish identity.</p>
    {!item.can_link_technical ? <p role="status">{item.link_blocked_reason}</p> : <>
      {choices?.error && <p role="alert">{choices.error}</p>}
      {choices?.loading && <p role="status">Loading existing {kind}s…</p>}
      {choices && !choices.loading && !candidates.length && <p role="status">No existing {kind}s are available{kind === "interface" ? " for this accepted asset" : " in this customer and site"}. Accept a new entity only if it is distinct.</p>}
      <div className="reconciliation-link"><label htmlFor={`technical-link-${item.id}`}>Existing {kind}</label>
        <select id={`technical-link-${item.id}`} value={linkSelections[item.id] || ""} disabled={busy || choices?.loading || !candidates.length} onChange={event => setLinkSelections(current => ({ ...current, [item.id]: event.target.value }))}>
          <option value="">Select existing {kind}…</option>{candidates.map(candidate => <option key={candidate.id} value={candidate.id}>{[candidate.name, candidate.mac_address, candidate.ip_address, candidate.network_id && `Network ${candidate.network_id}`, candidate.cidr, candidate.vlan_id != null && `VLAN ${candidate.vlan_id}`].filter(Boolean).join(" · ")}</option>)}
        </select><Button variant="secondary" type="button" disabled={busy || choices?.loading || !selected} onClick={() => linkTechnical(item)}>Link {kind}</Button>
      </div>
      {choices?.nextOffset != null && <Button variant="quiet" type="button" disabled={busy || choices.loading} onClick={() => loadTechnicalChoices(item, choices.nextOffset)}>Show more {kind}s</Button>}
      {choices?.error && <Button variant="quiet" type="button" disabled={busy || choices.loading} onClick={() => loadTechnicalChoices(item, 0)}>Retry candidates</Button>}
    </>}
  </details>;
}

export function ReconciliationReviewRow({ item, busy, decide, reviewHref, ...actions }) {
  return <article className="review-row" aria-labelledby={`review-item-${item.id}`}>
    <div className="review-row-heading"><h4 id={`review-item-${item.id}`}>{item.label}</h4><StatusBadge status={item.status} /></div>
    {item.warning && <p className="review-warning">{item.warning}</p>}
    <ProposedValue item={item} />
    {item.category === "no_longer_observed" && <p className="secondary-text">This source no longer observes the asset. Choose a lifecycle disposition.</p>}
    <ReviewBlockers item={item} reviewHref={reviewHref} />
    <ReviewActions item={item} busy={busy} decide={decide} />
    <TechnicalIdentityLink item={item} busy={busy} {...actions} />
    <ReviewProvenance item={item} />
  </article>;
}

function ReviewSection({ entity, section, ...actions }) {
  return <section className="review-section" data-loaded-complete={section.next_offset === null} aria-label={`${section.label} for ${entity.name}`}>
    <details open={section.total <= 4}>
      <summary><span>{section.label}</span><span className="secondary-text">{section.total} {section.total === 1 ? "change" : "changes"}{section.blocked_count ? ` · ${section.blocked_count} waiting` : ""}</span><span className="review-chevron"><NavigationIcon name="chevron-down" /></span></summary>
      {section.items.map(item => <ReconciliationReviewRow key={item.id} item={item} {...actions} />)}
      {section.next_offset !== null && <Button variant="secondary" disabled={actions.busy} onClick={() => actions.loadSection(entity, section)}>Show more {section.label.toLowerCase()}</Button>}
    </details>
    {section.warnings.length > 0 && <div className="review-section-warnings" role="status">{section.warnings.map(warning => <p key={warning}>{warning}</p>)}</div>}
  </section>;
}

export function ReconciliationEntityCard({ entity, focused = false, canDecide, busy, acceptAll, assets = [], linkSelections = {}, setLinkSelections, linkAsset, ...actions }) {
  const parent = entity.parent;
  const identityReview = parent?.entity_type === "source_identity";
  const candidates = assets.filter(asset => asset.customer_id === entity.customer_id && asset.site_id === entity.site_id);
  const blocked = entity.sections.reduce((count, section) => count + section.blocked_count, 0);
  return <article id={`entity-${entity.id}`} tabIndex={-1} className={`detail-card review-entity${focused ? " review-entity-focused" : ""}`} aria-label={`Review ${entity.name}`}>
    <details open={focused || entity.default_expanded}>
      <summary className="review-entity-heading">
        <EntityIdentity type={["asset", "source_identity"].includes(entity.entity_type) ? "asset" : "network"} record={entity} />
        <span className="review-identity"><span className="review-entity-name" role="heading" aria-level={2}>{entity.name}</span><span className="secondary-text">{entity.type_label} · {entity.matching_record_count} {entity.matching_record_count === 1 ? "record" : "records"}</span></span>
        {parent ? <StatusBadge status={parent.status} /> : <span className="secondary-text">{entity.matching_record_count} changes</span>}
        {blocked > 0 && <span className="review-warning">{blocked} waiting</span>}
        {entity.sections.some(section => section.warnings.length > 0) && <span className="review-warning">Needs review</span>}
        <span className="review-chevron"><NavigationIcon name="chevron-down" /></span>
      </summary>
      <div className="review-entity-body">
        {parent && <section className="review-parent" aria-label={identityReview ? "Identity review" : "Entity decision"}>
          {!identityReview && <div className="review-row-heading"><h3>{parent.label}</h3><StatusBadge status={parent.status} /></div>}
          {parent.warning && <p className="review-warning">{parent.warning}</p>}
          {identityReview && <GuestIdentityEvidence item={parent} />}
          <ReviewBlockers item={parent} reviewHref={actions.reviewHref} />
          {canDecide && <ReviewActions item={parent} parent busy={busy} decide={actions.decide} />}
          <TechnicalIdentityLink item={parent} busy={busy} {...actions} linkSelections={linkSelections} setLinkSelections={setLinkSelections} />
          {canDecide && ["open", "deferred"].includes(parent.status) && parent.entity_type === "asset" && <details className="review-provenance"><summary>Link an existing asset</summary><div className="reconciliation-link">
            <select aria-label={`Existing asset to link to ${entity.name}`} value={linkSelections[parent.id] || ""} onChange={event => setLinkSelections(current => ({ ...current, [parent.id]: event.target.value }))}><option value="">Select existing asset…</option>{candidates.map(asset => <option key={asset.id} value={asset.id}>{asset.name} · {asset.asset_type}</option>)}</select>
            <Button variant="secondary" disabled={busy || !linkSelections[parent.id]} onClick={() => linkAsset(parent)}>Link asset</Button>
          </div></details>}
          <ReviewProvenance item={parent} />
        </section>}
        {canDecide && entity.decision_items.length > 0 && <div className="review-bulk"><Button variant="secondary" disabled={busy || !entity.accept_all_available} onClick={() => acceptAll(entity)}>Accept all</Button><span className="secondary-text">Accept eligible changes in this review{parent && ["open", "deferred"].includes(parent.status) ? ", including the asset" : ""}. Waiting items stay unresolved.</span></div>}
        {!entity.accept_all_available && entity.matching_record_count > entity.bulk_limit && <p className="review-warning">Review these changes individually; this entity exceeds the {entity.bulk_limit} record bulk limit.</p>}
        {entity.sections.map(section => <ReviewSection key={section.key} entity={entity} section={section} busy={busy} {...actions} linkSelections={linkSelections} setLinkSelections={setLinkSelections} />)}
        {!entity.sections.length && !parent && <p className="secondary-text">No unresolved changes remain for this entity.</p>}
      </div>
    </details>
  </article>;
}
