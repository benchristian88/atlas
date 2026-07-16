"use client";

import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { CrudScreen } from "../../components/crud-screen";
import { useWorkspaceContext } from "../../components/workspace-context";
import { NETWORK_TYPES, taxonomyLabel } from "../../lib/taxonomy";

const dependencies = [
  { key: "customers", endpoint: "/customers" },
  { key: "sites", endpoint: "/sites" },
];

const fields = [
  { name: "customer_id", label: "Customer", type: "select", optionsKey: "customers", required: true, placeholder: "Select a customer", clearFields: ["site_id"] },
  { name: "site_id", label: "Site", type: "select", optionsKey: "sites", optionsFilter: (site, form) => !form.customer_id || site.customer_id === form.customer_id, placeholder: "All customer sites" },
  { name: "name", label: "Name", required: true },
  { name: "network_type", label: "Network type", type: "select", required: true, options: NETWORK_TYPES.map((value) => ({ value, label: taxonomyLabel(value) })) },
  { name: "vlan_id", label: "VLAN ID", type: "number", placeholder: "1-4094" },
  { name: "cidr", label: "CIDR", placeholder: "192.168.5.0/24" },
  { name: "gateway", label: "Gateway", placeholder: "192.168.5.1" },
  { name: "purpose", label: "Purpose" },
  { name: "zone", label: "Zone", placeholder: "trusted, guest, dmz…" },
  { name: "notes", label: "Notes", type: "textarea", wide: true },
];

const columns = [
  { key: "name", label: "Network", render: (row) => <span className="primary-cell">{row.name}</span> },
  { key: "network_type", label: "Type", render: (row) => taxonomyLabel(row.network_type) },
  { key: "vlan_id", label: "VLAN", render: (row) => row.vlan_id ?? "—" },
  { key: "cidr", label: "CIDR", render: (row) => <span className="mono">{row.cidr || "—"}</span> },
  { key: "gateway", label: "Gateway", render: (row) => <span className="mono">{row.gateway || "—"}</span> },
  { key: "customer_id", label: "Customer", render: (row, related) => related.customers?.[row.customer_id]?.name || "Unknown" },
  { key: "site_id", label: "Site", render: (row, related) => row.site_id ? related.sites?.[row.site_id]?.name || "Unknown" : "All sites" },
];

export default function NetworksPage() {
  const {
    hasPermission,
    hasPermissionForObject,
    hasPermissionInContext,
  } = useAuth();
  const { customerId, reloadKey, siteId } = useWorkspaceContext();
  if (!hasPermissionInContext("networks.view", customerId, siteId)) return <AccessDenied />;
  const availableDependencies = dependencies.filter((dependency) => (
    dependency.key === "customers"
      ? hasPermission("customers.view")
      : hasPermission("sites.view")
  ));
  return <CrudScreen
    canCreate={hasPermissionInContext("networks.create", customerId, siteId)}
    canDelete={(row) => hasPermissionForObject("networks.delete", row.customer_id, row.site_id)}
    canEdit={(row) => hasPermissionForObject("networks.edit", row.customer_id, row.site_id)}
    columns={columns}
    contextReloadKey={reloadKey}
    dependencies={availableDependencies}
    description="Define LANs, VLANs, routed zones, overlays, and other network segments."
    emptyValues={{ customer_id: customerId || "", site_id: siteId || "", name: "", network_type: "vlan", vlan_id: "", cidr: "", gateway: "", purpose: "", zone: "", notes: "" }}
    endpoint="/networks"
    eyebrow="Connectivity"
    fields={fields.map((field) => (
      field.name === "customer_id" && customerId
        ? { ...field, disabled: true }
        : field.name === "site_id" && siteId ? { ...field, disabled: true } : field
    ))}
    preparePayload={(form) => ({
      ...form,
      site_id: form.site_id || null,
      vlan_id: form.vlan_id === "" ? null : Number(form.vlan_id),
      cidr: form.cidr || null,
      gateway: form.gateway || null,
      purpose: form.purpose || null,
      zone: form.zone || null,
      notes: form.notes || null,
    })}
    title="Networks"
  />;
}
