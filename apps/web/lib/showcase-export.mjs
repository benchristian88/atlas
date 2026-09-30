import { assetIconSources, GENERIC_ICON } from "./asset-icon.mjs";
import { showcaseFilename } from "./showcase.mjs";

export const SHOWCASE_LOGO = "/branding/lockups/atlas-impact-lockup-light.svg";
const asDataUrl = blob => new Promise((resolve, reject) => {
  const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(blob);
});
const decodeImage = src => new Promise((resolve, reject) => {
  const image = new Image(); image.onload = () => resolve(image); image.onerror = () => reject(new Error("An image could not be rendered.")); image.src = src;
});

// Resolve optional resources before declaring the preview export-ready. Each URL
// is fetched once per scene, with bounded concurrency; the export itself is offline.
export async function showcaseResources(layout, apiBase, signal) {
  const cache = new Map();
  const resourceSignal = AbortSignal.any([signal, AbortSignal.timeout(5000)]);
  const read = (url, credentials = "omit") => {
    if (!cache.has(url)) cache.set(url, (async () => {
      if (url.startsWith("data:")) return url;
      try {
        const response = await fetch(url, { credentials, signal: resourceSignal });
        if (!response.ok) return null;
        const blob = await response.blob();
        if (!/^image\/(png|jpeg|webp|gif|svg\+xml)$/.test(blob.type) || blob.size > 2 * 1024 * 1024) return null;
        // Cached icons are raster images. Brand SVG is a bundled trusted asset;
        // external SVG may reference resources, so it is not embedded here.
        if (blob.type === "image/svg+xml" && url !== SHOWCASE_LOGO) return null;
        const data = await asDataUrl(blob);
        const image = await decodeImage(data);
        if (blob.type === "image/svg+xml") return data;
        // Freeze even an animated Type fallback to the same decoded frame used
        // in the preview. Canvas sees only local data URLs, never remote images.
        const canvas = document.createElement("canvas");
        const scale = Math.min(1, 256 / Math.max(image.naturalWidth, image.naturalHeight));
        canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
        canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
        const context = canvas.getContext("2d");
        if (!context) return null;
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        return canvas.toDataURL("image/png");
      } catch { return null; }
    })());
    return cache.get(url);
  };
  const logoPromise = read(SHOWCASE_LOGO);
  const members = layout.items.flatMap(n => n.kind === "asset" ? n.members : n.preview).filter(n => n.asset);
  const icons = {};
  let cursor = 0;
  await Promise.all(Array.from({ length: Math.min(6, members.length) }, async () => {
    while (cursor < members.length && !signal.aborted) {
      const node = members[cursor++];
      const cached = assetIconSources({ cached_icon_url: node.asset.cached_icon_url }, null, apiBase)[0];
      for (const source of assetIconSources(node.asset, node.type, apiBase)) {
        if (source === GENERIC_ICON) break; // The scene uses managed category/type fallback artwork.
        const data = await read(source, source === cached ? "include" : "omit");
        if (data) { icons[node.key] = data; break; }
      }
    }
  }));
  const logo = await logoPromise;
  return { icons, logo };
}

export async function exportShowcasePng(svg, siteName) {
  await document.fonts.ready;
  const clone = svg.cloneNode(true);
  // Freeze the existing Atlas managed identity palette and SVG typography.
  // No other DOM, layout, theme rules, or external styles enter the export.
  const originals = [svg, ...svg.querySelectorAll("*")], copies = [clone, ...clone.querySelectorAll("*")];
  const properties = ["fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "opacity", "color", "font-family", "font-size", "font-weight", "letter-spacing", "text-anchor", "dominant-baseline"];
  originals.forEach((original, index) => {
    const computed = getComputedStyle(original);
    for (const property of properties) copies[index].style.setProperty(property, computed.getPropertyValue(property));
  });
  const { width: logicalWidth, height: logicalHeight } = svg.viewBox.baseVal;
  const width = logicalWidth * 2, height = logicalHeight * 2;
  clone.setAttribute("width", String(width)); clone.setAttribute("height", String(height));
  clone.style.width = `${width}px`; clone.style.height = `${height}px`;
  const images = [...clone.querySelectorAll("image")];
  if (images.some(image => !image.getAttribute("href")?.startsWith("data:image/"))) throw new Error("Showcase images are still loading. Try again in a moment.");
  const source = await asDataUrl(new Blob([new XMLSerializer().serializeToString(clone)], { type: "image/svg+xml;charset=utf-8" }));
  const image = await decodeImage(source);
  const canvas = document.createElement("canvas"); canvas.width = width; canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("PNG export is unavailable in this browser.");
  context.drawImage(image, 0, 0, width, height);
  const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/png"));
  if (!blob) throw new Error("The browser could not create the PNG.");
  const url = URL.createObjectURL(blob), link = document.createElement("a");
  link.href = url; link.download = showcaseFilename(siteName); link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return blob;
}
