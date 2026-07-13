"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { PageHeader } from "../../components/page-header";
import { apiRequest } from "../../lib/api";

export default function TopologyPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    async function load() {
      try {
        const [customers, sites, assets, relationships] = await Promise.all([
          apiRequest("/customers"), apiRequest("/sites"), apiRequest("/assets"),
          apiRequest("/asset-relationships"),
        ]);
        setData({ customers, sites, assets, relationships });
      } catch (requestError) {
        setError(requestError.message || "Atlas could not load the topology.");
      }
    }
    load();
  }, []);

  const relationshipsByAsset = useMemo(() => {
    const result = {};
    for (const edge of data?.relationships || []) {
      (result[edge.source_asset_id] ||= []).push(edge);
      (result[edge.target_asset_id] ||= []).push(edge);
    }
    return result;
  }, [data]);
  const assetsById = useMemo(() => Object.fromEntries((data?.assets || []).map((asset) => [asset.id, asset])), [data]);

  return (
    <>
      <PageHeader eyebrow="Infrastructure map" title="Topology" description="Customers, sites, assets, and their recorded relationships." />
      {error && <div className="error-banner" role="alert">{error}</div>}
      {!data && !error && <div className="status-banner" role="status">Loading topology…</div>}
      {data && data.customers.length === 0 && <div className="empty-state detail-card">No customers yet.</div>}
      {data && <div className="topology-tree">{data.customers.map((customer) => {
        const customerSites = data.sites.filter((site) => site.customer_id === customer.id);
        const withoutSite = data.assets.filter((asset) => asset.customer_id === customer.id && !asset.site_id);
        return <section className="topology-customer" key={customer.id}><h2>{customer.name}</h2>{customerSites.map((site) => <div className="topology-site" key={site.id}><h3>{site.name}</h3><AssetNodes assets={data.assets.filter((asset) => asset.site_id === site.id)} assetsById={assetsById} relationshipsByAsset={relationshipsByAsset} /></div>)}{withoutSite.length > 0 && <div className="topology-site"><h3>Unassigned assets</h3><AssetNodes assets={withoutSite} assetsById={assetsById} relationshipsByAsset={relationshipsByAsset} /></div>}</section>;
      })}</div>}
    </>
  );
}

function AssetNodes({ assets, assetsById, relationshipsByAsset }) {
  if (assets.length === 0) return <p className="secondary-text">No assets</p>;
  return <ul className="topology-assets">{assets.map((asset) => <li key={asset.id}><Link href={`/assets/${asset.id}`}>{asset.name}</Link><span>{asset.asset_type}{(relationshipsByAsset[asset.id] || []).map((edge) => { const otherId = edge.source_asset_id === asset.id ? edge.target_asset_id : edge.source_asset_id; return ` · ${edge.relationship_type}: ${assetsById[otherId]?.name || "unknown"}`; }).join("")}</span></li>)}</ul>;
}
