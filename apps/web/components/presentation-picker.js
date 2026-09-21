"use client";

import { PRESENTATION_ICONS, PRESENTATION_ACCENTS, presentationIcon, presentationAccent } from "../lib/presentation.mjs";
import { PresentationIcon } from "./presentation-identity.mjs";

export function PresentationPicker({ form, onChange, fallback = "infrastructure", disabled = false }) {
  const iconKey = presentationIcon(form.icon_key, fallback).key;
  const accentKey = presentationAccent(form.accent_key);
  return <div className="field-wide presentation-picker">
    <p className="ops-meta">Icon and accent identify this item. They do not indicate health or operational status.</p>
    <fieldset disabled={disabled}><legend>Icon</legend><div className="presentation-options">
      {PRESENTATION_ICONS.map(icon => <label key={icon.key}>
        <input type="radio" name="icon_key" value={icon.key} checked={iconKey === icon.key} onChange={() => onChange({ ...form, icon_key: icon.key })} />
        <PresentationIcon record={{ icon_key: icon.key, accent_key: accentKey }} /><span>{icon.label}</span>
      </label>)}
    </div></fieldset>
    <fieldset disabled={disabled}><legend>Accent</legend><div className="presentation-options">
      {PRESENTATION_ACCENTS.map(accent => <label key={accent}>
        <input type="radio" name="accent_key" value={accent} checked={accentKey === accent} onChange={() => onChange({ ...form, accent_key: accent })} />
        <PresentationIcon record={{ icon_key: iconKey, accent_key: accent }} /><span>{accent[0].toUpperCase() + accent.slice(1)}</span>
      </label>)}
    </div></fieldset>
    <div className="presentation-identity" aria-label="Presentation preview"><PresentationIcon record={{ icon_key: iconKey, accent_key: accentKey }} /><span>{form.name || "Preview"}</span></div>
  </div>;
}

export const presentationField = (fallback = "infrastructure") => ({
  name: "presentation", render: ({ form, setForm, disabled }) => <PresentationPicker form={form} onChange={setForm} fallback={fallback} disabled={disabled} />,
});
