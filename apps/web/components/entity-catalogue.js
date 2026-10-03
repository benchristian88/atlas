import Link from "next/link";
import { StatusIndicator } from "./status-indicator";
import { EntityIdentity } from "./entity-identity";
import { EmptyState } from "./section";
import { Button } from "./button";

export function relationshipCount(count, singular) {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}

export function EntityCollection({ label, count, loading, error, onRefresh, empty, children }) {
  return <section className="table-card entity-catalogue" aria-label={label} aria-busy={loading}>
    <div className="table-meta"><span role="status">{loading ? `Loading ${label}…` : error ? `${label} could not be loaded.` : `${count} ${label}`}</span>{onRefresh && <Button variant="quiet" disabled={loading} onClick={onRefresh}>Refresh</Button>}</div>
    {count ? <ul className="catalogue-list">{children}</ul> : !loading && !error && <EmptyState>{empty}</EmptyState>}
  </section>;
}

export function CatalogueRow({ href, name, description, context, identity, actions, children }) {
  return <li className={actions ? "catalogue-item-with-actions" : undefined}><Link className="catalogue-row" href={href}>
    <div className="catalogue-identity">{identity}<div className="catalogue-copy"><strong className="catalogue-name">{name}</strong><span className="secondary-text catalogue-description">{description}</span><span className="catalogue-context">{context}</span></div></div>
    <div className="catalogue-secondary">{children}</div>
  </Link>{actions && <div className="catalogue-row-actions">{actions}</div>}</li>;
}

export function ServiceCatalogueRow({ service, serviceType }) {
  const relationships = [
    service.asset_dependency_count > 0 && relationshipCount(service.asset_dependency_count, "asset"),
    service.business_function_count > 0 && relationshipCount(service.business_function_count, "business function"),
  ].filter(Boolean).join(" · ");
  const health = service.operational_status || "unknown";
  return <CatalogueRow identity={<EntityIdentity type="service" record={service} reference={serviceType} size={38} />} href={`/services/${service.id}`} name={service.name} description={service.description || service.purpose || "Description not documented"} context={relationships}>
    <span>{service.service_type_name || "Type unavailable"}</span>
    <span className="catalogue-health"><StatusIndicator state={health} /></span>
    {service.archived_at ? <span>Archived</span> : service.lifecycle_status && service.lifecycle_status !== "active" && <span className="catalogue-lifecycle">{service.lifecycle_status}</span>}
  </CatalogueRow>;
}

export function BusinessFunctionCatalogueRow({ item }) {
  return <CatalogueRow identity={<EntityIdentity type="business_function" record={item} size={38} />} href={`/business-functions/${item.id}`} name={item.name} description={item.description || "Description not documented"} context={relationshipCount(item.service_count, "service")}>
    <span>{item.active ? "Active" : "Archived"}</span>
  </CatalogueRow>;
}

export const EntityCatalogue = EntityCollection;

export function AssetCatalogueRow({ asset, assetType, category, customer, site, canViewCompleteness, actions }) {
  const context = [assetType?.name || asset.asset_type, customer?.name, site?.name].filter(Boolean).join(" · ");
  return <CatalogueRow href={`/assets/${asset.id}`} identity={<EntityIdentity type="asset" record={asset} reference={{ ...category, ...assetType }} size={38} />} name={asset.name} description={[asset.vendor, asset.model].filter(Boolean).join(" ") || asset.description || "Description not documented"} context={context} actions={actions}>
    {asset.hostname && <span className="mono">{asset.hostname}</span>}
    <StatusIndicator state={asset.status} />
    {canViewCompleteness && <span className="catalogue-completeness">{asset.required_total > 0 ? `${Math.round(100 * asset.required_satisfied / asset.required_total)}% complete` : (asset.completeness_status || "not_evaluated").replaceAll("_", " ")}{asset.open_knowledge_gap_count > 0 && ` · ${asset.open_knowledge_gap_count} open gaps`}</span>}
  </CatalogueRow>;
}
