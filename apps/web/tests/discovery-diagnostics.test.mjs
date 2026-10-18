import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { loadComponent } from "./helpers/components.mjs";

const { DiagnosticsView, DebugNextRunControl } = loadComponent(new URL("../components/discovery-diagnostics.js", import.meta.url));
const run = { debug_enabled: true, diagnostics_summary: { available: true,
  counts: { processed: 179, accepted: 178, skipped: 1, warning: 1, error: 0 }, reasons: [{ reason_code: "interface_invalid", count: 1 }] },
  diagnostics_events: [{ sequence: 17, stage: "guest_interface", result: "warning", reason_code: "interface_invalid",
    object_class: "fixture.guest", external_id: "guest/1027", parent_external_id: "node/example" }] };
const trace = { state: "available", expires_at: "2026-10-20T00:00:00Z", events: [{ ...run.diagnostics_events[0], field: "net0", encountered_type: "string", validation_rule: "interface_config" }] };
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props));

test("normal diagnostics show structured counts and generic safe identities", () => {
  const html = render(DiagnosticsView, { run, canDebug: false, trace });
  for (const text of ["179", "178", "guest_interface", "interface_invalid", "guest/1027", "node/example"]) assert.ok(html.includes(text.replaceAll("guest_interface", "guest interface")));
  assert.match(html, /<caption class="sr-only">Discovery diagnostics<\/caption>/);
  assert.match(html, /scope="col"/);
  assert.doesNotMatch(html, /Debug trace|net0|interface_config|Expires/);
});

test("only authorised administrators see expandable debug and deletion", () => {
  const html = render(DiagnosticsView, { run, canDebug: true, trace, expanded: true });
  assert.match(html, /<details open=""><summary>Debug trace<\/summary>/);
  assert.match(html, /Field: net0/);
  assert.match(html, /Type: string/);
  assert.match(html, /Delete debug data/);
  assert.match(html, /Expires/);
  assert.doesNotMatch(render(DiagnosticsView, { run: { ...run, debug_enabled: false }, canDebug: true, trace }), /Debug trace/);
});

test("expired and deleted debug show retained normal diagnostics without debug events", () => {
  for (const state of ["expired", "deleted"]) {
    const html = render(DiagnosticsView, { run, canDebug: true, trace: { ...trace, state } });
    assert.match(html, new RegExp(`Debug data: ${state}`));
    assert.match(html, /interface_invalid/);
    assert.doesNotMatch(html, /Field: net0|Delete debug data/);
  }
});

test("next run arming is explicit, off by default and hidden from non-admin", () => {
  assert.equal(render(DebugNextRunControl, { allowed: false, armed: true }), "");
  assert.match(render(DebugNextRunControl, { allowed: true }), /Debug next run: <strong>Off/);
  assert.match(render(DebugNextRunControl, { allowed: true, armed: true }), /Debug next run: <strong>Armed/);
  assert.match(render(DebugNextRunControl, { allowed: true }), /Enable debug for next discovery run/);
  assert.match(render(DebugNextRunControl, { allowed: true }), /48 hours/);
});
