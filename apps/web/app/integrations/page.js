"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { useWorkspaceContext } from "../../components/workspace-context";
import { Button } from "../../components/button";
import { DataTable } from "../../components/data-table";
import { RuntimePanel } from "../../components/integration-panels";
import { OfficialCatalogue } from "../../components/official-catalogue";
import { PageHeader } from "../../components/page-header";
import { EmptyState, Section, Surface } from "../../components/section";
import { StatusIndicator } from "../../components/status-indicator";
import { apiRequest } from "../../lib/api";
import { requestConnectorAction } from "../../lib/connector-actions";
import { integrationTab, INTEGRATION_TABS } from "../../lib/integrations.mjs";
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
  const generation = useRef(0);
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
      if (result.status === "rejected") {
        nextErrors[key] = result.reason.message || `Atlas could not load ${key}.`;
        if (key === "catalogue" && [401, 403].includes(result.reason.status)) setCatalogue(null);
      }
      else if (key === "catalogue") setCatalogue(result.value);
      else if (key === "configured") setConfigured(result.value);
      else setRuntime(result.value);
    });
    setErrors(nextErrors);
    setLoading(false);
  }, [canView, canViewRuntime, workspace.reloadKey]);
  useEffect(() => { setConfigured([]); load(); return () => { generation.current += 1; }; }, [load]);
  if (!canView) return <AccessDenied />;
  async function action(entry, selected) {
    if (!canManage || busy) return;
    setBusy(entry.connector_id); setSuccess(""); setErrors({});
    try {
      await requestConnectorAction(selected);
      setSuccess(`${entry.name}: ${selected.action === "remove" ? "package removed" : "package activated"}.`);
      await load();
    } catch (error) { setErrors({ catalogue: error.message || "Atlas could not change this Connector package." }); }
    finally { setBusy(""); }
  }
  const activeError = errors[tab];
  return <div className={styles.page}>
    <PageHeader eyebrow="Connections" title="Integrations" description="Inspect configured connections, Connector availability and the local runtime." actions={tab === "configured" && hasPermissionInContext("integrations.manage", workspace.customerId, workspace.siteId) ? <Button href="/integrations/new" variant="primary">Add integration</Button> : tab === "catalogue" && canViewRuntime ? <Button href="/integrations?tab=runtime">View runtime</Button> : undefined} />
    <nav className="admin-tabs" aria-label="Integration views">{INTEGRATION_TABS.filter(value => value !== "runtime" || canViewRuntime).map(value => <Link key={value} href={`/integrations?tab=${value}`} className={tab === value ? "active" : ""} aria-current={tab === value ? "page" : undefined}>{value[0].toUpperCase() + value.slice(1)}</Link>)}</nav>
    {activeError && <div className="error-banner" role="alert">{activeError}</div>}
    {success && <div className="success-banner" role="status">{success}</div>}
    {tab === "configured" && <>
      <div className={styles.stats}><Surface><dl><dt>Configured</dt><dd>{loading ? "Loading…" : errors.configured ? "Unavailable" : `${configured.length} integration${configured.length === 1 ? "" : "s"}`}</dd></dl></Surface>{canViewRuntime && <Surface><dl><dt>Runtime</dt><dd>{runtime ? <StatusIndicator state={runtime.status} /> : loading ? "Checking…" : "Unavailable"}</dd></dl></Surface>}</div>
      {configured.length || loading || activeError ? <DataTable label="Configured integrations" loading={loading} error={activeError} rows={configured} onRefresh={load} columns={[{ key: "name", label: "Integration", render: item => item.generic ? <Link href={`/integrations/${item.id}`}>{item.name}</Link> : item.name }, { key: "connector_id", label: "Connector" }, { key: "scope", label: "Scope", render: item => [item.customer_name, item.site_name].filter(Boolean).join(" · ") || "Customer / site" }, { key: "status", label: "Status", render: item => <StatusIndicator state={item.status} /> }]} /> : <Surface><EmptyState title="No configured integrations" description="Add a connection using a verified installed Connector." action={<Button href="/integrations?tab=catalogue">Browse catalogue</Button>} /></Surface>}
    </>}
    {tab === "catalogue" && <OfficialCatalogue canViewOfficial={canViewRuntime} canManage={canManage} styles={styles} catalogue={catalogue} localLoading={loading} localError={errors.catalogue} busy={busy} onAction={action} onInstalled={load} />}
    {tab === "runtime" && <Section title="Integration runtime" className={styles.section} actions={<Button loading={loading} onClick={load}>Refresh health</Button>}>
      {loading && !runtime ? <div className="status-banner" role="status">Checking runtime health…</div> : <div className={styles.grid}><RuntimePanel runtime={runtime} className={styles.runtime} healthClassName={styles.runtime} technicalClassName={styles.technical} /></div>}
    </Section>}
  </div>;
}
