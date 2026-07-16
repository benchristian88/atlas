import test from "node:test";
import assert from "node:assert/strict";

import {
  checkSession,
  checkingSessionState,
  publicSessionState,
} from "../lib/session-state.mjs";

const user = { id: "user-1", email: "admin@example.test", display_name: "Admin" };

test("session states distinguish checking and public routes", () => {
  assert.equal(checkingSessionState.status, "checking");
  assert.equal(publicSessionState.status, "public");
  assert.equal(publicSessionState.user, null);
});

test("a valid current user authenticates the protected shell", async () => {
  const state = await checkSession(async () => user);
  assert.deepEqual(state, { status: "authenticated", user, error: null });
});

test("an expected 401 becomes unauthenticated rather than remaining checking", async () => {
  const state = await checkSession(async () => {
    throw { status: 401, kind: "api", message: "Authentication required" };
  });
  assert.deepEqual(state, { status: "unauthenticated", user: null, error: null });
});

for (const failure of [
  { status: 404, kind: "api", expected: "not found" },
  { status: 500, kind: "api", expected: "could not complete" },
  { status: null, kind: "network", expected: "Could not reach" },
]) {
  test(`${failure.kind} ${failure.status ?? "failure"} becomes a visible error`, async () => {
    const state = await checkSession(async () => { throw failure; });
    assert.equal(state.status, "error");
    assert.equal(state.user, null);
    assert.match(state.error, new RegExp(failure.expected, "i"));
  });
}

test("retry performs a fresh check and can authenticate", async () => {
  let calls = 0;
  const getCurrentUser = async () => {
    calls += 1;
    if (calls === 1) throw { status: 503, kind: "api" };
    return user;
  };
  const first = await checkSession(getCurrentUser);
  const second = await checkSession(getCurrentUser);
  assert.equal(first.status, "error");
  assert.equal(second.status, "authenticated");
  assert.equal(calls, 2);
});

test("unknown exceptions do not expose arbitrary internal messages", async () => {
  const state = await checkSession(async () => {
    throw new Error("internal implementation detail");
  });
  assert.equal(state.error, "Atlas could not verify your session.");
});

test("effect cleanup suppresses an async state result", async () => {
  let resolve;
  let active = true;
  const pendingUser = new Promise((done) => { resolve = done; });
  const result = checkSession(() => pendingUser, () => active);
  active = false;
  resolve(user);
  assert.equal(await result, null);
});
