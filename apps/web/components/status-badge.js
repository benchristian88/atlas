export function StatusBadge({ status }) {
  const normalized = status.toLowerCase().replaceAll(" ", "-");
  return <span className={`status-badge status-${normalized}`}>{status}</span>;
}
