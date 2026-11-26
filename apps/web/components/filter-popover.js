"use client";

import { useId } from "react";
import { Button } from "./button";

export function FilterPopover({ activeCount, children }) {
  const id = useId();

  return <>
    <Button popoverTarget={id}>Filters{activeCount > 0 ? ` (${activeCount})` : ""}</Button>
    <div id={id} popover="auto" role="region" aria-label="Filters" className="filter-popover">
      {children}
    </div>
  </>;
}
