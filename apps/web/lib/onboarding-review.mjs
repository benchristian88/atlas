export function integrationNeedsConfiguration(integration) {
  return integration.discovery_configured === false
    || (integration.status === "unconfigured" && integration.discovery_configured !== true);
}

export function reviewRecommendations(review) {
  const decisions = review.discovery.decisions;
  return [
    decisions?.eligible > 0 && { id: "proposals", stage: "discovery_review", label: "Review eligible discovery proposals" },
    decisions?.conflicts > 0 && { id: "conflicts", stage: "discovery_review", label: "Review discovery conflicts individually" },
    decisions?.exceptions > 0 && { id: "exceptions", stage: "discovery_review", label: "Inspect blocked or exceptional discovery decisions",
      actionLabel: "Review blocked or exceptional discovery decisions" },
    review.link_services?.unlinked > 0 && { id: "mappings", stage: "link_services", label: "Link remaining unmapped Services",
      actionLabel: "Review remaining unmapped Services" },
    review.required_gaps > 0 && { id: "gaps", label: "Address required Knowledge Gaps",
      actionLabel: "Review outstanding Knowledge Gaps" },
    review.integrations?.items.some(row => integrationNeedsConfiguration(row) || ["failed", "cancelled"].includes(row.discovery_status))
      && { id: "integrations", stage: "integrations", label: "Review Integration issues" },
  ].filter(Boolean);
}
