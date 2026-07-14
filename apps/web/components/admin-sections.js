export const ADMIN_SECTIONS = [
  {
    href: "/admin/users",
    label: "Users",
    description: "Accounts, access assignments, state, and password resets.",
    permissions: ["users.view"],
    global: true,
  },
  {
    href: "/admin/roles",
    label: "Roles & permissions",
    description: "Built-in and custom permission bundles.",
    permissions: ["roles.view"],
    global: true,
  },
  {
    href: "/admin/customers",
    label: "Customers",
    description: "Managed organisations and their lifecycle.",
    permissions: ["customers.view"],
  },
  {
    href: "/admin/sites",
    label: "Sites",
    description: "Customer locations and operational scope.",
    permissions: ["sites.view"],
  },
  {
    href: "/admin/asset-types",
    label: "Asset types",
    description: "Inventory taxonomy and default icons.",
    permissions: ["asset_types.view"],
  },
  {
    href: "/admin/relationship-types",
    label: "Relationship types",
    description: "Topology semantics and endpoint constraints.",
    permissions: ["relationship_types.view"],
  },
  {
    href: "/admin/custom-fields",
    label: "Custom fields",
    description: "Typed enrichment fields for selected asset types.",
    permissions: ["custom_fields.view"],
  },
  {
    href: "/admin/audit",
    label: "Audit log",
    description: "Security-sensitive and administrative activity.",
    permissions: ["audit.view"],
  },
  {
    href: "/admin/system-settings",
    label: "System settings",
    description: "Instance-level configuration managed by master administrators.",
    permissions: ["system_settings.manage"],
    global: true,
  },
];

export function visibleAdminSections(user) {
  const permissions = new Set(user?.permissions || []);
  return ADMIN_SECTIONS.filter((section) => section.permissions.some((key) => {
    if (!permissions.has(key)) return false;
    if (!section.global) return true;
    return user?.assignments?.some(
      (assignment) => assignment.scope_type === "global"
        && assignment.permissions?.includes(key),
    );
  }));
}
