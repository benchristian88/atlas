"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "../lib/api";
import {
  MAPPING_PAGE_SIZE, MAPPING_SELECTION_LIMIT, mappingAssetContext, mappingPagePath, readUnconfirmedMapping,
  remainingMappingSelection, requiresMappingAcknowledgement, storeUnconfirmedMapping,
  submitMappingActions, toggleMappingAsset,
} from "../lib/onboarding-link-services.mjs";
import { Button } from "./button";
import { useCatalogueSearch } from "./catalogue-filters";
import { AssetIdentity, ServiceIdentity } from "./entity-identity";
import { FilterToolbar } from "./filter-toolbar";
import { ReconciliationPagination } from "./reconciliation-cards";
import { StatusIndicator } from "./status-indicator";
import styles from "./onboarding.module.css";

const request = (path, options) => apiRequest(path, { ...options, omitContext: true });
const blankServiceFilters = { search: "", mapping: "all", offset: 0 };
const blankAssetFilters = { search: "", asset_type: "", offset: 0 };

function useMappingRead(path) {
  const [result, setResult] = useState(null);
  const [loadingPath, setLoadingPath] = useState(null);
  const previous = useRef(null);
  const controller = useRef(null);
  const latestPath = useRef(path);
  latestPath.current = path;
  const load = useCallback(async () => {
    const path = latestPath.current;
    controller.current?.abort();
    const read = new AbortController();
    controller.current = read;
    setLoadingPath(path);
    try {
      const data = await request(path, { signal: read.signal });
      if (!read.signal.aborted) {
        previous.current = data;
        setResult({ path, data });
        return data;
      }
    } catch (error) {
      if (!read.signal.aborted) {
        previous.current = null;
        setResult({ path, error });
      }
    } finally {
      if (!read.signal.aborted) setLoadingPath(null);
    }
    return null;
  }, []);
  useEffect(() => {
    load();
    return () => controller.current?.abort();
  }, [load, path]);
  const current = result?.path === path ? result : null;
  const loading = !current || loadingPath === path;
  return { data: loading ? previous.current : current.data, loading, error: current?.error, load };
}

function MappingReadStatus({ error, load, label, disabled }) {
  const alert = useRef(null);
  useEffect(() => { if (error) alert.current?.focus(); }, [error]);
  return error ? <div>
    <p ref={alert} tabIndex={-1} role="alert" className="error-banner">{label} could not be loaded. {error.message}</p>
    <Button disabled={disabled} onClick={load}>Reload {label.toLowerCase()}</Button>
  </div> : <p role="status">Loading {label.toLowerCase()}…</p>;
}

function MappingFilters({ label, filters, setFilters, initial, search, disabled, children }) {
  return <fieldset disabled={disabled} className={styles.mappingFilters}>
    <legend className="sr-only">{label} filters</legend>
    <FilterToolbar onSubmit={event => event.preventDefault()}>
      <label className="field">
        <span>{label}</span>
        <input type="search" maxLength={300} value={search.draft} onChange={event => search.change(event.target.value)} />
      </label>
      {children}
      {(search.draft || Object.keys(initial).some(key => key !== "offset" && initial[key] !== filters[key])) &&
        <Button variant="quiet" onClick={() => { search.reset(); setFilters(initial); }}>Clear filters</Button>}
    </FilterToolbar>
  </fieldset>;
}

function useMappingSearch(filters, setFilters) {
  return useCatalogueSearch(filters.search, search => setFilters(previous => ({ ...previous, search, offset: 0 })));
}

function MappingPagination({ label, page, filters, setFilters, disabled }) {
  useEffect(() => {
    if (!disabled && filters.offset && !page.has_more && !(page.services || page.available)?.length) {
      setFilters(previous => ({ ...previous, offset: 0 }));
    }
  }, [disabled, filters.offset, page, setFilters]);
  return <ReconciliationPagination label={label} pageIndex={filters.offset / MAPPING_PAGE_SIZE}
    hasMore={page.has_more} busy={disabled}
    onPrevious={() => setFilters(previous => ({ ...previous, offset: previous.offset - MAPPING_PAGE_SIZE }))}
    onNext={() => setFilters(previous => ({ ...previous, offset: previous.offset + MAPPING_PAGE_SIZE }))} />;
}

