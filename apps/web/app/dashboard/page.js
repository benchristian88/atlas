"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { useWorkspaceContext } from "../../components/workspace-context";
import { ServiceLandscape } from "../../components/service-landscape";
import { CompletenessLine, EntityMark, RecordedStatus } from "../../components/operations-primitives";
import { NavigationIcon } from "../../components/navigation-icon.mjs";
import { WIDGETS, graphHref } from "../../lib/operations-experience.mjs";
import { normalizeOperationalGraph } from "../../lib/operational-graph.mjs";
import { dependencyAttention } from "../../lib/dependency-attention.mjs";
import { apiRequest } from "../../lib/api";
import { useRouter } from "next/navigation";

const metrics = [
  { key: "assets", label: "Assets", type: "asset", href: "/assets", permission: "assets.view" },
  { key: "services", label: "Services", type: "service", href: "/services", permission: "services.view" },
  { key: "business_functions", label: "Business Functions", type: "business_function", href: "/business-functions", permission: "business_functions.view" },
  { key: "open_knowledge_gap_count", label: "Knowledge Gaps", href: "/knowledge-gaps", permission: "knowledge_gaps.view" },
];

function Summary({ summary, hasPermission }) {
  return <section className="summary-grid dashboard-summary-grid" aria-label="Environment summary">{metrics.map((metric) => {
    const allowed = hasPermission(metric.permission);
    const count = allowed ? summary?.[metric.key] : null;
    return <Link className="ops-summary-item" href={allowed ? metric.href : "/dashboard"} key={metric.key}>
      {metric.type ? <EntityMark type={metric.type} /> : <span className="ops-icon-tile ops-icon-warning"><NavigationIcon name="knowledge-gaps" /></span>}
      <div className="ops-summary-copy">
        <span>{metric.label}</span>
        <strong>{count ?? "—"}</strong>
        <small>{!allowed ? "Requires view permission" : count == null ? "Total unavailable" : "Current recorded total"}</small>
      </div>
    </Link>;
  })}</section>;
}

function EnvironmentOverview({ graph, graphError, workspace, hasPermission }) {
  const router = useRouter();
  const [quick, setQuick] = useState("all");
  const services = graph?.nodes.filter((n) => n.entity_type === "service") || [];
  const partial = services.filter((s) => !graph.edges.some((e) => e.source_key === s.key && ["service_asset", "service_business_function"].includes(e.edge_family))).length;
  return <section className="ops-card"><header className="ops-section-header"><div><h2>Environment Overview</h2><p>From business purpose to Services and infrastructure.</p></div><Link className="text-button" href="/knowledge-graph">Open Knowledge Graph ↗</Link></header>
    <div className="ops-segments" aria-label="Environment overview filter">{["all", "critical", "gaps"].map((value) => <button type="button" key={value} aria-pressed={quick === value} onClick={() => setQuick(value)}>{value === "all" ? "All" : value === "critical" ? "Critical" : "With gaps"}</button>)}</div>
    {graph?.truncated && <p className="warning-banner" role="status">{graph.warnings.join(" ")} Open Focus to explore a specific entity.</p>}
    {!graph ? <p role="status">{graphError ? "Service landscape is unavailable. Use Try again above to reload." : "Loading service landscape…"}</p> : <>
      {!graph.edges.length && <div className="ops-guided"><h3>Build your service landscape</h3><p>Atlas can show how Business Functions, Services and Assets connect once those relationships are recorded.</p><div className="row-actions">{hasPermission("services.create") && <Link className="button button-primary" href="/services/new">Add a Service</Link>}{hasPermission("knowledge_gaps.view") && <Link className="button button-secondary" href="/knowledge-gaps">Open Knowledge Gaps</Link>}</div></div>}
      {graph.nodes.length > 0 && <ServiceLandscape graph={graph} compact siteId={workspace.siteId} quick={quick} onSelect={(node) => router.push(graphHref({ focus: node.key }))} />}
      {partial > 0 && <p className="ops-meta">{partial} Services are not yet connected to visible Assets or Business Functions.</p>}
    </>}
  </section>;
}

