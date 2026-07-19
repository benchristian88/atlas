import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import {
  NAVIGATION_GROUPS,
  navigationItemIsActive,
  visibleNavigationGroups,
} from "../lib/navigation-model.mjs";

function access({ context = [], global = [] } = {}) {
  const contextPermissions = new Set(context);
  const globalPermissions = new Set(global);
  return {
    customerId: "customer-1",
    siteId: "site-1",
    hasGlobalPermission: (permission) => globalPermissions.has(permission),
    hasPermissionInContext: (permission) => (
      contextPermissions.has(permission) || globalPermissions.has(permission)
    ),
  };
}

function groupMap(groups) {
  return Object.fromEntries(groups.map((group) => [
    group.label,
    group.items.map((item) => item.label),
  ]));
}

function resolvedItem(groups, id) {
  return groups.flatMap((group) => group.items).find((item) => item.id === id);
}

test("viewer navigation uses implemented product domains without administration", () => {
  const groups = visibleNavigationGroups(access({
    context: [
      "customers.view",
      "sites.view",
      "assets.view",
      "relationships.view",
      "networks.view",
      "integrations.view",
      "asset_types.view",
      "relationship_types.view",
      "custom_fields.view",
      "changes.view",
      "reconciliation.view",
      "knowledge_gaps.view",
      "services.view",
      "business_functions.view",
    ],
  }));

  assert.deepEqual(groupMap(groups), {
    Overview: ["Dashboard", "Changes"],
    Knowledge: ["Knowledge Graph", "Assets", "Services", "Business Functions", "Networks"],
    Operations: ["Discovery", "Reconciliation", "Knowledge Gaps"],
    Connections: ["Integrations"],
  });
  assert.equal(resolvedItem(groups, "users-access"), undefined);
  assert.equal(resolvedItem(groups, "reference-data"), undefined);
  assert.equal(resolvedItem(groups, "administration"), undefined);
});

test("system entries resolve only for their explicit permissions", () => {
  const userManager = visibleNavigationGroups(access({ global: ["users.view"] }));
  assert.equal(resolvedItem(userManager, "users-access").href, "/admin/users");
  assert.equal(resolvedItem(userManager, "reference-data"), undefined);

  const roleViewer = visibleNavigationGroups(access({ global: ["roles.view"] }));
  assert.equal(resolvedItem(roleViewer, "users-access").href, "/admin/roles");

  const scopedReferenceAdmin = visibleNavigationGroups(access({ context: ["customers.manage"] }));
  assert.equal(resolvedItem(scopedReferenceAdmin, "reference-data").href, "/admin/customers");
  assert.equal(resolvedItem(scopedReferenceAdmin, "administration"), undefined);

  const globalReferenceAdmin = visibleNavigationGroups(access({ global: ["asset_types.manage"] }));
  assert.equal(resolvedItem(globalReferenceAdmin, "reference-data").href, "/admin/asset-types");

  const systemAdministrator = visibleNavigationGroups(access({ global: ["system_settings.manage"] }));
  assert.equal(resolvedItem(systemAdministrator, "administration").href, "/admin");
});

test("active matching covers renamed pages, child routes, and admin domains", () => {
  const allGroups = visibleNavigationGroups(access({
    context: ["assets.view", "services.view", "business_functions.view", "integrations.view", "customers.manage", "reconciliation.view", "knowledge_gaps.view", "changes.view"],
    global: ["users.view", "asset_types.manage", "system_settings.manage"],
  }));
  const cases = [
    ["knowledge-graph", "/topology"],
    ["knowledge-graph", "/topology/focus/asset-1"],
    ["discovery", "/discovery-runs/run-1"],
    ["discovery", "/discovery/simulate"],
    ["reconciliation", "/reconciliation"],
    ["knowledge-gaps", "/knowledge-gaps"],
    ["services", "/services/service-1"],
    ["business-functions", "/business-functions/function-1"],
    ["users-access", "/admin/roles/role-1"],
    ["reference-data", "/admin/custom-fields/field-1"],
    ["administration", "/admin"],
    ["administration", "/admin/system-settings"],
  ];

  for (const [itemId, pathname] of cases) {
    assert.equal(navigationItemIsActive(resolvedItem(allGroups, itemId), pathname), true);
  }
});

test("operations entries retain independent permission visibility", () => {
  const reconciliationOnly = visibleNavigationGroups(access({ context: ["reconciliation.view"] }));
  assert.equal(resolvedItem(reconciliationOnly, "reconciliation")?.href, "/reconciliation");
  assert.equal(resolvedItem(reconciliationOnly, "knowledge-gaps"), undefined);

  const gapsOnly = visibleNavigationGroups(access({ context: ["knowledge_gaps.view"] }));
  assert.equal(resolvedItem(gapsOnly, "reconciliation"), undefined);
  assert.equal(resolvedItem(gapsOnly, "knowledge-gaps")?.href, "/knowledge-gaps");
});

test("roadmap entries remain representable but never render broken links", () => {
  const roadmapLabels = NAVIGATION_GROUPS
    .flatMap((group) => group.items)
    .filter((item) => item.available === false)
    .map((item) => item.label);
  const visibleLabels = visibleNavigationGroups(access({
    context: ["customers.view", "assets.view", "networks.view", "integrations.view"],
    global: ["users.view", "roles.view", "asset_types.manage", "system_settings.manage"],
  })).flatMap((group) => group.items.map((item) => item.label));

  assert.deepEqual(roadmapLabels, [
    "People & Teams",
    "Impact Analysis",
    "Backup & Recovery",
    "Documentation",
  ]);
  assert.equal(roadmapLabels.some((label) => visibleLabels.includes(label)), false);
  assert.equal(visibleLabels.includes("Administration"), true);
});

test("shell regression keeps workspace context, profile access, and logout intact", async () => {
  const shell = await readFile(new URL("../components/app-shell.js", import.meta.url), "utf8");
  const accountMenu = await readFile(new URL("../components/account-menu.js", import.meta.url), "utf8");
  const navigation = await readFile(new URL("../components/navigation.js", import.meta.url), "utf8");
  const topologyPage = await readFile(new URL("../app/topology/page.js", import.meta.url), "utf8");
  const discoveryPage = await readFile(new URL("../app/discovery-runs/page.js", import.meta.url), "utf8");

  assert.match(shell, /<ContextSelector \/>/);
  assert.match(shell, /<AccountMenu/);
  assert.match(shell, /await logout\(\)/);
  assert.match(accountMenu, /href="\/profile"/);
  assert.match(shell, /<Navigation \/>/);
  assert.match(navigation, /customerId/);
  assert.match(navigation, /siteId/);
  assert.match(navigation, /aria-current/);
  assert.doesNotMatch(navigation, /PROFILE_NAVIGATION_ITEM|nav-profile/);
  assert.match(topologyPage, /title="Knowledge Graph"/);
  assert.match(discoveryPage, /title="Discovery"/);
});
