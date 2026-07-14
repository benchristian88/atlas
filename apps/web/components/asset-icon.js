"use client";

import { useEffect, useMemo, useState } from "react";

const GENERIC_ICON = `data:image/svg+xml,${encodeURIComponent(`
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
    <rect width="48" height="48" rx="10" fill="#def3ee"/>
    <rect x="11" y="10" width="26" height="9" rx="2" fill="#1a7f72"/>
    <rect x="11" y="22" width="26" height="9" rx="2" fill="#1a7f72"/>
    <rect x="11" y="34" width="26" height="4" rx="2" fill="#1a7f72"/>
    <circle cx="16" cy="14.5" r="1.5" fill="#fff"/>
    <circle cx="16" cy="26.5" r="1.5" fill="#fff"/>
  </svg>
`)}`;

function safeIconUrl(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  const candidate = value.trim();
  if (candidate.startsWith("/") && !candidate.startsWith("//")) return candidate;
  try {
    const url = new URL(candidate);
    if (url.protocol === "https:") return url.href;
    if (
      url.protocol === "http:"
      && ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)
    ) return url.href;
  } catch {
    return null;
  }
  return null;
}

export function AssetIcon({ asset, assetType, alt = "", className = "", size = 32 }) {
  const sources = useMemo(() => {
    const candidates = [
      safeIconUrl(asset?.icon_url),
      safeIconUrl(assetType?.default_icon_url),
      GENERIC_ICON,
    ].filter(Boolean);
    return [...new Set(candidates)];
  }, [asset?.icon_url, assetType?.default_icon_url]);
  const [sourceIndex, setSourceIndex] = useState(0);

  useEffect(() => setSourceIndex(0), [sources]);

  function useFallback(event) {
    if (sourceIndex < sources.length - 1) {
      setSourceIndex(sourceIndex + 1);
      return;
    }
    event.currentTarget.onerror = null;
  }

  return (
    <img
      alt={alt}
      className={`asset-icon${className ? ` ${className}` : ""}`}
      height={size}
      loading="lazy"
      onError={useFallback}
      referrerPolicy="no-referrer"
      src={sources[sourceIndex] || GENERIC_ICON}
      width={size}
    />
  );
}

export { GENERIC_ICON };
