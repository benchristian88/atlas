import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { loadComponent } from "./helpers/components.mjs";
import { reconciliationEntityPagePath, reconciliationQueueFromValue, reconciliationReviewHref, reconciliationReturnHref } from "../lib/reconciliation-queues.mjs";

const { ReconciliationEntityCard, ReconciliationReviewLink, TechnicalIdentityLink } = loadComponent(new URL("../components/reconciliation-cards.js", import.meta.url));
const row = { id: "fact", category: "changed", status: "open", entity_type: "asset", label: "Serial number", proposed: "12345", current: null, assertion_predicate: "generic.serial", source_name: "Source", can_accept: false, can_reject: true, can_defer: true, blocked_reason: "Requires Workload to exist", blockers: [{ item_id: "parent", entity_id: "owner", name: "Workload" }], warning: null };
const parent = { ...row, id: "parent", category: "newly_discovered", entity_type: "asset", label: "New asset", can_accept: true, blockers: [], blocked_reason: null };
const entity = { id: "owner", entity_type: "asset", customer_id: "customer", site_id: "site", name: "Workload", type_label: "Virtual Machine", default_expanded: true, matching_record_count: 2, parent, sections: [{ key: "facts", label: "Facts", total: 1, items: [row], warnings: [row.blocked_reason], blocked_count: 1, next_offset: null }], decision_items: [{ id: "parent", version: "0".repeat(64) }, { id: "fact", version: "0".repeat(64) }], accept_all_available: true, bulk_limit: 1000 };
function render(record = entity, extra = {}) {
  return renderToStaticMarkup(React.createElement(ReconciliationEntityCard, { entity: record, canDecide: true, reviewHref: id => `/reconciliation?entity=${id}`, ...extra }));
}

test("new entity card expands, separates Accept asset and Accept all, and exposes blocked child evidence", () => {
  const html = render();
  assert.match(html, /<details open="">/);
  assert.match(html, />Accept asset<\/button>/);
  assert.match(html, />Accept all<\/button>/);
  assert.match(html, /disabled=""[^>]*>Accept<\/button>/);
  assert.match(html, /Serial number/);
  assert.match(html, /12345/);
  assert.match(html, /Waiting — Requires Workload to exist/);
  assert.match(html, /href="\/reconciliation\?entity=owner">Review Workload/);
  assert.match(html, /Evidence and details/);
  assert.match(html, /generic.serial/);
});

test("accepted parent remains visible while children are independently actionable", () => {
  const eligible = { ...row, can_accept: true, blocked_reason: null, blockers: [] };
  const html = render({ ...entity, default_expanded: false, parent: { ...parent, status: "accepted", can_reject: false }, sections: [{ ...entity.sections[0], items: [eligible], blocked_count: 0, warnings: [] }] });
  assert.match(html, />Accepted</);
  assert.doesNotMatch(html, />Accept asset<\/button>/);
  assert.match(html, />Accept<\/button>/);
  assert.match(html, /<details><summary class="review-entity-heading"/);
});

test("canonical review renders the backend snapshot in the comparison and evidence", () => {
  const fresh = { ...row, label: "Name", current: "New manual value", proposed: "Observed",
    current_value_json: { field: "name", value: "New manual value" },
    observed_value_json: { field: "name", value: "Observed" },
    version: "2".repeat(64), can_accept: true, blocked_reason: null, blockers: [] };
  const html = render({ ...entity, parent: null, sections: [{ ...entity.sections[0], items: [fresh] }] });
  assert.match(html, /New manual value<\/span><span aria-label="changes to"> → <\/span><span>Observed/);
  assert.match(html, /<span>Current<\/span><code>\{&quot;field&quot;:&quot;name&quot;,&quot;value&quot;:&quot;New manual value&quot;\}<\/code>/);
});

test("existing entity shares sections, starts compact, and focus expands it", () => {
  const existing = { ...entity, parent: null, default_expanded: false };
  assert.match(render(existing), /<details><summary class="review-entity-heading"/);
  assert.match(render(existing, { focused: true }), /review-entity-focused/);
  assert.match(render(existing, { focused: true }), /<details open="">/);
});

test("large sections collapse independently with warnings outside the disclosure", () => {
  const html = render({ ...entity, sections: [{ ...entity.sections[0], total: 12, next_offset: 20 }] });
  assert.match(html, /<details><summary><span>Facts<\/span>/);
  assert.match(html, /12 changes · 1 waiting/);
  assert.match(html, /<\/details><div class="review-section-warnings" role="status">/);
  assert.match(html, /Show more facts/);
});

test("read only review has evidence and no decisions", () => {
  const html = render({ ...entity, parent: { ...parent, can_reject: false }, sections: [{ ...entity.sections[0], items: [{ ...row, can_reject: false }] }] }, { canDecide: false });
  assert.doesNotMatch(html, />Accept|>Reject|>Defer|>Link asset/);
  assert.match(html, /Evidence and details/);
});

test("grouped queries retain status, category, search, section and cursor", () => {
  const path = reconciliationEntityPagePath(reconciliationQueueFromValue("changed"), { cursor: "opaque", search: "Workload", section: "facts" });
  const url = new URL(path, "https://atlas.test");
  assert.equal(url.pathname, "/reconciliation-entities");
  assert.deepEqual(Object.fromEntries(url.searchParams), { status: "open", limit: "50", category: "changed", cursor: "opaque", search: "Workload", section: "facts" });
});

