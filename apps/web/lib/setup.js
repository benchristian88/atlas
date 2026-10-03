import { apiRequest } from "./api";
import { ApiError } from "./api-error";

export async function getSetupStatus() {
  const result = await apiRequest("/setup/status", { omitContext: true, redirectOnUnauthorized: false, cache: "no-store" });
  if (!["INITIALISED", "UNINITIALISED"].includes(result?.state)) {
    throw new ApiError("Atlas API returned an unexpected initialization response.", { kind: "response" });
  }
  return result;
}

export function setupRequest(path, payload) {
  return apiRequest(`/setup/${path}`, { method: "POST", body: JSON.stringify(payload), omitContext: true, redirectOnUnauthorized: false });
}
