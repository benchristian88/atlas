import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import {
  initialsForName,
  primaryRoleLabel,
  validAvatarUrl,
} from "../lib/user-presentation.mjs";

test("user presentation derives safe initials, roles, and avatar URLs", () => {
  assert.equal(initialsForName("Ben Atlas"), "BA");
  assert.equal(initialsForName("ben@example.com"), "BE");
  assert.equal(initialsForName(""), "?");
  assert.equal(primaryRoleLabel({ roles: ["Administrator"] }), "Administrator");
  assert.equal(primaryRoleLabel({ assignments: [{ role_name: "Viewer" }] }), "Viewer");
  assert.equal(primaryRoleLabel({ permissions: ["assets.manage"] }), "Administrator");
  assert.equal(validAvatarUrl("javascript:alert(1)"), null);
  assert.equal(validAvatarUrl("/avatars/user.png"), "/avatars/user.png");
});

test("account menu is accessible, keyboard operable, and reuses profile/logout flows", async () => {
  const menu = await readFile(new URL("../components/account-menu.js", import.meta.url), "utf8");
  assert.match(menu, /aria-haspopup="menu"/);
  assert.match(menu, /aria-expanded=/);
  assert.match(menu, /Open user menu for/);
  assert.match(menu, /event\.key === "Escape"/);
  assert.match(menu, /pointerdown/);
  assert.match(menu, /ArrowDown/);
  assert.match(menu, /href="\/profile"/);
  assert.match(menu, /My profile/);
  assert.match(menu, /role="separator"/);
  assert.match(menu, /await onLogout\(\)/);
});

test("avatar falls back after image failure and narrow layouts retain the trigger", async () => {
  const avatar = await readFile(new URL("../components/user-avatar.js", import.meta.url), "utf8");
  const styles = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.match(avatar, /onError=\{\(\) => setImageFailed\(true\)\}/);
  assert.match(avatar, /initialsForName/);
  assert.match(styles, /\.account-trigger-copy \{ display: none; \}/);
  assert.match(styles, /\.account-menu-trigger:focus-visible/);
});

test("profile remains directly routable with existing account sections", async () => {
  const profile = await readFile(new URL("../app/profile/page.js", import.meta.url), "utf8");
  assert.match(profile, /title="My profile"/);
  assert.match(profile, /Personal details/);
  assert.match(profile, /changePassword/);
  assert.match(profile, /saveAppearance/);
  assert.match(profile, /updateUser/);
});
