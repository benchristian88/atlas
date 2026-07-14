"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { visibleAdminSections } from "./admin-sections";
import { useAuth } from "./auth-context";
import { useWorkspaceContext } from "./workspace-context";

const items = [
  {
    href: "/dashboard",
    label: "Dashboard",
    anyPermission: ["customers.view", "sites.view", "assets.view", "relationships.view", "networks.view"],
  },
  { href: "/assets", label: "Assets", permission: "assets.view" },
  { href: "/topology", label: "Topology", permission: "assets.view" },
  { href: "/networks", label: "Networks", permission: "networks.view" },
  { href: "/integrations", label: "Integrations", permission: "integrations.view" },
  { href: "/discovery-runs", label: "Discovery runs", permission: "integrations.view" },
];

function maySee(item, hasPermissionInContext, customerId, siteId) {
  if (item.permission) {
    return hasPermissionInContext(item.permission, customerId, siteId);
  }
  if (item.anyPermission) {
    return item.anyPermission.some(
      (permission) => hasPermissionInContext(permission, customerId, siteId),
    );
  }
  return true;
}

export function Navigation() {
  const pathname = usePathname();
  const { hasPermissionInContext, user } = useAuth();
  const { customerId, siteId } = useWorkspaceContext();
  const visibleItems = items.filter(
    (item) => maySee(item, hasPermissionInContext, customerId, siteId),
  );
  if (visibleAdminSections(user).length) {
    visibleItems.push({ href: "/admin", label: "Administration" });
  }
  visibleItems.push({ href: "/profile", label: "Profile" });

  return (
    <nav className="nav-list" aria-label="Primary navigation">
      {visibleItems.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={`nav-link${active ? " active" : ""}`}
            href={item.href}
            key={item.href}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
