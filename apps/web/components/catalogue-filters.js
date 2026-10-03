"use client";

import { useEffect, useRef, useState } from "react";
import { FilterToolbar } from "./filter-toolbar";

export const CATALOGUE_SEARCH_DELAY = 300;

// Only typing schedules work. URL navigation and Clear cancel pending searches.
export function useCatalogueSearch(value, onSearch, resetKey = value) {
  const [draft, setDraft] = useState(value);
  const timer = useRef(null);
  const cancel = () => clearTimeout(timer.current);
  useEffect(() => {
    cancel();
    setDraft(value);
    return cancel;
  }, [value, resetKey]);
  function change(next) {
    cancel();
    setDraft(next);
    if (next.trim() !== value) timer.current = setTimeout(() => onSearch(next.trim()), CATALOGUE_SEARCH_DELAY);
  }
  function reset() { cancel(); setDraft(""); }
  return { draft, change, reset, cancel };
}

export function CatalogueFilters({ label, search, primary, activeCount, onClear, children }) {
  return <FilterToolbar className="catalogue-filters" gridClassName="catalogue-filter-grid" onSubmit={(event) => event.preventDefault()}>
    <label className={`field${primary ? "" : " field-wide"}`}><span className="sr-only">{label}</span><input type="search" placeholder={`${label}...`} value={search.draft} onChange={(event) => search.change(event.target.value)} /></label>
    {primary}
    <details className="catalogue-more-filters">
      <summary>Filters{activeCount > 0 ? ` (${activeCount})` : ""}</summary>
      {children}
    </details>
    {(search.draft || activeCount > 0) && <button className="text-button catalogue-clear" type="button" onClick={onClear}>Clear filters</button>}
  </FilterToolbar>;
}