function Confirmation({ confirmation, label, onCancel, onConfirm, children, confirmLabel, destructive }) {
  const dialog = useRef(null);
  useEffect(() => {
    if (confirmation && !dialog.current.open) dialog.current.showModal();
  }, [confirmation]);
  return <dialog className="dialog-card" ref={dialog} aria-label={label} onClose={onCancel}>
    {confirmation && <form onSubmit={event => {
      event.preventDefault();
      dialog.current.close();
      onConfirm(confirmation);
    }}>
      <h3>{label}</h3>
      {children}
      <div className="form-actions">
        <Button autoFocus onClick={() => dialog.current.close()}>Cancel</Button>
        <Button type="submit" variant={destructive ? "destructive" : "primary"}>{confirmLabel}</Button>
      </div>
    </form>}
  </dialog>;
}

function MappingAssetText({ asset, relationship, site }) {
  const details = [mappingAssetContext(asset), relationship, site].filter(Boolean);
  return <span className={styles.mappingAssetText}>
    <strong>{asset.name}</strong><small>{details.join(" · ")}</small>
  </span>;
}

function mappingAssetName(asset) {
  return [asset.name, mappingAssetContext(asset)].join(" · ");
}

function LinkedAssets({ title, mappings, canRemove, onRemove, disabled }) {
  return <section>
    <h4>{title}</h4>
    {mappings === null ? <p>Mapping visibility is restricted for this scope.</p>
      : !mappings.length ? <p>{canRemove !== undefined ? "No mappings at the selected Site."
        : "No visible mappings at other Sites."}</p>
        : <ul className={styles.mappingList}>
          {mappings.map(item => <li key={item.id} className={styles.mappingRow}>
            <AssetIdentity record={item.asset} size={24} />
            <div>
              <MappingAssetText asset={item.asset} relationship={item.relationship_name}
                site={canRemove === undefined ? item.site_name : undefined} />
              {item.asset.status === "retired" && <StatusIndicator state="retired" variant="lifecycle" />}
            </div>
            {canRemove && item.removal_version && <Button variant="quiet" aria-label={`Remove ${mappingAssetName(item.asset)} mapping`}
              disabled={disabled} onClick={() => onRemove(item)}>Remove</Button>}
          </li>)}
        </ul>}
  </section>;
}

const outcomeLabels = {
  added: "Added", already_exists: "Already linked", rejected: "Rejected",
  unconfirmed: "Unconfirmed", removed: "Removed",
};

