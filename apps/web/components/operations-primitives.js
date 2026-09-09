import { completenessPercent } from "../lib/operations-experience.mjs";

export function RecordedStatus({ state }) {
  const value = (state || "unknown").replaceAll("_", " ");
  return <span className={`recorded-status status-${state || "unknown"}`} role="img" aria-label={`Recorded status: ${value}`} title={`Recorded status: ${value}`} />;
}

export function CompletenessLine({ node }) {
  const percent = completenessPercent(node);
  return <div className="ops-completeness">
    <span>{percent == null ? "Not evaluated" : `${percent}%`}</span>
    {percent != null && <div className="ops-completeness-track" role="meter" aria-label="Required knowledge completeness" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-valuetext={`${node.required_satisfied} of ${node.required_total} required requirements satisfied`}><span style={{ width: `${percent}%` }} /></div>}
  </div>;
}

export function EntityMark({ type }) {
  return <svg className={`entity-mark entity-${type}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
    {type === "asset" ? <><path d="m12 3 9 5v9l-9 5-9-5V8Z M3 8l9 5 9-5 M12 13v9" /></> : type === "service" ? <><circle cx="12" cy="12" r="9" /><ellipse cx="12" cy="12" rx="4" ry="9" /><path d="M3 12h18M5 7h14M5 17h14" /></> : <><circle cx="9" cy="7" r="3" /><path d="M2 21v-3a7 7 0 0 1 14 0v3M16 4a3 3 0 0 1 0 6M19 21v-3a6 6 0 0 0-3-5" /></>}
  </svg>;
}
