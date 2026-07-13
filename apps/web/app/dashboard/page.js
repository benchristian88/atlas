"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { PageHeader } from "../../components/page-header";
import { apiRequest } from "../../lib/api";

const cards = [
  { key: "customers", label: "Customers", href: "/customers", description: "Managed organisations" },
  { key: "sites", label: "Sites", href: "/sites", description: "Customer locations" },
  { key: "assets", label: "Assets", href: "/assets", description: "Managed infrastructure" },
  { key: "relationships", label: "Relationships", href: "/topology", description: "Connections between assets" },
];

export default function DashboardPage() {
  const [counts, setCounts] = useState(null);
  const [error, setError] = useState("");
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    async function loadCounts() {
      try {
        const [customers, sites, assets, relationships] = await Promise.all([
          apiRequest("/customers"),
          apiRequest("/sites"),
          apiRequest("/assets"),
          apiRequest("/asset-relationships"),
        ]);
        setCounts({
          customers: customers.length,
          sites: sites.length,
          assets: assets.length,
          relationships: relationships.length,
        });
      } catch (requestError) {
        setError(requestError.message || "Atlas could not load dashboard counts.");
      }
    }
    loadCounts();
  }, []);

  return (
    <>
      <PageHeader
        eyebrow="Dashboard"
        title="Infrastructure at a glance"
        description="Live totals for manually entered Atlas infrastructure and relationships."
      />
      {error && <div className="error-banner" role="alert">Could not load summary counts. {error}</div>}
      {!counts && !error && <div className="status-banner" role="status">Loading summary…</div>}
      <section className="summary-grid" aria-label="Atlas MVP summary">
        {cards.map((card) => (
          <Link className="summary-card" href={card.href} key={card.key}>
            <span>{card.label}</span>
            <strong>{counts ? counts[card.key] : "—"}</strong>
            <span className="summary-description">{card.description}</span>
            <span className="card-link">View <span aria-hidden="true">→</span></span>
          </Link>
        ))}
      </section>
    </>
  );
}
