"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { PageHeader } from "../../../../components/page-header";
import { apiRequest } from "../../../../lib/api";
import { ASSET_TYPES, taxonomyLabel } from "../../../../lib/taxonomy";

export default function EditAssetPage() {
  const { id } = useParams();
  const router = useRouter();
  const [customers, setCustomers] = useState([]);
  const [sites, setSites] = useState([]);
  const [form, setForm] = useState(null);
  const [metadata, setMetadata] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    Promise.all([apiRequest(`/assets/${id}`), apiRequest("/customers"), apiRequest("/sites")])
      .then(([asset, allCustomers, allSites]) => {
        setCustomers(allCustomers);
        setSites(allSites);
        setMetadata(asset.metadata || {});
        setForm({
          customer_id: asset.customer_id,
          site_id: asset.site_id || "",
          name: asset.name,
          asset_type: asset.asset_type,
          vendor: asset.vendor || "",
          model: asset.model || "",
          hostname: asset.hostname || "",
          management_url: asset.metadata?.management_url || "",
          tags: (asset.metadata?.tags || []).join(", "),
          status: asset.status,
          description: asset.description || "",
        });
      })
      .catch((requestError) => setError(requestError.message || "Atlas could not load this asset."));
  }, [id]);

  function change(name, value, extra = {}) {
    setForm((current) => ({ ...current, [name]: value, ...extra }));
  }

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await apiRequest(`/assets/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          customer_id: form.customer_id,
          site_id: form.site_id || null,
          name: form.name,
          asset_type: form.asset_type,
          vendor: form.vendor || null,
          model: form.model || null,
          hostname: form.hostname || null,
          status: form.status,
          description: form.description || null,
          metadata: {
            ...metadata,
            management_url: form.management_url || null,
            tags: form.tags.split(",").map((tag) => tag.trim()).filter(Boolean),
          },
        }),
      });
      router.replace(`/assets/${id}?updated=1`);
    } catch (requestError) {
      setError(requestError.message || "Atlas could not update this asset.");
      setSaving(false);
    }
  }

  if (!form && !error) return <div className="status-banner" role="status">Loading asset…</div>;

  return <>
    <PageHeader eyebrow="Asset" title="Edit asset" description="Update identity and inventory fields. IP addresses are managed through interfaces." />
    {error && <div className="error-banner" role="alert">{error}</div>}
    {form && <section className="form-card"><form className="resource-form" onSubmit={submit}><div className="form-grid">
      <label className="field"><span>Customer *</span><select required value={form.customer_id} onChange={(event) => change("customer_id", event.target.value, { site_id: "" })}>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}</select></label>
      <label className="field"><span>Site</span><select value={form.site_id} onChange={(event) => change("site_id", event.target.value)}><option value="">No site</option>{sites.filter((site) => site.customer_id === form.customer_id).map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}</select></label>
      <label className="field"><span>Name *</span><input required value={form.name} onChange={(event) => change("name", event.target.value)} /></label>
      <label className="field"><span>Asset type *</span><select required value={form.asset_type} onChange={(event) => change("asset_type", event.target.value)}>{!ASSET_TYPES.includes(form.asset_type) && <option value={form.asset_type}>{form.asset_type} (existing custom value)</option>}{ASSET_TYPES.map((value) => <option key={value} value={value}>{taxonomyLabel(value)}</option>)}</select></label>
      <label className="field"><span>Vendor</span><input value={form.vendor} onChange={(event) => change("vendor", event.target.value)} /></label>
      <label className="field"><span>Model</span><input value={form.model} onChange={(event) => change("model", event.target.value)} /></label>
      <label className="field"><span>Hostname</span><input value={form.hostname} onChange={(event) => change("hostname", event.target.value)} /></label>
      <label className="field"><span>Management URL</span><input type="url" value={form.management_url} onChange={(event) => change("management_url", event.target.value)} /></label>
      <label className="field"><span>Status</span><select value={form.status} onChange={(event) => change("status", event.target.value)}><option value="active">Active</option><option value="stale">Stale</option><option value="unknown">Unknown</option></select></label>
      <label className="field"><span>Tags</span><input value={form.tags} onChange={(event) => change("tags", event.target.value)} placeholder="homelab, production" /></label>
      <label className="field field-wide"><span>Description</span><textarea rows="4" value={form.description} onChange={(event) => change("description", event.target.value)} /></label>
    </div><div className="form-actions"><Link className="button button-secondary" href={`/assets/${id}`}>Cancel</Link><button className="button button-primary" disabled={saving} type="submit">{saving ? "Saving…" : "Save changes"}</button></div></form></section>}
  </>;
}
