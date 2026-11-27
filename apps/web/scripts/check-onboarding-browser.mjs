// Live guided setup acceptance. Use a fresh, disposable Atlas with the onboarding preview enabled.
// Pass { code } on stdin. Administrator credentials are generated in memory.
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { checkCapabilities } from "./onboarding-capabilities-browser.mjs";
import { checkIntegrations } from "./onboarding-integrations-browser.mjs";
import { checkDiscoveryReview } from "./onboarding-discovery-review-browser.mjs";
import { checkLinkServices } from "./onboarding-link-services-browser.mjs";
import { checkReviewReady } from "./onboarding-review-browser.mjs";
import { checkStageNavigation } from "./onboarding-stage-navigation-browser.mjs";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE
  ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");

let input = "";
for await (const chunk of process.stdin) input += chunk;
const { code } = JSON.parse(input);
input = "";
const origin = process.env.ATLAS_BROWSER_BASE_URL || "http://localhost:3147";
const api = process.env.ATLAS_BROWSER_API_URL || `${origin}/api`;
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-onboarding-browser";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
const pageErrors = [];
const layouts = [];
const accents = [];
const action = (page, name) => page.getByRole("button", { name, exact: true });
const link = (page, name) => page.getByRole("link", { name, exact: true });
const heading = (page, name) => page.getByRole("heading", { name, exact: true });

async function openPage() {
  const context = await browser.newContext({ viewport: { width: 1440, height: 950 }, colorScheme: "light" });
  const page = await context.newPage();
  page.on("pageerror", error => pageErrors.push(error.message));
  return { context, page };
}

function credentials(email, name) {
  return { email, name, password: randomBytes(24).toString("base64url") };
}

async function resumeWithKeyboard(page, stage) {
  const resume = action(page, "Resume setup");
  await resume.focus();
  await page.keyboard.press("Enter");
  await resume.waitFor({ state: "detached" });
  await page.waitForFunction(title => document.activeElement?.textContent === title, stage);
  assert.equal(await heading(page, stage).evaluate(el => el === document.activeElement), true);
  assert.match(await page.locator('[aria-current="step"]').innerText(), new RegExp(stage));
}

async function login(page, user) {
  await page.goto(`${origin}/login`);
  await page.getByLabel("Email", { exact: true }).fill(user.email);
  await page.getByLabel("Password", { exact: true }).fill(user.password);
  await action(page, "Sign in").click();
  await page.waitForURL("**/dashboard");
}

