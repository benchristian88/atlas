"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./auth-context";
import { Navigation } from "./navigation";
import { logout } from "../lib/auth";

export function AppShell({ children }) {
  const router = useRouter();
  const { user } = useAuth();
  const [logoutError, setLogoutError] = useState("");

  function signOut() {
    setLogoutError("");
    try {
      logout();
      router.replace("/login");
      router.refresh();
    } catch (storageError) {
      setLogoutError(storageError.message);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" href="/dashboard">
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
          <span className="workspace-name">Atlas Demo Workspace</span>
          <div className="account-menu">
            <span className="account-identity">
              <strong>{user.display_name || user.email}</strong>
              {user.display_name && <span>{user.email}</span>}
            </span>
            <button className="button button-secondary" onClick={signOut} type="button">Logout</button>
          </div>
        </header>
        {logoutError && <div className="shell-error error-banner" role="alert">{logoutError}</div>}
        <main className="page-content">{children}</main>
      </div>
    </div>
  );
}
