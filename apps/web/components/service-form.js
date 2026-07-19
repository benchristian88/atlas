"use client";

import { useMemo, useState } from "react";
import { DURATION_UNITS, durationToMinutes, minutesToDuration } from "../lib/duration.mjs";

function initialState(service, context) {
  const rto = minutesToDuration(service?.rto_minutes);
  const rpo = minutesToDuration(service?.rpo_minutes);
  return {
    customer_id: service?.customer_id || context.customerId || "",
    site_id: service?.site_id || context.siteId || "",
    name: service?.name || "", slug: service?.slug || "",
    service_type_id: service?.service_type_id || "",
    criticality_level_id: service?.criticality_level_id || "",
    purpose: service?.purpose || "", description: service?.description || "",
    lifecycle_status: service?.lifecycle_status || "active",
    operational_status: service?.operational_status || "unknown",
    owner_name: service?.owner_name || "", technical_contact: service?.technical_contact || "",
    support_group: service?.support_group || "", documentation_url: service?.documentation_url || "",
    runbook_url: service?.runbook_url || "", backup_notes: service?.backup_notes || "",
    recovery_notes: service?.recovery_notes || "", notes: service?.notes || "",
    rto_value: rto.value, rto_unit: rto.unit, rpo_value: rpo.value, rpo_unit: rpo.unit,
  };
}

export function ServiceForm({ service = null, serviceTypes, criticalityLevels, customers, sites, context, onSubmit, onCancel, saving }) {
  const [form, setForm] = useState(() => initialState(service, context));
  const matchingSites = useMemo(() => sites.filter((site) => site.customer_id === form.customer_id), [form.customer_id, sites]);
  const criticality = criticalityLevels.find((item) => item.id === form.criticality_level_id);
  const update = (name, value) => setForm((current) => ({ ...current, [name]: value }));
  const text = (name, label, options = {}) => <label className={options.wide ? "field field-wide" : "field"}><span>{label}{options.required ? " *" : ""}</span>{options.textarea ? <textarea rows={options.rows || 3} value={form[name]} onChange={(event) => update(name, event.target.value)} /> : <input type={options.type || "text"} required={options.required} value={form[name]} onChange={(event) => update(name, event.target.value)} />}{options.help && <small>{options.help}</small>}</label>;
  function duration(prefix, label, suggested) {
    return <fieldset className="field duration-field"><legend>{label}</legend><div className="duration-control"><input min="0" step="1" type="number" value={form[`${prefix}_value`]} onChange={(event) => update(`${prefix}_value`, event.target.value)} /><select value={form[`${prefix}_unit`]} onChange={(event) => update(`${prefix}_unit`, event.target.value)}>{DURATION_UNITS.map((unit) => <option key={unit.value} value={unit.value}>{unit.label}</option>)}</select></div><small>Explicit target{suggested == null ? "" : ` · suggested default ${suggested} minutes`}</small></fieldset>;
  }
  function submit(event) {
    event.preventDefault();
    onSubmit({
      ...(!service ? { customer_id: form.customer_id } : {}),
      site_id: form.site_id || null, name: form.name.trim(), slug: form.slug.trim() || null,
      service_type_id: form.service_type_id, criticality_level_id: form.criticality_level_id,
      purpose: form.purpose.trim() || null, description: form.description.trim() || null,
      lifecycle_status: form.lifecycle_status, operational_status: form.operational_status,
      owner_name: form.owner_name.trim() || null, technical_contact: form.technical_contact.trim() || null,
      support_group: form.support_group.trim() || null, documentation_url: form.documentation_url.trim() || null,
      runbook_url: form.runbook_url.trim() || null,
      rto_minutes: durationToMinutes(form.rto_value, form.rto_unit), rpo_minutes: durationToMinutes(form.rpo_value, form.rpo_unit),
      backup_notes: form.backup_notes.trim() || null, recovery_notes: form.recovery_notes.trim() || null, notes: form.notes.trim() || null,
    });
  }
  return <form className="resource-form" onSubmit={submit}>
    <div className="form-grid">
      {!service && <label className="field"><span>Customer *</span><select required disabled={Boolean(context.customerId)} value={form.customer_id} onChange={(event) => setForm((current) => ({ ...current, customer_id: event.target.value, site_id: "" }))}><option value="">Choose customer</option>{customers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
      <label className="field"><span>Site</span><select disabled={Boolean(context.siteId)} value={form.site_id} onChange={(event) => update("site_id", event.target.value)}><option value="">Customer-wide</option>{matchingSites.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      {text("name", "Service name", { required: true })}{text("slug", "Slug", { help: "Leave blank to generate from the name." })}
      <label className="field"><span>Service type *</span><select required value={form.service_type_id} onChange={(event) => update("service_type_id", event.target.value)}><option value="">Choose type</option>{serviceTypes.filter((item) => item.active || item.id === service?.service_type_id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label className="field"><span>Criticality *</span><select required value={form.criticality_level_id} onChange={(event) => update("criticality_level_id", event.target.value)}><option value="">Choose criticality</option>{criticalityLevels.filter((item) => item.active || item.id === service?.criticality_level_id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      {text("purpose", "Purpose", { textarea: true, wide: true, rows: 2 })}{text("description", "Description", { textarea: true, wide: true })}
      <label className="field"><span>Lifecycle status</span><select value={form.lifecycle_status} onChange={(event) => update("lifecycle_status", event.target.value)}><option value="planned">Planned</option><option value="active">Active</option><option value="deprecated">Deprecated</option><option value="retired">Retired</option></select></label>
      <label className="field"><span>Operational status</span><select value={form.operational_status} onChange={(event) => update("operational_status", event.target.value)}><option value="unknown">Unknown</option><option value="operational">Operational</option><option value="degraded">Degraded</option><option value="outage">Outage</option><option value="maintenance">Maintenance</option></select></label>
      {text("owner_name", "Owner")}{text("technical_contact", "Technical contact")}{text("support_group", "Support group")}
      {duration("rto", "RTO", criticality?.default_rto_minutes)}{duration("rpo", "RPO", criticality?.default_rpo_minutes)}
      {text("runbook_url", "Runbook URL", { type: "url" })}{text("documentation_url", "Documentation URL", { type: "url" })}
      {text("recovery_notes", "Recovery notes", { textarea: true, wide: true })}{text("backup_notes", "Backup notes", { textarea: true, wide: true })}{text("notes", "Notes", { textarea: true, wide: true })}
    </div>
    <div className="form-actions"><button className="button button-secondary" disabled={saving} onClick={onCancel} type="button">Cancel</button><button className="button button-primary" disabled={saving} type="submit">{saving ? "Saving…" : service ? "Save Service" : "Create Service"}</button></div>
  </form>;
}
