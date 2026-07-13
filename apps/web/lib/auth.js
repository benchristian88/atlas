import { apiRequest } from "./api";
import { ApiError } from "./api-error";
import { clearToken, getToken, setToken } from "./auth-token";

function validUser(value) {
  return Boolean(
    value
    && typeof value.email === "string"
    && typeof value.display_name === "string",
  );
}

export { clearToken, getToken, setToken };

export async function login(email, password) {
  const result = await apiRequest("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
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
