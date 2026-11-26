"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "../lib/api";
import { requestConnectorAction } from "../lib/connector-actions";
import { connectorState, filterConnectors, officialCatalogueBlocked, officialCatalogueDiagnostic, officialCatalogueRequestError, orderConnectorCards, readOfficialCatalogueStatus, reconcileConnectorCatalogue } from "../lib/integrations.mjs";
import { resolveStatus } from "../lib/status.mjs";
import { Button } from "./button";
import { ConnectorCard, OfficialCataloguePanel } from "./integration-panels";
import { CatalogueFilters, useCatalogueSearch } from "./catalogue-filters";
import { EmptyState, Section } from "./section";

export function OfficialCatalogue({ canViewOfficial, canManage, styles, catalogue, localLoading, localError, busy, onAction, onInstalled, configuration }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [selection, setSelection] = useState(null);
  const [installing, setInstalling] = useState(false);
  const [installError, setInstallError] = useState("");
  const dialog = useRef(null);
  const installedFocus = useRef(null);
  const cards = useRef(null);
  const operation = useRef(null);
  const generation = useRef(0);
  const [query, setQuery] = useState("");
  const [state, setState] = useState("");
  const search = useCatalogueSearch(query, setQuery);
  const installed = [...(canViewOfficial ? catalogue?.installed_entries || [] : [])];
  for (const form of configuration?.forms || []) {
    if (!installed.some(entry => entry.connector_id === form.connector_id)) {
      const local = catalogue?.entries?.find(entry => entry.connector_id === form.connector_id && entry.version === form.version);
      installed.push({ ...local, ...form, source: local ? "bootstrap" : "installed", installed: true,
        description: local?.description || "Available for configuration through the installed package." });
    }
  }
  const entries = reconcileConnectorCatalogue(catalogue?.entries, canViewOfficial ? status : null, installed);
  const visible = orderConnectorCards(filterConnectors(entries, query, state));
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
  useEffect(() => {
    if (!installedFocus.current || installing || localLoading) return;
    const card = [...(cards.current?.children || [])].find(item => item.dataset.connectorId === installedFocus.current);
    (card?.querySelector("[data-configure]") || card?.querySelector("[tabindex]"))?.focus();
    installedFocus.current = null;
  }, [configuration, installing, localLoading]);

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

  function review(entry, action) {
    const selected = action || (entry.installSelection && {
      path: `/integration-catalogue/${encodeURIComponent(entry.connector_id)}/install`,
      method: "POST", body: entry.installSelection,
    });
    if (!canManage || installing || busy || !selected || (!action && (operation.current || error))) return;
    setSelection({ entry, action: selected }); setInstallError(""); dialog.current.showModal();
  }

  async function install(event) {
    event.preventDefault();
    if (!canManage || installing || !selection || operation.current) return;
    const controller = new AbortController();
    operation.current = controller;
    setInstalling(true); setInstallError("");
    try {
      await requestConnectorAction(selection.action, controller.signal);
      if (controller.signal.aborted) return;
      if (configuration) installedFocus.current = selection.entry.connector_id;
      dialog.current.close(); setSelection(null);
      operation.current = null;
      if (canViewOfficial) await reload();
      await onInstalled?.();
    } catch (failure) {
      if (!controller.signal.aborted) setInstallError(failure.status === 403 ? "You do not have permission to install Connectors." : "Installation was unsuccessful. Reload the catalogue and review the selected package before trying again.");
    } finally { operation.current = null; setInstalling(false); }
  }

  async function reloadDisplayed() {
    await onInstalled?.();
    if (canViewOfficial) await reload();
  }
  const reviewed = selection?.entry;
  const packageUpdate = selection?.action.action === "update" || Boolean(reviewed?.installed_version);
  return <>
    {!configuration && canViewOfficial && <OfficialCataloguePanel status={status} loading={loading} refreshing={refreshing} error={error} feedback={feedback} canManage={canManage} onRefresh={refresh} onReload={reload} styles={styles} />}
    {!configuration && <CatalogueFilters label="Search Connectors" search={search} activeCount={state ? 1 : 0} onClear={() => { search.reset(); setQuery(""); setState(""); }}><label className="field"><span>Package state</span><select value={state} onChange={event => setState(event.target.value)}><option value="">All states</option>{states.map(value => <option key={value} value={value}>{resolveStatus(value).label}</option>)}</select></label></CatalogueFilters>}
    <Section title={configuration ? "Available connectors" : "Connector catalogue"} heading={configuration ? "h3" : "h2"} className={styles.section}
      actions={<Button variant="quiet" loading={localLoading || (!configuration && canViewOfficial && loading)} disabled={installing || (!configuration && refreshing) || Boolean(busy)} onClick={reloadDisplayed}>{configuration ? "Reload connectors" : "Reload displayed catalogue"}</Button>}>
      {configuration && canViewOfficial && <OfficialCataloguePanel status={status} loading={loading} refreshing={refreshing} error={error} feedback={feedback} canManage={canManage} onRefresh={refresh} onReload={reload} styles={styles} compact />}
      {configuration && localError && <p className="error-banner" role="alert">{localError}</p>}
      {localLoading && !entries.length ? <div className="status-banner" role="status">Loading Connector catalogue…</div> : visible.length > 0 ? <div className={styles.grid} ref={cards}>{visible.map(entry => {
        const form = configuration?.forms.find(item => item.connector_id === entry.connector_id);
        const local = configuration && catalogue?.entries?.find(item => item.connector_id === entry.connector_id);
        const limitation = !form && entry.installed_version ? local?.state === "update_requires_configuration"
          ? local.message : "The installed connector has no available configuration form. Check package verification and mappings."
          : form && !form.capabilities?.test_connection ? "This installed connector does not support a connection test." : null;
        return <ConnectorCard key={entry.connector_id} entry={entry} className={styles.card} styles={styles} canManage={canManage}
          configuration={configuration && { local, limitation, needsForm: !form, configure: form?.capabilities?.test_connection && configuration.canConfigure ? () => configuration.open(form) : undefined }}
          busy={busy || (installing ? "installation" : "")} onAction={configuration ? review : onAction}
          onInstall={entry => review(entry)} installBlocked={loading || refreshing || Boolean(error) || Boolean(status?.last_error_code || status?.source_conflict || status?.refresh_state === "failed")} />;
      })}</div> : !localError && <EmptyState title={configuration ? "No connectors available" : "No matching Connectors"} description={configuration ? undefined : "Clear your filters to view the catalogue."} />}
    </Section>
    <dialog ref={dialog} className="dialog-card" aria-labelledby="official-install-title" onCancel={event => { if (installing) event.preventDefault(); }} onClose={() => { if (!installing) setSelection(null); }}>
      <form onSubmit={install}>
        <h2 id="official-install-title">{configuration && packageUpdate ? "Update" : "Install"} {reviewed?.name}</h2>
        <p>Review this exact package before activating it in the local runtime.</p>
        {configuration && <p>Package activation applies to the entire Atlas instance.</p>}
        <dl className="ops-definition"><dt>Connector identity</dt><dd>{reviewed?.connector_id}</dd><dt>Version</dt><dd>{reviewed?.version}</dd>
          {configuration && <><dt>Publisher</dt><dd>{reviewed?.publisher || "Not specified"}</dd><dt>Source</dt><dd>{reviewed?.source === "official" ? "Official catalogue" : "Bundled catalogue"}</dd>
            <dt>Verification</dt><dd>{reviewed?.source === "official" ? "Package verified during installation" : "Bundled package verified"}</dd>
            {reviewed?.source_versions?.qualification && <><dt>Source qualification</dt><dd>{reviewed.source_versions.qualification.replaceAll("_", " ")}</dd></>}
            <dt>Compatibility</dt><dd>{reviewed?.source === "official" ? "Checked before activation" : reviewed?.message || "Compatible with the local runtime"}</dd></>}
          {reviewed?.installSelection && <><dt>Catalogue sequence</dt><dd>{reviewed.installSelection.catalogue_sequence}</dd><dt>Catalogue SHA-256</dt><dd className="mono">{reviewed.installSelection.catalogue_digest}</dd><dt>Release asset</dt><dd>{reviewed.installSelection.release_asset_id}</dd></>}
          <dt>Package SHA-256</dt><dd className="mono">{selection?.action.body.digest}</dd></dl>
        <label className="field checkbox-field"><input type="checkbox" required disabled={installing} key={selection?.action.body.digest} /><span>I confirm {configuration && packageUpdate ? "activation" : "installation"} of this package.</span></label>
        {installError && <p role="alert" className="error-banner">{installError}</p>}
        <div className="form-actions"><Button autoFocus type="button" disabled={installing} onClick={() => dialog.current.close()}>Cancel</Button><Button type="submit" variant="primary" loading={installing} disabled={installing}>Verify and install</Button></div>
      </form>
    </dialog></>;
}
