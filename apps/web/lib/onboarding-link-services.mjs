import { mutationOutcomeUnknown } from "./onboarding-integrations.mjs";

export const MAPPING_PAGE_SIZE = 25;
export const MAPPING_SELECTION_LIMIT = 25;

export function mappingPagePath(path, filters) {
  const params = new URLSearchParams({ limit: MAPPING_PAGE_SIZE });
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  return `${path}?${params}`;
}

export function requiresMappingAcknowledgement(summary) {
  return !summary || summary.unlinked > 0 || summary.unavailable > 0;
}

export function mappingAssetContext(asset) {
  return [asset.type_name, asset.hostname, `ID ${asset.id}`].filter(Boolean).join(" · ");
}

export function toggleMappingAsset(selection, asset) {
  if (selection.some(item => item.id === asset.id)) return selection.filter(item => item.id !== asset.id);
  if (selection.length >= MAPPING_SELECTION_LIMIT) return selection;
  const { id, name, type_name, hostname } = asset;
  return [...selection, { id, name, type_name, hostname }];
}

export function remainingMappingSelection(selection, outcome, mappings) {
  const settled = new Set([
    ...outcome.filter(item => ["added", "already_exists"].includes(item.status)).map(item => item.id),
    ...(mappings || []).map(item => item.asset.id),
  ]);
  return selection.filter(item => !settled.has(item.id));
}

export function readUnconfirmedMapping(key) {
  try {
    const marker = JSON.parse(sessionStorage.getItem(key));
    if (["add", "remove"].includes(marker?.kind) && typeof marker.id === "string") return marker;
  } catch {}
  return null;
}

export function storeUnconfirmedMapping(key, marker) {
  try {
    if (marker) sessionStorage.setItem(key, JSON.stringify(marker));
    else sessionStorage.removeItem(key);
  } catch {}
}

export async function submitMappingActions(path, confirmation, request, markUnconfirmed) {
  const adding = confirmation.kind === "add";
  const results = [];
  for (const asset of confirmation.assets) {
    const id = adding ? asset.id : confirmation.mappingId;
    const endpoint = adding ? `assets/${id}` : `mappings/${id}`;
    markUnconfirmed({ kind: confirmation.kind, id });
    try {
      const options = adding ? { method: "POST" } : {
        method: "DELETE", body: JSON.stringify({ removal_version: confirmation.removalVersion }),
      };
      const result = await request(`${path}/${endpoint}`, options);
      results.push({ ...asset, status: adding ? result.outcome : "removed" });
      markUnconfirmed(null);
    } catch (error) {
      if (mutationOutcomeUnknown(error)) {
        results.push({ ...asset, status: "unconfirmed" });
        break;
      }
      markUnconfirmed(null);
      const reason = !adding && error.status === 404
        ? "This mapping is no longer available. Check the refreshed mappings." : error.message;
      results.push({ ...asset, status: "rejected", reason });
      if ([401, 403].includes(error.status)) break;
    }
  }
  return { results, unsubmitted: confirmation.assets.length - results.length };
}
