import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { randomBytes, randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const run = promisify(execFile);
const apiDirectory = fileURLToPath(new URL("../../api/", import.meta.url));

export async function checkShowcase({ a, b, api, origin, output, workshopHref, action, link, heading, openPage, resumeWithKeyboard }) {
  const { page } = a;
  const layouts = [];
  const suffix = randomUUID().slice(0, 8);
  const pathFor = ({ customer, site }) => `/onboarding/${customer}/${site}`;
  const ids = href => href.split("/").slice(-2);
  const scope = ([customer, site]) => ({ "X-Atlas-Customer-ID": customer, "X-Atlas-Site-ID": site });

  async function request(actor, method, path, data, status = 200, headers) {
    const response = await actor.context.request.fetch(api + path, { method, data, headers });
    assert.equal(response.status(), status, `${method} ${path}: ${await response.text()}`);
    return response.json();
  }
  const get = path => request(a, "GET", path);
  const post = (path, data, status = 201) => request(a, "POST", path, data, status);
  const progress = async href => (await get(href)).progress;
  const projection = href => get(href + "/showcase");
  async function database(command, href) {
    const { stdout } = await run(process.env.ATLAS_E1H_TEST_PYTHON || ".venv/bin/python", [
      "-m", "tests.seed_onboarding_integration_browser", command, ...ids(href),
    ], { cwd: apiDirectory });
    return stdout ? JSON.parse(stdout) : null;
  }

  async function siteFor(label, customerId) {
    const customer = customerId || (await post("/customers", { name: `${label} ${suffix}` })).id;
    const site = await post("/sites", { customer_id: customer, name: label });
    return pathFor({ customer, site: site.id });
  }

  async function reach(href, profile = "blank") {
    let state = await progress(href) || await post(href + "/start", undefined, 200);
    if (state.status === "saved") state = await post(href + "/resume", { version: state.version }, 200);
    if (state.current_stage === "environment") state = await request(a, "PATCH", href + "/environment", {
      version: state.version, environment_profile: profile,
    });
    for (const [stage, endpoint, body] of [
      ["capabilities", "capabilities/skip", {}],
      ["integrations", "integrations/decision", { decision: "skipped" }],
      ["discovery_review", "discovery-review/decision", { decision: "skipped" }],
      ["link_services", "link-services/decision", { action: "skip" }],
      ["review_ready", "review-ready/decision", {}],
    ]) {
      if (state.current_stage === stage) state = await post(`${href}/${endpoint}`, { version: state.version, ...body }, 200);
    }
    assert.equal(state.current_stage, "showcase");
    return state;
  }

  async function load(href) {
    await page.goto(origin + href);
    await heading(page, "Showcase").waitFor();
    await heading(page, "Your capabilities").waitFor();
  }

  async function capture(scenario, href, view) {
    for (const [theme, accent] of [["light", "#2563EB"], ["dark", "#7C3AED"]]) {
      await request(a, "PATCH", "/auth/profile", { display_name: "Onboarding Administrator", theme_mode: theme, accent_colour: accent });
      await page.reload();
      await heading(page, view).waitFor();
      if (view === "Showcase") await heading(page, "Your capabilities").waitFor();
      else await link(page.locator(".page-header"), "Guided setup").waitFor();
      assert.equal(await page.locator("html").getAttribute("data-theme"), theme);
      assert.equal(await page.locator(".app-shell").evaluate(el => el.style.getPropertyValue("--accent")), accent);
      const widths = view === "Dashboard" ? [1440, 390] : [1440, 1024, 900, 390];
      for (const width of widths) {
        await page.setViewportSize({ width, height: 950 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${scenario} ${theme} ${width}`);
        if (view === "Dashboard" && width === 1440) {
          const title = await heading(page, "Dashboard").boundingBox();
          const button = await link(page.locator(".page-header"), "Guided setup").boundingBox();
          assert.ok(button.x > title.x + title.width && Math.abs(button.y - title.y) < 30);
        }
        await page.screenshot({ path: `${output}/e1h-${scenario}-${theme}-${width}.png`, fullPage: true });
        layouts.push({ scenario, theme, width, href });
      }
    }
    await page.setViewportSize({ width: 1440, height: 950 });
  }

  const [types, levels, relationships] = await Promise.all([get("/service-types"), get("/criticality-levels"), get("/relationship-types")]);
  const service = (href, name) => {
    const [customer_id, site_id] = ids(href);
    return post("/services", { customer_id, site_id, name,
      service_type_id: types.find(type => type.key === "application_service").id,
      criticality_level_id: levels.find(level => level.key === "medium").id,
    });
  };
  const asset = (href, name, asset_type) => {
    const [customer_id, site_id] = ids(href);
    return post("/assets", { customer_id, site_id, name, asset_type });
  };

  const workshop = await reach(workshopHref, "homelab");
  assert.equal(workshop.stage_decisions.capabilities, "completed");
  const [customer_id, site_id] = ids(workshopHref);
  const siblingHref = await siteFor("Another Site remains eligible", customer_id);
  const longName = `A ${"LongRecordedCapability".repeat(6)}`;
  const longService = `Manual ${"LongServiceName".repeat(8)}`;
  await request(a, "PATCH", `/sites/${site_id}`, { name: `Site ${"LongEnvironmentName".repeat(6)}` });
  await request(a, "PATCH", `/customers/${customer_id}`, { name: `Customer ${"LongEnvironmentName".repeat(6)}` });
  const fn = await post("/business-functions", { customer_id, site_id, name: longName });
  const workService = await service(workshopHref, longService);
  await post(`/services/${workService.id}/business-functions`, { business_function_id: fn.id });
  const provider = await asset(workshopHref, "Showcase provider", "virtual_machine");
  const host = await asset(workshopHref, "Showcase host", "physical_server");
  const retired = await asset(workshopHref, "Showcase retired", "virtual_machine");
  await request(a, "PATCH", `/assets/${retired.id}`, { status: "retired" });
  const dependency = relationships.find(row => row.key === "depends_on");
  await post(`/services/${workService.id}/asset-dependencies`, { asset_id: provider.id, relationship_type_id: dependency.id });
  await request(a, "POST", "/asset-relationships", {
    source_asset_id: host.id, target_asset_id: provider.id, relationship_type: dependency.key,
  }, 201, scope(ids(workshopHref)));
  await post("/networks", { customer_id, site_id, name: "Showcase LAN", network_type: "lan" });
  await database("review-history", workshopHref);
  const summary = await projection(workshopHref);
  assert.ok(summary.assets.total >= 2 && summary.mappings.linked > 0 && summary.mappings.unlinked > 0);
  assert.ok(summary.required_gaps > 0 && summary.integrations.active_runs > 0);
  const snapshot = await database("showcase-snapshot", workshopHref);
  await load(workshopHref);
  await page.getByText(longName, { exact: true }).waitFor();
  await page.getByText(longService, { exact: true }).waitFor();
  const typeName = summary.assets.by_type.find(row => row.name === "Virtual Machine");
  assert.ok(typeName);
  const typeRow = page.getByRole("listitem").filter({ has: page.getByText(typeName.name, { exact: true }) });
  await typeRow.getByText(typeName.count.toLocaleString(), { exact: true }).waitFor();
  for (const [label, count] of [
    ["Services linked to Assets", summary.mappings.linked],
    ["Services with no Site mapping", summary.mappings.unlinked],
    ["Service-to-Asset mappings", summary.mappings.mappings],
  ]) {
    const term = page.getByText(label, { exact: true });
    await term.locator("..").getByText(count.toLocaleString(), { exact: true }).waitFor();
  }
  await capture("populated", workshopHref, "Showcase");

  await action(page, "Back to Review & Ready").click();
  await heading(page, "Review & Ready").waitFor();
  await action(page, "Return to current stage").click();
  await heading(page, "Your capabilities").waitFor();
  await action(page, "Open Knowledge Graph").focus();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Shift+Tab");
  assert.notEqual(await action(page, "Open Knowledge Graph").evaluate(el => getComputedStyle(el).outlineStyle), "none");
  await page.keyboard.press("Enter");
  await page.waitForURL("**/knowledge-graph");
  await page.getByRole("combobox", { name: "Active site" }).waitFor();
  assert.equal(await page.getByRole("combobox", { name: "Active site" }).inputValue(), site_id);
  await page.goBack();
  await heading(page, "Your capabilities").waitFor();
  await action(page, "Open Topology").click();
  await page.waitForURL("**/topology");
  await page.goBack();
  await heading(page, "Your capabilities").waitFor();
  const analysisResponse = page.waitForResponse(response => response.url().startsWith(api + "/dependency-analysis?") && response.status() === 200);
  await action(page, "Preview dependency analysis").click();
  await page.waitForURL(/\/knowledge-graph\?.*analysis=unavailable/);
  await page.getByRole("region", { name: "Hypothetical scenario" }).waitFor();
  await analysisResponse;
  await page.goBack();
  await heading(page, "Your capabilities").waitFor();
  assert.deepEqual(await database("showcase-snapshot", workshopHref), snapshot);

  await action(page, "Save & exit").click();
  await page.waitForURL("**/dashboard");
  const card = page.getByRole("region", { name: "Guided setup", exact: true });
  await card.getByText("Step 7 of 7 · Showcase").waitFor();
  const saved = await database("showcase-snapshot", workshopHref);
  assert.equal(saved.workflow.status, "saved");
  assert.equal(saved.workflow.completed_at, null);
  await link(card, "Resume").click();
  await resumeWithKeyboard(page, "Showcase");
  await heading(page, "Your capabilities").waitFor();
  const active = await progress(workshopHref);
  await request(b, "POST", workshopHref + "/save", { version: active.version });
  const finish = action(page, "Finish setup & explore Atlas");
  await finish.click();
  await page.getByRole("alert").filter({ hasText: "Setup progress changed" }).waitFor();
  await action(page, "Reload progress").click();
  await resumeWithKeyboard(page, "Showcase");
  await heading(page, "Your capabilities").waitFor();

  // Commit once, drop the response, and read the state from the real API.
  let completionPosts = 0;
  const finishUrl = api + workshopHref + "/complete";
  const loseFirstReply = async route => {
    completionPosts += 1;
    if (completionPosts > 1) return route.continue();
    const response = await route.fetch();
    assert.equal(response.status(), 200);
    await route.abort("failed");
  };
  await page.route(finishUrl, loseFirstReply);
  await finish.evaluate(button => { button.click(); button.click(); });
  await page.getByText("Atlas verified that setup is complete for this Site.").waitFor();
  await page.unroute(finishUrl, loseFirstReply);
  assert.equal(completionPosts, 1);
  assert.equal(await finish.count(), 0);
  const completed = await database("showcase-snapshot", workshopHref);
  assert.equal(completed.workflow.status, "completed");
  assert.deepEqual(completed.completion_audits, [(await get("/auth/me")).id]);
  assert.deepEqual(completed.domain, snapshot.domain);
  assert.ok(completed.workflow.completed_at && completed.workflow.decisions.showcase === "completed");

  await action(page, "Return to Dashboard").click();
  await page.waitForURL("**/dashboard");
  const dashboardButton = link(page.locator(".page-header"), "Guided setup");
  await dashboardButton.waitFor();
  assert.equal(await card.count(), 0);
  assert.equal(await link(page, "Guided setup").count(), 1);
  await capture("dashboard-completed", workshopHref, "Dashboard");
  await dashboardButton.click();
  await page.getByText("Setup is complete for this Site.").waitFor();
  await action(page, "Back to Review & Ready").click();
  await heading(page, "Review & Ready").waitFor();
  await action(page, "Back to Link Services").click();
  await heading(page, "Link Services").waitFor();
  await action(page, "Return to current stage").click();
  await action(page, "Return to Dashboard").click();
  await page.waitForURL("**/dashboard");
  assert.deepEqual(await database("showcase-snapshot", workshopHref), completed);
  assert.equal((await get(siblingHref)).status, "not_started");

  const partlyHref = await siteFor("Partially configured Site");
  await service(partlyHref, "Manual alerting");
  const [partlyCustomer, partlySite] = ids(partlyHref);
  await request(a, "POST", "/discovery/simulate", {
    customer_id: partlyCustomer, site_id: partlySite,
    observations: [{ name: "Outstanding discovery", external_id: `e1h-${suffix}`, asset_type: "virtual_machine" }],
  }, 200, scope(ids(partlyHref)));
  await reach(partlyHref, "homelab");
  await load(partlyHref);
  await capture("partial", partlyHref, "Showcase");
  const partialBefore = await database("showcase-snapshot", partlyHref);

  // The mutation succeeds even when the secondary workspace request fails.
  await page.route(api + partlyHref + "/showcase", route => route.fulfill({ status: 503, json: { detail: "Unavailable" } }), { times: 1 });
  await page.reload();
  await page.getByRole("alert").filter({ hasText: "temporarily unavailable" }).waitFor();
  await page.route(api + "/context", route => route.fulfill({ status: 503, json: { detail: "Temporarily unavailable" } }), { times: 1 });
  await finish.focus();
  await page.keyboard.press("Enter");
  await page.waitForURL("**/dashboard");
  await link(page, "View completed setup").waitFor();
  const partialAfter = await database("showcase-snapshot", partlyHref);
  assert.deepEqual(partialAfter.domain, partialBefore.domain);
  assert.equal(partialAfter.workflow.status, "completed");
  assert.equal(partialAfter.completion_audits.length, 1);

  const blankHref = await siteFor("Blank manual Site");
  await reach(blankHref);
  await asset(blankHref, "Manually recorded system", "physical_server");
  await load(blankHref);
  await capture("blank", blankHref, "Showcase");
  await database("showcase-inventory", blankHref);
  await load(blankHref);
  await page.setViewportSize({ width: 390, height: 950 });
  await page.getByText("Non-retired Assets", { exact: true }).locator("..").getByText("12,346", { exact: true }).waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.screenshot({ path: `${output}/e1h-large-metric-dark-390.png`, fullPage: true });
  await page.setViewportSize({ width: 1440, height: 950 });
  const emptyHref = await siteFor("Empty Site");
  await reach(emptyHref);
  await page.route(api + emptyHref + "/showcase", route => route.fulfill({ status: 503, json: { detail: "Unavailable" } }), { times: 1 });
  await page.goto(origin + emptyHref);
  await page.getByRole("alert").filter({ hasText: "temporarily unavailable" }).waitFor();
  assert.equal(await finish.isEnabled(), true);
  await action(page, "Retry Showcase").click();
  await page.getByText("No non-retired Assets recorded at this Site yet.").waitFor();
  assert.equal(await action(page, "Preview dependency analysis").count(), 0);
  await capture("empty", emptyHref, "Showcase");

  // A failed request without a commit is checked against the workflow before retry.
  const emptyVersion = await progress(emptyHref);
  await page.route(api + emptyHref + "/complete", route => route.fulfill({ status: 502, json: { detail: "Unavailable" } }), { times: 1 });
  await finish.click();
  await page.getByRole("alert").filter({ hasText: "Setup is still in progress" }).waitFor();
  assert.deepEqual(await progress(emptyHref), emptyVersion);

  const role = await post("/roles", { name: `E1-H workflow only ${suffix}`, permission_keys: ["customers.view", "sites.view", "sites.manage"] });
  const email = `e1h-${suffix}@example.com`;
  const password = randomBytes(24).toString("base64url");
  const [emptyCustomer, emptySite] = ids(emptyHref);
  const restrictedUser = await post("/users", { email, display_name: "Showcase operator", temporary_password: password,
    force_password_change: false, assignments: [{ role_id: role.id, scope_type: "site", customer_id: emptyCustomer, site_id: emptySite }],
  });
  const restricted = await openPage();
  try {
    await request(restricted, "POST", "/auth/login", { email, password });
    await restricted.page.goto(origin + emptyHref);
    await heading(restricted.page, "Your capabilities").waitFor();
    await restricted.page.getByText("Restricted", { exact: true }).first().waitFor();
    assert.equal(await action(restricted.page, "Open Knowledge Graph").count(), 0);
    await restricted.page.screenshot({ path: `${output}/e1h-restricted-light-1440.png`, fullPage: true });

    // Another administrator completes during an uncertain reply. The first
    // browser reports shared completion, and PostgreSQL credits that operator.
    await page.route(api + emptyHref + "/complete", async route => {
      await request(restricted, "POST", emptyHref + "/complete", { version: emptyVersion.version });
      await route.abort("failed");
    }, { times: 1 });
    await finish.click();
    await page.getByText("Atlas verified that setup is complete for this Site.").waitFor();
    const persisted = await database("showcase-snapshot", emptyHref);
    assert.deepEqual(persisted.completion_audits, [restrictedUser.id]);
    assert.equal(persisted.workflow.last_actor_id, restrictedUser.id);
  } finally {
    await restricted.context.close();
  }

  return { layouts, duplicateActivationGuarded: true, dashboardHandoffRecovered: true, competingActorVerified: true,
    uncertainResponseChecked: true, canonicalStatePreserved: true, completionAudits: completed.completion_audits.length };
}
