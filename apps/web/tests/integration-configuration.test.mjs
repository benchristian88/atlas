import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { loadComponent } from "./helpers/components.mjs";
import { initialConfig, configurationPayload, testMessage } from "../lib/integration-configuration.mjs";

const components = loadComponent(new URL("../components/integration-configuration.js", import.meta.url));
const form = { connection_fields: [
  { key: "address", label: "Source address", type: "url", required: true, secret: false },
  { key: "credential", label: "Credential", type: "secret", required: true, secret: true },
  { key: "tls_mode", label: "TLS mode", type: "enum", options: ["verify", "fingerprint", "insecure"], default: "verify", required: true, secret: false },
  { key: "pin", label: "Fingerprint", type: "fingerprint", required: true, secret: false, visible_when: { field: "tls_mode", equals: "fingerprint" } },
] };

test("form hydration excludes declared secrets and unknown configuration fields", () => {
  assert.deepEqual(initialConfig(form, { credential: "sentinel", address: "https://source.example.test", hidden: true }), { address: "https://source.example.test", tls_mode: "verify" });
  const value = configurationPayload(form, { address: "https://source.example.test", tls_mode: "verify", pin: "hidden" }, { credential: "new entry", hidden: "ignored" });
  assert.deepEqual(value.config, { address: "https://source.example.test", tls_mode: "verify" });
  assert.deepEqual(value.credentials, { credential: "new entry" });
});

test("initial secrets are blank password fields, configured state never rehydrates a value", () => {
  const props = { form, config: { tls_mode: "verify" }, onConfig: () => {}, onCredentials: () => {} };
  const initial = renderToStaticMarkup(React.createElement(components.ConnectionFields, props));
  assert.match(initial, /type="password"/);
  assert.match(initial, /autoComplete="new-password"/);
  assert.doesNotMatch(initial, /Fingerprint/);
  const configured = renderToStaticMarkup(React.createElement(components.ConnectionFields, { ...props, secretMode: "state", configuredFields: ["credential"], credentials: { credential: "sentinel" } }));
  assert.match(configured, /Configured/);
  assert.doesNotMatch(configured, /sentinel|type="password"/);
});

test("insecure TLS is explicitly warned independent of source-specific field keys", () => {
  const html = renderToStaticMarkup(React.createElement(components.ConnectionFields, { form, config: { tls_mode: "insecure" } }));
  assert.match(html, /Advanced TLS exception/);
  assert.match(html, /role="status"/);
});

test("probe messages use fixed categories and never vendor error text", () => {
  assert.match(testMessage({ category: "authentication_failed" }), /rejected/);
  assert.doesNotMatch(testMessage({ category: "secret sentinel" }), /sentinel/);
  const html = renderToStaticMarkup(React.createElement(components.ConnectionResult, { result: { success: true, category: "connected", source_version: "8.4", compatibility: "untested" } }));
  assert.match(html, /8\.4/);
  assert.match(html, /not been qualified/);
});

function diagnosticHtml(rows) {
  return renderToStaticMarkup(React.createElement(components.ConnectionResult, {
    result: { success: true, category: "connected", capability_diagnostics: rows },
  }));
}

test("capability readiness renders generic state, category and optional privilege", () => {
  const html = diagnosticHtml([
    { capability: "inventory", state: "ready", path_category: "inventory" },
    { capability: "inventory.records", state: "permission_limited", path_category: "authorization", privilege: "Inventory.Audit" },
    { capability: "topology", state: "source_unavailable", path_category: "topology" },
    { capability: "visibility", state: "unproven", path_category: "root" },
  ]);
  for (const text of ["Capability readiness", "Ready", "Limited", "Unavailable", "Unproven", "Path category", "Inventory.Audit"]) assert.ok(html.includes(text), text);
  assert.match(html, /data-status-tone="success"/);
  assert.match(html, /data-status-tone="warning"/);
  assert.match(html, /aria-label="Capability diagnostics"/);
});

test("absent diagnostics preserve ordinary connection results", () => {
  for (const rows of [undefined, null, []]) {
    const html = diagnosticHtml(rows);
    assert.match(html, /authenticated successfully/);
    assert.doesNotMatch(html, /Capability readiness/);
  }
});

test("malformed diagnostic lists are rejected like the API boundary", () => {
  const valid = { capability: "inventory", state: "ready", path_category: "inventory" };
  const attacks = ["raw body", [{ ...valid, capability: "/private/acl/path" }], [{ ...valid, privilege: "token=secret" }],
    [{ ...valid, raw_body: "sentinel" }], [{ ...valid, state: "sentinel" }], [{ ...valid, path_category: "sentinel" }],
    [{ ...valid, capability: "a".repeat(65) }], [{ ...valid, privilege: null }], Array(17).fill(valid), [valid, {}], [null]];
  for (const rows of attacks) assert.doesNotMatch(diagnosticHtml(rows), /Capability readiness|sentinel|private|token=secret/);
});
