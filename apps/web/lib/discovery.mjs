export const DISCOVERY_SCHEDULES = Object.freeze([
  ["manual", "Manual"], ["hourly", "Hourly"], ["6_hours", "Every 6 hours"],
  ["12_hours", "Every 12 hours"], ["daily", "Daily"], ["weekly", "Weekly"],
]);

export function discoveryControls(record, canRun, canManage) {
  const available = Boolean(record?.discovery_capable && record.enabled && !record.retired_at);
  return { run: available && canRun, schedule: available && record.scheduling_capable && canRun && canManage,
    active: Boolean(record?.current_run_id), eligible: available && (record.discovery_configured ?? record.credential_configured) && record.source_compatibility !== "known_incompatible" };
}

export function discoveryDuration(run) {
  if (!run?.started_at || !run?.finished_at) return "In progress";
  const seconds = Math.max(0, Math.round((new Date(run.finished_at) - new Date(run.started_at)) / 1000));
  return Number.isFinite(seconds) ? `${seconds}s` : "Unavailable";
}

export function discoveryRunPresentation(run) {
  const provenance = run?.execution_provenance;
  const connector = provenance?.connector_id;
  const connectorName = typeof connector === "string" && /^[a-z][a-z0-9_-]{0,99}$/.test(connector)
    ? connector.replace(/[-_]/g, " ").replace(/\b[a-z]/g, letter => letter.toUpperCase()) : "Unknown connector";
  const triggers = { manual: "Manual", schedule: "Scheduled", onboarding: "Onboarding", retry: "Retry" };
  return {
    source: run?.source_name || "Unknown source",
    connector: provenance ? [connectorName, provenance.connector_version].filter(Boolean).join(" · ") : "Legacy",
    trigger: provenance ? (Object.hasOwn(triggers, provenance.trigger) ? triggers[provenance.trigger] : "Unknown trigger") : "Manual",
    coverage: run?.is_complete_snapshot === true ? "Full scope" : run?.is_complete_snapshot === false ? "Partial scope" : "Unspecified",
  };
}
