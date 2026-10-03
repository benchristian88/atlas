"use client";

import { Button, IconButton } from "./button";

import { useCallback, useEffect, useState } from "react";
import { AccessDenied } from "./access-denied";
import { useAuth } from "./auth-context";
import { PageHeader } from "./page-header";
import { KnowledgeProfileTable } from "./knowledge-profile-table";
import { apiRequest } from "../lib/api";

const SERVICE_FIELDS = [
  "name", "service_type_id", "purpose", "description", "lifecycle_status",
  "operational_status", "criticality_level_id", "rto_minutes", "rpo_minutes",
  "owner_name", "technical_contact", "support_group", "recovery_notes",
  "runbook_url", "documentation_url", "backup_notes", "notes",
];
const RULE_TYPES = [
  ["service_field_present", "Service field is present"],
  ["service_asset_dependency_exists", "Asset dependency exists"],
  ["service_dependency_exists", "Service dependency exists"],
  ["service_business_function_exists", "Business Function link exists"],
  ["one_of", "Either of two Service fields is present"],
  ["criticality_rank", "Criticality rank is at least a value"],
];
const EMPTY = {
  key: "", name: "", description: "", requirement_level: "required",
  severity: "medium", rule_type: "service_field_present", field: "purpose",
  alternative_field: "description", minimum: "1", minimum_rank: "75",
  applicable_criticality_rank_min: "", remediation_hint: "", active: true,
  sort_order: "100",
};

function configFor(form) {
  let config;
  if (form.rule_type === "service_field_present") config = { field: form.field };
  else if (["service_asset_dependency_exists", "service_dependency_exists", "service_business_function_exists"].includes(form.rule_type)) config = { minimum: Number(form.minimum) };
  else if (form.rule_type === "one_of") config = { rules: [
    { rule_type: "service_field_present", rule_config: { field: form.field } },
    { rule_type: "service_field_present", rule_config: { field: form.alternative_field } },
  ] };
  else config = { minimum_rank: Number(form.minimum_rank) };
  if (form.applicable_criticality_rank_min !== "") config.applicable_criticality_rank_min = Number(form.applicable_criticality_rank_min);
  return config;
}

function formFrom(item) {
  const config = item.rule_config_json || {};
  return {
    ...EMPTY,
    ...item,
    field: config.field || config.rules?.[0]?.rule_config?.field || "purpose",
    alternative_field: config.rules?.[1]?.rule_config?.field || "description",
    minimum: String(config.minimum || 1),
    minimum_rank: String(config.minimum_rank || 75),
    applicable_criticality_rank_min: config.applicable_criticality_rank_min == null ? "" : String(config.applicable_criticality_rank_min),
    sort_order: String(item.sort_order),
  };
}

