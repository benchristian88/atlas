"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { apiRequest } from "../lib/api";
import {
  clearRequestContext,
  readStoredContext,
  setRequestContext,
  storeContext,
} from "../lib/context-store";

const WorkspaceContext = createContext(null);

function idOf(value) {
  if (value === null || value === undefined || value === "") return null;
  return String(value);
}

function customerIdOf(site) {
  return idOf(site?.customer_id ?? site?.customerId ?? site?.customer?.id);
}

function selectedFromResponse(response) {
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

function resolveSelection({ customers, sites, preferred, serverSelected, allowGlobal }) {
  const customerIds = new Set(customers.map((customer) => idOf(customer.id)).filter(Boolean));
  const sitesById = new Map(sites.map((site) => [idOf(site.id), site]));

  function validated(candidate) {
    if (!candidate) return null;
    let customerId = idOf(candidate.customerId);
    const siteId = idOf(candidate.siteId);
    const site = siteId ? sitesById.get(siteId) : null;
    if (!customerId && site) customerId = customerIdOf(site);
    if (!customerId) return allowGlobal && !siteId ? { customerId: null, siteId: null } : null;
    if (!customerIds.has(customerId)) return null;
    return {
      customerId,
      siteId: site && customerIdOf(site) === customerId ? siteId : null,
    };
  }

  let selection = validated(preferred) || validated(serverSelected);
  if (!selection) {
    selection = {
      customerId: customers.length === 1 ? idOf(customers[0].id) : null,
      siteId: null,
    };
  }
  let { customerId, siteId } = selection;

  const customerSites = customerId
    ? sites.filter((site) => customerIdOf(site) === customerId)
    : [];
  if (siteId && customerIdOf(sitesById.get(siteId)) !== customerId) siteId = null;
  if (!siteId && customerSites.length === 1) siteId = idOf(customerSites[0].id);

  return { customerId, siteId };
}

export function WorkspaceContextProvider({ user, children }) {
  const loadGeneration = useRef(0);
  const [state, setState] = useState({
    status: "loading",
    customers: [],
    sites: [],
    customerId: null,
    siteId: null,
    allowGlobal: false,
    error: "",
  });

  const load = useCallback(async () => {
    const generation = ++loadGeneration.current;
    clearRequestContext();
    setState((current) => ({ ...current, status: "loading", error: "" }));
    try {
      const response = await apiRequest("/context", { omitContext: true });
      if (generation !== loadGeneration.current) return;
      const customers = Array.isArray(response?.customers) ? response.customers : [];
      const sites = Array.isArray(response?.sites) ? response.sites : [];
      const allowGlobal = response?.global_access === true;
      const selection = resolveSelection({
        customers,
        sites,
        preferred: readStoredContext(user.id),
        serverSelected: selectedFromResponse(response),
        allowGlobal,
      });
      setRequestContext(selection);
      storeContext(user.id, selection);
      setState({
        status: "ready",
        customers,
        sites,
        ...selection,
        allowGlobal,
        error: "",
      });
    } catch (requestError) {
      if (generation !== loadGeneration.current) return;
      clearRequestContext();
      setState({
        status: "error",
        customers: [],
        sites: [],
        customerId: null,
        siteId: null,
        allowGlobal: false,
        error: requestError.message || "Atlas could not load your available customer and site context.",
      });
    }
  }, [user.id]);

  useEffect(() => {
    load();
    return () => {
      loadGeneration.current += 1;
      clearRequestContext();
    };
  }, [load]);

  useEffect(() => {
    function revalidateContext() {
      load();
    }
    window.addEventListener("atlas:context-invalid", revalidateContext);
    return () => window.removeEventListener(
      "atlas:context-invalid",
      revalidateContext,
    );
  }, [load]);

  const commitSelection = useCallback((selection) => {
    setRequestContext(selection);
    storeContext(user.id, selection);
    setState((current) => ({ ...current, ...selection, error: "" }));
  }, [user.id]);

  const selectCustomer = useCallback((value) => {
    const customerId = idOf(value);
    if (!customerId) {
      if (state.allowGlobal) commitSelection({ customerId: null, siteId: null });
      return;
    }
    if (!state.customers.some((customer) => idOf(customer.id) === customerId)) return;

    const customerSites = state.sites.filter((site) => customerIdOf(site) === customerId);
    const currentSiteIsValid = customerSites.some((site) => idOf(site.id) === state.siteId);
    const siteId = currentSiteIsValid
      ? state.siteId
      : customerSites.length === 1 ? idOf(customerSites[0].id) : null;
    commitSelection({ customerId, siteId });
  }, [commitSelection, state.allowGlobal, state.customers, state.siteId, state.sites]);

  const selectSite = useCallback((value) => {
    const siteId = idOf(value);
    if (!siteId) {
      commitSelection({ customerId: state.customerId, siteId: null });
      return;
    }
    const site = state.sites.find((candidate) => idOf(candidate.id) === siteId);
    if (!site || customerIdOf(site) !== state.customerId) return;
    commitSelection({ customerId: state.customerId, siteId });
  }, [commitSelection, state.customerId, state.sites]);

  const value = useMemo(() => {
    const availableSites = state.customerId
      ? state.sites.filter((site) => customerIdOf(site) === state.customerId)
      : [];
    const activeCustomer = state.customers.find(
      (customer) => idOf(customer.id) === state.customerId,
    ) || null;
    const activeSite = state.sites.find((site) => idOf(site.id) === state.siteId) || null;
    return {
      ...state,
      availableSites,
      activeCustomer,
      activeSite,
      reloadKey: `${state.customerId || "all-customers"}:${state.siteId || "all-sites"}`,
      selectCustomer,
      selectSite,
      reload: load,
    };
  }, [load, selectCustomer, selectSite, state]);

  return (
    <WorkspaceContext.Provider value={value}>
      {state.status === "loading" ? (
        <main className="route-loading" aria-live="polite">
          <div className="status-banner" role="status">Loading your Atlas workspace…</div>
        </main>
      ) : children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspaceContext() {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("useWorkspaceContext must be used inside the Atlas workspace provider");
  return value;
}

export { customerIdOf };
