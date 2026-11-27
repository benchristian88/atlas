"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { showcaseDestinations } from "../lib/onboarding-showcase.mjs";
import { useAuth } from "./auth-context";
import { Button } from "./button";
import { NavigationIcon } from "./navigation-icon.mjs";
import { Section, Surface } from "./section";
import styles from "./onboarding-showcase.module.css";

const format = value => value.toLocaleString();
const restricted = "Restricted by your permissions.";

function Metric({ label, value, icon }) {
  return <div className={styles.metric}>
    <dt><NavigationIcon name={icon} />{label}</dt>
    <dd className={value == null ? styles.restricted : undefined}>{value == null ? "Restricted" : format(value)}</dd>
  </div>;
}

function Capabilities({ functions, services, servicesWithoutFunctions }) {
  return <Section title="Your capabilities" heading="h3" className={styles.section}
    description="Business Functions and the Services recorded for this Customer and Site.">
    <dl className={styles.metrics}>
      <Metric label="Business Functions" value={functions?.total} icon="business-functions" />
      <Metric label="Services" value={services} icon="services" />
    </dl>
    {servicesWithoutFunctions > 0 && <p className={styles.note}>
      {format(servicesWithoutFunctions)} {servicesWithoutFunctions === 1 ? "Service has" : "Services have"} no current association with a visible Business Function.
    </p>}
    {functions?.total > 0 ? <>
      <ul className={styles.functions} aria-label="Business Functions and associated Services">
        {functions.items.map(item => <li key={item.id}>
          <h4>{item.name}</h4>
          {item.services == null ? <p>{restricted}</p> : item.services.total === 0 ? <p>No visible Services linked.</p> : <>
            <ul>{item.services.examples.map(service => <li key={service.id}>{service.name}</li>)}</ul>
            {item.services.total > item.services.examples.length &&
              <p>+{format(item.services.total - item.services.examples.length)} more linked Services</p>}
          </>}
        </li>)}
      </ul>
      {functions.total > functions.items.length && <p className={styles.note}>+{format(functions.total - functions.items.length)} more Business Functions</p>}
    </> : functions && <p className={styles.note}>No Business Functions are recorded in your visible scope yet.</p>}
  </Section>;
}

function Infrastructure({ assets, networks, integrations }) {
  const distribution = assets?.by_type ?? [];
  const bars = assets?.other_assets > 0
    ? [...distribution, { id: "other", name: "Other recorded types", count: assets.other_assets }] : distribution;
  return <Section title="Your infrastructure" heading="h3" className={styles.section}
    description="The current inventory and Integration activity in your visible scope.">
    <dl className={styles.metrics}>
      <Metric label="Non-retired Assets" value={assets?.total} icon="assets" />
      <Metric label="Recorded Networks" value={networks} icon="networks" />
      <Metric label="Configured Integrations" value={integrations?.total} icon="integrations" />
    </dl>
    <div className={styles.infrastructure}>
      <div>
        <h4>Assets by type</h4>
        {assets === null ? <p>{restricted}</p> : bars.length === 0 ? <p>No non-retired Assets recorded at this Site yet.</p> :
          <ul className={styles.bars}>
            {bars.map(({ id, name, count }) => <li key={id}>
              <div><span>{name}</span><strong>{format(count)}</strong></div>
              <span className={styles.barTrack} aria-hidden="true"><span style={{ width: `${count / assets.total * 100}%` }} /></span>
            </li>)}
          </ul>}
      </div>
      <div>
        <h4>Integration activity</h4>
        {integrations === null ? <p>{restricted}</p> : integrations.total === 0 ? <p>No configured Integrations at this Site yet.</p> :
          <dl className={styles.integrationStatus}>
            <div><dt>Enabled</dt><dd>{format(integrations.enabled)}</dd></div>
            <div><dt>Disabled</dt><dd>{format(integrations.disabled)}</dd></div>
            <div><dt>Discovery runs queued or running</dt><dd>{format(integrations.active_runs)}</dd></div>
          </dl>}
      </div>
    </div>
  </Section>;
}

const layers = [
  ["business-functions", "Business Functions", "What matters"],
  ["services", "Services", "What delivers it"],
  ["assets", "Assets and Networks", "What supports it"],
];

