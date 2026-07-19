"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "./auth-context";
import { useWorkspaceContext } from "./workspace-context";
import {
  navigationItemIsActive,
  visibleNavigationGroups,
} from "../lib/navigation-model.mjs";

export function Navigation() {
  const pathname = usePathname();
  const { hasGlobalPermission, hasPermissionInContext } = useAuth();
  const { customerId, siteId } = useWorkspaceContext();
  const groups = visibleNavigationGroups({
    customerId,
    hasGlobalPermission,
    hasPermissionInContext,
    siteId,
  });
  const primaryGroups = groups.filter((group) => group.placement !== "bottom");
  const systemGroup = groups.find((group) => group.id === "system");

  return (
    <nav className="nav-list" aria-label="Primary navigation">
      <div className="nav-primary-groups">
        {primaryGroups.map((group) => <NavigationGroup group={group} key={group.id} pathname={pathname} />)}
      </div>
      {systemGroup && <NavigationGroup className="nav-system-group" group={systemGroup} pathname={pathname} />}
    </nav>
  );
}

function NavigationGroup({ className = "", group, pathname }) {
  const labelId = `navigation-${group.id}-label`;
  return (
    <section aria-labelledby={labelId} className={`nav-group ${className}`.trim()}>
      <h2 className="nav-group-label" id={labelId}>{group.label}</h2>
      <div className="nav-group-items">
        {group.items.map((item) => <NavigationLink item={item} key={item.id} pathname={pathname} />)}
      </div>
    </section>
  );
}

function NavigationLink({ item, pathname }) {
  const active = navigationItemIsActive(item, pathname);
  return (
    <Link
      aria-current={active ? "page" : undefined}
      className={`nav-link${active ? " active" : ""}`}
      href={item.href}
    >
      {item.label}
    </Link>
  );
}
