import { StatusIndicator } from "./status-indicator";

// Compatibility adapter for workflow/severity consumers.
export function StatusBadge({ status }) {
  return <StatusIndicator state={status} variant="badge" />;
}
