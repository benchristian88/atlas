"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { STAGES } from "../lib/onboarding.mjs";
import { integrationNeedsConfiguration, reviewRecommendations } from "../lib/onboarding-review.mjs";
import { Button } from "./button";
import { StatusIndicator } from "./status-indicator";
import styles from "./onboarding.module.css";

const restricted = "Restricted by your permissions";

function ReviewStage({ stage, decision, onReview, children }) {
  const title = STAGES.find(([key]) => key === stage)[1];
  return <li className={`${styles.reviewRow} ${styles.reviewStage}`}>
    <h4>{title}</h4>
    {onReview && <Button variant="quiet" onClick={onReview} aria-label={`Review ${title}`}>Review</Button>}
    <div className={styles.reviewStageDetails}>
      <div className={styles.reviewDecision}>Saved decision {decision
        ? <StatusIndicator state={decision === "attention" ? "needs_attention" : decision} variant="badge" />
        : "Pending"}</div>
      {children}
    </div>
  </li>;
}

function IntegrationStatus({ integrations }) {
  if (integrations === null) return <p>{restricted}.</p>;
  if (!integrations.items.length) return <p>No configured Integrations at this Site.</p>;
  return <>
    <ul className={styles.reviewIntegrations} aria-label="Configured Integrations">
      {integrations.items.map(row => <li key={row.id}>
        <strong>{row.name}</strong>
        <StatusIndicator state={row.status} variant="badge" />
        <span>{row.discovery_status ? <>Discovery <StatusIndicator
          state={row.discovery_status === "pending" ? "queued" : row.discovery_status} /></> : "No recorded discovery run"}</span>
        {row.discovery_configured === false && <StatusIndicator state="configuration_required" variant="badge" />}
      </li>)}
    </ul>
    {integrations.has_more && <p>Additional Integrations are outside this summary.</p>}
  </>;
}

function DiscoveryStatus({ decisions, active_runs }) {
  return <>
    <p>{decisions === null ? "Discovery decisions are restricted by your permissions."
      : `${decisions.eligible} eligible · ${decisions.conflicts} conflicts · ${decisions.exceptions} blocked or exceptional`}</p>
    <p>{active_runs === null ? "Discovery run status is restricted by your permissions."
      : active_runs === 0 ? "No discovery runs queued or running."
        : `${active_runs} discovery ${active_runs === 1 ? "run" : "runs"} queued or running.`}</p>
  </>;
}

function ReviewSummary({ review, decisions, visits, onKnowledgeGaps, blocked }) {
  const recommendations = reviewRecommendations(review);
  const stageProps = stage => ({ stage, decision: decisions[stage], onReview: blocked ? undefined : visits[stage] });
  return <div className={styles.reviewSections}>
    <section aria-labelledby="review-setup-summary">
      <h3 id="review-setup-summary">Setup summary</h3>
      <ul className={styles.reviewList}>
        <ReviewStage {...stageProps("environment")} />
        <ReviewStage {...stageProps("capabilities")}>
          <dl className={styles.reviewContext}>
            <div><dt>Business Functions</dt><dd>{review.business_functions ?? restricted}</dd></div>
            <div><dt>Services</dt><dd>{review.services ?? restricted}</dd></div>
          </dl>
        </ReviewStage>
        <ReviewStage {...stageProps("integrations")}><IntegrationStatus integrations={review.integrations} /></ReviewStage>
        <ReviewStage {...stageProps("discovery_review")}><DiscoveryStatus {...review.discovery} /></ReviewStage>
        <ReviewStage {...stageProps("link_services")}>
          {review.link_services === null ? <p>{restricted}.</p> : <>
            <p>{review.link_services.linked} linked · {review.link_services.unlinked} unlinked · {review.link_services.mappings} Asset mappings at this Site</p>
            {review.link_services.unavailable > 0 && <p>Mapping status is restricted for {review.link_services.unavailable} of the visible Services.</p>}
          </>}
        </ReviewStage>
      </ul>
    </section>
    <section aria-labelledby="review-next-steps">
      <h3 id="review-next-steps">Recommended next steps</h3>
      <p>{review.required_gaps === null ? "Required Knowledge Gaps are restricted by your permissions."
        : `${review.required_gaps} required or conditional Knowledge Gaps are open or deferred.`}</p>
      {recommendations.length ? <ul className={styles.reviewList}>
        {recommendations.map(({ id, stage, label, actionLabel = label }) => <li className={styles.reviewRow} key={id}>
          <span>{label}</span>
          {(stage ? visits[stage] : onKnowledgeGaps) && <Button variant="quiet"
            disabled={blocked} onClick={stage ? visits[stage] : onKnowledgeGaps} aria-label={actionLabel}>Review</Button>}
        </li>)}
      </ul> : <p>No outstanding work is visible in this review.</p>}
    </section>
  </div>;
}

export function OnboardingReviewReady({ path, decisions, visits, blocked, onKnowledgeGaps, onReloadProgress }) {
  const [review, setReview] = useState(null);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    apiRequest(`${path}/review-ready`, { signal, omitContext: true }).then(result => {
      if (!signal.aborted) setReview(result);
    }).catch(requestError => {
      if (!signal.aborted) setError(requestError);
    });
    return () => controller.abort();
  }, [path, attempt]);

  const contextUnavailable = [403, 404].includes(error?.status);
  return <>
    {error ? <div className="error-banner" role="alert">
      <p>{contextUnavailable ? "This review is unavailable. Reload setup progress to check your access."
        : "Current setup information could not be loaded."}</p>
      <Button disabled={blocked} onClick={contextUnavailable ? onReloadProgress : () => {
        setError(null);
        setAttempt(value => value + 1);
      }}>{contextUnavailable ? "Reload progress" : "Retry review"}</Button>
    </div> : review ? <ReviewSummary review={review} decisions={decisions} visits={visits} blocked={blocked}
      onKnowledgeGaps={onKnowledgeGaps ? () => onKnowledgeGaps(review.customer.id, review.site.id) : undefined} />
      : <p role="status">Loading current setup information…</p>}
  </>;
}
