import test from "node:test";
import assert from "node:assert/strict";
import { DISCOVERY_SCHEDULES, discoveryControls, discoveryDuration } from "../lib/discovery.mjs";

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
