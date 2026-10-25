import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { connectorActions, connectorState, filterConnectors, integrationTab, formatIntegrationTime, runtimeErrorMessage, runtimeOperations, readOfficialCatalogueStatus, officialConnectorMetadata, formatOfficialCatalogueTime, officialCatalogueBlocked, officialCatalogueSummary, officialCatalogueDiagnostic, officialCatalogueRequestError } from "../lib/integrations.mjs";
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
  for (const text of ["Sequence 1", "1.0", officialDigest, formatOfficialCatalogueTime(confirmed), "Past confirmation does not establish", "Previously".toLowerCase(), "Proxmox VE", "0.2.0", "Apache-2.0", "Unavailable for remote installation"]) assert.ok(html.includes(text), text);
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
    assert.match(html, /role="alert"/); assert.match(html, /Proxmox VE/); assert.match(html, /Sequence 1/);
    assert.equal(status.last_confirmed_current_at, confirmed);
    assert.doesNotMatch(html, /unknown-internal-secret/);
  }
});

test("official API errors are bounded and distinct from verification failures", () => {
  for (const [status, text] of [[401, /session has expired/], [403, /permission/], [503, /does not establish a verification failure/]]) {
    const message = officialCatalogueRequestError({ status, message: "Traceback /var/private token=private https://signed.invalid" });
    assert.match(message, text); assert.doesNotMatch(message, /Traceback|private|signed/);
    const html = render("OfficialCataloguePanel", { status: official(), error: message, canManage: true });
    assert.match(html, /Proxmox VE/); assert.match(html, /role="alert"/);
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
  assert.match(render("OfficialCataloguePanel", { status: official({ entries: [] }) }), /No official connector entries/);
});

test("official viewer and manager controls stay separate from executable local package actions", () => {
  for (const scope_type of ["customer", "site"]) for (const permission of ["integration_runtime.view", "integration_runtime.manage"]) {
    assert.equal(userHasGlobalPermission({ permissions: [permission], assignments: [{ scope_type, permissions: [permission] }] }, permission), false);
    assert.equal(userHasGlobalPermission({ assignments: [{ scope_type: "global", permissions: [permission] }] }, permission), true);
  }
  assert.doesNotMatch(render("OfficialCataloguePanel", { status: official(), canManage: false }), /Check official catalogue/);
  assert.match(render("OfficialCataloguePanel", { status: official(), canManage: true }), /Check official catalogue/);
  const entry = { connector_id: "proxmox", version: "0.2.0", status: "active", package_available: true, state: "installable", verification_status: "verified", digest, supported_actions: ["install", "update", "rollback", "remove"], manifest: { display: { name: '<img src=x onerror="window.executed=true">', description: "<script>window.executed=true</script>" }, publisher: { name: "<iframe>" }, distribution: { asset_uri: "https://private.invalid/?secret=value" }, connection_fields: [{ secret: true, default: "credential-value" }] } };
  const status = official({ entries: [entry] });
  assert.deepEqual(connectorActions(status.entries[0], true), []);
  const html = render("OfficialCataloguePanel", { status, canManage: true });
  assert.match(html, /&lt;img/); assert.match(html, /&lt;script/);
  assert.doesNotMatch(html, /<img|<script|<iframe|Install Connector|Upgrade|Roll back|Activate|Configure|Resolve mappings|private.invalid|credential-value/);
  const local = { connector_id: "proxmox", version: "0.1.0", package_available: true, verification_status: "verified", state: "installable", digest, supported_actions: ["install"] };
  assert.equal(connectorActions(local, true).length, 1);
  assert.equal(filterConnectors([{ ...local, name: "Local Proxmox" }], "local", "installable").length, 1);
});
