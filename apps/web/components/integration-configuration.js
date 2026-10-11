"use client";
import { visibleField, testMessage } from "../lib/integration-configuration.mjs";
import { StatusIndicator } from "./status-indicator";

export function ConnectionFields({ form, config, credentials = {}, onConfig, onCredentials, secretMode = "enter", configuredFields = [], onlySecrets = false }) {
  return <div className="form-grid">{form.connection_fields.filter(field => visibleField(field, config) && (!onlySecrets || field.secret)).map(field => {
    const id = `connection-${field.key}`, help = `${id}-help`;
    if (field.secret && secretMode === "state") return <div className="field" key={field.key}><span>{field.label}</span><span>{configuredFields.includes(field.key) ? "Configured" : "Not configured"}</span></div>;
    const value = (field.secret ? credentials : config)[field.key];
    const change = next => field.secret ? onCredentials({ ...credentials, [field.key]: next }) : onConfig({ ...config, [field.key]: next });
    const properties = { id, required: field.required, "aria-label": field.secret ? `${field.label} · Write-only` : field.label, "aria-describedby": field.help ? help : undefined };
    return <label className="field" key={field.key} htmlFor={id}><span>{field.label}{field.secret && " · Write-only"}</span>
      {field.type === "enum" ? <select {...properties} value={value ?? ""} onChange={event => change(event.target.value)}>{!field.default && <option value="">Select</option>}{field.options.map(option => <option key={String(option)} value={option}>{String(option).replaceAll("_", " ")}</option>)}</select>
      : field.type === "boolean" ? <input {...properties} required={false} type="checkbox" checked={value === true} onChange={event => change(event.target.checked)} />
      : <input {...properties} type={field.secret ? "password" : field.type === "number" ? "number" : field.type === "url" ? "url" : "text"} value={value ?? ""} autoComplete={field.secret ? "new-password" : "off"} minLength={field.validation?.min_length} maxLength={field.validation?.max_length || 2048} min={field.validation?.minimum} max={field.validation?.maximum} onChange={event => change(field.type === "number" ? event.target.value === "" ? "" : Number(event.target.value) : event.target.value)} />}
      {field.help && <small id={help}>{field.help}</small>}
    </label>;
  })}{form.connection_fields.some(field => !field.secret && field.type === "enum" && field.options.includes("insecure") && config[field.key] === "insecure") && <div className="warning-banner" role="status">Advanced TLS exception: certificate verification is disabled. Credentials could be exposed to an impersonated source. Prefer verification or a trusted fingerprint.</div>}</div>;
}

export function ConnectionResult({ result }) {
  if (!result) return null;
  return <div className={result.success ? "success-banner" : "error-banner"} role="status"><p>{testMessage(result)}</p>{result.source_version && <p>Detected source version: {result.source_version}</p>}{result.compatibility === "untested" && <p>This source version has not been qualified by the Connector. The connection result carries a compatibility warning.</p>}{result.permission_limited && <p>The token exposes limited permission information. Inventory capabilities have not been tested.</p>}</div>;
}
