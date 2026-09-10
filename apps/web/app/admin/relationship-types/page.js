"use client";

import { AccessDenied } from "../../../components/access-denied";
import { useAuth } from "../../../components/auth-context";
import { CrudScreen } from "../../../components/crud-screen";

const dependencies = [{ key: "assetTypes", endpoint: "/asset-types" }];
const endpointOptions = [
  { id: "asset:asset", name: "Asset → Asset" },
  { id: "service:asset", name: "Service → Asset" },
  { id: "service:service", name: "Service → Service" },
  { id: "service:business_function", name: "Service → Business Function" },
];
const fields = [
  { name: "key", label: "Key", createOnly: true, required: true, placeholder: "managed_by", help: "Lowercase letters, numbers, and underscores; cannot change later." },
  { name: "name", label: "Name", required: true },
  { name: "source_label", label: "Source label", required: true, placeholder: "manages" },
  { name: "target_label", label: "Target label", required: true, placeholder: "managed by" },
  { name: "inverse_label", label: "Inverse label", placeholder: "Optional inverse wording" },
  { name: "sort_order", label: "Sort order", type: "number", required: true },
  { name: "directional", label: "Directional relationship", type: "checkbox" },
  { name: "active", label: "Available for new relationships", type: "checkbox" },
  { name: "allowed_source_asset_type_keys", label: "Allowed source asset types", type: "multiselect", optionsKey: "assetTypes", optionValue: (option) => option.key, help: "Leave empty to allow every active asset type." },
  { name: "allowed_target_asset_type_keys", label: "Allowed target asset types", type: "multiselect", optionsKey: "assetTypes", optionValue: (option) => option.key, help: "Leave empty to allow every active asset type." },
  { name: "applicability_pairs", label: "Typed endpoint applicability", type: "multiselect", options: endpointOptions, valueFromRecord: (record) => (record.applicability || []).filter((item) => item.active).map((item) => `${item.source_entity_type}:${item.target_entity_type}`), help: "Service dependency selectors only show relationships explicitly allowed for that endpoint pair." },
  { name: "description", label: "Description", type: "textarea", wide: true },
];
const columns = [
  { key: "name", label: "Relationship", render: (row) => <span className="primary-cell">{row.name}</span> },
  { key: "key", label: "Key", render: (row) => <span className="mono secondary-text">{row.key}</span> },
  { key: "labels", label: "Direction", render: (row) => `${row.source_label} → ${row.target_label}` },
  { key: "directional", label: "Mode", render: (row) => row.directional ? "Directional" : "Bidirectional" },
  { key: "active", label: "State", render: (row) => row.active ? "Active" : "Inactive" },
  { key: "in_use_count", label: "Uses", render: (row) => row.in_use_count },
  { key: "applicability", label: "Typed endpoints", render: (row) => (row.applicability || []).filter((item) => item.active).map((item) => `${item.source_entity_type.replace("_", " ")} → ${item.target_entity_type.replace("_", " ")}`).join(", ") || "Legacy Asset → Asset" },
  { key: "system_defined", label: "Origin", render: (row) => row.system_defined ? "Built-in" : "Custom" },
];

function deleteReason(row) {
  if (row.system_defined) return "Built-in relationship types cannot be deleted.";
  if (row.in_use_count) return "This type is used by relationships. Deactivate it instead.";
  return "This permanently removes the unused relationship type.";
}

export default function RelationshipTypesAdminPage() {
  const { hasGlobalPermission, hasPermission } = useAuth();
  if (!hasPermission("relationship_types.view")) return <AccessDenied />;
  const manage = hasGlobalPermission("relationship_types.manage");
  return (
    <CrudScreen
      canCreate={manage}
      canDelete={manage ? (row) => !row.system_defined && row.in_use_count === 0 : false}
      canEdit={manage}
      columns={columns}
      deleteReason={deleteReason}
      dependencies={hasPermission("asset_types.view") ? dependencies : []}
      description="Define the vocabulary and permitted endpoint types used by Atlas topology relationships."
      emptyValues={{ key: "", name: "", source_label: "", target_label: "", inverse_label: "", sort_order: "100", directional: true, active: true, allowed_source_asset_type_keys: [], allowed_target_asset_type_keys: [], applicability_pairs: [], description: "" }}
      endpoint="/relationship-types"
      eyebrow="Reference Data"
      fields={fields}
      preparePayload={(form, editingId) => ({
        ...(!editingId ? { key: form.key } : {}),
        name: form.name,
        source_label: form.source_label,
        target_label: form.target_label,
        inverse_label: form.inverse_label || null,
        directional: form.directional,
        active: form.active,
        sort_order: Number(form.sort_order),
        allowed_source_asset_type_keys: form.allowed_source_asset_type_keys,
        allowed_target_asset_type_keys: form.allowed_target_asset_type_keys,
        applicability: form.applicability_pairs.map((pair) => { const [source_entity_type, target_entity_type] = pair.split(":"); return { source_entity_type, target_entity_type, active: true }; }),
        description: form.description || null,
      })}
      title="Relationship types"
    />
  );
}
