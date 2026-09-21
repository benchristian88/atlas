"use client";

import Link from "next/link";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { AccessDenied } from "../../components/access-denied";
import { AssetIcon } from "../../components/asset-icon";
import { useAuth } from "../../components/auth-context";
import { ExpandedGraphSurface } from "../../components/expanded-graph-surface";
import { NavigationIcon } from "../../components/navigation-icon.mjs";
import { assetListFiltersHref } from "../../lib/asset-list-filters.mjs";
import { PageHeader } from "../../components/page-header";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";
import { topologyPresentation, platformMatches, matchesSearch, CHILD_PREVIEW_COUNT, CATEGORY_PREVIEW_COUNT, CONNECTIVITY_NODE_WIDTH, CONNECTIVITY_NODE_HEIGHT, connectivityLayout } from "../../lib/infrastructure-topology.mjs";

import { PresentationIdentity, PresentationIcon } from "../../components/presentation-identity.mjs";
import { presentationAttributes } from "../../lib/presentation.mjs";

const tabs = { overview: "Overview", platform: "Platform", networks: "Network & VLAN", connectivity: "Connectivity" };

export default function TopologyPage() {
  const workspace = useWorkspaceContext();
  return <TopologyWorkbench key={workspace.reloadKey} />;
}

function TopologyWorkbench() {
  const { hasPermissionInContext } = useAuth();
  const workspace = useWorkspaceContext();
  const canView = hasPermissionInContext("assets.view", workspace.customerId, workspace.siteId);
  const [data, setData] = useState(null), [error, setError] = useState("");
  const [reload, setReload] = useState(0), [tab, setTab] = useState("overview");
  const [choices, setChoices] = useState({}), [filtersOpen, setFiltersOpen] = useState(false);
  const [search, setSearch] = useState(""), [selectedId, setSelectedId] = useState("");
  const [networkId, setNetworkId] = useState(""), [parentId, setParentId] = useState("");
  const [expandedParents, setExpandedParents] = useState({});
  const [focusId, setFocusId] = useState(""), [hops, setHops] = useState(1), [showNetworks, setShowNetworks] = useState(true);
  const [graph, setGraph] = useState(null), [graphError, setGraphError] = useState("");
  const [expanded, setExpanded] = useState(false);
  const expandButton = useRef(null), scrollPosition = useRef({ left: 0, top: 0 });

  useEffect(() => {
    if (!canView) return;
    let active = true;
    setData(null); setError(""); setGraph(null);
    apiRequest("/topology").then(value => { if (active) setData(value); }).catch(e => { if (active) setError(e.message || "Unable to load topology."); });
    return () => { active = false; };
  }, [canView, workspace.reloadKey, reload]);
  const enabled = useMemo(() => new Set((data?.categories || []).filter(c => choices[c.id] ?? c.show_in_topology).map(c => c.id)), [data, choices]);
  const view = useMemo(() => data ? topologyPresentation(data, enabled) : null, [data, enabled]);
  const networkFocus = Boolean(view?.assets.length) && showNetworks && focusId.startsWith("network:") && view?.networks.some(n => `network:${n.id}` === focusId);
  const actualFocus = networkFocus || view?.byId[focusId] ? focusId : view?.assets[0]?.id || "";
  const categoryKey = [...enabled].sort().join(",");
  const graphKey = `${actualFocus}/${hops}/${showNetworks}/${categoryKey}`;
  const currentGraph = graph?.requestKey === graphKey ? graph : null;
  useEffect(() => {
    if (tab !== "connectivity" || !actualFocus || !data) { setGraph(null); return; }
    let active = true;
    setGraph(null); setGraphError("");
    const params = new URLSearchParams({ [networkFocus ? "focus_network_id" : "focus_asset_id"]: networkFocus ? actualFocus.slice(8) : actualFocus, hops: String(hops), show_networks: String(showNetworks), limit: "25" });
    categoryKey.split(",").filter(Boolean).forEach(id => params.append("category_ids", id));
    apiRequest(`/topology/connectivity?${params}`).then(value => { if (active) setGraph({ ...value, requestKey: graphKey }); }).catch(e => { if (active) setGraphError(e.message || "Unable to load connectivity."); });
    return () => { active = false; };
  }, [tab, actualFocus, hops, showNetworks, categoryKey, graphKey, data, networkFocus]);

  if (!canView) return <AccessDenied />;
  const selectionInView = tab !== "connectivity" || currentGraph?.nodes.some(node => node.key === `asset:${selectedId}`);
  const selected = tab === "overview" ? null : (selectionInView ? view?.byId[selectedId] : null) || (tab === "connectivity" ? view?.byId[actualFocus] : null);
  const select = asset => {
    setSelectedId(asset.id);
    if (tab === "connectivity" && !currentGraph?.nodes.some(node => node.key === `asset:${asset.id}`)) setFocusId(asset.id);
  };
  const network = view?.networks.find(n => n.id === networkId) || view?.networks[0];
  const openNetwork = id => { setNetworkId(id); setTab("networks"); };
  return <div className="operations-page infrastructure-topology">
    <PageHeader eyebrow="Knowledge" title="Infrastructure Topology" description="Visualise your infrastructure, networks and connectivity." />
    <ExpandedGraphSurface title="Infrastructure Topology" expanded={expanded} onClose={() => setExpanded(false)} returnFocus={expandButton} scrollPosition={scrollPosition}>
      <div className="topology-toolbar">
        <div className="lens-selector" aria-label="Topology views">{Object.entries(tabs).map(([key, label]) => <button key={key} type="button" aria-pressed={tab === key} className={`button selector-control-text ${tab === key ? "button-primary" : "button-secondary"}`} onClick={() => { setTab(key); setSelectedId(""); }}>{label}</button>)}</div>
        <div className="row-actions"><button type="button" className="button button-secondary" aria-expanded={filtersOpen} onClick={() => setFiltersOpen(!filtersOpen)}>Filters</button><button type="button" className="text-button" onClick={() => setReload(n => n + 1)}>Refresh</button>{!expanded && <button ref={expandButton} type="button" className="button button-secondary graph-icon-button" title="Expand Infrastructure Topology" aria-label="Expand Infrastructure Topology" onClick={() => { scrollPosition.current = { left: window.scrollX, top: window.scrollY }; setExpanded(true); }}><NavigationIcon name="expand" /></button>}</div>
      </div>
      {filtersOpen && data && <fieldset className="topology-category-filters"><legend>Asset Categories</legend>{data.categories.map(category => <label key={category.id} {...presentationAttributes(category)}><input type="checkbox" checked={enabled.has(category.id)} onChange={event => setChoices(current => ({ ...current, [category.id]: event.target.checked }))} /><PresentationIdentity record={category} />{!category.active && <small> (inactive)</small>}</label>)}</fieldset>}
      {error && <p className="error-banner" role="alert">{error}</p>}
      {!data && !error && <p role="status">Loading infrastructure…</p>}
      {data && <>
        <div className="topology-context ops-meta">{workspace.customers.find(c => c.id === workspace.customerId)?.name || "Authorized customers"} · {workspace.sites.find(s => s.id === workspace.siteId)?.name || "Authorized sites"} · Recorded knowledge</div>
        {tab !== "overview" && <label className="field topology-search"><span>{tab === "networks" ? "Search Networks and connected Assets" : "Search Assets"}</span><input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder={tab === "networks" ? "Network, VLAN or Asset name" : "Asset name, hostname or IP"} /></label>}
        {tab === "overview" ? <Overview view={view} onNetwork={openNetwork} /> :
          tab === "networks" ? <Networks view={view} network={network} search={search} onNetwork={setNetworkId} select={select} sites={data.sites} /> :
          tab === "platform" ? <Platform view={view} search={search} parentId={parentId} onParent={setParentId} expandedParents={expandedParents} onExpand={id => setExpandedParents(p => ({ ...p, [id]: !p[id] }))} select={select} /> :
          <>
            <div className="topology-connectivity-controls"><label className="field"><span>Focus Asset or Network</span><select aria-label="Focus Asset or Network" value={actualFocus} onChange={e => { setFocusId(e.target.value); setSelectedId(e.target.value); }}>{view.assets.filter(a => a.id === actualFocus || matchesSearch(a, search)).map(a => <option key={a.id} value={a.id}>{a.name}</option>)}{showNetworks && view.networks.map(n => <option key={`network:${n.id}`} value={`network:${n.id}`}>{n.name} (Network)</option>)}</select></label><div className="row-actions" aria-label="Hops">{[1, 2].map(n => <button type="button" key={n} aria-pressed={hops === n} className={`button ${hops === n ? "button-primary" : "button-secondary"}`} onClick={() => setHops(n)}>{n} {n === 1 ? "hop" : "hops"}</button>)}</div><label><input type="checkbox" checked={showNetworks} onChange={e => setShowNetworks(e.target.checked)} /> Networks</label></div>
            {graphError && <p className="error-banner" role="alert">{graphError}</p>}
            {!actualFocus ? <p className="empty-state">Enable a category with Assets to explore connectivity.</p> : !currentGraph && !graphError ? <p role="status">Loading recorded connectivity…</p> : currentGraph && <div className="graph-workspace"><Connectivity expanded={expanded} filtersOpen={filtersOpen} graph={currentGraph} view={view} selected={selected} select={select} onNetwork={id => { setFocusId(`network:${id}`); setSelectedId(""); }} />{networkFocus && !selected ? <aside className="ops-card graph-inspector"><h2><PresentationIdentity record={view.networkById[actualFocus.slice(8)]} fallback="network" /></h2><p>{view.interfaces.filter(i => `network:${i.network_id}` === actualFocus).length} recorded interfaces</p><button type="button" className="button button-secondary" onClick={() => openNetwork(actualFocus.slice(8))}>Open Network detail</button></aside> : <Inspector asset={selected} view={view} sites={data.sites} select={select} onFocus={a => { setFocusId(a.id); setSelectedId(a.id); }} />}</div>}
          </>}
        {tab !== "overview" && tab !== "connectivity" && selected && <div className="topology-detail-inspector"><button type="button" className="text-button" onClick={() => setSelectedId("")}>Close details</button><Inspector asset={selected} view={view} sites={data.sites} select={select} onFocus={a => { setFocusId(a.id); setTab("connectivity"); }} /></div>}
        {view.assets.length === 0 && tab !== "connectivity" && <p className="empty-state">No Assets match the enabled categories. Use Filters to include other categories, or <Link href="/assets">open Assets</Link> to curate your infrastructure.</p>}
      </>}
    </ExpandedGraphSurface>
  </div>;
}

