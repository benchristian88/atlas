import Link from "next/link";
import { PageHeader } from "../components/page-header";
import { assets, customers, discoveryRuns, integrations, sites } from "../lib/mock-data";

const summaries = [
  { label: "Customers", value: customers.length, href: "/customers" },
  { label: "Sites", value: sites.length, href: "/sites" },
  { label: "Assets", value: assets.length, href: "/assets" },
  { label: "Integrations", value: integrations.length, href: "/integrations" },
  { label: "Discovery runs", value: discoveryRuns.length, href: "/discovery-runs" },
];

export default function Home() {
  return (
    <>
      <PageHeader
        eyebrow="Overview"
        title="Infrastructure at a glance"
        description="A single view of customers, sites, integrations, and discovered infrastructure."
      />
      <div className="mock-notice">
        <span className="notice-dot" aria-hidden="true" />
        Showing sample data while API endpoints are being built.
      </div>
      <section className="summary-grid" aria-label="Atlas summary">
        {summaries.map((summary) => (
          <Link className="summary-card" href={summary.href} key={summary.label}>
            <span>{summary.label}</span>
            <strong>{summary.value}</strong>
            <span className="card-link">View all <span aria-hidden="true">→</span></span>
          </Link>
        ))}
      </section>
    </>
  );
}
