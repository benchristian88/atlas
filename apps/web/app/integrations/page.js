"use client";
import { AccessDenied } from "../../components/access-denied";
import { useAuth } from "../../components/auth-context";
import { PageHeader } from "../../components/page-header";
import { EmptyState } from "../../components/section";

export default function IntegrationsPage() {
  const { hasPermission } = useAuth();
  if (!hasPermission("integrations.view")) return <AccessDenied />;
  return <><PageHeader eyebrow="Connections" title="Integrations" description="Discovery source management." /><EmptyState title="Integration management is unavailable" description="Manage accepted knowledge through Assets, Services and Business Functions." /></>;
}
