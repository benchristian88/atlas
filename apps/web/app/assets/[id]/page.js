"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { PageHeader } from "../../../components/page-header";
import { StatusBadge } from "../../../components/status-badge";
import { apiRequest } from "../../../lib/api";
import { RELATIONSHIP_TYPES, taxonomyLabel } from "../../../lib/taxonomy";

const detailFields = [
  ["asset_type", "Type"], ["vendor", "Vendor"], ["model", "Model"],
  ["hostname", "Hostname"], ["source", "Source"],
  ["description", "Description"],
];

export default function AssetDetailPage() {
  const { id } = useParams();
  const searchParams = useSearchParams();
  const [asset, setAsset] = useState(null);
  const [assets, setAssets] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [sites, setSites] = useState([]);
  const [relationships, setRelationships] = useState([]);
  const [networks, setNetworks] = useState([]);
  const [interfaces, setInterfaces] = useState([]);
  const [form, setForm] = useState({ source_asset_id: "", target_asset_id: "", relationship_type: "depends_on", notes: "" });
  const [interfaceForm, setInterfaceForm] = useState({ name: "eth0", network_id: "", ip_address: "", mac_address: "", is_primary: true, notes: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savingInterface, setSavingInterface] = useState(false);
  const [showInterfaceForm, setShowInterfaceForm] = useState(false);
  const [showRelationshipForm, setShowRelationshipForm] = useState(false);
  const [error, setError] = useState("");
  const started = useRef(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const [current, allAssets, allCustomers, allSites, edges, allNetworks, assetInterfaces] = await Promise.all([
        apiRequest(`/assets/${id}`), apiRequest("/assets"), apiRequest("/customers"),
        apiRequest("/sites"), apiRequest(`/asset-relationships?asset_id=${id}`),
        apiRequest("/networks"), apiRequest(`/asset-interfaces?asset_id=${id}`),
      ]);
      setAsset(current);
      setAssets(allAssets);
      setCustomers(allCustomers);
      setSites(allSites);
      setRelationships(edges);
      setNetworks(allNetworks);
      setInterfaces(assetInterfaces);
      setForm((currentForm) => ({ ...currentForm, source_asset_id: currentForm.source_asset_id || id }));
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
  const networksById = useMemo(() => Object.fromEntries(networks.map((item) => [item.id, item])), [networks]);
  const availableNetworks = networks.filter((network) =>
    network.customer_id === asset?.customer_id
    && (!network.site_id || network.site_id === asset?.site_id)
  );

  async function createInterface(event) {
    event.preventDefault();
    setSavingInterface(true);
    setError("");
    try {
      await apiRequest("/asset-interfaces", {
        method: "POST",
        body: JSON.stringify({
          asset_id: id,
          network_id: interfaceForm.network_id || null,
          name: interfaceForm.name,
          ip_address: interfaceForm.ip_address || null,
          mac_address: interfaceForm.mac_address || null,
          is_primary: interfaceForm.is_primary,
          notes: interfaceForm.notes || null,
        }),
      });
      setInterfaceForm({ name: "eth0", network_id: "", ip_address: "", mac_address: "", is_primary: false, notes: "" });
      await load();
      setShowInterfaceForm(false);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSavingInterface(false);
    }
  }

  async function removeInterface(interfaceId) {
    setError("");
    try {
      await apiRequest(`/asset-interfaces/${interfaceId}`, { method: "DELETE" });
      await load();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function createRelationship(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await apiRequest("/asset-relationships", {
        method: "POST",
        body: JSON.stringify({
          source_asset_id: form.source_asset_id,
          target_asset_id: form.target_asset_id,
          relationship_type: form.relationship_type,
          notes: form.notes || null,
        }),
      });
      setForm({ source_asset_id: id, target_asset_id: "", relationship_type: "depends_on", notes: "" });
      await load();
      setShowRelationshipForm(false);
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
      <div className="page-heading-row"><PageHeader eyebrow="Asset detail" title={asset.name} description={`${customer?.name || "Unknown customer"} · ${site?.name || "No site"}`} /><Link className="button button-secondary" href={`/assets/${id}/edit`}>Edit Asset</Link></div>
      {searchParams.get("updated") === "1" && <div className="success-banner" role="status">Asset updated successfully.</div>}
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
        <div className="form-card-header"><h2>Interfaces and networks</h2>{!showInterfaceForm && <button className="button button-primary" onClick={() => setShowInterfaceForm(true)} type="button">Add interface</button>}</div>
        {showInterfaceForm && <form className="resource-form" onSubmit={createInterface}>
          <div className="form-grid">
            <label className="field"><span>Interface name *</span><input required value={interfaceForm.name} onChange={(event) => setInterfaceForm({ ...interfaceForm, name: event.target.value })} placeholder="eth0" /></label>
            <label className="field"><span>Network / VLAN</span><select value={interfaceForm.network_id} onChange={(event) => setInterfaceForm({ ...interfaceForm, network_id: event.target.value })}><option value="">Unassigned network</option>{availableNetworks.map((network) => <option key={network.id} value={network.id}>{network.vlan_id !== null ? `VLAN ${network.vlan_id} — ` : ""}{network.name}{network.cidr ? ` — ${network.cidr}` : ""}</option>)}</select></label>
            <label className="field"><span>IP address</span><input value={interfaceForm.ip_address} onChange={(event) => setInterfaceForm({ ...interfaceForm, ip_address: event.target.value })} placeholder="192.168.5.8" /></label>
            <label className="field"><span>MAC address</span><input value={interfaceForm.mac_address} onChange={(event) => setInterfaceForm({ ...interfaceForm, mac_address: event.target.value })} placeholder="02:00:00:00:05:08" /></label>
            <label className="field checkbox-field"><input checked={interfaceForm.is_primary} onChange={(event) => setInterfaceForm({ ...interfaceForm, is_primary: event.target.checked })} type="checkbox" /><span>Primary interface</span></label>
            <label className="field field-wide"><span>Notes</span><textarea rows="2" value={interfaceForm.notes} onChange={(event) => setInterfaceForm({ ...interfaceForm, notes: event.target.value })} /></label>
          </div>
          <div className="form-actions"><button className="button button-secondary" onClick={() => setShowInterfaceForm(false)} type="button">Cancel</button><button className="button button-primary" disabled={savingInterface} type="submit">{savingInterface ? "Saving…" : "Add interface"}</button></div>
        </form>}
        <div className="interface-list">{interfaces.length === 0 ? <p className="secondary-text">No interfaces yet.</p> : interfaces.map((item) => { const network = networksById[item.network_id]; return <div className="interface-row" key={item.id}><div><strong>{item.name}{item.is_primary ? " · Primary" : ""}</strong><span>{item.ip_address || "No IP"}{item.mac_address ? ` · ${item.mac_address}` : ""}</span><span>{network ? `${network.vlan_id !== null ? `VLAN ${network.vlan_id} — ` : ""}${network.name}${network.cidr ? ` — ${network.cidr}` : ""}` : "Unassigned network"}</span></div><button className="text-button text-danger" onClick={() => removeInterface(item.id)} type="button">Delete</button></div>; })}</div>
      </section>

      <section className="form-card">
        <div className="form-card-header"><h2>Relationships</h2>{!showRelationshipForm && <button className="button button-primary" onClick={() => setShowRelationshipForm(true)} type="button">Add relationship</button>}</div>
        {showRelationshipForm && <form className="resource-form" onSubmit={createRelationship}>
          <div className="form-grid">
            <label className="field"><span>Source asset *</span><select required value={form.source_asset_id} onChange={(event) => setForm({ ...form, source_asset_id: event.target.value, target_asset_id: event.target.value === form.target_asset_id ? "" : form.target_asset_id })}><option value="">Select an asset</option>{assets.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <label className="field"><span>Relationship type *</span><select required value={form.relationship_type} onChange={(event) => setForm({ ...form, relationship_type: event.target.value })}>{RELATIONSHIP_TYPES.map((value) => <option key={value} value={value}>{taxonomyLabel(value)}</option>)}</select></label>
            <label className="field"><span>Target asset *</span><select required value={form.target_asset_id} onChange={(event) => setForm({ ...form, target_asset_id: event.target.value })}><option value="">Select an asset</option>{assets.filter((item) => item.id !== form.source_asset_id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <label className="field field-wide"><span>Notes</span><textarea rows="2" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label>
          </div>
          <div className="form-actions"><button className="button button-secondary" onClick={() => setShowRelationshipForm(false)} type="button">Cancel</button><button className="button button-primary" disabled={saving} type="submit">{saving ? "Saving…" : "Add relationship"}</button></div>
        </form>}
      </section>

      <section className="table-card" aria-label="Asset relationships">
        <div className="table-meta"><span>{relationships.length} relationships</span></div>
        {relationships.length === 0 ? <p className="empty-state">No relationships yet.</p> : (
          <div className="relationship-list">{relationships.map((edge) => {
            return <div className="relationship-row" key={edge.id}><span><strong>{edge.source_asset_name || assetsById[edge.source_asset_id]?.name || "Unknown asset"}</strong> → {taxonomyLabel(edge.relationship_type)} → <strong>{edge.target_asset_name || assetsById[edge.target_asset_id]?.name || "Unknown asset"}</strong>{edge.notes ? ` — ${edge.notes}` : ""}</span><button className="text-button text-danger" onClick={() => removeRelationship(edge.id)} type="button">Delete</button></div>;
          })}</div>
        )}
      </section>
    </>
  );
}