function Attention({ graph, summary, hasPermission }) {
  const { unknown, ungrouped, relationships } = dependencyAttention(graph);
  const items = [
    { label: "Unknown dependency effects", icon: "discovery", count: unknown, href: "/knowledge-graph", text: "Recorded dependencies with an unknown failure effect." },
    { label: "Ungrouped dependencies", icon: "knowledge-graph", count: ungrouped, href: "/knowledge-graph", text: "Review whether these dependencies need explicit behaviour." },
    ...(hasPermission("knowledge_gaps.view") ? [{ label: "Knowledge gaps", icon: "knowledge-gaps", count: summary?.open_knowledge_gap_count, href: "/knowledge-gaps", text: "Required or conditional knowledge that needs attention." }, { label: "Critical Services with gaps", icon: "services", count: graph?.nodes.filter((n) => n.entity_type === "service" && n.criticality_rank >= 75 && n.open_gap_count > 0).length, href: "/services?attention=required_gaps", text: "High criticality Services with recorded knowledge gaps." }] : []),
  ];
  return <section className="ops-card"><header className="ops-section-header"><div><h2>Knowledge attention</h2><p>What Atlas needs you to review.</p></div></header>{items.map((item) => <Link className="ops-attention-row" href={item.href} key={item.label}><span className="ops-icon-tile"><NavigationIcon name={item.icon} /></span><div><strong>{item.label}</strong><small>{item.text}</small></div><span className="ops-badge">{item.count ?? "—"}{graph?.truncated && item.href === "/knowledge-graph" ? "+" : ""}</span><span aria-hidden="true">›</span></Link>)}<details className="graph-semantic-list"><summary>Relationships needing dependency-impact classification</summary><ul>{relationships.map(edge => <li key={edge.key}><Link href={`/services/${edge.source.entity_id}#dependency-impact`}>{edge.source.name} — {edge.label} → {edge.target.name}</Link><small> · {!edge.dependency_group_id ? "Impact not classified" : "Unknown effect"}</small></li>)}</ul>{graph && !relationships.length && <p>No visible dependencies need classification.</p>}{graph?.truncated && <p>Showing relationships within this bounded overview. Other Services may also need review.</p>}</details><p className="ops-meta">Knowledge quality based on recorded data.</p></section>;
}

function CriticalServices({ graph, graphError }) {
  const services = graph?.nodes.filter((n) => n.entity_type === "service" && n.criticality_rank >= 75).sort((a, b) => b.criticality_rank - a.criticality_rank || a.name.localeCompare(b.name)) || [];
  return <section className="ops-card"><header className="ops-section-header"><div><h2>Critical Services</h2><p>Recorded status and required knowledge completeness.</p></div><Link className="text-button" href="/services">View all</Link></header><div className="critical-service-grid">{services.slice(0, 3).map((node) => <Link className="critical-service-card" href={graphHref({ focus: node.key })} key={node.key}>
    <div className="critical-service-heading"><EntityMark type="service" /><span className="ops-badge">{node.criticality_name}</span></div>
    <strong>{node.name}</strong>
    <div className="critical-service-status"><RecordedStatus state={node.operational_state} /><span>{(node.operational_state || "unknown").replaceAll("_", " ")}</span></div>
    <div className="critical-service-completeness"><span>Required knowledge</span><CompletenessLine node={node} /></div>
  </Link>)}</div>{!graph ? <p role="status">{graphError ? "Critical Services are unavailable." : "Loading Services…"}</p> : !services.length && <p className="ops-meta">No high criticality Services recorded in this view.</p>}{services.length > 3 && <Link className="text-button" href="/services">View {services.length - 3} more Services →</Link>}</section>;
}

const changeIcons = {
  entity_discovered: "discovery", entity_reobserved: "discovery", entity_no_longer_observed: "discovery",
  entity_accepted: "reconciliation", assertion_retracted: "reconciliation", exception_recorded: "reconciliation",
  relationship_added: "knowledge-graph", relationship_removed: "knowledge-graph",
  service_dependency_added: "knowledge-graph", service_dependency_removed: "knowledge-graph",
  service_business_function_added: "business-functions", service_business_function_removed: "business-functions",
  knowledge_gap_opened: "knowledge-gaps", knowledge_gap_resolved: "knowledge-gaps", service_completeness_changed: "knowledge-gaps",
  service_created: "services", service_updated: "services", service_archived: "services",
};

