import registry from "./presentation-registry.json" with { type: "json" };

export const PRESENTATION_ICONS = registry.icons;
export const PRESENTATION_ACCENTS = registry.accents;
const icons = new Map(PRESENTATION_ICONS.map(icon => [icon.key, icon]));
export function presentationIcon(key, fallback = "infrastructure") {
  return icons.get(key) || icons.get(fallback) || icons.get("infrastructure");
}
export function presentationAccent(key) {
  return PRESENTATION_ACCENTS.includes(key) ? key : "slate";
}
export function presentationAttributes(record) {
  return { "data-presentation-accent": presentationAccent(record?.accent_key) };
}
