"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AccessDenied } from "../../../components/access-denied";
import { useAuth } from "../../../components/auth-context";
import { PageHeader } from "../../../components/page-header";
import { StatusBadge } from "../../../components/status-badge";
import { apiRequest } from "../../../lib/api";

function dateTime(value) {
  return value ? new Date(value).toLocaleString() : "—";
}

export default function DiscoveryRunDetailPage() {
  const { id } = useParams();
  const { hasPermission } = useAuth();
  const [run, setRun] = useState(null);
  const [error, setError] = useState("");
  const canView = hasPermission("integrations.view");

  useEffect(() => {
    if (!canView) return;
    let active = true;
    apiRequest(`/discovery-runs/${id}`)
      .then((result) => { if (active) setRun(result); })
      .catch((requestError) => { if (active) setError(requestError.message); });
    return () => { active = false; };
  }, [canView, id]);

  if (!canView) return <AccessDenied />;
  if (error) return <div className="error-banner" role="alert">{error}</div>;
  if (!run) return <div className="status-banner" role="status">Loading discovery run…</div>;
  return <>
    <PageHeader eyebrow="Discovery run" title={run.source_name || "Unknown source"} description={`Run ${run.id}`} />
    <section className="detail-card"><div className="detail-grid">
      <div><span>Status</span><strong><StatusBadge status={run.status} /> {run.archived_at && <StatusBadge status="Archived" />}</strong></div>
      <div><span>Started</span><strong>{dateTime(run.started_at)}</strong></div>
      <div><span>Finished</span><strong>{dateTime(run.finished_at)}</strong></div>
      <div><span>Archived</span><strong>{dateTime(run.archived_at)}</strong></div>
      <div className="detail-span"><span>Archive reason</span><strong>{run.archive_reason || "—"}</strong></div>
      <div className="detail-span"><span>Error</span><strong>{run.error_message || "—"}</strong></div>
    </div></section>
    <section className="detail-card"><h2>Summary</h2><pre className="json-details">{JSON.stringify(run.summary || {}, null, 2)}</pre></section>
  </>;
}
