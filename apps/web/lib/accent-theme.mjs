export const ATLAS_DEFAULT_ACCENT = "#1A7F72";
export const ACCENT_PATTERN = /^#[0-9A-Fa-f]{6}$/;

export function normalizeAccentColour(value) {
  if (value === null || value === undefined || value === "") return null;
  const normalized = String(value).trim();
  if (!ACCENT_PATTERN.test(normalized)) {
    throw new Error("Use a six-digit hexadecimal colour such as #2563EB.");
  }
  return normalized.toUpperCase();
}

function rgb(hex) {
  const normalized = normalizeAccentColour(hex);
  return [1, 3, 5].map((offset) => Number.parseInt(normalized.slice(offset, offset + 2), 16));
}

function hex([red, green, blue]) {
  return `#${[red, green, blue].map((value) => Math.round(value).toString(16).padStart(2, "0")).join("")}`.toUpperCase();
}

export function mixColours(colour, target, targetWeight) {
  if (targetWeight < 0 || targetWeight > 1) throw new Error("Colour mix weight must be between 0 and 1.");
  const sourceRgb = rgb(colour);
  const targetRgb = rgb(target);
  return hex(sourceRgb.map((value, index) => value * (1 - targetWeight) + targetRgb[index] * targetWeight));
}

function relativeLuminance(colour) {
  const channels = rgb(colour).map((value) => {
    const channel = value / 255;
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

export function contrastRatio(first, second) {
  const lighter = Math.max(relativeLuminance(first), relativeLuminance(second));
  const darker = Math.min(relativeLuminance(first), relativeLuminance(second));
  return (lighter + 0.05) / (darker + 0.05);
}

export function readableForeground(background) {
  // Black and white guarantee that at least one candidate reaches WCAG AA for
  // every opaque sRGB background colour.
  const candidates = ["#FFFFFF", "#000000"];
  return candidates.sort((first, second) => contrastRatio(background, second) - contrastRatio(background, first))[0];
}

function accessibleMutedForeground(background, foreground) {
  let accessible = foreground;
  for (const backgroundWeight of [0.12, 0.18, 0.24, 0.3, 0.36]) {
    const candidate = mixColours(foreground, background, backgroundWeight);
    if (contrastRatio(background, candidate) < 4.5) break;
    accessible = candidate;
  }
  return accessible;
}

export function deriveAccentTheme(value) {
  const accent = normalizeAccentColour(value);
  if (!accent) return null;
  const foreground = readableForeground(accent);
  const sidebar = mixColours(accent, "#000000", 0.48);
  const soft = mixColours(accent, "#FFFFFF", 0.84);
  return {
    accent,
    accentHover: mixColours(accent, "#000000", foreground === "#FFFFFF" ? 0.16 : 0.12),
    accentSoft: soft,
    accentSoftForeground: readableForeground(soft),
    accentBorder: mixColours(accent, "#FFFFFF", 0.66),
    focusRing: contrastRatio(accent, "#FFFFFF") >= 3
      ? accent
      : mixColours(accent, "#000000", 0.42),
    foreground,
    sidebar,
    sidebarForeground: readableForeground(sidebar),
    sidebarMuted: accessibleMutedForeground(sidebar, readableForeground(sidebar)),
  };
}

export function accentThemeStyle(value) {
  const theme = deriveAccentTheme(value);
  if (!theme) return undefined;
  return {
    "--accent": theme.accent,
    "--accent-hover": theme.accentHover,
    "--accent-soft": theme.accentSoft,
    "--accent-soft-foreground": theme.accentSoftForeground,
    "--accent-border": theme.accentBorder,
    "--accent-foreground": theme.foreground,
    "--focus-ring": theme.focusRing,
    "--sidebar": theme.sidebar,
    "--sidebar-foreground": theme.sidebarForeground,
    "--sidebar-muted": theme.sidebarMuted,
    "--brand-mark": theme.accent,
    "--brand-mark-foreground": theme.foreground,
  };
}
