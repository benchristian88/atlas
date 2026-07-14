"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getCurrentUser } from "../lib/auth";
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
  const [authState, setAuthState] = useState({
    status: "checking",
    user: null,
  });

  useEffect(() => {
    if (publicRoute) {
      setAuthState({ status: "public", user: null });
      return;
    }

    let active = true;
    setAuthState({ status: "checking", user: null });
    async function protectRoute() {
      try {
        const user = await getCurrentUser();
        if (!active) return;
        setAuthState({ status: "authenticated", user });
      } catch {
        if (!active) return;
        router.replace("/login");
      }
    }
    protectRoute();
    return () => { active = false; };
  }, [publicRoute, router]);

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
  if (authState.status !== "authenticated" || passwordChangeRequired || redirectHome) {
    return (
      <main className="route-loading" aria-live="polite">
        <div className="status-banner" role="status">Checking your Atlas session…</div>
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
