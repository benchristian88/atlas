"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { apiRequest } from "../../lib/api";

const cards = [
  { key: "customers", label: "Customers", href: "/admin/customers", description: "Managed organisations", permission: "customers.view" },
  { key: "sites", label: "Sites", href: "/admin/sites", description: "Customer locations", permission: "sites.view" },
  { key: "assets", label: "Assets", href: "/assets", description: "Managed infrastructure", permission: "assets.view" },
  { key: "networks", label: "Networks", href: "/networks", description: "VLANs and network segments", permission: "networks.view" },
  { key: "relationships", label: "Relationships", href: "/topology", description: "Connections between assets", permission: "relationships.view" },
  { key: "reconciliation", label: "Reconciliation", href: "/reconciliation", description: "Open knowledge decisions", permission: "assets.view" },
  { key: "topology", label: "Knowledge Graph", href: "/topology", description: "Five focused infrastructure lenses", value: "5", permission: "assets.view" },
];

export default function DashboardPage() {
  const { hasAnyPermission, hasPermission } = useAuth();
  const [counts, setCounts] = useState(null);
  const [error, setError] = useState("");
  const canView = hasAnyPermission(["customers.view", "sites.view", "assets.view", "relationships.view", "networks.view"]);

  useEffect(() => {
    if (!canView) return;
    async function loadCounts() {
      try {
        setCounts(await apiRequest("/dashboard/summary"));
      } catch (requestError) {
        setError(requestError.message || "Atlas could not load dashboard counts.");
      }
    }
    loadCounts();
  }, [canView]);

  if (!canView) return <AccessDenied />;

  return (
    <>
      <PageHeader
        eyebrow="Dashboard"
        title="Infrastructure at a glance"
        description="Live totals for the active customer and site context."
      />
      {error && <div className="error-banner" role="alert">Could not load summary counts. {error}</div>}
      {!counts && !error && <div className="status-banner" role="status">Loading summary…</div>}
      <section className="summary-grid" aria-label="Atlas MVP summary">
        {cards.filter((card) => hasPermission(card.permission)).map((card) => (
          <Link className="summary-card" href={card.href} key={card.key}>
            <span>{card.label}</span>
            <strong>{card.value || (counts ? counts[card.key] : "—")}</strong>
            <span className="summary-description">{card.description}</span>
            <span className="card-link">View <span aria-hidden="true">→</span></span>
          </Link>
        ))}
      </section>
      {hasPermission("assets.view") && <section className="dashboard-prompt">
        <div><p className="eyebrow">Homelab modelling</p><h2>Map infrastructure from hardware to workloads</h2><p>Start with Customer → Site → Proxmox Host → VM/LXC/Docker Host → Workload, then connect dependencies.</p></div>
        <Link className="button button-primary" href="/topology">Open Topology</Link>
      </section>}
    </>
  );
}