function RecentChanges({ changes, changesError, hasPermission }) {
  return <section className="ops-card"><header className="ops-section-header"><div><h2>Recent meaningful changes</h2><p>Updates to accepted Atlas knowledge.</p></div>{hasPermission("changes.view") && <Link className="text-button" href="/changes">View all</Link>}</header>{!hasPermission("changes.view") ? <p className="ops-meta">Changes are unavailable with your current permissions.</p> : changes == null ? <p role="status">{changesError ? "Recent changes are unavailable." : "Loading changes…"}</p> : !changes.length ? <p className="ops-meta">No meaningful changes recorded yet.</p> : <ol className="ops-activity">{changes.map((change) => <li key={change.id}><Link href="/changes">
    <span className="ops-icon-tile"><NavigationIcon name={changeIcons[change.change_type] || "changes"} /></span>
    <div className="ops-activity-copy"><strong>{change.summary}</strong><small>{change.entity_name_snapshot}</small><div className="ops-activity-meta">{change.change_type && <span>{change.change_type.replaceAll("_", " ")}</span>}<time dateTime={change.occurred_at}>{new Date(change.occurred_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</time></div></div>
    <span className="ops-activity-chevron" aria-hidden="true">›</span>
  </Link></li>)}</ol>}</section>;
}

const widgetComponents = { "environment-summary": Summary, "environment-overview": EnvironmentOverview, attention: Attention, "critical-services": CriticalServices, "recent-meaningful-changes": RecentChanges };

export default function DashboardPage() {
  const { hasAnyPermission, hasPermission } = useAuth();
  const workspace = useWorkspaceContext();
  const [data, setData] = useState({});
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const canView = hasAnyPermission(["customers.view", "sites.view", "assets.view", "relationships.view", "networks.view", "services.view", "business_functions.view"]);
  const canGraph = hasAnyPermission(["assets.view", "services.view", "business_functions.view"]);
  useEffect(() => {
    if (!canView || !workspace.customerId || !workspace.siteId) return;
    let active = true;
    setData(canGraph ? {} : { graphError: true }); setError("");
    const requests = [["summary", "/dashboard/summary?include_customer_wide=true"], ...(canGraph ? [["graph", "/operational-graph/landscape"]] : []), ...(hasPermission("changes.view") ? [["changes", "/changes?limit=6&offset=0&include_customer_wide=true"]] : [])];
    Promise.all(requests.map(async ([key, path]) => { try { const response = await apiRequest(path); if (active) setData((old) => ({ ...old, [key]: key === "graph" ? normalizeOperationalGraph(response) : key === "changes" ? response.items : response })); } catch (e) { if (active) { setError(e.message || "Atlas could not load this dashboard."); setData((old) => ({ ...old, [`${key}Error`]: true })); } } }));
    return () => { active = false; };
  }, [canView, canGraph, hasPermission, workspace.customerId, workspace.siteId, retry]);
  if (!canView) return <AccessDenied />;
  return <div className="operations-page"><PageHeader title="Dashboard" description="Your environment, built from recorded knowledge." />
    {!workspace.customerId || !workspace.siteId ? <section className="ops-card"><h2>Set up your environment</h2><p>Select a Customer and Site to build your service landscape.</p>{hasPermission("sites.manage") && <Link className="text-button" href="/admin/sites">Manage Sites →</Link>}</section> : <>
      {error && <div className="error-banner" role="alert">{error} <button className="text-button" onClick={() => setRetry((n) => n + 1)} type="button">Try again</button></div>}
      <div className="ops-dashboard">{WIDGETS.map((widget) => { const Component = widgetComponents[widget.id]; return <div className={`widget-${widget.id}`} data-widget-id={widget.id} key={widget.id}><Component {...data} workspace={workspace} hasPermission={hasPermission} /></div>; })}</div>
    </>}
  </div>;
}
