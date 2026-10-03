import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { PRESENTATION_ICONS, PRESENTATION_ACCENTS, presentationIcon, presentationAccent } from "../lib/presentation.mjs";
import { PresentationIdentity, PresentationIcon } from "../components/presentation-identity.mjs";
import { contrastRatio } from "../lib/accent-theme.mjs";
import { topologyPresentation } from "../lib/infrastructure-topology.mjs";

test("bounded shared registry renders all icons with safe historical fallbacks", () => {
  assert.equal(PRESENTATION_ICONS.length, 14);
  assert.equal(PRESENTATION_ACCENTS.length, 10);
  for (const icon of PRESENTATION_ICONS) {
    const html = renderToStaticMarkup(createElement(PresentationIdentity, { record: { icon_key: icon.key, accent_key: "teal", name: "Custom label" } }));
    assert.match(html, /<svg/);
    assert.match(html, /Custom label/);
    assert.match(html, /data-presentation-accent="teal"/);
  }
  for (const invalid of [null, undefined, "__proto__", "<svg>", "unknown"]) {
    assert.equal(presentationIcon(invalid).key, "infrastructure");
    assert.equal(presentationIcon(invalid, "network").key, "network");
    assert.equal(presentationAccent(invalid), "slate");
  }
  assert.match(renderToStaticMarkup(createElement(PresentationIcon, { record: { icon_key: "broken", accent_key: "broken" }, fallback: "network" })), /data-presentation-icon="network"/);
});

test("every accent has light/dark tokens and accessible icon, text and edge contrast", async () => {
  const css = await readFile(new URL("../app/presentation.css", import.meta.url), "utf8");
  const blocks = [...css.matchAll(/\[data-presentation-accent="(\w+)"\] \{([^}]+)\}/g)];
  assert.deepEqual(blocks.map(b => b[1]), PRESENTATION_ACCENTS);
  for (const [_, key, body] of blocks) {
    const tokens = Object.fromEntries([...body.matchAll(/--identity-(\w+): light-dark\((#[\dA-F]+), (#[\dA-F]+)\)/g)].map(m => [m[1], [m[2],m[3]]]));
    assert.deepEqual(Object.keys(tokens), ["foreground", "tile", "border", "tint", "emphasis"]);
    for (const mode of [0, 1]) {
      assert.ok(contrastRatio(tokens.foreground[mode], tokens.tile[mode]) >= 4.5, `${key} icon in ${mode}`);
      assert.ok(contrastRatio(mode ? "#E7EDF0" : "#152629", tokens.tint[mode]) >= 4.5, `${key} text in ${mode}`);
      assert.ok(contrastRatio(mode ? "#AFBEC6" : "#647579", tokens.tint[mode]) >= 4.5, `${key} metadata in ${mode}`);
      assert.ok(contrastRatio(tokens.emphasis[mode], mode ? "#1B272E" : "#FFFFFF") >= 3, `${key} membership edge in ${mode}`);
    }
  }
});

test("custom categories own Asset identity independently of parent and multiple Networks", () => {
  const data = {
    categories: [{ id: "compute", name: "Renamed freely", icon_key: "server", accent_key: "blue" }, { id: "custom", name: "Home Automation", icon_key: "home", accent_key: "teal" }],
    asset_types: [{ key: "host", category_id: "compute" }, { key: "workload", category_id: "custom" }],
    assets: [{ id: "host", name: "PVE1", asset_type: "host", cached_icon_url: "/pve.png" }, { id: "child", name: "AdGuard", asset_type: "workload", cached_icon_url: "/adguard.png" }],
    networks: [{ id: "management", name: "Management", accent_key: "purple", icon_key: "network" }, { id: "apps", name: "Apps", accent_key: "orange", icon_key: "cloud" }],
    asset_interfaces: [{ id: "eth0", name: "eth0", asset_id: "child", network_id: "management", ip_address: "10.0.99.5" }, { id: "eth1", name: "eth1", asset_id: "child", network_id: "apps", ip_address: "10.0.3.5" }],
    platform_links: [{ parent_id: "host", child_id: "child" }], relationships: [], relationship_types: [],
  };
  const view = topologyPresentation(data, new Set(["compute", "custom"]));
  assert.equal(view.byId.host.presentation.accent_key, "blue");
  assert.equal(view.children.host[0].presentation.accent_key, "teal");
  assert.equal(view.byId.child.cached_icon_url, "/adguard.png");
  assert.equal(view.byId.child.display_ip, "10.0.99.5 +1");
  assert.equal(view.networkById.management.accent_key, "purple");
  assert.equal(view.networkById.apps.accent_key, "orange");
  data.categories[1].accent_key = "green";
  assert.equal(topologyPresentation(data, new Set(["custom"])).byId.child.presentation.accent_key, "green");
});
