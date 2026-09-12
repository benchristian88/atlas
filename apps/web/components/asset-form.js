"use client";

import { useEffect, useMemo, useState } from "react";
import { AssetIcon } from "./asset-icon";

function initialForm(asset, assetTypes, customers, sites, context) {
  const customerId = asset?.customer_id || context.customerId || (customers.length === 1 ? customers[0].id : "");
  const customerSites = sites.filter((site) => site.customer_id === customerId);
  const siteId = asset?.site_id || context.siteId || (customerSites.length === 1 ? customerSites[0].id : "");
  const metadata = { ...(asset?.metadata || {}) };
  const managementUrl = metadata.management_url || "";
  const tags = Array.isArray(metadata.tags) ? metadata.tags.join(", ") : "";
  delete metadata.management_url;
  delete metadata.tags;
  return {
    customer_id: customerId,
    site_id: siteId,
    name: asset?.name || "",
    asset_type: asset?.asset_type || assetTypes.find((item) => item.active)?.key || "",
    icon_url: asset?.icon_url || "",
    vendor: asset?.vendor || "",
    model: asset?.model || "",
    hostname: asset?.hostname || "",
    ip_address: asset?.ip_address || "",
    management_url: managementUrl,
    tags,
    status: asset?.status || "active",
    description: asset?.description || "",
    metadata_json: JSON.stringify(metadata, null, 2),
  };
}

function initialCustomValues(asset) {
  return Object.fromEntries(Object.entries(asset?.custom_fields || {}).map(([key, value]) => [
    key,
    typeof value === "boolean" ? String(value) : value ?? "",
  ]));
}

function applicableFields(definitions, assetType) {
  return definitions.filter((definition) => definition.active && (
    definition.applies_to_all_asset_types || definition.asset_type_keys.includes(assetType)
  ));
}

