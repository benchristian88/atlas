import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { INSTALLATION_LABELS, updateMessage, upgradeGuidance } from "../lib/updates.mjs";

test("updates present all normalized states without remote release bodies", () => {
  assert.equal(updateMessage({ status: "up_to_date" }), "Atlas is up to date.");
  assert.equal(updateMessage({ status: "update_available", latest_version: "0.2.0" }), "Atlas 0.2.0 is available.");
  assert.match(updateMessage({ status: "ahead_of_release" }), /ahead/);
  assert.match(updateMessage({ status: "unavailable" }), /currently unavailable/);
  assert.match(updateMessage(null), /currently unavailable/);
});

test("guidance is installation-specific with backup and preserved configuration", () => {
  assert.equal(INSTALLATION_LABELS.docker_compose, "Docker Compose");
  assert.match(upgradeGuidance("docker_compose"), /encrypted backup.*Docker Compose.*existing protected configuration/);
  assert.match(upgradeGuidance("systemd"), /encrypted backup.*native.*application state/);
  assert.match(upgradeGuidance("development"), /development Git workflow/);
});

test("Updates composes the adjacent System Settings card and shared controls", async () => {
  const page = await readFile(new URL("../app/admin/system-settings/page.js", import.meta.url), "utf8");
  const card = await readFile(new URL("../components/updates.js", import.meta.url), "utf8");
  assert.match(page, /<Updates buildInfo=\{buildInfo\}/);
  assert.match(card, /className="ops-card system-settings-section"/);
  assert.match(card, /aria-labelledby="settings-updates"/);
  assert.match(card, /role="status" aria-live="polite"/);
  assert.match(card, /\/system-settings\/updates\/check.*method: "POST"/);
  assert.match(card, /refresh_after_seconds/);
  assert.match(card, /rel="noopener noreferrer"/);
  assert.match(card, /prefetch=\{false\}/);
  assert.doesNotMatch(card, /dangerouslySetInnerHTML|github\.com|fetch\(|localStorage|process.env|Update now|systemctl|docker compose/);
});
