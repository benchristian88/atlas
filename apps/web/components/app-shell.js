import Link from "next/link";
import { Navigation } from "./navigation";

export function AppShell({ children }) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" href="/">
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
          <span className="environment-badge">Mock data</span>
        </header>
        <main className="page-content">{children}</main>
      </div>
    </div>
  );
}
