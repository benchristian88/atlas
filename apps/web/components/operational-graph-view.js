import Link from "next/link";

import { normalizeOperationalGraph } from "../lib/operational-graph.mjs";

export function OperationalGraphView({ graph, emptyMessage = "No connected operational knowledge is available." }) {
  const normalized = normalizeOperationalGraph(graph);
  return <div aria-label="Operational graph" className="operational-graph-view">
    {normalized.truncated && <div className="warning-banner" role="status">{normalized.warnings[0] || "This graph was truncated at the requested limit."}</div>}
    {normalized.edges.length === 0 ? <p className="empty-state" role="status">{emptyMessage}</p> : <div className="service-graph-list">
      {normalized.edges.map((edge) => <div key={edge.key}>
        <Link href={edge.source.href}>{edge.source.name}</Link>
        <span aria-label={edge.label}>{edge.label} →</span>
        <Link href={edge.target.href}>{edge.target.name}</Link>
      </div>)}
    </div>}
  </div>;
}
