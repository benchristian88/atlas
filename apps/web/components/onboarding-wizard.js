"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiRequest } from "../lib/api";
import { DASHBOARD_GAPS_HREF } from "../lib/knowledge-gap-filters.mjs";
import { canContinueSetup, initialEnvironment, onboardingPath, PROFILES, STAGES } from "../lib/onboarding.mjs";
import { pendingApplyKey, readPendingApply } from "../lib/onboarding-capabilities.mjs";
import { finishSetup } from "../lib/onboarding-showcase.mjs";
import { authenticatedHome, useAuth } from "./auth-context";
import { Button } from "./button";
import { OnboardingCapabilities } from "./onboarding-capabilities";
import { OnboardingDiscoveryReview } from "./onboarding-discovery-review";
import { OnboardingIntegrations } from "./onboarding-integrations";
import { OnboardingLinkServices } from "./onboarding-link-services";
import { OnboardingReviewReady } from "./onboarding-review-ready";
import { OnboardingShowcase } from "./onboarding-showcase";
import { PageHeader } from "./page-header";
import { Section, Surface } from "./section";
import { useWorkspaceContext } from "./workspace-context";
import styles from "./onboarding.module.css";

const request = (path, options) => apiRequest(path, { ...options, omitContext: true });
const write = (path, method, values) => request(path, { method, body: JSON.stringify(values) });
const decisionLabels = { completed: "Completed", skipped: "Skipped", attention: "Needs attention" };

function Wizard({ stage, activeStage = stage, decisions = {}, completed, context, visits, children }) {
  return <>
    <PageHeader title="Guided setup" description={completed ? "Setup is complete for this Site." : !context ? "Set up one Site at a time." : undefined}
      metadata={context && <dl className={styles.contextLine} aria-label={context.profile ? "Confirmed setup context" : "Selected setup context"}>
        <div><dt>Customer</dt><dd>{context.customer.name}</dd></div>
        <div><dt>Site</dt><dd>{context.site.name}</dd></div>
        {context.profile && <div><dt>Profile</dt><dd>{PROFILES[context.profile]}</dd></div>}
      </dl>} />
    <div className={styles.layout}>
      <nav aria-label="Setup stages" className={styles.rail}>
        <ol>
          {STAGES.map(([key, title], index) => {
            const label = decisionLabels[decisions[key]] || (key === activeStage ? "In progress" : "Pending");
            const openStage = stage !== key && visits?.[key];
            return <li key={key} aria-current={stage === key ? "step" : undefined}>
              <span className={styles.stepNumber} aria-hidden="true">{index + 1}</span>
              <div>
                {openStage
                  ? <button className="text-button" type="button" onClick={openStage}>{title}</button>
                  : <strong>{title}</strong>}
                <small>{label}{key === activeStage && stage !== key && " · Current stage"}</small>
              </div>
            </li>;
          })}
        </ol>
      </nav>
      {children}
    </div>
  </>;
}

function Feedback({ error, retry, busy }) {
  const errorRef = useRef(null);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);
  if (!error) return null;
  return <div className="error-banner" role="alert" tabIndex={-1} ref={errorRef}>
    {error.message}
    {retry && <> <Button onClick={retry} disabled={busy}>Reload progress</Button></>}
  </div>;
}

function Unavailable({ error, retry, recovery = false }) {
  const { user } = useAuth();
  const blocked = [403, 404, 422].includes(error?.status);
  return <Surface>
    <Feedback error={blocked ? new Error("Guided setup is unavailable for this selection.") : error} />
    <div className={styles.actions}>
      {!blocked && <Button onClick={retry}>Try again</Button>}
      {recovery && <Button href="/onboarding">Choose another Site</Button>}
      <Button href={authenticatedHome(user)}>Return to Atlas</Button>
    </div>
  </Surface>;
}