function Identity({ asset, view, select, compact = false }) {
  return <button type="button" className={`topology-asset-identity${compact ? " compact" : ""}`} onClick={() => select(asset)}><AssetIcon asset={asset} assetType={view.types[asset.asset_type]} size={compact ? 26 : 34} /><span><strong>{asset.name}</strong><small>{view.types[asset.asset_type]?.name}</small>{asset.display_ip && <small>{asset.display_ip}</small>}{!compact && <small>Recorded: {asset.status}</small>}</span></button>;
}

function Overview({ view, onNetwork }) {
  const metrics = [["Assets", view.assets.length, "server", "blue"], ["Networks / VLANs", view.networks.length, "network", "cyan"], ["Interfaces", view.interfaces.length, "bridge", "teal"], ["Categories represented", view.categories.filter(c => view.assets.some(a => view.types[a.asset_type]?.category_id === c.id)).length, "application", "purple"]];
  return <><div className="topology-metrics">{metrics.map(([label, count, icon_key, accent_key]) => <div className="ops-card" key={label}><span className="presentation-identity"><PresentationIcon record={{ icon_key, accent_key }} />{label}</span><strong>{count}</strong></div>)}</div><div className="topology-overview-columns"><section className="ops-card"><h2>Environment at a glance</h2>{view.categories.map(category => {
    const assets = view.assets.filter(a => view.types[a.asset_type]?.category_id === category.id);
    const hidden = Math.max(0, assets.length - CATEGORY_PREVIEW_COUNT);
    const href = assetListFiltersHref({ categoryId: category.id });
    return <div key={category.id} className="topology-summary-row" {...presentationAttributes(category)}><div><strong><PresentationIdentity record={category} /></strong><small>{assets.length} Assets · {new Set(assets.map(a => a.asset_type)).size} Asset Types</small><Link className="text-button" href={href} aria-label={`View all ${category.name} Assets`}>View all</Link></div><div className="topology-summary-icons">{assets.slice(0, CATEGORY_PREVIEW_COUNT).map(asset => <Link key={asset.id} href={`/assets/${asset.id}`} title={asset.name} aria-label={`Open ${asset.name}`}><AssetIcon asset={asset} assetType={view.types[asset.asset_type]} size={26} /></Link>)}{hidden > 0 && <Link href={href} className="topology-preview-more" aria-label={`${hidden} more ${category.name} Assets`}>+{hidden}</Link>}</div></div>;
  })}</section><section className="ops-card"><h2>Recorded Networks</h2>{view.networks.slice(0, 8).map(n => <button className="topology-network-row" {...presentationAttributes(n)} key={n.id} type="button" onClick={() => onNetwork(n.id)}><strong><PresentationIdentity record={n} fallback="network" /></strong><span>{[n.vlan_id != null ? `VLAN ${n.vlan_id}` : null, n.cidr].filter(Boolean).join(" · ")}</span><small>{view.interfaces.filter(i => i.network_id === n.id).length} interfaces</small></button>)}{view.networks.length > 8 && <button type="button" className="text-button" onClick={() => onNetwork(view.networks[0].id)}>View all {view.networks.length} Networks</button>}{!view.networks.length && <p className="ops-meta">No visible Networks recorded.</p>}</section></div></>;
}

