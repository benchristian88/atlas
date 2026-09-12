"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AccessDenied } from "../../components/access-denied";
import { AssetIcon } from "../../components/asset-icon";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { StatusBadge } from "../../components/status-badge";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";
import { taxonomyLabel } from "../../lib/taxonomy";

const lenses = {
  physical: { label: "Physical", description: "Physical hosts and network hardware connectivity." },
  platform: { label: "Platform", description: "Virtualisation, hosting, and workload containment." },
  networks: { label: "Network / VLAN", description: "Explicit interface membership across networks and VLANs." },
  dependency: { label: "Dependency", description: "Operational dependencies between applications, services, and infrastructure." },
  all: { label: "All relationships", description: "Every recorded relationship for advanced inspection and debugging." },
};
const physicalAssetTypes = new Set(["firewall", "router", "switch", "access_point", "nas", "backup_target", "proxmox_host", "physical_server", "docker_host"]);
const physicalRelationships = new Set(["connects_to", "uplinks_to", "connected_via"]);
const platformAssetTypes = new Set(["proxmox_cluster", "proxmox_host", "virtual_machine", "lxc_container", "docker_host", "docker_container", "application", "database", "service"]);
const platformRelationships = new Set(["member_of", "hosts", "runs_on", "runs", "contains"]);
const dependencyAssetTypes = new Set(["application", "service", "database", "docker_container", "virtual_machine", "lxc_container", "nas", "backup_target", "firewall", "proxy"]);
const dependencyRelationships = new Set(["depends_on", "proxies", "authenticates", "exposes", "backs_up_to", "monitors", "uses_storage", "protects", "protected_by", "served_by"]);

