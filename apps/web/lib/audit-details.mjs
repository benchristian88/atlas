const sensitive = /password|secret|token|cookie|authorization|hash|credential/i;

function readableName(value) {
  return typeof value === "string" && value.trim() !== "[redacted]" ? value.trim() : "";
}

export function needsIntegrationName(event) {
  return event.target_type === "integration" && Boolean(event.target_id && event.customer_id && event.site_id)
    && !readableName(event.metadata?.name);
}

function auditReference(id, capturedName, currentName) {
  const current = readableName(currentName);
  return { id, name: capturedName || current, isCurrent: !capturedName && Boolean(current) };
}

export function auditReferences(event, { customers, sites, integrations }) {
  const { target_type: type, target_id: targetId, customer_id: customerId, site_id: siteId } = event;
  // Audit writers that record a top-level name use it for the event's target.
  const capturedName = readableName(event.metadata?.name);
  const customerById = id => customers.find(customer => customer.id === id);
  const siteById = id => sites.find(site => site.id === id && (!customerId || site.customer_id === customerId));
  let currentTarget;
  if (targetId && !capturedName) {
    if (type === "customer") currentTarget = customerById(targetId);
    if (type === "site") currentTarget = siteById(targetId);
    if (needsIntegrationName(event)) {
      currentTarget = integrations.find(integration => integration.id === targetId
        && integration.customer_id === customerId && integration.site_id === siteId);
    }
  }
  return {
    object: { ...auditReference(targetId, capturedName, currentTarget?.name), type },
    customer: auditReference(customerId, type === "customer" && targetId === customerId ? capturedName : "", customerById(customerId)?.name),
    site: auditReference(siteId, type === "site" && targetId === siteId ? capturedName : "", siteById(siteId)?.name),
  };
}

export function safeAuditValue(value) {
  if (Array.isArray(value)) return value.map(safeAuditValue);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, sensitive.test(key) ? "[redacted]" : safeAuditValue(item)]));
  return value;
}
export function auditDetails(metadata) {
  const changes = [], facts = [];
  function difference(field, before, after, hasBefore, hasAfter) {
    const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
    if ((object(before) || !hasBefore) && (object(after) || !hasAfter)) {
      const keys = [...new Set([...Object.keys(before || {}), ...Object.keys(after || {})])];
      if (keys.length) {
        for (const key of keys) difference(field ? `${field} / ${key}` : key, before?.[key], after?.[key], hasBefore && Object.hasOwn(before, key), hasAfter && Object.hasOwn(after, key));
        return;
      }
    }
    if (hasBefore && hasAfter && JSON.stringify(before) === JSON.stringify(after)) return;
    changes.push({ field: field || "Value", before, after, hasBefore, hasAfter });
  }
  function walk(value, path) {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const pair = Object.hasOwn(value, "from") || Object.hasOwn(value, "to") ? ["from", "to"] : Object.hasOwn(value, "before") || Object.hasOwn(value, "after") ? ["before", "after"] : null;
      if (pair) {
        difference(path, value[pair[0]], value[pair[1]], Object.hasOwn(value, pair[0]), Object.hasOwn(value, pair[1]));
        return;
      }
      for (const [key, item] of Object.entries(value)) walk(item, path ? `${path} / ${key}` : key);
    } else facts.push({ field: path, value });
  }
  walk(safeAuditValue(metadata || {}), "");
  return { changes, facts };
}
export function auditValue(value) {
  if (value === null) return "null";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}
