import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { connectorActions, connectorState, filterConnectors, integrationTab, formatIntegrationTime, runtimeErrorMessage, runtimeOperations, readOfficialCatalogueStatus, officialConnectorMetadata, formatOfficialCatalogueTime, officialCatalogueBlocked, officialCatalogueSummary, officialCatalogueDiagnostic, officialCatalogueRequestError, orderConnectorCards, reconcileConnectorCatalogue } from "../lib/integrations.mjs";
import { resolveStatus } from "../lib/status.mjs";
import { loadComponent } from "./helpers/components.mjs";
const components = loadComponent(new URL("../components/integration-panels.js", import.meta.url));
const { userHasGlobalPermission } = loadComponent(new URL("../components/auth-context.js", import.meta.url));
const render = (name, props) => renderToStaticMarkup(React.createElement(components[name], props));
const digest = "a".repeat(64);

test("unreleased catalogue metadata has truthful distinct state and searchable backend fields", () => {
  const entry = { connector_id: "atlas.proxmox", name: "Proxmox VE", description: "Compute inventory", publisher: "Atlas", package_available: false, verification_status: "metadata_only", state: "unavailable" };
  assert.equal(connectorState(entry), "bundle_not_released");
  assert.equal(filterConnectors([entry], "ATLAS.PROXMOX").length, 1);
  assert.equal(filterConnectors([entry], "Atlas", "bundle_not_released").length, 1);
  assert.equal(filterConnectors([entry], "Docker").length, 0);
  assert.equal(filterConnectors([entry], "", "installed").length, 0);
  assert.equal(connectorState({ state: "runtime_update_required" }), "runtime_update_required");
  for (const [state, tone] of [["healthy", "success"], ["installable", "info"], ["installed", "success"], ["runtime_update_required", "warning"], ["incompatible", "danger"], ["verification_failed", "danger"], ["bundle_not_released", "neutral"]]) assert.equal(resolveStatus(state).tone, tone);
});

test("package actions require a global management grant, explicit backend support and verified immutable identity", () => {
  const entry = { connector_id: "atlas.proxmox", version: "1.0.0", digest, bundle_digest: `sha256:${digest}`, package_available: true, verification_status: "verified", state: "installable", supported_actions: ["install"] };
  assert.deepEqual(connectorActions(entry, false), []);
  assert.deepEqual(connectorActions({ ...entry, supported_actions: [] }, true), []);
  for (const patch of [{ verification_status: "metadata_only" }, { package_available: false }, { digest: "../unsafe" }, { version: null }, { state: "runtime_update_required" }, { state: "incompatible" }, { state: "verification_failed" }]) assert.deepEqual(connectorActions({ ...entry, ...patch }, true), []);
  assert.deepEqual(connectorActions(entry, true)[0], { action: "install", label: "Install Connector", method: "POST", path: "/integration-catalogue/atlas.proxmox/install", body: { version: "1.0.0", digest } });
  const rollback = { ...entry, state: "installed", installed_version: "2.0.0", supported_actions: ["rollback", "remove"], rollback_version: "1.0.0", rollback_digest: "b".repeat(64) };
  assert.equal(connectorActions(rollback, true)[0].body.digest, "b".repeat(64));
  assert.equal(connectorActions({ ...rollback, rollback_digest: null }, true).length, 1);
  assert.equal(connectorActions(rollback, true)[1].method, "DELETE");
});

test("runtime view is hidden without the global view grant and invalid query tabs fall back", () => {
  assert.equal(integrationTab("catalogue", false), "catalogue");
  assert.equal(integrationTab("runtime", false), "configured");
  assert.equal(integrationTab("runtime", true), "runtime");
  assert.equal(integrationTab("<script>", true), "configured");
  assert.equal(formatIntegrationTime("invalid"), "Not checked");
});

