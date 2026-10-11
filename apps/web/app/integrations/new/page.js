"use client";
import { Fragment, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../../components/auth-context";
import { useWorkspaceContext } from "../../../components/workspace-context";
import { AccessDenied } from "../../../components/access-denied";
import { Button } from "../../../components/button";
import { PageHeader } from "../../../components/page-header";
import { Section, Surface, EmptyState } from "../../../components/section";
import { ConnectionFields, ConnectionResult } from "../../../components/integration-configuration";
import { apiRequest } from "../../../lib/api";
import { initialConfig, configurationPayload } from "../../../lib/integration-configuration.mjs";

export default function AddIntegration() {
  const auth = useAuth(), workspace = useWorkspaceContext(), router = useRouter();
  const [forms, setForms] = useState(null), [connector, setConnector] = useState("");
  const [customer, setCustomer] = useState(workspace.customerId || ""), [site, setSite] = useState(workspace.siteId || "");
  const [name, setName] = useState(""), [config, setConfig] = useState({}), [credentials, setCredentials] = useState({}), [scopes, setScopes] = useState([]);
  const [step, setStep] = useState(0), [busy, setBusy] = useState(false), [error, setError] = useState(""), [result, setResult] = useState(null);
  const [creationKey, setCreationKey] = useState("");
  const canManage = auth.hasPermissionInContext("integrations.manage", customer || workspace.customerId, site || workspace.siteId);
  const canRun = auth.hasPermissionInContext("integrations.run", customer, site);
  useEffect(() => { let alive = true; setCreationKey(crypto.randomUUID()); apiRequest("/integration-forms", { omitContext: true }).then(value => { if (alive) setForms(value); }).catch(reason => { if (alive) setError(reason.message); }); return () => { alive = false; }; }, []);
  const sites = workspace.sites.filter(item => auth.hasPermissionInContext("integrations.manage", item.customer_id, item.id));
  const customers = workspace.customers.filter(item => sites.some(candidate => candidate.customer_id === item.id));
  const form = forms?.find(item => item.connector_id === connector);
  const choose = id => { const next = forms.find(item => item.connector_id === id); setConnector(id); setConfig(next ? initialConfig(next) : {}); setCredentials({}); setScopes(next?.discovery_scopes.filter(scope => scope.default_enabled).map(scope => scope.key) || []); setResult(null); };
  const changeConfig = value => { setConfig(value); setResult(null); };
  const changeCredentials = value => { setCredentials(value); setResult(null); };
  const body = () => ({ creation_key: creationKey, name, customer_id: customer, site_id: site, connector_id: connector, ...configurationPayload(form, config, credentials), selected_scopes: scopes });
  async function test() { setBusy(true); setError(""); try { setResult(await apiRequest(`/integration-forms/${encodeURIComponent(connector)}/test-connection`, { method: "POST", body: JSON.stringify(body()), omitContext: true })); } catch (reason) { setError(reason.message); } finally { setBusy(false); } }
  async function create() { setBusy(true); setError(""); try { const saved = await apiRequest("/integrations", { method: "POST", body: JSON.stringify(body()), omitContext: true }); setCredentials({}); router.push(`/integrations/${saved.id}`); } catch (reason) { setError(reason.message); } finally { setBusy(false); } }
  if (workspace.status === "ready" && !sites.length) return <AccessDenied />;
  return <div><PageHeader title="Add integration" description="Configure a scoped connection using a verified installed Connector." actions={<Button href="/integrations">Cancel</Button>} />
    {error && <div className="error-banner" role="alert">{error}</div>}
    {!forms ? <p role="status">Loading installed Connectors…</p> : !forms.length ? <EmptyState title="No configurable Connectors" description="A global administrator must install and activate a verified Connector and resolve any required mappings." action={<Button href="/integrations?tab=catalogue">Browse catalogue</Button>} /> : <>
    <ol className="integration-steps" aria-label="Configuration steps">{["Scope", "Connection", "Test", "Review"].map((label, index) => <li key={label} aria-current={step === index ? "step" : undefined}>{index + 1}. {label}</li>)}</ol>
    <Surface><form onSubmit={event => { event.preventDefault(); if (step === 3) create(); else setStep(step + 1); }}>
      {step === 0 && <Section title="Connector and scope"><div className="form-grid">
        <label className="field"><span>Connector</span><select aria-label="Connector" required value={connector} onChange={event => choose(event.target.value)}><option value="">Select Connector</option>{forms.map(item => <option key={item.connector_id} value={item.connector_id}>{item.name} · {item.version}</option>)}</select></label>
        <label className="field"><span>Customer</span><select aria-label="Customer" required value={customer} onChange={event => { setCustomer(event.target.value); setSite(""); }}><option value="">Select customer</option>{customers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="field"><span>Site</span><select aria-label="Site" required value={site} onChange={event => setSite(event.target.value)}><option value="">Select site</option>{sites.filter(item => item.customer_id === customer).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="field"><span>Integration name</span><input aria-label="Integration name" required maxLength={255} value={name} onChange={event => setName(event.target.value)} /></label>
      </div></Section>}
      {step === 1 && form && <Section title="Connection"><ConnectionFields form={form} config={config} credentials={credentials} onConfig={changeConfig} onCredentials={changeCredentials} />{form.discovery_scopes.length > 0 && <fieldset><legend>Declared scopes · configuration only</legend>{form.discovery_scopes.map(scope => <label key={scope.key}><input type="checkbox" checked={scopes.includes(scope.key)} disabled={scope.required} onChange={event => setScopes(event.target.checked ? [...scopes, scope.key] : scopes.filter(key => key !== scope.key))} />{scope.label}</label>)}</fieldset>}</Section>}
      {step === 2 && <Section title="Test Connection"><p>Test authentication and the source version through the local runtime.</p><Button loading={busy} disabled={!canRun} onClick={test}>Test Connection</Button>{!canRun && <p>You need permission to test connections in this scope.</p>}<ConnectionResult result={result} /></Section>}
      {step === 3 && form && <Section title="Review integration"><dl className="ops-definition"><dt>Name</dt><dd>{name}</dd><dt>Connector</dt><dd>{form.name} · {form.version}</dd><dt>Scope</dt><dd>{customers.find(item => item.id === customer)?.name} · {sites.find(item => item.id === site)?.name}</dd><dt>Credentials</dt><dd>Write-only · ready to configure</dd>{Object.entries(configurationPayload(form, config).config).map(([key, value]) => <Fragment key={key}><dt>{form.connection_fields.find(field => field.key === key)?.label}</dt><dd>{String(value)}</dd></Fragment>)}</dl><ConnectionResult result={result} />{!result && <p>Connection has not been tested.</p>}</Section>}
      <div className="form-actions">{step > 0 && <Button disabled={busy} onClick={() => setStep(step - 1)}>Back</Button>}<Button type="submit" variant="primary" loading={busy} disabled={!canManage || !form || !site}>{step === 3 ? "Create integration" : step === 2 ? "Review" : "Continue"}</Button></div>
    </form></Surface></>}
  </div>;
}
