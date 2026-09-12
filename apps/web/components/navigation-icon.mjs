import { createElement } from "react";

// Small inline line icons, following the existing EntityMark SVG convention.
const paths = {
  expand: "M8 3H3v5 M16 3h5v5 M3 16v5h5 M21 16v5h-5 M3 3l6 6 M21 3l-6 6 M3 21l6-6 M21 21l-6-6",
  close: "M6 6l12 12 M18 6 6 18",
  dashboard: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  changes: "M3 11a9 9 0 1 1 2 7 M3 4v7h7 M12 7v5l3 2",
  "knowledge-graph": "M4 4h4v4H4z M16 4h4v4h-4z M10 16h4v4h-4z M8 6h8 M6 8v4l6 4 6-4V8",
  assets: "M3 4h18v7H3z M3 14h18v7H3z M6 7.5h1 M6 17.5h1 M11 7.5h7 M11 17.5h7",
  services: "M12 3a9 9 0 1 0 0 18 9 9 0 1 0 0-18 M12 3c-5 5-5 13 0 18 5-5 5-13 0-18 M3 12h18 M5 7h14 M5 17h14",
  "business-functions": "M9 7V4h6v3 M3 7h18v14H3z M3 12l9 3 9-3 M10 14v3h4v-3",
  networks: "M9 3h6v6H9z M3 17h6v4H3z M15 17h6v4h-6z M12 9v4 M6 17v-4h12v4",
  discovery: "M11 3a8 8 0 1 0 0 16 8 8 0 1 0 0-16 M17 17l4 4 M7 11h8 M11 7v8",
  reconciliation: "M4 7h16l-4-4 M20 17H4l4 4 M20 7l-4 4 M4 17l4-4",
  "knowledge-gaps": "M12 3 2 21h20L12 3z M12 9v5 M12 17v1",
  integrations: "M8 3v5 M16 3v5 M6 8h12v4a6 6 0 0 1-12 0V8z M12 18v4",
  organisation: "M9 3a3 3 0 1 0 0 6 3 3 0 1 0 0-6 M2 21v-3a7 7 0 0 1 10-6 M18 11l4 2v4c0 2-4 4-4 4s-4-2-4-4v-4l4-2z",
  "reference-data": "M4 3h16v18H4z M4 9h16 M4 15h16 M10 3v18",
  "audit-log": "M5 3h14v18H5z M8 7h8 M8 11h8 M8 15h5",
  "system-settings": "M3 6h18 M3 12h18 M3 18h18 M7 3v6 M17 9v6 M10 15v6",
};

export function NavigationIcon({ name }) {
  if (!paths[name]) return null;
  return createElement("svg", {
    className: "nav-icon", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 1.7, strokeLinecap: "round",
    strokeLinejoin: "round", "aria-hidden": true, focusable: "false",
  }, createElement("path", { d: paths[name] }));
}
