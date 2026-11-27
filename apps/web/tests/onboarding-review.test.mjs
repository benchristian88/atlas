import assert from "node:assert/strict";
import { test } from "node:test";
import { integrationNeedsConfiguration, reviewRecommendations } from "../lib/onboarding-review.mjs";

const empty = {
  discovery: { decisions: { eligible: 0, conflicts: 0, exceptions: 0 }, active_runs: 0 },
  link_services: { linked: 0, unlinked: 0, mappings: 0, unavailable: 0 },
  integrations: { items: [], has_more: false },
  required_gaps: 0,
};

test("advisory actions are ordered by visible, actionable current work", () => {
  const review = {
    ...empty,
    discovery: { decisions: { eligible: 2, conflicts: 1, exceptions: 3 }, active_runs: 1 },
    link_services: { unlinked: 2 },
    required_gaps: 5,
    integrations: { items: [{ status: "configured", discovery_status: "failed" }] },
  };
  const recommendations = reviewRecommendations(review);
  assert.deepEqual(recommendations.map(({ id, stage }) => [id, stage]), [
    ["proposals", "discovery_review"], ["conflicts", "discovery_review"], ["exceptions", "discovery_review"],
    ["mappings", "link_services"], ["gaps", undefined], ["integrations", "integrations"],
  ]);
  assert.ok(recommendations.every(({ label, actionLabel = label }) => actionLabel.startsWith("Review ")));
});

test("empty, active-only and restricted projections produce no speculative actions", () => {
  assert.deepEqual(reviewRecommendations(empty), []);
  assert.deepEqual(reviewRecommendations({
    ...empty,
    discovery: { decisions: null, active_runs: 1 },
    link_services: { linked: 0, unlinked: 0, mappings: 0, unavailable: 3 },
    integrations: null,
    required_gaps: null,
  }), []);
});

test("configuration guidance respects canonical readiness when available", () => {
  assert.equal(integrationNeedsConfiguration({ status: "unconfigured", discovery_configured: true }), false);
  assert.equal(integrationNeedsConfiguration({ status: "unconfigured", discovery_configured: null }), true);
  assert.equal(integrationNeedsConfiguration({ status: "configured", discovery_configured: false }), true);
  assert.equal(integrationNeedsConfiguration({ status: "disabled", discovery_configured: null }), false);
  assert.deepEqual(reviewRecommendations({
    ...empty,
    integrations: { items: [{ status: "configured", discovery_configured: false }] },
  }).map(row => row.stage), ["integrations"]);
});
