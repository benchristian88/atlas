import { StatusBadge } from "./status-badge";

const BRIDGE = "proxmox.bridge_name";
const VLAN = "proxmox.vlan_tag";

function latestFact(facts, predicate) {
  return facts.filter((fact) => fact.predicate === predicate).reduce((latest, fact) => (
    !latest || Date.parse(fact.last_observed_at) > Date.parse(latest.last_observed_at)
      ? fact : latest
  ), null);
}

export function InterfaceAttachment({ item, className }) {
  const network = item.assigned_network;
  const facts = item.observed_facts ?? [];
  const bridge = latestFact(facts, BRIDGE);
  const vlan = latestFact(facts, VLAN);
  return <dl className={className}>
    <div>
      <dt>Assigned Atlas Network</dt>
      <dd>{network ? <>{network.name}{network.vlan_id != null && ` · VLAN ${network.vlan_id}`}</> : "Not assigned"}</dd>
    </div>
    <div>
      <dt>{bridge || vlan ? "Observed Proxmox attachment" : "Observed attachment"}</dt>
      <dd>{bridge || vlan ? <>
        {bridge && <code>{bridge.value}</code>}
        {bridge && vlan && " · "}
        {vlan && <>VLAN tag {vlan.value}</>}
      </> : "Not recorded"}</dd>
    </div>
  </dl>;
}

export function InterfaceDiscoveryDetails({ facts = [] }) {
  if (!facts.length) return null;
  return <details className="entity-disclosure">
    <summary>Discovery details</summary>
    <ul className="knowledge-value-sources">
      {facts.map((fact) => <li key={`${fact.predicate}:${fact.is_accepted}`}>
        <div>
          <strong>{fact.predicate === VLAN ? "Observed VLAN tag" : "Observed bridge"} <code>{fact.value}</code></strong>{" "}
          <StatusBadge status={fact.is_accepted ? "Accepted" : "Not accepted"} />
        </div>
        <div>
          {fact.source_name || "Source unavailable"} · <time dateTime={fact.last_observed_at}>Last observed {new Date(fact.last_observed_at).toLocaleString()}</time>
          {fact.is_accepted && fact.accepted_at && <> · <time dateTime={fact.accepted_at}>Accepted {new Date(fact.accepted_at).toLocaleString()}</time></>}
        </div>
      </li>)}
    </ul>
    <small className="secondary-text">Observations do not assign a Network or confirm the current configuration.</small>
  </details>;
}
