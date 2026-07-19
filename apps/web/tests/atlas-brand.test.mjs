import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  AtlasBrand,
  AtlasLogo,
  ATLAS_BRAND_ASSETS,
  brandAssetForFailureCount,
} from "../components/atlas-brand.mjs";
import { contrastRatio, deriveAccentTheme, mixColours } from "../lib/accent-theme.mjs";

test("renders the local Atlas wordmark as an accessible authenticated-home link", () => {
  const markup = renderToStaticMarkup(React.createElement(AtlasBrand, { href: "/dashboard" }));

  assert.match(markup, /href="\/dashboard"/);
  assert.match(markup, /aria-label="Atlas home"/);
  assert.match(markup, /src="\/branding\/atlas-logo\.svg"/);
  assert.match(markup, /alt="Atlas"/);
  assert.doesNotMatch(markup, /brand-mark/);
});

test("falls back from SVG to accessible text", () => {
  assert.deepEqual(ATLAS_BRAND_ASSETS, [
    "/branding/atlas-logo.svg",
  ]);
  assert.equal(brandAssetForFailureCount(0), "/branding/atlas-logo.svg");
  assert.equal(brandAssetForFailureCount(1), null);
});

test("the shared logo preserves the source asset and natural aspect ratio", () => {
  const markup = renderToStaticMarkup(React.createElement(AtlasLogo, { className: "login-logo-image" }));

  assert.match(markup, /src="\/branding\/atlas-logo\.svg"/);
  assert.match(markup, /alt="Atlas"/);
  assert.match(markup, /width="900"/);
  assert.match(markup, /height="200"/);
  assert.match(markup, /class="login-logo-image"/);
});

test("the authenticated shell uses the shared brand without the old A tile", async () => {
  const shell = await readFile(new URL("../components/app-shell.js", import.meta.url), "utf8");

  assert.match(shell, /<AtlasBrand href=\{authenticatedHome\(user\)\} \/>/);
  assert.doesNotMatch(shell, /className="brand-mark"/);
});

test("the login page uses the shared logo without an opaque logo wrapper", async () => {
  const [login, styles] = await Promise.all([
    readFile(new URL("../app/login/page.js", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
  ]);

  assert.match(login, /<AtlasLogo className="login-logo-image"/);
  assert.doesNotMatch(login, /className="login-brand"/);
  assert.doesNotMatch(login, /className="brand-mark"/);
  assert.match(styles, /\.login-logo \{[^}]*background: transparent;[^}]*border: 0;[^}]*box-shadow: none;/);
  assert.match(styles, /\.login-logo-image \{[^}]*height: auto;[^}]*object-fit: contain;/);
});

test("the fixed logo treatment remains readable across extreme sidebar accents", () => {
  for (const accent of ["#FFFFFF", "#FFFF00", "#2563EB", "#7C3AED", "#000000"]) {
    const sidebar = deriveAccentTheme(accent).sidebar;
    const logoBackground = mixColours(sidebar, "#000000", 0.26);

    assert.ok(contrastRatio(logoBackground, "#FFFFFF") >= 4.5);
    assert.ok(contrastRatio(logoBackground, "#22D3EE") >= 3);
    assert.ok(contrastRatio(logoBackground, "#5BC7FF") >= 3);
  }
});
