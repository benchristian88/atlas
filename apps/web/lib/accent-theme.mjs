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

function accessibleAccent(accent, backgrounds, minimum) {
  const target = readableForeground(backgrounds[0]);
  for (let step = 0; step <= 100; step++) {
    const candidate = mixColours(accent, target, step / 100);
    if (backgrounds.every((background) => contrastRatio(candidate, background) >= minimum)) return candidate;
  }
  return target;
}

export function deriveAccentTheme(value, mode = "light") {
  const accent = normalizeAccentColour(value) || ATLAS_DEFAULT_ACCENT;
  const dark = mode === "dark";
  const backgrounds = dark ? ["#131D23", "#1B272E", "#233139", "#102A2E"] : ["#F5F7F9", "#FFFFFF", "#F8FAFB"];
  const foreground = readableForeground(accent);
  const soft = mixColours(accent, backgrounds[1], dark ? 0.82 : 0.92);
  return {
    accent,
    accentHover: mixColours(accent, foreground === "#FFFFFF" ? "#000000" : "#FFFFFF", 0.16),
    accentText: accessibleAccent(accent, backgrounds, 4.5),
    accentSoft: soft,
    accentSoftForeground: accessibleAccent(accent, [soft], 4.5),
    accentBorder: mixColours(accent, backgrounds[1], 0.55),
    focusRing: accessibleAccent(accent, backgrounds, 3),
    foreground,
  };
}

export function accentThemeStyle(value, mode = "light") {
  const theme = deriveAccentTheme(value, mode);
  return {
    "--accent": theme.accent,
    "--accent-hover": theme.accentHover,
    "--accent-text": theme.accentText,
    "--accent-soft": theme.accentSoft,
    "--accent-soft-foreground": theme.accentSoftForeground,
    "--accent-border": theme.accentBorder,
    "--accent-foreground": theme.foreground,
    "--focus-ring": theme.focusRing,
    "--brand-mark": theme.accentText,
    "--brand-mark-foreground": theme.foreground,
  };
}