function Connections({ mappings, assetRelationships, networkMemberships }) {
  return <Section title="Your connected knowledge" heading="h3" className={styles.section}>
    <figure className={styles.layers}>
      <figcaption>How Atlas organises knowledge</figcaption>
      <ol>{layers.map(([icon, title, description]) => <li key={icon}>
        <NavigationIcon name={icon} /><div><strong>{title}</strong><span>{description}</span></div>
      </li>)}</ol>
    </figure>
    <h4>Recorded connections at this Site</h4>
    <dl className={styles.connections}>
      <Metric label="Services linked to Assets" value={mappings?.linked} icon="services" />
      <Metric label="Services with no Site mapping" value={mappings?.unlinked} icon="services" />
      <Metric label="Service-to-Asset mappings" value={mappings?.mappings} icon="knowledge-graph" />
      <Metric label="Relationships between Assets" value={assetRelationships} icon="topology" />
      <Metric label="Interface memberships in Networks" value={networkMemberships} icon="networks" />
    </dl>
    {mappings?.unavailable > 0 && <p className={styles.note}>
      Mapping status is restricted for {format(mappings.unavailable)} of the visible Services.
    </p>}
  </Section>;
}

const features = [
  ["graph", "Knowledge Graph", "knowledge-graph", "Explore how your recorded Business Functions, Services and infrastructure relate.", "Open Knowledge Graph"],
  ["topology", "Topology", "topology", "Explore your recorded infrastructure and network connectivity.", "Open Topology"],
  ["analysis", "Impact and dependency analysis", "discovery", "Preview the potential consequences of a failure using recorded dependency knowledge.", "Preview dependency analysis"],
];

function Explore({ destinations, blocked, onExplore, completed }) {
  return <Section title="Explore Atlas" heading="h3" className={styles.section}
    description={completed ? undefined : "You can explore now and return to guided setup when you’re ready to finish."}>
    <div className={styles.explore}>
      {features.map(([key, title, icon, description, action]) => <Surface className={styles.feature} key={key}>
        <span className={styles.icon}><NavigationIcon name={icon} /></span>
        <h4>{title}</h4>
        <p>{description}</p>
        {destinations[key] && <Button onClick={() => onExplore(destinations[key])} disabled={blocked}>{action}</Button>}
      </Surface>)}
    </div>
  </Section>;
}

export function OnboardingShowcase({ path, customer, site, profile, completed, headingRef, blocked, onExplore, children }) {
  const { hasPermissionInContext } = useAuth();
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    apiRequest(`${path}/showcase`, { signal, omitContext: true, cache: "no-store" }).then(value => {
      if (!signal.aborted) setData(value);
    }).catch(() => {
      if (!signal.aborted) setFailed(true);
    });
    return () => controller.abort();
  }, [path, attempt]);

  const hasRecords = [data?.business_functions?.total, data?.services, data?.assets?.total, data?.networks].some(count => count > 0);
  const destinations = showcaseDestinations(data, permission => hasPermissionInContext(permission, customer.id, site.id));
  return <div className={styles.showcase}>
    <header className={styles.hero}>
      <div>
        <h2 className="eyebrow" ref={headingRef} tabIndex={-1}>Showcase</h2>
        <p className={styles.title}>Your environment, connected.</p>
        <p>{profile === "homelab" && hasRecords
          ? "You’ve started building a connected view of your homelab, from the capabilities that matter to the infrastructure that supports them."
          : "You’ve laid the groundwork for a shared view of your environment. Start with the knowledge you have and build on it over time."}</p>
      </div>
    </header>
    {data ? <div className={styles.story}>
      <p className={styles.scopeNote}>This view includes current records you can access, including knowledge recorded outside guided setup.</p>
      <Capabilities functions={data.business_functions} services={data.services} servicesWithoutFunctions={data.services_without_functions} />
      <Infrastructure assets={data.assets} networks={data.networks} integrations={data.integrations} />
      <Connections mappings={data.mappings} assetRelationships={data.asset_relationships} networkMemberships={data.network_memberships} />
    </div> : failed ? <div className="error-banner" role="alert">
      <p>Current environment information is temporarily unavailable.</p>
      <Button onClick={() => { setFailed(false); setAttempt(value => value + 1); }} disabled={blocked}>Retry Showcase</Button>
    </div> : <p role="status">Loading current environment information…</p>}
    <Explore destinations={destinations} blocked={blocked} onExplore={onExplore} completed={completed} />
    <Section title="Looking ahead" heading="h3" className={`${styles.section} ${styles.lookingAhead}`}>
      <p>Add detail and record new relationships as your environment changes.</p>
      {data?.required_gaps > 0 && <p>Review &amp; Ready has more on the {format(data.required_gaps)} visible
        required or conditional Knowledge {data.required_gaps === 1 ? "Gap" : "Gaps"} still open or deferred.</p>}
      {children}
    </Section>
  </div>;
}
