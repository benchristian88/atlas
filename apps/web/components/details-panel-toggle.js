"use client";
import { NavigationIcon } from "./navigation-icon.mjs";

export function DetailsPanelToggle({ hidden, onToggle }) {
  const label = hidden ? "Show details panel" : "Hide details panel";
  return <button type="button" className="button button-secondary graph-icon-button" title={label} aria-label={label} aria-pressed={!hidden} onClick={onToggle}><NavigationIcon name="panel-right" /></button>;
}
