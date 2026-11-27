export const STAGES = [
  ["environment", "Environment"],
  ["capabilities", "Capabilities"],
  ["integrations", "Add integrations"],
  ["discovery_review", "Discovery review"],
  ["link_services", "Link Services"],
  ["review_ready", "Review & Ready"],
  ["showcase", "Showcase"],
];

export const PROFILES = { homelab: "Homelab", blank: "Blank" };

export function onboardingPath(customerId, siteId) {
  return `/onboarding/${encodeURIComponent(customerId)}/${encodeURIComponent(siteId)}`;
}

export function initialEnvironment({ customers, sites }) {
  if (sites.length === 1 && customers.length === 1 && sites[0].customer_id === customers[0].id) {
    return { customerId: customers[0].id, siteId: sites[0].id };
  }
  return { customerId: customers.length === 1 ? customers[0].id : "", siteId: "" };
}

export function canContinueSetup(status) {
  return status === "saved" || status === "in_progress";
}

export function dashboardOnboardingEntry(status) {
  if (status?.status === "completed") return "completed";
  if (status?.invitation?.offered && !status.invitation.dismissed) return "invitation";
  if (status?.can_manage && canContinueSetup(status.status)) return "continue";
  return "voluntary";
}
