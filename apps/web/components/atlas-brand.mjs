"use client";

import React, { useState } from "react";
import Link from "next/link.js";

export const ATLAS_BRAND_ASSETS = {
  dark: [
    "/branding/lockups/atlas-impact-lockup-dark.svg",
    "/branding/lockups/atlas-impact-lockup-dark.png",
  ],
  light: [
    "/branding/lockups/atlas-impact-lockup-light.svg",
    "/branding/lockups/atlas-impact-lockup-light.png",
  ],
};

export function brandAssetForFailureCount(failureCount, variant = "dark") {
  return (ATLAS_BRAND_ASSETS[variant] || ATLAS_BRAND_ASSETS.dark)[failureCount] || null;
}

export function AtlasLogo({ className = "", fallbackClassName = "atlas-brand-fallback", variant = "dark" }) {
  const [failureCount, setFailureCount] = useState(0);
  const asset = brandAssetForFailureCount(failureCount, variant);

  return asset
    ? React.createElement("img", {
      alt: "Atlas Impact",
      className,
      height: 300,
      onError: () => setFailureCount((count) => count + 1),
      src: asset,
      width: 800,
    })
    : React.createElement("span", { className: fallbackClassName }, "Atlas Impact");
}

export function AtlasBrand({ href, variant = "dark" }) {
  return React.createElement(
    Link,
    { "aria-label": "Atlas Impact home", className: "brand atlas-brand", href },
    React.createElement(AtlasLogo, { className: "atlas-brand-logo", variant }),
  );
}
