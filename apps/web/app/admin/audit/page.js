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

function timestamp(value) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "medium" }).format(new Date(value));
}

export default function AuditAdminPage() {
  const { hasPermission, hasPermissionInContext } = useAuth();
  const { customerId, siteId, customers, sites } = useWorkspaceContext();
  const loadGeneration = useRef(0);
  const [events, setEvents] = useState([]);
  const [integrations, setIntegrations] = useState([]);
  const [expanded, setExpanded] = useState({});
  const [filters, setFilters] = useState({ actor: "", action: "", entity_type: "", date_from: "", date_to: "" });
  const [appliedFilters, setAppliedFilters] = useState(filters);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const canView = hasPermission("audit.view");
  const canViewIntegrations = hasPermissionInContext("integrations.view", customerId, siteId);

  const load = useCallback(async () => {
    if (!canView) return;
    const generation = ++loadGeneration.current;
    setLoading(true);
    setError("");
    setIntegrations([]);
    try {
      const query = new URLSearchParams({ limit: "200" });
      for (const [key, value] of Object.entries(appliedFilters)) {
        if (!value) continue;
        query.set(key, key.startsWith("date_") ? new Date(value).toISOString() : value);
      }
      if (customerId) query.set("customer_id", customerId);
      if (siteId) query.set("site_id", siteId);
      const rows = await apiRequest(`/audit-events?${query}`);
      if (generation !== loadGeneration.current) return;
      setEvents(rows);
      if (canViewIntegrations && rows.some(needsIntegrationName)) {
        // The scoped list is bounded and optional. Missing names keep their audit fallback.
        apiRequest("/integrations").catch(() => []).then((visibleIntegrations) => {
          if (generation === loadGeneration.current && Array.isArray(visibleIntegrations)) setIntegrations(visibleIntegrations);
        });
      }
    } catch (requestError) {
      if (generation === loadGeneration.current) setError(requestError.message || "Atlas could not load the audit log.");
    } finally {
      if (generation === loadGeneration.current) setLoading(false);
    }
  }, [appliedFilters, canView, canViewIntegrations, customerId, siteId]);

  useEffect(() => {
    load();
    return () => { loadGeneration.current += 1; };
  }, [load]);
  if (!canView) return <AccessDenied />;

  function submit(event) {
    event.preventDefault();
    setAppliedFilters(filters);
  }

  return (
    <>
      <PageHeader eyebrow="System" title="Audit log" description="Review security-sensitive and administrative changes within your authorised scope." />
      <form className="filter-card" onSubmit={submit}>
        <div className="form-grid audit-filter-grid">
          <label className="field"><span>Actor</span><input onChange={(event) => setFilters({ ...filters, actor: event.target.value })} placeholder="Email or display name" value={filters.actor} /></label>
          <label className="field"><span>Action</span><input onChange={(event) => setFilters({ ...filters, action: event.target.value })} placeholder="asset.updated" value={filters.action} /></label>
          <label className="field"><span>Entity type</span><input onChange={(event) => setFilters({ ...filters, entity_type: event.target.value })} placeholder="asset" value={filters.entity_type} /></label>
          <label className="field"><span>From</span><input onChange={(event) => setFilters({ ...filters, date_from: event.target.value })} type="datetime-local" value={filters.date_from} /></label>
          <label className="field"><span>To</span><input onChange={(event) => setFilters({ ...filters, date_to: event.target.value })} type="datetime-local" value={filters.date_to} /></label>
        </div>
        <div className="form-actions"><Button variant="secondary" onClick={() => { const empty = { actor: "", action: "", entity_type: "", date_from: "", date_to: "" }; setFilters(empty); setAppliedFilters(empty); }} type="button">Clear</Button><Button variant="primary" disabled={loading} type="submit">Apply filters</Button></div>
      </form>
      {error && <div className="error-banner" role="alert">{error}</div>}
      <section className="table-card" aria-label="Audit events">
        <div className="table-meta"><span>{loading ? "Loading…" : `${events.length} events`}</span><button className="text-button" disabled={loading} onClick={load} type="button">Refresh</button></div>
        <div className="table-scroll"><table><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Target</th><th>Result</th><th>Summary</th><th>Details</th></tr></thead><tbody>
          {!loading && events.length === 0 && <tr><td className="empty-state" colSpan="7">No audit events match these filters.</td></tr>}
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
    </>
  );
}
