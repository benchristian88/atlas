"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AccessDenied } from "../../../../components/access-denied";
import { useAuth } from "../../../../components/auth-context";
import { PageHeader } from "../../../../components/page-header";
import { ServiceForm } from "../../../../components/service-form";
import { useWorkspaceContext } from "../../../../components/workspace-context";
import { apiRequest } from "../../../../lib/api";

export default function EditServicePage({ params }) {
  const { id } = use(params); const router = useRouter(); const workspace = useWorkspaceContext(); const { hasPermission } = useAuth();
  const [service, setService] = useState(null); const [types, setTypes] = useState([]); const [levels, setLevels] = useState([]); const [loading, setLoading] = useState(true); const [saving, setSaving] = useState(false); const [error, setError] = useState("");
  const canEdit = hasPermission("services.edit");
  useEffect(() => { if (!canEdit) return; Promise.all([apiRequest(`/services/${id}`), apiRequest("/service-types"), apiRequest("/criticality-levels")]).then(([item, serviceTypes, criticality]) => { setService(item); setTypes(serviceTypes); setLevels(criticality); }).catch((requestError) => setError(requestError.message)).finally(() => setLoading(false)); }, [canEdit, id]);
  if (!canEdit) return <AccessDenied />;
  async function save(payload) { setSaving(true); setError(""); try { await apiRequest(`/services/${id}`, { method: "PATCH", body: JSON.stringify(payload) }); router.replace(`/services/${id}`); } catch (requestError) { setError(requestError.message || "Atlas could not update this Service."); setSaving(false); } }
  return <><PageHeader eyebrow="Services" title={`Edit ${service?.name || "Service"}`} description="Update operational identity, ownership, recovery targets, and documentation." />{error && <div className="error-banner" role="alert">{error}</div>}{loading ? <div className="status-banner">Loading Service…</div> : service && <section className="form-card"><ServiceForm context={{ customerId: workspace.customerId, siteId: workspace.siteId }} criticalityLevels={levels} customers={workspace.customers} onCancel={() => router.push(`/services/${id}`)} onSubmit={save} saving={saving} service={service} serviceTypes={types} sites={workspace.sites} /></section>}</>;
}
