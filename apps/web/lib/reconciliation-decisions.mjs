export function decisionRequest(item, action, { disposition, outcome, reason = null, target } = {}) {
  let body = { reason, expected_version: item.version };
  if (action === "identity-decision") {
    const review = item.identity_review;
    const expected_version = outcome === "replace" ? (review.replacement_expected_version ?? review.expected_version) : review.expected_version;
    body = { outcome, expected_version, reason };
  } else if (action === "link-asset") body.asset_id = target;
  else if (action === "link-technical") body.entity_id = target;
  else body.disposition = disposition ?? null;
  return [`/reconciliation-items/${item.id}/${action}`, { method: "POST", body: JSON.stringify(body) }];
}

export function technicalCandidatesPath(item, offset) {
  const params = new URLSearchParams({ limit: "100", offset: String(offset) });
  if (item.entity_type === "asset_interface") {
    params.set("asset_id", item.link_asset_id);
    return `/asset-interfaces?${params}`;
  }
  params.set("customer_id", item.customer_id);
  params.set("site_id", item.site_id);
  return `/networks?${params}`;
}
