"use client";

import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { CrudScreen } from "../../components/crud-screen";
import { useWorkspaceContext } from "../../components/workspace-context";

const fields = [
  { name: "name", label: "Name", required: true },
  { name: "description", label: "Description", type: "textarea", wide: true },
  { name: "status", label: "Status", type: "select", required: true, options: [
    { value: "active", label: "Active" }, { value: "inactive", label: "Inactive" },
  ] },
];

const columns = [
  { key: "name", label: "Customer", render: (row) => <span className="primary-cell">{row.name}</span> },
  { key: "description", label: "Description", render: (row) => <span className="secondary-text">{row.description || "—"}</span> },
  { key: "status", label: "Status" },
];

export default function CustomersPage() {
  const { hasGlobalPermission, hasPermission, hasPermissionForObject } = useAuth();
  const { allowGlobal, reload, reloadKey } = useWorkspaceContext();
  if (!hasPermission("customers.view")) return <AccessDenied />;
  return (
    <CrudScreen
      canCreate={allowGlobal && hasGlobalPermission("customers.manage")}
      canDelete={(row) => hasPermissionForObject("customers.manage", row.id)}
      canEdit={(row) => hasPermissionForObject("customers.manage", row.id)}
      columns={columns}
      contextReloadKey={reloadKey}
      deleteReason="Customers with sites or infrastructure must be deactivated instead."
      description="Create and maintain organisations whose infrastructure is managed in this workspace."
      emptyValues={{ name: "", description: "", status: "active" }}
      endpoint="/customers"
      eyebrow="Organisation"
      fields={fields}
      onMutation={reload}
      preparePayload={(form) => ({ ...form, description: form.description || null })}
      title="Customers"
    />
  );
}