function ServiceMappings({ path, service, actor, canManage, blocked, onBusy, reloadServices }) {
  const [filters, setFilters] = useState(blankAssetFilters);
  const [selection, setSelection] = useState([]);
  const [confirmation, setConfirmation] = useState(null);
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState(null);
  const [recovery, setRecovery] = useState("");
  const storageKey = `atlas-link-services:${actor}:${path}`;
  const [unconfirmed, setUnconfirmed] = useState(() => readUnconfirmedMapping(storageKey));
  const pending = useRef(false);
  const heading = useRef(null);
  const feedback = useRef(null);
  const read = useMappingRead(mappingPagePath(path, filters));
  const search = useMappingSearch(filters, setFilters);
  const data = read.data;
  const canChange = canManage && data?.can_manage;
  const disabled = blocked || busy;
  const inputsDisabled = disabled || read.loading || Boolean(unconfirmed) || search.draft.trim() !== filters.search;

  useEffect(() => { heading.current?.focus(); }, []);
  useEffect(() => {
    if (outcome || recovery) feedback.current?.focus();
  }, [outcome, recovery]);

  function mark(marker) {
    storeUnconfirmedMapping(storageKey, marker);
    setUnconfirmed(marker);
  }

  async function mutate(command) {
    if (pending.current || inputsDisabled || !canChange) return;
    pending.current = true;
    setBusy(true);
    onBusy(true);
    setOutcome(null);
    setRecovery("");
    try {
      const result = await submitMappingActions(path, command, request, mark);
      const [latest] = await Promise.all([read.load(), reloadServices()]);
      setSelection(previous => remainingMappingSelection(previous, result.results, latest?.site_mappings));
      setOutcome(result);
    } finally {
      pending.current = false;
      setBusy(false);
      onBusy(false);
    }
  }

  async function checkCurrentMappings() {
    if (pending.current || blocked) return;
    pending.current = true;
    setBusy(true);
    onBusy(true);
    setRecovery("");
    try {
      const [latest] = await Promise.all([read.load(), reloadServices()]);
      if (latest?.site_mappings) {
        setSelection(previous => remainingMappingSelection(previous, [], latest.site_mappings));
        mark(null);
        setRecovery("Current saved mappings refreshed. Check the linked Assets before making another change.");
      } else {
        setRecovery("Current mappings could not be verified. Reload them to check the pending request.");
      }
    } finally {
      pending.current = false;
      setBusy(false);
      onBusy(false);
    }
  }

  return <section className={styles.mappingDetail} aria-labelledby="selected-link-service">
    <h3 ref={heading} tabIndex={-1} id="selected-link-service">{data?.service_name || service.name}</h3>
    {(outcome || recovery) && <div className={styles.mappingFeedback} ref={feedback} tabIndex={-1}
      role={outcome?.results.some(item => ["rejected", "unconfirmed"].includes(item.status)) ? "alert" : "status"}>
      {outcome && <>
        <ul>{outcome.results.map(item => <li key={item.id}>
          {outcomeLabels[item.status]} · {mappingAssetName(item)}{item.reason && ` · ${item.reason}`}
        </li>)}</ul>
        {outcome.unsubmitted > 0 && <p>{outcome.unsubmitted} selected Assets still await submission.</p>}
      </>}
      {recovery && <p>{recovery}</p>}
    </div>}
    {unconfirmed && !busy && <div>
      <p className="error-banner" role="alert">A mapping request has an unconfirmed outcome. Check the current saved mappings before trying again.</p>
      <Button disabled={disabled} onClick={checkCurrentMappings}>Check current mappings</Button>
    </div>}
    {!data ? <MappingReadStatus {...read} label="Asset mappings" disabled={disabled} /> : <>
      {read.loading && <p role="status">Refreshing Asset mappings…</p>}
      <LinkedAssets title="Linked Assets at this Site" mappings={data.site_mappings}
        canRemove={Boolean(canChange)} disabled={inputsDisabled}
        onRemove={item => setConfirmation({
          kind: "remove", mappingId: item.id, removalVersion: item.removal_version, assets: [item.asset],
          relationshipName: item.relationship_name, serviceName: data.service_name,
        })} />
      <LinkedAssets title="Linked Assets at other Sites · read-only" mappings={data.other_mappings} />
      {!canChange ? <p>Read-only mapping access. Site setup management, Service dependency management and view access are required to change mappings.</p> : <section>
        <h4>Available Assets</h4>
        <MappingFilters label="Search Assets" initial={blankAssetFilters} filters={filters}
          setFilters={setFilters} search={search} disabled={disabled}>
          <label className="field"><span>Asset Type</span>
            <select value={filters.asset_type} onChange={event => setFilters(previous => ({ ...previous, asset_type: event.target.value, offset: 0 }))}>
              <option value="">All Asset Types</option>
              {data.asset_types.map(item => <option key={item.key} value={item.key}>{item.name}</option>)}
            </select>
          </label>
        </MappingFilters>
        {data.available.length ? <ul className={styles.mappingList}>
          {data.available.map(asset => {
            const checked = selection.some(item => item.id === asset.id);
            return <li key={asset.id}><label className={styles.mappingRow}>
              <input type="checkbox" checked={checked}
                disabled={inputsDisabled || (!checked && selection.length >= MAPPING_SELECTION_LIMIT)}
                onChange={() => setSelection(previous => toggleMappingAsset(previous, asset))} />
              <AssetIdentity record={asset} size={24} />
              <MappingAssetText asset={asset} />
            </label></li>;
          })}
        </ul> : <p>{!data.has_eligible_assets ? "No available Assets at this Site."
          : !data.has_unlinked_assets ? "All available Assets are already linked to this Service."
            : "No matching Assets."}</p>}
        <MappingPagination label="Available Asset pages" page={data} filters={filters} setFilters={setFilters} disabled={disabled || read.loading} />
        <div className={styles.actions}>
          <span role="status">{selection.length} selected{selection.length >= MAPPING_SELECTION_LIMIT && ` (limit ${MAPPING_SELECTION_LIMIT})`}</span>
          {selection.length > 0 && <Button variant="quiet" disabled={inputsDisabled} onClick={() => setSelection([])}>Clear selection</Button>}
          <Button variant="primary" disabled={inputsDisabled || !selection.length}
            onClick={() => setConfirmation({ kind: "add", assets: [...selection], serviceName: data.service_name })}>Add selected Assets</Button>
        </div>
        {selection.length > 0 && <>
          <details>
            <summary>Review selection</summary>
            <ul className={styles.mappingList}>{selection.map(asset => <li key={asset.id} className={styles.mappingRow}>
              <div><MappingAssetText asset={asset} /></div>
              <Button variant="quiet" aria-label={`Deselect ${mappingAssetName(asset)}`} disabled={inputsDisabled}
                onClick={() => setSelection(previous => toggleMappingAsset(previous, asset))}>Deselect</Button>
            </li>)}</ul>
          </details>
          <p className={styles.manualContinuation}>Unsubmitted selections are cleared when you change Services or leave this step.</p>
        </>}
      </section>}
    </>}
    <Confirmation confirmation={confirmation} label={confirmation?.kind === "remove" ? "Remove mapping" : "Add Asset mappings"}
      onCancel={() => setConfirmation(null)} onConfirm={mutate} destructive={confirmation?.kind === "remove"}
      confirmLabel={confirmation?.kind === "remove" ? "Confirm removal" : "Confirm add"}>
      {confirmation && <>
        {confirmation.kind === "remove"
          ? <p>Remove the <strong>{confirmation.relationshipName}</strong> mapping from <strong>{confirmation.serviceName}</strong> to this Asset?</p>
          : <p>Add these Assets to <strong>{confirmation.serviceName}</strong>.</p>}
        <ul>{confirmation.assets.map(asset => <li key={asset.id}><MappingAssetText asset={asset} /></li>)}</ul>
      </>}
    </Confirmation>
  </section>;
}

