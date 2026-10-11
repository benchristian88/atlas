import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { connectorActions, connectorState, filterConnectors, integrationTab, formatIntegrationTime, runtimeErrorMessage, runtimeOperations } from "../lib/integrations.mjs";
import { resolveStatus } from "../lib/status.mjs";
import { loadComponent } from "./helpers/components.mjs";
const components = loadComponent(new URL("../components/integration-panels.js", import.meta.url));
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
