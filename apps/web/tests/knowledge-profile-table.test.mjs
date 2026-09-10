import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");

test("both profiles use the shared requirement layout and preserve typed API/lifecycle paths", async () => {
  for (const entity of ["asset", "service"]) {
    const page = await read(`../app/admin/${entity}-types/[id]/knowledge-profile/page.js`);
    assert.match(page, /<KnowledgeProfileTable requirements=\{requirements\}/);
    assert.ok(page.includes(`apiRequest(\`/${entity}-types/\${id}/knowledge-requirements\`)`));
    assert.match(page, /hasGlobalPermission\("knowledge_requirements.manage"\)/);
    assert.match(page, /item.active \? "deactivate" : "activate"/);
    assert.match(page, /onToggle=\{toggle\} onRemove=\{remove\}/);
    assert.doesNotMatch(page, /Default C1/);
  }
});

test("shared profile table separates name and description, scope groups and secondary actions", async () => {
  const table = await read("../components/knowledge-profile-table.js");
  assert.match(table, /<div className="table-cell-identity"><strong>\{item.name\}<\/strong><small className="secondary-text">/);
  for (const label of ["Global requirements", "Type-specific requirements", "Global default", "Reactivate"]) assert.ok(table.includes(label));
  assert.match(table, /className="profile-rule secondary-text">\{item.rule_summary\}/);
  assert.match(table, /scope="rowgroup"/);
  assert.match(table, /role="region"[^>]*tabIndex=\{0\}/);
  assert.match(table, /canManage && <td>/);
  assert.match(table, /item\[scopeKey\] === typeId && <button className="text-button text-danger"/);
});

test("profile wrapping and muted styles use shared theme tokens", async () => {
  const css = await read("../app/globals.css");
  assert.match(css, /\.knowledge-profile-table th, \.knowledge-profile-table td \{[^}]*white-space: normal; overflow-wrap: anywhere;/);
  assert.match(css, /\.knowledge-profile-table \.table-cell-identity \{ gap: 6px; \}/);
  assert.match(css, /\.knowledge-profile-table \.table-cell-identity small, \.knowledge-profile-table \.profile-rule \{ font-size: 12px; line-height: 1.5; \}/);
  assert.match(css, /\.knowledge-profile-table \.status-badge[^\n]*background: var\(--surface-muted\); color: var\(--muted\);/);
});
