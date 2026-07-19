export const RECONCILIATION_QUEUES = [
  { key: "all-open", label: "All Open", href: "/reconciliation", status: "open" },
  { key: "newly-discovered", label: "Newly discovered", href: "/reconciliation?queue=newly-discovered", status: "open", category: "newly_discovered" },
  { key: "changed", label: "Changed", href: "/reconciliation?queue=changed", status: "open", category: "changed" },
  { key: "no-longer-observed", label: "No longer observed", href: "/reconciliation?queue=no-longer-observed", status: "open", category: "no_longer_observed" },
  { key: "contradictions", label: "Contradictions", href: "/reconciliation?queue=contradictions", status: "open", category: "contradiction" },
  { key: "possible-duplicates", label: "Possible duplicates", href: "/reconciliation?queue=possible-duplicates", status: "open", category: "possible_duplicate" },
  { key: "deferred", label: "Deferred", href: "/reconciliation?queue=deferred", status: "deferred" },
  { key: "resolved", label: "Resolved", href: "/reconciliation?queue=resolved", status: "resolved" },
];

export function reconciliationQueueFromValue(value) {
  return RECONCILIATION_QUEUES.find((queue) => queue.key === value) || RECONCILIATION_QUEUES[0];
}
