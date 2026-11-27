"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiRequest } from "../lib/api";
import { canContinueSetup, initialEnvironment, onboardingPath, PROFILES, STAGES } from "../lib/onboarding.mjs";
import { pendingApplyKey, readPendingApply } from "../lib/onboarding-capabilities.mjs";
import { authenticatedHome, useAuth } from "./auth-context";
import { Button } from "./button";
import { OnboardingCapabilities } from "./onboarding-capabilities";
import { OnboardingDiscoveryReview } from "./onboarding-discovery-review";
import { OnboardingIntegrations } from "./onboarding-integrations";
import { OnboardingLinkServices } from "./onboarding-link-services";
import { PageHeader } from "./page-header";
import { Section, Surface } from "./section";
import styles from "./onboarding.module.css";

const request = (path, options) => apiRequest(path, { ...options, omitContext: true });
const write = (path, method, values) => request(path, { method, body: JSON.stringify(values) });
const decisionLabels = { completed: "Completed", skipped: "Skipped", attention: "Needs attention" };

function Wizard({ stage, decisions = {}, onEnvironment, onCapabilities, onIntegrations, onDiscoveryReview, onLinkServices, children }) {
  return <>
    <PageHeader title="Guided setup" description="Set up one Site at a time." />
    <div className={styles.layout}>
      <nav aria-label="Setup stages" className={styles.rail}>
        <ol>
          {STAGES.map(([key, title], index) => {
            const label = decisionLabels[decisions[key]]
              || (stage === key && ["environment", "capabilities", "integrations", "discovery_review", "link_services"].includes(key) ? "In progress" : "Pending");
            const openStage = { environment: onEnvironment, capabilities: onCapabilities, integrations: onIntegrations,
              discovery_review: onDiscoveryReview, link_services: onLinkServices }[key];
            return <li key={key} aria-current={stage === key ? "step" : undefined}>
              <span className={styles.stepNumber} aria-hidden="true">{index + 1}</span>
              <div>
                {openStage
                  ? <button className="text-button" type="button" onClick={openStage}>{title}</button>
                  : <strong>{title}</strong>}
                <small>{label}</small>
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
                {canContinueSetup(status) ? `${name} · Setup started` : name}
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
  const router = useRouter();
  const path = onboardingPath(customerId, siteId);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const [pendingProfile, setPendingProfile] = useState(null);
  const [revisiting, setRevisiting] = useState(false);
  const [visitingCapabilities, setVisitingCapabilities] = useState(false);
  const [capabilitiesBusy, setCapabilitiesBusy] = useState(false);
  const [visitingIntegrations, setVisitingIntegrations] = useState(false);
  const [integrationsBusy, setIntegrationsBusy] = useState(false);
  const [integrationDirty, setIntegrationDirty] = useState(false);
  const [visitingDiscoveryReview, setVisitingDiscoveryReview] = useState(false);
  const [discoveryReviewBusy, setDiscoveryReviewBusy] = useState(false);
  const [visitingLinkServices, setVisitingLinkServices] = useState(false);
  const [linkServicesBusy, setLinkServicesBusy] = useState(false);
  const [receipt, setReceipt] = useState(null);
  const [editor, setEditor] = useState(null);
  const heading = useRef(null);
  const capabilitiesHeading = useRef(null);
  const progressWrite = useRef(false);
  const saved = data?.status === "saved";
  const pendingKey = pendingApplyKey(user.id, path);
  const pending = data?.progress?.environment_profile === "homelab" && Boolean(readPendingApply(pendingKey));
  const activeStage = data?.progress?.current_stage || "environment";
  const showCapabilities = data?.progress?.environment_profile
    && (pending || ((!saved || !data.can_manage) && (activeStage === "capabilities" || visitingCapabilities)));
  const headingTarget = data && (revisiting ? "environment" : showCapabilities ? "capabilities"
    : visitingIntegrations ? "integrations" : visitingDiscoveryReview ? "discovery_review"
      : visitingLinkServices ? "link_services" : activeStage);
  const profile = pendingProfile ?? data?.progress?.draft_profile ?? "homelab";

  useEffect(() => {
    let active = true;
    request(path).then((result) => {
      if (!active) return;
      setData(result);
      if (readPendingApply(pendingKey)) setVisitingCapabilities(true);
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
    const target = showCapabilities && !revisiting ? capabilitiesHeading : heading;
    target.current?.focus();
  }, [headingTarget, loading, saved, showCapabilities, revisiting, receipt]);

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

  function leaveIntegration(visit) {
    if (!confirmLeavingIntegration()) return;
    setIntegrationDirty(false);
    visit();
  }

  function refresh() {
    if (!confirmLeavingIntegration()) return;
    setIntegrationDirty(false);
    setLoading(true);
    setError(null);
    setEditor(null);
    setRevisiting(false);
    setVisitingCapabilities(false);
    setVisitingIntegrations(false);
    setVisitingDiscoveryReview(false);
    setVisitingLinkServices(false);
    setPendingProfile(null);
    setReload((value) => value + 1);
  }

  async function change(action, decision, decisionVersion) {
    if (!data.can_manage || progressWrite.current || !confirmLeavingIntegration()) return;
    progressWrite.current = true;
    setBusy(true);
    setError(null);
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
      setIntegrationDirty(false);
      setPendingProfile(null);
      setData((old) => ({ ...old, progress: updated, status: updated.status }));
      if (action === "save") router.replace(authenticatedHome(user));
      return { ok: true };
    } catch (requestError) {
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
    setData((old) => ({ ...old, progress, status: progress.status, can_manage: canManage ?? old.can_manage }));
    if (!keepCapabilities || progress.current_stage !== "capabilities") setVisitingCapabilities(keepCapabilities);
  }

  if (loading) return <p role="status">Loading setup progress…</p>;
  if (!data) return <Unavailable error={error} retry={refresh} recovery />;
  const { customer, site, progress, can_manage: canManage } = data;
  const stage = headingTarget;
  const confirmed = Boolean(progress?.environment_profile);
  const completed = data.status === "completed";
  const conflict = error?.status === 409;
  const blocked = busy || capabilitiesBusy || integrationsBusy || discoveryReviewBusy || linkServicesBusy || Boolean(editor) || conflict;
  const stageTitle = STAGES.find(([key]) => key === stage)?.[1] || "Setup progress";

  const canVisitCapabilities = confirmed && progress.stage_decisions.capabilities && canManage && !saved && !blocked && stage !== "capabilities";
  const visitCapabilities = () => leaveIntegration(() => {
    setReceipt(null);
    setRevisiting(false);
    setVisitingCapabilities(true);
  });
  const visitEnvironment = () => leaveIntegration(() => setRevisiting(true));
  const canVisitIntegrations = confirmed && progress.stage_decisions.integrations && !saved && !blocked && !pending
    && stage !== "integrations" && !showCapabilities;
  const visitIntegrations = () => {
    setRevisiting(false);
    setVisitingLinkServices(false);
    setVisitingIntegrations(true);
  };
  const visitDiscoveryReview = () => leaveIntegration(() => {
    setRevisiting(false);
    setVisitingIntegrations(false);
    setVisitingLinkServices(false);
    setVisitingDiscoveryReview(true);
  });
  const visitLinkServices = () => leaveIntegration(() => {
    setRevisiting(false);
    setVisitingIntegrations(false);
    setVisitingDiscoveryReview(false);
    setVisitingLinkServices(true);
  });
  const canVisitDiscoveryReview = confirmed && progress.stage_decisions.discovery_review && !saved && !blocked && !pending
    && stage !== "discovery_review" && !showCapabilities;
  const canVisitLinkServices = confirmed && progress.stage_decisions.link_services && !saved && !blocked && !pending
    && stage !== "link_services" && !showCapabilities;

  return <Wizard stage={stage} decisions={progress?.stage_decisions}
    onEnvironment={confirmed && stage !== "environment" && !blocked && !pending ? visitEnvironment : undefined}
    onCapabilities={canVisitCapabilities && (stage === "integrations" || progress.environment_profile === "homelab") ? visitCapabilities : undefined}
    onIntegrations={canVisitIntegrations ? visitIntegrations : undefined}
    onDiscoveryReview={canVisitDiscoveryReview ? visitDiscoveryReview : undefined}
    onLinkServices={canVisitLinkServices ? visitLinkServices : undefined}>
    <div className={showCapabilities && !revisiting ? styles.capabilitiesSession
      : stage === "link_services" ? `${styles.session} ${styles.linkSession}` : styles.session}>
      {showCapabilities && <Surface className={styles.panel} hidden={revisiting}>
        <Section title="Capabilities" headingRef={capabilitiesHeading}>
          <OnboardingCapabilities path={path} pendingKey={pendingKey} progress={progress} customer={customer} site={site}
            visible={!revisiting} headingRef={capabilitiesHeading} home={authenticatedHome(user)}
            onEnvironment={() => setRevisiting(true)} onReturn={() => setVisitingCapabilities(false)}
            onProgress={adoptProgress} onExit={() => router.replace(authenticatedHome(user))}
            onApplied={(outcome, latest, canManage) => {
              setReceipt(outcome);
              adoptProgress(latest, false, canManage);
            }}
            onBusy={setCapabilitiesBusy} />
        </Section>
      </Surface>}
      {(!showCapabilities || revisiting) && <>
      <Surface className={styles.summary}>
        <Section title="Setup context">
          <dl>
            <div><dt>Customer</dt><dd>{customer.name}</dd></div>
            <div><dt>Site</dt><dd>{site.name}</dd></div>
            {confirmed && <div><dt>Profile</dt><dd>{PROFILES[progress.environment_profile]}</dd></div>}
          </dl>
        </Section>
      </Surface>
      <Surface className={`${styles.panel} ${styles.stagePanel}`}>
        <Section title={stageTitle} headingRef={heading}>
          <Feedback error={error} retry={conflict ? refresh : undefined} busy={busy} />
          {receipt && <p role="status" className="success-banner">
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
              {hasPermissionForObject("customers.manage", customer.id) && <Button disabled={busy}
                onClick={() => setEditor({ kind: "customer", id: customer.id, name: customer.name })}>Rename Customer</Button>}
              {canManage && <Button disabled={busy} onClick={() => setEditor({ kind: "site", id: site.id, name: site.name })}>Rename Site</Button>}
            </div>}
          </> : stage === "integrations" && (!saved || !canManage)
            ? <OnboardingIntegrations key={`${user.id}:${path}`} customer={customer} site={site} profile={progress.environment_profile}
                canManage={canManage && !saved && !completed} blocked={blocked}
                canAdvance={activeStage === "integrations" && !progress.stage_decisions.integrations}
                onBusy={setIntegrationsBusy} onDirty={setIntegrationDirty}
                onDecision={(decision, runId) => change("integrations/decision", decision, runId)} />
            : stage === "discovery_review" && (!saved || !canManage)
              ? <OnboardingDiscoveryReview key={`${user.id}:${path}`} customer={customer} site={site}
                  canManage={canManage && !saved && !completed} blocked={blocked}
                  canAdvance={activeStage === "discovery_review" && !progress.stage_decisions.discovery_review}
                  onBusy={setDiscoveryReviewBusy}
                  onDecision={(decision, reviewVersion) => change("discovery-review/decision", decision, reviewVersion)} />
              : stage === "link_services" && (!saved || !canManage)
                ? <OnboardingLinkServices key={`${user.id}:${path}`} path={path} actor={user.id}
                    canManage={canManage && !saved && !completed} blocked={blocked}
                    canAdvance={activeStage === "link_services" && !progress.stage_decisions.link_services}
                    onBusy={setLinkServicesBusy}
                    onDecision={(action, acknowledge) => change("link-services/decision", action, acknowledge)} />
                : !saved && <p>{completed ? "Setup is complete." : "This setup stage is pending in this preview."}</p>}
          <div className={styles.footer}>
            {canManage && !confirmed && <Button href="/onboarding" disabled={blocked}>Change Site</Button>}
            {revisiting && <Button onClick={() => setRevisiting(false)} disabled={blocked}>Return to current stage</Button>}
            {!revisiting && confirmed && !["environment", "integrations", "discovery_review", "link_services"].includes(stage) && <Button onClick={visitEnvironment} disabled={blocked}>Back to Environment</Button>}
            {stage === "integrations" && canVisitCapabilities && <Button onClick={visitCapabilities}>Back to Capabilities</Button>}
            {stage === "integrations" && visitingIntegrations && <Button onClick={() => leaveIntegration(() => setVisitingIntegrations(false))} disabled={blocked}>Return to current stage</Button>}
            {stage === "discovery_review" && canVisitIntegrations && <Button onClick={visitIntegrations}>Back to Add Integrations</Button>}
            {stage === "discovery_review" && visitingDiscoveryReview && <Button onClick={() => setVisitingDiscoveryReview(false)} disabled={blocked}>Return to current stage</Button>}
            {stage === "link_services" && canVisitDiscoveryReview && <Button onClick={visitDiscoveryReview}>Back to Discovery Review</Button>}
            {stage === "link_services" && visitingLinkServices && <Button onClick={() => setVisitingLinkServices(false)} disabled={blocked}>Return to current stage</Button>}
            {(!canManage || completed || saved) ? <Button href={authenticatedHome(user)} disabled={Boolean(editor) || busy}>Return to Atlas</Button>
              : !showCapabilities && <Button onClick={() => change("save")} disabled={blocked}>Save &amp; exit</Button>}
            {stage !== "environment" && stage !== "integrations" && canVisitCapabilities && progress.environment_profile === "homelab"
              && <Button onClick={visitCapabilities}>Open capability catalogue</Button>}
            {canManage && saved && <Button variant="primary" onClick={() => change("resume")} disabled={blocked}>Resume setup</Button>}
            {canManage && !confirmed && !saved && !completed && <Button variant="primary" onClick={() => change("environment")} disabled={blocked}>Confirm Environment</Button>}
          </div>
        </Section>
      </Surface>
      </>}
    </div>
  </Wizard>;
}
