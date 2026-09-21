"use client";

import { useId, useLayoutEffect, useRef, useState } from "react";
import { AssetIcon } from "./asset-icon";
import { connectivitySearchResults } from "../lib/infrastructure-topology.mjs";

// Search only the existing backend-authorized topology projection. It already
// includes visible interface addresses, so no second query or debounce is needed.
export function ConnectivityAssetSearch({ assets, types, value, onChange, onSelect, disabled }) {
  const listId = useId();
  const input = useRef(null);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const results = connectivitySearchResults(assets, value);
  const visible = open && Boolean(value.trim()) && !disabled;
  const active = visible ? results[activeIndex] : null;
  const activeId = active ? `${listId}-${active.id}` : undefined;
  useLayoutEffect(() => {
    if (activeId) document.getElementById(activeId)?.scrollIntoView({ block: "nearest" });
  }, [activeId]);
  const choose = asset => {
    onSelect(asset.id);
    onChange("");
    setOpen(false);
    setActiveIndex(-1);
    input.current?.focus({ preventScroll: true });
  };
  return <div className="field connectivity-asset-search" onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
  }}>
    <input ref={input} type="search" role="combobox" aria-label="Search assets"
      placeholder="Search assets…" autoComplete="off" value={value} disabled={disabled}
      aria-autocomplete="list" aria-expanded={visible} aria-controls={visible ? listId : undefined}
      aria-activedescendant={activeId}
      onClick={() => setOpen(true)}
      onFocus={() => setOpen(true)}
      onChange={event => { onChange(event.target.value); setOpen(true); setActiveIndex(-1); }}
      onKeyDown={event => {
        if (event.key === "Escape" && visible) {
          event.preventDefault(); event.stopPropagation(); setOpen(false); setActiveIndex(-1);
        } else if (["ArrowDown", "ArrowUp"].includes(event.key) && results.length) {
          event.preventDefault(); setOpen(true);
          const next = event.key === "ArrowDown" ? (activeIndex + 1) % results.length : (activeIndex <= 0 ? results.length : activeIndex) - 1;
          setActiveIndex(next);
        } else if (event.key === "Enter" && active && !event.nativeEvent.isComposing) {
          event.preventDefault(); choose(active);
        } else if (event.key === "Tab") setOpen(false);
      }} />
    {visible && <div className="connectivity-search-popup">
      <div id={listId} role="listbox" aria-label="Matching assets">
        {results.map((asset, index) => <div key={asset.id} id={`${listId}-${asset.id}`}
          role="option" aria-selected={activeIndex === index}
          className="connectivity-search-result"
          onPointerDown={event => { if (event.button === 0) event.preventDefault(); }}
          onClick={() => choose(asset)}>
          <AssetIcon asset={asset} assetType={types[asset.asset_type]} size={28} />
          <span><strong>{asset.name}</strong><small>{[types[asset.asset_type]?.name, asset.hostname, asset.display_ip].filter(Boolean).join(" · ")}</small></span>
        </div>)}
      </div>
      {!results.length && <p role="status">No assets found</p>}
    </div>}
  </div>;
}
