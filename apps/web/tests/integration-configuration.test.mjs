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
