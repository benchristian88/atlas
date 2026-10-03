import { Fragment } from "react";
import { auditDetails, auditValue } from "../lib/audit-details.mjs";

export function AuditInvestigation({ event, timestamp }) {
  const { changes, facts } = auditDetails(event.metadata);
  const context = [["Timestamp", timestamp(event.created_at)], ["Actor", event.actor_snapshot || "System"], ["Action", event.event_type], ["Object", [event.target_type, event.target_id].filter(Boolean).join(" · ")], ["Customer", event.customer_id], ["Site", event.site_id], ["Workspace", event.workspace_id], ["Source IP", event.source_ip], ["Request", event.request_id]];
  return <section className="audit-investigation" tabIndex={0} aria-label="Audit investigation" id={`audit-${event.id}`}>
    <dl>{context.filter(([, value]) => value).map(([label, value]) => <Fragment key={label}><dt>{label}</dt><dd>{value}</dd></Fragment>)}</dl>
    <h3>What changed</h3>
    {event.change_summary && <p>{event.change_summary}</p>}
    {changes.length > 0 && <table><thead><tr><th>Field</th><th>Change</th><th>Before</th><th>After</th></tr></thead><tbody>{changes.map(row => <tr key={row.field}><td>{row.field}</td><td>{!row.hasBefore ? "Added" : !row.hasAfter ? "Removed" : "Changed"}</td><td>{row.hasBefore ? <pre>{auditValue(row.before)}</pre> : "Not recorded"}</td><td>{row.hasAfter ? <pre>{auditValue(row.after)}</pre> : "Not recorded"}</td></tr>)}</tbody></table>}
    {facts.length > 0 && <dl>{facts.map(row => <Fragment key={row.field}><dt>{row.field.replaceAll("_", " ")}</dt><dd>{Array.isArray(row.value) && row.value.every(v => typeof v !== "object") ? row.value.join(", ") : <pre>{auditValue(row.value)}</pre>}</dd></Fragment>)}</dl>}
    {!changes.length && <p className="ops-meta">Before/after values were not recorded for this event.</p>}
  </section>;
}
