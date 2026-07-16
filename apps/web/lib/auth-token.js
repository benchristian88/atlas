// Authentication now uses an HttpOnly cookie. This helper only removes tokens
// left behind by pre-cookie Atlas builds; it never reads or writes a live token.
export function discardLegacyAuthToken() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem("atlas_access_token");
  } catch {
    // A blocked localStorage API does not prevent cookie authentication.
  }
}
