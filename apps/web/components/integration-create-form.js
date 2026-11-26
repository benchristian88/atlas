"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import { apiRequest } from "../lib/api";
import { initialConfig, configurationPayload } from "../lib/integration-configuration.mjs";
import { Button } from "./button";
import { ConnectionFields, ConnectionResult } from "./integration-configuration";
import { Section, Surface } from "./section";

export function IntegrationCreateForm({
  forms, customers = [], sites = [], initialCustomer = "", initialSite = "", fixedScope, selectedForm,
  canManageIn, canRunIn, onCreate, onCancel, onDirty, onBusy,
}) {
  const guided = Boolean(fixedScope);
  const [connector, setConnector] = useState(selectedForm?.connector_id || "");
  const [customer, setCustomer] = useState(fixedScope?.customer.id || initialCustomer);
  const [site, setSite] = useState(fixedScope?.site.id || initialSite);
  const [name, setName] = useState("");
  const [config, setConfig] = useState(() => selectedForm ? initialConfig(selectedForm) : {});
  const [credentials, setCredentials] = useState({});
  const [scopes, setScopes] = useState(() => defaultScopes(selectedForm));
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [result, setResult] = useState(null);
  const [creationKey, setCreationKey] = useState("");
  const active = useRef(false);
  const operation = useRef(false);
  const heading = useRef(null);
  const notice = useRef(null);
  const form = selectedForm || forms.find(item => item.connector_id === connector);
  const canManage = canManageIn(customer, site);
  const canRun = canRunIn(customer, site);
  const verified = result?.success === true;

  useEffect(() => {
    active.current = true;
    setCreationKey(crypto.randomUUID());
    return () => { active.current = false; };
  }, []);
  useEffect(() => { if (guided) heading.current?.focus(); }, [guided, step]);
  useEffect(() => { if (guided && feedback) notice.current?.focus(); }, [guided, feedback]);

  function change(setter, value) {
    setter(value);
    setResult(null);
    setFeedback(null);
    onDirty?.(true);
  }

  function choose(id) {
    const next = forms.find(item => item.connector_id === id);
    change(setConnector, id);
    setConfig(next ? initialConfig(next) : {});
    setCredentials({});
    setScopes(defaultScopes(next));
  }

  function body() {
    return {
      creation_key: creationKey, name, customer_id: customer, site_id: site, connector_id: connector,
      ...configurationPayload(form, config, credentials), selected_scopes: scopes,
      ...(guided ? { start_initial_discovery: false, expected_connector_digest: form.digest } : {}),
    };
  }

  async function perform(testing) {
    if (operation.current || !creationKey || !form || !canManage || !site
        || (testing && !canRun) || (!testing && guided && (!verified || !canRun))) return;
    operation.current = true;
    setBusy(true);
    onBusy?.(true);
    setFeedback(null);
    if (testing) setResult(null);
    try {
      if (testing) {
        const tested = await apiRequest(`/integration-forms/${encodeURIComponent(connector)}/test-connection`, {
          method: "POST", body: JSON.stringify(body()), omitContext: true,
        });
        if (active.current) {
          setResult(tested);
          if (guided && !tested.success) setFeedback({ message: "Connection test failed. Check the result and return to Connection to make corrections." });
        }
      } else {
        await onCreate(body());
        if (active.current) setCredentials({});
      }
    } catch (error) {
      if (active.current) {
        if (error.details?.detail?.code === "connector_changed") setResult(null);
        setFeedback({ message: error.message });
      }
    } finally {
      operation.current = false;
      if (active.current) setBusy(false);
      onBusy?.(false);
    }
  }

  function submit(event) {
    event.preventDefault();
    if (operation.current || !canManage || !site || !form) return;
    if (step === 3) void perform(false);
    else if (step !== 2 || !guided || verified) {
      setFeedback(null);
      setStep(step + 1);
    }
  }

  return <>
    {feedback && <div className="error-banner" role="alert" ref={notice} tabIndex={-1}>{feedback.message}</div>}
    <ol className="integration-steps" aria-label="Configuration steps">{["Scope", "Connection", "Test", "Review"].map((label, index) => <li key={label} aria-current={step === index ? "step" : undefined}>{index + 1}. {label}</li>)}</ol>
    <Surface><form onSubmit={submit} aria-label={guided ? `Configure ${form.name}` : undefined}>
      {step === 0 && <Section title="Connector and scope" headingRef={guided ? heading : undefined}><div className="form-grid">
        {guided ? <dl className="ops-definition"><dt>Connector</dt><dd>{form.name} · {form.version}</dd><dt>Customer</dt><dd>{fixedScope.customer.name}</dd><dt>Site</dt><dd>{fixedScope.site.name}</dd></dl> : <>
          <label className="field"><span>Connector</span><select aria-label="Connector" required value={connector} onChange={event => choose(event.target.value)}><option value="">Select Connector</option>{forms.map(item => <option key={item.connector_id} value={item.connector_id}>{item.name} · {item.version}</option>)}</select></label>
          <label className="field"><span>Customer</span><select aria-label="Customer" required value={customer} onChange={event => { change(setCustomer, event.target.value); setSite(""); }}><option value="">Select customer</option>{customers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label className="field"><span>Site</span><select aria-label="Site" required value={site} onChange={event => change(setSite, event.target.value)}><option value="">Select site</option>{sites.filter(item => item.customer_id === customer).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        </>}
        <label className="field"><span>Integration name</span><input aria-label="Integration name" required maxLength={255} value={name} onChange={event => change(setName, event.target.value)} /></label>
      </div></Section>}
      {step === 1 && form && <Section title="Connection" headingRef={guided ? heading : undefined}>
        <ConnectionFields form={form} config={config} credentials={credentials} onConfig={value => change(setConfig, value)} onCredentials={value => change(setCredentials, value)} />
        {form.discovery_scopes.length > 0 && <fieldset><legend>Declared scopes · configuration only</legend>{form.discovery_scopes.map(scope => <label key={scope.key}><input type="checkbox" checked={scopes.includes(scope.key)} disabled={scope.required} onChange={event => change(setScopes, event.target.checked ? [...scopes, scope.key] : scopes.filter(key => key !== scope.key))} />{scope.label}</label>)}</fieldset>}
      </Section>}
      {step === 2 && <Section title="Test Connection" headingRef={guided ? heading : undefined}><p>Test authentication and the source version through the local runtime.</p><Button loading={busy} disabled={!canRun} onClick={() => perform(true)}>Test Connection</Button>{!canRun && <p>You need permission to test connections in this scope.</p>}<ConnectionResult result={result} /></Section>}
      {step === 3 && form && <Section title="Review integration" headingRef={guided ? heading : undefined}><dl className="ops-definition"><dt>Name</dt><dd>{name}</dd><dt>Connector</dt><dd>{form.name} · {form.version}</dd><dt>Scope</dt><dd>{fixedScope?.customer.name || customers.find(item => item.id === customer)?.name} · {fixedScope?.site.name || sites.find(item => item.id === site)?.name}</dd><dt>Credentials</dt><dd>Write-only · ready to configure</dd>{Object.entries(configurationPayload(form, config).config).map(([key, value]) => <Fragment key={key}><dt>{form.connection_fields.find(field => field.key === key)?.label}</dt><dd>{String(value)}</dd></Fragment>)}</dl><ConnectionResult result={result} />{!result && <p>Connection has not been tested.</p>}</Section>}
      <div className="form-actions">
        {onCancel && <Button disabled={busy} onClick={onCancel}>Cancel configuration</Button>}
        {step > 0 && <Button disabled={busy} onClick={() => { setFeedback(null); setStep(step - 1); }}>Back</Button>}
        <Button type="submit" variant="primary" loading={busy} disabled={!canManage || !form || !site || (guided && step >= 2 && (!verified || !canRun))}>{step === 3 ? guided ? form.capabilities?.discover === "read_only" ? "Save & discover" : "Save integration" : "Create integration" : step === 2 ? "Review" : "Continue"}</Button>
      </div>
    </form></Surface>
  </>;
}

function defaultScopes(form) {
  return form?.discovery_scopes.filter(scope => scope.default_enabled).map(scope => scope.key) || [];
}
