"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { canContinueSetup, dashboardOnboardingEntry, onboardingPath, PROFILES, STAGES } from "../lib/onboarding.mjs";
import { useAuth } from "./auth-context";
import { Button } from "./button";
import { NavigationIcon } from "./navigation-icon.mjs";
import { PageHeader } from "./page-header";
import { Surface } from "./section";
import styles from "./onboarding.module.css";

const request = (path, options) => apiRequest(path, { ...options, omitContext: true, cache: "no-store" });

export function DashboardOnboardingHeader({ customerId, siteId, children }) {
  const { hasPermission } = useAuth();
  const canManageSites = hasPermission("sites.manage");
  const [entry, setEntry] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pair = customerId && siteId ? onboardingPath(customerId, siteId) : null;

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    setEntry(null);
    setError("");
    async function load() {
      const status = pair && await request(pair, { signal }).catch(() => null);
      if (signal.aborted) return;
      const kind = dashboardOnboardingEntry(status);
      if (kind !== "voluntary") {
        setEntry({ kind, href: pair, status });
        return;
      }
      if (!canManageSites) return;
      const options = await request("/onboarding/contexts", { signal }).catch(() => null);
      if (signal.aborted || !Array.isArray(options?.sites) || !Array.isArray(options.customers)) return;
      const resumable = options.sites.filter(({ status }) => canContinueSetup(status));
      if (resumable.length === 1) {
        const site = resumable[0];
        const href = onboardingPath(site.customer_id, site.id);
        const shared = await request(href, { signal }).catch(() => null);
        if (signal.aborted) return;
        if (dashboardOnboardingEntry(shared) === "continue") {
          setEntry({ kind: "continue", href, status: shared, otherSite: true });
          return;
        }
      }
      if (status?.status === "not_started" && status.can_manage && !status.invitation?.dismissed) {
        setEntry({ kind: "start", href: pair, status });
      } else if (options.customers.length || options.can_add_customer) {
        setEntry({ kind: "voluntary" });
      }
    }
    load();
    return () => controller.abort();
  }, [canManageSites, pair]);

  async function dismiss() {
    setBusy(true);
    setError("");
    try {
      await request(`${pair}/invitation/dismiss`, { method: "POST" });
      setEntry(entry.status.can_manage || canManageSites ? { kind: "voluntary" } : null);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  return <>
    <PageHeader title="Dashboard" description="Your environment, built from recorded knowledge."
      actions={entry?.kind === "completed" && entry.status.can_manage
        ? <Button href={entry.href}><NavigationIcon name="compass" />Guided setup</Button> : undefined} />
    {children}
    <OnboardingEntry entry={entry} pair={pair} error={error} busy={busy} dismiss={dismiss} />
  </>;
}

function OnboardingEntry({ entry, pair, error, busy, dismiss }) {
  if (!entry || entry.kind === "completed") return null;
  if (entry.kind === "voluntary") return <section className={styles.dashboardEntry} aria-label="Guided setup">
    <Button href={entry.href ?? "/onboarding"} variant="quiet">Guided setup</Button>
  </section>;
  if (entry.kind === "continue") {
    const { progress, site } = entry.status;
    const profile = PROFILES[progress?.environment_profile ?? progress?.draft_profile];
    const index = STAGES.findIndex(([key]) => key === progress?.current_stage);
    return <Surface className={styles.invitation} role="region" aria-label="Guided setup">
      <div>
        <h2>{profile ? `Continue your ${profile} setup` : "Continue your guided setup"}</h2>
        {index >= 0 && <p>Step {index + 1} of {STAGES.length} · {STAGES[index][1]}</p>}
        {entry.otherSite && <p>{site.name}</p>}
      </div>
      <div className={styles.actions}>
        <Button href={entry.href} variant="primary">Resume</Button>
        <Button href="/onboarding" variant="quiet">Guided setup</Button>
      </div>
    </Surface>;
  }
  if (entry.kind === "start") return <section className={styles.dashboardEntry} aria-label="Guided setup">
    <Button href={entry.href}>Start guided setup</Button>
    <Button href="/onboarding" variant="quiet">Guided setup</Button>
  </section>;

  return <Surface className={styles.invitation} role="region" aria-label="Optional guided setup">
    <div>
      <h2>Set up Atlas your way</h2>
      <p>{entry.status.can_manage
        ? "Choose a setup profile for this Site, or start recording your environment manually."
        : "A Site manager can run guided setup for this Site."}</p>
      {error && <p className="error-banner" role="alert">{error}</p>}
    </div>
    <div className={styles.actions}>
      {entry.status.can_manage && <Button href={pair} variant="primary">Start guided setup</Button>}
      <Button loading={busy} onClick={dismiss}>{entry.status.can_manage ? "Set up manually" : "Dismiss invitation"}</Button>
    </div>
  </Surface>;
}
