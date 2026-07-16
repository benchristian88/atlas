"use client";

import React, { useState } from "react";
import Link from "next/link.js";

export const ATLAS_BRAND_ASSETS = [
  "/branding/atlas-logo.svg",
];

export function brandAssetForFailureCount(failureCount) {
  return ATLAS_BRAND_ASSETS[failureCount] || null;
}

export function AtlasBrand({ href }) {
  const [failureCount, setFailureCount] = useState(0);
  const asset = brandAssetForFailureCount(failureCount);

  return React.createElement(
    Link,
    { "aria-label": "Atlas home", className: "brand atlas-brand", href },
    asset
      ? React.createElement("img", {
        alt: "Atlas",
        className: "atlas-brand-logo",
        height: 200,
        onError: () => setFailureCount((count) => count + 1),
        src: asset,
        width: 900,
      })
      : React.createElement("span", { className: "atlas-brand-fallback" }, "Atlas"),
  );
}
