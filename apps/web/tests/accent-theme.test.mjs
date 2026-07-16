import test from "node:test";
import assert from "node:assert/strict";

import {
  accentThemeStyle,
  contrastRatio,
  deriveAccentTheme,
  normalizeAccentColour,
  readableForeground,
} from "../lib/accent-theme.mjs";

test("normalises valid colours and treats null as the Atlas default", () => {
  assert.equal(normalizeAccentColour(" #2563eb "), "#2563EB");
  assert.equal(normalizeAccentColour(null), null);
  assert.equal(accentThemeStyle(null), undefined);
});

for (const invalid of ["red", "#FFF", "#12345678", "rgb(1,2,3)", "#123456; color:red", "url(x)"]) {
  test(`rejects unsafe colour input: ${invalid}`, () => {
    assert.throws(() => normalizeAccentColour(invalid), /six-digit hexadecimal/i);
  });
}

test("chooses WCAG AA foregrounds for light and dark accents", () => {
  for (const colour of ["#FFFFFF", "#FFFF00", "#F3E8A1", "#172554", "#2563EB", "#1A7F72", "#000000"]) {
    const foreground = readableForeground(colour);
    assert.ok(contrastRatio(colour, foreground) >= 4.5);
  }
});

test("derived variants are deterministic and keep primary text readable", () => {
  assert.deepEqual(deriveAccentTheme("#7C3AED"), deriveAccentTheme("#7c3aed"));
  for (const colour of ["#FFFFFF", "#FFFF00", "#7C3AED", "#000000"]) {
    const theme = deriveAccentTheme(colour);
    assert.ok(contrastRatio(theme.accent, theme.foreground) >= 4.5);
    assert.ok(contrastRatio(theme.sidebar, theme.sidebarForeground) >= 4.5);
    assert.ok(contrastRatio(theme.sidebar, theme.sidebarMuted) >= 4.5);
    assert.ok(contrastRatio(theme.focusRing, "#FFFFFF") >= 3);
    assert.match(theme.accentHover, /^#[0-9A-F]{6}$/);
    assert.match(theme.accentSoft, /^#[0-9A-F]{6}$/);
  }
});

test("theme styles do not override semantic status variables", () => {
  const style = accentThemeStyle("#2563EB");
  assert.equal(style["--danger"], undefined);
  assert.equal(style["--warning"], undefined);
  assert.equal(style["--success"], undefined);
});
