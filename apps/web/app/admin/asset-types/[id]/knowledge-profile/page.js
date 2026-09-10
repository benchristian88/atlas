"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AccessDenied } from "../../../../../components/access-denied";
import { useAuth } from "../../../../../components/auth-context";
import { PageHeader } from "../../../../../components/page-header";
import { StatusBadge } from "../../../../../components/status-badge";
import { apiRequest } from "../../../../../lib/api";

const CORE_FIELDS = ["name", "asset_type", "hostname", "ip_address", "status", "vendor", "model", "description", "source"];
const RULE_TYPES = [
  ["field_present", "Asset field is present"], ["field_value_in", "Asset field has an allowed value"],
  ["custom_field_present", "Custom field is present"], ["custom_field_value_in", "Custom field has an allowed value"],
  ["interface_exists", "Interface exists"], ["interface_has_ip", "Interface has an IP address"],
  ["minimum_interface_count", "Minimum interface count"], ["relationship_exists", "Relationship exists"],
  ["relationship_target_type", "Relationship counterpart has an allowed type"], ["minimum_relationship_count", "Minimum relationship count"],
  ["one_of", "Any one of two fields is present"], ["explicit_state_or_exception", "Explicit state or exception"],
  ["freshness_within_days", "Knowledge was observed recently"],
  ["owner_exists", "Owner exists (available after the ownership model)", true],
];
const EMPTY = {
  key: "", name: "", description: "", requirement_level: "required", severity: "medium",
  rule_type: "field_present", field: "hostname", values: "", custom_field_id: "",
  relationship_type_ids: [], target_asset_type_ids: [], direction: "outgoing", minimum: "1",
  interface_role: "", allow_any_role: true, require_primary: false, address_family: "either",
  predicate: "", maximum_age_days: "30", alternative_field: "ip_address",
  unless_field_id: "", unless_values: "", remediation_hint: "", active: true, sort_order: "100",
};

function values(text) { return text.split(",").map((item) => item.trim()).filter(Boolean); }

function configFor(form) {
  const minimum = Number(form.minimum || 1);
  let config = {};
  if (form.rule_type === "field_present") config = { field: form.field };
  if (["field_value_in", "explicit_state_or_exception"].includes(form.rule_type)) config = { field: form.field, values: values(form.values) };
  if (form.rule_type === "custom_field_present") config = { custom_field_definition_id: form.custom_field_id };
  if (form.rule_type === "custom_field_value_in") config = { custom_field_definition_id: form.custom_field_id, values: values(form.values) };
  if (["interface_exists", "minimum_interface_count"].includes(form.rule_type)) config = { minimum, interface_role: form.interface_role || undefined, allow_any_role: form.allow_any_role };
  if (form.rule_type === "interface_has_ip") config = { minimum, interface_role: form.interface_role || undefined, allow_any_role: form.allow_any_role, require_primary: form.require_primary, allowed_address_families: form.address_family === "either" ? ["ipv4", "ipv6"] : [form.address_family] };
  if (["relationship_exists", "relationship_target_type", "minimum_relationship_count"].includes(form.rule_type)) config = { relationship_type_ids: form.relationship_type_ids, allowed_target_asset_type_ids: form.target_asset_type_ids, direction: form.direction, minimum };
  if (form.rule_type === "one_of") config = { rules: [{ rule_type: "field_present", rule_config: { field: form.field } }, { rule_type: "field_present", rule_config: { field: form.alternative_field } }] };
  if (form.rule_type === "freshness_within_days") config = { predicate: form.predicate, maximum_age_days: Number(form.maximum_age_days) };
  if (form.unless_field_id && form.unless_values.trim()) config.unless = { rule_type: "custom_field_value_in", rule_config: { custom_field_definition_id: form.unless_field_id, values: values(form.unless_values) } };
  return config;
}

function formFrom(item) {
  const config = item.rule_config_json || {};
  return {
    ...EMPTY, ...item, sort_order: String(item.sort_order), field: config.field || "hostname",
    values: (config.values || []).join(", "), custom_field_id: config.custom_field_definition_id || "",
    relationship_type_ids: config.relationship_type_ids || [], target_asset_type_ids: config.allowed_target_asset_type_ids || [],
    direction: config.direction || "outgoing", minimum: String(config.minimum || 1), interface_role: config.interface_role || "",
    allow_any_role: config.allow_any_role ?? true, require_primary: config.require_primary || false,
    address_family: config.allowed_address_families?.length === 1 ? config.allowed_address_families[0] : "either",
    predicate: config.predicate || "", maximum_age_days: String(config.maximum_age_days || 30),
    alternative_field: config.rules?.[1]?.rule_config?.field || "ip_address",
    unless_field_id: config.unless?.rule_config?.custom_field_definition_id || "",
    unless_values: (config.unless?.rule_config?.values || []).join(", "),
  };
}

