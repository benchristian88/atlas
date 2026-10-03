"use client";

import Link from "next/link";
import { EntityIdentity } from "./entity-identity";
import { Children } from "react";
import { Section } from "./section";
import { PageHeader } from "./page-header";
import { CompletenessLine, RecordedStatus } from "./operations-primitives";
import { graphHref } from "../lib/operations-experience.mjs";

export function EntityDetailHeader({ type, id, name, description, subtitle, criticality, state, completeness, canViewCompleteness = true, canGraph = true, canPreview = false, actions, record, reference }) {
  const label = type === "asset" ? "Asset" : type === "service" ? "Service" : "Business Function";
  return <header className="entity-detail-header">
    <nav aria-label="Breadcrumb" className="entity-breadcrumb"><Link href={type === "asset" ? "/assets" : type === "service" ? "/services" : "/business-functions"}>{label}s</Link><span aria-hidden="true">/</span><span aria-current="page">{name}</span></nav>
    <PageHeader title={name} description={description} identity={<EntityIdentity type={type} record={record || { id }} reference={reference} size={48} />} />
    <div className="entity-detail-summary">
      <div className="entity-detail-meta"><span>{subtitle || label}</span>{criticality && <span className="ops-badge" aria-label={`Criticality: ${criticality}`}>{criticality}</span>}{type !== "business_function" && <span className="entity-recorded-state"><RecordedStatus state={state} />Recorded: {(state || "unknown").replaceAll("_", " ")}</span>}</div>
      <div className="entity-detail-completeness"><span className="ops-meta">Knowledge completeness</span>{type === "business_function" ? <span className="ops-meta">Not evaluated for Business Functions</span> : canViewCompleteness ? <CompletenessLine node={completeness} /> : <span className="ops-meta">Requires knowledge gaps permission</span>}</div>
    </div>
    <div className="entity-detail-actions">{canPreview && <Link className="button button-primary" href={graphHref({ focus: `${type}:${id}`, analysis: true })}>Preview unavailable</Link>}{canGraph && <Link className="button button-secondary" href={graphHref({ focus: `${type}:${id}` })}>View in Knowledge Graph</Link>}{actions}</div>
  </header>;
}

export function EntitySection({ title, description, count, children, id }) {
  return <Section className="ops-card entity-section" id={id} title={title} description={description} actions={count != null && <span className="ops-badge" aria-label={`${count} relationships`}>{count}</span>}>{children}</Section>;
}

export function EntityRelationshipRow({ type, name, href, context, description, metadata, children, actions }) {
  return <article className="entity-relationship-row">
    <EntityIdentity type={type} record={metadata} size={24} /><div className="entity-relationship-copy"><Link className="entity-relationship-name" href={href}>{name}</Link>{context && <p className="ops-meta">{context}</p>}{description && <p>{description}</p>}{metadata && <div className="entity-relationship-meta">{metadata.criticality_name && <span className="ops-badge">{metadata.criticality_name}</span>}{type === "service" && metadata.operational_state && <span><RecordedStatus state={metadata.operational_state} /> Recorded: {metadata.operational_state}</span>}{type === "service" && <CompletenessLine node={metadata} />}</div>}{children}</div>
    <div className="entity-relationship-actions"><Link className="text-button" href={href} aria-label={`Open ${name}`}>Open<span aria-hidden="true"> ↗</span></Link>{actions}</div>
  </article>;
}

export function EntityRelationshipList({ children, limit = 6 }) {
  const rows = Children.toArray(children);
  return <div className="entity-relationship-list">{rows.slice(0, limit)}{rows.length > limit && <details className="entity-disclosure"><summary>View all ({rows.length}) · {rows.length - limit} more</summary>{rows.slice(limit)}</details>}</div>;
}

export function EntityEditDisclosure({ title, children }) {
  return <details className="entity-disclosure entity-edit-disclosure"><summary>{title}</summary>{children}</details>;
}
