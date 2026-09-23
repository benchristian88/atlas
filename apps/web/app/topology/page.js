"use client";

import Link from "next/link";
import { Fragment, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { AccessDenied } from "../../components/access-denied";
import { AssetIcon } from "../../components/asset-icon";
import { useAuth } from "../../components/auth-context";
import { ConnectivityAssetSearch } from "../../components/connectivity-asset-search";
import { ExpandedGraphSurface } from "../../components/expanded-graph-surface";
import { DetailsPanelToggle } from "../../components/details-panel-toggle";
import { sortNetworkMembers } from "../../lib/network-sort.mjs";
import { NavigationIcon } from "../../components/navigation-icon.mjs";
import { assetListFiltersHref } from "../../lib/asset-list-filters.mjs";
import { TopologyCategoryFilter } from "../../components/topology-category-filter";
import { PageHeader } from "../../components/page-header";
import { useWorkspaceContext } from "../../components/workspace-context";
import { apiRequest } from "../../lib/api";
import { TOPOLOGY_CLASSES, topologyClassSelection, topologyCategorySelection, topologyPresentation, platformMatches, platformCardFacts, matchesSearch, CATEGORY_PREVIEW_COUNT, CONNECTIVITY_NODE_WIDTH, CONNECTIVITY_NODE_HEIGHT, connectivityLayout, connectivityPositionGroups, connectivityPreview, connectivityRoutes, connectivityBounds, connectivityFit } from "../../lib/infrastructure-topology.mjs";

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
  const [classChoices, setClassChoices] = useState({});
  const [choices, setChoices] = useState({}), [filtersOpen, setFiltersOpen] = useState(false);
  const [search, setSearch] = useState(""), [selectedId, setSelectedId] = useState("");
  const [networkId, setNetworkId] = useState(""), [parentId, setParentId] = useState("");
  const [expandedParents, setExpandedParents] = useState({});
  const [focusId, setFocusId] = useState(""), [hops, setHops] = useState(1), [showNetworks, setShowNetworks] = useState(true);
  const [graph, setGraph] = useState(null), [graphError, setGraphError] = useState("");
  const [expanded, setExpanded] = useState(false), [detailsHidden, setDetailsHidden] = useState(false);
  const [expandedConnectivityHosts, setExpandedConnectivityHosts] = useState({});
  const toolbar = useRef(null);
  const expandButton = useRef(null), scrollPosition = useRef({ left: 0, top: 0 });

  useEffect(() => {
    if (!canView) return;
    let active = true;
    setError("");
    apiRequest("/topology").then(value => { if (active) setData(value); }).catch(e => { if (active) setError(e.message || "Unable to load topology."); });
    return () => { active = false; };
  }, [canView, workspace.reloadKey, reload]);
  const { enabled, changedCount } = useMemo(() => topologyCategorySelection(data?.categories || [], choices), [data, choices]);
  const view = useMemo(() => data ? topologyPresentation(data, enabled) : null, [data, enabled]);
  const searchable = useMemo(() => data ? topologyPresentation(data, new Set(data.categories.map(c => c.id))) : null, [data]);
  const networkFocus = Boolean(view?.assets.length) && showNetworks && focusId.startsWith("network:") && view?.networks.some(n => `network:${n.id}` === focusId);
  const actualFocus = networkFocus || searchable?.byId[focusId] ? focusId : view?.assets[0]?.id || "";
  const focusHidden = Boolean(searchable?.byId[actualFocus] && !view?.byId[actualFocus]);
  const classSelection = useMemo(() => topologyClassSelection(classChoices), [classChoices]);
  const classKey = [...classSelection.enabled].sort().join(",");
  const categoryKey = [...enabled].sort().join(",");
  const graphKey = `${actualFocus}/${hops}/${showNetworks}/${categoryKey}/${classKey}`;
  const currentGraph = graph?.requestKey === graphKey && graph.nodes.every(node =>
    node.entity_type === "asset" ? view?.byId[node.entity_id] : view?.networkById[node.entity_id]) ? graph : null;
  useEffect(() => {
    if (tab !== "connectivity" || !actualFocus || !data) { setGraph(null); return; }
    let active = true;
    setGraphError("");
    const params = new URLSearchParams({ [networkFocus ? "focus_network_id" : "focus_asset_id"]: networkFocus ? actualFocus.slice(8) : actualFocus, hops: String(hops), show_networks: String(showNetworks) });
    params.set("topology_classes", classKey);
    categoryKey.split(",").filter(Boolean).forEach(id => params.append("category_ids", id));
    apiRequest(`/topology/connectivity?${params}`).then(value => { if (active) setGraph({ ...value, requestKey: graphKey }); }).catch(e => { if (active) setGraphError(e.message || "Unable to load connectivity."); });
    return () => { active = false; };
  }, [tab, actualFocus, hops, showNetworks, categoryKey, classKey, graphKey, data, networkFocus]);

  useEffect(() => { setExpandedConnectivityHosts({}); }, [actualFocus]);

  if (!canView) return <AccessDenied />;
  // Selection is inspection state, independent of the Connectivity query.
  const selectedNetworkId = selectedId.startsWith("network:") ? selectedId.slice(8) : "";
  const selectedNetwork = tab === "connectivity" && showNetworks && view?.networkById[selectedNetworkId];
  const selected = tab === "overview" ? null : view?.byId[selectedId] ||
    (tab === "connectivity" && !selectedNetwork ? view?.byId[actualFocus] : null);
  const inspectedNetwork = selectedNetwork || (tab === "connectivity" && networkFocus && !selected ? view?.networkById[actualFocus.slice(8)] : null);
  const selectedKey = selected ? `asset:${selected.id}` : inspectedNetwork ? `network:${inspectedNetwork.id}` : "";
  const select = asset => setSelectedId(asset.id);
  // In-view refocus preserves controls; enterView below initializes a different tab.
  const refocusConnectivity = id => {
    const asset = data?.assets.find(a => a.id === id);
    const network = id.startsWith("network:") && data?.networks.find(n => `network:${n.id}` === id);
    if (!asset && !network) return;
    if (network && !showNetworks) setShowNetworks(true);
    setSelectedId(id);
    setFocusId(id);
  };
  const network = view?.networks.find(n => n.id === networkId) || view?.networks[0];
  // Enter a fresh projection. Explicit navigation may supply a new initial focus;
  // ordinary tabs supply none. Expand and Refresh never call this initializer.
  const enterView = (destination, initial = {}) => {
    setClassChoices({}); setChoices({}); setFiltersOpen(false); setSearch(""); setSelectedId("");
    const focusAsset = data?.assets.find(asset => asset.id === initial.focusId);
    const focusCategory = data?.asset_types.find(type => type.key === focusAsset?.asset_type)?.category_id;
    // An explicitly requested Asset remains visible even if its category is
    // hidden by default. This is new navigation context, not a carried override.
    if (focusCategory) setChoices({ [focusCategory]: true });
    setNetworkId(initial.networkId || ""); // Empty uses first Network in byNetwork order.
    setParentId(""); setExpandedParents({}); setExpandedConnectivityHosts({});
    setFocusId(initial.focusId || ""); // Empty uses first visible Asset in byName order.
    setHops(1); setShowNetworks(true); setGraph(null); setGraphError("");
    setTab(destination);
    toolbar.current?.closest("dialog")?.scrollTo({ left: 0, top: 0, behavior: "instant" });
    scrollPosition.current = { left: 0, top: 0 };
    if (!expanded) window.scrollTo({ left: 0, top: 0, behavior: "instant" });
  };
  const openNetwork = id => enterView("networks", { networkId: id });
  return <div className="operations-page infrastructure-topology">
    <PageHeader eyebrow="Knowledge" title="Infrastructure Topology" description="Visualise your infrastructure, networks and connectivity." />
    <ExpandedGraphSurface title="Infrastructure Topology" expanded={expanded} onClose={() => { setExpanded(false); setHops(n => Math.min(n, 2)); }} returnFocus={expandButton} scrollPosition={scrollPosition}>
      <div className="topology-toolbar" ref={toolbar}>
        <div className="lens-selector" aria-label="Topology views">{Object.entries(tabs).map(([key, label]) => <button key={key} type="button" aria-pressed={tab === key} className={`button selector-control-text ${tab === key ? "button-primary" : "button-secondary"}`} onClick={() => { if (key !== tab) enterView(key); }}>{label}</button>)}</div>
        <div className="row-actions"><TopologyCategoryFilter
          categories={data?.categories || []} enabled={enabled}
          changedCount={changedCount + (tab === "connectivity" ? classSelection.changedCount : 0)}
          classes={tab === "connectivity" ? TOPOLOGY_CLASSES : []} enabledClasses={classSelection.enabled}
          onClassChange={(key, checked) => setClassChoices(current => ({ ...current, [key]: checked }))}
          open={filtersOpen} onOpenChange={setFiltersOpen}
          onChange={(id, checked) => setChoices(current => ({ ...current, [id]: checked }))}
          onReset={() => { setChoices({}); setClassChoices({}); }}
        /><button type="button" className="text-button" onClick={() => setReload(n => n + 1)}>Refresh</button>{tab !== "overview" && <DetailsPanelToggle hidden={detailsHidden} onToggle={() => setDetailsHidden(hidden => !hidden)} />}{!expanded && <button ref={expandButton} type="button" className="button button-secondary graph-icon-button" title="Expand Infrastructure Topology" aria-label="Expand Infrastructure Topology" onClick={() => { scrollPosition.current = { left: window.scrollX, top: window.scrollY }; setExpanded(true); }}><NavigationIcon name="expand" /></button>}</div>
      </div>
      {error && <p className="error-banner" role="alert">{error}</p>}
      {!data && !error && <p role="status">Loading infrastructure…</p>}
      {data && <>
        {tab !== "overview" && tab !== "connectivity" && <label className="field topology-search"><span>{tab === "networks" ? "Search Networks and connected Assets" : "Search Assets"}</span><input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder={tab === "networks" ? "Network, VLAN or Asset name" : "Asset name, hostname or IP"} /></label>}
        <TopologyPanel active={tab === "platform" || tab === "networks"} hidden={detailsHidden} inspector={<Inspector asset={selected} view={view} sites={data.sites} select={select} onFocus={a => enterView("connectivity", { focusId: a.id })} />}>{tab === "overview" ? <Overview view={view} onNetwork={openNetwork} /> :
          tab === "networks" ? <Networks view={view} network={network} search={search} onNetwork={setNetworkId} select={select} sites={data.sites} /> :
          tab === "platform" ? <Platform view={view} search={search} parentId={parentId} onParent={setParentId} expandedParents={expandedParents} onExpand={id => setExpandedParents(p => ({ ...p, [id]: !p[id] }))} select={select} /> :
          <>
            <div className="topology-connectivity-controls" role="group" aria-label="Connectivity controls">
              <ConnectivityAssetSearch assets={searchable.assets} types={searchable.types} value={search} onChange={setSearch} onSelect={refocusConnectivity} disabled={Boolean(error)} />
              <label className="field topology-focus-control"><span>Focus</span><select aria-label="Focus" value={actualFocus} onChange={e => refocusConnectivity(e.target.value)}>{searchable.assets.filter(a => a.id === actualFocus || view.byId[a.id]).map(a => <option key={a.id} value={a.id}>{a.name}</option>)}{showNetworks && view.networks.map(n => <option key={`network:${n.id}`} value={`network:${n.id}`}>{n.name} (Network)</option>)}</select></label>
              <div className="row-actions" aria-label="Hops">{(expanded ? [1, 2, 3] : [1, 2]).map(n => <button type="button" key={n} aria-pressed={hops === n} className={`button ${hops === n ? "button-primary" : "button-secondary"}`} onClick={() => setHops(n)}>{n} {n === 1 ? "hop" : "hops"}</button>)}</div>
              <label className="topology-networks-control"><input type="checkbox" checked={showNetworks} onChange={e => setShowNetworks(e.target.checked)} /> Networks</label>
            </div>
            {focusHidden && <p role="status">The focused Asset’s category is hidden. Enable it in Filters to show connectivity.</p>}
            {graphError && <p className="error-banner" role="alert">{graphError}</p>}
            {!actualFocus ? <p className="empty-state">Enable a category with Assets to explore connectivity.</p> : focusHidden ? null : !currentGraph && !graphError ? <p role="status">Loading recorded connectivity…</p> : currentGraph && <div className={`graph-workspace${detailsHidden ? " topology-details-hidden" : ""}`}><Connectivity branches={expandedConnectivityHosts} onExpandBranch={(key, stage) => setExpandedConnectivityHosts(current => ({ ...current, [key]: stage }))} key={actualFocus} expanded={expanded} graph={currentGraph} view={view} selectedKey={selectedKey} onSelect={setSelectedId} onFocus={refocusConnectivity} />{!(detailsHidden) && (inspectedNetwork ? <NetworkInspector network={inspectedNetwork} view={view} onOpen={() => openNetwork(inspectedNetwork.id)} onFocus={actualFocus === `network:${inspectedNetwork.id}` ? null : () => refocusConnectivity(`network:${inspectedNetwork.id}`)} /> : <Inspector asset={selected} view={view} sites={data.sites} select={select} onFocus={selected?.id === actualFocus ? null : a => refocusConnectivity(a.id)} />)}</div>}
          </>}
        </TopologyPanel>
        {view.assets.length === 0 && tab !== "connectivity" && <p className="empty-state">No Assets match the enabled categories. Use Filters to include other categories, or <Link href="/assets">open Assets</Link> to curate your infrastructure.</p>}
      </>}
    </ExpandedGraphSurface>
  </div>;
}

