import { ApiError } from "./api-error";

export const TOKEN_KEY = "atlas_access_token";

export function getToken() {
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

export function setToken(token) {
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

export function clearToken() {
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
