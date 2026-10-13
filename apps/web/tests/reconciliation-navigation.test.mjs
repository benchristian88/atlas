import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { loadComponent } from "./helpers/components.mjs";
import { reconciliationPagePath, reconciliationGroups } from "../lib/reconciliation-queues.mjs";

import {
  RECONCILIATION_QUEUES,
  reconciliationQueueFromValue,
} from "../lib/reconciliation-queues.mjs";

test("All Open is the canonical reconciliation route and invalid queues fall back safely", () => {
  const allOpen = reconciliationQueueFromValue(null);
  assert.equal(allOpen.key, "all-open");
  assert.equal(allOpen.href, "/reconciliation");
  assert.equal(reconciliationQueueFromValue("").key, "all-open");
  assert.equal(reconciliationQueueFromValue("unknown").key, "all-open");
  assert.equal(reconciliationQueueFromValue("missing-knowledge").key, "all-open");
});

test("reconciliation exposes only stable reconciliation queue links", () => {
  assert.deepEqual(RECONCILIATION_QUEUES.map((queue) => queue.key), [
    "all-open",
    "newly-discovered",
    "changed",
    "no-longer-observed",
    "contradictions",
    "possible-duplicates",
    "deferred",
    "resolved",
  ]);
  assert.equal(new Set(RECONCILIATION_QUEUES.map((queue) => queue.href)).size, RECONCILIATION_QUEUES.length);
  assert.equal(RECONCILIATION_QUEUES.some((queue) => queue.href.includes("missing-knowledge")), false);
});

test("client queue transitions use URL state and reset stale request state", async () => {
  const page = await readFile(new URL("../app/reconciliation/page.js", import.meta.url), "utf8");
  assert.match(page, /reconciliationQueueFromValue\(searchParams\.get\("queue"\)\)/);
  assert.match(page, /RECONCILIATION_QUEUES\.map/);
  assert.match(page, /requestId\.current/);
  assert.match(page, /setError\(""\)/);
  assert.doesNotMatch(page, /setTab|window\.location|router\.(push|replace)/);
});

const components = loadComponent(new URL("../components/reconciliation-cards.js", import.meta.url));
const parent = { id: "new", category: "newly_discovered", status: "open", entity_type: "asset", entity_name: "joomla-lab",
  customer_id: "customer", site_id: "site", data_source_id: "source", discovery_run_id: "run", candidate_external_id: "guest/lxc/1006", created_at: "2026-10-13T00:00:00Z" };
const fact = { ...parent, id: "fact", category: "changed", initial_entity_item_id: "new", assertion_predicate: "proxmox.vmid", observed_value_json: { field: "proxmox.vmid", value: 1006 } };

test("All Open and category queues follow bounded pages beyond 200 and preserve their union", () => {
  const rows = Array.from({ length: 237 }, (_, id) => ({ id, status: "open", category: ["newly_discovered", "changed", "contradiction"][id % 3] }));
  function browse(queue) {
    let cursor = null, found = [];
    do {
      const url = new URL(reconciliationPagePath(queue, cursor), "https://atlas.test");
      assert.equal(url.pathname, "/reconciliation-items/page");
      assert.equal(url.searchParams.get("limit"), "50");
      const matching = rows.filter(row => row.status === url.searchParams.get("status") && (!url.searchParams.has("category") || row.category === url.searchParams.get("category")));
      const start = url.searchParams.has("cursor") ? Number(url.searchParams.get("cursor")) : 0;
      found.push(...matching.slice(start, start + 50));
      cursor = start + 50 < matching.length ? String(start + 50) : null;
    } while (cursor);
    return found;
  }
  const all = browse(RECONCILIATION_QUEUES[0]);
  assert.equal(all.length, 237);
  assert.equal(new Set(all.map(row => row.id)).size, 237);
  const union = RECONCILIATION_QUEUES.filter(queue => queue.category).flatMap(browse);
  assert.deepEqual(new Set(union.map(row => row.id)), new Set(all.map(row => row.id)));
  assert.match(reconciliationPagePath(reconciliationQueueFromValue("resolved")), /status=resolved/);
});

test("paging follows the Assets footer and disabled edges", () => {
  const html = renderToStaticMarkup(React.createElement(components.ReconciliationPagination, { pageIndex: 0, hasMore: true }));
  assert.match(html, /class="pagination"/);
  assert.match(html, /button-secondary/);
  assert.match(html, /Previous<\/button><span>Page 1<\/span>/);
  assert.match(html, /disabled=""[^>]*>Previous/);
  const last = renderToStaticMarkup(React.createElement(components.ReconciliationPagination, { pageIndex: 4, hasMore: false }));
  assert.match(last, /Page 5/);
  assert.match(last, /disabled=""[^>]*>Next/);
});

test("new Asset and initial facts share presentation with independent decisions", () => {
  const html = renderToStaticMarkup(React.createElement(components.ReconciliationCards, { items: [fact, parent], canDecide: true }));
  assert.match(html, /New entity and initial facts: joomla-lab/);
  assert.match(html, /Initial source fact/);
  assert.match(html, /proxmox\.vmid/);
  assert.doesNotMatch(html, />changed</);
  assert.equal((html.match(/>Accept<\/button>/g) || []).length, 2);
  assert.match(html, /<summary>Initial source facts/);
  const acrossPage = reconciliationGroups([fact], [parent]);
  assert.equal(acrossPage[0].entity.id, parent.id);
  assert.deepEqual(acrossPage[0].facts, [fact]);
});

test("new Asset headings follow the API presentation name while grouping retains source identity", () => {
  const renamed = { ...parent, entity_name: "joomla-renamed" };
  for (const entity of [parent, renamed]) {
    const html = renderToStaticMarkup(React.createElement(components.ReconciliationCards, { items: [fact, entity] }));
    assert.ok(html.includes(`id="reconciliation-new">${entity.entity_name}</h2>`));
    assert.doesNotMatch(html, /<h2[^>]*>guest\/lxc\/1006<\/h2>/);
    const group = reconciliationGroups([fact, entity])[0];
    assert.equal(group.entity.candidate_external_id, "guest/lxc/1006");
    assert.deepEqual(group.facts, [fact]);
  }
});

test("later Changed facts and contradictions stay independent and actionable", () => {
  const later = { ...fact, id: "later", initial_entity_item_id: null };
  const contradiction = { ...fact, id: "contradiction", category: "contradiction" };
  const html = renderToStaticMarkup(React.createElement(components.ReconciliationCards, { items: [parent, fact, later, contradiction], canDecide: true }));
  assert.match(html, />changed</);
  assert.match(html, />contradiction</);
  assert.equal((html.match(/>Accept<\/button>/g) || []).length, 4);
  assert.equal(reconciliationGroups([parent, fact, later, contradiction]).length, 3);
});

test("presentation never groups across entity, source, run or tenant boundaries", () => {
  for (const [key, next] of [["candidate_external_id", "other/entity"], ["data_source_id", "other/source"], ["discovery_run_id", "other/run"], ["customer_id", "other/customer"], ["site_id", "other/site"]]) {
    const groups = reconciliationGroups([parent, { ...fact, [key]: next }]);
    assert.equal(groups.length, 2);
    assert.ok(groups.every(group => group.facts.length === 0));
  }
});