function TopologyPanel({ active, hidden, inspector, children }) {
  if (!active) return children;
  return <div className={`graph-workspace${hidden ? " topology-details-hidden" : ""}`}><div className="topology-main">{children}</div>{!hidden && inspector}</div>;
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
  return <>{focused && <button type="button" className="button button-secondary" onClick={() => onParent("")}>All platform Assets</button>}{view.categories.map(category => { const assets = roots.filter(a => view.types[a.asset_type]?.category_id === category.id); if (!assets.length) return null; return <section className="topology-platform-section" key={category.id}><h2 {...presentationAttributes(category)}><PresentationIdentity record={category} /> <small>{assets.length}</small></h2><div className="topology-platform-grid">{assets.map(asset => { const children = view.children[asset.id]; const matchingChildren = search && !matchesSearch(asset, search) ? children.filter(child => platformMatches(child, view.children, search)) : children; const displayed = expandedParents[asset.id] ? matchingChildren : matchingChildren.slice(0, 4); const interfaces = view.interfaces.filter(i => i.asset_id === asset.id); const networks = view.networks.filter(n => interfaces.some(i => i.network_id === n.id)); return <article className="ops-card topology-platform-card" key={asset.id} data-platform-id={asset.id} {...presentationAttributes(asset.presentation)}><Identity asset={asset} view={view} select={select} />{view.cycleRoots.has(asset.id) && <p className="ops-meta">Recorded platform cycle</p>}{platformCardFacts(children.length, interfaces.length) && <p className="ops-meta topology-platform-facts">{platformCardFacts(children.length, interfaces.length)}</p>}{networks.length > 0 && <p className="ops-meta">{networks.map(n => n.name).join(" · ")}</p>}{children.length > 0 && <><div className="topology-children">{displayed.map(child => <div key={child.id} className="topology-child" {...presentationAttributes(child.presentation)}><Identity compact asset={child} view={view} select={select} /><small>Recorded: {child.status}</small>{view.children[child.id]?.length > 0 && <button type="button" className="text-button" onClick={() => onParent(child.id)}>View platform ({view.children[child.id].length})</button>}</div>)}</div>{matchingChildren.length > 4 && <button type="button" className="text-button" onClick={() => onExpand(asset.id)}>{expandedParents[asset.id] ? "Show fewer" : `+${matchingChildren.length - 4} more`}</button>}</>}</article>; })}</div></section>; })}{!roots.length && view.assets.length > 0 && <p className="empty-state">No platform Assets match this search.</p>}</>;
}

