"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AccessDenied } from "../../../components/access-denied";
import { useAuth } from "../../../components/auth-context";
import { PageHeader } from "../../../components/page-header";
import { ServiceForm } from "../../../components/service-form";
import { useWorkspaceContext } from "../../../components/workspace-context";
import { apiRequest } from "../../../lib/api";

export default function NewServicePage() {
  const router = useRouter(); const workspace = useWorkspaceContext(); const { hasPermissionInContext } = useAuth();
  const [types, setTypes] = useState([]); const [levels, setLevels] = useState([]); const [loading, setLoading] = useState(true); const [saving, setSaving] = useState(false); const [error, setError] = useState("");
  const canCreate = hasPermissionInContext("services.create", workspace.customerId, workspace.siteId);
  useEffect(() => { if (!canCreate) return; Promise.all([apiRequest("/service-types?active_only=true"), apiRequest("/criticality-levels?active_only=true")]).then(([serviceTypes, criticality]) => { setTypes(serviceTypes); setLevels(criticality); }).catch((requestError) => setError(requestError.message)).finally(() => setLoading(false)); }, [canCreate]);
  if (!canCreate) return <AccessDenied />;
  async function create(payload) { setSaving(true); setError(""); try { const item = await apiRequest("/services", { method: "POST", body: JSON.stringify(payload) }); const created = new URLSearchParams({ created: "true", required_gaps: String(item.required_gap_count || 0), recommended_gaps: String(item.recommended_gap_count || 0) }); router.replace(`/services/${item.id}?${created}`); } catch (requestError) { setError(requestError.message || "Atlas could not create this Service."); setSaving(false); } }
  return <><PageHeader eyebrow="Services" title="Add Service" description="Describe an operational capability before linking its infrastructure and upstream dependencies." />{error && <div className="error-banner" role="alert">{error}</div>}{loading ? <div className="status-banner">Loading Service options…</div> : <section className="form-card"><ServiceForm context={{ customerId: workspace.customerId, siteId: workspace.siteId }} criticalityLevels={levels} customers={workspace.customers} onCancel={() => router.push("/services")} onSubmit={create} saving={saving} serviceTypes={types} sites={workspace.sites} /></section>}</>;
}