function Platform({ view, search, parentId, onParent, expandedParents, onExpand, select }) {
  const focused = view.byId[parentId];
  const roots = (focused ? [focused] : view.roots).filter(a => platformMatches(a, view.children, search));
  return <>{focused && <button type="button" className="button button-secondary" onClick={() => onParent("")}>All platform Assets</button>}{view.categories.map(category => { const assets = roots.filter(a => view.types[a.asset_type]?.category_id === category.id); if (!assets.length) return null; return <section className="topology-platform-section" key={category.id}><h2 {...presentationAttributes(category)}><PresentationIdentity record={category} /> <small>{assets.length}</small></h2><div className="topology-platform-grid">{assets.map(asset => { const children = view.children[asset.id]; const matchingChildren = search && !matchesSearch(asset, search) ? children.filter(child => platformMatches(child, view.children, search)) : children; const displayed = expandedParents[asset.id] ? matchingChildren : matchingChildren.slice(0, CHILD_PREVIEW_COUNT); const interfaces = view.interfaces.filter(i => i.asset_id === asset.id); const networks = view.networks.filter(n => interfaces.some(i => i.network_id === n.id)); return <article className="ops-card topology-platform-card" key={asset.id} data-platform-id={asset.id} {...presentationAttributes(asset.presentation)}><Identity asset={asset} view={view} select={select} />{view.cycleRoots.has(asset.id) && <p className="ops-meta">Recorded platform cycle</p>}<p className="ops-meta">{children.length} hosted / contained Assets · {interfaces.length} interfaces</p>{networks.length > 0 && <p className="ops-meta">{networks.map(n => n.name).join(" · ")}</p>}{children.length > 0 && <><div className="topology-children">{displayed.map(child => <div key={child.id} className="topology-child" {...presentationAttributes(child.presentation)}><Identity compact asset={child} view={view} select={select} /><small>Recorded: {child.status}</small>{view.children[child.id]?.length > 0 && <button type="button" className="text-button" onClick={() => onParent(child.id)}>View platform ({view.children[child.id].length})</button>}</div>)}</div>{matchingChildren.length > CHILD_PREVIEW_COUNT && <button type="button" className="text-button" onClick={() => onExpand(asset.id)}>{expandedParents[asset.id] ? "Show fewer" : `Show all ${matchingChildren.length} (+${matchingChildren.length - CHILD_PREVIEW_COUNT} more)`}</button>}</>}</article>; })}</div></section>; })}{!roots.length && view.assets.length > 0 && <p className="empty-state">No platform Assets match this search.</p>}</>;
}

