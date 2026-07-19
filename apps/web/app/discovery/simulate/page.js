"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AccessDenied } from "../../../components/access-denied";
import { useAuth } from "../../../components/auth-context";
import { PageHeader } from "../../../components/page-header";
import { useWorkspaceContext } from "../../../components/workspace-context";
import { apiRequest } from "../../../lib/api";

function examplePayload(customerId, siteId) {
  return JSON.stringify({
    customer_id: customerId || "select-a-customer",
    site_id: siteId || "select-a-site",
    observations: [{
      external_id: "manual:docker01",
      entity_kind: "asset",
      asset_type: "virtual_machine",
      name: "docker01",
      facts: { hostname: "docker01", status: "running" },
      interfaces: [{ name: "eth0", ip_address: "192.168.5.8", network_name: "Apps VLAN", is_primary: true }],
      relationships: [{ relationship_type: "runs_on", target_external_id: "manual:pve1" }],
    }],
  }, null, 2);
}

export default function SimulateDiscoveryPage() {
  const { hasPermission } = useAuth();
  const workspace = useWorkspaceContext();
  const [payload, setPayload] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);
  const canManage = hasPermission("integrations.manage");

  useEffect(() => {
    setPayload(examplePayload(workspace.customerId, workspace.siteId));
  }, [workspace.reloadKey, workspace.customerId, workspace.siteId]);

  if (!canManage) return <AccessDenied />;

  async function submit(event) {
    event.preventDefault();
    setError("");
    setResult(null);
    let body;
    try { body = JSON.parse(payload); }
    catch { setError("The simulation payload is not valid JSON."); return; }
    setRunning(true);
    try {
      setResult(await apiRequest("/discovery/simulate", { method: "POST", body: JSON.stringify(body) }));
    } catch (requestError) {
      setError(requestError.message || "Atlas could not run the simulation.");
    } finally { setRunning(false); }
  }

  return <>
    <div className="page-heading-row"><PageHeader eyebrow="Discovery" title="Simulate discovery" description="Create evidence and reviewable assertions without changing operational assets." /><Link className="button button-secondary" href="/discovery-runs">View runs</Link></div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <section className="form-card"><form onSubmit={submit}><label className="field"><span>Observation payload</span><textarea className="knowledge-json-input mono" onChange={(event) => setPayload(event.target.value)} rows={24} value={payload} /></label><div className="form-actions"><button className="button button-primary" disabled={running || !workspace.customerId || !workspace.siteId} type="submit">{running ? "Running…" : "Run simulation"}</button></div></form></section>
    {result && <section className="detail-card"><div className="form-card-header"><h2>Run completed</h2><Link className="card-link" href="/reconciliation">Review reconciliation →</Link></div><div className="detail-grid"><div><span>Evidence records</span><strong>{result.evidence_records_created}</strong></div><div><span>Assertions</span><strong>{result.assertions_created}</strong></div><div><span>Reconciliation items</span><strong>{result.reconciliation_items_created}</strong></div><div><span>Run</span><strong className="mono">{result.run.id}</strong></div></div></section>}
  </>;
}
