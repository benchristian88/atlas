"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AccountMenu } from "./account-menu";
import { authenticatedHome, useAuth } from "./auth-context";
import { AtlasBrand } from "./atlas-brand.mjs";
import { useBuildInfo } from "./build-info-context";
import { ContextSelector } from "./context-selector";
import { Navigation } from "./navigation";
import { useWorkspaceContext } from "./workspace-context";
import { logout } from "../lib/auth";
import { accentThemeStyle } from "../lib/accent-theme.mjs";

export function AppShell({ children }) {
  const router = useRouter();
  const { user, resolvedThemeMode } = useAuth();
  const version = useBuildInfo()?.version;
  const workspace = useWorkspaceContext();
  const [logoutError, setLogoutError] = useState("");
  const [signingOut, setSigningOut] = useState(false);
  const sidebarBrandVariant = resolvedThemeMode;

  async function signOut() {
    setLogoutError("");
    setSigningOut(true);
    try {
      await logout();
      router.replace("/login");
      router.refresh();
    } catch (requestError) {
      setLogoutError(requestError.message || "Atlas could not end your session.");
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <div className="app-shell" style={accentThemeStyle(user.accent_colour, resolvedThemeMode)}>
      <aside className="sidebar">
        <AtlasBrand href={authenticatedHome(user)} variant={sidebarBrandVariant} />
        <Navigation />
        {version && <div className="sidebar-footer">Atlas {version}</div>}
      </aside>
      <div className="content">
        <header className="topbar">
          <ContextSelector />
          <AccountMenu onLogout={signOut} signingOut={signingOut} user={user} />
        </header>
        {workspace.error && (
          <div className="shell-error error-banner" role="alert">
            <span>{workspace.error}</span>
            <button className="text-button" onClick={workspace.reload} type="button">Try again</button>
          </div>
        )}
        {logoutError && <div className="shell-error error-banner" role="alert">{logoutError}</div>}
        <main className="page-content" key={workspace.reloadKey}>{children}</main>
      </div>
    </div>
  );
}