function Networks({ view, network, search, onNetwork, select, sites }) {
  const networks = view.networks.filter(n => [n.name, n.cidr, n.vlan_id].join(" ").toLowerCase().includes(search.toLowerCase()) || view.interfaces.some(i => i.network_id === n.id && matchesSearch(view.byId[i.asset_id], search)));
  const selected = networks.find(n => n.id === network?.id) || networks[0];
  const [sort, setSort] = useState({ key: "", direction: 1 });
  const members = sortNetworkMembers(view.interfaces.filter(i => i.network_id === selected?.id), view.byId, sort);
  const columns = [["asset", "Name"], ["name", "Interface"], ["ip_address", "IP address"], ["mac_address", "MAC"], ["status", "Recorded status"]];
  return <div className="topology-network-layout"><nav className="ops-card topology-network-list" aria-label="Networks">{networks.map(n => <button key={n.id} type="button" aria-current={selected?.id === n.id ? "true" : undefined} className="topology-network-row" {...presentationAttributes(n)} onClick={() => onNetwork(n.id)}><strong><PresentationIdentity record={n} fallback="network" /></strong><span>{[n.vlan_id != null ? `VLAN ${n.vlan_id}` : null, n.cidr].filter(Boolean).join(" · ")}</span><small>{view.interfaces.filter(i => i.network_id === n.id).length} interfaces</small></button>)}{!networks.length && <p>No matching Networks.</p>}</nav><section className="ops-card topology-network-detail">{selected ? <><h2 className="topology-network-heading" {...presentationAttributes(selected)}><PresentationIdentity record={selected} fallback="network" /></h2>{selected.purpose && <p>{selected.purpose}</p>}<dl className="ops-definition">{selected.vlan_id != null && <><dt>VLAN</dt><dd>{selected.vlan_id}</dd></>}{selected.cidr && <><dt>CIDR</dt><dd>{selected.cidr}</dd></>}{selected.gateway && <><dt>Gateway</dt><dd>{selected.gateway}</dd></>}{sites.find(s => s.id === selected.site_id) && <><dt>Site</dt><dd>{sites.find(s => s.id === selected.site_id).name}</dd></>}<dt>Interfaces</dt><dd>{members.length}</dd><dt>Connected Assets</dt><dd>{new Set(members.map(i => i.asset_id)).size}</dd></dl><h3>Connected Assets</h3><div className="table-scroll"><table><thead><tr><>{columns.map(([key, label]) => <th key={key} aria-sort={sort.key === key ? sort.direction === 1 ? "ascending" : "descending" : "none"}><button className="text-button" type="button" onClick={() => setSort(previous => ({ key, direction: previous.key === key ? -previous.direction : 1 }))}>{label}{sort.key === key ? sort.direction === 1 ? " ↑" : " ↓" : ""}</button></th>)}</></tr></thead><tbody>{members.map(i => <tr key={i.id}><td><Identity compact asset={view.byId[i.asset_id]} view={view} select={select} /></td><td>{i.name}</td><td>{i.ip_address || "—"}</td><td>{i.mac_address || "—"}</td><td>{view.byId[i.asset_id].status}</td></tr>)}</tbody></table></div>{!members.length && <p>No visible interface memberships recorded.</p>}</> : <p>Select a recorded Network.</p>}</section></div>;
}

