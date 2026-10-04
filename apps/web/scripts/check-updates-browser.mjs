// H4 acceptance against actual Next/API/PostgreSQL/nginx. The opt-in backend
// harness controls GitHub HTTP input; there is no browser route interception.
// Input credentials are ephemeral JSON on stdin, never written to artifacts.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
let input = "";
for await (const chunk of process.stdin) input += chunk;
const { code, password } = JSON.parse(input); input = "";
const origin = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3187";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-h4-browser";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
const errors = [], outsideRequests = [], checks = [];
try {
  const context = await browser.newContext();
  const page = await context.newPage();
  page.on("pageerror", error => errors.push(error.message));
  page.on("request", request => { if (!request.url().startsWith(origin)) outsideRequests.push(request.url()); });
  await page.goto(`${origin}/setup`);
  await page.getByLabel("Setup code", { exact: true }).fill(code);
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Set up a new Atlas", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill("H4 Acceptance Administrator");
  await page.getByLabel("Email", { exact: true }).fill("h4@example.com");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Create administrator", exact: true }).click();
  await page.waitForURL("**/login");
  await page.getByLabel("Email", { exact: true }).fill("h4@example.com");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL("**/dashboard");
  const card = page.getByRole("region", { name: "Updates", exact: true });
  async function scenario(scenario, method, allow_refresh = false) {
    const response = await fetch("http://127.0.0.1:3191/control", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario, method, allow_refresh }) });
    assert.equal(response.ok, true);
    await page.goto(`${origin}/admin/system-settings`);
    await card.getByText("Current version", { exact: true }).waitFor();
    await page.waitForFunction(() => !document.querySelector('[aria-labelledby="settings-updates"]')?.textContent.includes("Checking release availability"));
    const info = await (await context.request.get(`${origin}/api/system-settings/updates`)).json();
    assert.equal(info.install_method, method);
    assert.equal(info.cached, true);
    assert.equal(typeof info.build_id, "string");
    assert.equal(info.current_version, "0.1.0");
    assert.equal(info.current_channel, "beta");
    return info;
  }
  let info = await scenario("current", "docker_compose");
  assert.equal(info.status, "up_to_date");
  await card.getByText("Atlas is up to date.", { exact: true }).waitFor();
  assert.match(await card.innerText(), /Docker Compose/);
  checks.push("current release, installed identity and cache");
  info = await scenario("newer", "docker_compose");
  assert.equal(info.status, "update_available");
  await card.getByText("Atlas 0.2.0 is available.", { exact: true }).waitFor();
  assert.equal(await card.getByRole("link", { name: "View release", exact: true }).getAttribute("href"), "https://github.com/benchristian88/atlas/releases/tag/v0.2.0");
  assert.match(await card.innerText(), /existing protected configuration/);
  assert.equal(await card.getByRole("button", { name: "Check for updates" }).isDisabled(), true);
  checks.push("newer release, safe link, Docker guidance and refresh cooldown");
  info = await scenario("newer", "systemd");
  assert.match(await card.innerText(), /native release package/);
  assert.match(info.upgrade_guide_url, /#nativesystemd-upgrade$/);
  checks.push("native guidance");
  info = await scenario("newer", "development");
  assert.match(await card.innerText(), /development Git workflow/);
  assert.equal(await card.getByRole("link", { name: "Read upgrade guide" }).count(), 0);
  checks.push("development guidance");
  await scenario("current", "docker_compose", true);
  // Only the test harness shortens the refresh interval here; production cache
  // bounds are asserted above and in transport/backend concurrency tests.
  await fetch("http://127.0.0.1:3191/control", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario: "newer", method: "docker_compose", allow_refresh: true }) });
  await card.getByRole("button", { name: "Check for updates", exact: true }).click();
  await card.getByText("Atlas 0.2.0 is available.", { exact: true }).waitFor();
  checks.push("manual refresh through the real backend endpoint with test-only shortened interval");
  for (const theme of ["light", "dark"]) {
    for (const accent of [null, "#2563EB", "#9333EA"]) {
      const preference = await context.request.patch(`${origin}/api/auth/profile`, { data: { display_name: "H4 Acceptance Administrator", theme_mode: theme, accent_colour: accent } });
      assert.equal(preference.status(), 200);
      await page.reload();
      await card.getByText("Atlas 0.2.0 is available.", { exact: true }).waitFor();
      for (const width of [1440, 1024, 800, 390]) {
        await page.setViewportSize({ width, height: 1100 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        const comparison = await page.evaluate(() => {
          const update = document.querySelector('[aria-labelledby="settings-updates"]');
          const sibling = document.querySelector('[aria-labelledby="settings-general"]');
          const u = getComputedStyle(update), s = getComputedStyle(sibling);
          const fields = ["paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "borderRadius", "borderColor", "backgroundColor"];
          return { same: fields.every(field => u[field] === s[field]),
            headings: getComputedStyle(update.querySelector("h2")).fontSize === getComputedStyle(sibling.querySelector("h2")).fontSize };
        });
        assert.deepEqual(comparison, { same: true, headings: true });
        if (accent === null) await page.screenshot({ path: `${output}/updates-${theme}-${width}.png`, fullPage: true });
      }
    }
  }
  checks.push("sibling card style comparison, 24 responsive/theme/accent combinations");
  info = await scenario("unavailable", "docker_compose");
  assert.equal(info.status, "unavailable");
  await card.getByText("Update information is currently unavailable.", { exact: true }).waitFor();
  assert.equal(await card.getByRole("link", { name: "View release" }).count(), 0);
  await page.goto(`${origin}/dashboard`);
  await page.getByRole("heading", { name: "Dashboard", exact: true }).waitFor();
  assert.equal((await context.request.get(`${origin}/api/health`)).status(), 200);
  checks.push("unavailable update source, working Dashboard and API health");
  assert.deepEqual(errors, []);
  assert.deepEqual(outsideRequests, []);
  await writeFile(`${output}/report.json`, JSON.stringify({ result: "passed", checks, browserApiInterception: false, realPublicGitHubRead: false, errors, outsideRequests }, null, 2));
} finally { await browser.close(); }
