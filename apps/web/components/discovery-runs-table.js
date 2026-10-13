import Link from "next/link";
import { DataTable } from "./data-table";
import { StatusBadge } from "./status-badge";
import { discoveryRunPresentation } from "../lib/discovery.mjs";

function dateTime(value) {
  return value ? new Date(value).toLocaleString() : "—";
}

export function DiscoveryRunsTable({ runs, ...props }) {
  return <DataTable label="Discovery runs" rows={runs} empty="No discovery runs yet." {...props} columns={[
    { key: "source", label: "Source / Integration", render: run => run.integration_id
      ? <Link className="primary-cell" href={`/integrations/${run.integration_id}`}>{discoveryRunPresentation(run).source}</Link>
      : <span className="primary-cell">{discoveryRunPresentation(run).source}</span> },
    { key: "connector", label: "Connector / trigger", render: run => <div className="table-cell-identity">
      <span className="primary-cell">{discoveryRunPresentation(run).connector}</span>
      <span className="secondary-text">{discoveryRunPresentation(run).trigger}</span>
    </div> },
    { key: "status", label: "Status", render: run => <div className="table-cell-identity">
      <div role="group" aria-label="Run status"><StatusBadge status={run.status} /></div>
      <div role="group" aria-label="Completeness"><StatusBadge status={run.completeness_status} /></div>
      {run.archived_at && <StatusBadge status="Archived" />}
    </div> },
    { key: "coverage", label: "Coverage", render: run => discoveryRunPresentation(run).coverage },
    { key: "started_at", label: "Started", render: run => dateTime(run.started_at) },
    { key: "finished_at", label: "Finished", render: run => dateTime(run.finished_at) },
    { key: "counts", label: "Observations / batches", render: run => `${run.observation_count ?? run.summary?.observations ?? 0} / ${run.batch_count ?? 0}` },
    { key: "warnings", label: "Warnings / error", render: run => <div className="table-cell-identity">
      <span>{run.warning_count ?? 0}</span><span className="secondary-text">{run.error_message || ""}</span>
    </div> },
  ]} />;
}
