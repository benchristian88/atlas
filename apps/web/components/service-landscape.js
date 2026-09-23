"use client";

import { landscapeGeometry, fitLandscape } from "../lib/landscape-geometry.mjs";
import { AssetIcon } from "./asset-icon";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { analysisState, presentLandscape } from "../lib/operations-experience.mjs";
import { EntityMark, RecordedStatus } from "./operations-primitives";

// Pan only this canvas; locating a node must not scroll the page or modal toolbar.
function locateNode(viewport, key) {
  const node = key && viewport?.querySelector(`[data-node-key="${CSS.escape(key)}"]`);
  if (!node) return;
  const bounds = viewport.getBoundingClientRect(), target = node.getBoundingClientRect();
  const vertical = target.top < bounds.top ? target.top - bounds.top : target.bottom > bounds.bottom ? target.bottom - bounds.bottom : 0;
  viewport.scrollTo({ left: viewport.scrollLeft + target.left - bounds.left - (viewport.clientWidth - target.width) / 2, top: viewport.scrollTop + vertical, behavior: "instant" });
}

export function ServiceLandscape({ graph, compact = false, selected = "", onSelect, onFocus, onGroup, siteId, types, families, quick, analysis, fitKey = 0, expandedView = false, detailsHidden = false, centerKey = "", locateRequest = null }) {
  const viewport = useRef(null);
  const [expanded, setExpanded] = useState([]);
  const [zoom, setZoom] = useState(1);
  const [viewportWidth, setViewportWidth] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(0);
  useLayoutEffect(() => {
    const element = viewport.current;
    let frame;
    const measure = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        setViewportWidth(element.clientWidth);
        setViewportHeight(element.clientHeight);
      });
    };
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    measure();
    return () => { observer.disconnect(); cancelAnimationFrame(frame); };
  }, [expandedView, detailsHidden]);
  const presentation = useMemo(() => presentLandscape(graph, { types, families, quick, limit: compact ? 5 : 8, expanded, selected, focus: centerKey, analysis: Boolean(analysis) }), [graph, types, families, quick, compact, expanded, selected, centerKey, analysis]);
  const layout = useMemo(() => {
    let stepX = compact ? Math.max(222, viewportWidth / 3) : 330;
    const nodeWidth = compact ? stepX - 36 : 226;
    // Expanded mode spends less height on empty inter-card space so Fit can
    // keep cards readable. Dependency markers retain their full clearance.
    const stepY = compact ? 98 : expandedView ? 104 : 140;
    const positions = new Map();
    const groupIdsBySource = new Map();
    if (!compact) for (const edge of presentation.edges) if (edge.dependency_group_id) {
      if (!groupIdsBySource.has(edge.source_key)) groupIdsBySource.set(edge.source_key, new Set());
      groupIdsBySource.get(edge.source_key).add(edge.dependency_group_id);
    }
    let height = 300;
    presentation.lanes.forEach((lane, index) => {
      let y = 70;
      lane.nodes.forEach((node) => {
        positions.set(node.key, { x: index * stepX + 12, y, node });
        const groupCount = groupIdsBySource.get(node.key)?.size || 0;
        y += compact ? stepY : Math.max(stepY, groupCount ? 115 + groupCount * 58 : 0);
      });
      height = Math.max(height, y + 50);
    });
    if (!compact && expandedView) {
      stepX = landscapeGeometry(viewportWidth, viewportHeight, height).stepX;
      presentation.lanes.forEach((lane, index) => lane.nodes.forEach((node) => {
        positions.get(node.key).x = index * stepX + 12;
      }));
    }
    const groups = new Map();
    if (!compact) for (const edge of presentation.edges) if (edge.dependency_group_id) {
      const key = `dependency_group:${edge.dependency_group_id}`;
      if (!groups.has(key)) {
        const subject = positions.get(edge.source_key);
        const groupIndex = [...groupIdsBySource.get(edge.source_key)].indexOf(edge.dependency_group_id);
        groups.set(key, { ...edge, key, x: subject.x + nodeWidth - 110, y: subject.y + 100 + groupIndex * 58, edges: [] });
      }
      groups.get(key).edges.push(edge);
    }
    return { nodeWidth, stepX, positions, groups: [...groups.values()], width: stepX * 3, height };
  }, [presentation, compact, viewportWidth, viewportHeight, expandedView]);

  // Fit only for explicit requests or structural viewport changes. Selection,
  // graph presentation and manual zoom/pan must not continually reset the view.
  useLayoutEffect(() => {
    if (compact || !viewportWidth || !viewportHeight) return;
    setZoom(fitLandscape(viewportWidth, viewportHeight, layout.width, layout.height));
    viewport.current.scrollTo({ left: 0, top: 0 });
    // Layout/content changes alone must not undo manual zoom or pan.
  }, [fitKey, expandedView, detailsHidden, viewportWidth, viewportHeight, compact]);
  useEffect(() => {
    if (!centerKey) return;
    locateNode(viewport.current, centerKey);
  }, [centerKey, graph]);

  useEffect(() => {
    if (!locateRequest) return;
    locateNode(viewport.current, locateRequest.key);
  }, [locateRequest]);

  const pathKeys = new Set((analysis?.results || []).flatMap((r) => r.paths.flatMap((p) => p.edges.map((e) => e.key))));
  function edgePath(source, target, sourceWidth = layout.nodeWidth) {
    if (source.x === target.x) {
      const x = source.x + layout.nodeWidth;
      return `M${x} ${source.y + 30} C${x + 42} ${source.y + 30},${x + 42} ${target.y + 30},${x} ${target.y + 30}`;
    }
    const right = source.x < target.x;
    const x1 = source.x + (right ? sourceWidth : 0), x2 = target.x + (right ? 0 : layout.nodeWidth);
    const mid = (x1 + x2) / 2;
    return `M${x1} ${source.y + 30} C${mid} ${source.y + 30},${mid} ${target.y + 30},${x2} ${target.y + 30}`;
  }
  const drag = useRef(null);
  return <div className={`service-landscape ${compact ? "landscape-compact" : ""}`}>
    {!compact && <div className="landscape-zoom" aria-label="Graph zoom"><button type="button" aria-label="Zoom out" onClick={() => setZoom((z) => Math.max(.1, z - .1))}>−</button><span>{Math.round(zoom * 100)}%</span><button type="button" aria-label="Zoom in" onClick={() => setZoom((z) => Math.min(1.5, z + .1))}>+</button></div>}
    <div className="landscape-viewport" ref={viewport} style={!compact && !expandedView ? { height: `min(66vh, ${layout.height}px)` } : undefined} tabIndex={0} aria-label="Service landscape. Scroll to explore." onPointerDown={(event) => {
      if (event.pointerType !== "mouse" || event.target.closest("button, a")) return;
      drag.current = { x: event.clientX, y: event.clientY, left: event.currentTarget.scrollLeft, top: event.currentTarget.scrollTop };
      event.currentTarget.setPointerCapture(event.pointerId);
    }} onPointerMove={(event) => { if (drag.current) { event.currentTarget.scrollLeft = drag.current.left + drag.current.x - event.clientX; event.currentTarget.scrollTop = drag.current.top + drag.current.y - event.clientY; } }} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
      <div style={{ width: layout.width * zoom, height: layout.height * zoom, marginInline: "auto", ...(!compact ? { marginBlock: 16 } : {}) }}>
        <div className="landscape-canvas" style={{ width: layout.width, height: layout.height, transform: `scale(${zoom})` }}>
          {presentation.lanes.map((lane, index) => <section className={`landscape-lane entity-${lane.type}`} key={lane.type} style={{ left: index * layout.stepX, width: layout.stepX - 12, height: layout.height }} aria-label={lane.label}>
            <header><EntityMark type={lane.type} /><div><h3>{lane.label} <span>({lane.total})</span></h3><small>{lane.description}</small></div></header>
            {!lane.total && <p className="lane-empty">No {lane.label.toLowerCase()} in this view.</p>}
          </section>)}
          <svg className="landscape-connectors" width={layout.width} height={layout.height} aria-hidden="true">
            <defs><marker id={compact ? "overview-arrow" : "graph-arrow"} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0 10 5 0 10Z" fill="currentColor" /></marker></defs>
            {presentation.edges.map((edge) => {
              const group = layout.groups.find((g) => g.dependency_group_id === edge.dependency_group_id);
              const source = group ? { x: group.x, y: group.y - 10 } : layout.positions.get(edge.source_key), target = layout.positions.get(edge.target_key);
              return <path key={edge.key} d={edgePath(source, target, group ? 135 : layout.nodeWidth)} markerEnd={`url(#${compact ? "overview-arrow" : "graph-arrow"})`} className={`${edge.edge_family === "service_service" ? "secondary-dependency" : ""} ${analysis ? pathKeys.has(edge.key) ? "consequence-path" : "context-edge" : ""}`}><title>{edge.source.name} — {edge.label} → {edge.target.name}</title></path>;
            })}
            {layout.groups.map((group) => { const subject = layout.positions.get(group.source_key); return <path key={group.key} d={`M${subject.x + layout.nodeWidth / 2} ${subject.y + 64} V${group.y - 8} H${group.x + 67} V${group.y}`} />; })}
          </svg>
          {[...layout.positions.values()].map(({ node, x, y }) => {
            const state = analysisState(node, analysis);
            return <button className={`landscape-node entity-${node.entity_type} ${node.key === selected ? "is-selected" : ""} ${state ? `analysis-${state}` : analysis ? "analysis-context" : ""}`} key={node.key} data-node-key={node.key} style={{ left: x, top: y, width: layout.nodeWidth }} type="button" aria-pressed={node.key === selected} aria-label={`${node.entity_type.replaceAll("_", " ")}: ${node.name}${state ? `. Scenario: ${state}` : ""}`} onClick={() => onSelect?.(node)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect?.(node); } }} onDoubleClick={() => onFocus?.(node)}>
              {node.entity_type === "asset" ? <AssetIcon asset={node} size={32} /> : <EntityMark type={node.entity_type} />}<span className="landscape-node-text"><strong>{node.name}</strong><small>{node.entity_type.replaceAll("_", " ")}{!compact && node.criticality_name && <span className="ops-badge">{node.criticality_name}</span>}</small>
                {node.site_id && node.site_id !== siteId && <small className="site-badge">{node.site_name || "Another authorized Site"}</small>}
                {state && <small className="analysis-label">{state.toUpperCase()}</small>}
              </span>{node.entity_type !== "business_function" && <RecordedStatus state={node.operational_state || node.lifecycle_state} />}
            </button>;
          })}
          {layout.groups.map((group) => <button className="dependency-presentation" style={{ left: group.x, top: group.y }} key={group.key} type="button" onClick={() => onGroup?.(group)}><strong>{group.dependency_group_name}</strong><small>{group.dependency_strategy === "all" ? "ALL REQUIRED" : "ANY ONE"}</small></button>)}
        </div>
      </div>
    </div>
    <div className="landscape-disclosure">{presentation.lanes.map((lane) => lane.omitted > 0 ? <button className={`landscape-more entity-${lane.type}`} key={lane.type} type="button" onClick={() => setExpanded((values) => [...values, lane.type])}>+ {lane.omitted} more {lane.label.toLowerCase()}</button> : expanded.includes(lane.type) && lane.total > (compact ? 5 : 8) ? <button className={`landscape-more entity-${lane.type}`} key={lane.type} type="button" onClick={() => setExpanded((values) => values.filter((v) => v !== lane.type))}>Show fewer {lane.label.toLowerCase()}</button> : null)}</div>
    {(presentation.omittedEdges > 0 || presentation.filteredNodes > 0) && <p className="ops-meta" role="status">{presentation.omittedEdges > 0 && `${presentation.omittedEdges} relationships connect collapsed items. Expand their lanes to see them. `}{presentation.filteredNodes > 0 && `${presentation.filteredNodes} items excluded by presentation filters.`}</p>}
    {!compact && <details className="graph-semantic-list"><summary>Recorded relationships in this view ({presentation.edges.length})</summary><ul>{presentation.edges.map((edge) => <li key={edge.key}><button className="text-button" type="button" onClick={() => onSelect?.(edge.source)}>{edge.source.name}</button> — {edge.label} → <button className="text-button" type="button" onClick={() => onSelect?.(edge.target)}>{edge.target.name}</button>{edge.dependency_group_name && ` · ${edge.dependency_group_name}`}</li>)}</ul></details>}
  </div>;
}
