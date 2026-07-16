"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getCurrentUser } from "../lib/auth";
import {
  checkSession,
  checkingSessionState,
  publicSessionState,
} from "../lib/session-state.mjs";
import { AppShell } from "./app-shell";
import {
  authenticatedHome,
  AuthContext,
  userHasAnyPermission,
  userHasGlobalPermission,
  userHasPermission,
  userHasPermissionForObject,
  userHasPermissionInContext,
} from "./auth-context";
import { WorkspaceContextProvider } from "./workspace-context";

function isPublicRoute(pathname) {
  return pathname === "/login";
}

export function RootShell({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const publicRoute = isPublicRoute(pathname);
  const [authState, setAuthState] = useState(checkingSessionState);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    if (publicRoute) {
      setAuthState(publicSessionState);
      return;
    }

    let active = true;
    setAuthState(checkingSessionState);
    async function protectRoute() {
      const nextState = await checkSession(getCurrentUser, () => active);
      if (!nextState) return;
      setAuthState(nextState);
      if (nextState.status === "unauthenticated") {
        router.replace("/login");
      }
    }
    protectRoute();
    return () => { active = false; };
  }, [publicRoute, retryKey, router]);

  const updateUser = useCallback((nextUser) => {
    setAuthState((current) => ({
      ...current,
      user: typeof nextUser === "function" ? nextUser(current.user) : nextUser,
    }));
  }, []);

  const authValue = useMemo(() => ({
    user: authState.user,
    updateUser,
    permissions: authState.user?.permissions || [],
    hasPermission: (permission) => userHasPermission(authState.user, permission),
    hasAnyPermission: (permissions) => userHasAnyPermission(authState.user, permissions),
    hasGlobalPermission: (permission) => userHasGlobalPermission(authState.user, permission),
    hasPermissionInContext: (permission, customerId, siteId) => (
      userHasPermissionInContext(authState.user, permission, customerId, siteId)
    ),
    hasPermissionForObject: (permission, customerId, siteId) => (
      userHasPermissionForObject(authState.user, permission, customerId, siteId)
    ),
  }), [authState.user, updateUser]);

  const passwordChangeRequired = Boolean(
    authState.status === "authenticated"
    && authState.user?.force_password_change
    && pathname !== "/profile",
  );
  const redirectHome = authState.status === "authenticated" && pathname === "/";

  useEffect(() => {
    if (passwordChangeRequired) router.replace("/profile?password=required");
    else if (redirectHome) router.replace(authenticatedHome(authState.user));
  }, [authState.user, passwordChangeRequired, redirectHome, router]);

  if (publicRoute) return children;
  if (authState.status === "error") {
    return (
      <main className="route-loading">
        <section className="error-panel session-error" role="alert">
          <h1>Atlas could not verify your session</h1>
          <p>The Atlas API could not complete the session check. Check API routing and availability, then try again.</p>
          <p className="session-error-detail">{authState.error}</p>
          <div className="form-actions">
            <button className="button button-primary" onClick={() => setRetryKey((value) => value + 1)} type="button">Try again</button>
            <button className="button button-secondary" onClick={() => router.replace("/login")} type="button">Go to sign in</button>
          </div>
        </section>
      </main>
    );
  }
  if (authState.status === "unauthenticated") {
    return (
      <main className="route-loading" aria-live="polite">
        <div className="status-banner" role="status">Opening sign in…</div>
      </main>
    );
  }
  if (authState.status !== "authenticated" || passwordChangeRequired || redirectHome) {
    return (
      <main className="route-loading" aria-live="polite">
        <div className="status-banner" role="status">
          {authState.status === "checking" ? "Checking your Atlas session…" : "Opening Atlas…"}
        </div>
      </main>
    );
  }
  return (
    <AuthContext.Provider value={authValue}>
      <WorkspaceContextProvider user={authState.user}>
        <AppShell>{children}</AppShell>
      </WorkspaceContextProvider>
    </AuthContext.Provider>
  );
}
