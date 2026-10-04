import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

test("About uses the sibling card, installed identity and safe fixed project links", async () => {
  const page = await readFile(new URL("../app/admin/system-settings/page.js", import.meta.url), "utf8");
  const about = page.slice(page.indexOf('aria-labelledby="settings-about"'));
  assert.match(about, /AGPL-3.0-only/);
  for (const field of ["version", "release_channel", "build_id", "install_method"]) {
    assert.ok(about.includes(`buildInfo.${field}`));
  }
  for (const destination of ["atlas\"", "docs/README.md", "SECURITY.md", "COMMERCIAL-LICENSING.md"]) {
    assert.ok(about.includes(destination));
  }
  assert.equal((about.match(/target="_blank" rel="noopener noreferrer"/g) || []).length, 4);
  assert.match(page, /className="ops-card system-settings-section" aria-labelledby="settings-about"/);
  assert.doesNotMatch(about, /fetch\(|dangerouslySetInnerHTML|process.env|Check for updates/);
});
