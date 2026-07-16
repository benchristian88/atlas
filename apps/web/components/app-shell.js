"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { authenticatedHome, useAuth } from "./auth-context";
import { ContextSelector } from "./context-selector";
import { Navigation } from "./navigation";
import { useWorkspaceContext } from "./workspace-context";
import { logout } from "../lib/auth";
import { accentThemeStyle } from "../lib/accent-theme.mjs";

export function AppShell({ children }) {
  const router = useRouter();
  const { user } = useAuth();
  const workspace = useWorkspaceContext();
  const [logoutError, setLogoutError] = useState("");
  const [signingOut, setSigningOut] = useState(false);

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
    <div className="app-shell" style={accentThemeStyle(user.accent_colour)}>
      <aside className="sidebar">
        <Link className="brand" href={authenticatedHome(user)}>
          <span className="brand-mark" aria-hidden="true">A</span>
          Atlas
        </Link>
        <p className="nav-label">Workspace</p>
        <Navigation />
        <div className="sidebar-footer">
          Atlas MVP<br />Local development
        </div>
      </aside>
      <div className="content">
        <header className="topbar">
          <ContextSelector />
          <div className="account-menu">
            <Link className="account-identity" href="/profile">
              <strong>{user.display_name || user.email}</strong>
              {user.display_name && <span>{user.email}</span>}
            </Link>
            <button
              className="button button-secondary"
              disabled={signingOut}
              onClick={signOut}
              type="button"
            >
              {signingOut ? "Signing out…" : "Logout"}
            </button>
          </div>
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
