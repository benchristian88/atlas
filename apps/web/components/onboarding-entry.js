"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { canContinueSetup, dashboardOnboardingEntry, onboardingPath } from "../lib/onboarding.mjs";
import { useAuth } from "./auth-context";
import { Button } from "./button";
import { Surface } from "./section";
import styles from "./onboarding.module.css";

export function OnboardingEntry({ customerId, siteId }) {
  const { hasPermission } = useAuth();
  const canManageSites = hasPermission("sites.manage");
  const [entry, setEntry] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pair = customerId && siteId ? onboardingPath(customerId, siteId) : null;

  useEffect(() => {
    setEntry(null);
    setError("");
    let active = true;
    async function load() {
      if (pair) {
        const status = await apiRequest(pair, { omitContext: true }).catch(() => null);
        if (!active) return;
        const kind = dashboardOnboardingEntry(status);
        if (kind !== "voluntary") {
          setEntry({ kind, href: pair, canManage: status.can_manage });
          return;
        }
      }
      if (!canManageSites) return;
      const options = await apiRequest("/onboarding/contexts", { omitContext: true }).catch(() => null);
      if (!active || !Array.isArray(options?.sites) || !Array.isArray(options.customers)) return;
      const resumable = options.sites.filter(({ status }) => canContinueSetup(status));
      if (resumable.length === 1) {
        const site = resumable[0];
        setEntry({ kind: "continue", href: onboardingPath(site.customer_id, site.id), name: site.name });
      } else if (options.customers.length || options.can_add_customer) {
        setEntry({ kind: "voluntary" });
      }
    }
    load();
    return () => { active = false; };
  }, [canManageSites, pair]);

  async function dismiss() {
    setBusy(true);
    setError("");
    try {
      await apiRequest(`${pair}/invitation/dismiss`, { method: "POST", omitContext: true });
      setEntry(entry.canManage || canManageSites ? { kind: "voluntary" } : null);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  if (!entry) return null;
  if (entry.kind !== "invitation") return <div className={styles.actions}>
    {entry.kind === "continue" && <Button href={entry.href}>
      {entry.name ? `Continue setup for ${entry.name}` : "Continue setup"}
    </Button>}
    <Button href="/onboarding" variant="quiet">Guided setup</Button>
  </div>;

  return <Surface className={styles.invitation} role="region" aria-label="Optional guided setup">
    <div>
      <h2>Set up Atlas your way</h2>
      <p>{entry.canManage
        ? "Choose a setup profile for this Site, or start recording your environment manually."
        : "A Site manager can run guided setup for this Site."}</p>
      {error && <p className="error-banner" role="alert">{error}</p>}
    </div>
    <div className={styles.actions}>
      {entry.canManage && <Button href={pair} variant="primary">Start guided setup</Button>}
      <Button loading={busy} onClick={dismiss}>{entry.canManage ? "Set up manually" : "Dismiss invitation"}</Button>
    </div>
  </Surface>;
}
