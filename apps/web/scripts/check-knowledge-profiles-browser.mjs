// Opt-in regression against a running production build, using isolated API fixtures.
// ATLAS_PLAYWRIGHT_MODULE may point to an existing Playwright installation.
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { pathToFileURL } from "node:url";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const base = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3117";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-knowledge-profiles-browser";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
const typeId = "11111111-1111-4111-8111-111111111111";
let checks = 0;
try {
  for (const entity of ["asset", "service"]) for (const theme of ["light", "dark"]) for (const width of [1440, 1280, 768, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    let canManage = true;
    let canView = true;
    const calls = [];
    const requirements = [
      { id: "global", name: "Name", description: `Every ${entity === "asset" ? "Asset" : "Service"} must have a meaningful name.`, rule_summary: `Requires ${entity} field name`, requirement_level: "required", severity: "high", active: true },
      { id: "specific", name: "Detailed operational knowledge", description: "A long administrator description explains why this knowledge matters, who maintains it, and how operators use it during recovery. ".repeat(3), rule_summary: `Requires ${entity} field ${"long_technical_identifier_".repeat(9)}`, requirement_level: "conditional", severity: "medium", active: false, [`${entity}_type_id`]: typeId },
    ].map((item) => ({ configuration_valid: true, entity_type: entity, ...item }));
    await page.route("**/api/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      const permissions = ["asset_types.view", "service_types.view", ...(canView ? ["knowledge_requirements.view"] : []), ...(canManage ? ["knowledge_requirements.manage"] : [])];
      let body = [];
      if (path === "/api/auth/me") body = { id: "fixture", email: "profile@example.test", display_name: "Profile tester", theme_mode: theme, permissions, assignments: [{ scope_type: "global", permissions }] };
      else if (path === "/api/context") body = { customers: [], sites: [], global_access: true };
      else if (path === `/api/${entity}-types`) body = [{ id: typeId, name: "Example", key: "example", active: true }];
      else if (path.endsWith("/knowledge-requirements")) body = requirements;
      else if (/\/knowledge-requirements\/.*\/(deactivate|activate)$/.test(path)) {
        assert.equal(route.request().method(), "POST");
        const [, id, action] = path.match(/\/knowledge-requirements\/(.*)\/(deactivate|activate)$/);
        requirements.find((item) => item.id === id).active = action === "activate";
        calls.push(action);
      }
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.goto(`${base}/admin/${entity}-types/${typeId}/knowledge-profile`);
    const table = page.locator(".knowledge-profile-table");
    await table.getByText("Detailed operational knowledge").waitFor({ timeout: 10000 }).catch(async (error) => { console.error(await page.locator("body").innerText(), errors); throw error; });
    assert.equal(await table.locator("tbody").count(), 2);
    assert.equal(await table.getByRole("rowgroup").filter({ hasText: "Global requirements" }).getByText("Name", { exact: true }).count(), 1);
    assert.equal(await table.getByText(`This ${entity === "asset" ? "Asset" : "Service"} Type`).count(), 1);
    assert.equal(await table.getByRole("button", { name: "Delete", exact: true }).count(), 1);
    assert.equal(await page.locator("html").getAttribute("data-theme"), theme);
    const metrics = await table.evaluate((table) => {
      const identity = table.querySelectorAll(".table-cell-identity")[1];
      const name = identity.querySelector("strong");
      const description = identity.querySelector("small");
      const rule = table.querySelectorAll(".profile-rule")[1];
      return {
        separated: description.getBoundingClientRect().top >= name.getBoundingClientRect().bottom + 4,
        descriptionWrapped: description.offsetHeight > parseFloat(getComputedStyle(description).lineHeight) * 2,
        ruleWrapped: rule.offsetHeight > parseFloat(getComputedStyle(rule).lineHeight) * 2,
        noCellOverflow: [...table.querySelectorAll("td")].every((cell) => cell.scrollWidth <= cell.clientWidth + 1),
        pageFits: document.documentElement.scrollWidth <= window.innerWidth,
        tableFits: table.parentElement.scrollWidth <= table.parentElement.clientWidth + 1,
        muted: getComputedStyle(description).color !== getComputedStyle(name).color,
        compactBadges: [...table.querySelectorAll("td:nth-child(2) .status-badge, td:nth-child(3) .status-badge, td:nth-child(6) .status-badge")].every((badge) => badge.offsetHeight < 30),
      };
    });
    for (const key of ["separated", "descriptionWrapped", "ruleWrapped", "noCellOverflow", "pageFits", "muted", "compactBadges"]) assert.ok(metrics[key], `${key}: ${entity} ${theme} ${width}`);
    if (width >= 1280) assert.ok(metrics.tableFits, `desktop table overflow: ${width}`);
    const region = page.getByRole("region", { name: /knowledge requirements/ });
    await region.focus();
    assert.equal(await region.evaluate((element) => document.activeElement === element), true);
    await table.getByRole("button", { name: "Deactivate", exact: true }).click();
    await page.waitForFunction(() => document.querySelectorAll(".knowledge-profile-table .status-inactive").length === 2);
    await table.getByRole("button", { name: "Reactivate", exact: true }).first().click();
    await table.getByRole("button", { name: "Deactivate", exact: true }).waitFor();
    assert.deepEqual(calls, ["deactivate", "activate"]);
    await page.screenshot({ path: `${output}/${entity}-${theme}-${width}.png`, fullPage: true });
    canManage = false;
    await page.reload();
    await table.getByText("Detailed operational knowledge").waitFor();
    assert.equal(await table.getByRole("button").count(), 0);
    assert.equal(await table.getByRole("columnheader", { name: "Actions" }).count(), 0);
    canView = false;
    await page.reload();
    await page.getByText("Access unavailable", { exact: true }).waitFor();
    assert.equal(await table.count(), 0);
    assert.deepEqual(errors, []);
    await context.close();
    checks++;
  }
  console.log(`${checks} profile/theme/viewport cases passed: layout, wrapping, scope, lifecycle requests, keyboard region and permissions.`);
} finally { await browser.close(); }
