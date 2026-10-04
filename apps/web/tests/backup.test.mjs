import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { backupValidation, canManageBackups, MAX_BACKUP_BYTES, restoreFileValidation } from "../lib/backup.mjs";

test("backup uses length and confirmation without arbitrary complexity rules", () => {
  assert.equal(backupValidation("several unrelated words", "several unrelated words"), "");
  assert.match(backupValidation("short", "short"), /12/);
  assert.match(backupValidation("several unrelated words", "different words"), /match/);
});
test("backup controls require the protected global Master assignment", () => {
  const assignment = { role_name: "Master Administrator", scope_type: "global", permissions: ["system_settings.manage"] };
  assert.equal(canManageBackups({ assignments: [assignment] }), true);
  assert.equal(canManageBackups({ assignments: [{ ...assignment, scope_type: "customer" }] }), false);
  assert.equal(canManageBackups({ assignments: [{ ...assignment, role_name: "Administrator" }] }), false);
  assert.equal(canManageBackups({ assignments: [assignment], force_password_change: true }), false);
});
test("restore bounds file size without trusting MIME labels", () => {
  assert.match(restoreFileValidation(null), /Choose/);
  assert.match(restoreFileValidation({ size: MAX_BACKUP_BYTES + 1 }), /2 GiB/);
  assert.equal(restoreFileValidation({ size: 512, type: "unknown" }), "");
});
test("backup and fresh restore share credential-safe forms and scoped polling", async () => {
  const component = await readFile(new URL("../components/backup-restore.js", import.meta.url), "utf8");
  assert.match(component, /form.reset\(\)/);
  assert.doesNotMatch(component, /localStorage|sessionStorage|console\.|URLSearchParams/);
  assert.match(component, /\/restore-status\//);
  assert.match(component, /pattern="RESTORE"/);
  assert.match(component, /prefetch=\{false\}/);
  assert.match(component, /Atlas cannot recover this backup if the passphrase is lost/);
  assert.match(component, /window.location.replace\("\/login"\)/);
  assert.match(component, /apiRequest\("\/auth\/mfa\/status"/);
  assert.match(component, /mfaStatus.enabled/);
});
