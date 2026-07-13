"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { clearToken, getCurrentUser, getToken } from "../lib/auth";
import { AppShell } from "./app-shell";
import { AuthContext } from "./auth-context";

function isPublicRoute(pathname) {
  return pathname === "/login"
    || pathname === "/debug/auth"
    || pathname.startsWith("/debug/auth/");
}

export function RootShell({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const publicRoute = isPublicRoute(pathname);
  const [authState, setAuthState] = useState({
    status: "checking",
    user: null,
    pathname: null,
  });

  useEffect(() => {
    if (publicRoute) {
      setAuthState({ status: "public", user: null, pathname });
      return;
    }

    let active = true;
    setAuthState({ status: "checking", user: null, pathname });
    async function protectRoute() {
      try {
        if (!getToken()) {
          router.replace("/login");
          return;
        }
        const user = await getCurrentUser();
        if (!active) return;
        if (pathname === "/") {
          router.replace("/dashboard");
          return;
        }
        setAuthState({ status: "authenticated", user, pathname });
      } catch {
        if (!active) return;
        try {
          clearToken();
        } catch {
          // The login screen will display storage errors on its next interaction.
        }
        router.replace("/login");
      }
    }
    protectRoute();
    return () => { active = false; };
  }, [pathname, publicRoute, router]);

  if (publicRoute) return children;
  if (
    authState.status !== "authenticated"
    || authState.pathname !== pathname
  ) {
    return (
      <main className="route-loading" aria-live="polite">
        <div className="status-banner" role="status">Checking your Atlas session…</div>
      </main>
    );
  }
  return (
    <AuthContext.Provider value={{ user: authState.user }}>
      <AppShell>{children}</AppShell>
    </AuthContext.Provider>
  );
}