export default function TopologyPage() {
  const { hasPermission, hasPermissionInContext } = useAuth();
  const workspace = useWorkspaceContext();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [mode, setMode] = useState("physical");
  const [filters, setFilters] = useState({ customer: "", site: "", assetType: "", relationshipType: "", focusAsset: "" });
  const canView = hasPermissionInContext("assets.view", workspace.customerId, workspace.siteId);

  useEffect(() => {
    if (!canView) return;
    let active = true;
    setData(null);
    setError("");
    Promise.all([
      apiRequest("/topology"),
      optionalReferenceData("/asset-types", hasPermission("asset_types.view")),
      optionalReferenceData("/relationship-types", hasPermission("relationship_types.view")),
    ]).then(([topology, assetTypeDefinitions, relationshipTypeDefinitions]) => {
      if (active) setData({ ...topology, assetTypeDefinitions, relationshipTypeDefinitions });
    }).catch((requestError) => {
      if (active) setError(requestError.message || "Atlas could not load the topology.");
    });
    return () => { active = false; };
  }, [canView, hasPermission, workspace.reloadKey]);

  const assetsById = useMemo(() => Object.fromEntries((data?.assets || []).map((asset) => [asset.id, asset])), [data]);
  const assetTypeDefinitions = useMemo(() => Object.fromEntries(
    (data?.assetTypeDefinitions || []).map((type) => [type.key, type]),
  ), [data]);
  const relationshipTypeDefinitions = useMemo(() => Object.fromEntries(
    (data?.relationshipTypeDefinitions || []).map((type) => [type.key, type]),
  ), [data]);
  const assetTypes = useMemo(() => [...new Set((data?.assets || []).map((asset) => asset.asset_type))].sort(), [data]);
  const relationshipTypes = useMemo(() => [...new Set((data?.relationships || []).map((edge) => edge.relationship_type))].sort(), [data]);
  const filtered = useMemo(() => {
    if (!data) return { assets: [], relationships: [] };
    let assets = data.assets.filter((asset) =>
      (!filters.customer || asset.customer_id === filters.customer)
      && (!filters.site || asset.site_id === filters.site)
      && (!filters.assetType || asset.asset_type === filters.assetType)
    );
    let ids = new Set(assets.map((asset) => asset.id));
    let relationships = data.relationships.filter((edge) => ids.has(edge.source_asset_id) && ids.has(edge.target_asset_id));
    if (filters.focusAsset && ids.has(filters.focusAsset)) {
      const focusIds = new Set([filters.focusAsset]);
      for (const edge of relationships) {
        if (edge.source_asset_id === filters.focusAsset) focusIds.add(edge.target_asset_id);
        if (edge.target_asset_id === filters.focusAsset) focusIds.add(edge.source_asset_id);
      }
      assets = assets.filter((asset) => focusIds.has(asset.id));
      ids = focusIds;
      relationships = relationships.filter((edge) => ids.has(edge.source_asset_id) && ids.has(edge.target_asset_id));
    }
    if (filters.relationshipType) relationships = relationships.filter((edge) => edge.relationship_type === filters.relationshipType);
    return { assets, relationships };
  }, [data, filters]);

  function updateFilter(name, value) {
    setFilters((current) => ({
      ...current,
      [name]: value,
      ...(["customer", "site", "assetType"].includes(name) ? { focusAsset: "" } : {}),
      ...(name === "customer" ? { site: "" } : {}),
    }));
  }

  if (!canView) return <AccessDenied />;
  return <>
    <PageHeader eyebrow="Knowledge" title="Knowledge Graph" description="Explore recorded infrastructure and dependency relationships through focused topology lenses." />
    {error && <div className="error-banner" role="alert">{error}</div>}
    {!data && !error && <div className="status-banner" role="status">Loading topology…</div>}
    {data && <>
      <div className="topology-workbench">
        <div className="lens-selector" aria-label="Topology lens">{Object.entries(lenses).map(([key, lens]) => <button className={`button selector-control-text ${mode === key ? "button-primary" : "button-secondary"}`} key={key} onClick={() => setMode(key)} type="button">{lens.label}</button>)}</div>
        <p className="lens-description">{lenses[mode].description}</p>
        <div className="topology-filters topology-filters-wide">
          <Filter label="Customer" value={filters.customer} onChange={(value) => updateFilter("customer", value)} options={data.customers.map((item) => [item.id, item.name])} emptyLabel="All customers" />
          <Filter label="Site" value={filters.site} onChange={(value) => updateFilter("site", value)} options={data.sites.filter((item) => !filters.customer || item.customer_id === filters.customer).map((item) => [item.id, item.name])} emptyLabel="All sites" />
          <Filter label="Asset type" value={filters.assetType} onChange={(value) => updateFilter("assetType", value)} options={assetTypes.map((value) => [value, managedTypeName(assetTypeDefinitions, value)])} emptyLabel="All asset types" />
          <Filter label="Relationship" value={filters.relationshipType} onChange={(value) => updateFilter("relationshipType", value)} options={relationshipTypes.map((value) => [value, managedTypeName(relationshipTypeDefinitions, value)])} emptyLabel="All relationship types" />
          <label className="field"><span>Focus asset</span><div className="focus-control"><select value={filters.focusAsset} onChange={(event) => updateFilter("focusAsset", event.target.value)}><option value="">No focus</option>{data.assets.filter((asset) => (!filters.customer || asset.customer_id === filters.customer) && (!filters.site || asset.site_id === filters.site) && (!filters.assetType || asset.asset_type === filters.assetType)).map((asset) => <option key={asset.id} value={asset.id}>{asset.name}</option>)}</select>{filters.focusAsset && <button className="text-button" onClick={() => updateFilter("focusAsset", "")} type="button">Clear</button>}</div></label>
        </div>
      </div>
      {data.assets.length === 0 && <div className="topology-empty"><h2>Start modelling your infrastructure</h2><p>Create customers, sites, assets, interfaces, and relationships to use topology lenses.</p><Link className="button button-primary" href="/assets">{hasPermissionInContext("assets.create", workspace.customerId, workspace.siteId) ? "Create asset" : "View assets"}</Link></div>}
      {data.assets.length > 0 && <Lens mode={mode} data={data} assets={filtered.assets} relationships={filtered.relationships} assetsById={assetsById} assetTypeDefinitions={assetTypeDefinitions} relationshipTypeDefinitions={relationshipTypeDefinitions} filters={filters} />}
    </>}
  </>;
}

async function optionalReferenceData(endpoint, allowed) {
  if (!allowed) return [];
  try {
    return await apiRequest(endpoint);
  } catch {
    return [];
  }
}

function managedTypeName(definitions, key) {
  return definitions[key]?.name || taxonomyLabel(key);
}

function relationshipLabel(definitions, key, reverse = false) {
  const definition = definitions[key];
  if (!definition) return taxonomyLabel(key);
  if (reverse) return definition.target_label || definition.inverse_label || definition.name;
  return definition.source_label || definition.name;
}

function Filter({ label, value, onChange, options, emptyLabel }) {
  return <label className="field"><span>{label}</span><select value={value} onChange={(event) => onChange(event.target.value)}><option value="">{emptyLabel}</option>{options.map(([optionValue, optionLabel]) => <option key={optionValue} value={optionValue}>{optionLabel}</option>)}</select></label>;
}

