"use client";
import { use, useEffect, useState } from "react";
import { useAuth } from "../../../components/auth-context";
import { Button } from "../../../components/button";
import { PageHeader } from "../../../components/page-header";
import { Section, Surface } from "../../../components/section";
import { StatusIndicator } from "../../../components/status-indicator";
import { ConnectionFields, ConnectionResult } from "../../../components/integration-configuration";
import { apiRequest } from "../../../lib/api";
import { initialConfig, configurationPayload } from "../../../lib/integration-configuration.mjs";
import { formatIntegrationTime } from "../../../lib/integrations.mjs";
import { DISCOVERY_SCHEDULES, discoveryControls } from "../../../lib/discovery.mjs";
import { DebugNextRunControl } from "../../../components/discovery-diagnostics";

export default function IntegrationDetail({ params }) {
  const { id } = use(params), auth = useAuth();
  const [record, setRecord] = useState(null), [form, setForm] = useState(null), [config, setConfig] = useState({});
  const [error, setError] = useState(""), [busy, setBusy] = useState(false), [result, setResult] = useState(null);
  const [replacing, setReplacing] = useState(false), [credentials, setCredentials] = useState({}), [confirm, setConfirm] = useState("");
  async function load() { const [row, forms] = await Promise.all([apiRequest(`/integrations/${id}`), apiRequest("/integration-forms", { omitContext: true })]); setRecord(row); const current = forms.find(item => item.connector_id === row.connector_id); setForm(current); setConfig(current ? initialConfig(current, row.config) : {}); setCredentials({}); setReplacing(false); }
  useEffect(() => { load().catch(reason => setError(reason.message)); }, [id]);
  const manage = record && !record.retired_at && record.generic && auth.hasPermissionInContext("integrations.manage", record.customer_id, record.site_id);
  const run = record && !record.retired_at && record.generic && auth.hasPermissionInContext("integrations.run", record.customer_id, record.site_id);
  const discovery = discoveryControls(record, run, manage);
  useEffect(() => {
    if (!record?.current_run_id && !record?.debug_next_run) return;
    let active = true;
    const timer = setInterval(() => apiRequest(`/integrations/${id}`).then(value => { if (active) setRecord(value); }).catch(reason => { if (active) setError(reason.message); }), 3000);
    return () => { active = false; clearInterval(timer); };
  }, [id, record?.current_run_id, record?.debug_next_run]);
  async function discoveryAction(path, method, body) {
    setBusy(true); setError("");
    try { await apiRequest(path, { method, ...(body ? { body: JSON.stringify(body) } : {}) }); setRecord(await apiRequest(`/integrations/${id}`)); }
    catch (reason) { setError(reason.message); } finally { setBusy(false); }
  }
  async function action(path, method, body, testing = false) { setBusy(true); setError(""); try { const value = await apiRequest(`/integrations/${id}${path}`, { method, ...(body ? { body: JSON.stringify(body) } : {}) }); if (testing) setResult(value); else setResult(null); setConfirm(""); await load(); } catch (reason) { setError(reason.message); } finally { setBusy(false); } }
  return <div><PageHeader title={record?.name || "Integration"} description={record ? `${record.connector_id} · ${record.site_name || "Site"}` : "Loading connection…"} actions={<><Button href="/integrations">All integrations</Button>{run && <Button loading={busy} disabled={!record.credential_configured} onClick={() => action("/test-connection", "POST", null, true)}>Test Connection</Button>}</>} />
    {error && <div className="error-banner" role="alert">{error}</div>}
    {record && <><Section title="Connection"><Surface><dl className="ops-definition"><dt>Status</dt><dd><StatusIndicator state={record.status} /></dd><dt>Connector version</dt><dd>{record.connector_version || "Legacy connection"}</dd><dt>Credentials</dt><dd>{record.credential_configured ? "Configured" : "Not configured"}</dd><dt>Last Test Connection</dt><dd>{formatIntegrationTime(record.last_test_at)}{record.last_test_status && ` · ${record.last_test_status.replaceAll("_", " ")}`}</dd><dt>Detected source version</dt><dd>{record.source_version || "Not detected"}</dd><dt>Compatibility</dt><dd>{record.source_compatibility || "Not tested"}</dd></dl><ConnectionResult result={result} />{record.source_compatibility === "untested" && <p className="warning-banner">This source version has not been qualified.</p>}</Surface></Section>
    {record.generic && <Section title="Discovery">
      {!record.discovery_capable ? <p>Inventory discovery is unavailable in this Connector version.</p> : <>
        <dl className="ops-definition"><dt>Last run</dt><dd>{record.last_run_at ? formatIntegrationTime(record.last_run_at) : "No runs"}</dd><dt>Last success</dt><dd>{record.last_success_at ? formatIntegrationTime(record.last_success_at) : "No successful runs"}</dd><dt>Next run</dt><dd>{record.next_run_at ? formatIntegrationTime(record.next_run_at) : "Manual"}</dd><dt>Current run</dt><dd>{record.current_run_status || "Idle"}</dd></dl>
        {record.last_error_code && <p className="warning-banner" role="status">Discovery: {record.last_error_code.replaceAll("_", " ")}</p>}
        <div className="form-actions">{discovery.run && <Button variant="primary" loading={busy} disabled={!discovery.eligible || discovery.active} onClick={() => discoveryAction(`/integrations/${id}/run`, "POST")}>Run Now</Button>}{record.current_run_id && <Button href={`/discovery-runs/${record.current_run_id}`}>View current run</Button>}{discovery.run && discovery.active && <Button disabled={busy} onClick={() => discoveryAction(`/discovery-runs/${record.current_run_id}/cancel`, "POST")}>Cancel run</Button>}<Button href={`/discovery-runs?integration_id=${id}`}>Run history</Button></div>
        {discovery.schedule && <label className="field"><span>Discovery schedule</span><select disabled={busy} value={record.schedule_preset || "manual"} onChange={event => discoveryAction(`/integrations/${id}/schedule`, "PUT", { preset: event.target.value })}>{DISCOVERY_SCHEDULES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}
        <DebugNextRunControl armed={record.debug_next_run} allowed={!record.retired_at && auth.hasGlobalPermission("integration_runtime.manage")} busy={busy} onChange={enabled => discoveryAction(`/integrations/${id}/debug-next-run`, "PUT", { enabled })} />
      </>}
    </Section>}
    {record.generic && !form && !record.retired_at && <p className="warning-banner">The verified configuration form is unavailable. Ask a global administrator to check the package and required mappings.</p>}
    {form && !record.retired_at && <Section title="Configuration"><Surface><form onSubmit={event => { event.preventDefault(); action("", "PATCH", { config: configurationPayload(form, config).config }); }}><ConnectionFields form={form} config={config} onConfig={setConfig} secretMode="state" configuredFields={record.configured_fields} />{manage && <div className="form-actions"><Button loading={busy} type="submit" variant="primary">Save configuration</Button><Button disabled={busy} onClick={() => action("", "PATCH", { enabled: !record.enabled })}>{record.enabled ? "Disable integration" : "Enable integration"}</Button></div>}</form></Surface></Section>}
    {manage && form && <Section title="Credentials"><p>Credentials are write-only. Replacing them requires the complete declared credential set.</p>{!replacing ? <div className="form-actions"><Button onClick={() => { setCredentials({}); setReplacing(true); }}>Replace credentials</Button><Button variant="destructive" disabled={!record.credential_configured} onClick={() => setConfirm("clear")}>Clear credentials</Button></div> : <Surface><form onSubmit={event => { event.preventDefault(); action("/credentials", "PUT", { values: configurationPayload(form, config, credentials).credentials }); }}><ConnectionFields form={form} config={config} credentials={credentials} onCredentials={setCredentials} onlySecrets /><div className="form-actions"><Button type="submit" variant="primary" loading={busy}>Replace credentials</Button><Button onClick={() => { setCredentials({}); setReplacing(false); }}>Cancel replacement</Button></div></form></Surface>}</Section>}
    {manage && <Section title="Remove connection"><p>Removal destroys the live credentials and preserves its DataSource and knowledge history.</p><Button variant="destructive" onClick={() => setConfirm("retire")}>Remove connection</Button></Section>}
    {confirm && <Surface><p>{confirm === "clear" ? "Clear credentials? This connection will be unconfigured until replacement credentials are supplied." : "Remove this connection and destroy its live credentials? History and accepted knowledge will be retained."}</p><div className="form-actions"><Button variant="destructive" loading={busy} onClick={() => action(confirm === "clear" ? "/credentials" : "", "DELETE", { confirmed: true })}>Confirm {confirm === "clear" ? "clear" : "removal"}</Button><Button disabled={busy} onClick={() => setConfirm("")}>Cancel</Button></div></Surface>}</>}
  </div>;
}
