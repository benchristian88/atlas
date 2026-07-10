"use client";

import { CrudScreen } from "../../components/crud-screen";
import { StatusBadge } from "../../components/status-badge";

const dependencies = [
  { key: "customers", endpoint: "/customers" },
  { key: "sites", endpoint: "/sites" },
];
const fields = [
  { name: "customer_id", label: "Customer", type: "select", optionsKey: "customers", required: true, placeholder: "Select a customer" },
  { name: "site_id", label: "Site", type: "select", optionsKey: "sites", optionLabel: (site, related) => `${site.name} — ${related.customers?.[site.customer_id]?.name || "Unknown"}` },
  { name: "name", label: "Name", required: true },
  { name: "asset_type", label: "Asset type", required: true, placeholder: "server, switch, firewall…" },
  { name: "vendor", label: "Vendor" },
  { name: "status", label: "Status", type: "select", required: true, options: [
    { value: "active", label: "Active" }, { value: "stale", label: "Stale" }, { value: "unknown", label: "Unknown" },
  ] },
  { name: "description", label: "Description", type: "textarea", wide: true },
  { name: "metadata", label: "Metadata (JSON)", type: "textarea", rows: 5, wide: true, help: "Optional structured facts, entered as a JSON object." },
];
const columns = [
  { key: "name", label: "Asset", render: (row) => <span className="primary-cell mono">{row.name}</span> },
  { key: "asset_type", label: "Type" },
  { key: "customer_id", label: "Customer", render: (row, related) => related.customers?.[row.customer_id]?.name || "Unknown" },
  { key: "site_id", label: "Site", render: (row, related) => row.site_id ? related.sites?.[row.site_id]?.name || "Unknown" : "—" },
  { key: "vendor", label: "Vendor", render: (row) => <span className="secondary-text">{row.vendor || "—"}</span> },
  { key: "status", label: "Status", render: (row) => <StatusBadge status={row.status} /> },
];

function preparePayload(form) {
  let metadata = {};
  if (form.metadata.trim()) {
    metadata = JSON.parse(form.metadata);
    if (Array.isArray(metadata) || metadata === null || typeof metadata !== "object") {
      throw new Error("Metadata must be a JSON object.");
    }
  }
  return {
    ...form,
    site_id: form.site_id || null,
    vendor: form.vendor || null,
    description: form.description || null,
    metadata,
  };
}

export default function AssetsPage() {
  return (
    <CrudScreen
      columns={columns}
      dependencies={dependencies}
      description="Create and maintain manually entered infrastructure assets. Discovered assets remain read-only here."
      emptyValues={{ customer_id: "", site_id: "", name: "", asset_type: "", vendor: "", status: "active", description: "", metadata: "{}" }}
      endpoint="/manual-assets"
      eyebrow="Inventory"
      fields={fields}
      preparePayload={preparePayload}
      title="Manual assets"
    />
  );
}
