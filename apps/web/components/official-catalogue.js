"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "../lib/api";
import { connectorState, filterConnectors, officialCatalogueBlocked, officialCatalogueDiagnostic, officialCatalogueRequestError, readOfficialCatalogueStatus, reconcileConnectorCatalogue } from "../lib/integrations.mjs";
import { resolveStatus } from "../lib/status.mjs";
import { Button } from "./button";
import { ConnectorCard, OfficialCataloguePanel } from "./integration-panels";
import { CatalogueFilters, useCatalogueSearch } from "./catalogue-filters";
import { EmptyState, Section } from "./section";

export function OfficialCatalogue({ canViewOfficial, canManage, styles, catalogue, localLoading, localError, busy, onAction, onInstalled }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [selection, setSelection] = useState(null);
  const [installing, setInstalling] = useState(false);
  const [installError, setInstallError] = useState("");
  const dialog = useRef(null);
  const operation = useRef(null);
  const generation = useRef(0);
  const [query, setQuery] = useState("");
  const [state, setState] = useState("");
  const search = useCatalogueSearch(query, setQuery);
  const entries = reconcileConnectorCatalogue(catalogue?.entries, canViewOfficial ? status : null, canViewOfficial ? catalogue?.installed_entries : []);
  const visible = filterConnectors(entries, query, state);
  const states = [...new Set(entries.map(connectorState))];

  const reload = useCallback(async () => {
    if (operation.current) return;
    const controller = new AbortController();
    operation.current = controller;
    const current = ++generation.current;
    setLoading(true); setError("");
    try {
      const next = readOfficialCatalogueStatus(await apiRequest("/integration-catalogue/status", { omitContext: true, signal: controller.signal }));
      if (current === generation.current) { setStatus(next); setFeedback(null); }
    } catch (failure) {
      if (current === generation.current) {
        if ([401, 403].includes(failure.status)) { setStatus(null); setFeedback(null); }
        setError(officialCatalogueRequestError(failure));
      }
    } finally {
      if (current === generation.current) { operation.current = null; setLoading(false); }
    }
  }, []);

  useEffect(() => {
    if (canViewOfficial) reload();
    return () => { generation.current += 1; operation.current?.abort(); operation.current = null; };
  }, [reload, canViewOfficial]);

  async function refresh() {
    if (!canManage || !status || error || operation.current || officialCatalogueBlocked(status) || ["cooldown", "in_progress"].includes(feedback?.result)) return;
    const controller = new AbortController();
    operation.current = controller;
    const current = ++generation.current;
    setRefreshing(true); setFeedback(null); setError("");
    try {
      const response = await apiRequest("/integration-catalogue/refresh", { method: "POST", omitContext: true, signal: controller.signal });
      if (current !== generation.current) return;
      if (!["accepted", "unchanged", "in_progress", "cooldown", "failed"].includes(response?.result)) throw new Error("Unexpected refresh result");
      const next = response.status ? readOfficialCatalogueStatus(response.status, { requireEntries: false }) : null;
      if (response.result !== "failed" && !next) throw new Error("Missing refresh status");
      if (["accepted", "unchanged"].includes(response.result) && (!next.trusted_remote_available || next.refresh_state === "failed" || next.last_error_code || next.source_conflict)) throw new Error("Inconsistent refresh status");
      // Refresh returns checkpoint status only, never entries. Preserve existing
      // metadata until the independent GET supplies the complete projection.
      if (next) setStatus(previous => previous?.trusted_remote_available
        && (previous.sequence !== next.sequence || previous.content_digest !== next.content_digest)
        ? previous : { ...next, entries: previous?.entries || [] });
      const result = response.result;
      setFeedback({ result, message: {
        accepted: "Official catalogue verified and accepted.",
        unchanged: "Official catalogue verified; the accepted catalogue is unchanged.",
        in_progress: "An official catalogue check is already in progress. Reload status to see its result.",
        cooldown: "Official catalogue checks are temporarily unavailable. Reload status after the next permitted check time.",
        failed: officialCatalogueDiagnostic(next || { ...status, last_error_code: response.code }),
      }[result] });
      const complete = readOfficialCatalogueStatus(await apiRequest("/integration-catalogue/status", { omitContext: true, signal: controller.signal }));
      if (current === generation.current) setStatus(complete);
    } catch (failure) {
      if (current === generation.current) {
        if ([401, 403].includes(failure.status)) { setStatus(null); setFeedback(null); }
        setError(officialCatalogueRequestError(failure));
      }
    } finally {
      if (current === generation.current) { operation.current = null; setRefreshing(false); }
    }
  }

  function review(entry) {
    if (!canManage || installing || operation.current || busy || error || !entry.installSelection) return;
    setSelection(entry); setInstallError(""); dialog.current.showModal();
  }

  async function install(event) {
    event.preventDefault();
    if (!canManage || installing || !selection?.installSelection || operation.current) return;
    const controller = new AbortController();
    operation.current = controller;
    setInstalling(true); setInstallError("");
    try {
      await apiRequest(`/integration-catalogue/${encodeURIComponent(selection.connector_id)}/install`, {
        method: "POST", omitContext: true, signal: controller.signal,
        body: JSON.stringify(selection.installSelection),
      });
      dialog.current.close(); setSelection(null);
      operation.current = null;
      await reload();
      await onInstalled?.();
    } catch (failure) {
      setInstallError(failure.status === 403 ? "You do not have permission to install Connectors." : "Installation was unsuccessful. Reload the catalogue and review the selected package before trying again.");
    } finally { operation.current = null; setInstalling(false); }
  }

  async function reloadDisplayed() {
    await onInstalled?.();
    if (canViewOfficial) await reload();
  }
  return <>
    {canViewOfficial && <OfficialCataloguePanel status={status} loading={loading} refreshing={refreshing} error={error} feedback={feedback} canManage={canManage} onRefresh={refresh} onReload={reload} styles={styles} />}
    <CatalogueFilters label="Search Connectors" search={search} activeCount={state ? 1 : 0} onClear={() => { search.reset(); setQuery(""); setState(""); }}><label className="field"><span>Package state</span><select value={state} onChange={event => setState(event.target.value)}><option value="">All states</option>{states.map(value => <option key={value} value={value}>{resolveStatus(value).label}</option>)}</select></label></CatalogueFilters>
    <Section title="Connector catalogue" className={styles.section} actions={<Button variant="quiet" loading={localLoading || (canViewOfficial && loading)} disabled={refreshing || installing || Boolean(busy)} onClick={reloadDisplayed}>Reload displayed catalogue</Button>}>
      {localLoading && !catalogue ? <div className="status-banner" role="status">Loading Connector catalogue…</div> : visible.length > 0 ? <div className={styles.grid}>{visible.map(entry => <ConnectorCard key={entry.connector_id} entry={entry} className={styles.card} styles={styles} canManage={canManage} busy={busy || (installing ? "installation" : "")} onAction={onAction} onInstall={review} installBlocked={loading || refreshing || Boolean(error) || Boolean(status?.last_error_code || status?.source_conflict || status?.refresh_state === "failed")} />)}</div> : !localError && <EmptyState title="No matching Connectors" description="Clear your filters to view the catalogue." />}
    </Section>
    <dialog ref={dialog} className="dialog-card" aria-labelledby="official-install-title" onCancel={event => { if (installing) event.preventDefault(); }} onClose={() => { if (!installing) setSelection(null); }}>
      <form onSubmit={install}>
        <h2 id="official-install-title">Install {selection?.name}</h2>
        <p>Review this exact package before activating it in the local runtime.</p>
        <dl className="ops-definition"><dt>Connector identity</dt><dd>{selection?.connector_id}</dd><dt>Version</dt><dd>{selection?.version}</dd><dt>Catalogue sequence</dt><dd>{selection?.installSelection?.catalogue_sequence}</dd><dt>Catalogue SHA-256</dt><dd className="mono">{selection?.installSelection?.catalogue_digest}</dd><dt>Release asset</dt><dd>{selection?.installSelection?.release_asset_id}</dd><dt>Package SHA-256</dt><dd className="mono">{selection?.installSelection?.digest}</dd></dl>
        <label className="field checkbox-field"><input type="checkbox" required disabled={installing} key={selection?.installSelection?.digest} /><span>I confirm installation of this package.</span></label>
        {installError && <p role="alert" className="error-banner">{installError}</p>}
        <div className="form-actions"><Button autoFocus type="button" disabled={installing} onClick={() => dialog.current.close()}>Cancel</Button><Button type="submit" variant="primary" loading={installing} disabled={installing}>Verify and install</Button></div>
      </form>
    </dialog></>;
}
