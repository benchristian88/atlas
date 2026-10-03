import { presentationIcon, presentationAccent, PRESENTATION_ACCENTS } from "./presentation.mjs";

export function defaultEntityAccent(id) {
  // Durable identity, never display name, order, tenant or operational status.
  let hash = 0;
  for (const letter of String(id || "")) hash = (hash * 31 + letter.charCodeAt(0)) >>> 0;
  return PRESENTATION_ACCENTS[hash % PRESENTATION_ACCENTS.length];
}
export function resolveEntityIdentity(type, record = {}, reference = {}) {
  record ||= {};
  reference ||= {};
  const source = type === "service" ? (Object.keys(reference).length ? reference : { icon_key: record.service_type_icon_key, accent_key: record.service_type_accent_key, id: record.service_type_id }) : type === "asset" ? (Object.keys(reference).length ? reference : record) : record;
  const fallback = { asset: "server", service: "application", business_function: "home", network: "network" }[type] || "infrastructure";
  return { icon_key: presentationIcon(source.icon_key, fallback).key, accent_key: source.accent_key ? presentationAccent(source.accent_key) : defaultEntityAccent(source.id || record.entity_id || record.id || record.key) };
}
