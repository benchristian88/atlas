"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { PageHeader } from "../../../components/page-header";
import { StatusBadge } from "../../../components/status-badge";
import { apiRequest } from "../../../lib/api";

const detailFields = [
  ["asset_type", "Type"], ["vendor", "Vendor"], ["model", "Model"],
  ["hostname", "Hostname"], ["ip_address", "IP address"], ["source", "Source"],
  ["description", "Description"],
];

export default function AssetDetailPage() {
  const { id } = useParams();
  const [asset, setAsset] = useState(null);
  const [assets, setAssets] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [sites, setSites] = useState([]);
  const [relationships, setRelationships] = useState([]);
  const [form, setForm] = useState({ target_asset_id: "", relationship_type: "depends_on", notes: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const started = useRef(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const [current, allAssets, allCustomers, allSites, edges] = await Promise.all([
        apiRequest(`/assets/${id}`), apiRequest("/assets"), apiRequest("/customers"),
        apiRequest("/sites"), apiRequest(`/asset-relationships?asset_id=${id}`),
      ]);
      setAsset(current);
      setAssets(allAssets);
      setCustomers(allCustomers);
      setSites(allSites);
      setRelationships(edges);
    } catch (requestError) {
      setError(requestError.message || "Atlas could not load this asset.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    load();
  }, [load]);

  const assetsById = useMemo(() => Object.fromEntries(assets.map((item) => [item.id, item])), [assets]);
  const customer = customers.find((item) => item.id === asset?.customer_id);
  const site = sites.find((item) => item.id === asset?.site_id);

  async function createRelationship(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await apiRequest("/asset-relationships", {
        method: "POST",
        body: JSON.stringify({
          source_asset_id: id,
          target_asset_id: form.target_asset_id,
          relationship_type: form.relationship_type,
          notes: form.notes || null,
        }),
      });
      setForm({ target_asset_id: "", relationship_type: "depends_on", notes: "" });
      await load();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  async function removeRelationship(relationshipId) {
    setError("");
    try {
      await apiRequest(`/asset-relationships/${relationshipId}`, { method: "DELETE" });
      await load();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  if (loading) return <div className="status-banner" role="status">Loading asset…</div>;
  if (!asset) return <div className="error-banner" role="alert">{error || "Asset not found."}</div>;

  return (
    <>
      <PageHeader eyebrow="Asset detail" title={asset.name} description={`${customer?.name || "Unknown customer"} · ${site?.name || "No site"}`} />
      {error && <div className="error-banner" role="alert">{error}</div>}
      <section className="detail-card">
        <div className="detail-grid">
          <div><span>Status</span><strong><StatusBadge status={asset.status} /></strong></div>
          <div><span>Customer</span><strong>{customer?.name || "Unknown"}</strong></div>
          <div><span>Site</span><strong>{site?.name || "—"}</strong></div>
          {detailFields.map(([key, label]) => <div key={key}><span>{label}</span><strong>{asset[key] || "—"}</strong></div>)}
        </div>
      </section>

      <section className="form-card">
        <div className="form-card-header"><h2>Add relationship</h2></div>
        <form className="resource-form" onSubmit={createRelationship}>
          <div className="form-grid">
            <label className="field"><span>Target asset *</span><select required value={form.target_asset_id} onChange={(event) => setForm({ ...form, target_asset_id: event.target.value })}><option value="">Select an asset</option>{assets.filter((item) => item.id !== id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <label className="field"><span>Relationship type *</span><input required value={form.relationship_type} onChange={(event) => setForm({ ...form, relationship_type: event.target.value })} /></label>
            <label className="field field-wide"><span>Notes</span><textarea rows="2" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label>
          </div>
          <div className="form-actions"><button className="button button-primary" disabled={saving} type="submit">{saving ? "Saving…" : "Add relationship"}</button></div>
        </form>
      </section>

      <section className="table-card" aria-label="Asset relationships">
        <div className="table-meta"><span>{relationships.length} relationships</span></div>
        {relationships.length === 0 ? <p className="empty-state">No relationships yet.</p> : (
          <div className="relationship-list">{relationships.map((edge) => {
            const outgoing = edge.source_asset_id === id;
            const other = assetsById[outgoing ? edge.target_asset_id : edge.source_asset_id];
            return <div className="relationship-row" key={edge.id}><span><strong>{outgoing ? "Outgoing" : "Incoming"}</strong> · {edge.relationship_type} · {other?.name || "Unknown asset"}{edge.notes ? ` — ${edge.notes}` : ""}</span><button className="text-button text-danger" onClick={() => removeRelationship(edge.id)} type="button">Delete</button></div>;
          })}</div>
        )}
      </section>
    </>
  );
}
