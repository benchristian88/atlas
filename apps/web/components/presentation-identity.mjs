import { createElement as h } from "react";
import { NavigationIcon } from "./navigation-icon.mjs";
import { presentationIcon, presentationAttributes } from "../lib/presentation.mjs";

export function PresentationIcon({ record, fallback = "infrastructure" }) {
  const icon = presentationIcon(record?.icon_key, fallback);
  return h("span", { className: "presentation-icon", ...presentationAttributes(record), "data-presentation-icon": icon.key, "aria-hidden": true },
    h(NavigationIcon, { name: icon.navigation }));
}

export function PresentationIdentity({ record, fallback = "infrastructure" }) {
  return h("span", { className: "presentation-identity" },
    h(PresentationIcon, { record, fallback }), h("span", null, record?.name));
}
