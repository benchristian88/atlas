"use client";

import { Fragment } from "react";
import { Button } from "./button";
import { DataTable } from "./data-table";
import { Section } from "./section";
import { StatusBadge } from "./status-badge";

const label = value => (value || "Unspecified").replaceAll("_", " ");

export function DiagnosticEvents({ events = [], debug = false }) {
  const columns = [
    { key: "result", label: "Result", render: row => <StatusBadge status={row.result} /> },
    { key: "stage", label: "Stage", render: row => <div className="table-cell-identity"><span>{label(row.stage)}</span>{row.source_category && <span className="secondary-text">{label(row.source_category)}</span>}</div> },
    { key: "object", label: "Object", render: row => <div className="table-cell-identity"><span>{row.object_class || "Discovery"}</span><span>{row.external_id || "—"}</span>{row.parent_external_id && <span className="secondary-text">{row.parent_external_id}</span>}</div> },
    { key: "reason_code", label: "Reason", render: row => <code>{row.reason_code}</code> },
    ...(debug ? [{ key: "rule", label: "Validation", render: row => <div className="table-cell-identity"><span>{label(row.validation_rule || row.action)}</span>{row.field && <span>Field: {row.field}</span>}{row.encountered_type && <span>Type: {row.encountered_type}</span>}{row.expected && <span>Expected: {label(row.expected)}</span>}</div> }] : []),
  ];
  return <DataTable label={debug ? "Debug trace events" : "Discovery diagnostics"} rows={events.map(row => ({ ...row, id: row.sequence }))} columns={columns} empty="No diagnostic warnings or errors." />;
}

export function DebugNextRunControl({ armed, allowed, busy, onChange }) {
  if (!allowed) return null;
  return <div><p role="status">Debug next run: <strong>{armed ? "Armed" : "Off"}</strong></p><p className="secondary-text">Debug applies to the next run only. Redacted debug data expires within 48 hours.</p><Button disabled={busy} onClick={() => onChange(!armed)}>{armed ? "Disable debug for next discovery run" : "Enable debug for next discovery run"}</Button></div>;
}

export function DiagnosticsView({ run, canDebug, trace, expanded, onExpand, onDelete, busy, error }) {
  const summary = run.diagnostics_summary;
  return <Section title="Diagnostics">
    {summary?.available ? <>
      <dl className="ops-definition">{["processed", "accepted", "skipped", "warning", "error"].map(name => <Fragment key={name}><dt>{label(name)}</dt><dd>{summary.counts[name]}</dd></Fragment>)}</dl>
      {!!summary.reasons?.length && <p>Completeness reasons: {summary.reasons.map(row => `${row.reason_code} (${row.count})`).join(" · ")}</p>}
      <DiagnosticEvents events={run.diagnostics_events} />
      {summary.contexts_truncated && <p className="secondary-text">Showing the first bounded warning contexts. Counts and reason totals include all validated events.</p>}
    </> : <p>{summary?.processing_errors?.length ? "Diagnostic processing failed. See the safe reason codes below." : "Diagnostics are unavailable for this run."}</p>}
    {!!summary?.processing_errors?.length && <p className="warning-banner" role="status">{summary.processing_errors.join(" · ")}</p>}
    {canDebug && run.debug_enabled && <details open={expanded} onToggle={event => onExpand(event.currentTarget.open)}><summary>Debug trace</summary>
      {error && <p className="error-banner" role="alert">{error}</p>}
      {trace ? <><p>Debug data: {label(trace.state)}{trace.expires_at && ` · Expires ${new Date(trace.expires_at).toLocaleString()}`}</p>{trace.state === "available" && <DiagnosticEvents events={trace.events} debug />}{!["deleted", "expired", "unavailable"].includes(trace.state) && <Button variant="destructive" loading={busy} onClick={onDelete}>Delete debug data</Button>}</> : <p role="status">Expand to load the redacted debug trace.</p>}
    </details>}
  </Section>;
}
