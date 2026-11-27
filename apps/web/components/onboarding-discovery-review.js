"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "../lib/api";
import { mutationOutcomeUnknown } from "../lib/onboarding-integrations.mjs";
import {
  DISCOVERY_REVIEW, REVIEW_PAGE_SIZE, discoveryReviewPath, emptyReviewFilters, readUncertainReview,
  requiresReviewAcknowledgement, reviewedBatch, sameReviewedProposal,
} from "../lib/onboarding-discovery-review.mjs";
import { decisionRequest, technicalCandidatesPath } from "../lib/reconciliation-decisions.mjs";
import { useAuth } from "./auth-context";
import { Button } from "./button";
import { SearchFilterBar, useCatalogueSearch } from "./catalogue-filters";
import { ReconciliationPagination, ReconciliationProposalDetails } from "./reconciliation-cards";
import { Section } from "./section";
import { StatusIndicator } from "./status-indicator";
import reconciliation from "../app/reconciliation/reconciliation.module.css";
import styles from "./onboarding.module.css";

const categoryLabel = value => value.replaceAll("_", " ");
const closedStates = new Set(["accepted", "rejected", "exception"]);

function BatchResult({ result }) {
  const groups = [
    ["accepted", "Accepted"], ["already_resolved", "Already resolved"], ["blocked", "Waiting or needs review"], ["failed", "Failed or changed"],
  ];
  return <>
    <p>{groups.map(([key, label]) => `${result[key].length} ${label.toLowerCase()}`).join(" · ")}</p>
    {groups.slice(1).map(([key, label]) => result[key].length > 0 && <details key={key}>
      <summary>{label}</summary>
      <ul>{result[key].map(item => <li key={item.id}>{item.label} · {item.reason}</li>)}</ul>
    </details>)}
    {result.newly_eligible_total > 0 && <>
      <p><strong>{result.newly_eligible_total} newly eligible</strong> · Review these proposals and confirm a separate acceptance.</p>
      <ul>{result.newly_eligible.map(item => <li key={item.id}>{item.reason} · {item.label}</li>)}</ul>
      {result.newly_eligible_total > result.newly_eligible.length && <p>Showing the first {result.newly_eligible.length} newly eligible proposals.</p>}
    </>}
  </>;
}

