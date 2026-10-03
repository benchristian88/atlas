"use client";

import { Button } from "../../components/button";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { StatusBadge } from "../../components/status-badge";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";

function dateTime(value) {
  return value ? new Date(value).toLocaleString() : "—";
}

export default function DiscoveryRunsPage() {
  const { hasPermission } = useAuth();
  const workspace = useWorkspaceContext();
  const [runs, setRuns] = useState([]);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState(null);
  const [reason, setReason] = useState("");
  const [conflict, setConflict] = useState(null);
  const canView = hasPermission("integrations.view");
  const canArchive = hasPermission("discovery_runs.archive");
  const canDelete = hasPermission("discovery_runs.delete");

  const load = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    setError("");
    try {
      setRuns(await apiRequest(`/discovery-runs?include_archived=${includeArchived}`));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, [canView, includeArchived]);

  useEffect(() => { load(); }, [load, workspace.reloadKey]);

  function openDialog(type, run) {
    setDialog({ type, run });
    setReason("");
    setConflict(null);
  }

  function closeDialog() {
    if (saving) return;
    setDialog(null);
    setReason("");
    setConflict(null);
  }

  async function performAction() {
    if (!dialog) return;
    setSaving(true);
    setError("");
    setConflict(null);
    try {
      if (dialog.type === "delete") {
        await apiRequest(`/discovery-runs/${dialog.run.id}`, { method: "DELETE" });
      } else if (dialog.type === "restore") {
        await apiRequest(`/discovery-runs/${dialog.run.id}/restore`, { method: "POST" });
      } else {
        await apiRequest(`/discovery-runs/${dialog.run.id}/archive`, {
          method: "POST",
          body: JSON.stringify({ reason }),
        });
      }
      setDialog(null);
      setReason("");
      setConflict(null);
      await load();
    } catch (requestError) {
      if (requestError.status === 409 && dialog.type === "delete") {
        setConflict(requestError.details || { detail: requestError.message });
      } else {
        setError(requestError.message);
      }
    } finally {
      setSaving(false);
    }
  }

  if (!canView) return <AccessDenied />;
  return <>
    <PageHeader eyebrow="Operations" title="Discovery" description="Review sourced discovery runs and preserve accepted provenance." actions={<>{hasPermission("discovery.simulate") && <Link className="button button-primary" href="/discovery/simulate">Simulate discovery</Link>}</>} />
    <div className="filter-bar">
      <label className="field checkbox-field"><input checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} type="checkbox" /><span>Include archived</span></label>
    </div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {loading ? <div className="status-banner" role="status">Loading discovery runs…</div> : <section className="table-card">
      <div className="table-meta"><span>{runs.length} runs</span><button className="text-button" onClick={load} type="button">Refresh</button></div>
      {runs.length === 0 ? <p className="empty-state">No discovery runs yet.</p> : <div className="responsive-table"><table><thead><tr><th>Source</th><th>Status</th><th>Coverage</th><th>Started</th><th>Finished</th><th>Summary</th><th>Actions</th></tr></thead><tbody>{runs.map((run) => <tr key={run.id}><td><span className="primary-cell">{run.source_name || "Unknown source"}</span><span className="secondary-text mono">{run.id}</span></td><td><div className="badge-stack"><StatusBadge status={run.status} /><StatusBadge status={run.completeness_status} />{run.archived_at && <StatusBadge status="Archived" />}</div></td><td><span className="primary-cell">{run.is_complete_snapshot ? "Complete snapshot" : "Partial"}</span><span className="secondary-text">{run.coverage_key || "Unspecified"}</span></td><td>{dateTime(run.started_at)}</td><td>{dateTime(run.finished_at)}</td><td className="secondary-text discovery-summary" title={run.summary ? JSON.stringify(run.summary) : ""}>{run.summary ? Object.entries(run.summary).map(([key, value]) => `${key}: ${value}`).join(" · ") : "—"}</td><td><div className="table-actions"><Link className="text-button" href={`/discovery-runs/${run.id}`}>View</Link>{canArchive && (run.archived_at ? <button className="text-button" onClick={() => openDialog("restore", run)} type="button">Restore</button> : ["completed", "failed", "cancelled"].includes(run.status) ? <button className="text-button" onClick={() => openDialog("archive", run)} type="button">Archive</button> : null)}{canDelete && run.deletion_safety?.allowed && <button className="text-button text-danger" onClick={() => openDialog("delete", run)} type="button">Delete</button>}</div></td></tr>)}</tbody></table></div>}
    </section>}

    {dialog && <div className="dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) closeDialog(); }}>
      <section aria-labelledby="run-dialog-title" aria-modal="true" className="dialog-card" role="dialog">
        <h2 id="run-dialog-title">{dialog.type === "delete" ? "Delete discovery run?" : dialog.type === "restore" ? "Restore discovery run?" : "Archive discovery run"}</h2>
        {dialog.type === "delete" ? <p>Deletion removes unused test evidence, assertions, and reconciliation items permanently. This cannot be undone and never reverses operational Atlas data.</p> : dialog.type === "restore" ? <p>The run will return to the default discovery list. Its evidence and assertions are already preserved.</p> : <><p>Archiving hides this run from the default list while preserving all evidence, assertions, reconciliation history, and operational data.</p><label className="field"><span>Archive reason *</span><textarea autoFocus required value={reason} onChange={(event) => setReason(event.target.value)} /></label></>}
        {conflict && <div className="warning-banner" role="alert"><strong>{conflict.detail}</strong>{Array.isArray(conflict.blocking_reasons) && <ul>{conflict.blocking_reasons.map((item) => <li key={item}>{item}</li>)}</ul>}<p>Archive the run to preserve accepted knowledge and provenance.</p></div>}
        <div className="form-actions"><Button variant="secondary" disabled={saving} onClick={closeDialog} type="button">Cancel</Button>{conflict && canArchive && <Button variant="secondary" onClick={() => { setDialog({ type: "archive", run: dialog.run }); setConflict(null); }} type="button">Archive instead</Button>}<button className={`button ${dialog.type === "delete" ? "button-danger" : "button-primary"}`} disabled={saving || (dialog.type === "archive" && !reason.trim()) || Boolean(conflict)} onClick={performAction} type="button">{saving ? "Saving…" : dialog.type === "delete" ? "Delete permanently" : dialog.type === "restore" ? "Restore" : "Archive"}</button></div>
      </section>
    </div>}
  </>;
}
