"use client";

import { CrudScreen } from "../../components/crud-screen";

const fields = [
  { name: "workspace_id", label: "Workspace ID", required: true, createOnly: true, placeholder: "UUID", help: "Workspace cannot be changed after customer creation." },
  { name: "name", label: "Name", required: true },
  { name: "description", label: "Description", type: "textarea", wide: true },
];

const columns = [
  { key: "name", label: "Customer", render: (row) => <span className="primary-cell">{row.name}</span> },
  { key: "description", label: "Description", render: (row) => <span className="secondary-text">{row.description || "—"}</span> },
  { key: "workspace_id", label: "Workspace", render: (row) => <span className="mono secondary-text">{row.workspace_id}</span> },
];

export default function CustomersPage() {
  return (
    <CrudScreen
      columns={columns}
      description="Create and maintain organisations whose infrastructure is managed in this workspace."
      emptyValues={{ workspace_id: "", name: "", description: "" }}
      endpoint="/customers"
      eyebrow="Organisation"
      fields={fields}
      preparePayload={(form, editingId) => {
        const payload = { ...form, description: form.description || null };
        if (editingId) delete payload.workspace_id;
        return payload;
      }}
      title="Customers"
    />
  );
}
