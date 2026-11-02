import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { readFile } from "node:fs/promises";
import { loadComponent } from "./helpers/components.mjs";

const { AssetKnowledgeSummary } = loadComponent(new URL("../components/asset-knowledge-summary.js", import.meta.url));
const assertions = ["A", "B"].map(source => ({ assertion_id: `assertion-${source}`, source_name: `Proxmox ${source}`, source_id: source,
  last_observed_at: "2026-11-01T00:00:00Z", accepted_at: "2026-11-01T01:00:00Z", accepted_by_name: "Reviewer" }));
const observed = { predicate: "asset_type", label: "Asset Type", cardinality: "single", accepted_values: [], latest_observations: assertions,
  observation_groups: [{ key: "type", display_value: "LXC Container", assertions, source_count: 2 }], state: "observed", awaiting_acceptance: true,
  canonical_display_value: "LXC Container", canonical_consistency: "missing_acceptance", source_count: 2, assertion_count: 2, historical_count: 0 };
const render = groups => renderToStaticMarkup(React.createElement(AssetKnowledgeSummary, { groups }));

test("AK-01 agreeing observations stay Observed with explicit unaccepted operational value", () => {
  const html = render([observed]);
  assert.match(html, />Observed</);
  assert.doesNotMatch(html, />Unresolved</);
  assert.match(html, /Awaiting acceptance/);
  assert.match(html, /Not selected/);
  assert.match(html, /Operational Atlas value/);
  assert.match(html, /LXC Container/);
  assert.match(html, /no matching accepted assertion/);
  assert.match(html, /2 sources · Provenance/);
  assert.match(html, /Proxmox A/); assert.match(html, /Proxmox B/);
});

test("AK-01 disagreement, acceptance and operational mismatch remain distinct", () => {
  assert.match(render([{ ...observed, state: "unresolved", unresolved: true }]), />Unresolved</);
  assert.match(render([{ ...observed, state: "conflicting", conflict: true }]), />Conflicting</);
  const accepted = { ...observed, state: "accepted", awaiting_acceptance: false, canonical_consistency: "matches",
    accepted_values: [{ ...assertions[0], value: "lxc_container", display_value: "LXC Container" }] };
  assert.match(render([accepted]), />Accepted</);
  assert.doesNotMatch(render([accepted]), /Awaiting acceptance|no matching accepted assertion/);
  assert.match(render([{ ...accepted, canonical_consistency: "mismatch" }]), /operational value differs from accepted knowledge/);
});

test("AK-02 logical targets render once per bucket with named safe links and all provenance", () => {
  const name = "Proxmox host with a long operational name ".repeat(5);
  const relationship = { target_name: name, label: "Runs on", target_id: "canonical-target", href: "/assets/canonical-target" };
  const html = render([{ ...observed, predicate: "runs_on", label: "Runs on", cardinality: "multi", state: "accepted", awaiting_acceptance: false,
    canonical_consistency: "not_applicable", accepted_values: assertions, latest_observations: [],
    accepted_groups: [{ key: "logical", relationship, assertions, source_count: 2 }], observation_groups: [] }]);
  assert.equal((html.match(/href="\/assets\/canonical-target"/g) || []).length, 1);
  assert.match(html, /aria-label="Runs on: Proxmox host/);
  assert.match(html, /Proxmox A/); assert.match(html, /Proxmox B/);
  assert.match(html, /assertion-A/); assert.match(html, /assertion-B/);
  assert.doesNotMatch(html, /target_id|relationship_type|\{&quot;/);
});

test("AK-02 unavailable targets have no link and raw structured values are not default JSON labels", () => {
  const html = render([{ ...observed, accepted_values: [{ assertion_id: "legacy", value: { target_id: "hidden" }, display_value: "Unavailable asset",
    relationship: { target_name: "Unavailable asset", href: null } }], latest_observations: [], observation_groups: [] }]);
  assert.match(html, /Unavailable asset/);
  assert.doesNotMatch(html, /href=|target_id|hidden/);
  assert.match(render([{ ...observed, accepted_values: [{ assertion_id: "structured", value: { arbitrary: "raw" } }], latest_observations: [], observation_groups: [] }]), /Structured value — see Raw assertions/);
});

test("summary values wrap and existing history/raw controls remain reachable", async () => {
  const [css, page] = await Promise.all([
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
    readFile(new URL("../app/assets/[id]/page.js", import.meta.url), "utf8"),
  ]);
  assert.match(css, /knowledge-logical-value strong[^}]*overflow-wrap: anywhere; white-space: normal/);
  assert.match(page, /<AssertionsPanel assertions=\{assertions\}/);
  assert.match(page, /knowledgeTab === "history"/);
});
