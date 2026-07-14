const STORAGE_PREFIX = "atlas_active_context:";

let requestContext = { customerId: null, siteId: null };

function normalizedId(value) {
  if (value === null || value === undefined || value === "") return null;
  return String(value);
}

function normalizedContext(value = {}) {
  return {
    customerId: normalizedId(value.customerId ?? value.customer_id),
    siteId: normalizedId(value.siteId ?? value.site_id),
  };
}

export function getRequestContext() {
  return requestContext;
}

export function setRequestContext(value) {
  requestContext = normalizedContext(value);
  return requestContext;
}

export function clearRequestContext() {
  requestContext = { customerId: null, siteId: null };
}

export function readStoredContext(userId) {
  if (typeof window === "undefined" || !userId) return null;
  try {
    const rawValue = window.localStorage.getItem(`${STORAGE_PREFIX}${userId}`);
    if (!rawValue) return null;
    return normalizedContext(JSON.parse(rawValue));
  } catch {
    return null;
  }
}

export function storeContext(userId, value) {
  if (typeof window === "undefined" || !userId) return;
  try {
    window.localStorage.setItem(
      `${STORAGE_PREFIX}${userId}`,
      JSON.stringify(normalizedContext(value)),
    );
  } catch {
    // Context still works for this tab when browser storage is unavailable.
  }
}

export function removeStoredContext(userId) {
  if (typeof window === "undefined" || !userId) return;
  try {
    window.localStorage.removeItem(`${STORAGE_PREFIX}${userId}`);
  } catch {
    // There is no local context to rely on when storage is unavailable.
  }
}
