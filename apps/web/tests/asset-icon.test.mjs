import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { assetIconSources, GENERIC_ICON } from "../lib/asset-icon.mjs";
const local = `/api/assets/11111111-1111-4111-8111-111111111111/icon?v=${"a".repeat(64)}`;
const fallback = "https://example.com/type.png";

test("cached Asset > Asset Type > generic; external Asset source is never rendered", () => {
  assert.deepEqual(assetIconSources({ cached_icon_url: local, icon_url: "https://source.example/secret" }, { default_icon_url: fallback }), [local, fallback, GENERIC_ICON]);
  assert.deepEqual(assetIconSources({ icon_url: "https://source.example/icon", default_icon_url: fallback }), [fallback, GENERIC_ICON]);
  assert.deepEqual(assetIconSources({ resolved_icon_url: "https://source.example/icon" }), [GENERIC_ICON]);
  assert.deepEqual(assetIconSources({ cached_icon_url: "https://source.example/icon" }), [GENERIC_ICON]);
  assert.deepEqual(assetIconSources({ cached_icon_url: local }, null, "https://atlas.example/api"), [`https://atlas.example${local}`, GENERIC_ICON]);
});

test("all four surfaces and the inspector share AssetIcon, preserving non-Asset marks", async () => {
  for (const path of ["app/assets/page.js", "app/assets/[id]/page.js", "components/service-landscape.js", "components/graph-inspector.js", "app/topology/page.js"]) {
    const source = await readFile(new URL(`../${path}`, import.meta.url), "utf8");
    assert.match(source, /<AssetIcon asset=\{/);
    assert.doesNotMatch(source, /icon_url: asset\.icon_url/);
  }
  for (const path of ["app/dashboard/page.js", "app/knowledge-graph/page.js"]) {
    assert.match(await readFile(new URL(`../${path}`, import.meta.url), "utf8"), /<ServiceLandscape/);
  }
  const graph = await readFile(new URL("../components/service-landscape.js", import.meta.url), "utf8");
  assert.match(graph, /node.entity_type === "asset" \? <AssetIcon.*: <EntityMark type=\{node.entity_type\}/);
});

test("loading and failure retain fixed themed box and hide unready image", async () => {
  const component = await readFile(new URL("../components/asset-icon.js", import.meta.url), "utf8");
  const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.match(component, /width: size, height: size/);
  assert.match(component, /opacity: loaded \? 1 : 0/);
  assert.match(component, /opacity: loaded \? 0 : 1/);
  assert.match(component, /onError=.*setLoaded\(false\).*setIndex/);
  assert.match(component, /key=\{sources.join/);
  assert.match(component, /aria-label=\{alt/);
  assert.match(css, /\.asset-icon \{[^}]*var\(--surface-muted\)/);
  assert.match(css, /\.asset-icon > img \{[^}]*object-fit: contain/);
});
