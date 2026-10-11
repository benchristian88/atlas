"use client";
import { use, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "../../../../components/auth-context";
import { AccessDenied } from "../../../../components/access-denied";
import { PageHeader } from "../../../../components/page-header";
import { Button } from "../../../../components/button";
import { DataTable } from "../../../../components/data-table";
import { apiRequest } from "../../../../lib/api";

export default function ConnectorMappings({ params }) {
  const { connector } = use(params), query = useSearchParams(), auth = useAuth();
  const allowed = auth.hasGlobalPermission("integration_runtime.manage");
  const [state, setState] = useState(null), [types, setTypes] = useState({ asset: [], relationship: [] }), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  async function load() { const [mapped, asset, relationship] = await Promise.all([apiRequest(`/connector-mappings/${encodeURIComponent(connector)}${query.get("version") ? `?version=${encodeURIComponent(query.get("version"))}` : ""}`, { omitContext: true }), apiRequest("/asset-types", { omitContext: true }), apiRequest("/relationship-types", { omitContext: true })]); setState(mapped); setTypes({ asset, relationship }); }
  useEffect(() => { if (allowed) load().catch(reason => setError(reason.message)); }, [allowed, connector]);
  async function change(row, target_key, ignored = false) { setBusy(true); setError(""); try { setState(await apiRequest(`/connector-mappings/${encodeURIComponent(connector)}`, { method: "PUT", omitContext: true, body: JSON.stringify({ version: state.version, kind: row.kind, source_key: row.source_key, target_key: target_key || null, ignored }) })); } catch (reason) { setError(reason.message); } finally { setBusy(false); } }
  if (!allowed) return <AccessDenied />;
  return <div><PageHeader title="Connector mappings" description={`${connector}${state ? ` · ${state.version}` : ""} · instance-global mappings shared by every connection.`} actions={<Button href="/integrations?tab=catalogue">Connector catalogue</Button>} />
    {error && <div className="error-banner" role="alert">{error}</div>}
    <p>Required classes must map to active reference data before activation. Only exact stable-key recommendations map automatically.</p>
    <DataTable label="Global Connector mappings" loading={!state && !error} rows={(state?.mappings || []).map(row => ({ ...row, id: `${row.kind}:${row.source_key}` }))} columns={[
      { key: "label", label: "Source class" }, { key: "kind", label: "Kind" }, { key: "required", label: "Requirement", render: row => row.required ? "Required" : "Optional" },
      { key: "resolved", label: "State", render: row => row.ignored ? "Ignored" : row.resolved ? "Resolved" : "Unresolved" },
      { key: "target_key", label: "Atlas type", render: row => <label className="field"><select aria-label={`Map ${row.label}`} disabled={busy} value={row.target_key || ""} onChange={event => change(row, event.target.value)}><option value="">Select active type</option>{types[row.kind].filter(type => type.active).map(type => <option key={type.key} value={type.key}>{type.name} · {type.key}</option>)}</select></label> },
      { key: "ignore", label: "Action", render: row => !row.required && <Button disabled={busy || row.ignored} onClick={() => change(row, null, true)}>Ignore optional class</Button> },
    ]} />
    {state?.mappings.length === 0 && <p>This Connector version declares no discovery taxonomy mappings.</p>}
    <div className="form-actions"><Button href="/admin/asset-types">Manage Asset Types</Button><Button href="/admin/relationship-types">Manage Relationship Types</Button></div>
  </div>;
}
