import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import * as audit from "../lib/audit-details.mjs";

const require = createRequire(import.meta.url);
const { transformSync } = require("next/dist/compiled/babel/core");
const { code } = transformSync(readFileSync(new URL("../components/audit-investigation.js", import.meta.url), "utf8"), {
  babelrc: false,
  configFile: false,
  presets: [[require("next/dist/compiled/babel/preset-react"), { runtime: "classic" }]],
  plugins: [require("next/dist/compiled/babel/plugin-transform-modules-commonjs")],
});
const components = {};
Function("require", "exports", "React", code)(name => ({ react: React, "../lib/audit-details.mjs": audit })[name], components, React);

const id = number => `00000000-0000-4000-8000-${String(number).padStart(12, "0")}`;
const customer = { id: id(1), name: "Homelab" };
const site = { id: id(2), customer_id: customer.id, name: "Home" };
const integration = { id: id(3), customer_id: customer.id, site_id: site.id, name: "Proxmox Cluster" };
const debugEvent = {
  id: id(4), created_at: "2026-11-18T01:00:00Z", actor_snapshot: "Operator",
  event_type: "integration.debug_next_run_changed", target_type: "integration", target_id: integration.id,
  customer_id: customer.id, site_id: site.id, request_id: "request-audit-42", source_ip: "192.0.2.42",
  change_summary: "Discovery debug next run changed", success: true, metadata: { enabled: true },
};
const visible = { customers: [customer], sites: [site], integrations: [integration] };

function render(event, records = visible) {
  const references = audit.auditReferences(event, records);
  return {
    target: renderToStaticMarkup(React.createElement(components.AuditTarget, { object: references.object })),
    detail: renderToStaticMarkup(React.createElement(components.AuditInvestigation, { event, references, timestamp: value => value })),
  };
}

test("debug-next-run shows current Integration and scope names with the original identifiers", () => {
  assert.equal(audit.needsIntegrationName(debugEvent), true);
  const { target, detail } = render(debugEvent);
  assert.match(target, /Proxmox Cluster<\/span>.*integration · current name/);
  for (const [field, { name, id: uuid }] of [["Object", integration], ["Customer", customer], ["Site", site]]) {
    const value = detail.split(`<dt>${field}</dt><dd>`)[1]?.split("</dd>")[0];
    assert.match(value, new RegExp(`${name}<small[^>]*> \\(current name\\)</small>.*${uuid}`));
  }
  assert.match(detail, /<dt>Request<\/dt><dd>request-audit-42<\/dd>/);
  assert.match(detail, /<dt>Source IP<\/dt><dd>192\.0\.2\.42<\/dd>/);
  assert.match(detail, /<dt>Action<\/dt><dd>integration\.debug_next_run_changed<\/dd>/);
  assert.match(detail, /<p>Discovery debug next run changed<\/p>/);
  assert.match(detail, /<dt>enabled<\/dt><dd><pre>true<\/pre><\/dd>/);
});

test("a captured Site name takes precedence after a rename", () => {
  const event = { ...debugEvent, event_type: "site.created", target_type: "site", target_id: site.id, metadata: { name: "Original site" } };
  const { target, detail } = render(event);
  assert.match(target, /Original site<\/span>.*>site<\/small>/);
  for (const field of ["Object", "Site"]) {
    const value = detail.split(`<dt>${field}</dt><dd>`)[1]?.split("</dd>")[0];
    assert.ok(value.includes("Original site"));
    assert.ok(value.includes(site.id));
    assert.doesNotMatch(value, /Home|current name/);
  }
});

test("a captured Customer name is available for a deleted target with no live record", () => {
  const event = { ...debugEvent, event_type: "customer.deleted", target_type: "customer", target_id: id(6), customer_id: null, site_id: null, metadata: { name: "Deleted customer" } };
  const { target, detail } = render(event);
  assert.match(target, /Deleted customer<\/span>.*>customer<\/small>/);
  assert.match(detail, new RegExp(`<dt>Object</dt><dd>.*Deleted customer.*customer · ${event.target_id}`));
  assert.doesNotMatch(detail, /<dt>Customer<\/dt>|<dt>Site<\/dt>|current name/);
});

test("an event with no label retains type and ID without inferring a name from changed fields", () => {
  const event = { ...debugEvent, event_type: "asset.updated", target_type: "asset", target_id: id(7), metadata: { changed_fields: ["name"] } };
  assert.equal(audit.needsIntegrationName(event), false);
  const { target, detail } = render(event);
  assert.equal(target, "asset");
  assert.ok(detail.includes(`<dt>Object</dt><dd>asset · ${event.target_id}</dd>`));
});

test("restricted or mismatched records keep the authorised type and UUID fallbacks", () => {
  const records = {
    customers: [],
    sites: [{ ...site, customer_id: id(8), name: "Unrelated site" }],
    integrations: [{ ...integration, id: id(9), name: "Visible Integration" }, { ...integration, customer_id: id(8), name: "Unrelated Integration" }],
  };
  const { target, detail } = render(debugEvent, records);
  assert.equal(target, "integration");
  assert.doesNotMatch(detail, /Homelab|Home|Proxmox Cluster|Unrelated|Visible Integration|current name/);
  assert.ok(detail.includes(`<dt>Object</dt><dd>integration · ${integration.id}</dd>`));
  assert.ok(detail.includes(`<dt>Customer</dt><dd>${customer.id}</dd>`));
  assert.ok(detail.includes(`<dt>Site</dt><dd>${site.id}</dd>`));
  assert.ok(detail.includes(`<dt>Request</dt><dd>${debugEvent.request_id}</dd>`));
});
