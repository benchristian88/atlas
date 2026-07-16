export function normalizeApiBase(value) {
  const raw = typeof value === "string" ? value.trim() : "";
  const base = raw || "/api";
  if (/^https?:\/\//i.test(base)) {
    const url = new URL(base);
    url.pathname = `/${url.pathname.split("/").filter(Boolean).join("/")}`;
    if (url.pathname === "/") url.pathname = "";
    return url.toString().replace(/\/$/, "");
  }
  return `/${base.split("/").filter(Boolean).join("/")}`;
}

export function apiUrl(endpoint, base = normalizeApiBase()) {
  const normalizedBase = normalizeApiBase(base);
  const normalizedEndpoint = String(endpoint || "").replace(/^\/+/, "");
  const prefix = normalizedBase === "/" ? "" : normalizedBase;
  return normalizedEndpoint ? `${prefix}/${normalizedEndpoint}` : normalizedBase;
}