function Networks({ view, network, search, onNetwork, select, sites }) {
  const networks = view.networks.filter(n => [n.name, n.cidr, n.vlan_id].join(" ").toLowerCase().includes(search.toLowerCase()) || view.interfaces.some(i => i.network_id === n.id && matchesSearch(view.byId[i.asset_id], search)));
  const selected = networks.find(n => n.id === network?.id) || networks[0];
  const members = view.interfaces.filter(i => i.network_id === selected?.id);
  return <div className="topology-network-layout"><nav className="ops-card topology-network-list" aria-label="Networks">{networks.map(n => <button key={n.id} type="button" aria-current={selected?.id === n.id ? "true" : undefined} className="topology-network-row" {...presentationAttributes(n)} onClick={() => onNetwork(n.id)}><strong><PresentationIdentity record={n} fallback="network" /></strong><span>{[n.vlan_id != null ? `VLAN ${n.vlan_id}` : null, n.cidr].filter(Boolean).join(" · ")}</span><small>{view.interfaces.filter(i => i.network_id === n.id).length} interfaces</small></button>)}{!networks.length && <p>No matching Networks.</p>}</nav><section className="ops-card topology-network-detail">{selected ? <><h2 className="topology-network-heading" {...presentationAttributes(selected)}><PresentationIdentity record={selected} fallback="network" /></h2>{selected.purpose && <p>{selected.purpose}</p>}<dl className="ops-definition">{selected.vlan_id != null && <><dt>VLAN</dt><dd>{selected.vlan_id}</dd></>}{selected.cidr && <><dt>CIDR</dt><dd>{selected.cidr}</dd></>}{selected.gateway && <><dt>Gateway</dt><dd>{selected.gateway}</dd></>}{sites.find(s => s.id === selected.site_id) && <><dt>Site</dt><dd>{sites.find(s => s.id === selected.site_id).name}</dd></>}<dt>Interfaces</dt><dd>{members.length}</dd><dt>Connected Assets</dt><dd>{new Set(members.map(i => i.asset_id)).size}</dd></dl><h3>Connected Assets</h3><div className="table-scroll"><table><thead><tr><th>Asset / Type</th><th>Interface</th><th>IP address</th><th>MAC</th><th>Recorded status</th></tr></thead><tbody>{members.map(i => <tr key={i.id}><td><Identity compact asset={view.byId[i.asset_id]} view={view} select={select} /></td><td>{i.name}</td><td>{i.ip_address || "—"}</td><td>{i.mac_address || "—"}</td><td>{view.byId[i.asset_id].status}</td></tr>)}</tbody></table></div>{!members.length && <p>No visible interface memberships recorded.</p>}</> : <p>Select a recorded Network.</p>}</section></div>;
}

