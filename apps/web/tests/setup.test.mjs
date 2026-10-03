import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { checkSession } from "../lib/session-state.mjs";

test("uninitialized route protection opens setup without granting a user session", async () => {
  const state = await checkSession(async () => { const error = new Error("Setup required"); error.status = 428; throw error; });
  assert.deepEqual(state, { status: "setup", user: null, error: null });
});

test("setup keeps credentials out of storage and URLs and reserves restore honestly", async () => {
  const page = await readFile(new URL("../app/setup/page.js", import.meta.url), "utf8");
  assert.doesNotMatch(page, /localStorage|sessionStorage|searchParams/);
  assert.match(page, /form.reset\(\)/);
  assert.match(page, /name="code" type="password"/);
  assert.match(page, /Restore backup — coming later/);
  assert.match(page, /<Button disabled>/);
  assert.match(page, /router.replace\("\/login"\)/);
  const shell = await readFile(new URL("../components/root-shell.js", import.meta.url), "utf8");
  assert.match(shell, /getSetupStatus/);
  assert.match(shell, /router.replace\("\/setup"\)/);
});
