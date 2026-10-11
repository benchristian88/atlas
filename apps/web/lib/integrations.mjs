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
