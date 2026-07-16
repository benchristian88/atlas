import test from "node:test";
import assert from "node:assert/strict";

import {
  accentPreferenceFromSelection,
  accentPreferenceFromText,
  appearanceProfilePayload,
} from "../lib/accent-preference.mjs";

test("picker and preset selection synchronise the hex value", () => {
  assert.deepEqual(accentPreferenceFromSelection("#2563eb"), {
    input: "#2563EB", preference: "#2563EB", error: "",
  });
});

test("valid text input synchronises the preview preference", () => {
  const state = accentPreferenceFromText("#0f766e");
  assert.equal(state.input, "#0f766e");
  assert.equal(state.preference, "#0F766E");
  assert.equal(state.error, "");
});

test("invalid text keeps a safe preview and returns a validation error", () => {
  const state = accentPreferenceFromText("red", "#2563EB");
  assert.equal(state.input, "red");
  assert.equal(state.preference, "#2563EB");
  assert.match(state.error, /six-digit hexadecimal/i);
});

test("reset selects the database-null Atlas default", () => {
  const state = accentPreferenceFromSelection(null);
  assert.equal(state.preference, null);
  assert.equal(state.input, "#1A7F72");
  assert.deepEqual(appearanceProfilePayload("Atlas User", state), {
    display_name: "Atlas User",
    accent_colour: null,
  });
});

test("save payload uses the existing profile API shape", () => {
  const state = accentPreferenceFromSelection("#7C3AED");
  assert.deepEqual(appearanceProfilePayload("Atlas User", state), {
    display_name: "Atlas User",
    accent_colour: "#7C3AED",
  });
});