test("catalogue cards render real publisher/version/status without Configure or unsupported package actions", () => {
  const entry = { connector_id: "atlas.docker", name: "Docker + Compose", description: "Hosts and workloads", publisher: "Atlas", trust_tier: "atlas_official", version: null, package_available: false, verification_status: "metadata_only", state: "unavailable", message: "Executable bundle has not been released.", supported_actions: [] };
  const html = render("ConnectorCard", { entry, canManage: true });
  for (const value of ["Docker + Compose", "Atlas official", "Not released", "Bundle not released", "Catalogue metadata verified", "Executable bundle not released", "entity-connector"]) assert.match(html, new RegExp(value.replace(/[+]/g, "\\+")));
  assert.doesNotMatch(html, /Configure|Install Connector|Remove package|<button/);
  const installed = render("ConnectorCard", { entry: { ...entry, version: "2.0.0", installed_version: "1.0.0", state: "installed", package_available: true, verification_status: "verified", supported_actions: ["remove"] }, canManage: false });
  assert.match(installed, /1\.0\.0 installed/);
  assert.doesNotMatch(installed, /Remove package/);
});

test("runtime panels expose safe baseline data, unavailable isolation and semantic health", () => {
  const html = render("RuntimePanel", { runtime: { status: "unavailable", runtime_version: "0.1.0", protocol_version: "1", baseline_id: "atlas-ansible-v1", baseline_digest: digest, dependency_lock_digest: "b".repeat(64), packaging_mode: "systemd", ansible_core_version: "2.19.0", ansible_runner_version: "2.4.1", installed_connector_count: 0, last_error: "runtime_unavailable" } });
  for (const value of ["Runtime health", "Unavailable", "Native / systemd", "2.19.0", "2.4.1", "Baseline digest", "Dependency lock digest", "Technical details", "Accepted Atlas knowledge remains available", "Atlas could not reach the local runtime"]) assert.ok(html.includes(value), value);
  assert.doesNotMatch(html, /password|secret|token|localhost|\/var\//);
  assert.match(render("RuntimePanel", { runtime: null }), /Runtime information unavailable/);
  assert.deepEqual(runtimeOperations({ operations: ["health", "package_activation"] }), ["health", "package_activation"]);
  assert.deepEqual(runtimeOperations(null), []);
  assert.doesNotMatch(runtimeErrorMessage("/unsafe/path token=secret"), /unsafe|token|secret/);
  assert.match(runtimeErrorMessage("runtime_baseline_mismatch"), /approved baseline/);
});

const officialDigest = "55533ca67e7e9a14f82961e0a8c34ad78e2596049b3db02fde787494e3975afd";
const confirmed = "2026-10-25T22:20:00Z";
const official = (patch = {}) => readOfficialCatalogueStatus({ trusted_remote_available: true, refresh_state: "idle", sequence: 1, schema_version: "1.0", content_digest: officialDigest, accepted_at: confirmed, last_attempt_at: confirmed, last_confirmed_current_at: confirmed, entries: [{ connector_id: "proxmox", version: "0.2.0", status: "active", package_available: false, supported_actions: [], manifest: { display: { name: "Proxmox VE", description: "Official inventory metadata", category: "virtualization" }, publisher: { name: "Atlas Impact" }, licensing: { licence: "Apache-2.0" } } }], ...patch });

test("official never-checked and historical acceptance are distinct from current-source confirmation", () => {
  const never = readOfficialCatalogueStatus({ trusted_remote_available: false, refresh_state: "idle", entries: [] });
  assert.match(officialCatalogueSummary(never), /not yet been checked/);
  const html = render("OfficialCataloguePanel", { status: official(), canManage: true });
  for (const text of ["Sequence 1", "1.0", officialDigest, formatOfficialCatalogueTime(confirmed), "Past confirmation does not establish", "Previously".toLowerCase(), ]) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /up.to.date|source is current/i);
  const restored = render("OfficialCataloguePanel", { status: official({ last_confirmed_current_at: null }) });
  assert.match(restored, /Last confirmed: Not recorded/);
  assert.match(restored, /previously accepted/);
});

