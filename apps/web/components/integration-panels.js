import { Button } from "./button";
import { EntityIdentity } from "./entity-identity";
import { Surface, EmptyState } from "./section";
import { StatusIndicator } from "./status-indicator";
import { connectorActions, connectorState, formatIntegrationTime, PACKAGING_LABELS, TRUST_LABELS, runtimeErrorMessage, runtimeOperations, formatOfficialCatalogueTime, officialCatalogueBlocked, officialCatalogueDiagnostic, officialCatalogueSummary } from "../lib/integrations.mjs";

export function OfficialCataloguePanel({ status, canManage, loading, refreshing, error, feedback, onRefresh, onReload, styles = {} }) {
  const pending = loading || refreshing;
  const inProgress = refreshing || status?.refresh_state === "in_progress";
  const blocked = officialCatalogueBlocked(status);
  const warning = status && (status.last_error_code || status.source_conflict || status.refresh_state === "failed");
  const fresh = !error && !warning && ["accepted", "unchanged"].includes(feedback?.result);
  return <div id="official-catalogue" className={styles.catalogueStatus}>
    <div className={styles.statusHeading}>
      <div><strong>{status?.trusted_remote_available ? `Official catalogue · Sequence ${status.sequence}` : "Official catalogue"}</strong>
        <p className={styles.meta}>{fresh ? "Freshly confirmed by this check." : officialCatalogueSummary(status)}</p>
        {status?.trusted_remote_available && <p className={styles.meta}>Last confirmed: {formatOfficialCatalogueTime(status.last_confirmed_current_at)}. Past confirmation does not establish that the source is unchanged now.</p>}
      </div>
      <div className="form-actions">
        {canManage && <Button loading={refreshing} disabled={pending || !status || blocked || Boolean(error) || ["cooldown", "in_progress"].includes(feedback?.result)} onClick={onRefresh}>Check for catalogue updates</Button>}
      </div>
    </div>
    <div aria-live="polite" aria-atomic="true" role="status">
      {loading && <p>Loading official catalogue status…</p>}
      {inProgress && <p>Checking the official catalogue… A check is in progress. Duplicate checks are unavailable.</p>}
      {feedback && feedback.result !== "failed" && <p className={styles.meta}>{feedback.message}</p>}
      {blocked && !inProgress && <p className={styles.meta}>Checks are temporarily unavailable. Next permitted check: {formatOfficialCatalogueTime(status.next_attempt_at)}. Reload status after this time.</p>}
    </div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {feedback?.result === "failed" ? <div className="error-banner" role="alert">{feedback.message}</div> : warning && <div className="error-banner" role="alert">{officialCatalogueDiagnostic(status)}</div>}
    {status && <details className={styles.technical}><summary>Publication evidence and diagnostics</summary><dl className="ops-definition">
      <dt>Schema</dt><dd>{status.schema_version}</dd>
      {status.content_digest && <><dt>Catalogue SHA-256</dt><dd className="mono">{status.content_digest}</dd></>}
      {[["Generated", "generated_at"], ["Accepted", "accepted_at"], ["Last attempt", "last_attempt_at"], ["Last download", "last_download_at"], ["Last authenticity verification", "last_authenticity_verified_at"], ["Last source confirmation", "last_confirmed_current_at"], ["Next permitted check", "next_attempt_at"]].map(([label, key]) => <div className={styles.detailRow} key={key}><dt>{label}</dt><dd>{formatOfficialCatalogueTime(status[key])}</dd></div>)}
    </dl><p className={styles.meta}>Installation independently verifies the current publication and exact package before activation. Installed Connectors remain available offline.</p>
      <Button variant="quiet" disabled={pending} onClick={onReload}>Reload official status</Button>
    </details>}
    {!status && <Button variant="quiet" disabled={pending} onClick={onReload}>Reload official status</Button>}
  </div>;
}

export function ConnectorCard({ entry, canManage, busy, onAction, onInstall, installBlocked, className = "", styles = {} }) {
  const actions = connectorActions(entry.localActionEntry || (entry.source === "official" ? null : entry), canManage);
  const mappings = entry.installed?.package_available ? entry.installed : entry.package_available ? entry : entry.installEntry;
  return <Surface className={className} data-connector-id={entry.connector_id}>
    <header className="catalogue-identity"><EntityIdentity type="connector" record={{ ...entry, id: entry.connector_id }} size={38} /><div className="catalogue-copy"><h3>{entry.name}</h3>{entry.category && <span className="secondary-text">{entry.category}</span>}</div></header>
    <p>{entry.description}</p>
    <dl className="ops-definition"><dt>Publisher</dt><dd>{entry.publisher || "Not specified"} <span className="secondary-text">· {TRUST_LABELS[entry.trust_tier] || (entry.source === "official" ? "Atlas official" : "Trust not established")}</span></dd><dt>Version</dt><dd>{entry.version || "Not released"}{entry.installed_version && <span className="secondary-text"> · {entry.installed_version === entry.version ? "Installed" : `${entry.installed_version} installed`}</span>}</dd>{entry.availableRelease && entry.availableRelease.version !== entry.version && <><dt>Official release</dt><dd>{entry.availableRelease.version} · {entry.availableRelease.installSelection ? "Available for review" : "Unavailable for remote installation"}</dd></>}{entry.licence && <><dt>Licence</dt><dd>{entry.licence}</dd></>}</dl>
    <div className={styles.cardStatus}><StatusIndicator state={connectorState(entry)} variant="badge" />{entry.installed && <StatusIndicator state={entry.verification_status} variant="badge" />}</div>
    {canManage && (actions.length > 0 || entry.installEntry || mappings) && <div className={`form-actions ${styles.cardActions || ""}`}>
      {entry.installEntry && <Button variant="primary" disabled={Boolean(busy) || installBlocked} onClick={() => onInstall(entry.installEntry)}>{entry.installed_version ? "Review package change" : "Review installation"}</Button>}
      {mappings && <Button href={`/integrations/mappings/${encodeURIComponent(entry.connector_id)}?version=${encodeURIComponent(mappings.version)}`}>Resolve mappings</Button>}
      {actions.map(action => <Button key={action.action} variant={action.action === "remove" ? "destructive" : "primary"} loading={busy === entry.connector_id} disabled={Boolean(busy)} onClick={() => onAction(entry.localActionEntry || entry, action)}>{action.label}</Button>)}
    </div>}
    {entry.message && entry.message !== entry.description && entry.verification_status !== "metadata_only" && <p className="secondary-text">{entry.message}</p>}
    {entry.verification_status === "metadata_only" && <small className="secondary-text">{entry.source === "official" ? "Accepted official metadata. Package eligibility is checked separately." : "Planned · Catalogue metadata verified. Executable bundle not released."}</small>}
    {entry.history?.length > 0 && <details className={styles.technical}><summary>Release history and bundled packages ({entry.history.length})</summary><ul className={styles.releaseHistory}>{entry.history.map(release => <li key={`${release.source}/${release.version}/${release.digest || "metadata"}`}>
      <strong>{release.version || "Not released"}</strong> · {release.source === "bootstrap" ? "Included offline package" : release.withdrawn ? "Withdrawn official release" : "Official release"}
      <p>{release.description}</p>
      {release.source === "official" && !release.installSelection && <small>Unavailable for remote installation</small>}
      {release.digest && <p className="mono">SHA-256: {release.digest}</p>}
    </li>)}</ul></details>}
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
