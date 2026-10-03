import { resolveStatus } from "../lib/status.mjs";

export function StatusIndicator({ state, variant = "operational", dotOnly = false }) {
  const status = resolveStatus(state);
  const classes = `status-${status.value.replaceAll("_", "-")}`;
  if (variant === "lifecycle") return <span className="lifecycle-status">{status.label}</span>;
  if (variant === "badge") return <span className={`status-badge ${classes}`} data-status-tone={status.tone}>{status.label}</span>;
  const dot = <span className={`recorded-status ${classes}`} data-status-tone={status.tone} aria-hidden="true" />;
  if (dotOnly) return <span className="status-dot-only" role="img" aria-label={`Recorded status: ${status.value.replaceAll("_", " ")}`} title={`Recorded status: ${status.value.replaceAll("_", " ")}`}>{dot}</span>;
  return <span className="status-indicator">{dot}<span>{status.label}</span></span>;
}