export function ServiceKnowledgeProfile({ typeId: id, globalScope = false }) {
  const { hasGlobalPermission } = useAuth();
  const [serviceType, setServiceType] = useState(null);
  const [requirements, setRequirements] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [validation, setValidation] = useState(null);
  const canManage = hasGlobalPermission("knowledge_requirements.manage");
  const canView = hasGlobalPermission("knowledge_requirements.view") && (!globalScope || canManage);

  const load = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    setError("");
    try {
      const [types, rules] = await Promise.all([
        apiRequest("/service-types"),
        apiRequest(globalScope ? "/knowledge-requirements?entity_type=service" : `/service-types/${id}/knowledge-requirements`),
      ]);
      setServiceType(types.find((item) => item.id === id));
      setRequirements(rules);
    } catch (requestError) {
      setError(requestError.message || "Atlas could not load this Service knowledge profile.");
    } finally {
      setLoading(false);
    }
  }, [canView, globalScope, id]);
  useEffect(() => { load(); }, [load]);

  if (!canView) return <AccessDenied />;
  function update(name, value) { setForm((current) => ({ ...current, [name]: value })); setValidation(null); }
  function begin(item = null, duplicate = false) {
    setEditing(duplicate ? null : item);
    setValidation(null);
    setNotice("");
    setForm(item ? { ...formFrom(item), ...(duplicate ? { key: `${item.key}_copy_${Date.now().toString().slice(-4)}`, name: `${item.name} copy` } : {}) } : { ...EMPTY, key: `${serviceType?.key || "service"}_${Date.now().toString().slice(-6)}` });
    setShowForm(true);
  }
  async function save(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const payload = {
      key: form.key,
      name: form.name,
      description: form.description || null,
      entity_type: "service",
      service_type_id: globalScope ? null : id,
      requirement_level: form.requirement_level,
      severity: form.severity,
      rule_type: form.rule_type,
      rule_config_json: configFor(form),
      active: form.active,
      sort_order: Number(form.sort_order),
      remediation_hint: form.remediation_hint || null,
    };
    try {
      const body = editing ? Object.fromEntries(Object.entries(payload).filter(([key]) => !["key", "service_type_id"].includes(key))) : payload;
      await apiRequest(editing ? `/knowledge-requirements/${editing.id}` : globalScope ? "/knowledge-requirements" : `/service-types/${id}/knowledge-requirements`, { method: editing ? "PATCH" : "POST", body: JSON.stringify(body) });
      setShowForm(false);
      setEditing(null);
      setNotice("Requirement saved and affected Services were reevaluated.");
      await load();
    } catch (requestError) {
      setError(requestError.details?.errors?.join(" · ") || requestError.message || "Atlas could not save this requirement.");
    } finally {
      setSaving(false);
    }
  }
  async function validate() {
    try {
      setValidation(await apiRequest("/knowledge-requirements/validate", { method: "POST", body: JSON.stringify({ rule_type: form.rule_type, rule_config_json: configFor(form) }) }));
    } catch (requestError) {
      setValidation({ valid: false, errors: [requestError.message], interpretation: "Invalid rule" });
    }
  }
  async function toggle(item) {
    try { await apiRequest(`/knowledge-requirements/${item.id}/${item.active ? "deactivate" : "activate"}`, { method: "POST" }); await load(); }
    catch (requestError) { setError(requestError.message); }
  }
  async function remove(item) {
    if (!window.confirm(`Delete “${item.name}”? Requirements with gap history can only be deactivated.`)) return;
    try { await apiRequest(`/knowledge-requirements/${item.id}`, { method: "DELETE" }); await load(); }
    catch (requestError) { setError(requestError.message); }
  }

  const dependencyRule = form.rule_type.endsWith("_exists");
  const fieldRule = form.rule_type === "service_field_present" || form.rule_type === "one_of";
  return <>
    <PageHeader eyebrow="Reference Data · Service types" title={globalScope ? "Global Service requirements" : `${serviceType?.name || "Service type"} knowledge profile`} description={globalScope ? "Baseline knowledge expected for every Service." : "Define the operational knowledge Atlas expects for this Service type. Global Service requirements apply to every Service Type; type-specific requirements apply only to this type."} actions={<>{canManage && <Button variant="primary" onClick={() => begin()} type="button">Add requirement</Button>}</>} />
    {error && <div className="error-banner" role="alert">{error}</div>}
    {notice && <div className="success-banner" role="status">{notice}</div>}
    {showForm && <section className="form-card">
      <div className="form-card-header"><h2>{editing ? "Edit" : "Add"} Service requirement</h2><IconButton onClick={() => setShowForm(false)} type="button" label="Close form" icon="close" /></div>
      <form onSubmit={save}><div className="form-grid">
        <label className="field"><span>Key *</span><input disabled={Boolean(editing)} onChange={(event) => update("key", event.target.value)} pattern="[a-z][a-z0-9_]+" required value={form.key} /></label>
        <label className="field"><span>Name *</span><input onChange={(event) => update("name", event.target.value)} required value={form.name} /></label>
        <label className="field"><span>Level</span><select onChange={(event) => update("requirement_level", event.target.value)} value={form.requirement_level}><option value="required">Required</option><option value="conditional">Conditional</option><option value="recommended">Recommended</option></select></label>
        <label className="field"><span>Severity</span><select onChange={(event) => update("severity", event.target.value)} value={form.severity}><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label>
        <label className="field field-wide"><span>Rule</span><select onChange={(event) => update("rule_type", event.target.value)} value={form.rule_type}>{RULE_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        {fieldRule && <label className="field"><span>Service field</span><select onChange={(event) => update("field", event.target.value)} value={form.field}>{SERVICE_FIELDS.map((field) => <option key={field}>{field}</option>)}</select></label>}
        {form.rule_type === "one_of" && <label className="field"><span>Alternative field</span><select onChange={(event) => update("alternative_field", event.target.value)} value={form.alternative_field}>{SERVICE_FIELDS.map((field) => <option key={field}>{field}</option>)}</select></label>}
        {dependencyRule && <label className="field"><span>Minimum active links</span><input min="1" onChange={(event) => update("minimum", event.target.value)} required type="number" value={form.minimum} /></label>}
        {form.rule_type === "criticality_rank" && <label className="field"><span>Minimum rank</span><input min="0" onChange={(event) => update("minimum_rank", event.target.value)} required type="number" value={form.minimum_rank} /></label>}
        {form.rule_type !== "criticality_rank" && <label className="field"><span>Only at criticality rank (optional)</span><input min="0" onChange={(event) => update("applicable_criticality_rank_min", event.target.value)} placeholder="75 for High and Critical" type="number" value={form.applicable_criticality_rank_min} /></label>}
        <label className="field field-wide"><span>Description</span><textarea onChange={(event) => update("description", event.target.value)} value={form.description} /></label>
        <label className="field field-wide"><span>Remediation hint</span><textarea onChange={(event) => update("remediation_hint", event.target.value)} value={form.remediation_hint} /></label>
        <label className="field"><span>Sort order</span><input min="0" onChange={(event) => update("sort_order", event.target.value)} type="number" value={form.sort_order} /></label>
        <label className="field checkbox-field"><input checked={form.active} onChange={(event) => update("active", event.target.checked)} type="checkbox" /><span>Active</span></label>
      </div>
      {validation && <div className={validation.valid ? "success-banner" : "error-banner"} role="status"><strong>{validation.interpretation}</strong>{validation.errors?.map((message) => <span key={message}>{message}</span>)}</div>}
      <p className="warning-banner">Changing this requirement may create or resolve gaps on {globalScope ? "all Services" : `${editing ? editing.affected_asset_count : serviceType?.in_use_count || 0} affected Services`}.</p>
      <div className="form-actions"><Button variant="secondary" onClick={() => setShowForm(false)} type="button">Cancel</Button><Button variant="secondary" onClick={validate} type="button">Validate configuration</Button><Button variant="primary" disabled={saving} type="submit">{saving ? "Saving…" : "Save requirement"}</Button></div>
      </form>
    </section>}
    <KnowledgeProfileTable requirements={requirements} entityLabel="Service" typeId={id} loading={loading} canManage={canManage} globalScope={globalScope} onRefresh={load} onEdit={begin} onToggle={toggle} onRemove={remove} />
  </>;
}
