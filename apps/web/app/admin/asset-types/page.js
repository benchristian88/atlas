"use client";

import { AccessDenied } from "../../../components/access-denied";
import { AssetIcon } from "../../../components/asset-icon";
import { useAuth } from "../../../components/auth-context";
import { CrudScreen } from "../../../components/crud-screen";

const fields = [
  { name: "key", label: "Key", createOnly: true, required: true, placeholder: "home_assistant", help: "Lowercase letters, numbers, and underscores; cannot change later." },
  { name: "name", label: "Name", required: true },
  { name: "category", label: "Category", placeholder: "Platform, Network, Workload…" },
  { name: "default_icon_url", label: "Default icon URL", type: "url", help: "Absolute HTTPS image URL. Remote SVG files are not accepted." },
  { name: "sort_order", label: "Sort order", type: "number", required: true },
  { name: "active", label: "Available for new assets", type: "checkbox" },
  { name: "description", label: "Description", type: "textarea", wide: true },
];

const columns = [
  { key: "icon", label: "Icon", render: (row) => <AssetIcon asset={{}} assetType={row} size={34} /> },
  { key: "name", label: "Asset type", render: (row) => <span className="primary-cell">{row.name}</span> },
  { key: "key", label: "Key", render: (row) => <span className="mono secondary-text">{row.key}</span> },
  { key: "category", label: "Category", render: (row) => row.category || "—" },
  { key: "active", label: "State", render: (row) => row.active ? "Active" : "Inactive" },
  { key: "in_use_count", label: "Assets", render: (row) => row.in_use_count },
  { key: "system_defined", label: "Origin", render: (row) => row.system_defined ? "Built-in" : "Custom" },
];

function deleteReason(row) {
  if (row.system_defined) return "Built-in asset types cannot be deleted.";
  if (row.in_use_count) return "This type is used by assets. Deactivate it instead.";
  return "This permanently removes the unused asset type.";
}

export default function AssetTypesAdminPage() {
  const { hasGlobalPermission, hasPermission } = useAuth();
  if (!hasPermission("asset_types.view")) return <AccessDenied />;
  const manage = hasGlobalPermission("asset_types.manage");
  return (
    <CrudScreen
      canCreate={manage}
      canDelete={manage ? (row) => !row.system_defined && row.in_use_count === 0 : false}
      canEdit={manage}
      columns={columns}
      deleteReason={deleteReason}
      description="Define the inventory taxonomy and default icon used when an asset has no override."
      emptyValues={{ key: "", name: "", category: "", default_icon_url: "", sort_order: "100", active: true, description: "" }}
      endpoint="/asset-types"
      eyebrow="Administration"
      fields={fields}
      preparePayload={(form, editingId) => ({
        ...(!editingId ? { key: form.key } : {}),
        name: form.name,
        category: form.category || null,
        default_icon_url: form.default_icon_url || null,
        sort_order: Number(form.sort_order),
        active: form.active,
        description: form.description || null,
      })}
      title="Asset types"
    />
  );
}
