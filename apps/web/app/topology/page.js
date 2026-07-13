"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { PageHeader } from "../../components/page-header";
import { StatusBadge } from "../../components/status-badge";
import { apiRequest } from "../../lib/api";
import { taxonomyLabel } from "../../lib/taxonomy";

const parentTypes = new Set(["proxmox_cluster", "proxmox_host", "docker_host", "network", "vlan", "storage_pool", "nas"]);

export default function TopologyPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [mode, setMode] = useState("hierarchy");
  const [filters, setFilters] = useState({ customer: "", site: "", assetType: "" });
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    apiRequest("/topology").then(setData).catch((requestError) => {
      setError(requestError.message || "Atlas could not load the topology.");
    });
  }, []);

  const visibleAssets = useMemo(() => (data?.assets || []).filter((asset) =>
    (!filters.customer || asset.customer_id === filters.customer)
    && (!filters.site || asset.site_id === filters.site)
    && (!filters.assetType || asset.asset_type === filters.assetType)
  ), [data, filters]);
  const visibleIds = useMemo(() => new Set(visibleAssets.map((asset) => asset.id)), [visibleAssets]);
  const visibleRelationships = useMemo(() => (data?.relationships || []).filter((edge) =>
    visibleIds.has(edge.source_asset_id) && visibleIds.has(edge.target_asset_id)
  ), [data, visibleIds]);
  const assetsById = useMemo(() => Object.fromEntries((data?.assets || []).map((asset) => [asset.id, asset])), [data]);
  const assetTypes = useMemo(() => [...new Set((data?.assets || []).map((asset) => asset.asset_type))].sort(), [data]);

  function updateFilter(name, value) {
    setFilters((current) => ({
      ...current,
      [name]: value,
      ...(name === "customer" ? { site: "" } : {}),
    }));
  }

  const empty = data && data.assets.length === 0;
  return (
    <>
      <PageHeader eyebrow="Infrastructure map" title="Topology" description="Explore hosting hierarchy and explicit relationships across your infrastructure." />
      {error && <div className="error-banner" role="alert">{error}</div>}
      {!data && !error && <div className="status-banner" role="status">Loading topology…</div>}
      {data && <>
        <div className="topology-toolbar">
          <div className="mode-selector" aria-label="Topology mode">
            <button className={`button ${mode === "hierarchy" ? "button-primary" : "button-secondary"}`} onClick={() => setMode("hierarchy")} type="button">Hierarchy</button>
            <button className={`button ${mode === "relationships" ? "button-primary" : "button-secondary"}`} onClick={() => setMode("relationships")} type="button">Relationships</button>
            <button className={`button ${mode === "networks" ? "button-primary" : "button-secondary"}`} onClick={() => setMode("networks")} type="button">Network / VLAN</button>
          </div>
          <div className="topology-filters">
            <label className="field"><span>Customer</span><select value={filters.customer} onChange={(event) => updateFilter("customer", event.target.value)}><option value="">All customers</option>{data.customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}</select></label>
            <label className="field"><span>Site</span><select value={filters.site} onChange={(event) => updateFilter("site", event.target.value)}><option value="">All sites</option>{data.sites.filter((site) => !filters.customer || site.customer_id === filters.customer).map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}</select></label>
            <label className="field"><span>Asset type</span><select value={filters.assetType} onChange={(event) => updateFilter("assetType", event.target.value)}><option value="">All types</option>{assetTypes.map((type) => <option key={type} value={type}>{taxonomyLabel(type)}</option>)}</select></label>
          </div>
        </div>
        {empty && <div className="topology-empty"><h2>Start modelling your infrastructure</h2><p>Create a customer, site, assets, and relationships to build a topology.</p><div><Link className="button button-primary" href="/customers">Create customer</Link> <Link className="button button-secondary" href="/assets">Create asset</Link></div></div>}
        {!empty && visibleAssets.length === 0 && <div className="empty-state detail-card">No assets match these filters.</div>}
        {visibleAssets.length > 0 && mode === "hierarchy" && <Hierarchy data={data} assets={visibleAssets} relationships={visibleRelationships} assetsById={assetsById} filters={filters} />}
        {visibleAssets.length > 0 && mode === "relationships" && <RelationshipGraph data={data} assets={visibleAssets} relationships={visibleRelationships} assetsById={assetsById} />}
        {visibleAssets.length > 0 && mode === "networks" && <NetworkGraph data={data} assets={visibleAssets} visibleIds={visibleIds} filters={filters} />}
      </>}
    </>
  );
}

function Hierarchy({ data, assets, relationships, assetsById, filters }) {
  const interfaceIp = primaryInterfaceIps(data.asset_interfaces);
  const childIds = new Set();
  const children = {};
  for (const edge of relationships) {
    let parentId;
    let childId;
    if (edge.relationship_type === "runs_on") [childId, parentId] = [edge.source_asset_id, edge.target_asset_id];
    if (["hosts", "contains", "runs"].includes(edge.relationship_type)) [parentId, childId] = [edge.source_asset_id, edge.target_asset_id];
    if (parentId && childId) {
      (children[parentId] ||= []).push({ asset: assetsById[childId], label: edge.relationship_type });
      childIds.add(childId);
    }
  }
  const customers = data.customers.filter((customer) => !filters.customer || customer.id === filters.customer);
  return <div className="topology-tree">{customers.map((customer) => {
    const sites = data.sites.filter((site) => site.customer_id === customer.id && (!filters.site || site.id === filters.site));
    return <section className="topology-customer" key={customer.id}><h2>{customer.name}</h2>{sites.map((site) => {
      const siteAssets = assets.filter((asset) => asset.site_id === site.id);
      const roots = siteAssets.filter((asset) => !childIds.has(asset.id));
      return <div className="topology-site" key={site.id}><h3>{site.name}</h3>{roots.length ? <div className="hierarchy-nodes">{roots.sort((a, b) => Number(parentTypes.has(b.asset_type)) - Number(parentTypes.has(a.asset_type))).map((asset) => <HierarchyNode asset={asset} children={children} interfaceIp={interfaceIp} key={asset.id} seen={new Set()} />)}</div> : <p className="secondary-text">No root assets</p>}</div>;
    })}</section>;
  })}</div>;
}

