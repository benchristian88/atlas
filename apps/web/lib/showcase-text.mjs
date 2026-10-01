// Showcase uses the same Arial/600 canvas measurement for sizing and labels.
// Server tests use the same font's glyph metrics; Unicode falls back conservatively.
import { SHOWCASE_FONT_METRICS } from "./showcase-font-metrics.mjs";
export const SHOWCASE_NAME_FONT_SIZE = 15;
export const SHOWCASE_NAME_LINE_HEIGHT = 18;
export const SHOWCASE_NAME_MAX_LINES = 2;
export const SHOWCASE_MAX_NODE_WIDTH = 240;
export const SHOWCASE_MAX_MEMBER_WIDTH = 220;
let context;
const advances = new Map(Array.from(SHOWCASE_FONT_METRICS.chars, (char, index) => [char, SHOWCASE_FONT_METRICS.widths[index]]));
export function measureShowcaseName(value) {
  if (typeof document !== "undefined") {
    context ||= document.createElement("canvas").getContext("2d");
    if (context) {
      context.font = `600 ${SHOWCASE_NAME_FONT_SIZE}px Arial`;
      return context.measureText(value).width;
    }
  }
  const chars = Array.from(value);
  return chars.reduce((width, char, index) => width + (advances.get(char) ?? 2048) +
    (index ? SHOWCASE_FONT_METRICS.pairs[chars[index - 1] + char] || 0 : 0), 0) * SHOWCASE_NAME_FONT_SIZE / 2048;
}

export function showcaseNameLayout(value, member = false, measure = measureShowcaseName) {
  const name = String(value || "").trim().replace(/\s+/g, " ");
  const padding = member ? 28 : 44, minimum = member ? 112 : 124;
  const maximum = member ? SHOWCASE_MAX_MEMBER_WIDTH : SHOWCASE_MAX_NODE_WIDTH;
  const width = Math.min(maximum, Math.max(minimum, Math.ceil((measure(name) + padding + 2) / 4) * 4));
  const budget = width - padding - 2;
  if (measure(name) <= budget) return { width, height: member ? 22 : 32, lines: [name], truncated: false };
  // Prefer a word boundary, splitting an exceptionally long token only when
  // necessary. Keep all remaining text for the second line before ellipsising.
  const chars = Array.from(name);
  let count = 0;
  while (count < chars.length && measure(chars.slice(0, count + 1).join("")) <= budget) count++;
  const prefix = chars.slice(0, count).join("");
  const breakAt = prefix.lastIndexOf(" ");
  const first = breakAt > 0 ? prefix.slice(0, breakAt) : prefix;
  let last = chars.slice(Array.from(first).length).join("").trimStart();
  const truncated = measure(last) > budget;
  if (truncated) {
    const tail = Array.from(last);
    while (tail.length && measure(`${tail.join("")}…`) > budget) tail.pop();
    last = `${tail.join("").trimEnd()}…`;
  }
  const lines = [first, last];
  const wrappedWidth = Math.min(maximum, Math.max(minimum, Math.ceil((Math.max(...lines.map(measure)) + padding + 2) / 4) * 4));
  return { width: wrappedWidth, height: member ? 40 : 46, lines, truncated };
}
