import { SYSTEM_GROUPS } from "./system-navigation.mjs";

export const NAVIGATION_GROUPS = [
  {
    id: "overview",
    label: "Overview",
    items: [
      {
        id: "dashboard",
        href: "/dashboard",
        label: "Dashboard",
        anyPermission: ["customers.view", "sites.view", "assets.view", "relationships.view", "networks.view", "services.view", "business_functions.view"],
      },
      { id: "changes", href: "/changes", label: "Changes", permission: "changes.view" },
    ],
  },
  {
    id: "knowledge",
    label: "Knowledge",
    items: [
      { id: "knowledge-graph", href: "/knowledge-graph", activeRoutes: ["/knowledge-graph"], label: "Knowledge Graph", anyPermission: ["assets.view", "services.view", "business_functions.view"] },
      { id: "topology", href: "/topology", label: "Infrastructure Topology", permission: "assets.view" },
      { id: "assets", href: "/assets", label: "Assets", permission: "assets.view" },
      { id: "services", href: "/services", label: "Services", permission: "services.view" },
      { id: "business-functions", href: "/business-functions", label: "Business Functions", permission: "business_functions.view" },
      { id: "people-teams", label: "People & Teams", available: false },
      { id: "networks", href: "/networks", label: "Networks", permission: "networks.view" },
    ],
  },
  {
    id: "operations",
    label: "Operations",
    items: [
      { id: "discovery", href: "/discovery-runs", label: "Discovery", permission: "integrations.view", activeRoutes: ["/discovery-runs", "/discovery"] },
      { id: "reconciliation", href: "/reconciliation", label: "Reconciliation", permission: "reconciliation.view" },
      { id: "knowledge-gaps", href: "/knowledge-gaps", label: "Knowledge Gaps", permission: "knowledge_gaps.view" },
      { id: "impact-analysis", label: "Impact Analysis", available: false },
      { id: "backup-recovery", label: "Backup & Recovery", available: false },
      { id: "documentation", label: "Documentation", available: false },
    ],
  },
  {
    id: "connections",
    label: "Connections",
    items: [
      { id: "integrations", href: "/integrations", label: "Integrations", permission: "integrations.view" },
    ],
  },
  {
    id: "system",
    label: "System",
    placement: "bottom",
    items: SYSTEM_GROUPS,
  },
];

function mayUseDestination(destination, access) {
  if (destination.globalPermission) {
    return access.hasGlobalPermission(destination.globalPermission);
  }
  if (destination.permission) {
    return access.hasPermissionInContext(
      destination.permission,
      access.customerId,
      access.siteId,
    );
  }
  return true;
}

function resolveNavigationItem(item, access) {
  if (item.available === false) return null;
  if (item.destinations) {
    const destination = item.destinations.find((candidate) => mayUseDestination(candidate, access));
    return destination ? { ...item, href: destination.href } : null;
  }
  if (item.permission && !access.hasPermissionInContext(
    item.permission,
    access.customerId,
    access.siteId,
  )) return null;
  if (item.anyPermission && !item.anyPermission.some((permission) => (
    access.hasPermissionInContext(permission, access.customerId, access.siteId)
  ))) return null;
  return item.href ? item : null;
}

export function visibleNavigationGroups(access) {
  return NAVIGATION_GROUPS.map((group) => ({
    ...group,
    items: group.items
      .map((item) => resolveNavigationItem(item, access))
      .filter(Boolean),
  })).filter((group) => group.items.length > 0);
}

export function navigationItemIsActive(item, pathname) {
  const routes = item.activeRoutes || [item.href];
  return routes.some((route) => (
    pathname === route || pathname.startsWith(`${route}/`)
  ));
}
