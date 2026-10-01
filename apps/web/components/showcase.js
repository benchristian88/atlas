"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { NavigationIcon } from "./navigation-icon.mjs";
import { presentationAttributes, presentationIcon } from "../lib/presentation.mjs";
import { showcaseLayout, showcaseModel } from "../lib/showcase.mjs";
import { showcaseResources, exportShowcasePng } from "../lib/showcase-export.mjs";

// Fixed SVG text budgets are independent of browser width. Full names remain in
// accessible SVG titles; no operational properties enter the scene.
let textMeasure;
function fitted(value, width, size, weight = 400, keepSuffix = false) {
  const letters = Array.from(value || "");
  if (typeof document === "undefined") return value;
  textMeasure ||= document.createElement("canvas").getContext("2d");
  if (!textMeasure) return value;
  textMeasure.font = `${weight} ${size}px Arial`;
  if (textMeasure.measureText(value || "").width <= width) return value;
  // Compact Assets must remain distinguishable in the exported image, including
  // numbered host/workload peers. Preserve both ends when the name is too long.
  if (keepSuffix) {
    let count = letters.length;
    while (count > 1) {
      const tail = Math.max(1, Math.floor(count / 3)), head = count - tail;
      const label = `${letters.slice(0, head).join("")}…${letters.slice(-tail).join("")}`;
      if (textMeasure.measureText(label).width <= width) return label;
      count--;
    }
    return "…";
  }
  while (letters.length && textMeasure.measureText(`${letters.join("")}…`).width > width) letters.pop();
  return `${letters.join("")}…`;
}
function Icon({ node, resources, x, y, size = 22 }) {
  const record = node.category || node.network;
  const source = resources?.icons[node.key];
  const inset = size <= 24 ? 1 : 4;
  return <g transform={`translate(${x} ${y})`} {...presentationAttributes(record)}>
    <rect width={size} height={size} rx="9" style={{ fill: "var(--identity-tile)" }} />
    {source ? <image href={source} x={inset} y={inset} width={size - inset * 2} height={size - inset * 2} /> :
      <svg x={inset} y={inset} width={size - inset * 2} height={size - inset * 2} viewBox="0 0 24 24" style={{ color: "var(--identity-foreground)" }}><NavigationIcon name={presentationIcon(record?.icon_key, node.network ? "network" : "infrastructure").navigation} /></svg>}
  </g>;
}
function Tile({ node, resources, x = 0, y = 0, compact = false, width = 184 }) {
  const iconSize = 22, textX = iconSize + 6, fontSize = 15;
  const textWidth = width - textX;
  return <g transform={`translate(${x} ${y})`} data-showcase-asset={node.asset?.id} data-text-width={textWidth}>
    <title>{node.name}</title>
    <Icon node={node} resources={resources} x={0} y={0} size={iconSize} />
    <text x={textX} y={compact ? 16 : 20} fontSize={fontSize} fontWeight="600">{fitted(node.name, textWidth, fontSize, 600, true)}</text>
  </g>;
}

