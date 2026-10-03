"use client";

import { Button } from "./button";

import { useState } from "react";
import { CompletenessLine } from "./operations-primitives";
import { StatusBadge } from "./status-badge";
import { apiRequest } from "../lib/api";

function label(value) {
  return (value || "not_evaluated").replaceAll("_", " ");
}

export function CompletenessPanel({ assetId, serviceId, entityType = "asset", completeness, canEvaluate, canDefer, canExcept, onChanged, compact = false }) {
  const [working, setWorking] = useState("");
  const [error, setError] = useState("");
  const [action, setAction] = useState(null);
  const [reason, setReason] = useState("");
  const [date, setDate] = useState("");
  const summary = completeness?.summary;
  const groups = [
    { key: "required", label: "Required", match: (gap) => gap.requirement_level === "required" && gap.status !== "exception" },
    { key: "conditional", label: "Conditional", match: (gap) => gap.requirement_level === "conditional" && gap.status !== "exception" },
    { key: "recommended", label: "Recommended", match: (gap) => gap.requirement_level === "recommended" && gap.status !== "exception" },
    { key: "exceptions", label: "Exceptions", match: (gap) => gap.status === "exception" },
  ];

  async function evaluate() {
    setWorking("evaluate"); setError("");
    const entityId = entityType === "service" ? serviceId : assetId;
    try { await apiRequest(`/${entityType === "service" ? "services" : "assets"}/${entityId}/evaluate-completeness`, { method: "POST" }); await onChanged(); }
    catch (requestError) { setError(requestError.message || `Atlas could not evaluate this ${entityType}.`); }
    finally { setWorking(""); }
  }

  async function applyAction() {
    if (!action || !reason.trim()) return;
    setWorking(action.gap.id); setError("");
    const body = action.kind === "defer"
      ? { reason: reason.trim(), deferred_until: new Date(date).toISOString() }
      : { reason: reason.trim(), expires_at: date ? new Date(date).toISOString() : null };
    try {
      await apiRequest(`/knowledge-gaps/${action.gap.id}/${action.kind}`, { method: "POST", body: JSON.stringify(body) });
      setAction(null); setReason(""); setDate(""); await onChanged();
    } catch (requestError) { setError(requestError.message || "Atlas could not update this gap."); }
    finally { setWorking(""); }
  }

  return <section className="knowledge-card completeness-panel">
    <div className="form-card-header"><div><p className="eyebrow">Completeness</p><h2>Knowledge completeness</h2></div><div className="row-actions"><StatusBadge status={label(summary?.completeness_status)} />{canEvaluate && <Button variant="secondary" disabled={working === "evaluate"} onClick={evaluate} type="button">{working === "evaluate" ? "Evaluating…" : "Re-evaluate"}</Button>}</div></div>
    <div className="completeness-body">
      {error && <div className="error-banner" role="alert">{error}</div>}
      {!summary ? <p className="empty-state">Completeness has not been evaluated.</p> : <>
        {compact ? <CompletenessLine node={summary.completeness_status === "not_evaluated" ? null : summary} /> : <div className="completeness-meter" aria-label={`${summary.required_satisfied} of ${summary.required_total} required requirements satisfied`}><span style={{ width: `${summary.required_total ? Math.round((summary.required_satisfied / summary.required_total) * 100) : 100}%` }} /></div>}
        <div className="detail-grid completeness-counts"><div><span>Required</span><strong>{summary.required_satisfied} / {summary.required_total}</strong></div><div><span>Recommended</span><strong>{summary.recommended_satisfied} / {summary.recommended_total}</strong></div><div><span>Open gaps</span><strong>{summary.open_gap_count}</strong></div><div><span>Exceptions</span><strong>{summary.exception_count}</strong></div><div><span>Last evaluated</span><strong>{summary.last_evaluated_at ? new Date(summary.last_evaluated_at).toLocaleString() : "Never"}</strong></div></div>
      </>}
      {groups.map((group) => { const gaps = (completeness?.active_gaps || []).filter(group.match); if (!gaps.length) return null; return <div className="gap-group" key={group.key}><h3>{group.label}</h3>{gaps.map((gap) => <article className="gap-row" key={gap.id}><div><div className="row-actions"><StatusBadge status={gap.severity} /><StatusBadge status={gap.status} /><strong>{gap.requirement_name || gap.summary}</strong></div><p>{gap.summary}</p>{gap.details_json?.why_it_applies && <small>Why: {gap.details_json.why_it_applies}</small>}{gap.remediation_hint && <small>Next step: {gap.remediation_hint}</small>}{gap.exception_reason && <small>Exception: {gap.exception_reason}{gap.exception_expires_at ? ` · expires ${new Date(gap.exception_expires_at).toLocaleDateString()}` : ""}</small>}{gap.deferred_until && <small>Deferred until {new Date(gap.deferred_until).toLocaleString()}</small>}</div><div className="row-actions">{canDefer && gap.status !== "exception" && <button className="text-button" onClick={() => { setAction({ kind: "defer", gap }); setReason(""); setDate(""); }} type="button">Defer</button>}{canExcept && gap.status !== "exception" && <button className="text-button" onClick={() => { setAction({ kind: "exception", gap }); setReason(""); setDate(""); }} type="button">Exception</button>}{canExcept && gap.status === "exception" && <button className="text-button" onClick={async () => { setWorking(gap.id); try { await apiRequest(`/knowledge-gaps/${gap.id}/reopen`, { method: "POST", body: JSON.stringify({ reason: "Exception reopened from asset detail" }) }); await onChanged(); } catch (requestError) { setError(requestError.message); } finally { setWorking(""); } }} type="button">Reopen</button>}</div></article>)}</div>; })}
      {(completeness?.resolved_gaps || []).length > 0 && <details className="gap-history"><summary>Resolved history ({completeness.resolved_gaps.length})</summary>{completeness.resolved_gaps.map((gap) => <div className="gap-row" key={gap.id}><span>{gap.requirement_name || gap.summary}</span><StatusBadge status={gap.status} /></div>)}</details>}
      {action && <div className="gap-action-form"><h3>{action.kind === "defer" ? "Defer gap" : "Record exception"}</h3><label className="field"><span>Reason *</span><textarea autoFocus onChange={(event) => setReason(event.target.value)} required value={reason} /></label><label className="field"><span>{action.kind === "defer" ? "Review after *" : "Expires (optional)"}</span><input onChange={(event) => setDate(event.target.value)} required={action.kind === "defer"} type="datetime-local" value={date} /></label><div className="form-actions"><Button variant="secondary" onClick={() => setAction(null)} type="button">Cancel</Button><Button variant="primary" disabled={!reason.trim() || (action.kind === "defer" && !date) || working} onClick={applyAction} type="button">Save</Button></div></div>}
    </div>
  </section>;
}
