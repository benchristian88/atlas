"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { PresentationIdentity } from "./presentation-identity.mjs";

// Reuse Atlas dropdown styling and dismissal conventions, with native checkboxes
// so multiple choices remain open and participate in the normal Tab order.
export function TopologyCategoryFilter({ categories, enabled, changedCount, open, onOpenChange, onChange, onReset }) {
  const id = useId();
  const root = useRef(null), trigger = useRef(null), panel = useRef(null);
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
    const dismiss = event => { if (!root.current?.contains(event.target)) onOpenChange(false); };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, [open, onOpenChange]);
  return <div className="topology-filter" ref={root}
    onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) onOpenChange(false); }}
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
        {categories.map(category => <label key={category.id}>
          <input type="checkbox" checked={enabled.has(category.id)} onChange={event => onChange(category.id, event.target.checked)} />
          <PresentationIdentity record={category} />{!category.active && <small>(inactive)</small>}
        </label>)}
      </div></fieldset>
      <button type="button" className="text-button" onClick={onReset}>Reset to defaults</button>
    </div>}
  </div>;
}