function Lens({ mode, data, assets, relationships, assetsById, assetTypeDefinitions, relationshipTypeDefinitions, filters }) {
  if (mode === "networks") return assets.length ? <NetworkGraph data={data} assets={assets} assetTypeDefinitions={assetTypeDefinitions} filters={filters} /> : <LensEmpty mode={mode} />;
  let allowedAssets;
  let allowedRelationships;
  if (mode === "physical") [allowedAssets, allowedRelationships] = [physicalAssetTypes, physicalRelationships];
  if (mode === "platform") [allowedAssets, allowedRelationships] = [platformAssetTypes, platformRelationships];
  if (mode === "dependency") [allowedAssets, allowedRelationships] = [dependencyAssetTypes, dependencyRelationships];
  const lensAssets = allowedAssets ? assets.filter((asset) => {
    if (!allowedAssets.has(asset.asset_type)) return false;
    if (mode === "physical" && asset.asset_type === "docker_host") {
      return !data.relationships.some((edge) => edge.source_asset_id === asset.id && edge.relationship_type === "runs_on");
    }
    return true;
  }) : assets;
  const ids = new Set(lensAssets.map((asset) => asset.id));
  const lensRelationships = relationships.filter((edge) =>
    ids.has(edge.source_asset_id) && ids.has(edge.target_asset_id)
    && (!allowedRelationships || allowedRelationships.has(edge.relationship_type))
  );
  if (!lensAssets.length) return <LensEmpty mode={mode} />;
  if (mode === "platform") return <PlatformView data={data} assets={lensAssets} relationships={lensRelationships} assetsById={assetsById} assetTypeDefinitions={assetTypeDefinitions} relationshipTypeDefinitions={relationshipTypeDefinitions} filters={filters} />;
  const workloadCounts = mode === "physical" ? physicalWorkloadCounts(data.relationships) : {};
  return <>{mode === "all" && <div className="warning-banner">This view can become busy. Use filters or focus mode to narrow the graph.</div>}<RelationshipGraph data={data} assets={lensAssets} relationships={lensRelationships} assetsById={assetsById} assetTypeDefinitions={assetTypeDefinitions} relationshipTypeDefinitions={relationshipTypeDefinitions} workloadCounts={workloadCounts} /></>;
}

function LensEmpty({ mode }) {
  return <div className="empty-state detail-card">No {lenses[mode].label.toLowerCase()} topology matches the current filters.</div>;
}

function physicalWorkloadCounts(relationships) {
  const counts = {};
  for (const edge of relationships) {
    let parent;
    if (edge.relationship_type === "runs_on" || edge.relationship_type === "member_of") parent = edge.target_asset_id;
    if (["hosts", "contains", "runs"].includes(edge.relationship_type)) parent = edge.source_asset_id;
    if (parent) counts[parent] = (counts[parent] || 0) + 1;
  }
  return counts;
}

function PlatformView({ data, assets, relationships, assetsById, assetTypeDefinitions, relationshipTypeDefinitions }) {
  const interfaceIp = primaryInterfaceIps(data.asset_interfaces);
  const childIds = new Set();
  const children = {};
  for (const edge of relationships) {
    let parentId;
    let childId;
    let reverse = false;
    if (["runs_on", "member_of"].includes(edge.relationship_type)) {
      [childId, parentId] = [edge.source_asset_id, edge.target_asset_id];
      reverse = true;
    }
    if (["hosts", "contains", "runs"].includes(edge.relationship_type)) [parentId, childId] = [edge.source_asset_id, edge.target_asset_id];
    if (parentId && childId) { (children[parentId] ||= []).push({ asset: assetsById[childId], label: relationshipLabel(relationshipTypeDefinitions, edge.relationship_type, reverse) }); childIds.add(childId); }
  }
  const roots = assets.filter((asset) => !childIds.has(asset.id));
  return <div className="platform-lanes">{roots.map((asset) => <PlatformNode asset={asset} assetTypeDefinitions={assetTypeDefinitions} children={children} interfaceIp={interfaceIp} key={asset.id} seen={new Set()} />)}{roots.length === 0 && <LensEmpty mode="platform" />}</div>;
}

function PlatformNode({ asset, assetTypeDefinitions, children, interfaceIp, seen }) {
  if (!asset || seen.has(asset.id)) return null;
  const nextSeen = new Set(seen).add(asset.id);
  return <div className="platform-node"><AssetNode asset={asset} assetTypeDefinitions={assetTypeDefinitions} interfaceIp={interfaceIp[asset.id]} />{(children[asset.id] || []).map((child) => <div className="platform-child" key={`${asset.id}-${child.asset?.id}`}><span className="edge-label">{child.label}</span><PlatformNode asset={child.asset} assetTypeDefinitions={assetTypeDefinitions} children={children} interfaceIp={interfaceIp} seen={nextSeen} /></div>)}</div>;
}

