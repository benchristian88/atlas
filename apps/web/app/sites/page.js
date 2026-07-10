"use client";

import { CrudScreen } from "../../components/crud-screen";

const dependencies = [{ key: "customers", endpoint: "/customers" }];
const fields = [
  { name: "customer_id", label: "Customer", type: "select", optionsKey: "customers", required: true, placeholder: "Select a customer" },
  { name: "name", label: "Name", required: true },
  { name: "address", label: "Address", type: "textarea", wide: true },
  { name: "notes", label: "Notes", type: "textarea", wide: true },
];
const columns = [
  { key: "name", label: "Site", render: (row) => <span className="primary-cell">{row.name}</span> },
  { key: "customer_id", label: "Customer", render: (row, related) => related.customers?.[row.customer_id]?.name || "Unknown" },
  { key: "address", label: "Address", render: (row) => <span className="secondary-text">{row.address || "—"}</span> },
  { key: "notes", label: "Notes", render: (row) => <span className="secondary-text">{row.notes || "—"}</span> },
];

export default function SitesPage() {
  return (
    <CrudScreen
      columns={columns}
      dependencies={dependencies}
      description="Create and maintain physical or logical locations for each customer."
      emptyValues={{ customer_id: "", name: "", address: "", notes: "" }}
      endpoint="/sites"
      eyebrow="Locations"
      fields={fields}
      preparePayload={(form) => ({ ...form, address: form.address || null, notes: form.notes || null })}
      title="Sites"
    />
  );
}
