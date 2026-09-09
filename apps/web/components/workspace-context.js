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

import { idOf, customerIdOf, selectedFromResponse, resolveSelection } from "../lib/workspace-selection.mjs";

const WorkspaceContext = createContext(null);

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
    if (!customerId) return;
    if (!state.customers.some((customer) => idOf(customer.id) === customerId)) return;

    const customerSites = state.sites.filter((site) => customerIdOf(site) === customerId);
    const currentSiteIsValid = customerSites.some((site) => idOf(site.id) === state.siteId);
    const siteId = currentSiteIsValid
      ? state.siteId
      : customerSites.length > 0 ? idOf(customerSites[0].id) : null;
    commitSelection({ customerId, siteId });
  }, [commitSelection, state.allowGlobal, state.customers, state.siteId, state.sites]);

  const selectSite = useCallback((value) => {
    const siteId = idOf(value);
    if (!siteId) return;
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
      reloadKey: `${state.customerId || "no-customer"}:${state.siteId || "no-site"}`,
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
