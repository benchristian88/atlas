import { apiRequest } from "./api";
import { ApiError } from "./api-error";
import { clearToken, getToken, setToken } from "./auth-token";

const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");

function developmentInfo(message, value) {
  if (process.env.NODE_ENV === "development") {
    if (value === undefined) console.info(message);
    else console.info(message, value);
  }
}

function validUser(value) {
  return Boolean(
    value
    && typeof value.email === "string"
    && typeof value.display_name === "string",
  );
}

export { clearToken, getToken, setToken };

export async function login(email, password) {
  if (!API_URL) {
    throw new ApiError(
      "Could not reach Atlas API. NEXT_PUBLIC_API_URL is not configured.",
      { kind: "configuration" },
    );
  }

  const requestUrl = `${API_URL}/auth/login`;
  developmentInfo("auth login request URL", requestUrl);

  let response;
  try {
    response = await fetch(requestUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  } catch {
    throw new ApiError("Could not reach Atlas API", { kind: "network" });
  }

  developmentInfo("auth login response status", response.status);

  let result;
  try {
    result = await response.json();
  } catch {
    throw new ApiError("Atlas API returned an unexpected login response.", {
      status: response.status,
      kind: "response",
    });
  }

  if (!response.ok) {
    const message = typeof result?.detail === "string"
      ? result.detail
      : `Atlas login failed with status ${response.status}.`;
    throw new ApiError(message, { status: response.status });
  }

  if (
    typeof result?.access_token !== "string"
    || !result.access_token.trim()
    || result.token_type?.toLowerCase() !== "bearer"
    || !validUser(result.user)
  ) {
    throw new ApiError(
      "Atlas API returned an unexpected login response without a valid bearer token.",
      { kind: "response" },
    );
  }
  setToken(result.access_token);
  developmentInfo("token stored");
  return result.user;
}

export async function getCurrentUser() {
  if (!getToken()) {
    throw new ApiError("No Atlas access token is available.", {
      status: 401,
      kind: "authentication",
    });
  }
  const user = await apiRequest("/auth/me");
  if (!validUser(user)) {
    throw new ApiError("Atlas API returned an unexpected user response.", {
      kind: "response",
    });
  }
  return user;
}

export function logout() {
  clearToken();
}
