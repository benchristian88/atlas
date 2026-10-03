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
  assert.deepEqual(accentThemeStyle(null), accentThemeStyle("#1A7F72"));
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
    assert.ok(contrastRatio(theme.focusRing, "#FFFFFF") >= 3);
    assert.match(theme.accentHover, /^#[0-9A-F]{6}$/);
    assert.match(theme.accentSoft, /^#[0-9A-F]{6}$/);
  }
});

test("accent text, controls and focus stay readable in either mode without changing surfaces", () => {
  for (const mode of ["light", "dark"]) {
    const backgrounds = mode === "dark" ? ["#131D23", "#1B272E", "#233139", "#102A2E"] : ["#F5F7F9", "#FFFFFF", "#F8FAFB"];
    for (const colour of [null, "#FFFFFF", "#FFFF00", "#000000", "#2563EB", "#7C3AED", "#DC2626"]) {
      const theme = deriveAccentTheme(colour, mode);
      for (const background of backgrounds) {
        assert.ok(contrastRatio(theme.accentText, background) >= 4.5);
        assert.ok(contrastRatio(theme.focusRing, background) >= 3);
      }
      assert.ok(contrastRatio(theme.accentSoft, theme.accentSoftForeground) >= 4.5);
      assert.ok(contrastRatio(theme.accentHover, theme.foreground) >= 4.5);
      const styles = accentThemeStyle(colour, mode);
      for (const token of ["--sidebar", "--surface", "--background"]) assert.equal(styles[token], undefined);
    }
  }
});

test("theme styles do not override semantic status variables", () => {
  const style = accentThemeStyle("#2563EB");
  assert.equal(style["--danger"], undefined);
  assert.equal(style["--warning"], undefined);
  assert.equal(style["--success"], undefined);
});