function HierarchyNode({ asset, children, interfaceIp, seen }) {
  if (!asset || seen.has(asset.id)) return null;
  const nextSeen = new Set(seen).add(asset.id);
  return <div className="hierarchy-node"><AssetNode asset={asset} interfaceIp={interfaceIp[asset.id]} />{(children[asset.id] || []).map((child) => <div className="hierarchy-child" key={`${asset.id}-${child.asset?.id}`}><span className="edge-label">{taxonomyLabel(child.label)}</span><HierarchyNode asset={child.asset} children={children} interfaceIp={interfaceIp} seen={nextSeen} /></div>)}</div>;
}

function RelationshipGraph({ data, assets, relationships, assetsById }) {
  const interfaceIp = primaryInterfaceIps(data.asset_interfaces);
  return <div className="relationship-graph"><div className="graph-nodes">{assets.map((asset) => <AssetNode asset={asset} interfaceIp={interfaceIp[asset.id]} key={asset.id} />)}</div><div className="graph-edges"><h2>Relationship edges</h2>{relationships.length === 0 ? <p className="secondary-text">No relationships between the visible assets.</p> : relationships.map((edge) => <div className="graph-edge" key={edge.id}><strong>{edge.source_asset_name || assetsById[edge.source_asset_id]?.name}</strong><span>→ {taxonomyLabel(edge.relationship_type)} →</span><strong>{edge.target_asset_name || assetsById[edge.target_asset_id]?.name}</strong></div>)}</div></div>;
}

function NetworkGraph({ data, assets, visibleIds, filters }) {
  const interfaces = data.asset_interfaces.filter((item) => visibleIds.has(item.asset_id));
  const interfacesByNetwork = interfaces.reduce((groups, item) => {
    if (item.network_id) (groups[item.network_id] ||= []).push(item);
    return groups;
  }, {});
  const assignedAssetIds = new Set(interfaces.map((item) => item.asset_id));
  const networks = data.networks.filter((network) =>
    (!filters.customer || network.customer_id === filters.customer)
    && (!filters.site || network.site_id === filters.site || !network.site_id)
  );
  const assetsById = Object.fromEntries(assets.map((asset) => [asset.id, asset]));
  const unassigned = assets.filter((asset) => !assignedAssetIds.has(asset.id));
  const unassignedInterfaces = interfaces.filter((item) => !item.network_id);

  return <div className="network-groups">
    {networks.map((network) => {
      const members = interfacesByNetwork[network.id] || [];
      return <section className="network-group" key={network.id}>
        <div className="network-group-header"><div><p className="eyebrow">{network.network_type}</p><h2>{network.vlan_id !== null ? `VLAN ${network.vlan_id} — ` : ""}{network.name}{network.cidr ? ` — ${network.cidr}` : ""}</h2></div><span>{network.gateway ? `Gateway ${network.gateway}` : "No gateway"}</span></div>
        {members.length === 0 ? <p className="secondary-text">No interfaces assigned.</p> : <div className="network-members">{members.map((item) => <NetworkMember asset={assetsById[item.asset_id]} interfaceRecord={item} key={item.id} />)}</div>}
      </section>;
    })}
    {(unassigned.length > 0 || unassignedInterfaces.length > 0) && <section className="network-group network-unassigned"><div className="network-group-header"><div><p className="eyebrow">Unassigned</p><h2>Unassigned network</h2></div><span>Explicit network membership required</span></div><div className="network-members">{unassignedInterfaces.map((item) => <NetworkMember asset={assetsById[item.asset_id]} interfaceRecord={item} key={item.id} />)}{unassigned.map((asset) => <NetworkMember asset={asset} interfaceRecord={{ name: "No interface", ip_address: null }} key={asset.id} />)}</div></section>}
  </div>;
}

function NetworkMember({ asset, interfaceRecord }) {
  if (!asset) return null;
  return <Link className="network-member" href={`/assets/${asset.id}`}><strong>{asset.name}</strong><span>{taxonomyLabel(asset.asset_type)}</span><span>{asset.hostname || "No hostname"}</span><span>{interfaceRecord.name} · {interfaceRecord.ip_address || "No interface IP"}</span></Link>;
}

function primaryInterfaceIps(interfaces) {
  const grouped = interfaces.reduce((result, item) => {
    if (item.ip_address) (result[item.asset_id] ||= []).push(item);
    return result;
  }, {});
  return Object.fromEntries(Object.entries(grouped).map(([assetId, items]) => [
    assetId,
    (items.find((item) => item.is_primary) || items[0]).ip_address,
  ]));
}

function AssetNode({ asset, interfaceIp }) {
  return <Link className="asset-node" href={`/assets/${asset.id}`}><span className="asset-node-heading"><strong>{asset.name}</strong><StatusBadge status={asset.status} /></span><span>{taxonomyLabel(asset.asset_type)}</span><small>{interfaceIp || asset.hostname || "No interface IP"}</small></Link>;
}