export function OnboardingDiscoveryReview({ customer, site, canManage, canAdvance, blocked, onBusy, onDecision }) {
  const { user, hasPermissionForObject } = useAuth();
  const scoped = useCallback((path, options) => apiRequest(path, {
    ...options, omitContext: true, headers: { "X-Atlas-Customer-ID": customer.id, "X-Atlas-Site-ID": site.id },
  }), [customer.id, site.id]);
  const canViewIntegrations = hasPermissionForObject("integrations.view", customer.id, site.id);
  const canLinkAssets = ["assets.view", "assets.edit"].every(permission => hasPermissionForObject(permission, customer.id, site.id));
  const storageKey = `atlas-discovery-review:${user.id}:${customer.id}:${site.id}`;
  const [filters, setFilters] = useState(emptyReviewFilters);
  const [loaded, setLoaded] = useState(null);
  const [integrations, setIntegrations] = useState(null);
  const [error, setError] = useState("");
  const [runError, setRunError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const [selected, setSelected] = useState(null);
  const [confirmation, setConfirmation] = useState(null);
  const [uncertain, setUncertain] = useState({});
  const [assets, setAssets] = useState(null);
  const [linkSelections, setLinkSelections] = useState({});
  const [technicalChoices, setTechnicalChoices] = useState({});
  const uncertainRef = useRef({});
  const active = useRef(false);
  const reads = useRef(null);
  const pending = useRef(false);
  const candidates = useRef(new Map());
  const dialog = useRef(null);
  const feedback = useRef(null);
  const selectedHeading = useRef(null);
  const focusFeedback = useRef(false);
  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const page = loaded?.filters === filters ? loaded.page : null;
  const search = useCatalogueSearch(filters.search, value => setFilters(previous => ({ ...previous, search: value, offset: 0 })));

  const load = useCallback(async (next, { recover = false, status = true } = {}) => {
    reads.current?.abort();
    const controller = new AbortController();
    reads.current = controller;
    const { signal } = controller;
    const results = await Promise.allSettled([
      scoped(discoveryReviewPath(next, recover ? Object.keys(uncertainRef.current) : []), { signal }),
      status && canViewIntegrations ? scoped("/integrations?include_discovery=true", { signal }) : Promise.resolve(null),
    ]);
    if (signal.aborted || !active.current) return;
    const [review, integrations] = results;
    if (review.status === "fulfilled") {
      if (next.offset && next.offset >= review.value.eligible + review.value.needs_review) {
        setFilters(current => current === next ? { ...current, offset: 0 } : current);
      }
      setLoaded({ filters: next, page: review.value });
      setError("");
    } else {
      setLoaded(null);
      setError(review.reason.message || "Atlas could not load Discovery Review.");
    }
    if (status && canViewIntegrations) {
      setIntegrations(integrations.status === "fulfilled" ? integrations.value : null);
      setRunError(integrations.status === "rejected" ? "Discovery run status could not be loaded. Refresh Discovery Review to retry." : "");
    }
    return review.status === "fulfilled" ? review.value : null;
  }, [scoped, canViewIntegrations]);

  useEffect(() => {
    active.current = true;
    uncertainRef.current = readUncertainReview(storageKey);
    setUncertain(uncertainRef.current);
    const inflightCandidates = candidates.current;
    return () => {
      active.current = false;
      reads.current?.abort();
      for (const request of inflightCandidates.values()) request.abort();
      inflightCandidates.clear();
    };
  }, [storageKey]);

  useEffect(() => { load(filters, { recover: true }); }, [filters, load]);
  useEffect(() => {
    const interval = setInterval(() => {
      if (!pending.current && !reads.current?.signal.aborted) load(filtersRef.current, { recover: true });
    }, 10000);
    return () => clearInterval(interval);
  }, [load]);

  useEffect(() => {
    if (notice && focusFeedback.current) {
      focusFeedback.current = false;
      feedback.current?.focus();
    }
  }, [notice]);
  useEffect(() => { if (selected) selectedHeading.current?.focus(); }, [selected]);

  function updateUncertain(ids, add) {
    const next = { ...uncertainRef.current };
    for (const id of ids) {
      if (add) next[id] = true;
      else delete next[id];
    }
    uncertainRef.current = next;
    try { sessionStorage.setItem(storageKey, JSON.stringify(next)); } catch {}
    if (active.current) setUncertain(next);
  }

  function showNotice(value) {
    if (!active.current) return;
    focusFeedback.current = true;
    setNotice(value);
  }

  async function mutate(ids, path, options, describe, { batch = false } = {}) {
    if (blocked || pending.current || ids.some(id => uncertainRef.current[id])) return false;
    pending.current = true;
    setBusy(true);
    onBusy(true);
    updateUncertain(ids, true);
    setNotice(null);
    try {
      const result = await scoped(path, { ...options, signal: AbortSignal.timeout(30000) });
      if (!result) throw Object.assign(new Error("The decision response is unavailable."), { kind: "response" });
      updateUncertain(ids, false);
      if (!active.current) return true;
      setSelected(null);
      setLinkSelections({});
      showNotice(describe(result));
      await load(filtersRef.current, { recover: true });
      return true;
    } catch (failure) {
      const unknown = mutationOutcomeUnknown(failure);
      if (unknown) updateUncertain(ids, true);
      else updateUncertain(ids, false);
      if (!active.current) return true;
      await load(filtersRef.current, { recover: true });
      const unavailableBatch = batch && [403, 404].includes(failure.status);
      showNotice(unknown ? { warning: "The decision response was lost or incomplete. Check current proposal status below. Atlas cannot confirm which request caused any recorded decision." }
        : { error: unavailableBatch ? "Atlas could not authorize or verify the reviewed batch. Check your access and refresh Discovery Review." : failure.message });
      return unknown || failure.status === 409;
    } finally {
      pending.current = false;
      if (active.current) {
        setBusy(false);
        onBusy(false);
      }
    }
  }

  function individual(item, action, options) {
    const [path, request] = decisionRequest(item, action, options);
    return mutate([item.id], path, request, result => ({
      message: action === "identity-decision" ? (result.outcome === "replace" ? "Replacement asset created." : "Same guest confirmed.")
        : action.startsWith("link-") ? "Identity linked. Check any outstanding changes."
        : `Decision recorded for ${item.entity_name} · ${result.status}.`,
    }));
  }

  function select(item) {
    setSelected(item);
    setLinkSelections({});
  }

  function confirm(data) {
    if (blocked || pending.current) return;
    setConfirmation(data);
    dialog.current.showModal();
  }

  async function acceptBatch(batch) {
    await mutate(batch.items.map(item => item.id), `${DISCOVERY_REVIEW}/accept`, {
      method: "POST", body: JSON.stringify({ items: batch.items }),
    }, result => ({ result }), { batch: true });
  }

  async function decideStage(decision, version) {
    const result = await onDecision(decision, version);
    if (result?.refreshReview && active.current) {
      await load(filtersRef.current, { recover: true });
      showNotice({ warning: "Discovery Review changed. Check the latest Site totals before continuing." });
    }
  }

  async function submitConfirmation(event) {
    event.preventDefault();
    if (busy || blocked || pending.current || !confirmation) return;
    const { batch, retirement, summary } = confirmation;
    dialog.current.close();
    if (batch) await acceptBatch(batch);
    else if (retirement) await individual(retirement, "accept", { disposition: "retire" });
    else await decideStage("attention", summary.version);
  }

  async function loadCandidates(key, path, success, failure) {
    if (candidates.current.has(key)) return;
    const controller = new AbortController();
    candidates.current.set(key, controller);
    try {
      const rows = await scoped(path, { signal: controller.signal });
      if (!controller.signal.aborted) success(rows);
    } catch (error) {
      if (!controller.signal.aborted) failure(error);
    } finally {
      candidates.current.delete(key);
    }
  }

  function loadTechnicalChoices(item, offset) {
    setTechnicalChoices(old => ({ ...old, [item.id]: { ...old[item.id], loading: true, error: "" } }));
    loadCandidates(item.id, technicalCandidatesPath(item, offset), items => setTechnicalChoices(old => ({
      ...old, [item.id]: { items: offset ? [...(old[item.id]?.items || []), ...items] : items,
        nextOffset: items.length === 100 ? offset + 100 : null, loading: false },
    })), error => setTechnicalChoices(old => ({
      ...old, [item.id]: { ...old[item.id], loading: false, error: error.message },
    })));
  }

  function loadAssets() {
    if (assets) return;
    loadCandidates("assets", "/assets", setAssets, error => showNotice({ error: error.message }));
  }

  const summary = page?.summary;
  const hasReviewAccess = summary?.eligible != null;
  const visibleIntegrations = integrations?.filter(integration => !integration.retired_at);
  const ready = page?.items.filter(item => item.batch_version) || [];
  const exceptions = page?.items.filter(item => !item.batch_version) || [];
  const unavailable = blocked || busy;
  const batch = page && reviewedBatch(page, filters, site.name, uncertain);
  const latest = selected && page?.items.find(item => item.id === selected.id);
  const stale = selected && (!latest || !sameReviewedProposal(selected, latest));
  const recoveryIds = Object.keys(uncertain);
  const resolvedIds = recoveryIds.filter(id => closedStates.has(page?.decisions[id]));
  const outstanding = hasReviewAccess ? summary.eligible + summary.needs_review : null;
  const empty = visibleIntegrations?.length === 0 && integrations.length < 500 && outstanding === 0 && summary?.active_runs === 0 && summary?.accepted === 0;

  function reviewPrerequisite(blocker) {
    const target = page?.items.find(item => item.id === blocker.item_id);
    if (target) select(target);
    else {
      select(null);
      setFilters({ ...emptyReviewFilters, search: blocker.name.slice(0, 255) });
    }
  }

  function list(items) {
    return <ul className={styles.proposalList}>{items.map(item => <li key={item.id}>
      <div className={styles.proposalHeading}>
        <div><strong>{item.entity_name} · {item.label}</strong>
          <p className="secondary-text">{item.source_name || "Source unavailable"} · {categoryLabel(item.category)}
            {item.batch_exclusion && <> · {item.batch_exclusion}</>}</p>
          {item.batch_identity && <p className="secondary-text">{item.batch_identity.action === "create"
            ? "Create a new asset" : `Associate with existing asset ${item.batch_identity.asset_name}`}</p>}
        </div>
        <Button variant="quiet" aria-expanded={selected?.id === item.id} onClick={() => select(selected?.id === item.id ? null : item)}>
          {selected?.id === item.id ? "Close review" : "Review proposal"}
          <span className="sr-only"> for {item.entity_name} · {item.label}</span>
        </Button>
      </div>
      {hasReviewAccess && selected?.id === item.id && <div className={styles.proposalDetails}>
        <h4 ref={selectedHeading} tabIndex={-1}>Proposal details</h4>
        {stale ? <p role="status">This proposal or its eligibility changed. <Button disabled={unavailable} onClick={() => select(latest)}>Load updated proposal</Button></p>
          : <ReconciliationProposalDetails item={selected} busy={unavailable || Boolean(uncertain[item.id])}
              canLinkAsset={canLinkAssets && item.can_reject && item.entity_type === "asset" && ["newly_discovered", "possible_duplicate"].includes(item.category)}
              assets={assets || []} loadAssets={loadAssets} onReview={reviewPrerequisite}
              decide={(record, action, disposition) => disposition === "retire" ? confirm({ retirement: record }) : individual(record, action, { disposition })}
              decideIdentity={(record, outcome, reason) => individual(record, "identity-decision", { outcome, reason })}
              technicalChoices={technicalChoices} loadTechnicalChoices={loadTechnicalChoices}
              linkSelections={linkSelections} setLinkSelections={setLinkSelections}
              linkAsset={record => individual(record, "link-asset", { target: linkSelections[record.id], reason: "Linked during reconciliation" })}
              linkTechnical={record => individual(record, "link-technical", { target: linkSelections[record.id], reason: "Linked during reconciliation" })} />}
      </div>}
    </li>)}</ul>;
  }

  return <div className={`${styles.discoveryReview} ${reconciliation.list}`}>
    <p>Review your discovered infrastructure before adding it to your knowledge base.</p>
    <Section title="Discovery status" heading="h3" actions={
      <Button variant="quiet" disabled={unavailable} onClick={() => load(filters, { recover: true })}>Refresh Discovery Review</Button>
    }>
      {empty && <p>Manual setup · No integrations or discovered proposals for this Site. You can continue with manually entered knowledge.</p>}
      {!canViewIntegrations ? <p>Discovery run status is unavailable with your current permissions.</p>
        : runError ? <p role="alert" className="error-banner">{runError}</p>
        : !visibleIntegrations ? <p role="status">Loading discovery status…</p>
        : visibleIntegrations.length ? <ul className={styles.proposalList}>{visibleIntegrations.map(integration => <li key={integration.id} className={styles.proposalHeading}>
          <strong>{integration.name}</strong>
          <span>{integration.run ? <>
            <StatusIndicator state={integration.run.status === "pending" ? "queued" : integration.run.status} />
            {integration.run.observation_count != null && <> · {integration.run.observation_count} {integration.run.observation_count === 1 ? "observation" : "observations"}</>}
          </> : "No discovery run recorded"}</span>
        </li>)}</ul> : !empty && <p>No active integrations are configured for this Site.</p>}
      {integrations?.length === 500 && <p>Showing status for up to 500 configured integration records.</p>}
      {summary?.active_runs > 0 && <p>{summary.active_runs} {summary.active_runs === 1 ? "run is" : "runs are"} queued or running. You can review available proposals while discovery continues.</p>}
    </Section>
    {error && <p role="alert" className="error-banner">{error}</p>}
    {notice && <div ref={feedback} tabIndex={-1} role={notice.error ? "alert" : "status"}
      className={notice.error ? "error-banner" : notice.warning ? "warning-banner" : "status-banner"}>
      {notice.result ? <><strong>Batch result</strong><BatchResult result={notice.result} /></> : notice.message || notice.error || notice.warning}
    </div>}
    {busy && <p role="status">Recording reconciliation decisions…</p>}
    {!busy && recoveryIds.length > 0 && <div className="warning-banner" role="status">
      <p>{recoveryIds.length} {recoveryIds.length === 1 ? "proposal has" : "proposals have"} an unconfirmed request. Another decision on an affected proposal is paused in this browser session.</p>
      {resolvedIds.length > 0 && <p>Current Atlas records show {resolvedIds.length} resolved. The original request outcome is still unknown.</p>}
      {Object.entries(page?.decisions || {}).some(([, status]) => !closedStates.has(status)) &&
        <p>Some affected proposals still have a recorded open or deferred status.</p>}
      <div className={styles.actions}>
        <Button disabled={unavailable} onClick={() => load(filters, { recover: true })}>Check proposal status</Button>
        {resolvedIds.length > 0 && <Button disabled={unavailable} onClick={() => updateUncertain(resolvedIds, false)}>Dismiss resolved notices</Button>}
      </div>
    </div>}
    {selected && !latest && hasReviewAccess && <p role="status">The open proposal is outside the current results. Refresh or adjust the filters to find its latest state.</p>}
    {!page && !error && <p role="status">Loading proposals…</p>}
    {page && !hasReviewAccess && <p>Reconciliation proposals are unavailable with your current permissions.</p>}
    {hasReviewAccess && <>
      <p role="status">{outstanding} outstanding across this Site · {summary.eligible} eligible · {summary.needs_review} requiring review · {summary.accepted} proposals already accepted</p>
      {outstanding > 0 && <SearchFilterBar label="Search entities" search={search}
        activeCount={Number(Boolean(filters.source)) + Number(Boolean(filters.category))}
        onClear={() => { search.reset(); setFilters(emptyReviewFilters); }}>
        <label className="field">Integration or source<select value={filters.source} onChange={event => setFilters(old => ({ ...old, source: event.target.value, offset: 0 }))}>
          <option value="">All sources</option>
          {filters.source && !page.sources[filters.source] && <option value={filters.source}>Previously selected source</option>}
          {Object.entries(page.sources).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select></label>
        <label className="field">Proposal type<select value={filters.category} onChange={event => setFilters(old => ({ ...old, category: event.target.value, offset: 0 }))}>
          <option value="">All types</option>
          {[...new Set([filters.category, ...page.categories].filter(Boolean))].map(category => <option key={category} value={category}>{categoryLabel(category)}</option>)}
        </select></label>
      </SearchFilterBar>}
      {outstanding > 0 && <p>Showing {page.items.length} of {page.eligible + page.needs_review} matching proposals.</p>}
      <Section title="Eligible proposals" heading="h3" actions={ready.length > 0 &&
        <Button variant="primary" disabled={unavailable || !batch.items.length} onClick={() => confirm({ batch })}>Accept all eligible on this page</Button>}>
        <p>{ready.length} shown · {page.eligible} matching</p>
        {ready.length ? list(ready) : <p>No eligible proposals on this page.</p>}
      </Section>
      <Section title="Needs review" heading="h3">
        <p>{exceptions.length} shown · {page.needs_review} matching</p>
        {exceptions.length ? list(exceptions) : <p>No exceptional or blocked proposals on this page.</p>}
      </Section>
      <ReconciliationPagination pageIndex={filters.offset / REVIEW_PAGE_SIZE}
        hasMore={filters.offset + page.items.length < page.eligible + page.needs_review} busy={unavailable}
        onPrevious={() => setFilters(old => ({ ...old, offset: old.offset - REVIEW_PAGE_SIZE }))}
        onNext={() => setFilters(old => ({ ...old, offset: old.offset + REVIEW_PAGE_SIZE }))} />
    </>}
    {canManage && canAdvance && <div className={styles.actions}>
      <Button disabled={unavailable} onClick={() => decideStage("skipped")}>Skip Discovery Review</Button>
      <Button variant="primary" disabled={unavailable || !summary}
        onClick={() => requiresReviewAcknowledgement(summary) ? confirm({ summary }) : decideStage("completed", summary.version)}>
        Continue to Link Services
      </Button>
    </div>}
    <dialog className="dialog-card" ref={dialog} aria-labelledby="discovery-review-confirm-title" onClose={() => setConfirmation(null)}>
      {confirmation && <form onSubmit={submitConfirmation}>
        <h3 id="discovery-review-confirm-title">{confirmation.batch ? "Confirm eligible proposals"
          : confirmation.retirement ? "Confirm asset retirement" : "Continue with outstanding work"}</h3>
        {confirmation.batch && <>
          <p>Accept {confirmation.batch.items.length} reviewed proposals on page {confirmation.batch.page} for {confirmation.batch.siteName}.</p>
          <p>{confirmation.batch.source || "Selected source"}
            {confirmation.batch.category && <> · {categoryLabel(confirmation.batch.category)}</>}
            {confirmation.batch.search && <> · Search “{confirmation.batch.search}”</>}</p>
          <ul>{Object.entries(confirmation.batch.categories).map(([kind, count]) => <li key={kind}>{count} {categoryLabel(kind)}</li>)}</ul>
          {confirmation.batch.associations.length > 0 && <>
            <p>These proposals will associate with existing assets.</p>
            <ul>{confirmation.batch.associations.map(item => <li key={item.id}>{item.proposal} → {item.target}</li>)}</ul>
          </>}
          <p>{confirmation.batch.excluded} matching proposals need individual review. {confirmation.batch.outside} other matching eligible proposals are outside this batch or have an unconfirmed request.</p>
          <p>Atlas rechecks each selected proposal. Proposals that arrive or become eligible later need separate approval.</p>
        </>}
        {confirmation.retirement && <p>Retire {confirmation.retirement.entity_name} in Atlas? This changes the asset’s recorded lifecycle.</p>}
        {confirmation.summary && <>
          {confirmation.summary.eligible === null ? <p>Outstanding proposal counts are unavailable.</p>
            : <p>{confirmation.summary.eligible + confirmation.summary.needs_review} outstanding proposals will remain available for later review.</p>}
          {confirmation.summary.active_runs === null ? <p>Active discovery status is unavailable.</p>
            : confirmation.summary.active_runs > 0 ? <p>{confirmation.summary.active_runs} queued or running discovery {confirmation.summary.active_runs === 1 ? "job" : "jobs"} can finish independently.</p> : null}
          <p>You can return to Discovery Review after continuing.</p>
        </>}
        <div className="form-actions">
          <Button autoFocus onClick={() => dialog.current.close()}>Cancel</Button>
          <Button variant={confirmation.retirement ? "destructive" : "primary"} type="submit" disabled={unavailable}>
            {confirmation.batch ? "Confirm batch acceptance" : confirmation.retirement ? "Confirm retirement" : "Acknowledge and continue"}
          </Button>
        </div>
      </form>}
    </dialog>
  </div>;
}
