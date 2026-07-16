"use client";

import { AccessDenied } from "../../../components/access-denied";
import { useAuth } from "../../../components/auth-context";
import { CrudScreen } from "../../../components/crud-screen";

const dataTypes = [
  ["text", "Text"],
  ["multiline_text", "Multiline text"],
  ["number", "Number"],
  ["date", "Date"],
  ["boolean", "Yes / No"],
  ["url", "URL"],
  ["dropdown", "Dropdown"],
].map(([value, label]) => ({ value, label }));

const dependencies = [{ key: "assetTypes", endpoint: "/asset-types" }];
const fields = [
  { name: "key", label: "Key", createOnly: true, required: true, placeholder: "support_owner", help: "Lowercase letters, numbers, and underscores; cannot change later." },
  { name: "name", label: "Name", required: true },
  { name: "data_type", label: "Data type", type: "select", options: dataTypes, required: true, createOnly: true },
  { name: "sort_order", label: "Sort order", type: "number", required: true },
  { name: "required", label: "Required on matching assets", type: "checkbox" },
  { name: "active", label: "Active", type: "checkbox" },
  { name: "applies_to_all_asset_types", label: "Applies to every asset type", type: "checkbox", clearFields: ["asset_type_keys"] },
  {
    name: "asset_type_keys",
    label: "Specific asset types",
    type: "multiselect",
    optionsKey: "assetTypes",
    optionValue: (option) => option.key,
    disabled: (form) => form.applies_to_all_asset_types,
    help: "Used only when the field does not apply to every asset type.",
  },
  { name: "options_text", label: "Dropdown options", type: "textarea", rows: 5, wide: true, valueFromRecord: (record) => record.options.map((option) => `${option.value} | ${option.label}${option.active ? "" : " | inactive"}`).join("\n"), help: "For dropdowns only: one value | label pair per line. Add | inactive to retire an option without deleting stored values." },
  { name: "description", label: "Description", type: "textarea", wide: true },
  { name: "help_text", label: "Help text shown on asset forms", type: "textarea", wide: true },
];
const columns = [
  { key: "name", label: "Field", render: (row) => <span className="primary-cell">{row.name}</span> },
  { key: "key", label: "Key", render: (row) => <span className="mono secondary-text">{row.key}</span> },
  { key: "data_type", label: "Type", render: (row) => dataTypes.find((item) => item.value === row.data_type)?.label || row.data_type },
  { key: "scope", label: "Applies to", render: (row) => row.applies_to_all_asset_types ? "All asset types" : `${row.asset_type_keys.length} selected` },
  { key: "required", label: "Required", render: (row) => row.required ? "Yes" : "No" },
  { key: "active", label: "State", render: (row) => row.active ? "Active" : "Inactive" },
  { key: "in_use_count", label: "Values", render: (row) => row.in_use_count },
];

function parseOptions(value) {
  return value.split("\n").map((line) => line.trim()).filter(Boolean).map((line, index) => {
    const [rawValue, rawLabel, rawState] = line.split("|");
    const optionValue = rawValue.trim();
    const label = rawLabel?.trim() || optionValue;
    if (!optionValue) throw new Error(`Dropdown option ${index + 1} needs a value.`);
    return { value: optionValue, label, active: rawState?.trim().toLowerCase() !== "inactive", sort_order: (index + 1) * 10 };
  });
}

export default function CustomFieldsAdminPage() {
  const { hasGlobalPermission, hasPermission } = useAuth();
  if (!hasPermission("custom_fields.view")) return <AccessDenied />;
  const manage = hasGlobalPermission("custom_fields.manage");
  return (
    <CrudScreen
      canCreate={manage}
      canDelete={manage ? (row) => row.in_use_count === 0 : false}
      canEdit={manage}
      columns={columns}
      deleteReason={(row) => row.in_use_count
        ? "This field has stored values. Deactivate it instead."
        : "This permanently removes the unused field definition."}
      dependencies={hasPermission("asset_types.view") ? dependencies : []}
      description="Add up to ten typed enrichment fields per asset type without changing the core inventory schema."
      emptyValues={{ key: "", name: "", data_type: "text", sort_order: "100", required: false, active: true, applies_to_all_asset_types: true, asset_type_keys: [], options_text: "", description: "", help_text: "" }}
      endpoint="/custom-fields"
      eyebrow="Administration"
      fields={fields}
      preparePayload={(form, editingId) => {
        const payload = {
          ...(!editingId ? { key: form.key, data_type: form.data_type } : {}),
          name: form.name,
          sort_order: Number(form.sort_order),
          required: form.required,
          active: form.active,
          applies_to_all_asset_types: form.applies_to_all_asset_types,
          asset_type_keys: form.applies_to_all_asset_types ? [] : form.asset_type_keys,
          description: form.description || null,
          help_text: form.help_text || null,
        };
        if (form.data_type === "dropdown") payload.options = parseOptions(form.options_text);
        else if (!editingId) payload.options = [];
        return payload;
      }}
      title="Custom fields"
    />
  );
}