async function checkLayouts(page, stage) {
  await heading(page, stage).waitFor();
  for (const theme of ["light", "dark"]) {
    await page.emulateMedia({ colorScheme: theme });
    await page.waitForFunction(expected => document.documentElement.dataset.theme === expected, theme);
    for (const width of [1440, 1024, 900, 390]) {
      await page.setViewportSize({ width, height: 950 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      const current = page.getByRole("navigation", { name: "Setup stages" }).locator('[aria-current="step"]');
      assert.match(await current.innerText(), new RegExp(stage));
      assert.equal(await page.locator(".context-selector").count(), 0);
      await page.getByRole("button", { name: /Open user menu/ }).waitFor();
      await page.screenshot({ path: `${output}/${stage.toLowerCase()}-${theme}-${width}.png`, fullPage: true });
      layouts.push({ stage, theme, width });
    }
  }
}

async function namedChange(page, operation, field, value) {
  const form = page.getByRole("form", { name: operation, exact: true });
  await form.getByLabel(field, { exact: true }).fill(value);
  await action(form, operation.startsWith("Rename") ? "Save name" : operation).click();
  await form.waitFor({ state: "detached" });
}

try {
  const primary = credentials("e1a-admin@example.com", "Onboarding Administrator");
  const second = credentials("e1a-other@example.com", "Second Administrator");
  const viewer = credentials("e1a-viewer@example.com", "Read-only Operator");
  const a = await openPage();
  await a.page.goto(`${origin}/dashboard`);
  await a.page.waitForURL("**/setup");
  await a.page.getByLabel("Setup code", { exact: true }).fill(code);
  await action(a.page, "Continue").click();
  await action(a.page, "Set up a new Atlas").click();
  await a.page.getByLabel("Name", { exact: true }).fill(primary.name);
  await a.page.getByLabel("Email", { exact: true }).fill(primary.email);
  await a.page.getByLabel("Password", { exact: true }).fill(primary.password);
  await a.page.getByLabel("Confirm password", { exact: true }).fill(primary.password);
  await action(a.page, "Create administrator").click();
  await a.page.waitForURL("**/login");
  await login(a.page, primary);

  const invitation = a.page.getByRole("region", { name: "Optional guided setup" });
  await invitation.waitFor();
  const href = await link(invitation, "Start guided setup").getAttribute("href");
  const apiSite = `${api}${href}`;
  let releaseLoad;
  const loadingRequest = new Promise(resolve => { releaseLoad = resolve; });
  await a.page.route(apiSite, async (route) => {
    await loadingRequest;
    await route.continue();
  }, { times: 1 });
  await link(invitation, "Start guided setup").click();
  await a.page.getByRole("status").filter({ hasText: "Loading setup progress" }).waitFor();
  releaseLoad();
  await heading(a.page, "Environment").waitFor();
  await a.page.getByText("Homelab", { exact: true }).last().waitFor();
  await a.page.goBack();
  await invitation.waitFor();
  await action(invitation, "Set up manually").click();
  await invitation.waitFor({ state: "detached" });
  await a.page.reload();
  await link(a.page, "Guided setup").waitFor();
  assert.equal(await invitation.count(), 0);

  const roles = await (await a.context.request.get(`${api}/roles`)).json();
  for (const [account, roleName] of [[second, "Master Administrator"], [viewer, "Viewer"]]) {
    const response = await a.context.request.post(`${api}/users`, { data: {
      email: account.email, display_name: account.name, temporary_password: account.password, force_password_change: false,
      assignments: [{ role_id: roles.find(role => role.name === roleName).id, scope_type: "global" }],
    } });
    assert.equal(response.status(), 201);
  }
  const c = await openPage();
  await login(c.page, viewer);
  const viewerInvitation = c.page.getByRole("region", { name: "Optional guided setup" });
  await viewerInvitation.waitFor();
  assert.equal(await link(viewerInvitation, "Start guided setup").count(), 0);
  await action(viewerInvitation, "Dismiss invitation").click();
  await viewerInvitation.waitFor({ state: "detached" });

  await link(a.page, "Guided setup").click();
  await heading(a.page, "Environment").waitFor();
  assert.equal(await link(a.page, "Open Site setup").getAttribute("href"), href);
  await link(a.page, "Open Site setup").click();
  await a.page.waitForURL(`${origin}${href}`);
  await action(a.page, "Rename Customer").click();
  await namedChange(a.page, "Rename Customer", "Customer name", "Renamed Home");
  await action(a.page, "Rename Site").click();
  await namedChange(a.page, "Rename Site", "Site name", "Renamed Homelab");
  await a.page.getByText("Renamed Homelab", { exact: true }).waitFor();
  await checkLayouts(a.page, "Environment");

  const b = await openPage();
  await login(b.page, second);
  await link(b.page, "Start guided setup").click();
  await heading(b.page, "Environment").waitFor();
  await a.page.getByRole("radio", { name: /Blank/ }).focus();
  await a.page.keyboard.press("Space");
  assert.equal(await a.page.getByRole("radio", { name: /Blank/ }).isChecked(), true);
  assert.equal(await a.page.getByRole("radio", { name: /Blank/ }).evaluate(el => el.matches(":focus-visible")), true);
  await action(a.page, "Save & exit").focus();
  await a.page.keyboard.press("Enter");
  await a.page.waitForURL("**/dashboard");
  const draft = (await (await a.context.request.get(apiSite)).json()).progress;
  assert.equal(draft.draft_profile, "blank");
  assert.equal(draft.environment_profile, null);
  assert.deepEqual(draft.stage_decisions, {});
  await c.page.goto(`${origin}${href}`);
  await heading(c.page, "Environment").waitFor();
  assert.equal(await c.page.getByRole("radio", { name: /Blank/ }).isDisabled(), true);
  for (const label of ["Resume setup", "Save & exit", "Confirm Environment", "Rename Site", "Rename Customer"]) {
    assert.equal(await action(c.page, label).count(), 0);
  }
  await action(b.page, "Save & exit").click();
  const draftConflict = b.page.getByRole("alert").filter({ hasText: "Setup progress changed" });
  await draftConflict.waitFor();
  assert.equal(await draftConflict.evaluate(el => el === document.activeElement), true);
  await action(b.page, "Reload progress").click();
  await action(b.page, "Resume setup").waitFor();
  assert.equal(await b.page.getByRole("radio", { name: /Blank/ }).isChecked(), true);
  await link(a.page, "Resume").click();
  await resumeWithKeyboard(a.page, "Environment");
  assert.equal(await a.page.getByRole("radio", { name: /Blank/ }).isChecked(), true);
  await action(b.page, "Resume setup").click();
  await action(b.page, "Confirm Environment").waitFor();
  await action(a.page, "Confirm Environment").click();
  await heading(a.page, "Capabilities").waitFor();
  assert.equal(await heading(a.page, "Capabilities").evaluate(el => el === document.activeElement), true);
  const rejected = b.page.waitForResponse(response => response.url() === `${apiSite}/environment`
    && response.request().method() === "PATCH");
  await action(b.page, "Confirm Environment").click();
  assert.equal((await rejected).status(), 409);
  const conflict = b.page.getByRole("alert").filter({ hasText: "Setup progress changed" });
  await conflict.waitFor();
  assert.equal(await conflict.evaluate(el => el === document.activeElement), true);
  await action(b.page, "Reload progress").click();
  await heading(b.page, "Capabilities").waitFor();
  await b.page.getByText("Blank", { exact: true }).waitFor();
  await checkLayouts(a.page, "Capabilities");
  assert.equal(await a.page.getByRole("button", { name: /Finish/ }).count(), 0);
  await action(a.page, "Back to Environment").click();
  await heading(a.page, "Environment").waitFor();
  assert.equal(await a.page.getByRole("combobox").count(), 0);
  await action(a.page, "Return to current stage").click();
  await action(a.page, "Save & exit").click();
  await a.page.waitForURL("**/dashboard");
  await link(a.page, "Resume").click();
  await resumeWithKeyboard(a.page, "Capabilities");
  await action(a.page, "Save & exit").waitFor();
  await a.page.reload();
  await heading(a.page, "Capabilities").waitFor();
  assert.equal(a.page.url(), `${origin}${href}`);
  await action(a.page, "Save & exit").click();
  await a.page.waitForURL("**/dashboard");

  await c.page.goto(`${origin}${href}`);
  await heading(c.page, "Capabilities").waitFor();
  await c.page.getByText("Renamed Homelab", { exact: true }).waitFor();
  assert.equal(await action(c.page, "Resume setup").count(), 0);
  await link(c.page, "Return to Atlas").click();
  await c.page.waitForURL("**/dashboard");
  assert.equal(await link(c.page, "Guided setup").count(), 0);

  const bootstrap = await (await a.context.request.get(apiSite)).json();
  await link(a.page, "Guided setup").click();
  await action(a.page, "Create Customer").click();
  await namedChange(a.page, "Create Customer", "Customer name", "Existing workshop");
  const selectedCustomer = await a.page.getByRole("combobox", { name: "Customer", exact: true }).inputValue();
  assert.notEqual(selectedCustomer, bootstrap.customer.id);
  await a.page.route(`**/api/sites`, async route => {
    if (route.request().method() === "POST") {
      await route.fulfill({ status: 503, json: { detail: "Site creation temporarily unavailable" } });
    } else {
      await route.continue();
    }
  }, { times: 1 });
  await action(a.page, "Create Site").click();
  const siteForm = a.page.getByRole("form", { name: "Create Site", exact: true });
  await siteForm.getByLabel("Site name", { exact: true }).fill("Workshop floor");
  await action(siteForm, "Create Site").click();
  await siteForm.getByRole("alert").waitFor();
  assert.equal(await a.page.getByRole("combobox", { name: "Customer", exact: true }).inputValue(), selectedCustomer);
  await action(siteForm, "Create Site").click();
  await siteForm.waitFor({ state: "detached" });
  const workshopHref = await link(a.page, "Open Site setup").getAttribute("href");
  const workshopSite = workshopHref.split("/").at(-1);
  const network = await a.context.request.post(`${api}/networks`, { data: {
    name: "Retained LAN", customer_id: selectedCustomer, site_id: workshopSite, network_type: "lan",
  } });
  assert.equal(network.status(), 201);

  await link(a.page, "Return to Atlas").click();
  await a.page.waitForURL("**/dashboard");
  await link(a.page, "Guided setup").click();
  await heading(a.page, "Environment").waitFor();
  const customerSelect = a.page.getByRole("combobox", { name: "Customer", exact: true });
  const siteSelect = a.page.getByRole("combobox", { name: "Site", exact: true });
  assert.equal(await customerSelect.inputValue(), "");
  assert.equal(await siteSelect.inputValue(), "");
  await customerSelect.selectOption(selectedCustomer);
  await siteSelect.selectOption(workshopSite);
  await link(a.page, "Open Site setup").click();
  await a.page.waitForURL(`${origin}${workshopHref}`);
  await heading(a.page, "Environment").waitFor();
  assert.equal((await (await a.context.request.get(`${api}${workshopHref}`)).json()).invitation.offered, false);
  assert.equal((await (await a.context.request.get(apiSite)).json()).progress.environment_profile, "blank");
  await link(a.page, "Atlas Impact home").click();
  await a.page.waitForURL("**/dashboard");
  await a.page.getByRole("combobox", { name: "Active customer" }).selectOption(selectedCustomer);
  const resumeOther = a.page.getByRole("region", { name: "Guided setup" });
  await resumeOther.getByText("Renamed Homelab", { exact: true }).waitFor();
  await link(resumeOther, "Resume").click();
  await a.page.waitForURL(`${origin}${href}`);
  await heading(a.page, "Capabilities").waitFor();
  assert.equal(await a.page.locator(".context-selector").count(), 0);
  for (const [theme, accent] of [["light", "#2563EB"], ["dark", "#7C3AED"]]) {
    const updated = await a.context.request.patch(`${api}/auth/profile`, { data: {
      display_name: primary.name, theme_mode: theme, accent_colour: accent,
    } });
    assert.equal(updated.status(), 200);
    await a.page.reload();
    await heading(a.page, "Capabilities").waitFor();
    assert.equal(await a.page.locator(".app-shell").evaluate(el => el.style.getPropertyValue("--accent")), accent);
    assert.equal(await a.page.locator("html").getAttribute("data-theme"), theme);
    assert.equal(await a.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    accents.push({ theme, accent });
  }
  const capabilities = await checkCapabilities({
    a, b, c, origin, api, output, workshopHref, selectedCustomer, workshopSite, blankHref: href,
    login, openPage, credentials, action, link, heading, resumeWithKeyboard,
  });
  const integrations = process.env.ATLAS_E1D_LIVE === "true" ? await checkIntegrations({
    a, b, c, origin, api, output, workshopHref, blankHref: href, action, heading, resumeWithKeyboard,
  }) : null;
  const discoveryReview = integrations ? await checkDiscoveryReview({
    a, b, c, origin, api, output, workshopHref, blankHref: href, action, heading, resumeWithKeyboard,
  }) : null;
  const linkServices = process.env.ATLAS_E1F_LIVE === "true" ? await checkLinkServices({
    a, b, c, origin, api, output, action, heading, openPage, resumeWithKeyboard,
  }) : null;
  const stageNavigation = process.env.ATLAS_E1G_LIVE === "true" ? await checkStageNavigation({
    a, b, origin, api, action, heading,
  }) : null;
  const reviewReady = process.env.ATLAS_E1G_LIVE === "true" ? await checkReviewReady({
    a, b, origin, api, output, workshopHref, openPage, action, link, heading, resumeWithKeyboard,
  }) : null;
  assert.deepEqual(pageErrors, []);
  await writeFile(`${output}/report.json`, JSON.stringify({ layouts, accents, capabilities, integrations, discoveryReview, linkServices, reviewReady, stageNavigation, pageErrors, liveAuthentication: true }, null, 2));
  console.log(`PASS: live Environment and Capabilities, shared drafts and conflicts, keyboard and permissions, atomic Apply and receipt replay, additional import, ${layouts.length + capabilities.layouts.length} responsive/theme layouts.`);
  if (integrations) console.log(`PASS: live Add Integrations, verified installation, probe, discovery and recovery, ${integrations.layouts.length} responsive/theme layouts.`);
  if (discoveryReview) console.log(`PASS: live Discovery Review, versioned acceptance and PostgreSQL verification, uncertain response recovery, Skip and Link Services, ${discoveryReview.layouts.length} responsive/theme layouts.`);
  if (linkServices) console.log(`PASS: live Link Services, scoped dependency writes, uncertainty recovery, permissions, Save & exit, Continue and Skip, ${linkServices.layout.length} responsive/theme layouts.`);
  if (reviewReady) console.log(`PASS: live Review & Ready, advisory progression, confirmed Knowledge Gaps, revisit, stale-read and conflict recovery, ${reviewReady.layouts.length} responsive/theme layouts.`);
  if (stageNavigation) console.log("PASS: authoritative stage return, superseded workflow reads, and local Capabilities edits across revisits.");
} finally {
  await browser.close();
}
