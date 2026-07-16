import { ATLAS_DEFAULT_ACCENT, normalizeAccentColour } from "./accent-theme.mjs";

export function accentPreferenceFromSelection(value) {
  if (value === null) {
    return { input: ATLAS_DEFAULT_ACCENT, preference: null, error: "" };
  }
  const normalized = normalizeAccentColour(value);
  return { input: normalized, preference: normalized, error: "" };
}

export function accentPreferenceFromText(value, currentPreference = null) {
  try {
    const normalized = normalizeAccentColour(value);
    return { input: value, preference: normalized, error: "" };
  } catch (error) {
    return {
      input: value,
      preference: currentPreference || ATLAS_DEFAULT_ACCENT,
      error: error.message,
    };
  }
}

export function appearanceProfilePayload(displayName, state) {
  return {
    display_name: displayName,
    accent_colour: state.preference === null
      ? null
      : normalizeAccentColour(state.input),
  };
}
