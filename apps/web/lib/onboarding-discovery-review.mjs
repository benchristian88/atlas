export const DISCOVERY_REVIEW = "/reconciliation-entities/discovery-review";
export const REVIEW_PAGE_SIZE = 40;
export const emptyReviewFilters = { search: "", source: "", category: "", offset: 0 };

export function discoveryReviewPath(filters, recoveryIds = []) {
  const params = new URLSearchParams({ limit: REVIEW_PAGE_SIZE, offset: filters.offset });
  if (filters.search) params.set("search", filters.search);
  if (filters.source) params.set("source_id", filters.source);
  if (filters.category) params.set("category", filters.category);
  recoveryIds.slice(0, 100).forEach(id => params.append("decision_id", id));
  return `${DISCOVERY_REVIEW}?${params}`;
}

export function reviewedBatch(page, filters, siteName, uncertain) {
  const selected = page.items.filter(item => item.batch_version && !uncertain[item.id]);
  const categories = {};
  for (const item of selected) categories[item.category] = (categories[item.category] || 0) + 1;
  return {
    items: selected.map(item => ({ id: item.id, version: item.batch_version })),
    associations: selected.filter(item => item.batch_identity?.action === "associate")
      .map(item => ({ id: item.id, proposal: item.entity_name, target: item.batch_identity.asset_name })),
    categories, siteName,
    source: filters.source ? page.sources[filters.source] : "All visible sources",
    search: filters.search,
    category: filters.category,
    page: 1 + Math.floor(filters.offset / REVIEW_PAGE_SIZE),
    excluded: page.needs_review,
    outside: page.eligible - selected.length,
  };
}

export function requiresReviewAcknowledgement(summary) {
  return [summary.eligible, summary.needs_review, summary.active_runs].some(value => value !== 0);
}

export function sameReviewedProposal(left, right) {
  return left.version === right.version && left.batch_version === right.batch_version
    && left.batch_exclusion === right.batch_exclusion
    && left.can_accept === right.can_accept && left.can_link_technical === right.can_link_technical
    && left.identity_review?.expected_version === right.identity_review?.expected_version
    && left.identity_review?.replacement_expected_version === right.identity_review?.replacement_expected_version
    && JSON.stringify(left.identity_review?.actions) === JSON.stringify(right.identity_review?.actions);
}

export function readUncertainReview(key) {
  try { return JSON.parse(sessionStorage.getItem(key)) || {}; }
  catch { return {}; }
}
