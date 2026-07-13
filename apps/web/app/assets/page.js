"use client";

import Link from "next/link";
import { CrudScreen } from "../../components/crud-screen";
import { StatusBadge } from "../../components/status-badge";
import { ASSET_TYPES, taxonomyLabel } from "../../lib/taxonomy";

const dependencies = [
  { key: "customers", endpoint: "/customers" },
  { key: "sites", endpoint: "/sites" },
];
const fields = [
  { name: "customer_id", label: "Customer", type: "select", optionsKey: "customers", required: true, placeholder: "Select a customer", clearFields: ["site_id"] },
  { name: "site_id", label: "Site", type: "select", optionsKey: "sites", optionsFilter: (site, form) => !form.customer_id || site.customer_id === form.customer_id, optionLabel: (site, related) => `${site.name} — ${related.customers?.[site.customer_id]?.name || "Unknown"}` },
  { name: "name", label: "Name", required: true },
  { name: "asset_type", label: "Asset type", type: "select", required: true, placeholder: "Select an asset type", options: ASSET_TYPES.map((value) => ({ value, label: taxonomyLabel(value) })) },
  { name: "vendor", label: "Vendor" },
  { name: "model", label: "Model" },
  { name: "hostname", label: "Hostname" },
  { name: "ip_address", label: "IP address" },
  { name: "management_url", label: "Management URL", type: "url", valueFromRecord: (record) => record.metadata?.management_url || "" },
  { name: "tags", label: "Tags", placeholder: "homelab, production, critical", valueFromRecord: (record) => (record.metadata?.tags || []).join(", ") },
  { name: "status", label: "Status", type: "select", required: true, options: [
    { value: "active", label: "Active" }, { value: "stale", label: "Stale" }, { value: "unknown", label: "Unknown" },
  ] },
  { name: "description", label: "Description", type: "textarea", wide: true },
  { name: "metadata", label: "Metadata (JSON)", type: "textarea", rows: 5, wide: true, help: "Optional structured facts, entered as a JSON object." },
];
const columns = [
  { key: "name", label: "Asset", render: (row) => <Link className="primary-cell mono card-link" href={`/assets/${row.id}`}>{row.name}</Link> },
  { key: "asset_type", label: "Type" },
  { key: "customer_id", label: "Customer", render: (row, related) => related.customers?.[row.customer_id]?.name || "Unknown" },
  { key: "site_id", label: "Site", render: (row, related) => row.site_id ? related.sites?.[row.site_id]?.name || "Unknown" : "—" },
  { key: "hostname", label: "Hostname", render: (row) => <span className="mono secondary-text">{row.hostname || "—"}</span> },
  { key: "ip_address", label: "IP address", render: (row) => <span className="mono secondary-text">{row.ip_address || "—"}</span> },
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
    customer_id: form.customer_id,
    site_id: form.site_id || null,
    name: form.name,
    asset_type: form.asset_type,
    status: form.status,
    vendor: form.vendor || null,
    model: form.model || null,
    hostname: form.hostname || null,
    ip_address: form.ip_address || null,
    description: form.description || null,
    metadata: {
      ...metadata,
      ...(form.management_url ? { management_url: form.management_url } : {}),
      ...(form.tags ? { tags: form.tags.split(",").map((tag) => tag.trim()).filter(Boolean) } : {}),
    },
  };
}

export default function AssetsPage() {
  return (
    <CrudScreen
      columns={columns}
      dependencies={dependencies}
      description="Create and maintain infrastructure assets, addressing details, metadata, and topology roles."
      emptyValues={{ customer_id: "", site_id: "", name: "", asset_type: "", vendor: "", model: "", hostname: "", ip_address: "", management_url: "", tags: "", status: "active", description: "", metadata: "{}" }}
      endpoint="/assets"
      eyebrow="Inventory"
      fields={fields}
      preparePayload={preparePayload}
      title="Manual assets"
    />
  );
}
