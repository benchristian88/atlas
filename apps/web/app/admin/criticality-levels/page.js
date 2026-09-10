"use client";

import { AccessDenied } from "../../../components/access-denied";
import { useAuth } from "../../../components/auth-context";
import { CrudScreen } from "../../../components/crud-screen";

const fields = [
  { name: "key", label: "Key", createOnly: true, required: true, placeholder: "critical" },
  { name: "name", label: "Name", required: true },
  { name: "rank", label: "Rank", type: "number", required: true, help: "Higher ranks sort first and can drive conditional knowledge requirements." },
  { name: "default_rto_minutes", label: "Suggested RTO (minutes)", type: "number" },
  { name: "default_rpo_minutes", label: "Suggested RPO (minutes)", type: "number" },
  { name: "sort_order", label: "Sort order", type: "number", required: true },
  { name: "active", label: "Available for new Services", type: "checkbox" },
  { name: "description", label: "Description", type: "textarea", wide: true },
];
const columns = [
  { key: "name", label: "Criticality", render: (row) => <span className="primary-cell">{row.name}</span> },
  { key: "rank", label: "Rank", render: (row) => row.rank },
  { key: "default_rto_minutes", label: "Suggested RTO", render: (row) => row.default_rto_minutes == null ? "—" : `${row.default_rto_minutes} min` },
  { key: "default_rpo_minutes", label: "Suggested RPO", render: (row) => row.default_rpo_minutes == null ? "—" : `${row.default_rpo_minutes} min` },
  { key: "active", label: "State", render: (row) => row.active ? "Active" : "Inactive" },
  { key: "in_use_count", label: "Services", render: (row) => row.in_use_count },
];

export default function CriticalityLevelsAdminPage() {
  const { hasGlobalPermission, hasPermission } = useAuth();
  if (!hasPermission("criticality_levels.view")) return <AccessDenied />;
  const manage = hasGlobalPermission("criticality_levels.manage");
  return <CrudScreen
    canCreate={manage} canDelete={false} canEdit={manage}
    columns={columns} description="Rank Service importance and provide recovery suggestions. Explicit Service targets are never overwritten."
    emptyValues={{ key: "", name: "", rank: "50", default_rto_minutes: "", default_rpo_minutes: "", sort_order: "100", active: true, description: "" }}
    endpoint="/criticality-levels" eyebrow="Reference Data" fields={fields}
    preparePayload={(form, editingId) => ({ ...(!editingId ? { key: form.key } : {}), name: form.name, rank: Number(form.rank), default_rto_minutes: form.default_rto_minutes === "" ? null : Number(form.default_rto_minutes), default_rpo_minutes: form.default_rpo_minutes === "" ? null : Number(form.default_rpo_minutes), sort_order: Number(form.sort_order), active: form.active, description: form.description || null })}
    title="Criticality levels"
  />;
}
