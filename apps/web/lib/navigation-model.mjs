export const NAVIGATION_GROUPS = [
  {
    id: "overview",
    label: "Overview",
    items: [
      {
        id: "dashboard",
        href: "/dashboard",
        label: "Dashboard",
        anyPermission: ["customers.view", "sites.view", "assets.view", "relationships.view", "networks.view"],
      },
      { id: "changes", label: "Changes", available: false },
    ],
  },
  {
    id: "knowledge",
    label: "Knowledge",
    items: [
      { id: "knowledge-graph", href: "/topology", label: "Knowledge Graph", permission: "assets.view" },
      { id: "assets", href: "/assets", label: "Assets", permission: "assets.view" },
      { id: "services", label: "Services", available: false },
      { id: "business-functions", label: "Business Functions", available: false },
      { id: "people-teams", label: "People & Teams", available: false },
      { id: "networks", href: "/networks", label: "Networks", permission: "networks.view" },
    ],
  },
  {
    id: "operations",
    label: "Operations",
    items: [
      { id: "discovery", href: "/discovery-runs", label: "Discovery", permission: "integrations.view", activeRoutes: ["/discovery-runs", "/discovery"] },
      { id: "reconciliation", href: "/reconciliation", label: "Reconciliation", permission: "assets.view" },
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
    items: [
      {
        id: "users-access",
        label: "Users & Access",
        destinations: [
          { href: "/admin/users", globalPermission: "users.view" },
          { href: "/admin/roles", globalPermission: "roles.view" },
        ],
        activeRoutes: ["/admin/users", "/admin/roles"],
      },
      {
        id: "reference-data",
        label: "Reference Data",
        destinations: [
          { href: "/admin/asset-types", globalPermission: "asset_types.manage" },
          { href: "/admin/relationship-types", globalPermission: "relationship_types.manage" },
          { href: "/admin/custom-fields", globalPermission: "custom_fields.manage" },
          { href: "/admin/customers", permission: "customers.manage" },
          { href: "/admin/sites", permission: "sites.manage" },
        ],
        activeRoutes: [
          "/admin/asset-types",
          "/admin/relationship-types",
          "/admin/custom-fields",
          "/admin/customers",
          "/admin/sites",
        ],
      },
      {
        id: "system-settings",
        label: "System Settings",
        destinations: [
          { href: "/admin/system-settings", globalPermission: "system_settings.manage" },
        ],
        activeRoutes: ["/admin/system-settings"],
      },
    ],
  },
];

export const PROFILE_NAVIGATION_ITEM = {
  id: "profile",
  href: "/profile",
  label: "Profile",
};

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
