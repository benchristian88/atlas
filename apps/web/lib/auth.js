import { apiRequest } from "./api";
import { ApiError } from "./api-error";
import { discardLegacyAuthToken } from "./auth-token";
import { clearRequestContext } from "./context-store";
import { loginResult } from "./login-result.mjs";

function validUser(value) {
  return Boolean(
    value
    && typeof value.email === "string"
    && typeof value.display_name === "string",
  );
}

export async function login(email, password) {
  discardLegacyAuthToken();
  clearRequestContext();
  const result = await apiRequest("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
    omitContext: true,
    redirectOnUnauthorized: false,
  });
  try { return loginResult(result); }
  catch (error) { throw new ApiError(error.message, { kind: "response" }); }
}

export async function verifyLoginMfa(code, method) {
  const result = await apiRequest("/auth/mfa/verify", {
    method: "POST", body: JSON.stringify({ code, method }), omitContext: true, redirectOnUnauthorized: false,
  });
  if (!validUser(result?.user)) throw new ApiError("Atlas returned an unexpected verification response.", { kind: "response" });
  return result.user;
}

export async function cancelLoginMfa() {
  await apiRequest("/auth/mfa/cancel", { method: "POST", omitContext: true, redirectOnUnauthorized: false });
}

export async function getCurrentUser() {
  discardLegacyAuthToken();
  const user = await apiRequest("/auth/me", {
    omitContext: true,
    redirectOnUnauthorized: false,
  });
  if (!validUser(user)) {
    throw new ApiError("Atlas API returned an unexpected user response.", {
      kind: "response",
    });
  }
  return user;
}

export async function logout() {
  try {
    await apiRequest("/auth/logout", {
      method: "POST",
      omitContext: true,
      redirectOnUnauthorized: false,
    });
  } catch (requestError) {
    // An already-expired cookie is also a successfully ended local session.
    if (requestError.status !== 401) throw requestError;
  } finally {
    clearRequestContext();
    discardLegacyAuthToken();
  }
}