function RelationshipGraph({ data, assets, relationships, assetsById, assetTypeDefinitions, relationshipTypeDefinitions, workloadCounts = {} }) {
  const interfaceIp = primaryInterfaceIps(data.asset_interfaces);
  return <div className="relationship-graph"><div className="graph-nodes">{assets.map((asset) => <AssetNode asset={asset} assetTypeDefinitions={assetTypeDefinitions} interfaceIp={interfaceIp[asset.id]} key={asset.id} workloadCount={workloadCounts[asset.id]} />)}</div><div className="graph-edges"><h2>Relationship edges</h2>{relationships.length === 0 ? <p className="secondary-text">No matching relationships between these assets.</p> : relationships.map((edge) => { const definition = relationshipTypeDefinitions[edge.relationship_type]; const connector = definition?.directional === false ? "↔" : "→"; return <div className="graph-edge" key={edge.id}><strong>{edge.source_asset_name || assetsById[edge.source_asset_id]?.name}</strong><span>{connector} {relationshipLabel(relationshipTypeDefinitions, edge.relationship_type)} {connector}</span><strong>{edge.target_asset_name || assetsById[edge.target_asset_id]?.name}</strong></div>; })}</div></div>;
}

function NetworkGraph({ data, assets, assetTypeDefinitions, filters }) {
  const visibleIds = new Set(assets.map((asset) => asset.id));
  const interfaces = data.asset_interfaces.filter((item) => visibleIds.has(item.asset_id));
  const grouped = interfaces.reduce((result, item) => { if (item.network_id) (result[item.network_id] ||= []).push(item); return result; }, {});
  const assignedIds = new Set(interfaces.map((item) => item.asset_id));
  const assetsById = Object.fromEntries(assets.map((asset) => [asset.id, asset]));
  const networks = data.networks.filter((network) => (!filters.customer || network.customer_id === filters.customer) && (!filters.site || !network.site_id || network.site_id === filters.site));
  const unassignedAssets = assets.filter((asset) => !assignedIds.has(asset.id));
  const unassignedInterfaces = interfaces.filter((item) => !item.network_id);
  return <div className="network-groups">{networks.map((network) => <section className="network-group" key={network.id}><NetworkHeader network={network} />{(grouped[network.id] || []).length ? <div className="network-members">{grouped[network.id].map((item) => <NetworkMember asset={assetsById[item.asset_id]} assetTypeDefinitions={assetTypeDefinitions} interfaceRecord={item} key={item.id} />)}</div> : <p className="secondary-text">No interfaces assigned.</p>}</section>)}{(unassignedAssets.length > 0 || unassignedInterfaces.length > 0) && <section className="network-group network-unassigned"><div className="network-group-header"><div><p className="eyebrow">Unassigned</p><h2>Unassigned network</h2></div><span>Explicit interface membership required</span></div><div className="network-members">{unassignedInterfaces.map((item) => <NetworkMember asset={assetsById[item.asset_id]} assetTypeDefinitions={assetTypeDefinitions} interfaceRecord={item} key={item.id} />)}{unassignedAssets.map((asset) => <NetworkMember asset={asset} assetTypeDefinitions={assetTypeDefinitions} interfaceRecord={{ name: "No interface", ip_address: null }} key={asset.id} />)}</div></section>}</div>;
}

function NetworkHeader({ network }) {
  return <div className="network-group-header"><div><p className="eyebrow">{network.network_type}</p><h2>{network.vlan_id !== null ? `VLAN ${network.vlan_id} — ` : ""}{network.name}{network.cidr ? ` — ${network.cidr}` : ""}</h2></div><span>{network.gateway ? `Gateway ${network.gateway}` : "No gateway"}</span></div>;
}

function NetworkMember({ asset, assetTypeDefinitions, interfaceRecord }) {
  if (!asset) return null;
  return <Link className="network-member" href={`/assets/${asset.id}`}><span className="asset-inline-identity"><AssetIcon asset={asset} size={30} /><strong>{asset.name}</strong></span><span>{managedTypeName(assetTypeDefinitions, asset.asset_type)}</span><span>{asset.hostname || "No hostname"}</span><span>{interfaceRecord.name} · {interfaceRecord.ip_address || "No interface IP"}</span></Link>;
}

function primaryInterfaceIps(interfaces) {
  const grouped = interfaces.reduce((result, item) => { if (item.ip_address) (result[item.asset_id] ||= []).push(item); return result; }, {});
  return Object.fromEntries(Object.entries(grouped).map(([assetId, items]) => [assetId, (items.find((item) => item.is_primary) || items[0]).ip_address]));
}

function AssetNode({ asset, assetTypeDefinitions, interfaceIp, workloadCount }) {
  return <Link className="asset-node" href={`/assets/${asset.id}`}><span className="asset-node-heading"><span className="asset-inline-identity"><AssetIcon asset={asset} size={32} /><strong>{asset.name}</strong></span><StatusBadge status={asset.status} /></span><span>{managedTypeName(assetTypeDefinitions, asset.asset_type)}</span><small>{interfaceIp || asset.ip_address || asset.hostname || "No interface IP"}</small>{workloadCount ? <span className="workload-badge">{workloadCount} workload{workloadCount === 1 ? "" : "s"}</span> : null}</Link>;
}
