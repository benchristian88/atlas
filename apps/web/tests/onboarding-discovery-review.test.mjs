import test from "node:test";
import assert from "node:assert/strict";
import {
  discoveryReviewPath, emptyReviewFilters, readUncertainReview, requiresReviewAcknowledgement,
  reviewedBatch, sameReviewedProposal,
} from "../lib/onboarding-discovery-review.mjs";
import { decisionRequest } from "../lib/reconciliation-decisions.mjs";

test("review filters and recovery status IDs retain a bounded request", () => {
  const url = new URL(discoveryReviewPath({ search: "a & b", source: "integration-a",
    category: "inferred_relationship", offset: 40 }, ["first", "second"]), "https://atlas.test");
  assert.equal(url.searchParams.get("limit"), "40");
  assert.equal(url.searchParams.get("offset"), "40");
  assert.equal(url.searchParams.get("search"), "a & b");
  assert.equal(url.searchParams.get("source_id"), "integration-a");
  assert.equal(url.searchParams.get("category"), "inferred_relationship");
  assert.deepEqual(url.searchParams.getAll("decision_id"), ["first", "second"]);
  const bounded = new URL(discoveryReviewPath(emptyReviewFilters, Array.from({ length: 110 }, (_, id) => id)), "https://atlas.test");
  assert.equal(bounded.searchParams.getAll("decision_id").length, 100);
});

test("a confirmed batch is an independent snapshot of eligible and available identities on the page", () => {
  const page = { items: [
    { id: "asset", batch_version: "reviewed-asset", category: "newly_discovered", entity_name: "Reviewed candidate",
      batch_identity: { action: "associate", asset_name: "Original target" } },
    { id: "waiting" },
    { id: "uncertain", batch_version: "reviewed-uncertain", category: "changed" },
  ], eligible: 8, needs_review: 3, sources: { integration: "Network integration" } };
  const batch = reviewedBatch(page, { ...emptyReviewFilters, source: "integration" }, "Test Site", { uncertain: true });
  page.items[1].batch_version = "newly-eligible";
  page.items.push({ id: "arrived", batch_version: "new" });
  page.items[0].batch_version = "changed";
  page.items[0].batch_identity.asset_name = "Later target";
  assert.deepEqual(batch.items, [{ id: "asset", version: "reviewed-asset" }]);
  assert.deepEqual(batch.associations, [{ id: "asset", proposal: "Reviewed candidate", target: "Original target" }]);
  assert.deepEqual(batch.categories, { newly_discovered: 1 });
  assert.equal(batch.excluded, 3);
  assert.equal(batch.outside, 7);
  assert.equal(batch.source, "Network integration");
});

test("reviewed details require reopening after a material eligibility or identity change", () => {
  const item = { version: "item", batch_version: "yes", can_accept: true, identity_review: {
    expected_version: "current", replacement_expected_version: "replacement", actions: { replace: null },
  }};
  assert.equal(sameReviewedProposal(item, { ...item, source_name: "Friendly name" }), true);
  assert.equal(sameReviewedProposal(item, { ...item, batch_exclusion: "Prerequisite changed" }), false);
  assert.equal(sameReviewedProposal(item, { ...item, version: "next" }), false);
  assert.equal(sameReviewedProposal(item, { ...item, identity_review: { ...item.identity_review,
    replacement_expected_version: "changed" } }), false);
  const [path, request] = decisionRequest({ ...item, id: "identity" }, "identity-decision", { outcome: "replace", reason: "Verified" });
  assert.equal(path, "/reconciliation-items/identity/identity-decision");
  assert.deepEqual(JSON.parse(request.body), { expected_version: "replacement", outcome: "replace", reason: "Verified" });
});

test("continuation acknowledges outstanding, active and unavailable state independently", () => {
  const empty = { eligible: 0, needs_review: 0, active_runs: 0 };
  assert.equal(requiresReviewAcknowledgement(empty), false);
  for (const key of Object.keys(empty)) {
    assert.equal(requiresReviewAcknowledgement({ ...empty, [key]: 1 }), true);
    assert.equal(requiresReviewAcknowledgement({ ...empty, [key]: null }), true);
  }
  assert.deepEqual(readUncertainReview("without-session-storage"), {});
});
