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
