"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { useWorkspaceContext } from "../../components/workspace-context";
import { visibleSystemSections } from "../../lib/system-navigation.mjs";

export default function SystemLandingRedirect() {
  const router = useRouter();
  const auth = useAuth();
  const { customerId, siteId } = useWorkspaceContext();
  const destination = visibleSystemSections({ ...auth, customerId, siteId })[0]?.href;
  useEffect(() => { if (destination) router.replace(destination); }, [destination, router]);
  return destination ? <p role="status">Opening System…</p> : <AccessDenied />;
}
