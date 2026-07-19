"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const canView = hasPermission("integrations.view");

  useEffect(() => {
    if (!canView) return;
    let active = true;
    setLoading(true);
    setError("");
    apiRequest("/discovery-runs")
      .then((result) => { if (active) setRuns(result); })
      .catch((requestError) => { if (active) setError(requestError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [canView, workspace.reloadKey]);

  if (!canView) return <AccessDenied />;
  return <>
    <div className="page-heading-row">
      <PageHeader eyebrow="Operations" title="Discovery" description="Review sourced discovery runs and their evidence pipeline outcomes." />
      {hasPermission("integrations.manage") && <Link className="button button-primary" href="/discovery/simulate">Simulate discovery</Link>}
    </div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {loading ? <div className="status-banner" role="status">Loading discovery runs…</div> : <section className="table-card">
      <div className="table-meta"><span>{runs.length} runs</span></div>
      {runs.length === 0 ? <p className="empty-state">No discovery runs yet.</p> : <div className="responsive-table"><table><thead><tr><th>Source</th><th>Status</th><th>Started</th><th>Finished</th><th>Summary</th></tr></thead><tbody>{runs.map((run) => <tr key={run.id}><td><span className="primary-cell">{run.source_name || "Unknown source"}</span><span className="secondary-text mono">{run.id}</span></td><td><StatusBadge status={run.status} /></td><td>{dateTime(run.started_at)}</td><td>{dateTime(run.finished_at)}</td><td className="secondary-text">{run.summary ? Object.entries(run.summary).map(([key, value]) => `${key}: ${value}`).join(" · ") : "—"}</td></tr>)}</tbody></table></div>}
    </section>}
  </>;
}
