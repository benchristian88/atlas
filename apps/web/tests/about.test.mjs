import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

test("About opens System Settings with the approved description and project resources", async () => {
  const page = await readFile(new URL("../app/admin/system-settings/page.js", import.meta.url), "utf8");
  assert.match(page, /aria-labelledby="settings-about"[\s\S]*aria-labelledby="settings-general"[\s\S]*<BackupRestore \/>[\s\S]*<Updates /);
  const about = page.match(/<section className="ops-card system-settings-section" aria-labelledby="settings-about">[\s\S]*?<\/section>/)?.[0];
  assert.ok(about);
  assert.match(about, /<h2 id="settings-about">About<\/h2>\s*<p[^>]*>Atlas Impact is an infrastructure knowledge, documentation and topology platform for homelabs, internal IT teams and MSPs\. It connects discovered technical assets to services, business functions, evidence and recovery context so operational questions can be answered from one model\.<\/p>/);
  const project = "https://github.com/benchristian88/atlas";
  for (const [path, name] of [
    ["/blob/dev/LICENSE", "AGPL-3.0-only licence"],
    ["", "Source code"],
    ["/blob/dev/docs/README.md", "Operator and developer guides"],
    ["/blob/dev/SECURITY.md", "Security reporting policy"],
    ["/blob/dev/COMMERCIAL-LICENSING.md", "Commercial licensing information"],
  ]) {
    assert.ok(about.includes(`href="${project}${path}" target="_blank" rel="noopener noreferrer">${name}</a>`));
  }
  assert.doesNotMatch(about, /buildInfo|Release channel|Installation|<dl|Check for updates/);
});
