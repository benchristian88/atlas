"use client";

import { AccessDenied } from "../../../components/access-denied";
import { useAuth } from "../../../components/auth-context";
import { CrudScreen } from "../../../components/crud-screen";

const dependencies = [{ key: "permissions", endpoint: "/permissions" }];
const fields = [
  { name: "name", label: "Name", required: true },
  { name: "sort_order", label: "Sort order", type: "number", required: true },
  { name: "active", label: "Available for assignments", type: "checkbox" },
  {
    name: "permission_keys",
    label: "Permissions",
    type: "multiselect",
    optionsKey: "permissions",
    optionValue: (option) => option.key,
    optionLabel: (option) => `${option.category || "General"} — ${option.name}`,
    valueFromRecord: (record) => record.permissions.map((permission) => permission.key),
    wide: true,
    size: 12,
  },
  { name: "description", label: "Description", type: "textarea", wide: true },
];
const columns = [
  { key: "name", label: "Role", render: (row) => <span className="primary-cell">{row.name}</span> },
  { key: "description", label: "Description", render: (row) => <span className="secondary-text">{row.description || "—"}</span> },
  { key: "permissions", label: "Permissions", render: (row) => <details className="permission-details"><summary>{row.permissions.length} assigned</summary><div>{row.permissions.map((permission) => <code key={permission.key}>{permission.key}</code>)}</div></details> },
  { key: "active", label: "State", render: (row) => row.active ? "Active" : "Inactive" },
  { key: "system_defined", label: "Origin", render: (row) => row.system_defined ? "Built-in" : "Custom" },
];

export default function RolesAdminPage() {
  const { hasGlobalPermission } = useAuth();
  if (!hasGlobalPermission("roles.view")) return <AccessDenied />;
  const manage = hasGlobalPermission("roles.manage");
  return (
    <CrudScreen
      canCreate={manage}
      canDelete={manage ? (row) => !row.system_defined : false}
      canEdit={manage ? (row) => !row.system_defined : false}
      columns={columns}
      deleteReason={(row) => row.system_defined
        ? "Built-in roles are protected."
        : "Roles assigned to users cannot be deleted."}
      dependencies={dependencies}
      description="Inspect built-in roles or create permission bundles for future access assignments."
      emptyValues={{ name: "", sort_order: "100", active: true, permission_keys: [], description: "" }}
      endpoint="/roles"
      eyebrow="Organisation"
      fields={fields}
      preparePayload={(form) => ({
        name: form.name,
        sort_order: Number(form.sort_order),
        active: form.active,
        permission_keys: form.permission_keys,
        description: form.description || null,
      })}
      title="Roles"
    />
  );
}
