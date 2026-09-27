"use client";

import Link from "next/link";
import { useState } from "react";
import { useWorkspaceContext } from "./workspace-context";
import { apiRequest } from "../lib/api";
import { ANALYSIS_CLASSIFICATION_LABELS, ANALYSIS_STATE_LABELS, explainDependencyReason, previewUnavailable } from "../lib/dependency-analysis.mjs";
import { DEPENDENCY_REQUIREMENT_LABELS, DEPENDENCY_STRATEGY_LABELS } from "../lib/dependency-semantics.mjs";

export function DependencyAnalysisPanel({ focusType, focusId }) {
  const { customerId, siteId } = useWorkspaceContext();
  return <AnalysisPreview key={`${focusType}:${focusId}:${customerId}:${siteId}`} focusType={focusType} focusId={focusId} />;
}

function AnalysisPreview({ focusType, focusId }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function preview() {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      setResult(await previewUnavailable(apiRequest, focusType, focusId));
    } catch (requestError) {
      setError(requestError.message || "Atlas could not preview this scenario.");
    } finally {
      setLoading(false);
    }
  }

  return <section className="detail-card dependency-analysis-panel" aria-label="Dependency analysis" aria-busy={loading}>
    <div className="form-card-header">
      <div><p className="eyebrow">Hypothetical scenario</p><h2>Dependency analysis</h2></div>
      <button className="button button-secondary" type="button" disabled={loading} onClick={preview}>
        {loading ? "Analysing…" : "Preview unavailable"}
      </button>
    </div>
    <p>Preview consequences for known Services if this {focusType === "asset" ? "Asset" : "Service"} were unavailable. This does not change accepted knowledge or report live health.</p>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <div aria-live="polite">
      {result && <>
        <p>{result.assumption}</p>
        {result.truncated && <div className="warning-banner" role="status">{result.warnings.join(" ")}</div>}
        {result.results.length === 0 && <p className="empty-state" role="status">{result.truncated ? "No conclusions available within the analysis limits." : "No Service consequences were found in the authorized knowledge for this scenario."}</p>}
        <div className="dependency-list">
          {result.results.map((row) => <article className="dependency-row" key={row.service.key}>
            <div>
              <Link href={row.service.href}><strong>{row.service.name}</strong></Link>
              <span>{ANALYSIS_STATE_LABELS[row.state]}</span>
              <small>{row.state === "unaffected" ? "Dependency remains satisfied" : ANALYSIS_CLASSIFICATION_LABELS[row.classification]} · {row.distance} {row.distance === 1 ? "hop" : "hops"}</small>
              {row.reasons.map((reason) => <div key={reason.key}>
                <p>{explainDependencyReason(row.service.name, reason)}</p><details><summary>Technical details</summary><strong>{reason.dependency_group_name || "Ungrouped dependency"}</strong>
                <p>{[DEPENDENCY_REQUIREMENT_LABELS[reason.dependency_requirement], DEPENDENCY_STRATEGY_LABELS[reason.dependency_strategy]].filter(Boolean).join(" · ")}</p>
                <p>{reason.summary}</p>
                <ul>{reason.members.map((member) => <li key={member.edge.key}>{member.entity.name}: {ANALYSIS_STATE_LABELS[member.state]}</li>)}</ul><p>Reason: {reason.code}</p></details>
              </div>)}
              <details><summary>Explanation paths</summary>
                {row.paths.map((path) => <p key={path.edges.map((edge) => edge.key).join("/")}>{path.nodes.map((node, index) => <span key={node.key}>
                  {index > 0 && <> ← {path.edges[index - 1].label} — </>}
                  <Link href={node.href}>{node.name}</Link>
                </span>)}</p>)}
              </details>
            </div>
          </article>)}
        </div>
      </>}
    </div>
  </section>;
}
