"use client";

import { AccessDenied } from "../../../components/access-denied";
import { useAuth } from "../../../components/auth-context";
import { CrudScreen } from "../../../components/crud-screen";

const fields = [
  { name: "key", label: "Key", createOnly: true, required: true, help: "Lowercase letters, numbers, and underscores; cannot change later." },
  { name: "name", label: "Name", required: true, disabled: (form) => form.key === "uncategorized" },
  { name: "description", label: "Description", type: "textarea", wide: true },
  { name: "sort_order", label: "Sort order", type: "number", required: true },
  { name: "active", label: "Active", type: "checkbox", disabled: (form) => form.key === "uncategorized" },
  { name: "show_in_topology", label: "Show in Infrastructure Topology by default", type: "checkbox", help: "Operators can temporarily enable any category in topology Filters." },
];
const columns = [
  { key: "name", label: "Name" }, { key: "key", label: "Key" },
  { key: "description", label: "Description" }, { key: "asset_types_count", label: "Asset Types", render: row => row.asset_types_count },
  { key: "show_in_topology", label: "Show in Infrastructure Topology", render: row => row.show_in_topology ? "By default" : "Available in Filters" },
  { key: "active", label: "State", render: row => row.active ? "Active" : "Inactive" },
];
export default function AssetCategoriesPage() {
  const { hasPermission, hasGlobalPermission } = useAuth();
  if (!hasPermission("asset_types.view")) return <AccessDenied />;
  const manage = hasGlobalPermission("asset_types.manage");
  return <CrudScreen title="Asset categories" singularTitle="Asset category" eyebrow="Reference Data" description="Organise Asset Types and choose their default visibility in Infrastructure Topology."
    endpoint="/asset-categories" fields={fields} columns={columns}
    emptyValues={{ key: "", name: "", description: "", sort_order: "100", active: true, show_in_topology: true }}
    canCreate={manage} canEdit={manage} canDelete={manage ? row => row.key !== "uncategorized" && row.asset_types_count === 0 : false}
    deleteReason={row => row.key === "uncategorized" ? "Uncategorized is protected and cannot be deleted." : "Reassign all Asset Types before deleting a category."}
    preparePayload={(form, editingId) => ({ ...(!editingId ? { key: form.key } : {}), name: form.name, description: form.description || null, sort_order: Number(form.sort_order), active: form.active, show_in_topology: form.show_in_topology })} />;
}
