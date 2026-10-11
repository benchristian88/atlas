"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { useWorkspaceContext } from "../../components/workspace-context";
import { Button } from "../../components/button";
import { CatalogueFilters, useCatalogueSearch } from "../../components/catalogue-filters";
import { DataTable } from "../../components/data-table";
import { ConnectorCard, RuntimePanel } from "../../components/integration-panels";
import { PageHeader } from "../../components/page-header";
import { EmptyState, Section, Surface } from "../../components/section";
import { StatusIndicator } from "../../components/status-indicator";
import { apiRequest } from "../../lib/api";
import { connectorState, filterConnectors, formatIntegrationTime, integrationTab, INTEGRATION_TABS } from "../../lib/integrations.mjs";
import styles from "./integrations.module.css";

export default function IntegrationsPage() {
  const { hasPermissionInContext, hasGlobalPermission } = useAuth();
  const workspace = useWorkspaceContext();
  const params = useSearchParams();
  const canView = hasPermissionInContext("integrations.view", workspace.customerId, workspace.siteId);
  const canViewRuntime = hasGlobalPermission("integration_runtime.view");
  const canManage = hasGlobalPermission("integration_runtime.manage");
  const tab = integrationTab(params.get("tab"), canViewRuntime);
  const [catalogue, setCatalogue] = useState(null);
  const [runtime, setRuntime] = useState(null);
  const [configured, setConfigured] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState({});
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState("");
  const [query, setQuery] = useState("");
  const [state, setState] = useState("");
  const generation = useRef(0);
  const search = useCatalogueSearch(query, setQuery);
  const load = useCallback(async () => {
    const current = ++generation.current;
    if (!canView) return;
    setLoading(true);
    setErrors({});
    const requests = [apiRequest("/integration-catalogue", { omitContext: true }), apiRequest("/integrations"), canViewRuntime ? apiRequest("/integration-runtime", { omitContext: true }) : Promise.resolve(null)];
    const results = await Promise.allSettled(requests);
    if (current !== generation.current) return;
    const nextErrors = {};
    results.forEach((result, index) => {
      const key = ["catalogue", "configured", "runtime"][index];
      if (result.status === "rejected") nextErrors[key] = result.reason.message || `Atlas could not load ${key}.`;
      else if (key === "catalogue") setCatalogue(result.value);
      else if (key === "configured") setConfigured(result.value);
      else setRuntime(result.value);
    });
    setErrors(nextErrors);
    setLoading(false);
  }, [canView, canViewRuntime, workspace.reloadKey]);
  useEffect(() => { setConfigured([]); load(); return () => { generation.current += 1; }; }, [load]);
  if (!canView) return <AccessDenied />;
  const entries = catalogue?.entries || [];
  const visible = filterConnectors(entries, query, state);
  const states = [...new Set(entries.map(connectorState))];
  const clear = () => { search.reset(); setQuery(""); setState(""); };
  async function action(entry, selected) {
    if (!canManage || busy) return;
    setBusy(entry.connector_id); setSuccess(""); setErrors({});
    try {
      await apiRequest(selected.path, { method: selected.method, ...(selected.body ? { body: JSON.stringify(selected.body) } : {}), omitContext: true });
      setSuccess(`${entry.name}: ${selected.action === "remove" ? "package removed" : "package activated"}.`);
      await load();
    } catch (error) { setErrors({ catalogue: error.message || "Atlas could not change this Connector package." }); }
    finally { setBusy(""); }
  }
  const activeError = errors[tab];
  return <div className={styles.page}>
    <PageHeader eyebrow="Connections" title="Integrations" description="Inspect configured connections, Connector availability and the local runtime." actions={tab === "catalogue" && canViewRuntime ? <Button href="/integrations?tab=runtime">View runtime</Button> : undefined} />
    <nav className="admin-tabs" aria-label="Integration views">{INTEGRATION_TABS.filter(value => value !== "runtime" || canViewRuntime).map(value => <Link key={value} href={value === "configured" ? "/integrations" : `/integrations?tab=${value}`} className={tab === value ? "active" : ""} aria-current={tab === value ? "page" : undefined}>{value[0].toUpperCase() + value.slice(1)}</Link>)}</nav>
    {activeError && <div className="error-banner" role="alert">{activeError}</div>}
    {success && <div className="success-banner" role="status">{success}</div>}
    {tab === "configured" && <>
      <div className={styles.stats}><Surface><dl><dt>Configured</dt><dd>{loading ? "Loading…" : errors.configured ? "Unavailable" : `${configured.length} integration${configured.length === 1 ? "" : "s"}`}</dd></dl></Surface>{canViewRuntime && <Surface><dl><dt>Runtime</dt><dd>{runtime ? <StatusIndicator state={runtime.status} /> : loading ? "Checking…" : "Unavailable"}</dd></dl></Surface>}</div>
      {configured.length || loading || activeError ? <DataTable label="Configured integrations" loading={loading} error={activeError} rows={configured} onRefresh={load} columns={[{ key: "name", label: "Integration" }, { key: "connector_id", label: "Connector" }, { key: "scope", label: "Scope", render: item => [item.customer_name, item.site_name].filter(Boolean).join(" · ") || "Customer / site" }, { key: "status", label: "Status", render: item => <StatusIndicator state={item.status} /> }]} /> : <Surface><EmptyState title="No configured integrations" description="Browse the Connector catalogue to see available packages." action={<Button href="/integrations?tab=catalogue">Browse catalogue</Button>} /></Surface>}
    </>}
    {tab === "catalogue" && <>
      <CatalogueFilters label="Search Connectors" search={search} activeCount={state ? 1 : 0} onClear={clear}><label className="field"><span>Package state</span><select value={state} onChange={event => setState(event.target.value)}><option value="">All states</option>{states.map(value => <option key={value} value={value}>{value.replaceAll("_", " ").replace(/^./, letter => letter.toUpperCase())}</option>)}</select></label></CatalogueFilters>
      <Section title="Connector catalogue" className={styles.section} actions={<Button variant="quiet" loading={loading} onClick={load}>Refresh</Button>}>
        {loading && !catalogue ? <div className="status-banner" role="status">Loading Connector catalogue…</div> : visible.length > 0 ? <div className={styles.grid}>{visible.map(entry => <ConnectorCard key={entry.connector_id} entry={entry} className={styles.card} canManage={canManage} busy={busy} onAction={action} />)}</div> : !activeError && <EmptyState title="No matching Connectors" description="Clear your filters to view the catalogue." />}
        {catalogue && <p className={styles.meta}>{catalogue.source === "bootstrap" ? "Included offline catalogue" : "Connector catalogue"}{catalogue.checked_at ? ` · Checked ${formatIntegrationTime(catalogue.checked_at)}` : ""}</p>}
      </Section>
    </>}
    {tab === "runtime" && <Section title="Integration runtime" className={styles.section} actions={<Button loading={loading} onClick={load}>Refresh health</Button>}>
      {loading && !runtime ? <div className="status-banner" role="status">Checking runtime health…</div> : <div className={styles.grid}><RuntimePanel runtime={runtime} className={styles.runtime} healthClassName={styles.runtime} technicalClassName={styles.technical} /></div>}
    </Section>}
  </div>;
}
