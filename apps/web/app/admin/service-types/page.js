"use client";

import Link from "next/link";
import { AccessDenied } from "../../../components/access-denied";
import { useAuth } from "../../../components/auth-context";
import { CrudScreen } from "../../../components/crud-screen";

const fields = [
  { name: "key", label: "Key", createOnly: true, required: true, placeholder: "application_service" },
  { name: "name", label: "Name", required: true },
  { name: "icon_key", label: "Icon key", placeholder: "Optional display hint" },
  { name: "sort_order", label: "Sort order", type: "number", required: true },
  { name: "active", label: "Available for new Services", type: "checkbox" },
  { name: "requires_asset_dependency", label: "Requires an Asset dependency", type: "checkbox", help: "Turn this off for external Services that intentionally have no managed Asset." },
  { name: "description", label: "Description", type: "textarea", wide: true },
];
const columns = [
  { key: "name", label: "Service type", render: (row) => <span className="primary-cell">{row.name}</span> },
  { key: "key", label: "Key", render: (row) => <span className="mono secondary-text">{row.key}</span> },
  { key: "requires_asset_dependency", label: "Asset dependency", render: (row) => row.requires_asset_dependency ? "Required" : "Explicitly optional" },
  { key: "active", label: "State", render: (row) => row.active ? "Active" : "Inactive" },
  { key: "in_use_count", label: "Services", render: (row) => row.in_use_count },
  { key: "system_defined", label: "Origin", render: (row) => row.system_defined ? "Built-in" : "Custom" },
];

export default function ServiceTypesAdminPage() {
  const { hasGlobalPermission, hasPermission } = useAuth();
  if (!hasPermission("service_types.view")) return <AccessDenied />;
  const manage = hasGlobalPermission("service_types.manage");
  const visibleColumns = hasGlobalPermission("knowledge_requirements.view")
    ? [...columns, { key: "knowledge_profile", label: "Knowledge profile", render: (row) => <Link className="text-button" href={`/admin/service-types/${row.id}/knowledge-profile`}>Configure</Link> }]
    : columns;
  return <CrudScreen
    canCreate={manage} canDelete={false} canEdit={manage}
    columns={visibleColumns}
    description="Define stable operational Service categories. Referenced types can be renamed or deactivated without breaking Services."
    emptyValues={{ key: "", name: "", icon_key: "", sort_order: "100", active: true, requires_asset_dependency: true, description: "" }}
    endpoint="/service-types" eyebrow="Reference Data" fields={fields}
    preparePayload={(form, editingId) => ({ ...(!editingId ? { key: form.key } : {}), name: form.name, icon_key: form.icon_key || null, sort_order: Number(form.sort_order), active: form.active, requires_asset_dependency: form.requires_asset_dependency, description: form.description || null })}
    headingActions={hasGlobalPermission("knowledge_requirements.view") && hasGlobalPermission("knowledge_requirements.manage") && <Link className="button button-secondary" href="/admin/service-types/requirements/global">Manage global requirements</Link>}
    title="Service types"
  />;
}
