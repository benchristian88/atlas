"use client";

import { AssetIcon } from "./asset-icon";
import { PresentationIcon } from "./presentation-identity.mjs";
import { resolveEntityIdentity } from "../lib/entity-identity.mjs";

export function EntityIdentity({ type, record, reference, size = 32 }) {
  const identity = resolveEntityIdentity(type, record, reference);
  return <span className={`entity-identity entity-${type}`} style={{ "--identity-size": `${size}px` }}>
    {type === "asset" ? <AssetIcon asset={record} assetType={reference} presentation={identity} size={size} /> : <PresentationIcon record={identity} />}
  </span>;
}
export const AssetIdentity = props => <EntityIdentity {...props} type="asset" />;
export const ServiceIdentity = props => <EntityIdentity {...props} type="service" />;
export const BusinessFunctionIdentity = props => <EntityIdentity {...props} type="business_function" />;
export const NetworkIdentity = props => <EntityIdentity {...props} type="network" />;