function Connectivity({ graph, view, selectedKey, onSelect, onFocus, expanded, branches, onExpandBranch }) {
  const viewport = useRef(null);
  const pan = useRef({ x: 0, y: 0 }), placedScroll = useRef({ left: 0, top: 0 });
  const [height, setHeight] = useState(480), [width, setWidth] = useState(700);
  useLayoutEffect(() => {
    const element = viewport.current;
    const fitHeight = () => {
      // ExpandedGraphSurface briefly closes its dialog while changing modes.
      // Keep the last valid viewport until the same tree is visible again.
      if (!element.clientWidth) return;
      setHeight(Math.max(expanded ? 320 : 600, Math.min(800, window.innerHeight - element.getBoundingClientRect().top - 32)));
      setWidth(element.clientWidth);
    };
    fitHeight();
    const observer = new ResizeObserver(fitHeight);
    observer.observe(element);
    window.addEventListener("resize", fitHeight);
    return () => { observer.disconnect(); window.removeEventListener("resize", fitHeight); };
  }, [expanded]);
  const [zoom, setZoom] = useState(1);
  const preview = useMemo(() => connectivityPreview(graph, branches), [graph, branches]);
  const presentationEdges = useMemo(() => [...preview.edges, ...preview.moreEdges], [preview]);
  const nodes = useMemo(() => connectivityLayout({ ...preview, nodes: [...preview.nodes, ...preview.moreNodes], edges: presentationEdges }, { width }), [preview, presentationEdges, width]);
  const groups = useMemo(() => connectivityPositionGroups(nodes), [nodes]);
  const positions = Object.fromEntries(nodes.map(n => [n.key, n]));
  const routes = useMemo(() => connectivityRoutes(nodes, presentationEdges, groups), [nodes, presentationEdges, groups]);
  const bounds = useMemo(() => connectivityBounds(nodes, routes, groups), [nodes, routes, groups]);
  const extentX = -bounds.minX, extentY = -bounds.minY;
  const layoutWidth = bounds.width, layoutHeight = bounds.height;
  const { scale, canvasWidth, canvasHeight, top } = connectivityFit(bounds, width, height, zoom);
  useLayoutEffect(() => { setZoom(1); pan.current = { x: 0, y: 0 }; }, [graph.focus_key, nodes.length]);
  useLayoutEffect(() => {
    viewport.current.scrollLeft = (canvasWidth - width) / 2 + pan.current.x * scale;
    viewport.current.scrollTop = pan.current.y * scale;
    placedScroll.current = { left: viewport.current.scrollLeft, top: viewport.current.scrollTop };
  }, [canvasWidth, canvasHeight, width, height, scale]);
  const fit = () => {
    pan.current = { x: 0, y: 0 }; setZoom(1);
    viewport.current.scrollLeft = (canvasWidth - width) / 2;
    viewport.current.scrollTop = 0;
    placedScroll.current = { left: viewport.current.scrollLeft, top: viewport.current.scrollTop };
  };
  return <section className="ops-card topology-connectivity"><div className="row-actions"><button type="button" className="button button-secondary" onClick={fit}>Fit</button><button type="button" className="button button-secondary" aria-label="Zoom in" onClick={() => setZoom(z => Math.min(z + .25, 4))}>+</button><button type="button" className="button button-secondary" aria-label="Zoom out" onClick={() => setZoom(z => Math.max(z - .25, .5))}>−</button><span className="ops-meta">{preview.nodes.length} visible nodes · Dashed lines: interface membership</span></div>{graph.truncated && <p role="status">Topology safety limit reached ({graph.node_limit} nodes / {graph.edge_limit} edges). Refine the focus or filters.</p>}<div ref={viewport} onScroll={event => {
    const { scrollLeft: left, scrollTop: top } = event.currentTarget;
    if (left !== placedScroll.current.left || top !== placedScroll.current.top) {
      pan.current = { x: (left - (canvasWidth - width) / 2) / scale, y: top / scale };
    }
  }} className="topology-connectivity-viewport" style={{ height }}><div className="topology-connectivity-canvas" style={{ width: canvasWidth, height: canvasHeight }}><div className="topology-connectivity-world" role="group" aria-label="Recorded connectivity" style={{ width: layoutWidth, height: layoutHeight, left: (canvasWidth - layoutWidth * scale) / 2, top, transform: `scale(${scale})` }}>
    {groups.map(group => <div key={group.key} className="topology-position-group" data-position-id={group.position_id} data-group-key={group.key} {...presentationAttributes(group)} role="group" aria-label={`${group.name}: ${group.node_keys.length} Assets`}
      style={{ left: group.left + extentX, top: group.top + extentY, width: group.width, height: group.height }}>
      <span className="topology-position-label" title={group.name} style={{ width: group.labelWidth }}>{group.name}</span>
    </div>)}
    <svg width={layoutWidth} height={layoutHeight} aria-hidden="true">
      <defs><marker id="topology-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="var(--muted)" /></marker></defs>
      {presentationEdges.map(edge => {
        const route = routes[edge.key]; if (!route || route.render === false) return null;
        const relevant = edge.source_key === selectedKey || edge.target_key === selectedKey || route.member_keys?.includes(selectedKey);
        const membershipNetwork = edge.kind === "membership" ? view.networkById[edge.target_key.slice(8)] : null;
        return <g key={edge.key} {...(membershipNetwork ? presentationAttributes(membershipNetwork) : {})}><path
          data-internal-routing={route.internal_routing || undefined} data-group-connection={route.group_key} data-edge-key={edge.key} data-source-key={edge.source_key} data-target-key={edge.target_key}
          className={route.group_key ? "topology-host-rail" : edge.kind === "disclosure" ? "topology-disclosure-edge" : edge.platform_parent_key ? "topology-host-rail" : "topology-relationship-edge"}
          d={route.points.map(([x, y], index) => `${index ? "L" : "M"}${x + extentX},${y + extentY}`).join(" ")}
          fill="none" stroke={membershipNetwork ? "var(--identity-emphasis)" : "var(--muted)"} strokeWidth={relevant ? 2 : 1}
          strokeDasharray={edge.kind === "membership" ? "6 5" : undefined}
          markerEnd={edge.directional && !route.group_key ? "url(#topology-arrow)" : undefined} /></g>;
      })}
    </svg>
    {nodes.map(node => {
      if (node.entity_type === "disclosure") return <button key={node.key} type="button" className="topology-disclosure-more" data-disclosure-parent={node.parent_key}
        aria-label={`Show ${node.hiddenCount} more child Assets for ${positions[node.parent_key].name}`}
        style={{ left: node.x + extentX - 30, top: node.y + extentY - 30 }}
        onPointerDown={event => event.stopPropagation()} onDoubleClick={event => event.stopPropagation()}
        onClick={event => { event.stopPropagation(); onExpandBranch(node.parent_key, "all"); }}><strong>+{node.hiddenCount}</strong><small>more</small></button>;
      const disclosure = preview.disclosures[node.key];
      const asset = node.entity_type === "asset" ? view.byId[node.entity_id] : null;
      const network = node.entity_type === "network" ? view.networkById[node.entity_id] : null;
      const identity = asset ? asset.presentation : network;
      const count = node.entity_type === "network" ? view.interfaces.filter(i => i.network_id === node.entity_id).length : node.eligible_child_count;
      return <Fragment key={node.key}><button type="button" data-node-key={node.key} data-topology-rank={node.rank} {...presentationAttributes(identity)} aria-pressed={node.key === selectedKey} title={`${[node.name, network?.vlan_id != null ? `VLAN ${network.vlan_id}` : null, network?.cidr].filter(Boolean).join(" · ")}${node.key === graph.focus_key ? " (focus)" : ""}${node.key === selectedKey ? " (selected)" : ""}`} style={{ left: node.x + extentX - CONNECTIVITY_NODE_WIDTH / 2, top: node.y + extentY - CONNECTIVITY_NODE_HEIGHT / 2, width: CONNECTIVITY_NODE_WIDTH, height: CONNECTIVITY_NODE_HEIGHT }} className={`topology-graph-node${node.key === graph.focus_key ? " is-focus" : ""}${node.key === selectedKey ? " is-selected" : ""}`} onClick={() => { if (asset || network) onSelect(asset ? asset.id : `network:${network.id}`); }} onDoubleClick={() => { if (asset || network) onFocus(asset ? asset.id : `network:${network.id}`); }}>{asset ? <AssetIcon asset={asset} assetType={view.types[asset.asset_type]} size={28} /> : <PresentationIcon record={network} fallback="network" />}<span><strong>{node.name}</strong><small>{asset ? view.types[asset.asset_type]?.name : [network?.vlan_id != null ? `VLAN ${network.vlan_id}` : "Network", count > 0 ? `${count} interfaces` : null].filter(Boolean).join(" · ")}</small>{network?.cidr && <small>{network.cidr}</small>}{asset?.display_ip && !count && <small>{asset.display_ip}</small>}{asset && count > 0 && <small>{count} child Asset{count === 1 ? "" : "s"}</small>}</span></button>{disclosure && disclosure.shownCount === 0 && <button type="button" className="topology-disclosure-badge" data-disclosure-parent={node.key}
        aria-label={`Show ${disclosure.hiddenCount} child Assets for ${node.name}`}
        style={{ left: node.x + extentX + CONNECTIVITY_NODE_WIDTH / 2 - 18, top: node.y + extentY + CONNECTIVITY_NODE_HEIGHT / 2 - 18 }}
        onPointerDown={event => event.stopPropagation()} onDoubleClick={event => event.stopPropagation()}
        onClick={event => { event.stopPropagation(); onExpandBranch(node.key, "preview"); }}>+{disclosure.hiddenCount}</button>}</Fragment>;
    })}
  </div></div></div></section>;
}