test("official panel reports accepted, unchanged, pending, cooldown and failed results", () => {
  for (const [result, message] of [["accepted", "Official catalogue verified and accepted."], ["unchanged", "Official catalogue verified; the accepted catalogue is unchanged."]]) {
    const html = render("OfficialCataloguePanel", { status: official(), feedback: { result, message } });
    assert.ok(html.includes(message)); assert.match(html, /role="status"/); assert.doesNotMatch(html, /role="alert"/);
  }
  const pending = render("OfficialCataloguePanel", { status: official(), canManage: true, refreshing: true });
  assert.match(pending, /aria-busy="true"/); assert.match(pending, /check is in progress/); assert.match(pending, /disabled=""/);
  const inProgress = official({ refresh_state: "in_progress" });
  assert.equal(officialCatalogueBlocked(inProgress), true);
  const next = "2099-01-01T00:00:00Z";
  const cooldown = official({ next_attempt_at: next });
  assert.equal(officialCatalogueBlocked(cooldown), true);
  assert.equal(officialCatalogueBlocked(cooldown, Date.parse(next) + 1), false);
  assert.match(render("OfficialCataloguePanel", { status: cooldown, canManage: true }), /Next permitted check:/);
  for (const code of ["source_rate_limited", "catalogue_persistence_failed", "unknown-internal-secret"]) {
    const status = official({ refresh_state: "failed", last_error_code: code });
    const html = render("OfficialCataloguePanel", { status, canManage: true, feedback: { result: "failed", message: officialCatalogueDiagnostic(status) } });
    assert.match(html, /role="alert"/); assert.match(html, /Sequence 1/);
    assert.match(render("ConnectorCard", { entry: reconcileConnectorCatalogue([], status)[0] }), /Proxmox VE/);
    assert.equal(status.last_confirmed_current_at, confirmed);
    assert.doesNotMatch(html, /unknown-internal-secret/);
  }
});

test("official API errors are bounded and distinct from verification failures", () => {
  for (const [status, text] of [[401, /session has expired/], [403, /permission/], [503, /does not establish a verification failure/]]) {
    const message = officialCatalogueRequestError({ status, message: "Traceback /var/private token=private https://signed.invalid" });
    assert.match(message, text); assert.doesNotMatch(message, /Traceback|private|signed/);
    const html = render("OfficialCataloguePanel", { status: official(), error: message, canManage: true });
    assert.match(html, /Sequence 1/); assert.match(html, /role="alert"/);
    assert.match(render("ConnectorCard", { entry: reconcileConnectorCatalogue([], official())[0] }), /Proxmox VE/);
  }
  assert.match(officialCatalogueDiagnostic({ source_conflict: true }), /conflicts with retained/);
});

test("official projection tolerates optional metadata but rejects malformed status without conferring trust", () => {
  for (const value of [null, [], {}, { trusted_remote_available: "true" }, { trusted_remote_available: true, refresh_state: "idle", entries: [] }]) assert.throws(() => readOfficialCatalogueStatus(value));
  assert.throws(() => official({ entries: {} }));
  assert.throws(() => official({ entries: Array(201).fill({}) }));
  assert.equal(officialConnectorMetadata(null), null);
  const status = official({ entries: [null, {}, { manifest: { display: { name: {} }, publisher: [], licensing: null } }], last_confirmed_current_at: "invalid" });
  assert.equal(status.entries.length, 2);
  assert.equal(status.entries[0].name, "Unnamed connector");
  assert.equal(status.entries[1].licence, "Not specified");
  for (const value of [null, undefined, "invalid", {}, 123]) assert.equal(formatOfficialCatalogueTime(value), "Not recorded");
  assert.equal(officialConnectorMetadata({ manifest: { display: { name: "x".repeat(2000) } } }).name.length, 255);
  assert.deepEqual(reconcileConnectorCatalogue([], official({ entries: [] })), []);
});

