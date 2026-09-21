"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { PresentationIdentity } from "./presentation-identity.mjs";

// Reuse Atlas dropdown styling and dismissal conventions, with native checkboxes
// so multiple choices remain open and participate in the normal Tab order.
export function TopologyCategoryFilter({ categories, enabled, changedCount, open, onOpenChange, onChange, onReset, layers = [], enabledLayers, onLayerChange }) {
  const id = useId();
  const root = useRef(null), trigger = useRef(null), panel = useRef(null);
  const pointerInside = useRef(false);
  const [placement, setPlacement] = useState({});
  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const rect = trigger.current.getBoundingClientRect();
      const width = Math.min(380, window.innerWidth - 32);
      const below = window.innerHeight - rect.bottom - 16;
      const above = rect.top - 16;
      const upwards = below < 260 && above > below;
      setPlacement({ width, left: Math.max(16 - rect.left, rect.width - width), right: "auto",
        top: upwards ? "auto" : "calc(100% + 7px)", bottom: upwards ? "calc(100% + 7px)" : "auto",
        maxHeight: Math.max(100, Math.min(400, upwards ? above : below)) });
    };
    place();
    panel.current?.querySelector("input")?.focus({ preventScroll: true });
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const dismiss = event => {
      pointerInside.current = Boolean(root.current?.contains(event.target));
      if (!pointerInside.current) onOpenChange(false);
    };
    const endPointer = () => { pointerInside.current = false; };
    document.addEventListener("pointerdown", dismiss);
    document.addEventListener("pointerup", endPointer);
    document.addEventListener("pointercancel", endPointer);
    return () => {
      document.removeEventListener("pointerdown", dismiss);
      document.removeEventListener("pointerup", endPointer);
      document.removeEventListener("pointercancel", endPointer);
      endPointer();
    };
  }, [open, onOpenChange]);
  return <div className="topology-filter" ref={root}
    onBlur={event => {
      // A label's mousedown can focus the surrounding dialog before its native
      // click focuses/toggles the input. Keep it mounted through that interaction.
      if (!pointerInside.current && !event.currentTarget.contains(event.relatedTarget)) onOpenChange(false);
    }}
    onKeyDown={event => {
      if (open && event.key === "Escape") {
        event.preventDefault(); event.stopPropagation();
        onOpenChange(false); trigger.current?.focus({ preventScroll: true });
      }
    }}>
    <button ref={trigger} type="button" className="button button-secondary" disabled={!categories.length}
      aria-expanded={open} aria-controls={open ? id : undefined} onClick={() => onOpenChange(!open)}>
      Filters{changedCount > 0 && ` · ${changedCount}`}
    </button>
    {open && <div ref={panel} id={id} className="account-dropdown topology-filter-popover" style={placement}>
      <fieldset><legend>Asset categories</legend><div className="topology-filter-options">
        {categories.map(category => <label key={category.id} htmlFor={`${id}-${category.id}`}>
          <input id={`${id}-${category.id}`} type="checkbox" checked={enabled.has(category.id)} onChange={event => onChange(category.id, event.target.checked)} />
          <PresentationIdentity record={category} />{!category.active && <small>(inactive)</small>}
        </label>)}
      </div></fieldset>
      {layers.length > 0 && <fieldset><legend>Relationship layers</legend><div className="topology-filter-options">
        {layers.map(layer => <label key={layer.key} htmlFor={`${id}-layer-${layer.key}`}>
          <input id={`${id}-layer-${layer.key}`} type="checkbox" checked={enabledLayers.has(layer.key)} onChange={event => onLayerChange(layer.key, event.target.checked)} />
          {layer.label}
        </label>)}
      </div></fieldset>}
      <button type="button" className="text-button" onClick={onReset}>Reset to defaults</button>
    </div>}
  </div>;
}