function NetworkInspector({ network, view, onOpen, onFocus }) {
  return <aside className="ops-card graph-inspector" aria-label="Topology inspector">
    <h2><PresentationIdentity record={network} fallback="network" /></h2>
    <p>{view.interfaces.filter(i => i.network_id === network.id).length} recorded interfaces</p>
    <footer className="inspector-actions">
      <button type="button" className="button button-secondary" onClick={onOpen}>Open Network detail</button>
      {onFocus && <button type="button" className="button button-secondary" onClick={onFocus}>Focus Connectivity</button>}
    </footer>
  </aside>;
}

function Inspector({ asset, view, sites, select, onFocus }) {
  if (!asset) return <aside className="ops-card graph-inspector"><p>Select an Asset to inspect recorded knowledge.</p></aside>;
  const type = view.types[asset.asset_type], site = sites.find(s => s.id === asset.site_id);
  const interfaces = view.interfaces.filter(i => i.asset_id === asset.id);
  const relationships = view.relationships.filter(r => r.source_asset_id === asset.id || r.target_asset_id === asset.id);
  return <aside className="ops-card graph-inspector" aria-label="Topology inspector"><header className="inspector-identity"><AssetIcon asset={asset} assetType={type} size={36} /><div><h2>{asset.name}</h2><p>{type?.name} · {type?.category}</p></div></header><dl className="ops-definition"><dt>Recorded status</dt><dd>{asset.status}</dd>{site && <><dt>Site</dt><dd>{site.name}</dd></>}{asset.hostname && <><dt>Hostname</dt><dd>{asset.hostname}</dd></>}</dl><h3>Interfaces & Networks</h3>{interfaces.length ? <ul className="inspector-relationships">{interfaces.map(i => <li key={i.id}><strong>{i.name}</strong><span>{[i.ip_address, i.mac_address, view.networks.find(n => n.id === i.network_id)?.name].filter(Boolean).join(" · ")}</span></li>)}</ul> : <p className="ops-meta">No visible interfaces recorded.</p>}<h3>Key recorded relationships</h3><ul className="inspector-relationships">{relationships.slice(0, 12).map(r => <li key={r.id}><button type="button" className="text-button" onClick={() => select(view.byId[r.source_asset_id])}>{view.byId[r.source_asset_id].name}</button><span>{r.display_label || r.relationship_type} {r.directional === false ? "↔" : "→"}</span><button type="button" className="text-button" onClick={() => select(view.byId[r.target_asset_id])}>{view.byId[r.target_asset_id].name}</button></li>)}</ul>{relationships.length > 12 && <p className="ops-meta">Showing 12 of {relationships.length} visible relationships.</p>}<footer className="inspector-actions"><Link className="button button-secondary" href={`/assets/${asset.id}`}>Open Asset</Link><Link className="button button-secondary" href={`/knowledge-graph?focus=asset:${asset.id}&depth=1`}>View in Knowledge Graph</Link>{onFocus && <button type="button" className="button button-secondary" onClick={() => onFocus(asset)}>Focus Connectivity</button>}</footer></aside>;
}
