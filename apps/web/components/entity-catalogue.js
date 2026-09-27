import Link from "next/link";
import { RecordedStatus } from "./operations-primitives";

export function relationshipCount(count, singular) {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}

export function EntityCatalogue({ label, count, loading, error, onRefresh, empty, children }) {
  return <section className="table-card entity-catalogue" aria-label={label} aria-busy={loading}>
    <div className="table-meta"><span role="status">{loading ? `Loading ${label}…` : error ? `${label} could not be loaded.` : `${count} ${label}`}</span><button className="text-button" disabled={loading} onClick={onRefresh} type="button">Refresh</button></div>
    {count ? <ul className="catalogue-list">{children}</ul> : !loading && !error && <div className="empty-state">{empty}</div>}
  </section>;
}

export function CatalogueRow({ href, name, description, context, children }) {
  return <li><Link className="catalogue-row" href={href}>
    <div className="catalogue-identity"><strong className="catalogue-name">{name}</strong><span className="secondary-text catalogue-description">{description}</span><span className="catalogue-context">{context}</span></div>
    <div className="catalogue-secondary">{children}</div>
  </Link></li>;
}

export function ServiceCatalogueRow({ service }) {
  const relationships = [
    service.asset_dependency_count > 0 && relationshipCount(service.asset_dependency_count, "asset"),
    service.business_function_count > 0 && relationshipCount(service.business_function_count, "business function"),
  ].filter(Boolean).join(" · ");
  const health = service.operational_status || "unknown";
  return <CatalogueRow href={`/services/${service.id}`} name={service.name} description={service.description || service.purpose || "Description not documented"} context={relationships}>
    <span>{service.service_type_name || "Type unavailable"}</span>
    <span className="catalogue-health"><RecordedStatus state={health} /><span>{health[0].toUpperCase() + health.slice(1)}</span></span>
    {service.archived_at ? <span>Archived</span> : service.lifecycle_status && service.lifecycle_status !== "active" && <span className="catalogue-lifecycle">{service.lifecycle_status}</span>}
  </CatalogueRow>;
}

export function BusinessFunctionCatalogueRow({ item }) {
  return <CatalogueRow href={`/business-functions/${item.id}`} name={item.name} description={item.description || "Description not documented"} context={relationshipCount(item.service_count, "service")}>
    <span>{item.active ? "Active" : "Archived"}</span>
  </CatalogueRow>;
}