function NameEditor({ operation, onSave, onCancel, onRefresh }) {
  const [name, setName] = useState(operation.name || "");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const input = useRef(null);
  const entity = operation.kind === "customer" ? "Customer" : "Site";
  const label = operation.id ? `Rename ${entity}` : `Create ${entity}`;

  useEffect(() => { input.current?.focus(); }, []);

  async function submit(event) {
    event.preventDefault();
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onSave(operation, name.trim());
    } catch (requestError) {
      setError(requestError);
    } finally {
      setBusy(false);
    }
  }

  return <form onSubmit={submit} className={styles.editor} aria-label={label}>
    <h3>{label}</h3>
    <label className="field">{entity} name
      <input ref={input} required maxLength={255} value={name} onChange={(event) => setName(event.target.value)} disabled={busy} />
    </label>
    <Feedback error={error} />
    {error && !operation.id && <p>Refresh the Customer and Site choices before retrying if the last request may have succeeded.</p>}
    <div className={styles.actions}>
      <Button variant="primary" type="submit" loading={busy} disabled={!name.trim()}>{operation.id ? "Save name" : label}</Button>
      <Button onClick={onCancel} disabled={busy}>Cancel</Button>
      {error && !operation.id && onRefresh && <Button onClick={onRefresh} disabled={busy}>Refresh choices</Button>}
    </div>
  </form>;
}

function saveName({ kind, id, customerId }, name) {
  return write(`/${kind}s${id ? `/${id}` : ""}`, id ? "PATCH" : "POST", {
    name,
    ...(!id && kind === "site" ? { customer_id: customerId } : {}),
  });
}

export function OnboardingChooser() {
  const { user, hasPermissionForObject } = useAuth();
  const [options, setOptions] = useState(null);
  const [selection, setSelection] = useState(null);
  const [editor, setEditor] = useState(null);
  const [error, setError] = useState(null);
  const [reload, setReload] = useState(0);
  const heading = useRef(null);
  const choices = useRef(null);

  useEffect(() => {
    let active = true;
    request("/onboarding/contexts").then((result) => {
      if (!active) return;
      setOptions(result);
      setError(null);
    }).catch((requestError) => { if (active) setError(requestError); });
    return () => { active = false; };
  }, [reload]);

  useEffect(() => { if (options) heading.current?.focus(); }, [options]);

  function refresh() {
    setEditor(null);
    setError(null);
    setReload((value) => value + 1);
  }

  async function saveEditor(operation, name) {
    const record = await saveName(operation, name);
    // Keep the committed Customer selectable even if creating its Site fails.
    const key = operation.kind === "site" ? "sites" : "customers";
    const entry = key === "customers" ? { can_add_site: true, ...record } : record;
    setOptions((old) => ({
      ...old,
      [key]: operation.id
        ? old[key].map((row) => row.id === record.id ? { ...row, name: record.name } : row)
        : [...old[key], entry],
    }));
    if (!operation.id) {
      setSelection(operation.kind === "site"
        ? { customerId: record.customer_id, siteId: record.id }
        : { customerId: record.id, siteId: "" });
    }
    setEditor(null);
  }

  if (error) return <Unavailable error={error} retry={refresh} />;
  if (!options) return <p role="status">Loading Customer and Site choices…</p>;
  const suggested = selection || initialEnvironment(options);
  const customer = options.customers.find(({ id }) => id === suggested.customerId);
  const sites = options.sites.filter(({ customer_id }) => customer_id === customer?.id);
  const site = sites.find(({ id }) => id === suggested.siteId);

  return <Wizard stage="environment">
    <Surface className={styles.panel}>
      <Section title="Environment" description="Choose the Customer and Site you want to set up." headingRef={heading}>
        <div className={styles.fields} ref={choices}>
          <label className="field">Customer
            <select value={customer?.id || ""} disabled={Boolean(editor)}
              onChange={(event) => setSelection({ customerId: event.target.value, siteId: "" })}>
              <option value="">Select a Customer</option>
              {options.customers.map(({ id, name }) => <option key={id} value={id}>{name}</option>)}
            </select>
          </label>
          <label className="field">Site
            <select value={site?.id || ""} disabled={Boolean(editor) || !sites.length}
              onChange={(event) => setSelection({ customerId: customer.id, siteId: event.target.value })}>
              <option value="">Select a Site</option>
              {sites.map(({ id, name, status }) => <option key={id} value={id}>
                {status === "completed" ? `${name} · Setup completed` : canContinueSetup(status) ? `${name} · Setup started` : name}
              </option>)}
            </select>
          </label>
        </div>
        {customer && !sites.length && <p>No Sites are available for setup in this Customer.</p>}
        {!options.customers.length && <p>No Customers are available for setup.</p>}
        {editor
          ? <NameEditor operation={editor} onSave={saveEditor} onRefresh={refresh} onCancel={() => {
            setEditor(null);
            requestAnimationFrame(() => choices.current?.querySelector("select")?.focus());
          }} />
          : <div className={styles.actions}>
            {options.can_add_customer && <Button onClick={() => setEditor({ kind: "customer" })}>Create Customer</Button>}
            {customer && hasPermissionForObject("customers.manage", customer.id) &&
              <Button onClick={() => setEditor({ kind: "customer", id: customer.id, name: customer.name })}>Rename Customer</Button>}
            {customer?.can_add_site && <Button onClick={() => setEditor({ kind: "site", customerId: customer.id })}>Create Site</Button>}
            {site && <Button onClick={() => setEditor({ kind: "site", id: site.id, name: site.name })}>Rename Site</Button>}
          </div>}
        <div className={styles.footer}>
          <Button href={authenticatedHome(user)}>Return to Atlas</Button>
          <Button onClick={refresh} disabled={Boolean(editor)}>Refresh choices</Button>
          {site && <Button variant="primary" href={onboardingPath(customer.id, site.id)} disabled={Boolean(editor)}>Open Site setup</Button>}
        </div>
      </Section>
    </Surface>
  </Wizard>;
}

