"use client";

import { Button } from "../../../components/button";

import { AuditInvestigation, AuditTarget } from "../../../components/audit-investigation";
import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { AccessDenied } from "../../../components/access-denied";
import { useAuth } from "../../../components/auth-context";
import { PageHeader } from "../../../components/page-header";
import { useWorkspaceContext } from "../../../components/workspace-context";
import { apiRequest } from "../../../lib/api";
import { auditReferences, needsIntegrationName } from "../../../lib/audit-details.mjs";

const PAGE_SIZE = 30;
const EMPTY_FILTERS = { actor: "", action: "", entity_type: "", date_from: "", date_to: "" };

function timestamp(value) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "medium" }).format(new Date(value));
}

export default function AuditAdminPage() {
  const { hasPermission, hasPermissionInContext } = useAuth();
  const { customerId, siteId, customers, sites, reloadKey } = useWorkspaceContext();
  const loadGeneration = useRef(0);
  const [result, setResult] = useState(null);
  const [integrations, setIntegrations] = useState([]);
  const [expanded, setExpanded] = useState({});
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [view, setView] = useState({ filters: EMPTY_FILTERS, scope: reloadKey, offset: 0 });
  const canView = hasPermission("audit.view");
  const canViewIntegrations = hasPermissionInContext("integrations.view", customerId, siteId);

  if (view.scope !== reloadKey) {
    setView({ ...view, scope: reloadKey, offset: 0 });
    setExpanded({});
  }

  const load = useCallback(async () => {
    if (!canView) return;
    const generation = ++loadGeneration.current;
    setResult(null);
    setIntegrations([]);
    try {
      // The extra authorised match indicates whether another page is available.
      const query = new URLSearchParams({ limit: String(PAGE_SIZE + 1), offset: String(view.offset) });
      for (const [key, value] of Object.entries(view.filters)) {
        if (!value) continue;
        query.set(key, key.startsWith("date_") ? new Date(value).toISOString() : value);
      }
      if (customerId) query.set("customer_id", customerId);
      if (siteId) query.set("site_id", siteId);
      const rows = await apiRequest(`/audit-events?${query}`);
      if (generation !== loadGeneration.current) return;
      const events = rows.slice(0, PAGE_SIZE);
      setResult({ view, events, hasNext: rows.length > PAGE_SIZE, error: "" });
      const integrationIds = new Set(events.filter(needsIntegrationName).map(event => event.target_id));
      if (canViewIntegrations && integrationIds.size) {
        // Keep only relevant names from the existing bounded, workspace-scoped list.
        apiRequest("/integrations").catch(() => []).then((visibleIntegrations) => {
          if (generation === loadGeneration.current && Array.isArray(visibleIntegrations)) {
            setIntegrations(visibleIntegrations.filter(integration => integrationIds.has(integration.id)));
          }
        });
      }
    } catch (requestError) {
      if (generation === loadGeneration.current) {
        setResult({ view, events: [], hasNext: false, error: requestError.message || "Atlas could not load the audit log." });
      }
    }
  }, [view, canView, canViewIntegrations, customerId, siteId]);

  useEffect(() => {
    load();
    return () => { loadGeneration.current += 1; };
  }, [load]);
  if (!canView) return <AccessDenied />;

  const loading = result?.view !== view;
  const { events, hasNext, error } = loading ? { events: [], hasNext: false, error: "" } : result;
  const { offset } = view;

  function updateView(appliedFilters, offset = 0) {
    setView({ ...view, filters: appliedFilters, offset });
    setExpanded({});
  }

  return (
    <>
      <PageHeader eyebrow="System" title="Audit log" description="Review security-sensitive and administrative changes within your authorised scope." />
      <form className="filter-card" onSubmit={(event) => { event.preventDefault(); updateView(filters); }}>
        <div className="form-grid audit-filter-grid">
          <label className="field"><span>Actor</span><input onChange={(event) => setFilters({ ...filters, actor: event.target.value })} placeholder="Email or display name" value={filters.actor} /></label>
          <label className="field"><span>Action</span><input onChange={(event) => setFilters({ ...filters, action: event.target.value })} placeholder="asset.updated" value={filters.action} /></label>
          <label className="field"><span>Entity type</span><input onChange={(event) => setFilters({ ...filters, entity_type: event.target.value })} placeholder="asset" value={filters.entity_type} /></label>
          <label className="field"><span>From</span><input onChange={(event) => setFilters({ ...filters, date_from: event.target.value })} type="datetime-local" value={filters.date_from} /></label>
          <label className="field"><span>To</span><input onChange={(event) => setFilters({ ...filters, date_to: event.target.value })} type="datetime-local" value={filters.date_to} /></label>
        </div>
        <div className="form-actions"><Button variant="secondary" onClick={() => { setFilters(EMPTY_FILTERS); updateView(EMPTY_FILTERS); }} type="button">Clear</Button><Button variant="primary" disabled={loading} type="submit">Apply filters</Button></div>
      </form>
      {error && <div className="error-banner" role="alert">{error}</div>}
      <section className="table-card" aria-label="Audit events">
        <div className="table-meta"><span role="status">{loading ? "Loading audit events…" : !error && `${events.length} ${events.length === 1 ? "event" : "events"} on this page`}</span><button className="text-button" disabled={loading} onClick={load} type="button">Refresh</button></div>
        <div className="table-scroll"><table><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Target</th><th>Result</th><th>Summary</th><th>Details</th></tr></thead><tbody>
          {!loading && !error && events.length === 0 && <tr><td className="empty-state" colSpan="7">{offset ? "No audit events on this page." : "No audit events match these filters."}</td></tr>}
          {events.map((event) => {
            const references = auditReferences(event, { customers, sites, integrations: canViewIntegrations ? integrations : [] });
            const isExpanded = Boolean(expanded[event.id]);
            return <Fragment key={event.id}>
              <tr>
                <td className="secondary-text">{timestamp(event.created_at)}</td>
                <td>{event.actor_snapshot || "System"}</td>
                <td><span className="mono">{event.event_type}</span></td>
                <td><AuditTarget object={references.object} /></td>
                <td>{event.success ? "Success" : "Failed"}</td>
                <td>{event.change_summary || "—"}</td>
                <td><button type="button" className="audit-disclosure" aria-label={isExpanded ? "Collapse audit record" : "Expand audit record"} aria-expanded={isExpanded} aria-controls={`audit-${event.id}`} onClick={() => setExpanded(current => ({ ...current, [event.id]: !current[event.id] }))}>{isExpanded ? "−" : "+"}</button></td>
              </tr>
              {isExpanded && <tr><td colSpan="7"><AuditInvestigation event={event} references={references} timestamp={timestamp} /></td></tr>}
            </Fragment>;
          })}
        </tbody></table></div>
      </section>
      {!loading && (offset > 0 || hasNext) && <nav className="pagination" aria-label="Audit log pages">
        <Button variant="secondary" disabled={offset === 0} onClick={() => updateView(view.filters, offset - PAGE_SIZE)} type="button">Previous</Button>
        {events.length > 0 && <span>Events {offset + 1}–{offset + events.length}</span>}
        <Button variant="secondary" disabled={!hasNext} onClick={() => updateView(view.filters, offset + PAGE_SIZE)} type="button">Next</Button>
      </nav>}
    </>
  );
}
