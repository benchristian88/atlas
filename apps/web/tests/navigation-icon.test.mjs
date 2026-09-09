import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { NavigationIcon } from "../components/navigation-icon.mjs";
import { visibleNavigationGroups } from "../lib/navigation-model.mjs";

test("every available sidebar destination has a consistent decorative icon", () => {
  const groups = visibleNavigationGroups({ hasGlobalPermission: () => true, hasPermissionInContext: () => true });
  for (const item of groups.flatMap((group) => group.items)) {
    const markup = renderToStaticMarkup(React.createElement(NavigationIcon, { name: item.id }));
    assert.match(markup, /<svg/, item.id);
    assert.match(markup, /aria-hidden="true"/);
    assert.match(markup, /focusable="false"/);
    assert.match(markup, /stroke="currentColor"/);
  }
});
