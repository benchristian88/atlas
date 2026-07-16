"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AccessDenied } from "../../../../components/access-denied";
import { AssetForm } from "../../../../components/asset-form";
import { useAuth } from "../../../../components/auth-context";
import { PageHeader } from "../../../../components/page-header";
import { useWorkspaceContext } from "../../../../components/workspace-context";
import { apiRequest } from "../../../../lib/api";

export default function EditAssetPage() {
  const { id } = useParams();
  const router = useRouter();
  const { hasPermission, hasPermissionForObject } = useAuth();
  const workspace = useWorkspaceContext();
  const [asset, setAsset] = useState(null);
  const [assetTypes, setAssetTypes] = useState([]);
  const [customFields, setCustomFields] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const canEdit = hasPermission("assets.edit");

  useEffect(() => {
    if (!canEdit) return;
    let active = true;
    async function load() {
      try {
        const [assetRecord, typeRecords, fieldRecords] = await Promise.all([
          apiRequest(`/assets/${id}`),
          hasPermission("asset_types.view") ? apiRequest("/asset-types") : Promise.resolve([]),
          hasPermission("custom_fields.view") ? apiRequest("/custom-fields?active_only=true") : Promise.resolve([]),
        ]);
        if (!active) return;
        setAsset(assetRecord);
        setAssetTypes(typeRecords);
        setCustomFields(fieldRecords);
      } catch (requestError) {
        if (active) setError(requestError.message || "Atlas could not load this asset.");
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [canEdit, hasPermission, id]);

  if (!canEdit) return <AccessDenied description="You need assets.edit permission to change inventory records." />;

  async function save(payload) {
    setSaving(true);
    setError("");
    try {
      await apiRequest(`/assets/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
      router.replace(`/assets/${id}?updated=1`);
    } catch (requestError) {
      setError(requestError.message || "Atlas could not update this asset.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="status-banner" role="status">Loading asset…</div>;
  if (!asset) return <div className="error-banner" role="alert">{error || "Asset not found."}</div>;
  if (!hasPermissionForObject("assets.edit", asset.customer_id, asset.site_id)) {
    return <AccessDenied description="You cannot edit assets in this customer and site." />;
  }
  const editableSites = workspace.sites.filter((site) => (
    hasPermissionForObject("assets.edit", site.customer_id, site.id)
  ));
  const editableCustomerIds = new Set(editableSites.map((site) => site.customer_id));
  const editableCustomers = workspace.customers.filter(
    (customer) => editableCustomerIds.has(customer.id),
  );
  const contextMismatch = (workspace.customerId && workspace.customerId !== asset.customer_id)
    || (workspace.siteId && workspace.siteId !== asset.site_id);

  return (
    <>
      <PageHeader eyebrow="Asset" title={`Edit ${asset.name}`} description="Update identity, ownership, icon, inventory metadata, and custom enrichment." />
      {contextMismatch && <div className="warning-banner">This asset is outside the active header context. Switch to its customer and site before saving changes.</div>}
      {error && <div className="error-banner" role="alert">{error}</div>}
      <section className="form-card">
        <AssetForm
          asset={asset}
          assetTypes={assetTypes}
          context={{ customerId: workspace.customerId, siteId: workspace.siteId }}
          customFieldDefinitions={customFields}
          customers={editableCustomers}
          onCancel={() => router.push(`/assets/${id}`)}
          onSubmit={save}
          saving={saving}
          sites={editableSites}
          submitLabel="Save changes"
        />
      </section>
    </>
  );
}
