"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { NavigationIcon } from "./navigation-icon.mjs";
import { presentationAttributes, presentationIcon } from "../lib/presentation.mjs";
import { showcaseLayout, showcaseModel } from "../lib/showcase.mjs";
import { showcaseResources, exportShowcasePng } from "../lib/showcase-export.mjs";

// Fixed SVG text budgets are independent of browser width. Full names remain in
// accessible SVG titles; no operational properties enter the scene.
let textMeasure;
function fitted(value, width, size, weight = 400) {
  const letters = Array.from(value || "");
  if (typeof document === "undefined") return value;
  textMeasure ||= document.createElement("canvas").getContext("2d");
  if (!textMeasure) return value;
  textMeasure.font = `${weight} ${size}px Arial`;
  if (textMeasure.measureText(value || "").width <= width) return value;
  while (letters.length && textMeasure.measureText(`${letters.join("")}…`).width > width) letters.pop();
  return `${letters.join("")}…`;
}
function Icon({ node, resources, x, y, size = 40 }) {
  const record = node.category || node.network;
  const source = resources?.icons[node.key];
  return <g transform={`translate(${x} ${y})`} {...presentationAttributes(record)}>
    <rect width={size} height={size} rx="9" style={{ fill: "var(--identity-tile)" }} />
    {source ? <image href={source} x="5" y="5" width={size - 10} height={size - 10} /> :
      <svg x={size * .2} y={size * .2} width={size * .6} height={size * .6} viewBox="0 0 24 24" style={{ color: "var(--identity-foreground)" }}><NavigationIcon name={presentationIcon(record?.icon_key, node.network ? "network" : "infrastructure").navigation} /></svg>}
  </g>;
}
function Tile({ node, resources, x = 0, y = 0, compact = false }) {
  const name = node.name, type = node.type?.name || (node.network ? "Network membership" : "Asset");
  return <g transform={`translate(${x} ${y})`} data-showcase-asset={node.asset?.id}>
    <title>{name} · {type}</title>
    <Icon node={node} resources={resources} x={0} y={compact ? 5 : 0} size={compact ? 28 : 42} />
    <text x={compact ? 35 : 54} y={compact ? 16 : 17} fontSize={compact ? 15 : 18} fontWeight="600">{fitted(name, compact ? 89 : 154, compact ? 15 : 18, 600)}</text>
    <text x={compact ? 35 : 54} y={compact ? 35 : 39} fontSize="14" fill="#526477">{fitted(type, compact ? 89 : 154, 14)}</text>
  </g>;
}
function Scene({ layout, site, resources, svgRef }) {
  return <svg ref={svgRef} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="1920" height="1080" role="img" aria-label={`${site.name} — Atlas Showcase`} className="showcase-scene" style={{ display: "block", width: "100%", height: "auto", colorScheme: "light", background: "#ffffff", fontFamily: "Arial, sans-serif", color: "#17283e", fill: "#17283e" }} data-stage={layout.stage}>
    <title>{site.name} — Atlas Showcase</title>
    <desc>Whole-site infrastructure. Asset relationships determine branches. Category groups stay with their hosts. Dashed connectors indicate recorded Network membership.</desc>
    <rect width="1920" height="1080" fill="#ffffff" />
    {resources?.logo ? <image href={resources.logo} x="30" y="20" width="220" height="83" /> : <text x="44" y="76" fontSize="32" fontWeight="700">Atlas Impact</text>}
    <path d="M282 38V94" stroke="#cbd5e1" strokeWidth="1.5" />
    <text x="314" y="81" fontSize="38" fontWeight="600"><title>{site.name}</title>{fitted(site.name, 1540, 38, 600)}</text>
    <path d="M44 120H1876" stroke="#e4eaf0" />
    <g transform={`translate(${layout.x} ${layout.y}) scale(${layout.scale})`}>
      {layout.footer && <g><rect {...layout.footer} rx="10" fill="#fafbfc" stroke="#e1e7ee" strokeDasharray="4 4" /><text x={layout.footer.x + 16} y={layout.footer.y + 27} fontSize="16" fontWeight="600">Unconnected / Other</text></g>}
      <g fill="none" stroke="#64788f" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round">
        {layout.routes.map(route => <path key={route.key} d={route.path} strokeDasharray={route.kind === "membership" ? "5 5" : undefined} data-showcase-connector={route.key} />)}
      </g>
      {layout.items.map(item => <g key={item.key} transform={`translate(${item.x} ${item.y})`} data-showcase-item={item.key} data-showcase-kind={item.kind} {...presentationAttributes(item.category || item.network)}>
        {item.kind === "asset" ? <>
          <rect width={item.cardWidth} height={item.cardHeight} rx="10" fill="#ffffff" stroke="#d8e2ee" />
          {item.position && <text x="14" y="21" fontSize="14" fill="#536b84"><title>{item.position.name}</title>{fitted(item.position.name, item.cardWidth - 28, 14)}</text>}
          <Tile node={item} resources={resources} x={14} y={item.position ? 36 : 26} />
        </> : <>
          <rect width={item.cardWidth} height={item.cardHeight} rx="10" style={{ fill: "var(--identity-tint)", stroke: "var(--identity-border)" }} />
          <text x="14" y="23" fontSize="17" fontWeight="600" style={{ fill: "var(--identity-foreground)" }}><title>{item.name}</title>{fitted(item.name, item.cardWidth - 28, 17, 600)}</text>
          <text x="14" y="44" fontSize="14" fill="#526477">{item.members.length} {item.kind === "category" ? (item.members.length === 1 ? "workload" : "workloads") : (item.members.length === 1 ? "device" : "devices")}</text>
          {item.preview.map((node, index) => <Tile key={node.key} node={node} resources={resources} compact x={12 + (index % 2) * 132} y={item.memberTop + Math.floor(index / 2) * item.memberRow} />)}
          {item.hiddenCount > 0 && <g><rect x={item.cardWidth - 65} y={item.cardHeight - 32} width="51" height="24" rx="12" style={{ fill: "var(--identity-tile)" }} /><text x={item.cardWidth - 39} y={item.cardHeight - 15} textAnchor="middle" fontSize="14" fontWeight="600" style={{ fill: "var(--identity-foreground)" }}>+{item.hiddenCount}</text></g>}
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
    if (!layout.complete) return;
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
    <div className="showcase-frame"><Scene layout={layout} site={site} resources={resources} svgRef={svg} /></div>
  </section>;
}
