"use client";

import { useState } from "react";
import { apiRequest } from "../lib/api";
import { StatusBadge } from "./status-badge";

function assertionValue(assertion, assetsById) {
  if (assertion.value_json !== null && assertion.value_json !== undefined) {
    return typeof assertion.value_json === "string"
      ? assertion.value_json
      : JSON.stringify(assertion.value_json);
  }
  return assertion.object_external_id
    || assetsById[assertion.object_id]?.name
    || assertion.object_id
    || "Unavailable";
}

function dateTime(value) {
  return value ? new Date(value).toLocaleString() : "—";
}

function displayStatus(assertion) {
  return assertion.retracted_at ? "Retracted" : assertion.confirmation_status;
}

export function AssertionsPanel({
  assertions,
  assetsById,
  canDelete,
  canRetract,
  onChanged,
}) {
  const [dialog, setDialog] = useState(null);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [requiresGapConfirmation, setRequiresGapConfirmation] = useState(false);
  const [gapAcknowledged, setGapAcknowledged] = useState(false);

  function openDialog(type, assertion) {
    setDialog({ type, assertion });
    setReason("");
    setError("");
    setRequiresGapConfirmation(Boolean(assertion.provenance_gap_warning));
    setGapAcknowledged(false);
  }

  function closeDialog() {
    if (saving) return;
    setDialog(null);
    setReason("");
    setError("");
    setRequiresGapConfirmation(false);
    setGapAcknowledged(false);
  }

  async function performAction() {
    if (!dialog || dialog.type === "details") return;
    setSaving(true);
    setError("");
    try {
      if (dialog.type === "delete") {
        await apiRequest(`/assertions/${dialog.assertion.id}`, { method: "DELETE" });
      } else {
        await apiRequest(`/assertions/${dialog.assertion.id}/retract`, {
          method: "POST",
          body: JSON.stringify({
            reason,
            confirm_provenance_gap: gapAcknowledged,
          }),
        });
      }
      setDialog(null);
      setReason("");
      setRequiresGapConfirmation(false);
      setGapAcknowledged(false);
      await onChanged();
    } catch (requestError) {
      if (requestError.details?.requires_confirmation) {
        setRequiresGapConfirmation(true);
        setGapAcknowledged(false);
      }
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  return <section className="table-card assertions-card">
    <div className="table-meta"><span>{assertions.length} provenance assertions</span></div>
    {assertions.length === 0 ? <p className="empty-state">No sourced assertions are linked to this asset yet.</p> : <div className="responsive-table assertions-scroll"><table className="assertions-table"><thead><tr><th>Predicate</th><th>Value</th><th>Truth classification</th><th className="assertion-source-column">Source</th><th>Confirmation status</th><th className="assertion-observed-column">Last observed</th><th>Actions</th></tr></thead><tbody>{assertions.map((assertion) => {
      const value = assertionValue(assertion, assetsById);
      const mayDelete = canDelete && assertion.deletion_safety?.allowed;
      const mayRetract = canRetract && !assertion.retracted_at && assertion.confirmation_status === "confirmed";
      return <tr key={assertion.id}><td><span className="assertion-truncate primary-cell" title={assertion.predicate}>{assertion.predicate}</span></td><td><code className="assertion-truncate" title={value}>{value}</code></td><td><StatusBadge status={assertion.truth_classification} /></td><td className="assertion-source-column"><span className="assertion-truncate" title={assertion.source_name || "Unavailable"}>{assertion.source_name || "Unavailable"}</span></td><td><StatusBadge status={displayStatus(assertion)} /></td><td className="assertion-observed-column"><span className="secondary-text">{dateTime(assertion.last_observed_at)}</span></td><td><div className="table-actions"><button className="text-button" onClick={() => openDialog("details", assertion)} type="button">View details</button>{mayDelete && <button className="text-button text-danger" onClick={() => openDialog("delete", assertion)} type="button">Delete</button>}{mayRetract && <button className="text-button text-danger" onClick={() => openDialog("retract", assertion)} type="button">Retract</button>}</div></td></tr>;
    })}</tbody></table></div>}

    {dialog && <div className="dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) closeDialog(); }}>
      <section aria-labelledby="assertion-dialog-title" aria-modal="true" className="dialog-card dialog-card-wide" role="dialog">
        <h2 id="assertion-dialog-title">{dialog.type === "details" ? "Assertion details" : dialog.type === "delete" ? "Delete assertion?" : "Retract assertion"}</h2>
        {dialog.type === "details" && <div className="assertion-details-grid">
          <div><span>Assertion ID</span><strong className="mono">{dialog.assertion.id}</strong></div>
          <div><span>Discovery run</span><strong className="mono">{dialog.assertion.discovery_run_id || "—"}</strong></div>
          <div><span>Evidence record</span><strong className="mono">{dialog.assertion.evidence_record_id || "—"}</strong></div>
          <div><span>First observed</span><strong>{dateTime(dialog.assertion.first_observed_at)}</strong></div>
          <div><span>Last observed</span><strong>{dateTime(dialog.assertion.last_observed_at)}</strong></div>
          <div><span>Valid from / to</span><strong>{dateTime(dialog.assertion.valid_from)} / {dateTime(dialog.assertion.valid_to)}</strong></div>
          <div><span>Confidence</span><strong>{Math.round(dialog.assertion.confidence * 100)}%</strong></div>
          <div><span>Superseded by</span><strong className="mono">{dialog.assertion.superseded_by_id || "—"}</strong></div>
          <div><span>External subject</span><strong>{dialog.assertion.subject_external_id || "—"}</strong></div>
          <div><span>External object</span><strong>{dialog.assertion.object_external_id || "—"}</strong></div>
          <div className="detail-span"><span>Raw value</span><pre className="json-details">{JSON.stringify(dialog.assertion.value_json, null, 2)}</pre></div>
          {dialog.assertion.retracted_at && <div className="detail-span"><span>Retraction</span><strong>{dateTime(dialog.assertion.retracted_at)} — {dialog.assertion.retraction_reason}</strong></div>}
          {dialog.assertion.retracted_at && dialog.assertion.provenance_gap_warning && <div className="detail-span warning-banner"><strong>Provenance gap</strong><span>This operational value may no longer have a current confirmed assertion. Atlas has not changed the operational asset.</span></div>}
        </div>}
        {dialog.type === "delete" && <p>Deleting removes this unused assertion and its unaccepted reconciliation items permanently. Evidence and operational asset data remain unchanged.</p>}
        {dialog.type === "retract" && <><p>Retraction preserves evidence and history. It does not reverse or alter the current asset or other operational data.</p><label className="field"><span>Retraction reason *</span><textarea autoFocus required value={reason} onChange={(event) => setReason(event.target.value)} /></label>{requiresGapConfirmation && <label className="field checkbox-field provenance-confirm"><input required type="checkbox" checked={gapAcknowledged} onChange={(event) => setGapAcknowledged(event.target.checked)} /><span>I understand this may leave current operational knowledge without active provenance.</span></label>}</>}
        {error && <div className="error-banner" role="alert">{error}</div>}
        <div className="form-actions"><button className="button button-secondary" disabled={saving} onClick={closeDialog} type="button">{dialog.type === "details" ? "Close" : "Cancel"}</button>{dialog.type !== "details" && <button className="button button-danger" disabled={saving || (dialog.type === "retract" && (!reason.trim() || (requiresGapConfirmation && !gapAcknowledged)))} onClick={performAction} type="button">{saving ? "Saving…" : dialog.type === "delete" ? "Delete permanently" : "Retract assertion"}</button>}</div>
      </section>
    </div>}
  </section>;
}
