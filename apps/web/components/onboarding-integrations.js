"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "../lib/api";
import { discoveryControls } from "../lib/discovery.mjs";
import { formatIntegrationTime } from "../lib/integrations.mjs";
import { continuationCandidate, mutationOutcomeUnknown, runAppearedSinceRead, runNeedsPolling } from "../lib/onboarding-integrations.mjs";
import { useAuth } from "./auth-context";
import { Button } from "./button";
import { IntegrationCreateForm } from "./integration-create-form";
import { OfficialCatalogue } from "./official-catalogue";
import { EmptyState, Section } from "./section";
import { StatusIndicator } from "./status-indicator";
import styles from "./onboarding.module.css";

const POLL_INTERVAL = 3000;
const POLL_LIMIT = 100;
const globalRequest = (path, signal) => apiRequest(path, { omitContext: true, signal });
const discoveryFailure = {
  source_unavailable: "Discovery could not reach the source. Check the source and connection before retrying.",
  runtime_unavailable: "The discovery runtime was unavailable. Check its health before retrying.",
  runtime_interrupted: "The discovery runtime was interrupted. Check its health before retrying.",
  timeout: "Discovery timed out. Check the connection and try again.",
};

function useIntegrationReads(customerId, siteId, canView) {
  const [status, setStatus] = useState({ rows: [], loading: true });
  const [packages, setPackages] = useState({ forms: [], loading: true });
  const statusRequest = useRef(null);
  const packageRequest = useRef(null);
  const scoped = useCallback((path, options) => apiRequest(path, {
    ...options, omitContext: true, headers: { "X-Atlas-Customer-ID": customerId, "X-Atlas-Site-ID": siteId },
  }), [customerId, siteId]);
  const matches = useCallback(row => row?.customer_id === customerId && row?.site_id === siteId, [customerId, siteId]);

  const readRun = useCallback(async (id, signal) => {
    const [run] = await scoped(`/discovery-runs?integration_id=${id}&limit=1`, { signal });
    return matches(run) && run.integration_id === id ? run : null;
  }, [matches, scoped]);

  const loadStatus = useCallback(async ({ quiet = false } = {}) => {
    if (!canView || (quiet && statusRequest.current)) return;
    statusRequest.current?.abort();
    const controller = new AbortController();
    statusRequest.current = controller;
    const { signal } = controller;
    if (!quiet) setStatus(previous => ({ ...previous, loading: true, error: null }));
    try {
      const rows = (await scoped("/integrations?include_discovery=true", { signal })).filter(matches);
      if (!signal.aborted) setStatus({ rows, loading: false });
    } catch (error) {
      if (!signal.aborted) setStatus({ rows: [], loading: false, error: "Configured integrations could not be loaded. Reload integration status." });
    } finally {
      if (statusRequest.current === controller) statusRequest.current = null;
    }
  }, [canView, matches, scoped]);

  const loadPackages = useCallback(async () => {
    if (!canView) return;
    packageRequest.current?.abort();
    const controller = new AbortController();
    packageRequest.current = controller;
    setPackages(previous => ({ ...previous, loading: true }));
    const [catalogue, forms] = await Promise.allSettled([
      globalRequest("/integration-catalogue", controller.signal), globalRequest("/integration-forms", controller.signal),
    ]);
    if (controller.signal.aborted) return;
    setPackages({ loading: false, catalogue: catalogue.value, forms: forms.value || [],
      error: catalogue.status === "rejected" || forms.status === "rejected"
        ? "Some connector information is unavailable. Reload connectors to try again." : null });
  }, [canView]);

  useEffect(() => {
    if (canView) { void loadStatus(); void loadPackages(); }
    else { setStatus({ rows: [], loading: false }); setPackages({ forms: [], loading: false }); }
    return () => { statusRequest.current?.abort(); statusRequest.current = null; packageRequest.current?.abort(); };
  }, [canView, loadStatus, loadPackages]);

  const polling = canView && status.rows.some(row => runNeedsPolling(row.run));
  useEffect(() => {
    if (!polling) return;
    let remaining = POLL_LIMIT;
    const interval = setInterval(() => {
      void loadStatus({ quiet: true });
      if (--remaining === 0) clearInterval(interval);
    }, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [loadStatus, polling]);

  return { status, packages, loadStatus, loadPackages, scoped, matches, readRun };
}

function pendingOperation(key) {
  try {
    const value = JSON.parse(sessionStorage.getItem(key));
    if (value?.creationKey) return { creationKey: value.creationKey };
    if (value?.id) return { id: value.id };
  } catch { /* Session storage is optional. */ }
  return null;
}

function ConfiguredIntegration({ row, connector, canRun, disabled, feedback, launch }) {
  const controls = discoveryControls(row, canRun, false);
  const run = row.run;
  const failed = ["failed", "cancelled"].includes(run?.status);
  const retry = failed || (!run && feedback?.retry);
  return <li className={styles.integrationRow}>
    <div><h4>{row.name}</h4>
      <p className="secondary-text">{connector?.name || row.connector_id}{connector?.version ? ` · Installed ${connector.version}` : row.connector_version ? ` · Configured for ${row.connector_version}` : ""}</p>
      {row.generic || row.status === "disabled"
        ? <StatusIndicator state={row.retired_at ? "retired" : row.enabled ? "enabled" : "disabled"} />
        : <p className="secondary-text">Legacy integration</p>}
    </div>
    <dl className={styles.integrationFacts}>
      <div><dt>Last connection test</dt><dd>{row.last_test_at ? <><StatusIndicator state={row.last_test_status} /> · {formatIntegrationTime(row.last_test_at)}</> : row.generic ? "No recorded test" : "Unavailable"}</dd></div>
      <div><dt>Latest discovery</dt><dd>{run ? <>
        <StatusIndicator state={run.status === "pending" ? "queued" : run.status} /> · {formatIntegrationTime(run.finished_at || run.completed_at || run.started_at)}
        {run.observation_count > 0 && <p>{run.observation_count} observations recorded</p>}
      </> : "Not yet run"}</dd></div>
    </dl>
    {failed && <p className="secondary-text">{run.status === "cancelled" ? "Discovery was cancelled."
      : (Object.hasOwn(discoveryFailure, row.last_error_code) ? discoveryFailure[row.last_error_code]
        : "Discovery failed. Check the runtime and connection before retrying.")}</p>}
    {row.generic && row.enabled && !row.retired_at && !row.discovery_capable && <p className="secondary-text">Discovery is unavailable for this connector. Check the installed package and configuration in Integrations.</p>}
    {controls.run && !controls.eligible && <p className="secondary-text">Review configuration and credentials in Integrations before running discovery.</p>}
    {feedback && <p role={feedback.retry ? "alert" : "status"} className={feedback.retry ? "warning-banner" : "success-banner"}>{feedback.message}</p>}
    {controls.run && controls.eligible && !controls.active && !runNeedsPolling(run) && (!run || retry) &&
      <Button onClick={() => launch(row.id, run?.id)} disabled={disabled}>{retry ? "Retry discovery" : "Run discovery"}</Button>}
  </li>;
}

export function OnboardingIntegrations({ customer, site, profile, canManage, blocked, canAdvance, onBusy, onDirty, onDecision }) {
  const auth = useAuth();
  const permission = key => auth.hasPermissionInContext(key, customer.id, site.id);
  const canView = permission("integrations.view");
  const canConfigure = canManage && permission("integrations.manage") && permission("integrations.run") && canView;
  const canRun = canManage && permission("integrations.run");
  const reads = useIntegrationReads(customer.id, site.id, canView);
  const { status, packages, loadStatus, loadPackages, scoped, matches, readRun } = reads;
  const key = `atlas:onboarding:integration:${auth.user.id}:${customer.id}:${site.id}`;
  const [form, setForm] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [working, setWorking] = useState(false);
  const [feedback, setFeedback] = useState({});
  const [pending, setPending] = useState(null);
  const [recovering, setRecovering] = useState(false);
  const [recoveryNotice, setRecoveryNotice] = useState("");
  const [decisionNotice, setDecisionNotice] = useState("");
  const active = useRef(false);
  const focusReturn = useRef(null);
  const messageRef = useRef(null);
  const decisionNoticeRef = useRef(null);
  const operation = useRef(false);

  useEffect(() => {
    active.current = true;
    setPending(pendingOperation(key));
    return () => { active.current = false; };
  }, [key]);

  const setIntent = useCallback(intent => {
    if (active.current) setPending(intent);
    try {
      if (intent) sessionStorage.setItem(key, JSON.stringify(intent));
      else sessionStorage.removeItem(key);
    } catch { /* Preserve pending state for the lifetime of this view. */ }
  }, [key]);

  const recoverCreation = useCallback(async (creationKey, signal) => {
    if (!canView) return;
    setRecovering(true);
    try {
      const [saved] = await scoped(`/integrations?creation_key=${encodeURIComponent(creationKey)}`, { signal });
      if (!matches(saved) || signal?.aborted || !active.current) return;
      setRecoveryNotice("Atlas found the saved integration. Verify its discovery status before starting a run.");
      setIntent(null);
      void loadStatus();
    } catch {
      // Retain the unresolved operation. Reads can be repeated without replaying the mutation.
    } finally {
      if (!signal?.aborted && active.current) setRecovering(false);
    }
  }, [canView, loadStatus, matches, scoped, setIntent]);

  function markDirty(value) {
    setDirty(value);
    onDirty(value);
  }

  function closeForm(returnFocus = true) {
    setForm(null);
    markDirty(false);
    if (returnFocus) requestAnimationFrame(() => focusReturn.current?.isConnected && focusReturn.current.focus());
  }

  function handleBusy(value) {
    setWorking(value);
    onBusy(value);
  }

  async function dispatch(id, previousRunId) {
    try {
      const latest = await readRun(id);
      if (runAppearedSinceRead(latest, previousRunId)) return "A discovery run is already available for this integration.";
    } catch {
      if (active.current) setFeedback(old => ({ ...old, [id]: { retry: true, message: "The integration is saved. Atlas could not verify its discovery status before starting a run." } }));
      return "";
    }
    if (!active.current) return "";
    setIntent({ id });
    try {
      // Manual dispatch is also the canonical supported path for operator-local packages.
      const run = await scoped(`/integrations/${id}/run`, { method: "POST" });
      if (!matches(run) || run.integration_id !== id) throw new Error("Discovery response could not be confirmed.");
      setIntent(null);
      return active.current ? "Discovery requested." : "";
    } catch (error) {
      if (!active.current) return "";
      const activeId = error.details?.detail?.run_id;
      if (activeId && error.details.detail.code === "run_already_active") {
        setIntent(null);
        return "A discovery run is already active for this integration.";
      }
      if (mutationOutcomeUnknown(error)) return "";
      setIntent(null);
      setFeedback(old => ({ ...old, [id]: { retry: true, message: "The integration is saved. Discovery could not start. Check configuration, access and runtime, then retry discovery." } }));
      return "";
    }
  }

  async function runDiscovery(id, previousRunId) {
    if (operation.current || pending || blocked || !canRun) return;
    operation.current = true;
    handleBusy(true);
    setFeedback(old => ({ ...old, [id]: null }));
    try {
      const message = await dispatch(id, previousRunId);
      if (!active.current) return;
      if (message) setFeedback(old => ({ ...old, [id]: { message } }));
      await loadStatus();
    } finally {
      operation.current = false;
      if (active.current) handleBusy(false);
    }
  }

  async function create(body) {
    operation.current = true;
    setIntent({ creationKey: body.creation_key });
    try {
      let saved;
      try {
        saved = await scoped("/integrations", { method: "POST", body: JSON.stringify(body) });
        if (!matches(saved) || !saved.id) throw new Error("The saved integration could not be confirmed.");
      } catch (error) {
        if (!active.current) return;
        if (!mutationOutcomeUnknown(error)) { setIntent(null); throw error; }
        closeForm(false);
        requestAnimationFrame(() => messageRef.current?.focus());
        return;
      }
      if (!active.current) return;
      setIntent(null);
      closeForm(false);
      const message = form.capabilities?.discover === "read_only" ? await dispatch(saved.id, null) : "Integration saved.";
      if (active.current) {
        setRecoveryNotice(message === "Integration saved." ? message : ["Integration saved.", message].filter(Boolean).join(" "));
        await loadStatus();
        requestAnimationFrame(() => messageRef.current?.focus());
      }
    } finally { operation.current = false; }
  }

  // Only creation has an authoritative key lookup. Discovery reads update the
  // available runs without resolving the earlier request.
  useEffect(() => {
    if (!working && pending?.creationKey && !operation.current) {
      const controller = new AbortController();
      void recoverCreation(pending.creationKey, controller.signal);
      return () => controller.abort();
    }
  }, [working, pending, recoverCreation]);

  const next = !canView || status.loading ? null : continuationCandidate(status.rows);
  const uncertainDiscovery = Boolean(pending?.id);

  async function continueWithRun() {
    if (!next || blocked || working) return;
    setDecisionNotice("");
    const result = await onDecision("completed", next.continuation_run_id);
    if (result?.ok && uncertainDiscovery) setIntent(null);
    if (result?.status === 422) {
      setDecisionNotice("The discovery run is no longer eligible. Review the updated integration status before continuing.");
      requestAnimationFrame(() => decisionNoticeRef.current?.focus());
      await loadStatus();
    }
  }

  const configuration = {
    forms: packages.forms, canConfigure,
    open: selected => {
      if (!canConfigure || form || pending || working) return;
      focusReturn.current = document.activeElement;
      setForm(selected);
    },
  };
  const actionBlocked = blocked || working || Boolean(form || pending);
  return <div className={styles.integrationStage}>
    <p>{profile === "homelab" ? "Connect your Homelab to discover the Assets that support your Services." : "Connect infrastructure at this Site to discover Assets, or continue with manual setup."}</p>
    <div role="region" aria-label="Integration operation feedback" tabIndex={-1} ref={messageRef}>
      {pending && <div className="warning-banner">
        <p role="status">{uncertainDiscovery ? "Atlas has not confirmed the earlier discovery request. Check operation status to review the available runs."
          : "Atlas has not confirmed whether the integration was saved. Check the current records before submitting another request."}</p>
        {canView && <Button loading={uncertainDiscovery ? status.loading : recovering} disabled={working || blocked}
          onClick={() => uncertainDiscovery ? loadStatus() : recoverCreation(pending.creationKey)}>Check operation status</Button>}
      </div>}
      {recoveryNotice && <p role="status">{recoveryNotice}</p>}
    </div>
    {canView && <Section title="Configured integrations" heading="h3" actions={
      <Button variant="quiet" loading={status.loading} onClick={() => loadStatus()} disabled={working}>Reload integration status</Button>}>
      {status.error && <p className="error-banner" role="alert">{status.error}</p>}
      {status.loading && !status.rows.length ? <p role="status">Loading integrations…</p>
        : status.rows.length ? <ul className={styles.integrationList}>
          {status.rows.map(row => <ConfiguredIntegration key={row.id} row={row}
            connector={packages.catalogue?.installed_entries?.find(item => item.connector_id === row.connector_id)
              || packages.forms.find(item => item.connector_id === row.connector_id)
              || packages.catalogue?.entries?.find(item => item.connector_id === row.connector_id && item.installed_version === item.version && item.installed_version)}
            canRun={canRun} disabled={actionBlocked || status.loading} launch={runDiscovery} feedback={feedback[row.id]} />)}
        </ul> : !status.error && <EmptyState title="No configured integrations for this Site" />}
    </Section>}
    {!canView && <p>Your permissions do not include viewing integrations at this Site.</p>}
    {canView && !canConfigure && <p>Configuring a connection here requires Site setup, integration management and connection testing permissions.</p>}
    {form && <IntegrationCreateForm forms={packages.forms} selectedForm={form} fixedScope={{ customer, site }}
      canManageIn={() => canConfigure && !pending} canRunIn={() => canConfigure}
      onDirty={markDirty} onBusy={handleBusy} onCreate={create}
      onCancel={() => {
        if (!dirty || window.confirm("Discard this unsaved configuration? You will need to enter credentials again.")) closeForm();
      }} />}
    {canView && <OfficialCatalogue configuration={configuration}
      canViewOfficial={auth.hasGlobalPermission("integration_runtime.view")}
      canManage={canManage && auth.hasGlobalPermission("integration_runtime.manage")}
      styles={styles} catalogue={packages.catalogue} localLoading={packages.loading} localError={packages.error}
      busy={actionBlocked ? "setup" : ""} onInstalled={loadPackages} />}
    {canManage && canAdvance && <div className={styles.actions}>
      {decisionNotice && <p role="alert" tabIndex={-1} ref={decisionNoticeRef} className={`${styles.manualContinuation} warning-banner`}>{decisionNotice}</p>}
      {next && uncertainDiscovery && <p className={styles.manualContinuation}>
        A discovery run is available for {next.name}. You can use it to continue. The earlier request’s outcome is still unknown.
      </p>}
      {!next && canView && !status.loading && !status.error && <p className={styles.manualContinuation}>
        {uncertainDiscovery ? "There is no run available to continue with discovery. Check operation status again or continue without integrations."
          : canRun ? "Start discovery from a configured integration or continue without integrations."
          : "A user with discovery access can start a run, or you can continue without integrations."}
      </p>}
      {status.rows.length > 0 && <p className={styles.manualContinuation}>Manual continuation keeps existing integrations and discovery history.</p>}
      <Button disabled={blocked || working} onClick={() => onDecision("skipped")}>Continue without integrations</Button>
      {next && <Button variant="primary" disabled={blocked || working} onClick={continueWithRun}>
        {uncertainDiscovery ? "Use available run and continue" : "Continue to Discovery Review"}
      </Button>}
    </div>}
  </div>;
}
