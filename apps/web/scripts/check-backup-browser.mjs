// H3 production UI/API/PostgreSQL/nginx acceptance. Secrets arrive on stdin,
// stay in memory, and never enter screenshots, traces or the report.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
const { chromium } = await import(pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href);
let input = "";
for await (const chunk of process.stdin) input += chunk;
const { sourceCode, targetCode, password, passphrase } = JSON.parse(input);
input = "";
const source = process.env.ATLAS_BROWSER_BASE_URL;
const target = process.env.ATLAS_BROWSER_TARGET_URL;
const output = process.env.ATLAS_BROWSER_OUTPUT;
const email = "h3-browser@example.com";
await mkdir(output, { recursive: true, mode: 0o700 });
const errors = [];
let stage = "launch", lastStep = -1;
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
async function otp(seed) {
  while (Math.floor(Date.now() / 30000) <= lastStep) await new Promise(resolve => setTimeout(resolve, 500));
  lastStep = Math.floor(Date.now() / 30000);
  const result = spawnSync(process.env.ATLAS_TEST_PYTHON, ["-c", "import sys,pyotp;print(pyotp.TOTP(sys.stdin.read()).now())"], { input: seed, encoding: "utf8" });
  if (result.status) throw new Error("Test authenticator unavailable");
  return result.stdout.trim();
}
function captureErrors(page) { page.on("pageerror", () => errors.push(stage)); }
async function checkSettingsCards(page) {
  const cards = await page.evaluate(() => [
    'section[aria-labelledby="settings-general"]', "#settings-backup", 'section[aria-labelledby="settings-about"]',
  ].map(selector => {
    const card = document.querySelector(selector);
    const heading = card.querySelector("h2");
    const style = getComputedStyle(card), headingStyle = getComputedStyle(heading);
    const box = card.getBoundingClientRect();
    return {
      family: [style.backgroundColor, style.borderColor, style.borderStyle, style.borderWidth,
        style.borderRadius, style.paddingTop, style.paddingRight, style.paddingBottom, style.paddingLeft],
      heading: [headingStyle.fontSize, headingStyle.fontWeight, headingStyle.lineHeight],
      left: box.left, width: box.width, top: box.top, bottom: box.bottom,
      contentLeft: box.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft),
      contentRight: box.right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight),
      headingLeft: heading.getBoundingClientRect().left,
      nestedCards: card.querySelectorAll(".ops-card").length,
    };
  }));
  for (const card of cards.slice(1)) {
    assert.deepEqual(card.family, cards[0].family, "System Settings cards share border, background, radius and padding");
    assert.deepEqual(card.heading, cards[0].heading, "System Settings heading hierarchy matches");
    assert.ok(Math.abs(card.left - cards[0].left) < 1 && Math.abs(card.width - cards[0].width) < 1, "Card outer edges match");
    assert.ok(Math.abs(card.headingLeft - cards[0].headingLeft) < 1, "Card headings align");
  }
  assert.equal(cards[1].nestedCards, 0, "Backup & Restore has one outer card");
  assert.ok(Math.abs((cards[1].top - cards[0].bottom) - (cards[2].top - cards[1].bottom)) < 1, "Adjacent card spacing matches");
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, "No horizontal page overflow");
  for (const name of ["Create backup", "Restore backup"]) {
    const button = await page.getByRole("button", { name, exact: true }).boundingBox();
    assert.ok(button.width < cards[1].contentRight - cards[1].contentLeft - 1, "Actions keep their natural width");
    assert.ok(button.x >= cards[1].contentLeft - 1 && button.x + button.width <= cards[1].contentRight + 1, "Actions stay within the card padding");
  }
}
async function login(page, origin, seed) {
  await page.goto(`${origin}/login`);
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  if (seed) {
    await page.getByLabel("Authenticator code", { exact: true }).fill(await otp(seed));
    await page.getByRole("button", { name: "Verify and sign in", exact: true }).click();
  }
  await page.waitForURL("**/dashboard");
}
async function restoreForm(page, file, phrase, fresh, seed) {
  await page.getByLabel("Atlas backup file", { exact: true }).setInputFiles(file);
  await page.getByLabel("Backup passphrase", { exact: true }).fill(phrase);
  if (!fresh) {
    await page.getByLabel("Current password", { exact: true }).fill(password);
    await page.getByLabel("Current authenticator or recovery code", { exact: true }).fill(await otp(seed));
    await page.getByLabel("Type RESTORE to confirm replacement", { exact: true }).fill("RESTORE");
  }
  await page.getByRole("button", { name: fresh ? "Restore Atlas" : "Replace Atlas data", exact: true }).click();
}
try {
  const context = await browser.newContext();
  const page = await context.newPage(); captureErrors(page);
  stage = "source setup";
  await page.goto(`${source}/setup`);
  await page.getByLabel("Setup code", { exact: true }).fill(sourceCode);
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Set up a new Atlas", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill("H3 browser administrator");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Create administrator", exact: true }).click();
  await page.waitForURL("**/login");
  await login(page, source);
  const scope = await (await context.request.get(`${source}/api/context`)).json();
  const created = await context.request.post(`${source}/api/assets`, { data: {
    customer_id: scope.customers[0].id, site_id: scope.sites[0].id, name: "H3 backed-up host", asset_type: "server",
  } });
  assert.equal(created.status(), 201);
  const asset = await created.json();
  stage = "MFA enrollment";
  await page.goto(`${source}/profile`);
  const security = page.getByRole("region", { name: "Two-factor authentication", exact: true });
  await security.getByRole("button", { name: "Enable two-factor authentication", exact: true }).click();
  await security.getByLabel("Current password", { exact: true }).fill(password);
  await security.getByRole("button", { name: "Continue", exact: true }).click();
  const secret = await security.getByLabel("Manual setup key", { exact: true }).inputValue();
  await security.getByLabel("Authenticator code", { exact: true }).fill(await otp(secret));
  await security.getByRole("button", { name: "Confirm authenticator", exact: true }).click();
  await security.getByRole("button", { name: "I have saved my recovery codes", exact: true }).click();
  stage = "settings card consistency";
  await page.goto(`${source}/admin/system-settings`);
  await page.getByRole("heading", { name: "Backup & Restore", exact: true }).waitFor();
  const appearance = await (await context.request.get(`${source}/api/auth/me`)).json();
  for (const theme of ["light", "dark"]) for (const accent of [null, "#2563EB", "#7C3AED"]) {
    assert.equal((await context.request.patch(`${source}/api/auth/profile`, { data: { display_name: appearance.display_name, theme_mode: theme, accent_colour: accent } })).status(), 200);
    await page.goto(`${source}/admin/system-settings`);
    await page.getByRole("heading", { name: "Backup & Restore", exact: true }).waitFor();
    await page.getByRole("row").filter({ hasText: "Session lifetime" }).waitFor();
    await page.waitForFunction(value => document.documentElement.dataset.theme === value, theme);
    await page.evaluate(() => document.fonts.ready);
    for (const width of [1440, 1024, 800, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      await checkSettingsCards(page);
      const suffix = theme === "light" && accent === null ? `${width}` : `${theme}-${accent?.slice(1) || "default"}-${width}`;
      await page.screenshot({ path: `${output}/backup-settings-${suffix}.png`, fullPage: true });
    }
  }
  assert.equal((await context.request.patch(`${source}/api/auth/profile`, { data: { display_name: appearance.display_name, theme_mode: appearance.theme_mode, accent_colour: appearance.accent_colour } })).status(), 200);
  await page.goto(`${source}/admin/system-settings`);
  await page.getByRole("heading", { name: "Backup & Restore", exact: true }).waitFor();
  stage = "create encrypted backup";
  await page.getByRole("button", { name: "Create backup", exact: true }).click();
  await page.getByLabel("Backup passphrase", { exact: true }).fill(passphrase);
  await page.getByLabel("Confirm backup passphrase", { exact: true }).fill(passphrase);
  await page.getByLabel("Current password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Create encrypted backup", exact: true }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download encrypted backup", exact: true }).click();
  const download = await downloadPromise;
  const file = `${output}/acceptance.atlasbackup`;
  await download.saveAs(file); await chmod(file, 0o600);
  assert.match(download.suggestedFilename(), /^atlas-backup-\d{8}-\d{6}\.atlasbackup$/);
  assert.equal((await readFile(file)).subarray(0, 8).toString(), "ATLASBKP");
  stage = "later changes";
  assert.equal((await context.request.patch(`${source}/api/assets/${asset.id}`, { data: { name: "H3 changed host" } })).status(), 200);
  await page.getByRole("row").filter({ hasText: "Session lifetime" }).getByRole("button", { name: "Edit", exact: true }).click();
  await page.getByLabel("Session lifetime (minutes)", { exact: true }).fill("222");
  await page.getByRole("button", { name: "Save setting", exact: true }).click();
  await page.getByRole("status").filter({ hasText: "updated" }).waitFor();
  stage = "wrong passphrase";
  await page.getByRole("button", { name: "Restore backup", exact: true }).click();
  await restoreForm(page, file, passphrase + "incorrect", false, secret);
  await page.getByRole("alert").filter({ hasText: "Incorrect passphrase or invalid backup" }).waitFor();
  assert.equal((await (await context.request.get(`${source}/api/assets/${asset.id}`)).json()).name, "H3 changed host");
  stage = "overwrite restore";
  await restoreForm(page, file, passphrase, false, secret);
  await page.waitForURL("**/login", { timeout: 120000 });
  await login(page, source, secret);
  assert.equal((await (await context.request.get(`${source}/api/assets/${asset.id}`)).json()).name, "H3 backed-up host");
  const settings = await (await context.request.get(`${source}/api/system-settings`)).json();
  assert.equal(settings.find(setting => setting.key === "auth.session_minutes").value, 480);
  stage = "fresh setup restore";
  const fresh = await browser.newContext();
  const freshPage = await fresh.newPage(); captureErrors(freshPage);
  await freshPage.goto(`${target}/setup`);
  await freshPage.getByLabel("Setup code", { exact: true }).fill(targetCode);
  await freshPage.getByRole("button", { name: "Continue", exact: true }).click();
  await freshPage.getByRole("button", { name: "Restore existing Atlas backup", exact: true }).click();
  await restoreForm(freshPage, file, passphrase, true);
  await freshPage.waitForURL("**/login", { timeout: 120000 });
  await login(freshPage, target, secret);
  assert.equal((await (await fresh.request.get(`${target}/api/assets/${asset.id}`)).json()).name, "H3 backed-up host");
  assert.equal((await (await fresh.request.get(`${target}/api/setup/status`)).json()).state, "INITIALISED");
  assert.equal((await fresh.request.post(`${target}/api/setup/verify`, { data: { code: targetCode } })).status(), 409);
  assert.deepEqual(errors, []);
  await writeFile(`${output}/report.json`, JSON.stringify({ result: "passed", backup: true,
    overwriteRestore: true, freshRestore: true, wrongPassphraseNoChange: true, restoredMfa: true,
    widths: [1440, 1024, 800, 390], settingsCards: true, themes: ["light", "dark"],
    accents: [null, "#2563EB", "#7C3AED"], physicalAuthenticator: false, docker: false, systemd: false, errors }, null, 2));
  console.log("PASS: encrypted download, wrong passphrase, overwrite restore, fresh setup restore and restored MFA.");
} catch {
  throw new Error(`H3 browser acceptance failed at ${stage}; credentials omitted.`);
} finally { await browser.close(); }
