const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
const TOKEN_KEY = "atlas_access_token";

export function getAccessToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken() {
  if (typeof window !== "undefined") window.localStorage.removeItem(TOKEN_KEY);
}

export async function apiRequest(path, options = {}) {
  if (!API_URL) throw new Error("NEXT_PUBLIC_API_URL is not configured.");
  const token = getAccessToken();
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
      if (Array.isArray(body.detail)) detail = body.detail.map((item) => item.msg).join(", ");
    } catch {
      // Keep the status-based fallback for non-JSON errors.
    }
    if (response.status === 401) {
      detail = "Sign in to Atlas before managing records.";
    }
    throw new Error(detail);
  }

  if (response.status === 204) return null;
  return response.json();
}
