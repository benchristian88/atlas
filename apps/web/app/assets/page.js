"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AccessDenied } from "../../components/access-denied";
import { AssetForm } from "../../components/asset-form";
import { AssetIcon } from "../../components/asset-icon";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { StatusBadge } from "../../components/status-badge";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";

export default function AssetsPage() {
  const { hasPermission, hasPermissionForObject, hasPermissionInContext } = useAuth();
  const workspace = useWorkspaceContext();
  const [assets, setAssets] = useState([]);
  const [assetTypes, setAssetTypes] = useState([]);
  const [customFields, setCustomFields] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const canView = hasPermissionInContext(
    "assets.view",
    workspace.customerId,
    workspace.siteId,
  );
  const canCreate = hasPermissionInContext(
    "assets.create",
    workspace.customerId,
    workspace.siteId,
  );
  const canEdit = hasPermission("assets.edit");
  const canDelete = hasPermission("assets.delete");

  const load = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    setError("");
    try {
      const [assetRecords, typeRecords, fieldRecords] = await Promise.all([
        apiRequest("/assets"),
        hasPermission("asset_types.view") ? apiRequest("/asset-types") : Promise.resolve([]),
        hasPermission("custom_fields.view") ? apiRequest("/custom-fields?active_only=true") : Promise.resolve([]),
      ]);
      setAssets(assetRecords);
      setAssetTypes(typeRecords);
      setCustomFields(fieldRecords);
    } catch (requestError) {
      setError(requestError.message || "Atlas could not load assets.");
    } finally {
      setLoading(false);
    }
  }, [canView, hasPermission]);

  useEffect(() => { load(); }, [load]);
  const assetTypesByKey = useMemo(
    () => Object.fromEntries(assetTypes.map((type) => [type.key, type])),
    [assetTypes],
  );
  const hasActiveAssetType = assetTypes.some((type) => type.active);
  const creatableSites = workspace.sites.filter((site) => (
    hasPermissionForObject("assets.create", site.customer_id, site.id)
  ));
  const creatableCustomerIds = new Set(creatableSites.map((site) => site.customer_id));
  const creatableCustomers = workspace.customers.filter(
    (customer) => creatableCustomerIds.has(customer.id),
  );
  if (!canView) return <AccessDenied />;

  async function createAsset(payload) {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await apiRequest("/assets", { method: "POST", body: JSON.stringify(payload) });
      setShowCreate(false);
      setSuccess("Asset created.");
      await load();
    } catch (requestError) {
      setError(requestError.message || "Atlas could not create this asset.");
    } finally {
      setSaving(false);
    }
  }

  async function removeAsset(asset) {
    if (!window.confirm(`Delete “${asset.name}”? Relationships must be removed first and this action cannot be undone.`)) return;
    setError("");
    try {
      await apiRequest(`/assets/${asset.id}`, { method: "DELETE" });
      setSuccess("Asset deleted.");
      await load();
    } catch (requestError) {
      setError(requestError.message || "Atlas could not delete this asset.");
    }
  }

  const showActions = canEdit || canDelete;
  return (
    <>
      <div className="page-heading-row">
        <PageHeader eyebrow="Inventory" title="Assets" description="Create and maintain infrastructure within the active customer and site context." />
        {canCreate && <button className="button button-primary" disabled={!hasActiveAssetType} onClick={() => setShowCreate(true)} type="button">Add asset</button>}
      </div>
      {canCreate && !hasActiveAssetType && !loading && <div className="warning-banner">No active asset types are available. Ask an administrator to activate one before creating assets.</div>}
      {error && <div className="error-banner" role="alert">{error}</div>}
      {success && <div className="success-banner" role="status">{success}</div>}
      {showCreate && <section className="form-card"><div className="form-card-header"><h2>Add asset</h2><button className="icon-button" aria-label="Close form" onClick={() => setShowCreate(false)} type="button">×</button></div><AssetForm assetTypes={assetTypes} context={{ customerId: workspace.customerId, siteId: workspace.siteId }} customFieldDefinitions={customFields} customers={creatableCustomers} onCancel={() => setShowCreate(false)} onSubmit={createAsset} saving={saving} sites={creatableSites} submitLabel="Create asset" /></section>}

      <section className="table-card" aria-label="Assets list">
        <div className="table-meta"><span>{loading ? "Loading…" : `${assets.length} assets`}</span><button className="text-button" disabled={loading} onClick={load} type="button">Refresh</button></div>
        <div className="table-scroll"><table><thead><tr><th>Asset</th><th>Type</th><th>Customer</th><th>Site</th><th>Hostname / IP</th><th>Status</th>{showActions && <th>Actions</th>}</tr></thead><tbody>
          {!loading && assets.length === 0 && <tr><td className="empty-state" colSpan={showActions ? 7 : 6}>No assets match the active context.</td></tr>}
          {assets.map((asset) => {
            const type = assetTypesByKey[asset.asset_type];
            const customer = workspace.customers.find((item) => item.id === asset.customer_id);
            const site = workspace.sites.find((item) => item.id === asset.site_id);
            const canEditAsset = canEdit && hasPermissionForObject("assets.edit", asset.customer_id, asset.site_id);
            const canDeleteAsset = canDelete && hasPermissionForObject("assets.delete", asset.customer_id, asset.site_id);
            return <tr key={asset.id}><td><Link className="asset-table-identity" href={`/assets/${asset.id}`}><AssetIcon asset={{ ...asset, icon_url: asset.icon_url || asset.resolved_icon_url }} assetType={type} size={38} /><span><strong>{asset.name}</strong><small>{asset.vendor || asset.model ? [asset.vendor, asset.model].filter(Boolean).join(" ") : "View documentation"}</small></span></Link></td><td>{type?.name || asset.asset_type}</td><td>{customer?.name || "Unknown"}</td><td>{site?.name || "Unknown"}</td><td><span className="mono">{asset.ip_address || asset.hostname || "—"}</span></td><td><StatusBadge status={asset.status} /></td>{showActions && <td><div className="row-actions">{canEditAsset && <Link className="text-button" href={`/assets/${asset.id}/edit`}>Edit</Link>}{canDeleteAsset && <button className="text-button text-danger" onClick={() => removeAsset(asset)} type="button">Delete</button>}</div></td>}</tr>;
          })}
        </tbody></table></div>
      </section>
    </>
  );
}