test("official viewer and manager controls stay separate from executable local package actions", () => {
  for (const scope_type of ["customer", "site"]) for (const permission of ["integration_runtime.view", "integration_runtime.manage"]) {
    assert.equal(userHasGlobalPermission({ permissions: [permission], assignments: [{ scope_type, permissions: [permission] }] }, permission), false);
    assert.equal(userHasGlobalPermission({ assignments: [{ scope_type: "global", permissions: [permission] }] }, permission), true);
  }
  assert.doesNotMatch(render("OfficialCataloguePanel", { status: official(), canManage: false }), /Check for catalogue updates/);
  assert.match(render("OfficialCataloguePanel", { status: official(), canManage: true }), /Check for catalogue updates/);
  const entry = { connector_id: "proxmox", version: "0.2.0", status: "active", package_available: true, state: "installable", verification_status: "verified", digest, supported_actions: ["install", "update", "rollback", "remove"], manifest: { display: { name: '<img src=x onerror="window.executed=true">', description: "<script>window.executed=true</script>" }, publisher: { name: "<iframe>" }, distribution: { asset_uri: "https://private.invalid/?secret=value" }, connection_fields: [{ secret: true, default: "credential-value" }] } };
  const status = official({ entries: [entry] });
  assert.deepEqual(connectorActions(status.entries[0], true), []);
  const html = render("ConnectorCard", { entry: reconcileConnectorCatalogue([], status)[0], canManage: true });
  assert.match(html, /&lt;img/); assert.match(html, /&lt;script/);
  assert.doesNotMatch(html, /<img|<script|<iframe|Install Connector|Upgrade|Roll back|Activate|Configure|Resolve mappings|private.invalid|credential-value/);
  const local = { connector_id: "proxmox", version: "0.1.0", package_available: true, verification_status: "verified", state: "installable", digest, supported_actions: ["install"] };
  assert.equal(connectorActions(local, true).length, 1);
  assert.equal(filterConnectors([{ ...local, name: "Local Proxmox" }], "local", "installable").length, 1);
});

test("remote install confirmation binds the exact accepted identity", async () => {
  const { remoteInstallSelection, officialConnectorMetadata } = await import("../lib/integrations.mjs");
  const entry = { connector_id: "proxmox", version: "0.2.2", status: "active", eligible_for_install: true,
    catalogue_sequence: 2, catalogue_digest: "a".repeat(64), release_asset_id: 693849044, digest: "b".repeat(64) };
  const selection = remoteInstallSelection(entry);
  assert.equal(selection.confirm, "install");
  assert.equal(selection.source, "official");
  assert.equal(selection.catalogue_sequence, 2);
  assert.equal(selection.release_asset_id, 693849044);
  assert.equal(selection.digest, "b".repeat(64));
  assert.ok(Object.isFrozen(selection));
  assert.deepEqual(officialConnectorMetadata(entry).installSelection, selection);
  for (const change of [{ eligible_for_install: false }, { status: "withdrawn" }, { catalogue_sequence: true },
      { catalogue_digest: "wrong" }, { release_asset_id: 1.5 }, { digest: null }, { connector_id: "../other" }]) {
    assert.equal(remoteInstallSelection({ ...entry, ...change }), null);
  }
});

const bundled = { connector_id: "proxmox", name: "Proxmox VE", description: "Historical connection probe; inventory unavailable.", version: "0.1.0", digest, package_available: true, verification_status: "verified", supported_actions: ["install"], state: "installable" };
const officialRelease = (version, patch = {}) => ({ connector_id: "proxmox", version, status: "active", eligible_for_install: true, catalogue_sequence: 2, catalogue_digest: officialDigest, release_asset_id: 99, digest: "b".repeat(64), manifest: { id: "proxmox", version, manifest_version: "1.0", distribution: { bundle_digest: `sha256:${"b".repeat(64)}` }, display: { name: "Proxmox VE", description: `Read-only cluster inventory ${version}`, category: "virtualization" }, publisher: { name: "Atlas Impact" }, licensing: { licence: "Apache-2.0" } }, ...patch });
const installedRelease = { ...officialConnectorMetadata(officialRelease("0.2.2")), source: "installed", state: "installed", installed_version: "0.2.2", package_available: true, verification_status: "verified", supported_actions: ["remove"], installSelection: undefined };

