import { ApiError } from "./api-error";
import { clearToken, getToken } from "./auth-token";

const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");

function configuredApiUrl() {
  if (!API_URL) {
    throw new ApiError(
      "Atlas is missing NEXT_PUBLIC_API_URL. Configure it and rebuild or restart the web service.",
      { kind: "configuration" },
    );
  }
  return API_URL;
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
  const token = getToken();
  let response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...options,
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
    if (response.status === 401 && typeof window !== "undefined") {
      try {
        clearToken();
      } finally {
        window.location.replace("/login");
      }
    }
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
