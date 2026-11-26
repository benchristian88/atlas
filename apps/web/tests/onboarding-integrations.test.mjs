import { test } from "node:test";
import assert from "node:assert/strict";
import { continuationCandidate, mutationOutcomeUnknown, runAppearedSinceRead, runNeedsPolling } from "../lib/onboarding-integrations.mjs";

test("discovery continuation takes the first server-approved candidate independently of displayed history", () => {
  const retired = { id: "retired", run: { id: "old", status: "completed" }, continuation_run_id: null };
  const first = { id: "first", run: { id: "failed", status: "failed" }, continuation_run_id: "earlier-completed" };
  const second = { id: "second", run: { id: "queued", status: "pending" }, continuation_run_id: "queued" };
  assert.equal(continuationCandidate([retired, first, second]), first);
  assert.equal(continuationCandidate([retired, second]), second);
  assert.equal(continuationCandidate([retired]), null);
  assert.equal(continuationCandidate([]), null);
});

test("polling follows active intent until terminal dispatch settles", () => {
  assert.equal(runNeedsPolling({ status: "pending" }), true);
  assert.equal(runNeedsPolling({ status: "running" }), true);
  assert.equal(runNeedsPolling({ status: "cancelled", dispatch_state: "cancelling" }), true);
  assert.equal(runNeedsPolling({ status: "failed", dispatch_state: "settled" }), false);
  assert.equal(runNeedsPolling(null), false);
});

test("a definitive rejection can be retried but an uncertain write requires reconciliation", () => {
  for (const error of [{ kind: "network" }, { kind: "response", status: 200 }, { status: 408 }, { status: 503 }, new Error()]) {
    assert.equal(mutationOutcomeUnknown(error), true);
  }
  for (const status of [401, 403, 404, 409, 422]) assert.equal(mutationOutcomeUnknown({ status }), false);
});

test("preflight avoids another start when canonical history changed or execution is active", () => {
  const before = { id: "previous", status: "failed", dispatch_state: "settled" };
  const after = { id: "new", status: "completed", dispatch_state: "settled" };
  assert.equal(runAppearedSinceRead(null, before.id), false);
  assert.equal(runAppearedSinceRead(before, before.id), false);
  assert.equal(runAppearedSinceRead(after, before.id), true);
  assert.equal(runAppearedSinceRead({ ...before, dispatch_state: "running" }, before.id), true);
});
