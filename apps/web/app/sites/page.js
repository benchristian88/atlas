"use client";

import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { CrudScreen } from "../../components/crud-screen";
import { useWorkspaceContext } from "../../components/workspace-context";

const dependencies = [{ key: "customers", endpoint: "/customers" }];
const fields = [
  { name: "customer_id", label: "Customer", type: "select", optionsKey: "customers", required: true, placeholder: "Select a customer" },
  { name: "name", label: "Name", required: true },
  { name: "address", label: "Address", type: "textarea", wide: true },
  { name: "notes", label: "Notes", type: "textarea", wide: true },
  { name: "status", label: "Status", type: "select", required: true, options: [
    { value: "active", label: "Active" }, { value: "inactive", label: "Inactive" },
  ] },
];
const columns = [
  { key: "name", label: "Site", render: (row) => <span className="primary-cell">{row.name}</span> },
  { key: "customer_id", label: "Customer", render: (row, related) => related.customers?.[row.customer_id]?.name || "Unknown" },
  { key: "address", label: "Address", render: (row) => <span className="secondary-text">{row.address || "—"}</span> },
  { key: "notes", label: "Notes", render: (row) => <span className="secondary-text">{row.notes || "—"}</span> },
  { key: "status", label: "Status" },
];

export default function SitesPage() {
  const {
    hasPermission,
    hasPermissionForObject,
    hasPermissionInContext,
  } = useAuth();
  const { activeCustomer, customerId, reload, reloadKey } = useWorkspaceContext();
  if (!hasPermission("sites.view")) return <AccessDenied />;
  return (
    <CrudScreen
      canCreate={customerId
        ? hasPermissionForObject("sites.manage", customerId)
        : hasPermissionInContext("sites.manage")}
      canDelete={(row) => hasPermissionForObject("sites.manage", row.customer_id, row.id)}
      canEdit={(row) => hasPermissionForObject("sites.manage", row.customer_id, row.id)}
      columns={columns}
      contextReloadKey={reloadKey}
      dependencies={hasPermission("customers.view") ? dependencies : []}
      description="Create and maintain physical or logical locations for each customer."
      deleteReason="Sites with assets, networks, integrations, or access assignments must be deactivated instead."
      emptyValues={{ customer_id: customerId || "", name: "", address: "", notes: "", status: "active" }}
      endpoint="/sites"
      eyebrow="Locations"
      fields={fields}
      listEndpoint={customerId ? `/sites?customer_id=${encodeURIComponent(customerId)}` : "/sites"}
      onMutation={reload}
      preparePayload={(form) => ({ ...form, address: form.address || null, notes: form.notes || null })}
      title={activeCustomer ? `${activeCustomer.name} sites` : "Sites"}
    />
  );
}
