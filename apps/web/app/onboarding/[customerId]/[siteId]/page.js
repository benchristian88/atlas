import { OnboardingSession } from "../../../../components/onboarding-wizard";

export default async function OnboardingSitePage({ params }) {
  const { customerId, siteId } = await params;
  return <OnboardingSession key={`${customerId}:${siteId}`} customerId={customerId} siteId={siteId} />;
}
