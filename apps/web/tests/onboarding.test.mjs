import assert from "node:assert/strict";
import test from "node:test";
import { dashboardOnboardingEntry, initialEnvironment, onboardingPath, PROFILES, STAGES } from "../lib/onboarding.mjs";

test("preview exposes the agreed stages and two environment profiles", () => {
  assert.deepEqual(STAGES.map(([, title]) => title), [
    "Environment", "Capabilities", "Add integrations", "Discovery review", "Link Services", "Review & Ready", "Showcase",
  ]);
  assert.deepEqual(PROFILES, { homelab: "Homelab", blank: "Blank" });
});

test("only a unique authorized Customer/Site pair is suggested in the chooser", () => {
  const customers = [{ id: "customer" }];
  const sites = [{ id: "site", customer_id: "customer" }];
  assert.deepEqual(initialEnvironment({ customers, sites }), { customerId: "customer", siteId: "site" });
  assert.deepEqual(initialEnvironment({ customers, sites: [] }), { customerId: "customer", siteId: "" });
  assert.deepEqual(initialEnvironment({ customers, sites: [...sites, { id: "other", customer_id: "customer" }] }),
    { customerId: "customer", siteId: "" });
  assert.deepEqual(initialEnvironment({ customers: [...customers, { id: "other" }], sites }),
    { customerId: "", siteId: "" });
});

test("dismissal preserves voluntary entry and shared progress controls Continue", () => {
  assert.equal(dashboardOnboardingEntry({ status: "not_started", invitation: { offered: true, dismissed: false } }), "invitation");
  assert.equal(dashboardOnboardingEntry({ status: "not_started", invitation: { offered: false, dismissed: true } }), "voluntary");
  assert.equal(dashboardOnboardingEntry({ status: "saved", can_manage: true, invitation: { offered: false, dismissed: true } }), "continue");
  assert.equal(dashboardOnboardingEntry({ status: "saved", can_manage: false, invitation: { offered: false, dismissed: true } }), "voluntary");
  assert.equal(dashboardOnboardingEntry({ status: "completed", invitation: { offered: false, dismissed: false } }), "voluntary");
});

test("wizard addresses the selected pair explicitly", () => {
  assert.equal(onboardingPath("customer", "site"), "/onboarding/customer/site");
  assert.equal(onboardingPath("different/site", "other?site"), "/onboarding/different%2Fsite/other%3Fsite");
});