export function OnboardingLinkServices({ path, actor, canManage, canAdvance, blocked, onBusy, onDecision }) {
  const [filters, setFilters] = useState(blankServiceFilters);
  const [selected, setSelected] = useState(null);
  const [confirmContinue, setConfirmContinue] = useState(false);
  const [progressNotice, setProgressNotice] = useState("");
  const progressFeedback = useRef(null);
  const linkPath = `${path}/link-services`;
  const read = useMappingRead(mappingPagePath(linkPath, filters));
  const search = useMappingSearch(filters, setFilters);
  const page = read.data;
  const summary = page?.summary;
  const restricted = summary?.unavailable > 0 && summary.linked + summary.unlinked === 0;
  const needsAttention = requiresMappingAcknowledgement(read.loading ? null : summary);

  useEffect(() => { if (progressNotice) progressFeedback.current?.focus(); }, [progressNotice]);

  async function continueSetup(acknowledge) {
    const result = await onDecision("continue", acknowledge);
    if (result?.refreshMappings) {
      setProgressNotice("Mapping status changed. Review the latest counts before continuing.");
      await read.load();
    }
  }

  return <div className={styles.linkServices}>
    <p>Link your Services to the Assets that support them. You can connect multiple Assets to a Service, and an Asset can support multiple Services. You can complete remaining mappings later.</p>
    {summary && <dl className={styles.mappingSummary} aria-label="Saved mapping progress">
      <div><dt>Services linked</dt><dd>{restricted ? "Unavailable" : summary.linked}</dd></div>
      <div><dt>Services unlinked</dt><dd>{restricted ? "Unavailable" : summary.unlinked}</dd></div>
      <div><dt>Asset mappings</dt><dd>{restricted ? "Unavailable" : summary.mappings}</dd></div>
    </dl>}
    {summary?.unavailable > 0 && <p>{summary.unavailable} Services have restricted mapping status. Counts include mappings you can view at this Site.</p>}
    {page && !summary && <p>Service inventory is unavailable with your current permissions.</p>}
    <div className={styles.mappingGrid}>
      <section aria-labelledby="link-services-list">
        <h3 id="link-services-list">Services</h3>
        {page && read.loading && <p role="status">Refreshing Services…</p>}
        {page && summary && <>
          <MappingFilters label="Search Services" filters={filters} setFilters={setFilters}
            initial={blankServiceFilters} search={search} disabled={blocked}>
            <label className="field"><span>Mapping status</span>
              <select value={filters.mapping} onChange={event => setFilters(previous => ({ ...previous, mapping: event.target.value, offset: 0 }))}>
                <option value="all">All Services</option><option value="unlinked">Unlinked</option><option value="linked">Linked</option>
              </select>
            </label>
          </MappingFilters>
          {page.services.length ? <ul className={styles.mappingList}>
            {page.services.map(service => <li key={service.id}>
              <Button variant="quiet" className={styles.mappingService} aria-pressed={selected?.id === service.id}
                disabled={blocked || read.loading} onClick={() => setSelected({ id: service.id, name: service.name })}>
                <ServiceIdentity record={service} size={24} />
                <span><strong>{service.name}</strong>
                  <small>{service.site_id ? "This Site" : "Customer-wide"} · {service.mapping_count === null ? "Mapping status unavailable"
                    : `${service.mapping_count} ${service.mapping_count === 1 ? "mapping" : "mappings"} at this Site`}</small></span>
              </Button>
            </li>)}
          </ul> : <p>{summary.linked + summary.unlinked + summary.unavailable === 0 ? "No authorised Services in this setup." : "No matching Services."}</p>}
          <MappingPagination label="Service pages" page={page} filters={filters} setFilters={setFilters} disabled={blocked || read.loading} />
        </>}
        {!page && <MappingReadStatus {...read} label="Services" disabled={blocked} />}
      </section>
      {selected && <ServiceMappings key={selected.id} actor={actor} service={selected}
        path={`${linkPath}/services/${selected.id}`} canManage={canManage}
        blocked={blocked} onBusy={onBusy} reloadServices={read.load} />}
      {!selected && page?.services.length > 0 && <p>Choose a Service to view its Asset mappings.</p>}
    </div>
    {progressNotice && <p ref={progressFeedback} tabIndex={-1} role="alert">{progressNotice}</p>}
    {canManage && canAdvance && <div className={styles.actions}>
      <Button onClick={() => onDecision("skip")} disabled={blocked}>Skip</Button>
      <Button variant="primary" onClick={() => needsAttention ? setConfirmContinue(true) : continueSetup(false)}
        disabled={blocked}>Continue to Review &amp; Ready</Button>
    </div>}
    <Confirmation confirmation={confirmContinue} label="Continue Link Services" onCancel={() => setConfirmContinue(false)}
      onConfirm={() => continueSetup(true)} confirmLabel="Acknowledge and continue">
      {summary?.unlinked > 0 && <p>{summary.unlinked} Services still have no Asset mappings at this Site.</p>}
      {(!summary || summary.unavailable > 0) && <p>Some mapping status is unavailable.</p>}
      <p>You can return to Link Services to finish the remaining mappings.</p>
    </Confirmation>
  </div>;
}
