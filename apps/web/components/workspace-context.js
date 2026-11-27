"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
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

export function WorkspaceContextProvider({ user, focused, children }) {
  const loadGeneration = useRef(0);
  const previousFocused = useRef(focused);
  const selectedForExit = useRef(false);
  const [savedSetupPath, setSavedSetupPath] = useState(null);
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

  // Keep normal shell refreshes while carrying a confirmed handoff into its destination.
  const changingMode = previousFocused.current !== focused;
  const refreshOnModeChange = changingMode && (focused || !selectedForExit.current);
  useLayoutEffect(() => {
    if (!changingMode) return;
    previousFocused.current = focused;
    selectedForExit.current = false;
    if (refreshOnModeChange) load();
  }, [changingMode, focused, load, refreshOnModeChange]);

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

  const commitSelection = useCallback((selection, context) => {
    loadGeneration.current += 1;
    setRequestContext(selection);
    storeContext(user.id, selection);
    setState((current) => ({ ...current, ...context, ...selection, error: "" }));
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
  }, [commitSelection, state.customers, state.siteId, state.sites]);

  const selectSite = useCallback((value) => {
    const siteId = idOf(value);
    if (!siteId) return;
    const site = state.sites.find((candidate) => idOf(candidate.id) === siteId);
    if (!site || customerIdOf(site) !== state.customerId) return;
    commitSelection({ customerId: state.customerId, siteId });
  }, [commitSelection, state.customerId, state.sites]);

  const selectContext = useCallback(async (customerId, siteId, signal) => {
    if (signal.aborted) return null;
    const generation = ++loadGeneration.current;
    let context;
    try {
      context = await apiRequest("/context", { omitContext: true, signal, redirectOnUnauthorized: false });
    } catch (error) {
      if (generation !== loadGeneration.current) return null;
      throw error;
    }
    if (generation !== loadGeneration.current || signal.aborted) return null;
    const { customers, sites, global_access: allowGlobal } = context;
    if (!customers.some(customer => idOf(customer.id) === customerId)
      || !sites.some(site => idOf(site.id) === siteId && customerIdOf(site) === customerId)) return false;
    // Retain the verified selection across the next shell transition, even
    // when browser storage is unavailable.
    selectedForExit.current = true;
    commitSelection({ customerId, siteId }, { customers, sites, allowGlobal, status: "ready" });
    return true;
  }, [commitSelection]);

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
      selectContext,
      savedSetupPath,
      setSavedSetupPath,
      reload: load,
    };
  }, [load, selectCustomer, selectSite, selectContext, savedSetupPath, state]);

  return (
    <WorkspaceContext.Provider value={value}>
      {state.status === "loading" || refreshOnModeChange ? (
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
