export const checkingSessionState = Object.freeze({
  status: "checking",
  user: null,
  error: null,
});

export const publicSessionState = Object.freeze({
  status: "public",
  user: null,
  error: null,
});

function safeSessionError(error) {
  if (error?.kind === "network") {
    return "Could not reach the Atlas API. Check API routing and availability.";
  }
  if (error?.status === 404) {
    return "The Atlas session endpoint was not found. Check that /api routes to the Atlas API.";
  }
  if (error?.status >= 500) {
    return "The Atlas API could not complete the session check. Try again when the service is available.";
  }
  if (error?.kind === "response") {
    return "The Atlas API returned an unexpected session response.";
  }
  if (
    error
    && (typeof error.status === "number" || typeof error.kind === "string")
    && typeof error.message === "string"
    && error.message
  ) {
    return error.message;
  }
  return "Atlas could not verify your session.";
}

export async function checkSession(getCurrentUser, isActive = () => true) {
  try {
    const user = await getCurrentUser();
    if (!isActive()) return null;
    return { status: "authenticated", user, error: null };
  } catch (error) {
    if (!isActive()) return null;
    if (error?.status === 401) {
      return { status: "unauthenticated", user: null, error: null };
    }
    return { status: "error", user: null, error: safeSessionError(error) };
  }
}
