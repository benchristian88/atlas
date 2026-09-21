"use client";

import { useEffect, useId, useRef, useState } from "react";
import { PRESENTATION_ICONS, PRESENTATION_ACCENTS, presentationIcon, presentationAccent } from "../lib/presentation.mjs";
import { PresentationIcon } from "./presentation-identity.mjs";

const accentOptions = PRESENTATION_ACCENTS.map(key => ({ key, label: key[0].toUpperCase() + key.slice(1) }));

// Uses the AccountMenu button/menu pattern and dropdown styles for both controls.
function PresentationChoice({ label, options, value, onChange, renderIcon, disabled }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [placement, setPlacement] = useState({});
  const rootRef = useRef(null);
  const triggerRef = useRef(null);
  const menuRef = useRef(null);
  const selected = options.find(option => option.key === value);

  useEffect(() => {
    if (!open) return;
    menuRef.current?.querySelector('[aria-checked="true"]')?.focus();
    function dismissOutside(event) {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    }
    document.addEventListener("pointerdown", dismissOutside);
    return () => document.removeEventListener("pointerdown", dismissOutside);
  }, [open]);

  function openMenu() {
    const rect = triggerRef.current.getBoundingClientRect();
    const below = window.innerHeight - rect.bottom - 16;
    const above = rect.top - 16;
    const upwards = below < 300 && above > below;
    setPlacement({ top: upwards ? "auto" : "calc(100% + 7px)", bottom: upwards ? "calc(100% + 7px)" : "auto", maxHeight: Math.min(320, upwards ? above : below) });
    setOpen(true);
  }

  function closeMenu() {
    setOpen(false);
    triggerRef.current?.focus();
  }

  function handleKeyDown(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      closeMenu();
    } else if (event.key === "Tab") {
      // Resume the form's normal tab order from the originating control.
      closeMenu();
    } else if (["ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const items = [...menuRef.current.querySelectorAll('[role="menuitemradio"]')];
      const index = items.indexOf(document.activeElement);
      const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1
        : (index + (["ArrowUp", "ArrowLeft"].includes(event.key) ? -1 : 1) + items.length) % items.length;
      items[next]?.focus();
    }
  }

  return <div className="field presentation-choice" ref={rootRef} onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
  }}>
    <span id={`${id}-label`}>{label}</span>
    <button type="button" className="presentation-choice-trigger" ref={triggerRef} disabled={disabled}
      aria-labelledby={`${id}-label ${id}-value`} aria-haspopup="menu" aria-expanded={open} aria-controls={open ? `${id}-menu` : undefined}
      onClick={() => open ? closeMenu() : openMenu()}
      onKeyDown={event => {
        if (["ArrowDown", "ArrowUp"].includes(event.key)) { event.preventDefault(); openMenu(); }
      }}>
      {renderIcon(value)}<span id={`${id}-value`}>{selected.label}</span><span className="presentation-choice-chevron" aria-hidden="true">⌄</span>
    </button>
    {open && <div className="account-dropdown presentation-choice-menu" style={placement} id={`${id}-menu`} ref={menuRef} role="menu" aria-label={`Choose ${label.toLowerCase()}`} onKeyDown={handleKeyDown}>
      {options.map(option => <button type="button" role="menuitemradio" aria-checked={option.key === value} tabIndex={-1}
        className="account-dropdown-item presentation-choice-option" key={option.key}
        onClick={() => { onChange(option.key); closeMenu(); }}>
        {renderIcon(option.key)}<span>{option.label}</span><span className="presentation-choice-check" aria-hidden="true">{option.key === value ? "✓" : ""}</span>
      </button>)}
    </div>}
  </div>;
}

export function PresentationPicker({ form, onChange, fallback = "infrastructure", disabled = false }) {
  const iconKey = presentationIcon(form.icon_key, fallback).key;
  const accentKey = presentationAccent(form.accent_key);
  return <fieldset className="field-wide presentation-picker" disabled={disabled}>
    <legend>Presentation</legend>
    <div className="form-grid">
      <PresentationChoice label="Icon" options={PRESENTATION_ICONS} value={iconKey} disabled={disabled}
        onChange={key => onChange({ ...form, icon_key: key })}
        renderIcon={key => <PresentationIcon record={{ icon_key: key, accent_key: accentKey }} />} />
      <PresentationChoice label="Accent" options={accentOptions} value={accentKey} disabled={disabled}
        onChange={key => onChange({ ...form, accent_key: key })}
        renderIcon={key => <span className="presentation-swatch" data-presentation-accent={key} aria-hidden="true" />} />
    </div>
    <div className="presentation-identity" aria-label="Presentation preview"><PresentationIcon record={{ icon_key: iconKey, accent_key: accentKey }} /><span>{form.name || "Preview"}</span></div>
    <p className="ops-meta">Used for topology presentation only.</p>
  </fieldset>;
}

export const presentationField = (fallback = "infrastructure") => ({
  name: "presentation", render: ({ form, setForm, disabled }) => <PresentationPicker form={form} onChange={setForm} fallback={fallback} disabled={disabled} />,
});
