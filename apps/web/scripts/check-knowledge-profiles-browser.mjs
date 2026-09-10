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
    page.on("pageerror", (error) => { errors.push(error.message); console.error(error.message); });
    let canManage = true;
    let canView = true;
    const calls = [];
    const mutations = [];
    let emptyGlobals = false;
    let requirements = [
      { id: "global", name: "Name", description: `Every ${entity === "asset" ? "Asset" : "Service"} must have a meaningful name.`, rule_summary: `Requires ${entity} field name`, requirement_level: "required", severity: "high", active: true, system_defined: true, can_delete: false },
      { id: "specific", name: "Detailed operational knowledge", description: "A long administrator description explains why this knowledge matters, who maintains it, and how operators use it during recovery. ".repeat(3), rule_summary: `Requires ${entity} field ${"long_technical_identifier_".repeat(9)}`, requirement_level: "conditional", severity: "medium", active: false, [`${entity}_type_id`]: typeId },
    ].map((item) => ({ configuration_valid: true, rule_type: entity === "asset" ? "field_present" : "service_field_present", rule_config_json: { field: "name" }, key: item.id, entity_type: entity, ...item }));
    await page.route("**/api/**", async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;
      const method = route.request().method();
      const permissions = ["asset_types.view", "service_types.view", "asset_types.manage", "service_types.manage", ...(canView ? ["knowledge_requirements.view"] : []), ...(canManage ? ["knowledge_requirements.manage"] : [])];
      let body = [];
      if (path === "/api/auth/me") body = { id: "fixture", email: "profile@example.test", display_name: "Profile tester", theme_mode: theme, permissions, assignments: [{ scope_type: "global", permissions }] };
      else if (path === "/api/context") body = { customers: [], sites: [], global_access: true };
      else if (path === `/api/${entity}-types`) body = [{ id: typeId, name: "Example", key: "example", active: true }];
      else if (path === "/api/knowledge-requirements") {
        if (method === "GET") {
          assert.equal(url.searchParams.get("entity_type"), entity);
          body = emptyGlobals ? [] : requirements.filter((item) => !item[`${entity}_type_id`]);
        } else {
          assert.equal(method, "POST");
          const payload = route.request().postDataJSON();
          assert.equal(payload.entity_type, entity);
          assert.equal(payload[`${entity}_type_id`], null);
          mutations.push({ method, payload });
          body = { ...payload, id: `created-${mutations.length}`, configuration_valid: true, can_delete: true, system_defined: false, rule_summary: `Requires ${entity} field ${payload.rule_config_json.field}` };
          requirements.push(body); emptyGlobals = false;
        }
      }
      else if (path.endsWith("/knowledge-requirements")) body = requirements;
      else if (/\/knowledge-requirements\/[^/]+$/.test(path)) {
        const id = path.split("/").at(-1);
        if (method === "PATCH") {
          const payload = route.request().postDataJSON();
          mutations.push({ method, payload });
          Object.assign(requirements.find((item) => item.id === id), payload);
        } else if (method === "DELETE") {
          mutations.push({ method });
          requirements = requirements.filter((item) => item.id !== id);
          await route.fulfill({ status: 204 }); return;
        }
      }
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
    const inherited = table.locator("tbody").first();
    assert.equal(await inherited.getByRole("button").count(), 0);
    const manageLink = inherited.getByRole("link", { name: "Manage global requirements →" });
    assert.equal(await manageLink.getAttribute("href"), `/admin/${entity}-types/requirements/global`);
    await table.getByRole("button", { name: "Reactivate", exact: true }).click();
    await table.getByRole("button", { name: "Deactivate", exact: true }).waitFor();
    await table.getByRole("button", { name: "Deactivate", exact: true }).click();
    await table.getByRole("button", { name: "Reactivate", exact: true }).waitFor();
    assert.deepEqual(calls, ["activate", "deactivate"]);
    await page.screenshot({ path: `${output}/${entity}-${theme}-${width}.png`, fullPage: true });
    await manageLink.click();
    const globalPath = `/admin/${entity}-types/requirements/global`;
    await page.waitForURL(`**${globalPath}`);
    await page.getByRole("heading", { name: `Global ${entity === "asset" ? "Asset" : "Service"} requirements` }).waitFor();
    await table.getByText("Name", { exact: true }).waitFor();
    assert.equal(await table.getByText("Detailed operational knowledge").count(), 0);
    assert.equal(await table.locator("tbody").count(), 1);
    assert.equal(await table.getByRole("button", { name: "Delete", exact: true }).count(), 0);
    await table.getByRole("button", { name: "Deactivate", exact: true }).click();
    await table.getByRole("button", { name: "Reactivate", exact: true }).waitFor();
    await table.getByRole("button", { name: "Reactivate", exact: true }).click();
    await table.getByRole("button", { name: "Deactivate", exact: true }).waitFor();
    if (entity === "asset") {
      emptyGlobals = true;
      await page.getByRole("button", { name: "Refresh", exact: true }).click();
      await page.getByText("No global Asset requirements are configured.").waitFor();
      const emptyBox = await page.getByText("No global Asset requirements are configured.").boundingBox();
      assert.ok(emptyBox.x >= 0 && emptyBox.x + emptyBox.width <= width, "empty state remains readable without horizontal scrolling");
      assert.equal(await table.count(), 0);
      await page.screenshot({ path: `${output}/global-asset-empty-${theme}-${width}.png`, fullPage: true });
      requirements = requirements.filter((item) => item[`${entity}_type_id`]);
    }
    await page.getByRole("button", { name: "Add requirement", exact: true }).click();
    await page.getByLabel("Name *", { exact: true }).fill("Custom global requirement");
    await page.getByRole("textbox", { name: "Description", exact: true }).fill("Global operator policy with a clear description.");
    await page.getByRole("button", { name: "Save requirement", exact: true }).click();
    let custom = table.getByRole("row").filter({ hasText: "Custom global requirement" });
    await custom.getByRole("button", { name: "Edit", exact: true }).waitFor();
    assert.equal(mutations[0].method, "POST");
    await custom.getByRole("button", { name: "Edit", exact: true }).click();
    await page.getByRole("textbox", { name: "Description", exact: true }).fill("Revised global operator policy.");
    await page.getByRole("button", { name: "Save requirement", exact: true }).click();
    await custom.getByText("Revised global operator policy.").waitFor();
    assert.equal(mutations[1].method, "PATCH");
    await custom.getByRole("button", { name: "Duplicate", exact: true }).click();
    await page.getByRole("button", { name: "Save requirement", exact: true }).click();
    const duplicate = table.getByRole("row").filter({ hasText: "Custom global requirement copy" });
    await duplicate.getByRole("button", { name: "Delete", exact: true }).waitFor();
    assert.equal(mutations[2].method, "POST");
    assert.notEqual(mutations[0].payload.key, mutations[2].payload.key);
    page.once("dialog", (dialog) => dialog.accept());
    await duplicate.getByRole("button", { name: "Delete", exact: true }).click();
    await duplicate.waitFor({ state: "detached" });
    assert.equal(mutations[3].method, "DELETE");
    await page.screenshot({ path: `${output}/global-${entity}-${theme}-${width}.png`, fullPage: true });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.goto(`${base}/admin/${entity}-types`);
    const entry = page.getByRole("link", { name: "Manage global requirements", exact: true });
    await entry.waitFor();
    assert.equal(await entry.getAttribute("href"), globalPath);
    assert.ok((await entry.getAttribute("class")).includes("button-secondary"));
    assert.ok((await page.getByRole("button", { name: `Add ${entity === "asset" ? "Asset" : "Service"} type`, exact: true }).getAttribute("class")).includes("button-primary"));
    assert.equal(await page.locator(".admin-tabs a").count(), 2);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, "type-list heading actions fit the viewport");
    await page.screenshot({ path: `${output}/${entity}-types-${theme}-${width}.png`, fullPage: true });
    await entry.focus(); await page.keyboard.press("Enter");
    await page.waitForURL(`**${globalPath}`);
    await table.getByText("Custom global requirement", { exact: true }).waitFor();
    canManage = false;
    await page.reload();
    await page.getByText("Access unavailable", { exact: true }).waitFor();
    assert.equal(await table.count(), 0);
    await page.goto(`${base}/admin/${entity}-types`);
    await page.getByRole("heading", { name: `${entity === "asset" ? "Asset" : "Service"} types`, exact: true }).waitFor();
    assert.equal(await page.getByRole("link", { name: "Manage global requirements", exact: true }).count(), 0);
    await page.goto(`${base}/admin/${entity}-types/${typeId}/knowledge-profile`);
    await table.getByText("Detailed operational knowledge").waitFor();
    assert.equal(await table.getByRole("button").count(), 0);
    assert.equal(await table.getByRole("link", { name: "Manage global requirements →" }).count(), 0);
    assert.equal(await table.getByRole("columnheader", { name: "Actions" }).count(), 0);
    canView = false;
    await page.reload();
    await page.getByText("Access unavailable", { exact: true }).waitFor();
    assert.equal(await table.count(), 0);
    assert.deepEqual(errors, []);
    await context.close();
    checks++;
  }
  console.log(`${checks} profile/theme/viewport cases passed: layout, inheritance, global create/edit/duplicate/delete/lifecycle, navigation, empty state and permissions.`);
} finally { await browser.close(); }
