"use client";

import { PresentationIcon } from "./presentation-identity.mjs";
import { useState } from "react";
import { assetIconSources, GENERIC_ICON } from "../lib/asset-icon.mjs";

function IconImage({ sources, alt, className, size, presentation }) {
  const [index, setIndex] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const source = sources[index];
  return <span className={`asset-icon${className ? ` ${className}` : ""}`} style={{ width: size, height: size }} role={alt ? "img" : undefined} aria-label={alt || undefined} aria-hidden={alt ? undefined : true}>
    {presentation ? <span className="asset-icon-fallback" style={{ opacity: loaded ? 0 : 1 }}><PresentationIcon record={presentation} /></span> : <img alt="" src={GENERIC_ICON} width={size} height={size} style={{ opacity: loaded ? 0 : 1 }} />}
    {source !== GENERIC_ICON && <img key={source} alt="" src={source} width={size} height={size}
      loading="lazy" decoding="async" referrerPolicy="no-referrer"
      style={{ opacity: loaded ? 1 : 0 }}
      onLoad={() => setLoaded(true)}
      onError={() => { setLoaded(false); setIndex(Math.min(index + 1, sources.length - 1)); }} />}
  </span>;
}

export function AssetIcon({ asset, assetType, alt = "", className = "", size = 32, presentation }) {
  const sources = assetIconSources(asset, assetType, process.env.NEXT_PUBLIC_API_URL);
  // Remount on URL changes so failure/loading state cannot leak between Assets.
  return <IconImage key={sources.join("|")} sources={sources} alt={alt} className={className} size={size} presentation={presentation} />;
}

export { GENERIC_ICON };
