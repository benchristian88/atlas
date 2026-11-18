// Production web UI with intercepted API responses and no backend dependency.
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const origin = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3143";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-system-settings-browser";
const buildInfo = { version: "0.37.2-beta.4", release_channel: "beta", build_id: "test-build-id", install_method: "docker_compose" };
const settingsPath = "/admin/system-settings";
const buildInfoPath = "/api/system-settings/build-info";
const permission = "system_settings.manage";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });

async function openPage({ width = 1440, theme = "light", accent = null, scope = "global", metadata = buildInfo, metadataStatus = 200 } = {}) {
  const context = await browser.newContext({ viewport: { width, height: 960 }, colorScheme: theme });
  const page = await context.newPage();
  page.setDefaultTimeout(8000);
  const errors = [];
  const metadataRequests = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const globalPermissions = ["customers.view", ...(scope === "global" ? [permission] : [])];
  const responses = {
    "/api/setup/status": { state: "INITIALISED" },
    "/api/auth/me": {
      id: "browser-test", email: "browser@example.test", display_name: "Browser tester", theme_mode: theme, accent_colour: accent,
      permissions: ["customers.view", ...(scope ? [permission] : [])],
      assignments: [
        { scope_type: "global", role_name: "Master Administrator", permissions: globalPermissions },
        ...(scope === "customer" ? [{ scope_type: "customer", customer_id: "customer", permissions: [permission] }] : []),
      ],
    },
    "/api/context": { customers: [], sites: [], global_access: true },
    "/api/auth/mfa/status": { enabled: false },
    "/api/system-settings": [],
    "/api/system-settings/updates": { status: "unavailable", refresh_after_seconds: 0 },
  };
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) return route.abort();
    if (url.pathname === buildInfoPath) {
      metadataRequests.push(route.request().headers());
      return route.fulfill({ status: metadataStatus, json: metadata });
    }
    if (url.pathname.startsWith("/api/")) {
      return route.fulfill({ status: url.pathname in responses ? 200 : 404, json: responses[url.pathname] || {} });
    }
    return route.continue();
  });
  return { context, page, errors, metadataRequests };
}

async function navigate(page, name, destination) {
  await page.getByRole("navigation", { name: "Primary navigation" }).getByRole("link", { name, exact: true }).click();
  await page.waitForURL(`${origin}${destination}`);
}

try {
  for (const theme of ["light", "dark"]) {
    for (const width of [1440, 1024, 800, 390]) {
      const accent = { 1024: "#2563EB", 800: "#7C3AED" }[width] || null;
      const { context, page, errors, metadataRequests } = await openPage({ width, theme, accent });
      await page.goto(`${origin}/dashboard`);
      await page.getByRole("heading", { name: "Dashboard", exact: true }).waitFor();
      const footer = page.locator(".sidebar-footer");
      await page.getByText(`Atlas ${buildInfo.version}`, { exact: true }).waitFor();
      await navigate(page, "System Settings", settingsPath);
      const about = page.getByRole("region", { name: "About", exact: true });
      const updates = page.getByRole("region", { name: "Updates", exact: true });
      await about.waitFor();
      assert.deepEqual(await page.locator(".system-settings-section h2").allTextContents(), ["About", "General", "Backup & Restore", "Updates"]);
      await updates.getByText(buildInfo.version, { exact: true }).waitFor();
      assert.deepEqual(await updates.locator("dd").allTextContents(), [buildInfo.version, buildInfo.release_channel, buildInfo.build_id, "Docker Compose"]);
      assert.equal(await footer.innerText(), `Atlas ${buildInfo.version}`);
      assert.equal(await footer.evaluate((element) => element.tabIndex), -1);
      assert.equal(await page.locator("html").getAttribute("data-theme"), theme);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      const nav = page.getByRole("navigation", { name: "Primary navigation" });
      assert.equal(await nav.evaluate((element) => getComputedStyle(element).flexDirection), width <= 900 ? "row" : "column");
      const links = about.getByRole("link");
      assert.equal(await links.count(), 5);
      await links.first().focus();
      for (let index = 1; index < 5; index++) {
        await page.keyboard.press("Tab");
        assert.ok(await links.nth(index).evaluate((link) => link === document.activeElement && link.matches(":focus-visible") && getComputedStyle(link).outlineStyle === "solid"));
      }
      assert.equal(metadataRequests.length, 1);
      assert.equal(metadataRequests[0]["x-atlas-customer-id"], undefined);
      assert.equal(metadataRequests[0]["x-atlas-site-id"], undefined);
      if (width === 1440 || width === 390) {
        await page.evaluate(() => { document.activeElement.blur(); window.scrollTo(0, 0); });
        await page.screenshot({ path: `${output}/settings-${theme}-${width}.png` });
      }
      assert.deepEqual(errors, []);
      await context.close();
    }
  }

  for (const scenario of [{ metadata: {} }, { metadataStatus: 503 }, { metadataStatus: 401 }, { scope: "customer" }, { scope: null }]) {
    const { context, page, errors, metadataRequests } = await openPage(scenario);
    const restricted = "scope" in scenario;
    const response = restricted ? null : page.waitForResponse(`${origin}${buildInfoPath}`);
    await page.goto(origin + settingsPath);
    await response;
    await page.getByText(restricted ? "Access unavailable" : "No administrator-managed runtime settings are configured yet.", { exact: true }).waitFor();
    assert.equal(await page.locator(".sidebar-footer").count(), 0);
    await navigate(page, "Dashboard", "/dashboard");
    await page.getByRole("heading", { name: "Dashboard", exact: true }).waitFor();
    assert.equal(await page.locator(".sidebar-footer").count(), 0);
    assert.equal(metadataRequests.length, restricted ? 0 : 1);
    assert.deepEqual(errors, []);
    await context.close();
  }
  console.log(`Passed 8 viewport/theme checks and 5 metadata/access checks. Screenshots: ${output}`);
} finally {
  await browser.close();
}
