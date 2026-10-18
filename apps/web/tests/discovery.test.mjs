import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { loadComponent } from "./helpers/components.mjs";
import { DISCOVERY_SCHEDULES, discoveryControls, discoveryDuration, discoveryRunPresentation } from "../lib/discovery.mjs";

test("probe-only, disabled, retired and scoped permission gating", () => {
  const record = { discovery_capable: true, scheduling_capable: true, enabled: true, credential_configured: true };
  assert.deepEqual(discoveryControls(record, true, true), { run: true, schedule: true, active: false, eligible: true });
  for (const override of [{ discovery_capable: false }, { enabled: false }, { retired_at: "2026-10-12" }]) {
    const value = discoveryControls({ ...record, ...override }, true, true);
    assert.equal(value.run, false); assert.equal(value.schedule, false);
  }
  assert.equal(discoveryControls(record, false, true).run, false);
  assert.equal(discoveryControls(record, true, false).schedule, false);
  assert.equal(discoveryControls({ ...record, source_compatibility: "known_incompatible" }, true, true).eligible, false);
  assert.equal(discoveryControls({ ...record, credential_configured: false, discovery_configured: true }, true, true).eligible, true);
});
test("fixed schedules and truthful run duration", () => {
  assert.equal(DISCOVERY_SCHEDULES.length, 6);
  assert.equal(discoveryDuration({ started_at: "2026-10-12T00:00:00Z", finished_at: "2026-10-12T00:01:00Z" }), "60s");
  assert.equal(discoveryDuration({ started_at: "2026-10-12T00:00:00Z" }), "In progress");
});

const components = loadComponent(new URL("../components/discovery-runs-table.js", import.meta.url));
const run = {
  id: "00000000-0000-4000-8000-000000000004", integration_id: "00000000-0000-4000-8000-000000000003",
  source_name: "Proxmox Cluster", coverage_key: "connector:v1:135aab-opaque-scope", is_complete_snapshot: true,
  status: "completed", completeness_status: "partial", observation_count: 140, batch_count: 3,
  execution_provenance: { connector_id: "proxmox", connector_version: "0.2.0-i4b.2", trigger: "manual", connector_digest: "a".repeat(64) },
};

test("Discovery summary uses structured coverage without conflating completeness", () => {
  const before = structuredClone(run);
  assert.deepEqual(discoveryRunPresentation(run), { source: "Proxmox Cluster", connector: "Proxmox · 0.2.0-i4b.2", trigger: "Manual", coverage: "Full scope" });
  for (const completeness_status of ["complete", "partial", "unknown", "failed"]) {
    assert.equal(discoveryRunPresentation({ ...run, completeness_status }).coverage, "Full scope");
  }
  assert.equal(discoveryRunPresentation({ ...run, is_complete_snapshot: false }).coverage, "Partial scope");
  assert.equal(discoveryRunPresentation({ coverage_key: run.coverage_key }).coverage, "Unspecified");
  assert.deepEqual(run, before);
});

test("Discovery rows show friendly names and keep internal identities out of visible content", () => {
  const html = renderToStaticMarkup(React.createElement(components.DiscoveryRunsTable, { runs: [run] }));
  const text = html.replace(/<[^>]*>/g, "");
  assert.match(text, /Proxmox Cluster/);
  for (const internal of [run.id, run.integration_id, run.coverage_key, run.execution_provenance.connector_digest]) {
    assert.equal(text.includes(internal), false);
  }
  assert.match(html, new RegExp(`href="/integrations/${run.integration_id}"`));
  assert.match(html, /<caption class="sr-only">Discovery runs<\/caption>/);
  assert.match(html, /<th scope="col"/);
  assert.match(html, /role="region" aria-label="Discovery runs table" tabindex="0"/);
});

test("Discovery connector and trigger use separately spaced primary and secondary lines", () => {
  const html = renderToStaticMarkup(React.createElement(components.DiscoveryRunsTable, { runs: [run] }));
  assert.match(html, /class="table-cell-identity"><span class="primary-cell">Proxmox · 0\.2\.0-i4b\.2<\/span><span class="secondary-text">Manual<\/span>/);
  assert.match(html, /role="group" aria-label="Run status"[^]*?>Completed<\/span>/);
  assert.match(html, /role="group" aria-label="Completeness"[^]*?>Partial<\/span>/);
  assert.doesNotMatch(html, /i4b\.2manual|CompletedPartial/);
});

test("Discovery legacy and unavailable display values use safe generic labels", () => {
  assert.deepEqual(discoveryRunPresentation({}), { source: "Unknown source", connector: "Legacy", trigger: "Manual", coverage: "Unspecified" });
  const malformed = { execution_provenance: { connector_id: "/raw/source/path", trigger: "opaque-trigger-id" } };
  assert.deepEqual(discoveryRunPresentation(malformed), { source: "Unknown source", connector: "Unknown connector", trigger: "Unknown trigger", coverage: "Unspecified" });
  for (const [trigger, label] of [["schedule", "Scheduled"], ["retry", "Retry"], ["onboarding", "Onboarding"]]) {
    assert.equal(discoveryRunPresentation({ ...run, execution_provenance: { ...run.execution_provenance, trigger } }).trigger, label);
  }
});