test("one installed card uses its exact Manifest and keeps withdrawn and bundled versions in history", () => {
  const status = official({ sequence: 2, entries: [officialRelease("0.2.0", { status: "withdrawn" }), officialRelease("0.2.2")] });
  const cards = reconcileConnectorCatalogue([{ ...bundled, installed_version: "0.2.2" }], status, [installedRelease]);
  assert.equal(cards.length, 1);
  const card = cards[0];
  assert.equal(card.version, "0.2.2");
  assert.equal(card.digest, "b".repeat(64));
  assert.equal(card.description, "Read-only cluster inventory 0.2.2");
  assert.equal(card.verification_status, "verified");
  assert.equal(card.state, "installed");
  assert.equal(card.installEntry, null);
  assert.equal(card.localActionEntry, installedRelease);
  assert.deepEqual(card.history.map(release => release.version), ["0.2.2", "0.2.0", "0.1.0"]);
  const html = render("ConnectorCard", { entry: card, canManage: true });
  assert.match(html, /0\.2\.2.*Installed/);
  assert.match(html, /Verified/);
  assert.match(html, /Withdrawn official release/);
  assert.match(html, /Included offline package/);
  assert.match(html, /Remove package/);
  assert.match(html, /mappings\/proxmox\?version=0\.2\.2/);
  assert.doesNotMatch(html, /Review installation|Install Connector/);
  assert.ok(html.indexOf("Historical connection probe") > html.indexOf("<details"));
  assert.equal((html.match(/<h3>/g) || []).length, 1);
});

test("official package identity and action eligibility never inherit bundled authority", () => {
  for (const entry of [officialRelease("0.3.0", { eligible_for_install: false }), officialRelease("0.3.0", { digest: null })]) {
    const card = reconcileConnectorCatalogue([bundled], official({ entries: [entry] }))[0];
    assert.equal(card.version, "0.3.0");
    assert.equal(card.description, "Read-only cluster inventory 0.3.0");
    assert.equal(card.localActionEntry, null);
    assert.equal(card.installEntry, null);
    assert.deepEqual(connectorActions(card, true), []);
    assert.doesNotMatch(render("ConnectorCard", { entry: card, canManage: true }), /Install Connector|Review installation|Resolve mappings/);
  }
  const status = official({ sequence: 4, entries: [officialRelease("0.10.0"), officialRelease("0.9.9"), officialRelease("0.10.0-rc.2"), officialRelease("0.10.0-rc.10")] });
  const card = reconcileConnectorCatalogue([bundled], status, [installedRelease])[0];
  assert.equal(card.version, "0.2.2");
  assert.equal(card.availableRelease.version, "0.10.0");
  assert.equal(card.installEntry.version, "0.10.0");
  assert.equal(card.installEntry.installSelection.digest, "b".repeat(64));
  assert.deepEqual(card.history.slice(0, 4).map(entry => entry.version), ["0.10.0", "0.10.0-rc.10", "0.10.0-rc.2", "0.9.9"]);
  const manager = render("ConnectorCard", { entry: card, canManage: true });
  assert.match(manager, /Review package change/);
  assert.match(manager, /mappings\/proxmox\?version=0\.2\.2/);
  assert.doesNotMatch(render("ConnectorCard", { entry: card, canManage: false }), /Review package change|Resolve mappings|Remove package/);
});

test("new connector identities appear automatically and unaccepted metadata is ignored", () => {
  const future = officialRelease("1.0.0", { connector_id: "future-platform", manifest: { display: { name: "Future Platform", description: "New official connector" } } });
  const status = official({ sequence: 4, entries: [future, officialRelease("0.2.2")] });
  const local = [bundled, { connector_id: "docker", name: "Docker + Compose", version: null, package_available: false, verification_status: "metadata_only", state: "unavailable" }];
  const cards = reconcileConnectorCatalogue(local, status);
  assert.deepEqual(cards.map(entry => entry.connector_id), ["docker", "future-platform", "proxmox"]);
  assert.equal(connectorState(cards[0]), "bundle_not_released");
  assert.ok(cards[1].installEntry);
  assert.deepEqual(reconcileConnectorCatalogue(local, { ...status, trusted_remote_available: false }).map(entry => entry.connector_id), ["docker", "proxmox"]);
  const stale = reconcileConnectorCatalogue(local, { ...status, last_confirmed_current_at: null, refresh_state: "failed", last_error_code: "source_rate_limited" });
  assert.equal(stale.at(-1).version, "0.2.2");
});