export function OnboardingSession({ customerId, siteId }) {
  const { user, hasPermissionForObject } = useAuth();
  const { selectContext, setSetupHandoff } = useWorkspaceContext();
  const router = useRouter();
  const path = onboardingPath(customerId, siteId);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const [pendingProfile, setPendingProfile] = useState(null);
  const [visitedStage, setVisitedStage] = useState(null);
  const [returning, setReturning] = useState(false);
  const [returnError, setReturnError] = useState(null);
  const [retainCapabilities, setRetainCapabilities] = useState(false);
  const [capabilitiesBusy, setCapabilitiesBusy] = useState(false);
  const [integrationsBusy, setIntegrationsBusy] = useState(false);
  const [integrationDirty, setIntegrationDirty] = useState(false);
  const [discoveryReviewBusy, setDiscoveryReviewBusy] = useState(false);
  const [linkServicesBusy, setLinkServicesBusy] = useState(false);
  const [receipt, setReceipt] = useState(null);
  const [completionNotice, setCompletionNotice] = useState("");
  const [editor, setEditor] = useState(null);
  const heading = useRef(null);
  const capabilitiesHeading = useRef(null);
  const progressWrite = useRef(false);
  const workspaceHandoff = useRef(null);
  const stageReturn = useRef(null);
  const saved = data?.status === "saved";
  const pendingKey = pendingApplyKey(user.id, path);
  const pending = data?.progress?.environment_profile === "homelab" && Boolean(readPendingApply(pendingKey));
  const activeStage = data?.progress?.current_stage || "environment";
  const stage = visitedStage ?? (pending ? "capabilities" : activeStage);
  const showCapabilities = data?.progress?.environment_profile
    && (!saved || !data.can_manage || pending) && stage === "capabilities";
  const mountCapabilities = showCapabilities
    || (retainCapabilities && data?.progress?.environment_profile && data.can_manage && !saved);
  const profile = pendingProfile ?? data?.progress?.draft_profile ?? "homelab";

  useLayoutEffect(() => () => {
    workspaceHandoff.current?.abort();
    stageReturn.current?.abort();
  }, [path]);

  useEffect(() => {
    let active = true;
    request(path, { cache: "no-store" }).then((result) => {
      if (!active) return;
      setData(result);
      setError(null);
      setLoading(false);
    }).catch((requestError) => {
      if (!active) return;
      setData(null);
      setError(requestError);
      setLoading(false);
    });
    return () => { active = false; };
  }, [path, pendingKey, reload]);

  useEffect(() => {
    if (loading) return;
    const target = showCapabilities ? capabilitiesHeading : heading;
    target.current?.focus();
  }, [stage, loading, saved, showCapabilities, receipt]);

  useEffect(() => {
    if (!integrationDirty) return;
    const warn = event => { event.preventDefault(); event.returnValue = ""; };
    const guardLink = event => {
      const link = event.target.closest?.("a[href]");
      if (!link || link.target === "_blank" || event.metaKey || event.ctrlKey || link.href === location.href) return;
      if (!window.confirm("Discard this unsaved integration configuration? You will need to enter credentials again.")) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", warn);
    document.addEventListener("click", guardLink, true);
    return () => {
      window.removeEventListener("beforeunload", warn);
      document.removeEventListener("click", guardLink, true);
    };
  }, [integrationDirty]);

  function confirmLeavingIntegration() {
    return !integrationsBusy && (!integrationDirty || window.confirm(
      "Discard this unsaved integration configuration? You will need to enter credentials again.",
    ));
  }

  function cancelStageReturn() {
    if (!stageReturn.current) return;
    stageReturn.current.abort();
    stageReturn.current = null;
    setReturning(false);
  }

  function visitStage(nextStage) {
    if (progressWrite.current || !confirmLeavingIntegration()) return;
    cancelStageReturn();
    setReturnError(null);
    setIntegrationDirty(false);
    if (stage === "capabilities") setRetainCapabilities(true);
    if (nextStage === "capabilities") setReceipt(null);
    setVisitedStage(nextStage === activeStage ? null : nextStage);
  }

  function refresh() {
    if (!confirmLeavingIntegration()) return;
    cancelStageReturn();
    setReturnError(null);
    setIntegrationDirty(false);
    setLoading(true);
    setError(null);
    setEditor(null);
    setVisitedStage(null);
    setRetainCapabilities(false);
    setPendingProfile(null);
    setReload((value) => value + 1);
  }

  async function returnToCurrentStage(discardCapabilities = false) {
    if (progressWrite.current || stageReturn.current || !confirmLeavingIntegration()) return;
    const controller = new AbortController();
    stageReturn.current = controller;
    setReturning(true);
    setReturnError(null);
    try {
      const result = await request(path, {
        cache: "no-store",
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15_000)]),
        redirectOnUnauthorized: false,
      });
      if (controller.signal.aborted) return;
      setData(result);
      setError(null);
      setIntegrationDirty(false);
      if (discardCapabilities || !result.can_manage) setRetainCapabilities(false);
      else if (stage === "capabilities") setRetainCapabilities(true);
      setVisitedStage(null);
    } catch (requestError) {
      if (controller.signal.aborted) return;
      if (requestError.status === 401) {
        router.replace("/login");
      } else if ([403, 404].includes(requestError.status)) {
        setData(null);
        setError(requestError);
      } else {
        setReturnError(new Error("Current setup progress could not be verified. " + requestError.message));
      }
    } finally {
      if (stageReturn.current === controller && !controller.signal.aborted) {
        stageReturn.current = null;
        setReturning(false);
      }
    }
  }

  async function change(action, decision, decisionVersion) {
    if (!data.can_manage || progressWrite.current || stageReturn.current || !confirmLeavingIntegration()) return;
    progressWrite.current = true;
    setBusy(true);
    setError(null);
    const exit = action === "save" ? new AbortController() : null;
    if (exit) workspaceHandoff.current = exit;
    try {
      let progress = data.progress;
      if (!progress && action === "environment") {
        progress = await request(`${path}/start`, { method: "POST" });
        if (progress.version !== 1) {
          throw Object.assign(new Error("Setup progress changed. Reload progress before trying again."), { status: 409 });
        }
        setData((old) => ({ ...old, progress, status: progress.status }));
      }
      const updated = await write(`${path}/${action}`, action === "environment" ? "PATCH" : "POST", {
        version: progress?.version ?? 0,
        ...(action === "environment" ? { environment_profile: profile } : {}),
        ...(action === "save" && !progress?.environment_profile ? { draft_profile: profile } : {}),
        ...(action === "integrations/decision" ? { decision, discovery_run_id: decisionVersion } : {}),
        ...(action === "discovery-review/decision" ? { decision, review_version: decisionVersion } : {}),
        ...(action === "link-services/decision" ? { action: decision, acknowledge_attention: decisionVersion } : {}),
      });
      if (exit?.signal.aborted) return;
      setIntegrationDirty(false);
      setPendingProfile(null);
      setData((old) => ({ ...old, progress: updated, status: updated.status }));
      if (exit) await exitWithProgress(updated, exit.signal);
      return { ok: true };
    } catch (requestError) {
      if (exit?.signal.aborted) return;
      if (action === "integrations/decision" && decision === "completed" && requestError.status === 422) {
        return { status: 422 };
      }
      if (action === "discovery-review/decision" && requestError.details?.detail?.code === "discovery_review_changed") {
        return { refreshReview: true };
      }
      if (action === "link-services/decision" && requestError.details?.detail?.code === "link_services_attention") {
        return { refreshMappings: true };
      }
      if ([403, 404].includes(requestError.status)) {
        setIntegrationDirty(false);
        setData(null);
      }
      setError(requestError);
    } finally {
      if (exit) workspaceHandoff.current = null;
      progressWrite.current = false;
      setBusy(false);
    }
  }

  async function exitWithProgress(progress, signal) {
    if (["review_ready", "showcase"].includes(progress.current_stage)) {
      let selected;
      try {
        selected = await selectContext(progress.customer_id, progress.site_id,
          AbortSignal.any([signal, AbortSignal.timeout(15_000)]));
      } catch {
        selected = false;
      }
      if (signal.aborted) return;
      if (!selected) setSetupHandoff({ path, status: progress.status });
    }
    try {
      router.replace(authenticatedHome(user));
    } catch (navigationError) {
      if (progress.status !== "completed") throw navigationError;
      setCompletionNotice("Setup is complete. You can retry returning to the Dashboard.");
    }
  }

  async function finishOrReturn() {
    if (progressWrite.current || stageReturn.current || !confirmLeavingIntegration()) return;
    const controller = new AbortController();
    const { signal } = controller;
    workspaceHandoff.current = controller;
    progressWrite.current = true;
    setBusy(true);
    setError(null);
    setCompletionNotice("");
    try {
      if (data.status === "completed") {
        await exitWithProgress(data.progress, signal);
        return;
      }
      if (!data.can_manage || data.status !== "in_progress" || stage !== "showcase") return;
      const options = () => ({
        signal: AbortSignal.any([signal, AbortSignal.timeout(15_000)]),
        cache: "no-store",
        redirectOnUnauthorized: false,
      });
      const version = data.progress.version;
      const result = await finishSetup({
        version, signal,
        complete: async () => {
          const progress = await request(`${path}/complete`, {
            ...options(), method: "POST", body: JSON.stringify({ version }),
          });
          if (progress?.status !== "completed" || !progress.completed_at
            || progress.customer_id !== customerId || progress.site_id !== siteId) {
            throw new Error("Atlas returned an unexpected completion response.");
          }
          return progress;
        },
        read: () => request(path, options()),
      });
      if (signal.aborted) return;
      if (result.latest) {
        setData(result.latest);
        setCompletionNotice("Atlas verified that setup is complete for this Site.");
      } else if (result.progress) {
        const progress = result.progress;
        setData(old => ({ ...old, progress, status: progress.status }));
        await exitWithProgress(progress, signal);
      }
    } catch (requestError) {
      if (signal.aborted) return;
      if (requestError.status === 401) router.replace("/login");
      else if ([403, 404].includes(requestError.status)) refresh();
      else setError(requestError);
    } finally {
      workspaceHandoff.current = null;
      progressWrite.current = false;
      setBusy(false);
    }
  }

  async function openConfirmedDestination(confirmedCustomerId, confirmedSiteId, destination) {
    if (progressWrite.current || stageReturn.current) return;
    progressWrite.current = true;
    setBusy(true);
    setError(null);
    const controller = new AbortController();
    workspaceHandoff.current = controller;
    try {
      const selected = await selectContext(confirmedCustomerId, confirmedSiteId,
        AbortSignal.any([controller.signal, AbortSignal.timeout(15_000)]));
      if (controller.signal.aborted || selected === null) return;
      if (!selected) {
        throw new Error("The confirmed Customer and Site are no longer available in the workspace.");
      }
      router.push(destination);
    } catch (requestError) {
      if (!controller.signal.aborted) setError(requestError);
    } finally {
      workspaceHandoff.current = null;
      progressWrite.current = false;
      setBusy(false);
    }
  }

  async function saveEditor(operation, name) {
    const updated = await saveName(operation, name);
    setData((old) => ({ ...old, [operation.kind]: { ...old[operation.kind], name: updated.name } }));
    setEditor(null);
    heading.current?.focus();
  }

  function adoptProgress(progress, keepCapabilities = false, canManage) {
    // A catalogue read completing in a hidden panel must not move the operator.
    if (stage !== "capabilities" || stageReturn.current) return;
    setData((old) => ({ ...old, progress, status: progress.status, can_manage: canManage ?? old.can_manage }));
    if (!keepCapabilities) setRetainCapabilities(false);
    setVisitedStage(keepCapabilities && progress.current_stage !== "capabilities" ? "capabilities" : null);
  }

  if (loading) return <p role="status">Loading setup progress…</p>;
  if (!data) return <Unavailable error={error} retry={refresh} recovery />;
  const { customer, site, progress, can_manage: canManage } = data;
  const confirmed = Boolean(progress?.environment_profile);
  const completed = data.status === "completed";
  const conflict = error?.status === 409;
  const blocked = busy || capabilitiesBusy || integrationsBusy || discoveryReviewBusy || linkServicesBusy || Boolean(editor) || conflict;
  const stageTitle = STAGES.find(([key]) => key === stage)?.[1] || "Setup progress";
  const showingReview = stage === "review_ready";
  const showingShowcase = stage === "showcase" && (!saved || !canManage);

  const canVisitCapabilities = confirmed && progress.stage_decisions.capabilities && (canManage || showingReview)
    && !saved && !blocked && stage !== "capabilities";
  const visitCapabilities = () => visitStage("capabilities");
  const visitEnvironment = () => visitStage("environment");
  const canVisitIntegrations = confirmed && progress.stage_decisions.integrations && !saved && !blocked && !pending
    && stage !== "integrations";
  const visitIntegrations = () => visitStage("integrations");
  const visitDiscoveryReview = () => visitStage("discovery_review");
  const visitLinkServices = () => visitStage("link_services");
  const canVisitDiscoveryReview = confirmed && progress.stage_decisions.discovery_review && !saved && !blocked && !pending
    && stage !== "discovery_review";
  const canVisitLinkServices = confirmed && progress.stage_decisions.link_services && !saved && !blocked && !pending
    && stage !== "link_services";
  const visitEarlier = {
    environment: confirmed ? visitEnvironment : undefined,
    capabilities: canVisitCapabilities ? visitCapabilities : undefined,
    integrations: canVisitIntegrations ? visitIntegrations : undefined,
    discovery_review: canVisitDiscoveryReview ? visitDiscoveryReview : undefined,
    link_services: canVisitLinkServices ? visitLinkServices : undefined,
  };
  const railVisits = confirmed && !blocked && !saved && !pending ? {
    ...visitEarlier,
    capabilities: canVisitCapabilities && (showingReview || showingShowcase || stage === "integrations" || progress.environment_profile === "homelab")
      ? visitCapabilities : undefined,
    review_ready: progress.stage_decisions.review_ready ? () => visitStage("review_ready") : undefined,
    [activeStage]: () => returnToCurrentStage(),
  } : undefined;

  return <Wizard stage={stage} activeStage={activeStage} decisions={progress?.stage_decisions} completed={completed}
    context={{ customer, site, profile: progress?.environment_profile }} visits={railVisits}>
    <div className={styles.stageContent}>
      {mountCapabilities && <Surface className={styles.panel} hidden={!showCapabilities}>
        <Section title="Capabilities" headingRef={capabilitiesHeading}>
          <Feedback error={showCapabilities ? returnError : null} retry={refresh} busy={returning} />
          <OnboardingCapabilities key={String(canManage)} path={path} pendingKey={pendingKey} progress={progress}
            visible={showCapabilities} returning={returning} headingRef={capabilitiesHeading} home={authenticatedHome(user)}
            onEnvironment={visitEnvironment} onReturn={() => returnToCurrentStage(true)}
            onProgress={adoptProgress} onExit={() => router.replace(authenticatedHome(user))}
            onApplied={(outcome, latest, canManage) => {
              setReceipt(outcome);
              adoptProgress(latest, false, canManage);
            }}
            onBusy={setCapabilitiesBusy} />
        </Section>
      </Surface>}
      {!showCapabilities && (showingShowcase ? <OnboardingShowcase key={`${user.id}:${path}`}
        path={path} customer={customer} site={site} profile={progress.environment_profile} completed={completed}
        headingRef={heading} blocked={blocked || returning} onExplore={destination => openConfirmedDestination(customer.id, site.id, destination)}>
        <Feedback error={error} retry={conflict ? refresh : undefined} busy={busy} />
        {completionNotice && <p role="status" className="success-banner">{completionNotice}</p>}
        <div className={styles.footer}>
          <Button onClick={() => visitStage("review_ready")} disabled={blocked || returning}>Back to Review &amp; Ready</Button>
          {canManage && !completed && <Button onClick={() => change("save")} disabled={blocked || returning}>Save &amp; exit</Button>}
          {completed ? <Button variant="primary" onClick={finishOrReturn} loading={busy}>Return to Dashboard</Button>
            : canManage ? <Button variant="primary" onClick={finishOrReturn} loading={busy}
              disabled={blocked || returning}>Finish setup &amp; explore Atlas</Button>
              : <Button href={authenticatedHome(user)}>Return to Atlas</Button>}
        </div>
      </OnboardingShowcase> :
      <Surface className={styles.panel}>
        <Section title={stageTitle} headingRef={heading} description={showingReview
          ? "Review what you have configured so far. You can address outstanding items now or continue exploring Atlas and complete them later."
          : undefined}>
          <Feedback error={returnError ?? error} retry={returnError || conflict ? refresh : undefined} busy={busy || returning} />
          {receipt && !showingReview && stage !== "showcase" && <p role="status" className="success-banner">
            Capabilities applied. Created {receipt.created.functions} {receipt.created.functions === 1 ? "Business Function" : "Business Functions"},
            {" "}{receipt.created.services} {receipt.created.services === 1 ? "Service" : "Services"} and
            {" "}{receipt.created.associations} {receipt.created.associations === 1 ? "Supports association" : "Supports associations"}.
          </p>}
          {!canManage && <p>You can view setup progress for this Site.</p>}
          {saved && <p role="status">Progress is saved for this Site.</p>}
          {stage === "environment" ? <>
            {confirmed
              ? <p>The Customer, Site and profile are confirmed for this setup.</p>
              : <>
                {canManage && <p>Confirm this Customer and Site to fix the context for this setup.</p>}
                <fieldset className={styles.profiles} disabled={!canManage || busy || saved || completed || conflict}>
                  <legend>Environment profile</legend>
                  {Object.entries(PROFILES).map(([value, label]) => <label key={value}>
                    <input type="radio" name="environment-profile" value={value} checked={profile === value}
                      onChange={() => setPendingProfile(value)} /> <strong>{label}</strong>
                    <small>{value === "blank" ? "Start with a manual setup." : "Set up a home or lab environment."}</small>
                  </label>)}
                </fieldset>
              </>}
            {editor ? <NameEditor operation={editor} onSave={saveEditor} onCancel={() => {
              setEditor(null);
              heading.current?.focus();
            }} /> : <div className={styles.actions}>
              {hasPermissionForObject("customers.manage", customer.id) && <Button disabled={busy || returning}
                onClick={() => setEditor({ kind: "customer", id: customer.id, name: customer.name })}>Rename Customer</Button>}
              {canManage && <Button disabled={busy || returning} onClick={() => setEditor({ kind: "site", id: site.id, name: site.name })}>Rename Site</Button>}
            </div>}
          </> : stage === "integrations" && (!saved || !canManage)
            ? <OnboardingIntegrations key={`${user.id}:${path}`} customer={customer} site={site} profile={progress.environment_profile}
                canManage={canManage && !saved} blocked={blocked || returning}
                canAdvance={activeStage === "integrations" && !progress.stage_decisions.integrations}
                onBusy={setIntegrationsBusy} onDirty={setIntegrationDirty}
                onDecision={(decision, runId) => change("integrations/decision", decision, runId)} />
            : stage === "discovery_review" && (!saved || !canManage)
              ? <OnboardingDiscoveryReview key={`${user.id}:${path}`} customer={customer} site={site}
                  canManage={canManage && !saved} blocked={blocked || returning}
                  canAdvance={activeStage === "discovery_review" && !progress.stage_decisions.discovery_review}
                  onBusy={setDiscoveryReviewBusy}
                  onDecision={(decision, reviewVersion) => change("discovery-review/decision", decision, reviewVersion)} />
              : stage === "link_services" && (!saved || !canManage)
                ? <OnboardingLinkServices key={`${user.id}:${path}`} path={path} actor={user.id}
                    canManage={canManage && !saved} blocked={blocked || returning}
                    canAdvance={activeStage === "link_services" && !progress.stage_decisions.link_services}
                    onBusy={setLinkServicesBusy}
                    onDecision={(action, acknowledge) => change("link-services/decision", action, acknowledge)} />
                : showingReview && (!saved || !canManage)
                  ? <OnboardingReviewReady key={`${user.id}:${path}`} path={path} decisions={progress.stage_decisions}
                      visits={visitEarlier} blocked={blocked || returning}
                      onKnowledgeGaps={(customerId, siteId) => openConfirmedDestination(customerId, siteId, DASHBOARD_GAPS_HREF)}
                      onReloadProgress={refresh} />
                  : !saved && <p>This setup stage is unavailable.</p>}
          <div className={styles.footer}>
            {canManage && !confirmed && <Button href="/onboarding" disabled={blocked}>Change Site</Button>}
            {visitedStage && <Button onClick={() => returnToCurrentStage()} disabled={blocked} loading={returning}>Return to current stage</Button>}
            {confirmed && !["environment", "integrations", "discovery_review", "link_services", "review_ready"].includes(stage) && <Button onClick={visitEnvironment} disabled={blocked}>Back to Environment</Button>}
            {stage === "integrations" && canVisitCapabilities && <Button onClick={visitCapabilities}>Back to Capabilities</Button>}
            {stage === "discovery_review" && canVisitIntegrations && <Button onClick={visitIntegrations}>Back to Add Integrations</Button>}
            {stage === "link_services" && canVisitDiscoveryReview && <Button onClick={visitDiscoveryReview}>Back to Discovery Review</Button>}
            {showingReview && canVisitLinkServices && <Button onClick={visitLinkServices}>Back to Link Services</Button>}
            {completed ? <Button onClick={finishOrReturn} disabled={blocked || returning}>Return to Dashboard</Button>
              : (!canManage || saved) ? <Button href={authenticatedHome(user)} disabled={Boolean(editor) || busy}>Return to Atlas</Button>
              : <Button onClick={() => change("save")} disabled={blocked || returning}>Save &amp; exit</Button>}
            {stage !== "environment" && stage !== "integrations" && !showingReview && canVisitCapabilities && progress.environment_profile === "homelab"
              && <Button onClick={visitCapabilities}>Open capability catalogue</Button>}
            {canManage && saved && <Button variant="primary" onClick={() => change("resume")} disabled={blocked || returning}>Resume setup</Button>}
            {canManage && !confirmed && !saved && !completed && <Button variant="primary" onClick={() => change("environment")} disabled={blocked || returning}>Confirm Environment</Button>}
            {showingReview && canManage && !saved && !completed && activeStage === "review_ready"
              && <Button variant="primary" onClick={() => change("review-ready/decision")} disabled={blocked || returning}>Continue to Showcase</Button>}
          </div>
        </Section>
      </Surface>
      )}
    </div>
  </Wizard>;
}
