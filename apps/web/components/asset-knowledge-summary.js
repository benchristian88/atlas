import Link from "next/link";
import { StatusBadge } from "./status-badge";

function KnowledgeValue({ entry }) {
  const relation = entry.relationship;
  if (relation) return relation.href ? <Link href={relation.href} aria-label={`${relation.label}: ${relation.target_name}`}>{relation.target_name}</Link> : <span>{relation.target_name}</span>;
  const label = entry.display_value ?? (typeof entry.value === "object" ? "Structured value — see Raw assertions" : String(entry.value ?? "—"));
  return <span>{label}</span>;
}

function LogicalValues({ groups, entries = [] }) {
  // Additive API compatibility: older servers still supply individual values.
  const values = groups?.length ? groups : entries.map(entry => ({ ...entry, key: entry.assertion_id, assertions: [entry] }));
  return values.map(entry => <div className="knowledge-logical-value" key={entry.key}>
    <strong><KnowledgeValue entry={entry} /></strong>
    <details className="knowledge-value-sources"><summary>{entry.source_count ?? entry.assertions.length} source{(entry.source_count ?? entry.assertions.length) === 1 ? "" : "s"} · Provenance</summary>
      <ul>{entry.assertions.map(assertion => <li key={assertion.assertion_id}>
        <span>{assertion.source_name || "Source unavailable"}</span>
        {assertion.last_observed_at && <time dateTime={assertion.last_observed_at}>Observed {new Date(assertion.last_observed_at).toLocaleString()}</time>}
        {assertion.accepted_at && <span>Accepted {new Date(assertion.accepted_at).toLocaleString()}{assertion.accepted_by_name ? ` by ${assertion.accepted_by_name}` : ""}</span>}
        <small>Assertion <code>{assertion.assertion_id}</code></small>
      </li>)}</ul>
    </details>
  </div>);
}

export function AssetKnowledgeSummary({ groups }) {
  if (!groups.length) return <p className="empty-state">No current knowledge to summarize.</p>;
  return <div className="knowledge-summary-grid">{groups.map(item => <article className={`knowledge-summary-item${item.conflict || item.unresolved ? " knowledge-conflict" : ""}`} key={item.predicate} aria-label={`${item.label} knowledge`}>
    <div className="knowledge-summary-heading"><div><span className="secondary-text">{item.cardinality === "multi" ? "Multiple values" : "Single value"}</span><h3>{item.label}</h3></div><StatusBadge status={item.state || (item.conflict ? "Conflicting" : item.unresolved ? "Unresolved" : item.accepted ? "Accepted" : "Observed")} /></div>
    <div className="knowledge-accepted"><span>Accepted Atlas value</span>{item.accepted_values.length ? <LogicalValues groups={item.accepted_groups} entries={item.accepted_values} /> : <strong>Not selected</strong>}</div>
    {item.canonical_consistency && item.canonical_consistency !== "not_applicable" && <div className="knowledge-canonical"><span className="secondary-text">Operational Atlas value</span><strong>{item.canonical_display_value || "—"}</strong>
      {item.canonical_consistency === "missing_acceptance" && <p className="secondary-text" role="status">The operational value has no matching accepted assertion. Review source proposals; historical acceptance is not inferred.</p>}
      {item.canonical_consistency === "mismatch" && <p className="review-warning" role="status">The operational value differs from accepted knowledge. Review the discrepancy.</p>}
    </div>}
    {item.awaiting_acceptance && <p className="secondary-text">Awaiting acceptance{item.unresolved ? ": source values disagree." : ". Observations have not been selected as accepted knowledge."}</p>}
    <div className="knowledge-observations"><span>Latest source observations</span>{item.latest_observations.length ? <LogicalValues groups={item.observation_groups} entries={item.latest_observations} /> : <p className="secondary-text">No active observations</p>}</div>
    <footer>{item.source_count} active source{item.source_count === 1 ? "" : "s"} · {item.assertion_count} assertion{item.assertion_count === 1 ? "" : "s"} · {item.historical_count} historical · {item.last_observed_at ? `Observed ${new Date(item.last_observed_at).toLocaleString()}` : "Never observed"}. Individual evidence remains in History and Raw assertions.</footer>
  </article>)}</div>;
}
