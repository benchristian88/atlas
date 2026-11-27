import assert from "node:assert/strict";
import test from "node:test";
import { finishSetup, showcaseDestinations } from "../lib/onboarding-showcase.mjs";
import { parseGraphState } from "../lib/operations-experience.mjs";

test("exploration honors confirmed-context permissions and uses the existing analysis route", () => {
  const focus = "service:53ebb571-7f47-400c-adf1-c9e7bdaf04dc";
  assert.deepEqual(showcaseDestinations({ analysis_focus: focus }, () => false),
    { graph: null, topology: null, analysis: null });
  assert.deepEqual(showcaseDestinations({ analysis_focus: null }, permission => permission === "business_functions.view"),
    { graph: "/knowledge-graph", topology: null, analysis: null });
  const destinations = showcaseDestinations({ analysis_focus: focus }, () => true);
  assert.equal(destinations.topology, "/topology");
  const analysis = new URL(destinations.analysis, "https://atlas.test");
  assert.equal(analysis.pathname, destinations.graph);
  assert.equal(parseGraphState(analysis.searchParams).focus, focus);
  assert.equal(parseGraphState(analysis.searchParams).analysis, true);
});

function recovery({ completion, status }) {
  const calls = [];
  const controller = new AbortController();
  const run = () => finishSetup({
    version: 7, signal: controller.signal,
    complete: async () => { calls.push("POST"); return completion(); },
    read: async () => { calls.push("GET"); return status(); },
  });
  return { run, calls, controller };
}

const fail = status => () => { throw Object.assign(new Error("failed"), { status }); };

test("confirmed success and a definitive version conflict each issue one mutation", async () => {
  const progress = { status: "completed", version: 8 };
  const success = recovery({ completion: () => progress });
  assert.deepEqual(await success.run(), { progress });
  assert.deepEqual(success.calls, ["POST"]);
  const conflict = recovery({ completion: fail(409) });
  await assert.rejects(conflict.run(), { status: 409 });
  assert.deepEqual(conflict.calls, ["POST"]);
});

test("a lost response reads authoritative state once and does not attribute the completion to the request", async () => {
  const latest = { status: "completed", progress: { version: 8 }, can_manage: true };
  const lost = recovery({ completion: fail(), status: () => latest });
  assert.deepEqual(await lost.run(), { latest });
  assert.deepEqual(lost.calls, ["POST", "GET"]);
});

test("retry requires a fresh explicit action after authoritative verification, and unknown state requires reload", async () => {
  const active = recovery({
    completion: fail(502), status: () => ({ status: "in_progress", progress: { version: 7 }, can_manage: true }),
  });
  await assert.rejects(active.run(), /still in progress/);
  assert.deepEqual(active.calls, ["POST", "GET"]);
  const unknown = recovery({ completion: fail(200), status: fail(503) });
  await assert.rejects(unknown.run(), { status: 409, message: /Reload progress/ });
  assert.deepEqual(unknown.calls, ["POST", "GET"]);
});

test("an abandoned completion request cannot take over a later navigation", async () => {
  const abandoned = recovery({ completion: fail() });
  abandoned.controller.abort();
  assert.deepEqual(await abandoned.run(), {});
  assert.deepEqual(abandoned.calls, []);
});
