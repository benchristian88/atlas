import { MockPage } from "../../components/mock-page";
import { StatusBadge } from "../../components/status-badge";
import { discoveryRuns } from "../../lib/mock-data";

const columns = [
  { key: "id", label: "Run", render: (row) => <span className="primary-cell mono">{row.id}</span> },
  { key: "integration", label: "Integration" },
  { key: "customer", label: "Customer" },
  { key: "status", label: "Status", render: (row) => <StatusBadge status={row.status} /> },
  { key: "started", label: "Started", render: (row) => <span className="secondary-text">{row.started}</span> },
  { key: "duration", label: "Duration" },
  { key: "summary", label: "Summary", render: (row) => <span className="secondary-text">{row.summary}</span> },
];

export default function DiscoveryRunsPage() {
  return <MockPage eyebrow="History" title="Discovery runs" description="Recent discovery activity and outcomes from configured integrations." columns={columns} rows={discoveryRuns} />;
}
