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

export function reconciliationPagePath(queue, cursor = null) {
  const params = new URLSearchParams({ status: queue.status, limit: "50" });
  if (queue.category) params.set("category", queue.category);
  if (cursor) params.set("cursor", cursor);
  return `/reconciliation-items/page?${params}`;
}

export function reconciliationEntityPagePath(queue, { cursor = null, search = "", section = "" } = {}) {
  const params = new URLSearchParams({ status: queue.status, limit: "50" });
  if (queue.category) params.set("category", queue.category);
  if (cursor) params.set("cursor", cursor);
  if (search) params.set("search", search);
  if (section) params.set("section", section);
  return `/reconciliation-entities?${params}`;
}

// Review navigation survives refresh and browser Back. The return destination
// contains only this route's query, never an arbitrary external URL.
export function reconciliationReviewHref(params, entityId, returnEntityId = null) {
  const next = new URLSearchParams(params);
  if (returnEntityId) {
    const back = new URLSearchParams(params);
    back.set("entity", returnEntityId);
    back.delete("return");
    next.set("return", back.toString());
  }
  next.set("entity", entityId);
  return `/reconciliation?${next}`;
}

export function reconciliationReturnHref(value) {
  if (!value) return null;
  const params = new URLSearchParams(value);
  for (const key of [...params.keys()]) {
    if (!["queue", "search", "section", "cursor", "page", "entity"].includes(key)) params.delete(key);
  }
  return `/reconciliation?${params}`;
}

export function reconciliationGroups(items, relatedNewEntities = []) {
  const entities = new Map([...relatedNewEntities, ...items].map(item => [item.id, item]));
  const groups = new Map();
  for (const item of items) {
    const parent = entities.get(item.initial_entity_item_id);
    // Only the API identifies initial facts. Keep mismatched context independent.
    const initial = parent && parent.category === "newly_discovered" && item.category === "changed"
      && parent.entity_type === "asset" && item.entity_type === "asset"
      && parent.customer_id === item.customer_id && parent.site_id === item.site_id
      && parent.data_source_id && parent.data_source_id === item.data_source_id
      && parent.discovery_run_id && parent.discovery_run_id === item.discovery_run_id
      && parent.candidate_external_id && parent.candidate_external_id === item.candidate_external_id;
    const entity = initial ? parent : item;
    if (!groups.has(entity.id)) groups.set(entity.id, { entity, facts: [] });
    if (initial) groups.get(entity.id).facts.push(item);
  }
  return [...groups.values()];
}
