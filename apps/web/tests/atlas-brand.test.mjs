import test from "node:test";
import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  AtlasBrand,
  AtlasLogo,
  ATLAS_BRAND_ASSETS,
  brandAssetForFailureCount,
} from "../components/atlas-brand.mjs";

test("renders the Atlas Impact dark-background lockup as an accessible authenticated-home link", () => {
  const markup = renderToStaticMarkup(React.createElement(AtlasBrand, { href: "/dashboard" }));

  assert.match(markup, /href="\/dashboard"/);
  assert.match(markup, /aria-label="Atlas Impact home"/);
  assert.match(markup, /src="\/branding\/lockups\/atlas-impact-lockup-dark\.svg"/);
  assert.match(markup, /alt="Atlas Impact"/);
  assert.doesNotMatch(markup, /brand-mark/);
});

test("maps the supplied light and dark lockups with PNG and text fallbacks", () => {
  assert.deepEqual(ATLAS_BRAND_ASSETS.dark, [
    "/branding/lockups/atlas-impact-lockup-dark.svg",
    "/branding/lockups/atlas-impact-lockup-dark.png",
  ]);
  assert.deepEqual(ATLAS_BRAND_ASSETS.light, [
    "/branding/lockups/atlas-impact-lockup-light.svg",
    "/branding/lockups/atlas-impact-lockup-light.png",
  ]);
  assert.equal(brandAssetForFailureCount(0), ATLAS_BRAND_ASSETS.dark[0]);
  assert.equal(brandAssetForFailureCount(1, "light"), ATLAS_BRAND_ASSETS.light[1]);
  assert.equal(brandAssetForFailureCount(2), null);
});

test("the shared logo preserves the source asset and natural aspect ratio", () => {
  const markup = renderToStaticMarkup(React.createElement(AtlasLogo, { className: "login-logo-image" }));
  const lightMarkup = renderToStaticMarkup(React.createElement(AtlasLogo, { variant: "light" }));

  assert.match(markup, /src="\/branding\/lockups\/atlas-impact-lockup-dark\.svg"/);
  assert.match(lightMarkup, /src="\/branding\/lockups\/atlas-impact-lockup-light\.svg"/);
  assert.match(markup, /alt="Atlas Impact"/);
  assert.match(markup, /width="800"/);
  assert.match(markup, /height="300"/);
  assert.match(markup, /class="login-logo-image"/);
});

test("the authenticated shell selects a supplied lockup for the derived sidebar background", async () => {
  const shell = await readFile(new URL("../components/app-shell.js", import.meta.url), "utf8");

  assert.match(shell, /deriveAccentTheme\(user\.accent_colour\)/);
  assert.match(shell, /<AtlasBrand href=\{authenticatedHome\(user\)\} variant=\{sidebarBrandVariant\} \/>/);
  assert.match(shell, /Atlas Impact<br \/>Local development/);
  assert.doesNotMatch(shell, /className="brand-mark"/);
});

test("the login page uses the shared logo without an opaque logo wrapper", async () => {
  const [login, styles] = await Promise.all([
    readFile(new URL("../app/login/page.js", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
  ]);

  assert.match(login, /<AtlasLogo className="login-logo-image"/);
  assert.match(login, /Atlas Impact account/);
  assert.doesNotMatch(login, /className="login-brand"/);
  assert.doesNotMatch(login, /className="brand-mark"/);
  assert.match(styles, /\.login-logo \{[^}]*background: transparent;[^}]*border: 0;[^}]*box-shadow: none;/);
  assert.match(styles, /\.login-logo-image \{[^}]*height: auto;[^}]*object-fit: contain;/);
});

test("the canonical manifest and metadata use Atlas Impact install branding", async () => {
  const [manifestSource, layout] = await Promise.all([
    readFile(new URL("../app/manifest.webmanifest", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.js", import.meta.url), "utf8"),
  ]);
  const manifest = JSON.parse(manifestSource);

  assert.equal(manifest.name, "Atlas Impact");
  assert.equal(manifest.short_name, "Atlas Impact");
  assert.equal(manifest.start_url, "/");
  assert.equal(manifest.display, "standalone");
  assert.equal(manifest.background_color, "#111111");
  assert.equal(manifest.theme_color, "#111111");
  assert.deepEqual(manifest.icons.map(({ sizes, purpose }) => [sizes, purpose]), [
    ["192x192", "any"],
    ["512x512", "any"],
  ]);
  for (const icon of manifest.icons) {
    await access(new URL(`../public${icon.src}`, import.meta.url));
  }

  assert.match(layout, /title: "Atlas Impact"/);
  assert.match(layout, /applicationName: "Atlas Impact"/);
  assert.match(layout, /appleWebApp: \{/);
  assert.match(layout, /\/branding\/favicon\.svg/);
  assert.match(layout, /\/branding\/apple-touch-icon\.png/);
});
