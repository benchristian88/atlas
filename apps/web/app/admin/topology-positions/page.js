"use client";

import { AccessDenied } from "../../../components/access-denied";
import { useAuth } from "../../../components/auth-context";
import { CrudScreen } from "../../../components/crud-screen";

const fields = [
  { name: "name", label: "Name", required: true },
  { name: "key", label: "Key", createOnly: true, required: true, help: "Lowercase letters, numbers, and underscores; cannot change later." },
  { name: "description", label: "Description", type: "textarea", wide: true },
  { name: "active", label: "Active", type: "checkbox" },
];
const columns = [
  { key: "sort_order", label: "Order", render: (row, related, index) => <strong>{index + 1}</strong> },
  { key: "name", label: "Name" },
  { key: "key", label: "Key" },
  { key: "description", label: "Description" },
  { key: "asset_types_count", label: "Asset Types", render: row => row.asset_types_count },
  { key: "active", label: "State", render: row => row.active ? "Active" : "Inactive" },
];

export default function TopologyPositionsPage() {
  const { hasPermission, hasGlobalPermission } = useAuth();
  if (!hasPermission("asset_types.view")) return <AccessDenied />;
  const manage = hasGlobalPermission("asset_types.manage");
  return <CrudScreen title="Topology Positions" singularTitle="Topology Position" eyebrow="Reference Data"
    description="Controls vertical ordering in Infrastructure Topology."
    endpoint="/topology-positions" fields={fields} columns={columns} reorderable
    emptyValues={{ key: "", name: "", description: "", active: true }}
    canCreate={manage} canEdit={manage} canDelete={manage ? row => row.asset_types_count === 0 : false}
    deleteReason="Reassign all Asset Types before deleting a topology position."
    preparePayload={(form, editingId) => ({ ...(!editingId ? { key: form.key } : {}), name: form.name, description: form.description || null, active: form.active })} />;
}
