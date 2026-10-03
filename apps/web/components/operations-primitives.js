import { StatusIndicator } from "./status-indicator";
import { EntityIdentity } from "./entity-identity";
import { completenessPercent } from "../lib/operations-experience.mjs";

export function RecordedStatus({ state }) {
  return <StatusIndicator state={state} dotOnly />;
}

export function CompletenessLine({ node }) {
  const percent = completenessPercent(node);
  return <div className="ops-completeness">
    <span>{percent == null ? "Not evaluated" : `${percent}%`}</span>
    {percent != null && <div className="ops-completeness-track" role="meter" aria-label="Required knowledge completeness" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-valuetext={`${node.required_satisfied} of ${node.required_total} required requirements satisfied`}><span style={{ width: `${percent}%` }} /></div>}
  </div>;
}

export function EntityMark({ type, record }) {
  return <EntityIdentity type={type} record={record} />;
}
