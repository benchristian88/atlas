"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../../components/auth-context";
import { useWorkspaceContext } from "../../../components/workspace-context";
import { AccessDenied } from "../../../components/access-denied";
import { Button } from "../../../components/button";
import { PageHeader } from "../../../components/page-header";
import { EmptyState } from "../../../components/section";
import { IntegrationCreateForm } from "../../../components/integration-create-form";
import { apiRequest } from "../../../lib/api";

export default function AddIntegration() {
  const auth = useAuth(), workspace = useWorkspaceContext(), router = useRouter();
  const [forms, setForms] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    apiRequest("/integration-forms", { omitContext: true, signal: controller.signal }).then(setForms)
      .catch(reason => { if (!controller.signal.aborted) setError(reason.message); });
    return () => controller.abort();
  }, []);
  const canManageIn = (customer, site) => auth.hasPermissionInContext("integrations.manage", customer, site);
  const sites = workspace.sites.filter(item => canManageIn(item.customer_id, item.id));
  const customers = workspace.customers.filter(item => sites.some(candidate => candidate.customer_id === item.id));

  async function create(body) {
    const saved = await apiRequest("/integrations", { method: "POST", body: JSON.stringify(body), omitContext: true });
    router.push(`/integrations/${saved.id}`);
  }

  if (workspace.status === "ready" && !sites.length) return <AccessDenied />;
  return <div><PageHeader title="Add integration" description="Configure a scoped connection using a verified installed Connector." actions={<Button href="/integrations">Cancel</Button>} />
    {error && <div className="error-banner" role="alert">{error}</div>}
    {!forms ? <p role="status">Loading installed Connectors…</p> : !forms.length ? <EmptyState title="No configurable Connectors" description="A global administrator must install and activate a verified Connector and resolve any required mappings." action={<Button href="/integrations?tab=catalogue">Browse catalogue</Button>} /> :
      <IntegrationCreateForm forms={forms} customers={customers} sites={sites} initialCustomer={workspace.customerId}
        initialSite={workspace.siteId} canManageIn={(customer, site) => canManageIn(customer || workspace.customerId, site || workspace.siteId)}
        canRunIn={(customer, site) => auth.hasPermissionInContext("integrations.run", customer, site)} onCreate={create} />}
  </div>;
}