export function AssetForm({
  asset = null,
  assetTypes,
  customFieldDefinitions,
  customers,
  sites,
  context,
  saving,
  submitLabel,
  onCancel,
  onSubmit,
}) {
  const [form, setForm] = useState(() => initialForm(asset, assetTypes, customers, sites, context));
  const [customValues, setCustomValues] = useState(() => initialCustomValues(asset));
  const [formError, setFormError] = useState("");

  useEffect(() => {
    setForm(initialForm(asset, assetTypes, customers, sites, context));
    setCustomValues(initialCustomValues(asset));
  }, [asset, assetTypes, context.customerId, context.siteId, customers, sites]);

  const selectedType = assetTypes.find((item) => item.key === form.asset_type) || null;
  const fields = useMemo(
    () => applicableFields(customFieldDefinitions, form.asset_type),
    [customFieldDefinitions, form.asset_type],
  );
  const availableSites = sites.filter((site) => site.customer_id === form.customer_id);
  const availableTypes = assetTypes.filter((item) => item.active || item.key === asset?.asset_type);

  function change(name, value, extra = {}) {
    setForm((current) => ({ ...current, [name]: value, ...extra }));
  }

  async function submit(event) {
    event.preventDefault();
    setFormError("");
    if (!form.site_id) {
      setFormError("Choose a site. Every asset must belong to a customer and site.");
      return;
    }
    let metadata;
    try {
      metadata = form.metadata_json.trim() ? JSON.parse(form.metadata_json) : {};
      if (!metadata || Array.isArray(metadata) || typeof metadata !== "object") {
        throw new Error("Additional metadata must be a JSON object.");
      }
    } catch (error) {
      setFormError(error.message || "Additional metadata must be valid JSON.");
      return;
    }
    const customFields = {};
    for (const definition of fields) {
      const rawValue = customValues[definition.key] ?? "";
      customFields[definition.key] = definition.data_type === "boolean" && rawValue !== ""
        ? rawValue === "true"
        : rawValue;
    }
    await onSubmit({
      customer_id: form.customer_id,
      site_id: form.site_id,
      name: form.name,
      asset_type: form.asset_type,
      icon_url: form.icon_url || null,
      vendor: form.vendor || null,
      model: form.model || null,
      hostname: form.hostname || null,
      ip_address: form.ip_address || null,
      status: form.status,
      description: form.description || null,
      metadata: {
        ...metadata,
        ...(form.management_url ? { management_url: form.management_url } : {}),
        ...(form.tags ? { tags: form.tags.split(",").map((tag) => tag.trim()).filter(Boolean) } : {}),
      },
      custom_fields: customFields,
    });
  }

  return (
    <form className="resource-form" onSubmit={submit}>
      {formError && <div className="error-banner" role="alert">{formError}</div>}
      <div className="asset-form-heading">
        <AssetIcon asset={form.icon_url === asset?.icon_url ? asset : null} assetType={selectedType} alt="Asset icon preview" size={54} />
        <div><strong>Icon preview</strong><span>Asset override, then type default, then Atlas fallback.</span></div>
      </div>
      <div className="form-grid">
        <label className="field"><span>Customer *</span><select disabled={Boolean(context.customerId)} required value={form.customer_id} onChange={(event) => {
          const customerId = event.target.value;
          const matchingSites = sites.filter((site) => site.customer_id === customerId);
          change("customer_id", customerId, { site_id: matchingSites.length === 1 ? matchingSites[0].id : "" });
        }}><option value="">Select customer</option>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}</select></label>
        <label className="field"><span>Site *</span><select disabled={Boolean(context.siteId)} required value={form.site_id} onChange={(event) => change("site_id", event.target.value)}><option value="">Select site</option>{availableSites.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}</select></label>
        <label className="field"><span>Name *</span><input required value={form.name} onChange={(event) => change("name", event.target.value)} /></label>
        <label className="field"><span>Asset type *</span><select required value={form.asset_type} onChange={(event) => change("asset_type", event.target.value)}><option value="">Select asset type</option>{availableTypes.map((type) => <option key={type.key} value={type.key}>{type.name}</option>)}</select></label>
        <label className="field field-wide"><span>Asset icon URL</span><input placeholder="https://example.com/icon.png" type="url" value={form.icon_url} onChange={(event) => change("icon_url", event.target.value)} /><small>Optional public HTTPS PNG, JPEG or WebP source. Atlas caches a local copy after saving; changing the URL refreshes it. SVG and private addresses are blocked.</small></label>
        <label className="field"><span>Vendor</span><input value={form.vendor} onChange={(event) => change("vendor", event.target.value)} /></label>
        <label className="field"><span>Model</span><input value={form.model} onChange={(event) => change("model", event.target.value)} /></label>
        <label className="field"><span>Hostname</span><input value={form.hostname} onChange={(event) => change("hostname", event.target.value)} /></label>
        <label className="field"><span>Primary IP address</span><input placeholder="192.168.1.10" value={form.ip_address} onChange={(event) => change("ip_address", event.target.value)} /></label>
        <label className="field"><span>Management URL</span><input type="url" value={form.management_url} onChange={(event) => change("management_url", event.target.value)} /></label>
        <label className="field"><span>Tags</span><input placeholder="production, critical" value={form.tags} onChange={(event) => change("tags", event.target.value)} /></label>
        <label className="field"><span>Status *</span><select required value={form.status} onChange={(event) => change("status", event.target.value)}><option value="active">Active</option><option value="stale">Stale</option><option value="unknown">Unknown</option></select></label>
        <label className="field field-wide"><span>Description</span><textarea rows="3" value={form.description} onChange={(event) => change("description", event.target.value)} /></label>
      </div>

      {fields.length > 0 && <fieldset className="custom-fields-section"><legend>Custom enrichment</legend><div className="form-grid">{fields.map((definition) => <CustomFieldInput definition={definition} key={definition.id} onChange={(value) => setCustomValues((current) => ({ ...current, [definition.key]: value }))} value={customValues[definition.key] ?? ""} />)}</div></fieldset>}

      <label className="field"><span>Additional metadata (JSON)</span><textarea className="mono" rows="5" value={form.metadata_json} onChange={(event) => change("metadata_json", event.target.value)} /><small>Optional structured facts not covered by standard or custom fields.</small></label>
      <div className="form-actions"><button className="button button-secondary" onClick={onCancel} type="button">Cancel</button><button className="button button-primary" disabled={saving} type="submit">{saving ? "Saving…" : submitLabel}</button></div>
    </form>
  );
}

function CustomFieldInput({ definition, value, onChange }) {
  const className = definition.data_type === "multiline_text" ? "field field-wide" : "field";
  return <label className={className}><span>{definition.name}{definition.required ? " *" : ""}</span>{definition.data_type === "multiline_text" ? <textarea required={definition.required} rows="3" value={value} onChange={(event) => onChange(event.target.value)} /> : definition.data_type === "boolean" ? <select required={definition.required} value={value} onChange={(event) => onChange(event.target.value)}><option value="">Not set</option><option value="true">Yes</option><option value="false">No</option></select> : definition.data_type === "dropdown" ? <select required={definition.required} value={value} onChange={(event) => onChange(event.target.value)}><option value="">Select an option</option>{definition.options.filter((option) => option.active || option.value === value).map((option) => <option key={option.id} value={option.value}>{option.label}</option>)}</select> : <input required={definition.required} step={definition.data_type === "number" ? "any" : undefined} type={definition.data_type === "number" ? "number" : definition.data_type === "date" ? "date" : definition.data_type === "url" ? "url" : "text"} value={value} onChange={(event) => onChange(event.target.value)} />}{definition.help_text && <small>{definition.help_text}</small>}</label>;
}
