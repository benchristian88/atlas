import { Button } from "./button";
import { EntityIdentity } from "./entity-identity";
import { Surface, EmptyState } from "./section";
import { StatusIndicator } from "./status-indicator";
import { connectorActions, connectorState, formatIntegrationTime, PACKAGING_LABELS, TRUST_LABELS, runtimeErrorMessage, runtimeOperations } from "../lib/integrations.mjs";

export function ConnectorCard({ entry, canManage, busy, onAction, className = "" }) {
  const actions = connectorActions(entry, canManage);
  return <Surface className={className}>
    <header className="catalogue-identity"><EntityIdentity type="connector" record={{ ...entry, id: entry.connector_id }} size={38} /><div className="catalogue-copy"><h3>{entry.name}</h3>{entry.category && <span className="secondary-text">{entry.category}</span>}</div></header>
    <p>{entry.description}</p>
    <dl className="ops-definition"><dt>Publisher</dt><dd>{entry.publisher || "Not specified"} <span className="secondary-text">· {TRUST_LABELS[entry.trust_tier] || "Trust not established"}</span></dd><dt>Version</dt><dd>{entry.version || "Not released"}{entry.installed_version && entry.installed_version !== entry.version && <span className="secondary-text"> · {entry.installed_version} installed</span>}</dd>{entry.licence && <><dt>Licence</dt><dd>{entry.licence}</dd></>}</dl>
    <div className="ops-section-header"><StatusIndicator state={connectorState(entry)} variant="badge" />{actions.length > 0 && <div className="form-actions">{actions.map(action => <Button key={action.action} variant={action.action === "remove" ? "destructive" : "primary"} loading={busy === entry.connector_id} disabled={Boolean(busy)} onClick={() => onAction(entry, action)}>{action.label}</Button>)}</div>}</div>
    {canManage && entry.package_available && entry.version && <Button href={`/integrations/mappings/${encodeURIComponent(entry.connector_id)}?version=${encodeURIComponent(entry.version)}`}>Resolve mappings</Button>}
    {entry.message && entry.message !== entry.description && entry.verification_status !== "metadata_only" && <p className="secondary-text">{entry.message}</p>}
    {entry.verification_status === "metadata_only" && <small className="secondary-text">Catalogue metadata verified. Executable bundle not released.</small>}
  </Surface>;
}

export function RuntimePanel({ runtime, className = "", healthClassName = "", technicalClassName = "" }) {
  if (!runtime) return <EmptyState title="Runtime information unavailable" description="Refresh runtime health to try again." />;
  const operations = runtimeOperations(runtime.capabilities);
  return <>
    <Surface className={className}>
      <h3>Atlas Ansible Runtime</h3>
      <p className="secondary-text">Local runtime for verified Connector packages.</p>
      <dl className="ops-definition"><dt>Runtime version</dt><dd>{runtime.runtime_version || "Unavailable"}</dd><dt>Protocol</dt><dd>{runtime.protocol_version || "Unavailable"}</dd><dt>Baseline</dt><dd>{runtime.baseline_id || "Unavailable"}</dd><dt>Packaging</dt><dd>{PACKAGING_LABELS[runtime.packaging_mode] || runtime.packaging_mode || "Unavailable"}</dd><dt>ansible-core</dt><dd>{runtime.ansible_core_version || "Unavailable"}</dd><dt>ansible-runner</dt><dd>{runtime.ansible_runner_version || "Unavailable"}</dd></dl>
      {(runtime.baseline_digest || runtime.dependency_lock_digest) && <details className={technicalClassName}><summary>Technical details</summary><dl className="ops-definition">{runtime.baseline_digest && <><dt>Baseline digest</dt><dd className="mono">{runtime.baseline_digest}</dd></>}{runtime.dependency_lock_digest && <><dt>Dependency lock digest</dt><dd className="mono">{runtime.dependency_lock_digest}</dd></>}{runtime.baseline_version && <><dt>Baseline version</dt><dd>{runtime.baseline_version}</dd></>}</dl></details>}
    </Surface>
    <Surface className={healthClassName}>
      <h3>Runtime health</h3>
      <dl className="ops-definition"><dt>Status</dt><dd><StatusIndicator state={runtime.status} /></dd><dt>Last checked</dt><dd>{formatIntegrationTime(runtime.last_checked_at)}</dd><dt>Installed packages</dt><dd>{runtime.installed_connector_count ?? "Unavailable"}</dd></dl>
      {runtime.last_error && <p role="status" className="secondary-text">{runtimeErrorMessage(runtime.last_error)}</p>}
      {runtime.status === "unavailable" && <p className="secondary-text">Accepted Atlas knowledge remains available while the runtime is unavailable.</p>}
      {operations.length > 0 && <details className={technicalClassName}><summary>Runtime capabilities</summary><ul>{operations.map(capability => <li key={capability}>{capability.replaceAll("_", " ")}</li>)}</ul></details>}
    </Surface>
  </>;
}
