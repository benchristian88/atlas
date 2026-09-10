export const SYSTEM_SECTIONS = [
  { group: "organisation", href: "/admin/users", label: "Users", globalPermission: "users.view" },
  { group: "organisation", href: "/admin/roles", label: "Roles & permissions", globalPermission: "roles.view" },
  { group: "organisation", href: "/admin/customers", label: "Customers", permission: "customers.view" },
  { group: "organisation", href: "/admin/sites", label: "Sites", permission: "sites.view" },
  { group: "reference-data", href: "/admin/asset-types", label: "Asset types", permission: "asset_types.view" },
  { group: "reference-data", href: "/admin/relationship-types", label: "Relationship types", permission: "relationship_types.view" },
  { group: "reference-data", href: "/admin/service-types", label: "Service types", permission: "service_types.view" },
  { group: "reference-data", href: "/admin/criticality-levels", label: "Criticality levels", permission: "criticality_levels.view" },
  { group: "reference-data", href: "/admin/custom-fields", label: "Custom fields", permission: "custom_fields.view" },
  { group: "audit-log", href: "/admin/audit", label: "Audit Log", permission: "audit.view" },
  { group: "system-settings", href: "/admin/system-settings", label: "System Settings", globalPermission: "system_settings.manage" },
];

export const SYSTEM_GROUPS = [
  { id: "organisation", label: "Organisation" },
  { id: "reference-data", label: "Reference Data" },
  { id: "audit-log", label: "Audit Log" },
  { id: "system-settings", label: "System Settings" },
].map((group) => ({
  ...group,
  destinations: SYSTEM_SECTIONS.filter((section) => section.group === group.id),
  activeRoutes: SYSTEM_SECTIONS.filter((section) => section.group === group.id).map((section) => section.href),
}));

export function mayUseSystemSection(section, access) {
  return section.globalPermission
    ? access.hasGlobalPermission(section.globalPermission)
    : access.hasPermissionInContext(section.permission, access.customerId, access.siteId);
}

export function visibleSystemSections(access) {
  return SYSTEM_SECTIONS.filter((section) => mayUseSystemSection(section, access));
}

export function systemSectionForPath(pathname) {
  return SYSTEM_SECTIONS.find((section) => pathname === section.href || pathname.startsWith(`${section.href}/`));
}
