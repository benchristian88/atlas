export const INTEGRATION_TABS = Object.freeze(["configured", "catalogue", "runtime"]);
export const TRUST_LABELS = Object.freeze({ atlas_official: "Atlas official", approved_publisher: "Approved publisher" });
export const PACKAGING_LABELS = Object.freeze({ docker_compose: "Docker Compose", docker: "Docker", systemd: "Native / systemd", native: "Native / systemd", development: "Development" });

export function integrationTab(value, canViewRuntime = false) {
  return INTEGRATION_TABS.includes(value) && (value !== "runtime" || canViewRuntime) ? value : "configured";
}

export function connectorState(entry) {
  if (entry?.package_available === false && entry?.verification_status === "metadata_only" && entry?.state === "unavailable") return "bundle_not_released";
  return entry?.state || "unknown";
}

export function filterConnectors(entries = [], search = "", state = "") {
  const query = search.trim().toLowerCase();
  return entries.filter(entry => (!state || connectorState(entry) === state) && (!query || [entry.name, entry.description, entry.publisher, entry.category, entry.connector_id].filter(Boolean).join(" ").toLowerCase().includes(query)));
}

// Actions are based on backend-approved identities, never a user-supplied URL or path.
export function connectorActions(entry, canManage = false) {
  if (!canManage || !Array.isArray(entry?.supported_actions)) return [];
  const actions = [];
  for (const action of entry.supported_actions) {
    if (action === "remove" && entry.installed_version) actions.push({ action, label: "Remove package", method: "DELETE", path: `/installed-connectors/${encodeURIComponent(entry.connector_id)}` });
    if (!["install", "update", "rollback"].includes(action) || entry.verification_status !== "verified" || entry.package_available !== true) continue;
    const version = action === "rollback" ? entry.rollback_version : entry.version;
    const digest = action === "rollback" ? entry.rollback_digest : entry.digest;
    if (typeof version !== "string" || !version || typeof digest !== "string" || !/^[a-f0-9]{64}$/.test(digest)) continue;
    if (!["compatible", "installable", "installed", "update_available"].includes(entry.state)) continue;
    actions.push({ action, label: { install: "Install Connector", update: "Update package", rollback: "Roll back package" }[action], method: "POST", path: `/integration-catalogue/${encodeURIComponent(entry.connector_id)}/${action === "install" ? "install" : "activate"}`, body: { version, digest } });
  }
  return actions;
}

export function formatIntegrationTime(value) {
  if (!value) return "Not checked";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not checked" : date.toLocaleString();
}

export function runtimeErrorMessage(value) {
  return { runtime_unavailable: "Atlas could not reach the local runtime. Check the runtime service and refresh health.", runtime_baseline_mismatch: "The runtime does not match its approved baseline. Update the runtime through your Atlas installation." }[value] || (value ? "Runtime health could not be verified. Check the runtime service and refresh health." : "");
}

export function runtimeOperations(capabilities) {
  const values = Array.isArray(capabilities) ? capabilities : capabilities?.operations;
  return Array.isArray(values) ? values.filter(value => typeof value === "string") : [];
}

// Presentation only. Backend acceptance and package eligibility remain separate.
const record = value => value !== null && typeof value === "object" && !Array.isArray(value);
const displayText = (value, fallback, limit = 1000) => typeof value === "string" && value.trim() ? value.trim().slice(0, limit) : fallback;
const timestamp = value => typeof value === "string" && value.length <= 64 && !Number.isNaN(Date.parse(value)) ? value : null;

export function officialConnectorMetadata(entry) {
  if (!record(entry)) return null;
  const manifest = record(entry.manifest) ? entry.manifest : {};
  const display = record(manifest.display) ? manifest.display : {};
  return {
    connector_id: displayText(entry.connector_id, displayText(manifest.id, "Unknown connector", 100), 100),
    version: displayText(entry.version, displayText(manifest.version, "Not specified", 64), 64),
    name: displayText(display.name, "Unnamed connector", 255),
    description: displayText(display.description, "No description supplied."),
    category: displayText(display.category, "Not specified", 100),
    publisher: displayText(manifest.publisher?.name, "Not specified", 255),
    licence: displayText(manifest.licensing?.licence, "Not specified", 255),
    withdrawn: entry.status === "withdrawn",
    packageAvailable: entry.package_available === true,
  };
}

export function readOfficialCatalogueStatus(value, { requireEntries = true } = {}) {
  if (!record(value) || typeof value.trusted_remote_available !== "boolean"
      || !["idle", "in_progress", "failed"].includes(value.refresh_state)
      || (requireEntries && !Array.isArray(value.entries))
      || (Array.isArray(value.entries) && value.entries.length > 200)
      || (value.trusted_remote_available && (!Number.isSafeInteger(value.sequence) || value.sequence < 1
        || typeof value.content_digest !== "string" || !/^[a-f0-9]{64}$/.test(value.content_digest)))) {
    throw new Error("Unexpected official catalogue status");
  }
  const status = {
    trusted_remote_available: value.trusted_remote_available,
    sequence: value.trusted_remote_available ? value.sequence : null,
    content_digest: value.trusted_remote_available ? value.content_digest : null,
    schema_version: displayText(value.schema_version, "Not recorded", 32),
    refresh_state: value.refresh_state,
    // Error codes are used only to select bounded, release-owned messages.
    last_error_code: typeof value.last_error_code === "string" ? value.last_error_code.slice(0, 100) : null,
    source_conflict: Boolean(value.source_conflict),
    entries: value.trusted_remote_available && Array.isArray(value.entries) ? value.entries.map(officialConnectorMetadata).filter(Boolean) : [],
  };
  for (const key of ["generated_at", "accepted_at", "last_attempt_at", "last_download_at", "last_authenticity_verified_at", "last_confirmed_current_at", "next_attempt_at"]) status[key] = timestamp(value[key]);
  return status;
}

export function formatOfficialCatalogueTime(value) {
  return timestamp(value) ? new Date(value).toLocaleString() : "Not recorded";
}

export function officialCatalogueBlocked(status, now = Date.now()) {
  return status?.refresh_state === "in_progress" || Boolean(status?.next_attempt_at && Date.parse(status.next_attempt_at) > now);
}

export function officialCatalogueSummary(status) {
  if (!status) return "Official catalogue status is unavailable.";
  if (status.trusted_remote_available) return "Trusted catalogue previously accepted.";
  if (!status.last_attempt_at && !status.last_error_code && !status.source_conflict && status.refresh_state === "idle") return "The official catalogue has not yet been checked.";
  return "No trusted official catalogue has been accepted.";
}

export function officialCatalogueDiagnostic(status) {
  if (status?.source_conflict) return "The official source conflicts with retained catalogue history. An administrator should investigate; previously accepted metadata is retained.";
  if (status?.last_error_code === "source_rate_limited") return "The catalogue provider has temporarily limited requests. Wait until the next permitted check.";
  if (["catalogue_state_unavailable", "catalogue_persistence_failed"].includes(status?.last_error_code)) return "Atlas could not update official catalogue status. Reload status before trying again.";
  return status?.trusted_remote_available
    ? "The official catalogue could not be verified. Previously accepted metadata is retained; its last confirmation has not been renewed."
    : "The official catalogue could not be verified. No new catalogue was accepted.";
}

export function officialCatalogueRequestError(error) {
  if (error?.status === 401) return "Your session has expired. Sign in again to view official catalogue status.";
  if (error?.status === 403) return "You do not have permission to access official catalogue status or checks.";
  return "Atlas could not complete the official catalogue request. This does not establish a verification failure. Reload official status before checking again. The local catalogue remains available.";
}