test("prerequisite links preserve queue position, refresh, back and return without external redirects", () => {
  const original = "queue=changed&search=Workload&cursor=opaque&page=2";
  const href = reconciliationReviewHref(original, "host", "workload");
  const target = new URL(href, "https://atlas.test");
  assert.equal(target.searchParams.get("entity"), "host");
  const back = new URL(reconciliationReturnHref(target.searchParams.get("return")), target);
  assert.equal(back.searchParams.get("entity"), "workload");
  assert.equal(back.searchParams.get("cursor"), "opaque");
  assert.equal(back.searchParams.get("page"), "2");
  assert.equal(back.searchParams.get("queue"), "changed");
  assert.equal(reconciliationReturnHref("redirect=https://evil.test&entity=workload"), "/reconciliation?entity=workload");
});

test("review links record query history and retain modified-click browser behavior", () => {
  const previous = globalThis.window;
  const visited = [];
  globalThis.window = { history: { pushState: (_, __, href) => visited.push(href) } };
  try {
    const link = ReconciliationReviewLink({ href: "/reconciliation?entity=host", children: "Review Host" });
    let prevented = false;
    link.props.onClick({ button: 0, preventDefault: () => { prevented = true; } });
    assert.equal(prevented, true);
    assert.deepEqual(visited, ["/reconciliation?entity=host"]);
    prevented = false;
    link.props.onClick({ button: 0, ctrlKey: true, preventDefault: () => { prevented = true; } });
    assert.equal(prevented, false);
    assert.equal(visited.length, 1);
  } finally { globalThis.window = previous; }
});

const technical = { ...row, id: "interface", entity_type: "asset_interface", category: "newly_discovered", technical_identity: true, can_link_technical: true, link_asset_id: "accepted-owner" };
const interfaceCandidates = [
  { id: "eth0", asset_id: "accepted-owner", name: "eth0", mac_address: "02:00:00:00:00:01", ip_address: "192.0.2.8", network_id: "lan" },
  { id: "hidden", asset_id: "other-owner", name: "Hidden interface", mac_address: "02:00:00:00:00:ff" },
];
function renderTechnical(item = technical, extra = {}) {
  return renderToStaticMarkup(React.createElement(TechnicalIdentityLink, { item, technicalChoices: { [item.id]: { items: interfaceCandidates, loading: false } }, ...extra }));
}

test("technical linking identifies same-owner interfaces and requires an explicit valid selection", () => {
  const html = renderTechnical();
  assert.match(html, /Link existing interface/);
  assert.match(html, /for="technical-link-interface"/);
  assert.match(html, /id="technical-link-interface"/);
  assert.match(html, /eth0 · 02:00:00:00:00:01 · 192.0.2.8 · Network lan/);
  assert.doesNotMatch(html, /Hidden interface|00:ff/);
  assert.match(html, /disabled=""[^>]*>Link interface/);
  assert.doesNotMatch(renderTechnical(technical, { linkSelections: { interface: "eth0" } }), /disabled=""[^>]*>Link interface/);
  assert.match(renderTechnical(technical, { linkSelections: { interface: "hidden" } }), /disabled=""[^>]*>Link interface/);
  assert.match(renderTechnical(technical, { busy: true, linkSelections: { interface: "eth0" } }), /disabled=""[^>]*>Link interface/);
});

test("technical identity selection loads lazily and conveys owner prerequisites and empty/error states", () => {
  const calls = [];
  const control = TechnicalIdentityLink({ item: technical, loadTechnicalChoices: (...args) => calls.push(args) });
  control.props.onToggle({ currentTarget: { open: true } });
  assert.deepEqual(calls, [[technical, 0]]);
  const blocked = renderTechnical({ ...technical, can_link_technical: false, link_blocked_reason: "Accept or link the source Asset" });
  assert.match(blocked, /role="status">Accept or link the source Asset/);
  assert.doesNotMatch(blocked, /<select/);
  const empty = renderTechnical(technical, { technicalChoices: { interface: { items: [], loading: false } } });
  assert.match(empty, /No existing interfaces are available for this accepted asset/);
  assert.match(renderTechnical(technical, { technicalChoices: { interface: { error: "Refresh required" } } }), /role="alert">Refresh required/);
  assert.equal(renderTechnical({ ...technical, status: "accepted" }), "");
});

test("Network linking filters customer and site, and configuration review stays distinct", () => {
  const network = { ...technical, entity_type: "network", customer_id: "c", site_id: "s" };
  const html = renderTechnical(network, { technicalChoices: { interface: { items: [
    { id: "lan", customer_id: "c", site_id: "s", name: "LAN", cidr: "192.0.2.0/24", vlan_id: 9 },
    { id: "hidden", customer_id: "c", site_id: "other", name: "Hidden network" },
  ] } } });
  assert.match(html, /Link existing network/);
  assert.match(html, /LAN · 192.0.2.0\/24 · VLAN 9/);
  assert.doesNotMatch(html, /Hidden network/);
  const changed = { ...technical, technical_identity: false, category: "changed", assertion_predicate: "configuration", can_accept: true,
    proposed: { mac_address: "02:00:00:00:00:02" }, current: { mac_address: "02:00:00:00:00:01" } };
  const review = render({ ...entity, sections: [{ ...entity.sections[0], items: [changed] }] });
  assert.match(review, /Accepted configuration/);
  assert.match(review, /Observed configuration awaiting review/);
  assert.match(review, /Accept interface changes/);
  assert.doesNotMatch(review, /Link existing interface/);
});
