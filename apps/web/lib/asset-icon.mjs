import { apiUrl, normalizeApiBase } from "./api-url.mjs";

export const GENERIC_ICON = `data:image/svg+xml,${encodeURIComponent(`
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
    <rect width="48" height="48" rx="10" fill="#def3ee"/>
    <rect x="11" y="10" width="26" height="9" rx="2" fill="#1a7f72"/>
    <rect x="11" y="22" width="26" height="9" rx="2" fill="#1a7f72"/>
    <rect x="11" y="34" width="26" height="4" rx="2" fill="#1a7f72"/>
    <circle cx="16" cy="14.5" r="1.5" fill="#fff"/>
    <circle cx="16" cy="26.5" r="1.5" fill="#fff"/>
  </svg>
`)}`;

function defaultIcon(value) {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

export function assetIconSources(asset, assetType, apiBase) {
  // Never use icon_url (the external source) or an arbitrary resolved URL.
  const local = asset?.cached_icon_url;
  const validLocal = typeof local === "string" && /^\/api\/assets\/[0-9a-f-]{36}\/icon(?:\?v=[0-9a-f]{64})?$/.test(local);
  return [...new Set([
    validLocal ? apiUrl(local.slice(5), normalizeApiBase(apiBase)) : null,
    defaultIcon(assetType?.default_icon_url || asset?.default_icon_url),
    GENERIC_ICON,
  ].filter(Boolean))];
}
