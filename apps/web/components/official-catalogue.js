"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "../lib/api";
import { officialCatalogueBlocked, officialCatalogueDiagnostic, officialCatalogueRequestError, readOfficialCatalogueStatus } from "../lib/integrations.mjs";
import { Button } from "./button";
import { OfficialCataloguePanel } from "./integration-panels";

export function OfficialCatalogue({ canManage, styles, onInstalled }) {
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
    reload();
    return () => { generation.current += 1; operation.current?.abort(); operation.current = null; };
  }, [reload]);

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
    if (!canManage || installing || operation.current || !entry.installSelection) return;
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

  return <><OfficialCataloguePanel status={status} loading={loading} refreshing={refreshing} error={error} feedback={feedback} canManage={canManage} onRefresh={refresh} onReload={reload} onInstall={review} installing={installing} styles={styles} />
    <dialog ref={dialog} className="dialog-card" aria-labelledby="official-install-title" onCancel={event => { if (installing) event.preventDefault(); }} onClose={() => { if (!installing) setSelection(null); }}>
      <form onSubmit={install}>
        <h2 id="official-install-title">Install {selection?.name}</h2>
        <p>Review this exact package before activating it in the local runtime.</p>
        <dl className="ops-definition"><dt>Version</dt><dd>{selection?.version}</dd><dt>Catalogue sequence</dt><dd>{selection?.installSelection?.catalogue_sequence}</dd><dt>Package SHA-256</dt><dd className="mono">{selection?.installSelection?.digest}</dd></dl>
        <label className="field checkbox-field"><input type="checkbox" required disabled={installing} key={selection?.installSelection?.digest} /><span>I confirm installation of this package.</span></label>
        {installError && <p role="alert" className="error-banner">{installError}</p>}
        <div className="form-actions"><Button autoFocus type="button" disabled={installing} onClick={() => dialog.current.close()}>Cancel</Button><Button type="submit" variant="primary" loading={installing} disabled={installing}>Verify and install</Button></div>
      </form>
    </dialog></>;
}
