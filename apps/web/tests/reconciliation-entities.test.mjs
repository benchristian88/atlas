import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { loadComponent } from "./helpers/components.mjs";
import { reconciliationEntityPagePath, reconciliationQueueFromValue, reconciliationReviewHref, reconciliationReturnHref } from "../lib/reconciliation-queues.mjs";

const { ReconciliationEntityCard, ReconciliationReviewLink } = loadComponent(new URL("../components/reconciliation-cards.js", import.meta.url));
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
