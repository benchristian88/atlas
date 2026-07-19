import { ApiError } from "./api-error";
import { apiUrl, normalizeApiBase } from "./api-url.mjs";
import { getRequestContext } from "./context-store";

const API_BASE = normalizeApiBase(process.env.NEXT_PUBLIC_API_URL);

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
  const requestUrl = apiUrl(path, API_BASE);
  const {
    omitContext = false,
    redirectOnUnauthorized = true,
    ...fetchOptions
  } = options;
  const headers = new Headers(fetchOptions.headers || {});
  const bodyIsFormData = typeof FormData !== "undefined" && fetchOptions.body instanceof FormData;
  if (fetchOptions.body && !bodyIsFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!omitContext) {
    const { customerId, siteId } = getRequestContext();
    if (customerId) headers.set("X-Atlas-Customer-ID", customerId);
    if (siteId) headers.set("X-Atlas-Site-ID", siteId);
  }

  let response;
  try {
    response = await fetch(requestUrl, {
      ...fetchOptions,
      credentials: "include",
      headers,
    });
  } catch {
    throw new ApiError(
      `Could not reach the Atlas API at ${API_BASE}. Check API routing and availability.`,
      { kind: "network" },
    );
  }

  const body = await responseBody(response);
  if (!response.ok) {
    if (
      response.status === 401
      && redirectOnUnauthorized
      && typeof window !== "undefined"
      && window.location.pathname !== "/login"
    ) {
      window.location.replace("/login");
    }
    if (
      response.status === 403
      && typeof body?.detail === "string"
      && body.detail.startsWith("The selected ")
      && typeof window !== "undefined"
    ) {
      window.dispatchEvent(new Event("atlas:context-invalid"));
    }
    let detail = `Atlas API request failed with status ${response.status}.`;
    if (typeof body?.detail === "string") detail = body.detail;
    if (Array.isArray(body?.detail)) {
      detail = body.detail.map((item) => item.msg).filter(Boolean).join(", ") || detail;
    }
    throw new ApiError(detail, { status: response.status, details: body });
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