function Connectivity({ graph, view, selected, select, onNetwork, expanded, filtersOpen }) {
  const viewport = useRef(null);
  const [height, setHeight] = useState(480), [width, setWidth] = useState(700);
  useLayoutEffect(() => {
    const element = viewport.current;
    const fitHeight = () => {
      setHeight(Math.max(expanded ? 320 : 600, Math.min(800, window.innerHeight - element.getBoundingClientRect().top - 32)));
      setWidth(element.clientWidth);
    };
    fitHeight();
    const observer = new ResizeObserver(fitHeight);
    observer.observe(element);
    window.addEventListener("resize", fitHeight);
    return () => { observer.disconnect(); window.removeEventListener("resize", fitHeight); };
  }, [expanded, filtersOpen]);
  const [zoom, setZoom] = useState(1);
  const nodes = useMemo(() => connectivityLayout(graph), [graph]);
  const positions = Object.fromEntries(nodes.map(n => [n.key, n]));
  const extentX = Math.max(130, ...nodes.map(n => Math.abs(n.x) + CONNECTIVITY_NODE_WIDTH / 2)) + 24;
  const extentY = Math.max(130, ...nodes.map(n => Math.abs(n.y) + CONNECTIVITY_NODE_HEIGHT / 2)) + 24;
  const layoutWidth = extentX * 2, layoutHeight = extentY * 2;
  const scale = Math.min(1, width / layoutWidth, height / layoutHeight) * zoom;
  const canvasWidth = Math.max(width, layoutWidth * scale), canvasHeight = Math.max(height, layoutHeight * scale);
  useLayoutEffect(() => { setZoom(1); }, [graph.focus_key, graph.nodes.length]);
  useLayoutEffect(() => {
    viewport.current.scrollLeft = (canvasWidth - width) / 2;
    viewport.current.scrollTop = (canvasHeight - height) / 2;
  }, [canvasWidth, canvasHeight, width, height]);
  return <section className="ops-card topology-connectivity"><div className="row-actions"><button type="button" className="button button-secondary" onClick={() => setZoom(1)}>Fit</button><button type="button" className="button button-secondary" aria-label="Zoom in" onClick={() => setZoom(z => Math.min(z + .25, 4))}>+</button><button type="button" className="button button-secondary" aria-label="Zoom out" onClick={() => setZoom(z => Math.max(z - .25, .5))}>−</button><span className="ops-meta">{nodes.length} nodes · Dashed lines: interface membership</span></div>{graph.truncated && <p role="status">Result limited — showing {nodes.length} nodes, up to 25 nodes and 150 edges. Refine the focus or filters.</p>}<div ref={viewport} className="topology-connectivity-viewport" style={{ height }}><div className="topology-connectivity-canvas" style={{ width: canvasWidth, height: canvasHeight }}><div className="topology-connectivity-world" role="group" aria-label="Recorded connectivity" style={{ width: layoutWidth, height: layoutHeight, left: (canvasWidth - layoutWidth * scale) / 2, top: (canvasHeight - layoutHeight * scale) / 2, transform: `scale(${scale})` }}>
    <svg width={layoutWidth} height={layoutHeight} aria-hidden="true">
      <defs><marker id="topology-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="var(--muted)" /></marker></defs>
      {graph.edges.map(edge => {
        const a = positions[edge.source_key], b = positions[edge.target_key]; if (!a || !b) return null;
        const dx = b.x - a.x, dy = b.y - a.y;
        const inset = Math.min((CONNECTIVITY_NODE_WIDTH / 2 + 3) / (Math.abs(dx) || Number.EPSILON), (CONNECTIVITY_NODE_HEIGHT / 2 + 3) / (Math.abs(dy) || Number.EPSILON));
        const relevant = edge.source_key === `asset:${selected?.id}` || edge.target_key === `asset:${selected?.id}`;
        const membershipNetwork = edge.kind === "membership" ? view.networkById[edge.target_key.slice(8)] : null;
        return <g key={edge.key} {...(membershipNetwork ? presentationAttributes(membershipNetwork) : {})}><line x1={a.x + extentX} y1={a.y + extentY} x2={b.x + extentX - dx * inset} y2={b.y + extentY - dy * inset} stroke={membershipNetwork ? "var(--identity-emphasis)" : "var(--muted)"} strokeWidth={relevant ? 2 : 1} strokeDasharray={edge.kind === "membership" ? "6 5" : undefined} markerEnd={edge.directional ? "url(#topology-arrow)" : undefined}><title>{edge.label}</title></line>{relevant && <text className="topology-edge-label" x={(a.x + b.x) / 2 + extentX} y={(a.y + b.y) / 2 + extentY - 8} textAnchor="middle">{edge.label}</text>}</g>;
      })}
    </svg>
    {nodes.map(node => {
      const asset = node.entity_type === "asset" ? view.byId[node.entity_id] : null;
      const network = node.entity_type === "network" ? view.networkById[node.entity_id] : null;
      const identity = asset ? asset.presentation : network;
      const count = node.entity_type === "network" ? view.interfaces.filter(i => i.network_id === node.entity_id).length : view.children[node.entity_id]?.length;
      return <button key={node.key} type="button" data-node-key={node.key} {...presentationAttributes(identity)} aria-pressed={node.key === graph.focus_key || node.entity_id === selected?.id} title={`${[node.name, network?.vlan_id != null ? `VLAN ${network.vlan_id}` : null, network?.cidr].filter(Boolean).join(" · ")}${node.key === graph.focus_key ? " (focus)" : ""}${node.entity_id === selected?.id ? " (selected)" : ""}`} style={{ left: node.x + extentX - CONNECTIVITY_NODE_WIDTH / 2, top: node.y + extentY - CONNECTIVITY_NODE_HEIGHT / 2, width: CONNECTIVITY_NODE_WIDTH, height: CONNECTIVITY_NODE_HEIGHT }} className={`topology-graph-node${node.key === graph.focus_key ? " is-focus" : ""}${node.entity_id === selected?.id ? " is-selected" : ""}`} onClick={() => node.entity_type === "asset" ? select(asset) : onNetwork(node.entity_id)}>{asset ? <AssetIcon asset={asset} assetType={view.types[asset.asset_type]} size={28} /> : <PresentationIcon record={network} fallback="network" />}<span><strong>{node.name}</strong><small>{asset ? view.types[asset.asset_type]?.name : [network?.vlan_id != null ? `VLAN ${network.vlan_id}` : "Network", count > 0 ? `${count} interfaces` : null].filter(Boolean).join(" · ")}</small>{network?.cidr && <small>{network.cidr}</small>}{asset?.display_ip && !count && <small>{asset.display_ip}</small>}{asset && count > 0 && <small>{count} child Assets</small>}</span></button>;
    })}
  </div></div></div></section>;
}

