export function idOf(value) {
  if (value === null || value === undefined || value === "") return null;
  return String(value);
}

export function customerIdOf(site) {
  return idOf(site?.customer_id ?? site?.customerId ?? site?.customer?.id);
}

export function selectedFromResponse(response) {
  if (
    !response?.selected
    && response?.selected_customer_id === undefined
    && response?.selected_site_id === undefined
  ) return null;
  const selected = response?.selected || {};
  return {
    customerId: idOf(
      selected.customer_id
      ?? selected.customerId
      ?? selected.customer?.id
      ?? response?.selected_customer_id,
    ),
    siteId: idOf(
      selected.site_id
      ?? selected.siteId
      ?? selected.site?.id
      ?? response?.selected_site_id,
    ),
  };
}

export function resolveSelection({ customers, sites, preferred, serverSelected }) {
  const customerIds = new Set(customers.map((customer) => idOf(customer.id)).filter(Boolean));
  const sitesById = new Map(sites.map((site) => [idOf(site.id), site]));

  function validated(candidate) {
    if (!candidate) return null;
    let customerId = idOf(candidate.customerId);
    const siteId = idOf(candidate.siteId);
    const site = siteId ? sitesById.get(siteId) : null;
    if (!customerId && site) customerId = customerIdOf(site);
    if (!customerId) return null;
    if (!customerIds.has(customerId)) return null;
    return {
      customerId,
      siteId: site && customerIdOf(site) === customerId ? siteId : null,
    };
  }

  let selection = validated(preferred) || validated(serverSelected);
  if (!selection) {
    selection = {
      customerId: customers.length ? idOf(customers[0].id) : null,
      siteId: null,
    };
  }
  let { customerId, siteId } = selection;

  const customerSites = customerId
    ? sites.filter((site) => customerIdOf(site) === customerId)
    : [];
  if (siteId && customerIdOf(sitesById.get(siteId)) !== customerId) siteId = null;
  if (!siteId && customerSites.length > 0) siteId = idOf(customerSites[0].id);

  return { customerId, siteId };
}