function MultiSelect({ children, label, onChange, required = false, value }) {
  return <label className="field"><span>{label}</span><select multiple onChange={(event) => onChange(Array.from(event.target.selectedOptions, (option) => option.value))} required={required} value={value}>{children}</select></label>;
}

export default function KnowledgeProfilePage() {
  const { id } = useParams();
  const { hasGlobalPermission, hasPermission } = useAuth();
  const [assetType, setAssetType] = useState(null); const [assetTypes, setAssetTypes] = useState([]);
  const [requirements, setRequirements] = useState([]); const [customFields, setCustomFields] = useState([]); const [relationshipTypes, setRelationshipTypes] = useState([]);
  const [form, setForm] = useState(EMPTY); const [editing, setEditing] = useState(null); const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true); const [saving, setSaving] = useState(false); const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [validation, setValidation] = useState(null);
  const canView = hasPermission("knowledge_requirements.view"); const canManage = hasGlobalPermission("knowledge_requirements.manage");

  const load = useCallback(async () => {
    if (!canView) return; setLoading(true); setError("");
    try {
      const [types, rules, custom, relations] = await Promise.all([
        apiRequest("/asset-types"), apiRequest(`/asset-types/${id}/knowledge-requirements`),
        hasPermission("custom_fields.view") ? apiRequest("/custom-fields") : Promise.resolve([]),
        hasPermission("relationship_types.view") ? apiRequest("/relationship-types") : Promise.resolve([]),
      ]);
      setAssetTypes(types); setAssetType(types.find((item) => item.id === id)); setRequirements(rules); setCustomFields(custom); setRelationshipTypes(relations);
    } catch (requestError) { setError(requestError.message || "Atlas could not load this knowledge profile."); }
    finally { setLoading(false); }
  }, [canView, hasPermission, id]);
  useEffect(() => { load(); }, [load]);
  const typeNames = useMemo(() => Object.fromEntries(assetTypes.map((item) => [item.id, item.name])), [assetTypes]);
  if (!canView) return <AccessDenied />;

  function update(name, value) { setForm((current) => ({ ...current, [name]: value })); setValidation(null); }
  function begin(item = null, duplicate = false) {
    setEditing(duplicate ? null : item); setValidation(null); setNotice("");
    setForm(item ? { ...formFrom(item), ...(duplicate ? { key: `${item.key}_copy_${Date.now().toString().slice(-4)}`, name: `${item.name} copy` } : {}) } : { ...EMPTY, key: `${assetType?.key || "asset"}_${Date.now().toString().slice(-6)}` });
    setShowForm(true);
  }
  async function save(event) {
    event.preventDefault(); setSaving(true); setError("");
    const payload = { key: form.key, name: form.name, description: form.description || null, entity_type: "asset", asset_type_id: id, requirement_level: form.requirement_level, severity: form.severity, rule_type: form.rule_type, rule_config_json: configFor(form), active: form.active, sort_order: Number(form.sort_order), remediation_hint: form.remediation_hint || null };
    try {
      const body = editing ? Object.fromEntries(Object.entries(payload).filter(([key]) => !["key", "asset_type_id"].includes(key))) : payload;
      await apiRequest(editing ? `/knowledge-requirements/${editing.id}` : `/asset-types/${id}/knowledge-requirements`, { method: editing ? "PATCH" : "POST", body: JSON.stringify(body) });
      setShowForm(false); setEditing(null); setNotice("Requirement saved and affected assets were reevaluated."); await load();
    } catch (requestError) { setError(requestError.details?.errors?.join(" · ") || requestError.message || "Atlas could not save this requirement."); }
    finally { setSaving(false); }
  }
  async function validate() { try { setValidation(await apiRequest("/knowledge-requirements/validate", { method: "POST", body: JSON.stringify({ rule_type: form.rule_type, rule_config_json: configFor(form) }) })); } catch (requestError) { setValidation({ valid: false, errors: [requestError.message], interpretation: "Invalid rule" }); } }
  async function toggle(item) { try { await apiRequest(`/knowledge-requirements/${item.id}/${item.active ? "deactivate" : "activate"}`, { method: "POST" }); await load(); } catch (requestError) { setError(requestError.message); } }
  async function remove(item) { if (!window.confirm(`Delete “${item.name}”? Requirements with gap history can only be deactivated.`)) return; try { await apiRequest(`/knowledge-requirements/${item.id}`, { method: "DELETE" }); await load(); } catch (requestError) { setError(requestError.message); } }
  async function reevaluate() { setSaving(true); try { const result = await apiRequest("/knowledge-completeness/evaluate-batch", { method: "POST", body: JSON.stringify({ asset_type_id: id, limit: 500 }) }); setNotice(`Re-evaluated ${result.evaluated_assets} assets (bounded batch).`); await load(); } catch (requestError) { setError(requestError.message); } finally { setSaving(false); } }

  const relationshipRule = form.rule_type.includes("relationship"); const interfaceRule = form.rule_type.startsWith("interface") || form.rule_type === "minimum_interface_count"; const customRule = form.rule_type.startsWith("custom_field");
  return <>
    <div className="page-heading-row"><PageHeader eyebrow="Reference Data · Asset types" title={`${assetType?.name || "Asset type"} knowledge profile`} description="Define the operational knowledge Atlas expects for this asset type. Global rules are shown alongside this type-specific profile." />{canManage && <div className="row-actions"><button className="button button-secondary" disabled={saving} onClick={reevaluate} type="button">Re-evaluate assets</button><button className="button button-primary" onClick={() => begin()} type="button">Add requirement</button></div>}</div>
    {error && <div className="error-banner" role="alert">{error}</div>}{notice && <div className="success-banner" role="status">{notice}</div>}
    {showForm && <section className="form-card"><div className="form-card-header"><h2>{editing ? "Edit" : "Add"} requirement</h2><button className="icon-button" onClick={() => setShowForm(false)} type="button">×</button></div><form onSubmit={save}><div className="form-grid">
      <label className="field"><span>Key *</span><input disabled={Boolean(editing)} onChange={(event) => update("key", event.target.value)} pattern="[a-z][a-z0-9_]+" required value={form.key} /></label>
      <label className="field"><span>Name *</span><input onChange={(event) => update("name", event.target.value)} required value={form.name} /></label>
      <label className="field"><span>Level</span><select onChange={(event) => update("requirement_level", event.target.value)} value={form.requirement_level}><option value="required">Required</option><option value="conditional">Conditional</option><option value="recommended">Recommended</option></select></label>
      <label className="field"><span>Severity</span><select onChange={(event) => update("severity", event.target.value)} value={form.severity}><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label>
      <label className="field field-wide"><span>Rule</span><select onChange={(event) => update("rule_type", event.target.value)} value={form.rule_type}>{RULE_TYPES.map(([value, name, disabled]) => <option disabled={disabled} key={value} value={value}>{name}</option>)}</select></label>
      {["field_present", "field_value_in", "explicit_state_or_exception", "one_of"].includes(form.rule_type) && <label className="field"><span>Asset field</span><select onChange={(event) => update("field", event.target.value)} value={form.field}>{CORE_FIELDS.map((item) => <option key={item}>{item}</option>)}</select></label>}
      {form.rule_type === "one_of" && <label className="field"><span>Alternative field</span><select onChange={(event) => update("alternative_field", event.target.value)} value={form.alternative_field}>{CORE_FIELDS.map((item) => <option key={item}>{item}</option>)}</select></label>}
      {["field_value_in", "custom_field_value_in", "explicit_state_or_exception"].includes(form.rule_type) && <label className="field"><span>Allowed values (comma-separated)</span><input onChange={(event) => update("values", event.target.value)} required value={form.values} /></label>}
      {customRule && <label className="field"><span>Custom field</span><select onChange={(event) => update("custom_field_id", event.target.value)} required value={form.custom_field_id}><option value="">Select field</option>{customFields.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
      {relationshipRule && <><MultiSelect label="Relationship types" onChange={(value) => update("relationship_type_ids", value)} required value={form.relationship_type_ids}>{relationshipTypes.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</MultiSelect><label className="field"><span>Direction</span><select onChange={(event) => update("direction", event.target.value)} value={form.direction}><option value="outgoing">Outgoing</option><option value="incoming">Incoming</option><option value="either">Either</option></select></label><MultiSelect label="Allowed counterpart types (optional)" onChange={(value) => update("target_asset_type_ids", value)} value={form.target_asset_type_ids}>{assetTypes.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</MultiSelect></>}
      {(relationshipRule || interfaceRule) && <label className="field"><span>Minimum</span><input min="1" onChange={(event) => update("minimum", event.target.value)} required type="number" value={form.minimum} /></label>}
      {interfaceRule && <><label className="field"><span>Interface role (optional)</span><input onChange={(event) => update("interface_role", event.target.value)} placeholder="management" value={form.interface_role} /></label><label className="field checkbox-field"><input checked={form.allow_any_role} onChange={(event) => update("allow_any_role", event.target.checked)} type="checkbox" /><span>Allow any interface role</span></label>{form.rule_type === "interface_has_ip" && <><label className="field"><span>Address family</span><select onChange={(event) => update("address_family", event.target.value)} value={form.address_family}><option value="either">IPv4 or IPv6</option><option value="ipv4">IPv4</option><option value="ipv6">IPv6</option></select></label><label className="field checkbox-field"><input checked={form.require_primary} onChange={(event) => update("require_primary", event.target.checked)} type="checkbox" /><span>Primary interface required</span></label></>}</>}
      {form.rule_type === "freshness_within_days" && <><label className="field"><span>Assertion predicate</span><input onChange={(event) => update("predicate", event.target.value)} required value={form.predicate} /></label><label className="field"><span>Maximum age (days)</span><input min="1" onChange={(event) => update("maximum_age_days", event.target.value)} required type="number" value={form.maximum_age_days} /></label></>}
      <label className="field"><span>Unless custom field (optional)</span><select onChange={(event) => update("unless_field_id", event.target.value)} value={form.unless_field_id}><option value="">No exception condition</option>{customFields.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      {form.unless_field_id && <label className="field"><span>Unless values</span><input onChange={(event) => update("unless_values", event.target.value)} placeholder="root, core" required value={form.unless_values} /></label>}
      <label className="field field-wide"><span>Description</span><textarea onChange={(event) => update("description", event.target.value)} value={form.description} /></label><label className="field field-wide"><span>Remediation hint</span><textarea onChange={(event) => update("remediation_hint", event.target.value)} value={form.remediation_hint} /></label><label className="field"><span>Sort order</span><input min="0" onChange={(event) => update("sort_order", event.target.value)} type="number" value={form.sort_order} /></label><label className="field checkbox-field"><input checked={form.active} onChange={(event) => update("active", event.target.checked)} type="checkbox" /><span>Active</span></label>
    </div>{validation && <div className={validation.valid ? "success-banner" : "error-banner"} role="status"><strong>{validation.interpretation}</strong>{validation.errors?.map((item) => <span key={item}>{item}</span>)}</div>}<p className="warning-banner">Changing this requirement may create or resolve gaps on {editing ? editing.affected_asset_count : assetType?.in_use_count || 0} affected assets.</p><div className="form-actions"><button className="button button-secondary" onClick={() => setShowForm(false)} type="button">Cancel</button><button className="button button-secondary" onClick={validate} type="button">Validate configuration</button><button className="button button-primary" disabled={saving} type="submit">{saving ? "Saving…" : "Save requirement"}</button></div></form></section>}
    <section className="table-card"><div className="table-meta"><span>{loading ? "Loading…" : `${requirements.length} requirements`}</span><button className="text-button" onClick={load} type="button">Refresh</button></div><div className="table-scroll"><table><thead><tr><th>Requirement</th><th>Level</th><th>Severity</th><th>Rule</th><th>Scope</th><th>State</th>{canManage && <th>Actions</th>}</tr></thead><tbody>{!loading && requirements.length === 0 && <tr><td className="empty-state" colSpan={canManage ? 7 : 6}>No knowledge requirements yet.</td></tr>}{requirements.map((item) => <tr key={item.id}><td><strong>{item.name}</strong><small className="secondary-text">{item.description || item.remediation_hint || "No description"}</small></td><td>{item.requirement_level}</td><td><StatusBadge status={item.severity} /></td><td>{item.rule_summary}</td><td>{item.asset_type_id ? typeNames[item.asset_type_id] || "Unavailable" : "Global"}</td><td><StatusBadge status={!item.configuration_valid ? "Invalid" : item.active ? "Active" : "Inactive"} /></td>{canManage && <td><div className="row-actions">{item.asset_type_id === id && <button className="text-button" onClick={() => begin(item)} type="button">Edit</button>}{item.asset_type_id === id && <button className="text-button" onClick={() => begin(item, true)} type="button">Duplicate</button>}<button className="text-button" onClick={() => toggle(item)} type="button">{item.active ? "Deactivate" : "Activate"}</button>{item.asset_type_id === id && <button className="text-button text-danger" onClick={() => remove(item)} type="button">Delete</button>}</div></td>}</tr>)}</tbody></table></div></section>
  </>;
}
