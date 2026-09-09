"use client";

import { useWorkspaceContext } from "./workspace-context";

export function ContextSelector() {
  const {
    activeCustomer,
    activeSite,
    availableSites,
    customerId,
    customers,
    selectCustomer,
    selectSite,
    siteId,
  } = useWorkspaceContext();
  const customerIsFixed = customers.length === 1;
  const siteIsFixed = Boolean(customerId) && availableSites.length === 1;

  return (
    <div className="context-selector" aria-label="Active workspace context">
      {customerIsFixed ? (
        <span className="context-value">
          <span>Customer</span>
          <strong>{activeCustomer?.name || "Unavailable"}</strong>
        </span>
      ) : (
        <label className="context-field">
          <span>Customer</span>
          <select
            aria-label="Active customer"
            disabled={!customers.length}
            onChange={(event) => selectCustomer(event.target.value)}
            value={customerId || ""}
          >
            <option disabled value="">Choose customer</option>
            {customers.map((customer) => (
              <option key={customer.id} value={customer.id}>{customer.name}</option>
            ))}
          </select>
        </label>
      )}

      <span className="context-separator" aria-hidden="true">/</span>

      {!customerId ? (
        <span className="context-value">
          <span>Site</span>
          <strong>{"Choose a customer"}</strong>
        </span>
      ) : siteIsFixed ? (
        <span className="context-value">
          <span>Site</span>
          <strong>{activeSite?.name || "Unavailable"}</strong>
        </span>
      ) : (
        <label className="context-field">
          <span>Site</span>
          <select
            aria-label="Active site"
            onChange={(event) => selectSite(event.target.value)}
            value={siteId || ""}
          >
            <option disabled value="">{availableSites.length ? "Choose site" : "No sites available"}</option>
            {availableSites.map((site) => (
              <option key={site.id} value={site.id}>{site.name}</option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}
