// Opt-in browser regression against a running production build. API fixtures
// exercise rendering; PostgreSQL API behavior is tested separately.
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { SYSTEM_SECTIONS } from "../lib/system-navigation.mjs";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const base = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3106";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-c26-browser-results";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
const permissions = [...SYSTEM_SECTIONS.map((section) => section.permission || section.globalPermission), "services.view", "services.archive", "business_functions.view", "business_functions.manage"];
const customer = { id: "11111111-1111-4111-8111-111111111111", name: "Homelab" };
const site = { id: "22222222-2222-4222-8222-222222222222", customer_id: customer.id, name: "Home" };
const service = { id: "33333333-3333-4333-8333-333333333333", name: "Mistaken DNS Service", customer_id: customer.id, site_id: site.id, service_type_name: "Infrastructure", lifecycle_status: "active", operational_status: "unknown", criticality_name: "High", updated_at: "2026-09-10T00:00:00Z", archived_at: null };
const functionItem = { ...service, id: "44444444-4444-4444-8444-444444444444", name: "Mistaken Business Function", active: true };
let checks = 0;
try {
  for (const theme of ["light", "dark"]) {
    for (const width of [1440, 768, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme });
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      let blocked = false;
      let settingsEmpty = false;
      let deleted = false;
      let allowedPermissions = permissions;
      await page.route("**/api/**", async (route) => {
        const url = new URL(route.request().url());
        let body = [];
        let status = 200;
        if (url.pathname === "/api/auth/me") body = { id: "browser-test", email: "browser@example.test", display_name: "Browser tester", theme_mode: theme, permissions: allowedPermissions, assignments: [{ scope_type: "global", permissions: allowedPermissions }] };
        else if (url.pathname === "/api/context") body = { customers: [customer], sites: [site], global_access: true, selected_customer_id: customer.id, selected_site_id: site.id };
        else if (url.pathname === "/api/system-settings") body = settingsEmpty ? [] : [{ id: "safe", key: "display_name", value: "Homelab", description: "Instance name", sensitive: false, updated_at: service.updated_at }, { id: "sensitive", key: "restricted_fixture", value: "[redacted]", sensitive: true, updated_at: service.updated_at }];
        else if (url.pathname.endsWith("/deletion-eligibility")) body = { eligible: !blocked, reason: blocked ? "This Service cannot be deleted because it has participated in the operational model. Archive it instead." : null };
        else if (url.pathname === `/api/services/${service.id}`) {
          if (route.request().method() === "DELETE") { deleted = true; status = 204; }
          else body = service;
        } else if (url.pathname === `/api/business-functions/${functionItem.id}`) body = functionItem;
        else if (url.pathname.endsWith("/graph") || url.pathname === "/api/operational-graph") body = { nodes: [], edges: [] };
        else if (url.pathname.endsWith("/completeness")) body = { completeness_status: "not_evaluated", gaps: [] };
        await route.fulfill({ status, contentType: "application/json", ...(status === 204 ? {} : { body: JSON.stringify(body) }) });
      });
      for (const section of SYSTEM_SECTIONS) {
        await page.goto(`${base}${section.href}`);
        await page.locator(".nav-system-group").waitFor();
        const system = page.locator('[aria-labelledby="navigation-system-label"]');
        assert.deepEqual(await system.locator("a span").allTextContents(), ["Organisation", "Reference Data", "Audit Log", "System Settings"]);
        const active = system.locator('a[aria-current="page"]');
        assert.equal(await active.count(), 1);
        assert.equal((await active.innerText()).trim(), { organisation: "Organisation", "reference-data": "Reference Data", "audit-log": "Audit Log", "system-settings": "System Settings" }[section.group]);
        if (["organisation", "reference-data"].includes(section.group)) {
          assert.equal(await page.locator('.admin-tabs a[aria-current="page"]').innerText(), section.label);
        } else assert.equal(await page.locator(".admin-tabs").count(), 0);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, `overflow: ${section.href} ${width}`);
        checks++;
      }
      for (const heading of ["General", "Backup & Restore", "Updates", "About"]) assert.equal(await page.getByRole("heading", { name: heading, exact: true }).count(), 1);
      assert.equal(await page.getByText("restricted_fixture").count(), 0);
      assert.equal(await page.locator("html").getAttribute("data-theme"), theme);
      await page.screenshot({ path: `${output}/settings-${theme}-${width}.png`, fullPage: true });
      settingsEmpty = true;
      await page.reload();
      await page.getByText("No administrator-managed runtime settings are configured yet.").waitFor();
      checks++;
      await page.goto(`${base}/admin`);
      await page.waitForURL("**/admin/users");
      checks++;
      for (const [collection, record, label] of [["services", service, "Service"], ["business-functions", functionItem, "Business Function"]]) {
        await page.goto(`${base}/${collection}/${record.id}`);
        const trigger = page.getByRole("button", { name: `Delete ${label}`, exact: true });
        await trigger.waitFor();
        await trigger.click();
        const dialog = page.getByRole("dialog");
        assert.equal(await dialog.isVisible(), true);
        const contrast = await dialog.getByRole("button", { name: `Delete ${label}`, exact: true }).evaluate((button) => {
          const style = getComputedStyle(button);
          const luminance = (color) => color.match(/[\d.]+/g).slice(0, 3).map((value) => {
            const channel = Number(value) / 255;
            return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
          }).reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0);
          const foreground = luminance(style.color); const background = luminance(style.backgroundColor);
          return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
        });
        assert.ok(contrast >= 4.5, `Delete button contrast: ${contrast}`);
        const box = await dialog.boundingBox();
        assert.ok(box.x >= 15 && box.x + box.width <= width - 15, "dialog keeps mobile gutters");
        assert.equal(await page.evaluate(() => document.activeElement.textContent), "Cancel");
        await page.keyboard.press("Shift+Tab");
        assert.equal(await page.evaluate(() => document.activeElement.textContent), `Delete ${label}`);
        await page.keyboard.press("Shift+Tab");
        assert.equal(await page.evaluate(() => document.activeElement.textContent), "Cancel");
        await page.keyboard.press("Tab");
        assert.equal(await page.evaluate(() => document.activeElement.textContent), `Delete ${label}`);
        await page.keyboard.press("Tab");
        assert.equal(await page.evaluate(() => document.activeElement.textContent), "Cancel");
        await page.screenshot({ path: `${output}/delete-${collection}-${theme}-${width}.png` });
        await page.keyboard.press("Escape");
        assert.equal(await dialog.isVisible(), false);
        assert.equal(await trigger.evaluate((node) => node === document.activeElement), true);
        checks++;
      }
      blocked = true;
      await page.goto(`${base}/services/${service.id}`);
      await page.getByText("This Service cannot be deleted because it has participated in the operational model. Archive it instead.").waitFor();
      assert.equal(await page.getByRole("button", { name: "Delete Service", exact: true }).isDisabled(), true);
      blocked = false;
      await page.reload();
      await page.getByRole("button", { name: "Delete Service", exact: true }).click();
      await page.getByRole("dialog").getByRole("button", { name: "Delete Service", exact: true }).click();
      await page.waitForURL("**/services");
      assert.equal(deleted, true);
      checks++;
      allowedPermissions = ["roles.view"];
      await page.goto(`${base}/admin`);
      await page.waitForURL("**/admin/roles");
      assert.deepEqual(await page.locator(".admin-tabs a").allTextContents(), ["Roles & permissions"]);
      assert.deepEqual(await page.locator('[aria-labelledby="navigation-system-label"] a span').allTextContents(), ["Organisation"]);
      assert.deepEqual(errors, [], `${theme} ${width}`);
      checks++;
      await context.close();
    }
  }
  console.log(`${checks} browser scenarios passed across light/dark and desktop/tablet/mobile. Screenshots: ${output}`);
} finally { await browser.close(); }
