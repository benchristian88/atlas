"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";

const cards = [
  { key: "customers", label: "Customers", href: "/admin/customers", description: "Managed organisations", permission: "customers.view" },
  { key: "sites", label: "Sites", href: "/admin/sites", description: "Customer locations", permission: "sites.view" },
  { key: "assets", label: "Assets", href: "/assets", description: "Managed infrastructure", permission: "assets.view" },
  { key: "networks", label: "Networks", href: "/networks", description: "VLANs and network segments", permission: "networks.view" },
  { key: "relationships", label: "Relationships", href: "/topology", description: "Connections between assets", permission: "relationships.view" },
  { key: "reconciliation", label: "Reconciliation", href: "/reconciliation", description: "Open knowledge decisions", permission: "reconciliation.view" },
  { key: "open_knowledge_gap_count", label: "Knowledge gaps", href: "/reconciliation?queue=missing-knowledge", description: "Open required or conditional gaps", permission: "knowledge_gaps.view" },
  { key: "topology", label: "Knowledge Graph", href: "/topology", description: "Five focused infrastructure lenses", value: "5", permission: "assets.view" },
];

export default function DashboardPage() {
  const { hasAnyPermission, hasPermission } = useAuth();
  const workspace = useWorkspaceContext();
  const [counts, setCounts] = useState(null);
  const [reconciliation, setReconciliation] = useState(null);
  const [recentChanges, setRecentChanges] = useState([]);
  const [error, setError] = useState("");
  const canView = hasAnyPermission(["customers.view", "sites.view", "assets.view", "relationships.view", "networks.view"]);

  useEffect(() => {
    if (!canView) return;
    async function loadCounts() {
      try {
        const [summary, queueSummary, changes] = await Promise.all([
          apiRequest("/dashboard/summary"),
          hasPermission("reconciliation.view") ? apiRequest("/reconciliation-items/summary") : Promise.resolve(null),
          hasPermission("changes.view") ? apiRequest("/changes?limit=6&offset=0") : Promise.resolve({ items: [] }),
        ]);
        setCounts(summary);
        setReconciliation(queueSummary);
        setRecentChanges(changes.items);
      } catch (requestError) {
        setError(requestError.message || "Atlas could not load dashboard counts.");
      }
    }
    loadCounts();
  }, [canView, hasPermission, workspace.reloadKey]);

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
      {hasPermission("knowledge_gaps.view") && counts && <section className="detail-card"><div className="form-card-header"><div><p className="eyebrow">Completeness</p><h2>Knowledge health</h2></div><Link className="card-link" href="/reconciliation?queue=missing-knowledge">Review missing knowledge →</Link></div><div className="detail-grid"><div><span>Critical gaps</span><strong>{counts.critical_knowledge_gap_count}</strong></div><div><span>High gaps</span><strong>{counts.high_knowledge_gap_count}</strong></div><div><span>Assets with critical gaps</span><strong>{counts.assets_with_critical_gaps}</strong></div><div><span>Not evaluated</span><strong>{counts.assets_not_evaluated}</strong></div><div><span>Operationally complete</span><strong>{counts.assets_operationally_complete}</strong></div><div><span>Expired exceptions</span><strong>{counts.expired_exception_count}</strong></div></div></section>}
      {hasPermission("reconciliation.view") && reconciliation && <section className="detail-card"><div className="form-card-header"><div><p className="eyebrow">Reconciliation</p><h2>Decision queues</h2></div><Link className="card-link" href="/reconciliation">Review queues →</Link></div><div className="detail-grid"><div><span>Open</span><strong>{reconciliation.by_status.open || 0}</strong></div><div><span>Deferred</span><strong>{reconciliation.by_status.deferred || 0}</strong></div><div><span>Exceptions</span><strong>{reconciliation.by_status.exception || 0}</strong></div><div><span>Actionable</span><strong>{reconciliation.actionable}</strong></div></div></section>}
      {hasPermission("changes.view") && <section className="detail-card"><div className="form-card-header"><div><p className="eyebrow">Knowledge</p><h2>Recent meaningful changes</h2></div><Link className="card-link" href="/changes">View timeline →</Link></div>{recentChanges.length === 0 ? <p className="secondary-text">No meaningful changes yet.</p> : <div className="dashboard-change-list">{recentChanges.map((change) => <div key={change.id}><span><strong>{change.entity_name_snapshot}</strong> — {change.summary}</span><time>{new Date(change.occurred_at).toLocaleString()}</time></div>)}</div>}</section>}
      {hasPermission("assets.view") && <section className="dashboard-prompt">
        <div><p className="eyebrow">Homelab modelling</p><h2>Map infrastructure from hardware to workloads</h2><p>Start with Customer → Site → Proxmox Host → VM/LXC/Docker Host → Workload, then connect dependencies.</p></div>
        <Link className="button button-primary" href="/topology">Open Topology</Link>
      </section>}
    </>
  );
}
