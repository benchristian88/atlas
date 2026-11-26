import { apiRequest } from "./api";

export function requestConnectorAction({ path, method, body }, signal) {
  return apiRequest(path, {
    method, omitContext: true, signal,
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
}
