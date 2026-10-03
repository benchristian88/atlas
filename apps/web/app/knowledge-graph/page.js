"use client";

import { Button } from "../../components/button";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "../../components/auth-context";
import { AccessDenied } from "../../components/access-denied";
import { PageHeader } from "../../components/page-header";
import { useWorkspaceContext } from "../../components/workspace-context";
import { ServiceLandscape } from "../../components/service-landscape";
import { DetailsPanelToggle } from "../../components/details-panel-toggle";
import { ExpandedGraphSurface } from "../../components/expanded-graph-surface";
import { NavigationIcon } from "../../components/navigation-icon.mjs";
import { GraphInspector } from "../../components/graph-inspector";
import { apiRequest } from "../../lib/api";
import { LANES, RELATIONSHIPS, analysisOverlay, graphHref, parseGraphState, projectVisibleGraph, visibleGraphSelection } from "../../lib/operations-experience.mjs";

export default function KnowledgeGraphPage() { return <Suspense fallback={<p role="status">Loading Knowledge Graph…</p>}><KnowledgeGraph /></Suspense>; }

function KnowledgeGraph() {
  const params = useSearchParams();
  const workspace = useWorkspaceContext();
  const { hasAnyPermission, hasPermission } = useAuth();
  const [expanded, setExpanded] = useState(false);
  const [detailsHidden, setDetailsHidden] = useState(false);
  const expandButton = useRef(null);
  const expansionScroll = useRef({ left: 0, top: 0 });
  const urlState = useMemo(() => parseGraphState(params), [params]);
  const state = useMemo(() => ({ ...urlState, depth: expanded ? urlState.depth : Math.min(2, urlState.depth) }), [urlState, expanded]);
  const graphCache = useRef(new Map());
  const [graph, setGraph] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [selected, setSelected] = useState(state.focus);
  const [group, setGroup] = useState(null);
  const [error, setError] = useState("");
  const [analysisError, setAnalysisError] = useState("");
  const [locateRequest, setLocateRequest] = useState(null);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState([]);
  const [searchError, setSearchError] = useState("");
  const [searching, setSearching] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [fitKey, setFitKey] = useState(0);
  const [retry, setRetry] = useState(0);
  const canView = hasAnyPermission(["assets.view", "services.view", "business_functions.view"]);
  const update = (patch) => window.history.pushState(null, "", graphHref({ ...state, ...patch }));
  function closeExpanded() {
    setExpanded(false);
    if (urlState.depth === 3) window.history.replaceState(null, "", graphHref({ ...urlState, depth: 2 }));
  }
  const selectNode = (node) => { setSelected(node.key); setGroup(null); };
  const focusNode = (node) => { selectNode(node); setSearch(""); update({ focus: node.key, analysis: false, types: state.types.includes(node.entity_type) ? state.types : [...state.types, node.entity_type] }); };
  useEffect(() => { graphCache.current.clear(); setSelected(state.focus); setGroup(null); }, [state.focus, workspace.customerId, workspace.siteId, retry]);
  useEffect(() => {
    if (!canView || !workspace.customerId || !workspace.siteId) return;
    let active = true;
    setGraph(null); setError("");
    const [type, id] = state.focus.split(":");
    const path = state.focus ? `/operational-graph?focus_type=${type}&focus_id=${id}&max_depth=${state.depth}&site_viewpoint=true` : "/operational-graph/landscape";
    const cached = graphCache.current.get(path);
    if (cached) { setGraph(cached); return () => { active = false; }; }
    apiRequest(path).then((value) => { if (active) { graphCache.current.set(path, value); setGraph(value); } }).catch((e) => { if (active) setError(e.message || "Atlas could not load the graph."); });
    return () => { active = false; };
  }, [canView, state.focus, state.depth, workspace.customerId, workspace.siteId, retry]);
  useEffect(() => {
    let active = true;
    setAnalysis(null); setAnalysisError("");
    if (!state.analysis || !state.focus || !canView || !workspace.customerId || !workspace.siteId) return () => { active = false; };
    const [focus_type, focus_id] = state.focus.split(":");
    apiRequest("/dependency-analysis?site_viewpoint=true", { method: "POST", body: JSON.stringify({ focus_type, focus_id, state: "unavailable" }) }).then((value) => { if (active) setAnalysis(value); }).catch((e) => { if (active) setAnalysisError(e.message || "Atlas could not preview this scenario."); });
    return () => { active = false; };
  }, [state.analysis, state.focus, canView, workspace.customerId, workspace.siteId, retry]);
  useEffect(() => {
    let active = true;
    setResults([]); setSearchError(""); setSearching(false);
    if (!search.trim() || !workspace.customerId) return () => { active = false; };
    setSearching(true);
    const timer = setTimeout(async () => {
      try {
        const sources = [["asset", "/assets", "assets.view"], ["service", "/services", "services.view"], ["business_function", "/business-functions", "business_functions.view"]].filter(([, , permission]) => hasPermission(permission));
        const lists = await Promise.all(sources.map(async ([type, path]) => {
          const records = await apiRequest(`${path}?search=${encodeURIComponent(search.trim())}&limit=8&active_only=true`, { omitContext: true, headers: { "X-Atlas-Customer-ID": workspace.customerId } });
          return records.map((r) => ({ key: `${type}:${r.id}`, entity_id: r.id, entity_type: type, name: r.name }));
        }));
        if (active) setResults(lists.flat());
      } catch (e) { if (active) setSearchError(e.message || "Search unavailable."); }
      finally { if (active) setSearching(false); }
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [search, workspace.customerId, hasPermission]);
  const displayed = useMemo(() => analysisOverlay(graph || {}, analysis), [graph, analysis]);
  const visibleGraph = useMemo(() => projectVisibleGraph(displayed, { types: state.types, families: state.families, focus: state.focus, analysis: Boolean(analysis) }), [displayed, state.types, state.families, state.focus, analysis]);
  const localMatches = useMemo(() => search.trim() ? visibleGraph.nodes.filter(node => node.name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())) : [], [visibleGraph, search]);
  const { node: selectedNode, group: visibleGroup } = visibleGraphSelection(visibleGraph, selected, state.focus, group);
  useEffect(() => {
    if (!graph) return;
    if (selected !== (selectedNode?.key || "")) setSelected(selectedNode?.key || "");
    if (group && !visibleGroup) setGroup(null);
  }, [graph, selected, selectedNode, group, visibleGroup]);
  const scenarioName = displayed.nodesByKey[state.focus]?.name;
  function toggle(key, value) { update({ [key]: state[key].includes(value) ? state[key].filter((v) => v !== value) : [...state[key], value] }); }
  if (!canView) return <AccessDenied />;
  return <div className="operations-page"><PageHeader variant="canvas" title="Knowledge Graph" description="Why it matters, what delivers it, and what implements it." />
    {!workspace.customerId || !workspace.siteId ? <p className="ops-card">Select a Customer and Site to explore recorded knowledge.</p> : <ExpandedGraphSurface expanded={expanded} onClose={closeExpanded} returnFocus={expandButton} scrollPosition={expansionScroll}>
      <div className="graph-toolbar" aria-label="Knowledge Graph controls">
        <div className="ops-segments" aria-label="Graph mode"><button type="button" aria-pressed={!state.focus} onClick={() => update({ focus: "", analysis: false })}>Overview</button><button type="button" aria-pressed={Boolean(state.focus)} disabled={!selectedNode} onClick={() => focusNode(selectedNode)}>Focus</button></div>
        <div className="graph-find"><label className="sr-only" htmlFor="graph-find">Find in graph</label><input id="graph-find" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Find in graph…" type="search" aria-controls="graph-search-results" />{search.trim() && <div id="graph-search-results" className="graph-search-results"><ul aria-label="Matches in visible graph">{localMatches.map(node => <li key={node.key}><button type="button" onClick={() => { selectNode(node); setLocateRequest({ key: node.key }); setSearch(""); }}>{node.name}<small>Locate in current graph</small></button></li>)}</ul><p className="ops-meta">Focus another entity: authorized matches in this Customer; up to 8 of each type. Refine your search for more.</p>{searching && <p role="status">Searching…</p>}{searchError && <p role="alert">{searchError}</p>}{!searching && !searchError && !results.length && !localMatches.length && <p role="status">No matches.</p>}<ul>{results.map((node) => <li key={node.key}><button type="button" onClick={() => focusNode(node)}>{node.name}<small>{node.entity_type.replaceAll("_", " ")}</small></button></li>)}</ul></div>}</div>
        {state.focus && <div className="ops-segments" aria-label="Focus depth">{(expanded ? [1, 2, 3] : [1, 2]).map((depth) => <button type="button" key={depth} aria-label={`Depth ${depth}`} aria-pressed={state.depth === depth} onClick={() => update({ depth })}>{depth}</button>)}</div>}
        <Button variant="secondary" type="button" aria-expanded={showFilters} onClick={() => setShowFilters((value) => !value)}>Filters</Button>
        {state.focus && !state.focus.startsWith("business_function:") && !state.analysis && <Button variant="secondary" type="button" onClick={() => update({ analysis: true })}>Preview unavailable</Button>}
        <Button variant="secondary" type="button" onClick={() => setFitKey((n) => n + 1)}>Fit</Button>
        <DetailsPanelToggle hidden={detailsHidden} onToggle={() => setDetailsHidden(value => !value)} />
        <button ref={expandButton} hidden={expanded} className="button button-secondary graph-icon-button" type="button" aria-label="Expand Knowledge Graph" title="Expand Knowledge Graph" onClick={() => { expansionScroll.current = { left: window.scrollX, top: window.scrollY }; setExpanded(true); }}><NavigationIcon name="expand" /></button>
      </div>
      {showFilters && <section className="ops-card graph-filters" aria-label="Graph filters"><fieldset><legend>Node types</legend>{LANES.map((lane) => <label key={lane.type}><input type="checkbox" checked={state.types.includes(lane.type)} onChange={() => toggle("types", lane.type)} />{lane.label}</label>)}</fieldset><fieldset><legend>Relationships</legend>{Object.entries(RELATIONSHIPS).map(([key, label]) => <label key={key}><input type="checkbox" checked={state.families.includes(key)} onChange={() => toggle("families", key)} />{label}</label>)}</fieldset></section>}
      {state.analysis && <section className="analysis-scenario" aria-label="Hypothetical scenario"><div><strong>Scenario: {scenarioName || "selected entity"} unavailable</strong><p>{analysis?.assumption || "Previewing consequences in authorized recorded knowledge…"}</p></div><Button variant="secondary" type="button" onClick={() => update({ analysis: false })}>Exit analysis</Button></section>}
      {error && <div className="error-banner" role="alert">{error} <button type="button" className="text-button" onClick={() => setRetry((n) => n + 1)}>Try again</button></div>}
      {analysisError && <div className="error-banner" role="alert">{analysisError}</div>}
      {(graph?.truncated || analysis?.truncated) && <div className="warning-banner" role="status">{[...(graph?.warnings || []), ...(analysis?.warnings || [])].join(" ")}</div>}
      {!graph && !error && <div className="ops-card" role="status">Loading Knowledge Graph…</div>}
      {graph && <div className={`graph-workspace${detailsHidden ? " topology-details-hidden" : ""}`}><section className="ops-card graph-surface" aria-label="Graph workspace">{!graph.nodes.length ? <div className="ops-guided"><h2>Build your service landscape</h2><p>Record Services and their relationships to Assets and Business Functions.</p>{hasPermission("services.create") && <Link className="button button-primary" href="/services/new">Add a Service</Link>}{hasPermission("knowledge_gaps.view") && <Link className="text-button" href="/knowledge-gaps">Open Knowledge Gaps</Link>}</div> : <ServiceLandscape expandedView={expanded} detailsHidden={detailsHidden} graph={displayed} selected={selectedNode?.key || ""} selectedGroup={visibleGroup?.dependency_group_id || ""} centerKey={state.focus} types={state.types} families={state.families} siteId={workspace.siteId} fitKey={fitKey} locateRequest={locateRequest} analysis={analysis} onSelect={selectNode} onFocus={focusNode} onGroup={setGroup} />}</section>
        {!detailsHidden && <GraphInspector key={selectedNode?.key || "empty"} selected={selectedNode} group={visibleGroup} graph={displayed} analysis={analysis} analysisActive={state.analysis} siteId={workspace.siteId} onFocus={focusNode} onSelect={selectNode} onPreview={(node) => { setSelected(node.key); update({ focus: node.key, analysis: true }); }} />}
      </div>}
      {state.analysis && analysis && !analysis.results.length && <p className="ops-card" role="status">No Service consequences were found in the authorized knowledge for this scenario.</p>}
    </ExpandedGraphSurface>}
  </div>;
}
