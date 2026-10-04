export const INSTALLATION_LABELS = Object.freeze({
  docker_compose: "Docker Compose",
  systemd: "Native / systemd",
  development: "Development",
});

export function updateMessage(info) {
  switch (info?.status) {
    case "up_to_date": return "Atlas is up to date.";
    case "update_available": return `Atlas ${info.latest_version} is available.`;
    case "ahead_of_release": return "This installation is ahead of the latest supported release.";
    default: return "Update information is currently unavailable.";
  }
}

export function upgradeGuidance(method) {
  switch (method) {
    case "docker_compose": return "Create and download an encrypted backup, verify the Docker Compose release package, then use the upgrade helper with your existing protected configuration. Confirm health and installed version afterward.";
    case "systemd": return "Create and download an encrypted backup, verify the native release package, then run the native upgrade helper on the host. Preserve protected configuration and application state; confirm health and installed version afterward.";
    default: return "Development installation — update through the development Git workflow.";
  }
}