test("catalogue card ordering is stable and retains search results, state filters and actions", () => {
  const published = (connector_id, name, eligible_for_install) => officialRelease("1.0.0", {
    connector_id, eligible_for_install, manifest: { display: { name, category: "Network" } },
  });
  const status = official({ sequence: 2, entries: [
    published("official-network", "Alpha Network", true),
    published("pending-network", "Beta Network", false),
    officialRelease("0.3.0"),
  ] });
  const planned = { version: null, package_available: false, verification_status: "metadata_only", state: "unavailable" };
  const local = [
    { ...planned, connector_id: "planned-network", name: "Delta Network" },
    { ...bundled, connector_id: "local-network", name: "Echo Network" },
    { ...planned, connector_id: "planned-compute", name: "Foxtrot Compute" },
  ];
  const installed = [installedRelease, {
    ...installedRelease, connector_id: "unverified-network", name: "Zulu Network",
    package_available: false, verification_status: "verification_unavailable",
  }];
  const ids = entries => entries.map(entry => entry.connector_id);
  const entries = Object.freeze(reconcileConnectorCatalogue(local, status, installed));
  assert.deepEqual(ids(entries), ["official-network", "pending-network", "planned-network", "local-network", "planned-compute", "proxmox", "unverified-network"]);
  const ordered = orderConnectorCards(entries);
  assert.deepEqual(ids(ordered), ["proxmox", "unverified-network", "official-network", "local-network", "pending-network", "planned-network", "planned-compute"]);
  assert.deepEqual(ids(orderConnectorCards([...entries].reverse())), ["unverified-network", "proxmox", "local-network", "official-network", "pending-network", "planned-compute", "planned-network"]);
  const matching = (query, state) => orderConnectorCards(filterConnectors(entries, query, state));
  assert.deepEqual(ids(matching(" NETWORK ")), ["unverified-network", "official-network", "local-network", "pending-network", "planned-network"]);
  assert.deepEqual(ids(matching("network", "installable")), ["official-network", "local-network"]);
  assert.deepEqual(ids(matching("network", "unavailable")), ["pending-network"]);
  assert.deepEqual(ids(matching("network", "bundle_not_released")), ["planned-network"]);
  assert.deepEqual(ids(matching("network", "installed")), ["unverified-network"]);
  const card = entry => render("ConnectorCard", { entry, canManage: true });
  assert.match(card(ordered[0]), /Review package change/);
  assert.match(card(ordered[1]), /Verification unavailable.*Remove package/);
  assert.match(card(ordered[2]), /Review installation/);
  assert.match(card(ordered[3]), /Install Connector/);
  assert.doesNotMatch(card(ordered[4]), /Review installation|Install Connector/);
  assert.doesNotMatch(card(ordered[5]), /Review installation|Install Connector/);

  // An older API can report an installed version through an update card only.
  const legacyUpdate = { ...bundled, installed_version: "0.0.1", state: "update_available", supported_actions: ["update"] };
  const offline = orderConnectorCards(reconcileConnectorCatalogue([...local, legacyUpdate], null, [installed[1]]));
  assert.deepEqual(ids(offline), ["proxmox", "unverified-network", "local-network", "planned-network", "planned-compute"]);
  assert.match(card(offline[0]), /Update available.*Update package/);
});

test("offline and verification failures retain installed-only identities without borrowed metadata", () => {
  const installedOnly = { ...installedRelease, connector_id: "operator-package", name: "Operator package" };
  const cards = reconcileConnectorCatalogue([bundled], null, [installedRelease, installedOnly]);
  assert.equal(cards.length, 2);
  assert.equal(cards.find(entry => entry.connector_id === "proxmox").version, "0.2.2");
  const failed = { ...installedRelease, description: "Installed metadata unavailable", package_available: false, verification_status: "verification_unavailable" };
  const card = reconcileConnectorCatalogue([bundled], official({ entries: [officialRelease("0.2.2")] }), [failed])[0];
  assert.equal(card.description, "Installed metadata unavailable");
  assert.equal(card.verification_status, "verification_unavailable");
  assert.doesNotMatch(render("ConnectorCard", { entry: card, canManage: true }), /Resolve mappings/);
  assert.equal(reconcileConnectorCatalogue([bundled], null)[0].version, "0.1.0");
  const withdrawn = reconcileConnectorCatalogue([], official({ entries: [officialRelease("0.2.0", { status: "withdrawn" })] }))[0];
  assert.equal(connectorState(withdrawn), "withdrawn");
  assert.equal(resolveStatus("withdrawn").label, "Withdrawn");
  assert.equal(withdrawn.installEntry, null);
});
