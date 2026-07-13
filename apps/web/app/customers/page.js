"use client";

import { CrudScreen } from "../../components/crud-screen";

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
  return (
    <CrudScreen
      columns={columns}
      description="Create and maintain organisations whose infrastructure is managed in this workspace."
      emptyValues={{ name: "", description: "", status: "active" }}
      endpoint="/customers"
      eyebrow="Organisation"
      fields={fields}
      preparePayload={(form) => ({ ...form, description: form.description || null })}
      title="Customers"
    />
  );
}
