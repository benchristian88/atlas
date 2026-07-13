const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
export const TOKEN_KEY = "atlas_access_token";

export class ApiError extends Error {
  constructor(message, { status = null, kind = "api" } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.kind = kind;
  }
}

function configuredApiUrl() {
  if (!API_URL) {
    throw new ApiError(
      "Atlas is missing NEXT_PUBLIC_API_URL. Configure it and rebuild or restart the web service.",
      { kind: "configuration" },
    );
  }
  return API_URL;
}

export function getAccessToken() {
  if (typeof window === "undefined") return null;
  try {
    const token = window.localStorage.getItem(TOKEN_KEY);
    return token && token.trim() ? token : null;
  } catch {
    throw new ApiError(
      "Atlas cannot access browser storage. Allow local storage for this site and try again.",
      { kind: "storage" },
    );
  }
}

export function setAccessToken(token) {
  if (typeof token !== "string" || !token.trim()) {
    throw new ApiError("Atlas API returned an invalid access token.", { kind: "response" });
  }
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    throw new ApiError(
      "Atlas could not save your session in browser storage. Allow local storage and try again.",
      { kind: "storage" },
    );
  }
}

export function clearAccessToken() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    throw new ApiError(
      "Atlas could not clear your saved session. Allow local storage and try again.",
      { kind: "storage" },
    );
  }
}

async function responseBody(response) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) return null;
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export async function apiRequest(path, options = {}) {
  const baseUrl = configuredApiUrl();
  const token = getAccessToken();
  let response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...options,
      credentials: "include",
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new ApiError(
      `Could not reach the Atlas API at ${baseUrl}. Check NEXT_PUBLIC_API_URL, CORS_ORIGINS, and API availability.`,
      { kind: "network" },
    );
  }

  const body = await responseBody(response);
  if (!response.ok) {
    let detail = `Atlas API request failed with status ${response.status}.`;
    if (typeof body?.detail === "string") detail = body.detail;
    if (Array.isArray(body?.detail)) {
      detail = body.detail.map((item) => item.msg).filter(Boolean).join(", ") || detail;
    }
    throw new ApiError(detail, { status: response.status });
  }

  if (response.status === 204) return null;
  if (body === null) {
    throw new ApiError(
      "Atlas API returned an unexpected response instead of JSON.",
      { status: response.status, kind: "response" },
    );
  }
  return body;
}
