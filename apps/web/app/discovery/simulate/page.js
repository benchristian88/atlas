"use client";

import { Button } from "../../../components/button";

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
  const [completeSnapshot, setCompleteSnapshot] = useState(true);
  const [coverageKey, setCoverageKey] = useState("homelab-assets");
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);
  const canManage = hasPermission("discovery.simulate");

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
    body.coverage_key = coverageKey.trim() || null;
    body.is_complete_snapshot = completeSnapshot;
    setRunning(true);
    try {
      setResult(await apiRequest("/discovery/simulate", { method: "POST", body: JSON.stringify(body) }));
    } catch (requestError) {
      setError(requestError.message || "Atlas could not run the simulation.");
    } finally { setRunning(false); }
  }

  return <>
    <PageHeader eyebrow="Discovery" title="Simulate discovery" description="Create evidence and reviewable assertions without changing operational assets." actions={<><Link className="button button-secondary" href="/discovery-runs">View runs</Link></>} />
    {error && <div className="error-banner" role="alert">{error}</div>}
    <section className="form-card"><form onSubmit={submit}><div className="form-grid"><label className="field"><span>Coverage key</span><input onChange={(event) => setCoverageKey(event.target.value)} placeholder="homelab-assets" value={coverageKey} /></label><label className="field checkbox-field"><input checked={completeSnapshot} onChange={(event) => setCompleteSnapshot(event.target.checked)} type="checkbox" /><span>Complete snapshot</span></label></div>{completeSnapshot && <div className="warning-banner">Atlas will compare this run with the previous successful complete snapshot using the same source, context, and coverage key. Omitted assets become review items; they are never deleted automatically.</div>}<label className="field"><span>Observation payload</span><textarea className="knowledge-json-input mono" onChange={(event) => setPayload(event.target.value)} rows={24} value={payload} /></label><div className="form-actions"><Button variant="primary" disabled={running || !workspace.customerId || !workspace.siteId} type="submit">{running ? "Running…" : "Run simulation"}</Button></div></form></section>
    <section className="detail-card"><p className="eyebrow">Safe sample workflow</p><p>Run 1 with <strong>pve1</strong> and <strong>docker01</strong>, then Run 2 with <strong>pve1 only</strong>, using the same complete-snapshot coverage key. Expected: docker01 is proposed as no longer observed and remains in Atlas pending review.</p></section>
    {result && <section className="detail-card"><div className="form-card-header"><h2>Run completed</h2><Link className="card-link" href="/reconciliation">Review reconciliation →</Link></div><div className="detail-grid"><div><span>Observed</span><strong>{result.observed_count}</strong></div><div><span>New</span><strong>{result.new_count}</strong></div><div><span>Changed</span><strong>{result.changed_count}</strong></div><div><span>No longer observed</span><strong>{result.no_longer_observed_count}</strong></div><div><span>Reobserved</span><strong>{result.reobserved_count}</strong></div><div><span>Baseline run</span><strong className="mono">{result.baseline_run_id || "First baseline"}</strong></div><div><span>Evidence records</span><strong>{result.evidence_records_created}</strong></div><div><span>Assertions</span><strong>{result.assertions_created}</strong></div><div><span>Run</span><strong className="mono">{result.run.id}</strong></div></div></section>}
  </>;
}
