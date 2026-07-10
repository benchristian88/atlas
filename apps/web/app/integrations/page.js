import { MockPage } from "../../components/mock-page";
import { StatusBadge } from "../../components/status-badge";
import { integrations } from "../../lib/mock-data";

const columns = [
  { key: "name", label: "Integration", render: (row) => <span className="primary-cell">{row.name}</span> },
  { key: "plugin", label: "Plugin" },
  { key: "customer", label: "Customer" },
  { key: "site", label: "Site" },
  { key: "endpoint", label: "Endpoint", render: (row) => <span className="mono secondary-text">{row.endpoint}</span> },
  { key: "status", label: "Status", render: (row) => <StatusBadge status={row.status} /> },
];

export default function IntegrationsPage() {
  return <MockPage eyebrow="Connections" title="Integrations" description="Read-only discovery sources configured for customer environments." columns={columns} rows={integrations} />;
}
