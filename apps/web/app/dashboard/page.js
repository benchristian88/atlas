import Link from "next/link";
import { PageHeader } from "../../components/page-header";
import { assets, customers, discoveryRuns, integrations, sites } from "../../lib/mock-data";

const summaries = [
  { label: "Customers", value: customers.length, href: "/customers", description: "Managed organisations" },
  { label: "Sites", value: sites.length, href: "/sites", description: "Customer locations" },
  { label: "Assets", value: assets.length, href: "/assets", description: "Manual and discovered infrastructure" },
  { label: "Integrations", value: integrations.length, href: "/integrations", description: "Connected data sources" },
  { label: "Discovery runs", value: discoveryRuns.length, href: "/discovery-runs", description: "Proxmox discovery activity" },
];

export default function DashboardPage() {
  return (
    <>
      <PageHeader
        eyebrow="Dashboard"
        title="Infrastructure at a glance"
        description="A single view of customers, sites, integrations, discovery, and managed infrastructure."
      />
      <div className="mock-notice">
        <span className="notice-dot" aria-hidden="true" />
        Summary counts use sample data while aggregate API endpoints are being built.
      </div>
      <section className="summary-grid" aria-label="Atlas MVP summary">
        {summaries.map((summary) => (
          <Link className="summary-card" href={summary.href} key={summary.label}>
            <span>{summary.label}</span>
            <strong>{summary.value}</strong>
            <span className="summary-description">{summary.description}</span>
            <span className="card-link">View all <span aria-hidden="true">→</span></span>
          </Link>
        ))}
      </section>
    </>
  );
}