function Inspector({ asset, view, sites, select, onFocus }) {
  if (!asset) return <aside className="ops-card graph-inspector"><p>Select an Asset to inspect recorded knowledge.</p></aside>;
  const type = view.types[asset.asset_type], site = sites.find(s => s.id === asset.site_id);
  const interfaces = view.interfaces.filter(i => i.asset_id === asset.id);
  const relationships = view.relationships.filter(r => r.source_asset_id === asset.id || r.target_asset_id === asset.id);
  return <aside className="ops-card graph-inspector" aria-label="Topology inspector"><header className="inspector-identity"><AssetIcon asset={asset} assetType={type} size={36} /><div><h2>{asset.name}</h2><p>{type?.name} · {type?.category}</p></div></header><dl className="ops-definition"><dt>Recorded status</dt><dd>{asset.status}</dd>{site && <><dt>Site</dt><dd>{site.name}</dd></>}{asset.hostname && <><dt>Hostname</dt><dd>{asset.hostname}</dd></>}</dl><h3>Interfaces & Networks</h3>{interfaces.length ? <ul className="inspector-relationships">{interfaces.map(i => <li key={i.id}><strong>{i.name}</strong><span>{[i.ip_address, i.mac_address, view.networks.find(n => n.id === i.network_id)?.name].filter(Boolean).join(" · ")}</span></li>)}</ul> : <p className="ops-meta">No visible interfaces recorded.</p>}<h3>Key recorded relationships</h3><ul className="inspector-relationships">{relationships.slice(0, 12).map(r => <li key={r.id}><button type="button" className="text-button" onClick={() => select(view.byId[r.source_asset_id])}>{view.byId[r.source_asset_id].name}</button><span>{r.display_label || r.relationship_type} {r.directional === false ? "↔" : "→"}</span><button type="button" className="text-button" onClick={() => select(view.byId[r.target_asset_id])}>{view.byId[r.target_asset_id].name}</button></li>)}</ul>{relationships.length > 12 && <p className="ops-meta">Showing 12 of {relationships.length} visible relationships.</p>}<footer className="inspector-actions"><Link className="button button-secondary" href={`/assets/${asset.id}`}>Open Asset</Link><Link className="button button-secondary" href={`/knowledge-graph?focus=asset:${asset.id}&depth=1`}>View in Knowledge Graph</Link><button type="button" className="button button-secondary" onClick={() => onFocus(asset)}>Focus Connectivity</button></footer></aside>;
}
