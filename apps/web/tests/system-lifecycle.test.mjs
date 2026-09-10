import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { SYSTEM_GROUPS, SYSTEM_SECTIONS, systemSectionForPath, visibleSystemSections } from "../lib/system-navigation.mjs";
import { navigationItemIsActive, visibleNavigationGroups } from "../lib/navigation-model.mjs";

const access = (permissions) => ({
  customerId: "customer", siteId: "site",
  hasGlobalPermission: (key) => permissions.includes(key),
  hasPermissionInContext: (key, customer, site) => customer === "customer" && site === "site" && permissions.includes(key),
});

test("four System destinations cover every preserved route and nested profile", () => {
  assert.deepEqual(SYSTEM_GROUPS.map((group) => group.label), ["Organisation", "Reference Data", "Audit Log", "System Settings"]);
  for (const section of SYSTEM_SECTIONS) {
    const group = SYSTEM_GROUPS.find((group) => group.id === section.group);
    assert.equal(navigationItemIsActive(group, section.href), true);
    assert.equal(systemSectionForPath(`${section.href}/profile`).group, section.group);
    for (const other of SYSTEM_GROUPS.filter((item) => item !== group)) assert.equal(navigationItemIsActive(other, section.href), false);
  }
});

test("group tabs and sidebar choose the same authorized destination without restricted names", () => {
  for (const section of SYSTEM_SECTIONS) {
    const scoped = access([section.permission || section.globalPermission]);
    const tabs = visibleSystemSections(scoped);
    assert.deepEqual(tabs.map((tab) => tab.href), [section.href]);
    const sidebar = visibleNavigationGroups(scoped).find((group) => group.id === "system");
    assert.deepEqual(sidebar.items.map((item) => item.href), [section.href]);
  }
  assert.deepEqual(visibleSystemSections(access([])), []);
  const scopedUser = { ...access(["users.view", "system_settings.manage"]), hasGlobalPermission: () => false };
  assert.deepEqual(visibleSystemSections(scopedUser), []);
});

test("local System navigation is semantic and has no competing overview", async () => {
  const layout = await readFile(new URL("../app/admin/layout.js", import.meta.url), "utf8");
  assert.match(layout, /aria-current/);
  assert.match(layout, /useWorkspaceContext/);
  assert.match(layout, /section.group === group.id/);
  assert.doesNotMatch(layout, /Overview|Administration sections/);
});

test("System Settings provides truthful sections and package metadata without deployment configuration", async () => {
  const page = await readFile(new URL("../app/admin/system-settings/page.js", import.meta.url), "utf8");
  for (const title of ["General", "Backup &amp; Restore", "Updates", "About"]) assert.ok(page.includes(title));
  assert.match(page, /filter\(\(setting\) => !setting.sensitive\)/);
  assert.match(page, /packageMetadata.version/);
  assert.match(page, /Web package version/);
  assert.match(page, /Homelab Ready hardening/);
  assert.doesNotMatch(page, /process.env|DATABASE_URL|MASTER_KEY|replacement value|current secret/);
});

test("both lifecycle actions share a native modal with safe focus and server rechecking", async () => {
  const component = await readFile(new URL("../components/entity-delete-action.js", import.meta.url), "utf8");
  assert.match(component, /<dialog/);
  assert.match(component, /showModal\(\)/);
  assert.match(component, /autoFocus className="button button-secondary"/);
  assert.match(component, /aria-labelledby/);
  assert.match(component, /deletion-eligibility/);
  assert.match(component, /method: "DELETE"/);
  assert.match(component, /cannot be undone/);
  for (const kind of ["services", "business-functions"]) {
    const page = await readFile(new URL(`../app/${kind}/[id]/page.js`, import.meta.url), "utf8");
    assert.match(page, /<EntityDeleteAction/);
  }
});
