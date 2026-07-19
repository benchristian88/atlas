import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

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