function Scene({ layout, site, resources, svgRef }) {
  return <svg ref={svgRef} xmlns="http://www.w3.org/2000/svg" viewBox={`0 0 ${layout.sceneWidth} ${layout.sceneHeight}`} width={layout.sceneWidth} height={layout.sceneHeight} role="img" aria-label={`${site.name} — Atlas Showcase`} className="showcase-scene" style={{ display: "block", width: "100%", height: "auto", colorScheme: "light", background: "#ffffff", fontFamily: "Arial, sans-serif", color: "#17283e", fill: "#17283e" }} data-stage={layout.stage}>
    <title>{site.name} — Atlas Showcase</title>
    <desc>Whole-site infrastructure. Asset relationships determine branches. Category groups stay with their hosts. Logical Networks and interface memberships are excluded.</desc>
    <rect width={layout.sceneWidth} height={layout.sceneHeight} fill="#ffffff" />
    {resources?.logo ? <image href={resources.logo} x="26" y="10" width="164" height="62" /> : <text x="32" y="52" fontSize="26" fontWeight="700">Atlas Impact</text>}
    <path d="M222 23V63" stroke="#cbd5e1" strokeWidth="1.5" />
    <text x="248" y="55" fontSize="32" fontWeight="600"><title>{site.name}</title>{fitted(site.name, 1632, 32, 600)}</text>
    <path d="M32 84H1888" stroke="#e4eaf0" />
    <g transform={`translate(${layout.x} ${layout.y}) scale(${layout.scale})`}>
      {layout.footer && <g><rect {...layout.footer} rx="10" fill="#fafbfc" stroke="#e1e7ee" strokeDasharray="4 4" /><text x={layout.footer.x + 12} y={layout.footer.y + 20} fontSize="14" fontWeight="600">Unconnected / Other</text></g>}
      <g fill="none" stroke="#64788f" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round">
        {layout.routes.map(route => <path key={route.key} d={route.path} data-showcase-connector={route.key} />)}
      </g>
      {layout.positionLabels.map(label => <text key={label.key} x={label.x + 4} y={label.y + 12} fontSize="14" fill="#617185" data-showcase-position={label.positionId}><title>{label.name}</title>{fitted(label.name, label.width - 8, 14)}</text>)}
      {layout.items.map(item => <g key={item.key} transform={`translate(${item.x} ${item.y})`} data-showcase-item={item.key} data-showcase-kind={item.kind} {...presentationAttributes(item.category || item.network)}>
        {item.kind === "asset" ? <>
          <rect width={item.cardWidth} height={item.cardHeight} rx="8" fill="#ffffff" stroke="#d8e2ee" />
          <Tile node={item} resources={resources} x={8} y={5} width={item.cardWidth - 16} />
        </> : <>
          <rect width={item.cardWidth} height={item.cardHeight} rx="10" style={{ fill: "var(--identity-tint)", stroke: "var(--identity-border)" }} />
          <text x="12" y="21" fontSize="16" fontWeight="600" style={{ fill: "var(--identity-foreground)" }}><title>{item.name}</title>{fitted(item.name, item.cardWidth - 24, 16, 600)}</text>
          {item.kind === "type" && <text x="12" y={item.cardHeight - 10} fontSize="14" fill="#526477">{item.members.length} devices</text>}
          {item.preview.map((node, index) => <Tile key={node.key} node={node} resources={resources} compact width={item.memberColumns === 1 ? item.cardWidth - 24 : item.memberWidth} x={12 + (index % item.memberColumns) * (item.memberWidth + item.memberGap)} y={item.memberTop + Math.floor(index / item.memberColumns) * item.memberRow} />)}
          {item.hiddenCount > 0 && <g><rect x={item.cardWidth - 65} y={item.cardHeight - 25} width="51" height="20" rx="10" style={{ fill: "var(--identity-tile)" }} /><text x={item.cardWidth - 39} y={item.cardHeight - 10} textAnchor="middle" fontSize="14" fontWeight="600" style={{ fill: "var(--identity-foreground)" }}>+{item.hiddenCount}</text></g>}
        </>}
      </g>)}
    </g>
  </svg>;
}

export function Showcase({ data, site }) {
  const layout = useMemo(() => showcaseLayout(showcaseModel(data, site?.id)), [data, site?.id]);
  const [loaded, setLoaded] = useState(null), [exporting, setExporting] = useState(false), [error, setError] = useState("");
  const svg = useRef(null);
  const resources = loaded?.layout === layout ? loaded.resources : null;
  useEffect(() => {
    if (!layout.complete) {
      if (process.env.NODE_ENV === "development" && layout.diagnostics) console.debug("Showcase layout diagnostics", layout.diagnostics);
      return;
    }
    const controller = new AbortController();
    setError("");
    showcaseResources(layout, process.env.NEXT_PUBLIC_API_URL, controller.signal).then(resources => {
      if (!controller.signal.aborted) setLoaded({ layout, resources });
    }).catch(() => { if (!controller.signal.aborted) setError("Unable to prepare the Showcase images. Reload the page to try again."); });
    return () => controller.abort();
  }, [layout]);
  if (!site) return <p className="empty-state" role="status">Select a current site to create its Showcase.</p>;
  if (!layout.complete) return <p className="empty-state" role="status">{layout.reason}</p>;
  async function download() {
    setExporting(true); setError("");
    try { await exportShowcasePng(svg.current, site.name); }
    catch (e) { setError(e.message || "Unable to export the PNG. Please try again."); }
    finally { setExporting(false); }
  }
  return <section aria-label="Showcase" className="showcase">
    <div className="showcase-actions"><p>A shareable view of {site.name}.</p><button type="button" className="button button-primary" disabled={!resources || exporting} onClick={download}>{exporting ? "Exporting…" : "Export PNG"}</button></div>
    {error && <p className="error-banner" role="alert">{error}</p>}
    {!resources && <p role="status">Preparing Showcase images…</p>}
    <div className="showcase-frame" style={{ aspectRatio: `${layout.sceneWidth} / ${layout.sceneHeight}` }}><Scene layout={layout} site={site} resources={resources} svgRef={svg} /></div>
  </section>;
}
