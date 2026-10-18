"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AccessDenied } from "../../../components/access-denied";
import { useAuth } from "../../../components/auth-context";
import { PageHeader } from "../../../components/page-header";
import { StatusBadge } from "../../../components/status-badge";
import { apiRequest } from "../../../lib/api";
import { Button } from "../../../components/button";
import { Section } from "../../../components/section";
import { discoveryDuration } from "../../../lib/discovery.mjs";
import { RunDiagnostics } from "../../../components/run-diagnostics";

function dateTime(value) {
  return value ? new Date(value).toLocaleString() : "—";
}

export default function DiscoveryRunDetailPage() {
  const { id } = useParams();
  const { hasPermission, hasPermissionInContext, hasGlobalPermission } = useAuth();
  const [run, setRun] = useState(null);
  const [error, setError] = useState("");
  const canView = hasPermission("integrations.view");

  useEffect(() => {
    if (!canView) return;
    let active = true;
    const load = () => apiRequest(`/discovery-runs/${id}`)
      .then((result) => { if (active) setRun(result); })
      .catch((requestError) => { if (active) setError(requestError.message); });
    load();
    const timer = setInterval(load, 3000);
    return () => { active = false; clearInterval(timer); };
  }, [canView, id]);

  if (!canView) return <AccessDenied />;
  if (error) return <div className="error-banner" role="alert">{error}</div>;
  if (!run) return <div className="status-banner" role="status">Loading discovery run…</div>;
  return <>
    <PageHeader eyebrow="Discovery run" title={run.source_name || "Unknown source"} description={`Run ${run.id}`} actions={<><Button href="/discovery-runs">Run history</Button>{run.integration_id && <Button href={`/integrations/${run.integration_id}`}>Integration</Button>}{run.execution_provenance && ["pending", "running"].includes(run.status) && hasPermissionInContext("integrations.run", run.customer_id, run.site_id) && <Button onClick={async () => { try { setRun(await apiRequest(`/discovery-runs/${id}/cancel`, { method: "POST" })); } catch (reason) { setError(reason.message); } }}>Cancel run</Button>}</>} />
    <section className="detail-card"><div className="detail-grid">
      <div><span>Status</span><strong><StatusBadge status={run.status} /> {run.archived_at && <StatusBadge status="Archived" />}</strong></div>
      <div><span>Started</span><strong>{dateTime(run.started_at)}</strong></div>
      <div><span>Finished</span><strong>{dateTime(run.finished_at)}</strong></div>
      <div><span>Duration</span><strong>{discoveryDuration(run)}</strong></div>
      <div><span>Completeness</span><strong><StatusBadge status={run.completeness_status} /></strong></div>
      <div><span>Batches</span><strong>{run.batch_count ?? "—"}</strong></div>
      <div><span>Observations</span><strong>{run.observation_count ?? "—"}</strong></div>
      <div><span>Warnings</span><strong>{run.warning_count ?? "—"}</strong></div>
      <div className="detail-span"><span>Coverage</span><strong>{run.coverage_key || "Unspecified"}</strong></div>
      <div><span>Archived</span><strong>{dateTime(run.archived_at)}</strong></div>
      <div className="detail-span"><span>Archive reason</span><strong>{run.archive_reason || "—"}</strong></div>
      <div className="detail-span"><span>Error</span><strong>{run.error_message || "—"}</strong></div>
    </div></section>
    {run.execution_provenance && <Section title="Execution"><dl className="ops-definition"><dt>Connector</dt><dd>{run.execution_provenance.connector_id} · {run.execution_provenance.connector_version}</dd><dt>Trigger</dt><dd>{run.execution_provenance.trigger}</dd><dt>Source version</dt><dd>{run.source_version || "Not detected"}</dd><dt>Dispatch</dt><dd>{run.dispatch_state} · {run.dispatch_attempts} attempts</dd><dt>Runtime</dt><dd>{run.execution_provenance.runtime_type} · {run.execution_provenance.runtime_version}</dd><dt>Baseline</dt><dd>{run.execution_provenance.baseline_id} · {run.execution_provenance.baseline_version}</dd><dt>AIP / SDK</dt><dd>{run.execution_provenance.aip_version} / {run.execution_provenance.sdk_version}</dd></dl><details><summary>Technical identity</summary><dl className="ops-definition"><dt>Runtime job</dt><dd className="mono">{run.runtime_job_id || "Not dispatched"}</dd><dt>Bundle digest</dt><dd className="mono">{run.execution_provenance.connector_digest}</dd><dt>Environment digest</dt><dd className="mono">{run.execution_provenance.baseline_digest}</dd></dl></details><div className="form-actions"><Button href="/reconciliation">Reconciliation</Button><Button href="/changes">Changes</Button></div></Section>}
    {run.execution_provenance && <RunDiagnostics run={run} canDebug={hasGlobalPermission("integration_runtime.manage")} />}
    <section className="detail-card"><h2>Summary</h2><pre className="json-details">{JSON.stringify(run.summary || {}, null, 2)}</pre></section>
  </>;
}
