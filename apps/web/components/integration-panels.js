import { Button } from "./button";
import { EntityIdentity } from "./entity-identity";
import { Surface, EmptyState, Section } from "./section";
import { StatusIndicator } from "./status-indicator";
import { connectorActions, connectorState, formatIntegrationTime, PACKAGING_LABELS, TRUST_LABELS, runtimeErrorMessage, runtimeOperations, formatOfficialCatalogueTime, officialCatalogueBlocked, officialCatalogueDiagnostic, officialCatalogueSummary } from "../lib/integrations.mjs";

export function OfficialCataloguePanel({ status, canManage, loading, refreshing, error, feedback, onRefresh, onReload, styles = {} }) {
  const pending = loading || refreshing;
  const inProgress = refreshing || status?.refresh_state === "in_progress";
  const blocked = officialCatalogueBlocked(status);
  const warning = status && (status.last_error_code || status.source_conflict || status.refresh_state === "failed");
  return <Section id="official-catalogue" title="Official Connector Catalogue" description="Remote connector metadata · read only" className={styles.official} actions={<div className="form-actions">
    <Button variant="quiet" disabled={pending} onClick={onReload}>Reload official status</Button>
    {canManage && <Button loading={refreshing} disabled={pending || !status || blocked || Boolean(error) || ["cooldown", "in_progress"].includes(feedback?.result)} onClick={onRefresh}>Check official catalogue</Button>}
  </div>}>
    <div aria-live="polite" aria-atomic="true" role="status">
      {loading && <p>Loading official catalogue status…</p>}
      {inProgress && <p>Checking the official catalogue… A check is in progress. Duplicate checks are unavailable.</p>}
      {feedback && feedback.result !== "failed" && <p className={styles.meta}>{feedback.message}</p>}
    </div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {feedback?.result === "failed" ? <div className="error-banner" role="alert">{feedback.message}</div> : warning && <div className="error-banner" role="alert">{officialCatalogueDiagnostic(status)}</div>}
    {status && <>
      <p>{officialCatalogueSummary(status)}</p>
      {status.trusted_remote_available && <p className={styles.meta}>Sequence {status.sequence} · Last confirmed: {formatOfficialCatalogueTime(status.last_confirmed_current_at)}. Past confirmation does not establish that the source is unchanged now.</p>}
      {blocked && !inProgress && <p role="status" className={styles.meta}>Checks are temporarily unavailable. Next permitted check: {formatOfficialCatalogueTime(status.next_attempt_at)}. Reload official status after this time.</p>}
      {status.trusted_remote_available && (status.entries.length ? <ul className={styles.officialEntries}>{status.entries.map((entry, index) => <li key={`${entry.connector_id}/${entry.version}/${index}`} className={styles.officialEntry}>
        <div><h3>{entry.name}</h3><p>{entry.description}</p></div>
        <dl className="ops-definition"><dt>Publisher</dt><dd>{entry.publisher}</dd><dt>Category</dt><dd>{entry.category}</dd><dt>Version</dt><dd>{entry.version}</dd><dt>Licence</dt><dd>{entry.licence}</dd><dt>Package</dt><dd>{entry.packageAvailable ? "Reported available; actions unavailable in this view" : "Unavailable for remote installation"}</dd>{entry.withdrawn && <><dt>Publication</dt><dd>Withdrawn</dd></>}</dl>
      </li>)}</ul> : <EmptyState title="No official connector entries" description="No entries are available in the accepted catalogue display." />)}
      <p className={styles.meta}>Official metadata is separate from locally available packages above. Package actions remain in the local catalogue.</p>
      <details className={styles.technical}><summary>Official catalogue technical details</summary><dl className="ops-definition">
        <dt>Schema</dt><dd>{status.schema_version}</dd>
        {status.content_digest && <><dt>SHA-256</dt><dd className="mono">{status.content_digest}</dd></>}
        {[["Generated", "generated_at"], ["Accepted", "accepted_at"], ["Last attempt", "last_attempt_at"], ["Last download", "last_download_at"], ["Last authenticity verification", "last_authenticity_verified_at"], ["Last source confirmation", "last_confirmed_current_at"], ["Next permitted check", "next_attempt_at"]].map(([label, key]) => <div className={styles.detailRow} key={key}><dt>{label}</dt><dd>{formatOfficialCatalogueTime(status[key])}</dd></div>)}
      </dl></details>
    </>}
  </Section>;
}

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
