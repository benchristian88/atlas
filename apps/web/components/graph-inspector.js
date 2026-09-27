"use client";

import { AssetIcon } from "./asset-icon";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { ANALYSIS_CLASSIFICATION_LABELS, ANALYSIS_STATE_LABELS, explainDependencyReason } from "../lib/dependency-analysis.mjs";
import { DEPENDENCY_REQUIREMENT_LABELS, DEPENDENCY_STRATEGY_LABELS, dependencyDetail, dependencyGroupLabel } from "../lib/dependency-semantics.mjs";
import { normalizeOperationalGraph } from "../lib/operational-graph.mjs";
import { CompletenessLine, EntityMark, RecordedStatus } from "./operations-primitives";

export function GraphInspector({ selected, group, graph, analysis, analysisActive, onFocus, onPreview, onSelect, siteId }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setDetail(null); setError("");
    if (!selected || group || analysisActive) return () => { active = false; };
    apiRequest(`/operational-graph?focus_type=${selected.entity_type}&focus_id=${selected.entity_id}&max_depth=1&site_viewpoint=true`).then((value) => { if (active) setDetail(normalizeOperationalGraph(value)); }).catch((e) => { if (active) setError(e.message || "Atlas could not load this entity."); });
    return () => { active = false; };
  }, [selected?.key, group, analysisActive]);
  const node = detail?.nodesByKey[selected?.key] || selected;
  const relationships = (detail || graph).edges.filter((e) => e.source_key === node?.key || e.target_key === node?.key);
  const result = analysis?.results.find((r) => r.service.key === node?.key);
  return <aside className="ops-card graph-inspector" aria-label="Graph inspector" aria-live="polite">
    {group ? <><p className="ops-meta">Dependency behaviour</p><h2>{dependencyGroupLabel(group)}</h2><dl className="ops-definition"><dt>Requirement</dt><dd>{DEPENDENCY_REQUIREMENT_LABELS[group.dependency_requirement]}</dd><dt>Strategy</dt><dd>{DEPENDENCY_STRATEGY_LABELS[group.dependency_strategy]}</dd><dt>If unsatisfied</dt><dd>{ANALYSIS_STATE_LABELS[group.failure_effect]}</dd></dl><h3>Visible members</h3><ul>{group.edges.map((edge) => <li key={edge.key}><button type="button" className="text-button" onClick={() => onSelect(edge.target)}>{edge.target.name}</button></li>)}</ul><p className="ops-meta">Existing dependency-group semantics. This group represents recorded relationships.</p></> : !node ? <div className="ops-guided"><h2>Explore your environment</h2><p>Select an entity to inspect its recorded knowledge. Double click or choose Focus to explore its neighbourhood.</p><p>Use Tab and Enter to select nodes with the keyboard.</p></div> : <>
      <header className="inspector-identity">{node.entity_type === "asset" ? <AssetIcon asset={node} size={32} /> : <EntityMark type={node.entity_type} />}<div><h2>{node.name}</h2><p>{node.subtitle || node.entity_type.replaceAll("_", " ")}</p></div></header>
      {node.site_id && node.site_id !== siteId && <p className="site-badge">{node.site_name || "Another authorized Site"}</p>}
      {analysisActive ? <>
        {!analysis && <p role="status">Waiting for scenario explanation…</p>}
        {node.entity_type === "business_function" ? <p>Business Function context only. Availability is not evaluated.</p> : node.key === analysis?.focus_key ? <><h3>Scenario assumption</h3><p>Unavailable</p></> : result ? <><h3>Result</h3><p className={`analysis-result analysis-${result.state}`}>{ANALYSIS_STATE_LABELS[result.state]}</p><h3>Classification</h3><p>{ANALYSIS_CLASSIFICATION_LABELS[result.classification]} · {result.distance} {result.distance === 1 ? "hop" : "hops"}</p><h3>Why?</h3>{result.reasons.map((reason) => <section key={reason.key}><p>{explainDependencyReason(result.service.name, reason)}</p><details><summary>Technical details</summary><h4>{reason.dependency_group_name || "Ungrouped dependency"}</h4><p>{DEPENDENCY_REQUIREMENT_LABELS[reason.dependency_requirement]} · {DEPENDENCY_STRATEGY_LABELS[reason.dependency_strategy]}</p><p>{reason.summary}</p><p>Configured effect: {ANALYSIS_STATE_LABELS[reason.failure_effect]}</p><ul>{reason.members.map((member) => <li key={member.edge.key}>{member.entity.name}: {ANALYSIS_STATE_LABELS[member.state]}</li>)}</ul><p>Reason: {reason.code}</p></details></section>)}<h3>Explanation paths</h3>{result.paths.map((path, index) => <ol className="explanation-path" key={index}>{path.nodes.map((item) => <li key={item.key}><button type="button" className="text-button" onClick={() => onSelect(graph.nodesByKey[item.key])}>{item.name}</button></li>)}</ol>)}</> : analysis && <p>No derived consequence is reported for this context entity. This does not establish live availability.</p>}
      </> : <>
        {error && <p role="alert">{error}</p>}
        {!detail && !error && <p role="status">Loading recorded details…</p>}
        {node.entity_type !== "business_function" && <dl className="ops-definition"><dt>Recorded status</dt><dd><RecordedStatus state={node.operational_state || node.lifecycle_state} /> {node.operational_state || node.lifecycle_state || "Unknown"}</dd>{node.criticality_name && <><dt>Criticality</dt><dd><span className="ops-badge">{node.criticality_name}</span></dd></>}{node.entity_type === "asset" && <><dt>Contextual IP</dt><dd>{node.contextual_ip || "Not recorded on an interface"}</dd><dt>Contextual VLAN</dt><dd>{node.contextual_vlan ?? "Not recorded / unavailable"}</dd></>}</dl>}
        <h3>Knowledge completeness</h3>{node.entity_type === "business_function" ? <p>Not evaluated for Business Functions.</p> : <><CompletenessLine node={node} /><p className="ops-meta">{node.completeness_status?.replaceAll("_", " ") || "Not evaluated"}</p></>}
        <h3>{node.entity_type === "business_function" ? "Supporting Services" : "Key relationships"} ({relationships.length}{detail?.truncated ? "+" : ""})</h3>
        {detail?.truncated && <p role="status">This neighbourhood is bounded. Focus another entity to explore further.</p>}
        {!relationships.length ? <p className="ops-meta">No visible relationships recorded in this neighbourhood.</p> : <ul className="inspector-relationships">{relationships.map((edge) => <li key={edge.key}><button type="button" className="text-button" onClick={() => onSelect(edge.source)}>{edge.source.name}</button><small>{edge.label} →</small><button type="button" className="text-button" onClick={() => onSelect(edge.target)}>{edge.target.name}</button>{edge.failure_effect && <small>{dependencyDetail(edge)}</small>}</li>)}</ul>}
      </>}
      <footer className="inspector-actions"><button type="button" className="button button-secondary" onClick={() => onFocus(node)}>Focus in graph</button><Link className="button button-secondary" href={node.href}>Open {node.entity_type.replaceAll("_", " ")}</Link>{node.entity_type !== "business_function" && !analysisActive && <button type="button" className="button button-primary" onClick={() => onPreview(node)}>Preview unavailable</button>}</footer>
    </>}
  </aside>;
}
