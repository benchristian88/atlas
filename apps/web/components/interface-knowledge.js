import { StatusBadge } from "./status-badge";

export function InterfaceKnowledge({ item }) {
  const network = item.assigned_network;
  const facts = item.observed_facts || [];
  return <>
    <span>{network ? `Assigned Network: ${network.name}${network.vlan_id !== null ? ` · Canonical VLAN ${network.vlan_id}` : ""}` : "No Network assigned"}</span>
    {facts.map(fact => <div className="knowledge-value-sources" key={`${fact.predicate}:${fact.is_accepted}`}>
      <strong>{fact.predicate === "proxmox.vlan_tag" ? "Observed VLAN" : "Observed bridge"}: {fact.value}</strong>{" "}
      <StatusBadge status={fact.is_accepted ? "Accepted" : "Not accepted"} />
      <div>{fact.source_name || "Source unavailable"} · <time dateTime={fact.last_observed_at}>Last observed {new Date(fact.last_observed_at).toLocaleString()}</time>
        {fact.is_accepted && fact.accepted_at && <> · Accepted {new Date(fact.accepted_at).toLocaleString()}</>}
      </div>
    </div>)}
    {facts.length > 0 && <small className="secondary-text">Observations do not assign a Network or confirm the current configuration.</small>}
  </>;
}
