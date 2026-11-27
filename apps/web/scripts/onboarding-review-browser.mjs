import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { randomBytes, randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const run = promisify(execFile);
const apiDirectory = fileURLToPath(new URL("../../api/", import.meta.url));

export async function checkReviewReady({
  a, b, origin, api, output, workshopHref, openPage, action, link, heading, resumeWithKeyboard,
}) {
  const { page } = a;
  async function request(actor, method, path, data, status = 200, headers) {
    const response = await actor.context.request.fetch(api + path, { method, data, headers });
    assert.equal(response.status(), status, `${method} ${path} ${await response.text()}`);
    return response.json();
  }
  const get = (path, headers) => request(a, "GET", path, undefined, 200, headers);
  const post = (path, data, status = 201) => request(a, "POST", path, data, status);
  const progress = async href => (await get(href)).progress;
  const reviewPath = href => href + "/review-ready";
  const stage = "Review & Ready";
  const ready = heading(page, stage);
  const loaded = heading(page, "Setup summary");
  const next = action(page, "Continue to Showcase");
  const rail = page.getByRole("navigation", { name: "Setup stages" });
  const gapAction = action(page, "Review outstanding Knowledge Gaps");
  const mappingAction = action(page, "Review remaining unmapped Services");
  const stageRow = title => page.getByRole("listitem").filter({ has: heading(page, title) });
  const longName = `E1-G ${"LongEnvironmentName".repeat(7)}`;
  const [customerId, siteId] = workshopHref.split("/").slice(-2);
  const selected = { "X-Atlas-Customer-ID": customerId, "X-Atlas-Site-ID": siteId };
  const suffix = randomUUID().slice(0, 8);
  await request(a, "PATCH", `/customers/${customerId}`, { name: `${longName} Customer` });
  await request(a, "PATCH", `/sites/${siteId}`, { name: `${longName} Site` });

  async function reachReview(href, profile = "blank") {
    let state = await progress(href);
    if (!state) state = await post(href + "/start", undefined, 200);
    if (state.status === "saved") state = await post(href + "/resume", { version: state.version }, 200);
    if (state.current_stage === "environment") {
      state = await request(a, "PATCH", href + "/environment", { version: state.version, environment_profile: profile });
    }
    for (const [step, endpoint, body] of [
      ["capabilities", "capabilities/skip", {}],
      ["integrations", "integrations/decision", { decision: "skipped" }],
      ["discovery_review", "discovery-review/decision", { decision: "skipped" }],
      ["link_services", "link-services/decision", { action: "skip" }],
    ]) {
      if (state.current_stage === step) state = await post(`${href}/${endpoint}`, { ...body, version: state.version }, 200);
    }
    assert.equal(state.current_stage, "review_ready");
    return state;
  }

  const initial = await reachReview(workshopHref, "homelab");
  assert.equal(initial.stage_decisions.capabilities, "completed");
  const [types, levels] = await Promise.all([get("/service-types"), get("/criticality-levels")]);
  const service = (name, customer = customerId, site = siteId) => post("/services", {
    customer_id: customer, site_id: site, name,
    service_type_id: types.find(type => type.key === "application_service").id,
    criticality_level_id: levels.find(level => level.key === "medium").id,
  });
  await service("Manual Service at the confirmed Site");
  await request(a, "POST", "/discovery/simulate", {
    customer_id: customerId, site_id: siteId,
    observations: [{ name: "Proposal still outstanding", external_id: "e1g-proposal", asset_type: "virtual_machine" }],
  }, 200, selected);
  await run(process.env.ATLAS_E1G_TEST_PYTHON || ".venv/bin/python", [
    "-m", "tests.seed_onboarding_integration_browser", "review-history", customerId, siteId,
  ], { cwd: apiDirectory });
  const populated = await get(reviewPath(workshopHref));
  assert.equal(populated.profile, "homelab");
  assert.ok(populated.business_functions >= 1 && populated.services >= 2);
  assert.ok(populated.discovery.decisions.eligible > 0 && populated.link_services.unlinked > 0);
  assert.ok(populated.discovery.active_runs > 0);
  const gapRows = await get("/knowledge-gaps?include_customer_wide=true", selected);
  assert.ok(gapRows.some(gap => gap.requirement_level === "recommended"));
  assert.equal(populated.required_gaps, gapRows.filter(gap =>
    ["required", "conditional"].includes(gap.requirement_level) && ["open", "deferred"].includes(gap.status)
  ).length);

  const writes = [];
  page.on("request", req => {
    const path = new URL(req.url()).pathname;
    if (path.startsWith("/api/") && req.method() !== "GET") writes.push(`${req.method()} ${path}`);
  });
  const reviewUrl = api + reviewPath(workshopHref);
  await page.route(reviewUrl, route => route.fulfill({ status: 503, json: { detail: "Unavailable" } }), { times: 1 });
  await page.goto(origin + workshopHref);
  await ready.waitFor();
  await page.getByRole("alert").filter({ hasText: "Current setup information could not be loaded" }).waitFor();
  await action(page, "Retry review").click();
  await loaded.waitFor();
  await stageRow("Capabilities").getByText("Completed", { exact: true }).waitFor();
  await stageRow("Environment").getByText(`${longName} Customer`, { exact: true }).waitFor();
  await stageRow("Environment").getByText(`${longName} Site`, { exact: true }).waitFor();
  await action(page, "Review eligible discovery proposals").waitFor();
  await mappingAction.waitFor();
  await gapAction.waitFor();
  await action(page, "Review Integration issues").waitFor();
  const integrations = stageRow("Add integrations").getByRole("list", { name: "Configured Integrations" });
  await integrations.getByText("Failed", { exact: true }).waitFor();
  await integrations.getByText("Unconfigured", { exact: true }).waitFor();
  assert.deepEqual(writes, []);

  for (const title of ["Environment", "Capabilities", "Add integrations", "Discovery review", "Link Services"]) {
    await action(page, `Review ${title}`).click();
    await heading(page, title).waitFor();
    await action(page, "Return to current stage").click();
    await loaded.waitFor();
    assert.deepEqual(await progress(workshopHref), initial);
  }

  for (const stages of [
    ["Discovery review", "Add integrations"],
    ["Environment", "Discovery review", "Link Services"],
    ["Link Services", "Discovery review", "Add integrations", "Capabilities"],
  ]) {
    for (const title of stages) {
      await action(rail, title).click();
      await heading(page, title).waitFor();
    }
    const liveReview = page.waitForResponse(response => response.url() === reviewUrl && response.ok());
    await action(page, "Return to current stage").click();
    await liveReview;
    await loaded.waitFor();
    assert.match(await rail.locator('[aria-current="step"]').innerText(), /Review & Ready/);
    assert.deepEqual(await progress(workshopHref), initial);
  }

  let captured, release, settled;
  const capturedRead = new Promise(resolve => { captured = resolve; });
  const releaseRead = new Promise(resolve => { release = resolve; });
  const settledRead = new Promise(resolve => { settled = resolve; });
  await page.route(reviewUrl, async route => {
    try {
      const response = await route.fetch();
      captured(response.ok());
      await releaseRead;
      await route.fulfill({ response });
    } catch {
      // The prior request may already be cancelled by the stage transition.
      captured(false);
    } finally {
      settled();
    }
  }, { times: 1 });
  await page.reload();
  await page.getByRole("status").filter({ hasText: "Loading current setup information" }).waitFor();
  assert.equal(await capturedRead, true);
  await action(page, "Back to Link Services").click();
  await heading(page, "Link Services").waitFor();
  await service("Added while revisiting Link Services");
  await action(page, "Return to current stage").click();
  await loaded.waitFor();
  const mappingLabel = `${populated.link_services.linked} linked · ${populated.link_services.unlinked + 1} unlinked`;
  await stageRow("Link Services").getByText(mappingLabel, { exact: false }).waitFor();
  release();
  await settledRead;
  assert.equal(await stageRow("Link Services").getByText(mappingLabel, { exact: false }).count(), 1);
  assert.deepEqual(writes, []);

  const layouts = [];
  for (const [theme, accent] of [["light", "#2563EB"], ["dark", "#7C3AED"]]) {
    await request(a, "PATCH", "/auth/profile", { display_name: "Onboarding Administrator", theme_mode: theme, accent_colour: accent });
    await page.reload();
    await loaded.waitFor();
    assert.equal(await page.locator("html").getAttribute("data-theme"), theme);
    assert.equal(await page.locator(".app-shell").evaluate(el => el.style.getPropertyValue("--accent")), accent);
    for (const width of [1440, 1024, 800, 390]) {
      await page.setViewportSize({ width, height: 950 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      assert.equal(await page.getByRole("navigation", { name: "Setup stages" }).locator('[aria-current="step"] small').innerText(), "In progress");
      await action(page, "Save & exit").focus();
      await page.keyboard.press("Tab");
      assert.equal(await next.evaluate(el => el === document.activeElement && el.matches(":focus-visible")), true);
      if (width === 1440 || width === 390) {
        assert.equal(await gapAction.innerText(), "Review");
        assert.equal(await mappingAction.innerText(), "Review");
        assert.match(await gapAction.ariaSnapshot(), /button "Review outstanding Knowledge Gaps"/);
        assert.match(await mappingAction.ariaSnapshot(), /button "Review remaining unmapped Services"/);
        await mappingAction.press("Enter");
        await heading(page, "Link Services").waitFor();
        await action(page, "Return to current stage").press("Enter");
        await loaded.waitFor();
        await next.focus();
      }
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: `${output}/e1g-${theme}-${width}.png`, fullPage: true });
      layouts.push({ theme, accent, width });
    }
  }

  const manualCustomer = await post("/customers", { name: `Blank review ${suffix}` });
  const manualSite = await post("/sites", { customer_id: manualCustomer.id, name: "Empty manual Site" });
  const otherSite = await post("/sites", { customer_id: manualCustomer.id, name: "Secondary manual Site" });
  await post("/sites", { customer_id: customerId, name: "Secondary workshop Site" });
  const manualHref = `/onboarding/${manualCustomer.id}/${manualSite.id}`;
  const manualState = await reachReview(manualHref);
  await page.goto(origin + manualHref);
  await loaded.waitFor();
  await page.getByText("No outstanding work is visible in this review.", { exact: true }).waitFor();
  await service("Manually added after skipping Capabilities", manualCustomer.id, manualSite.id);
  await page.reload();
  await loaded.waitFor();
  const capabilities = stageRow("Capabilities");
  await capabilities.getByText("Skipped", { exact: true }).waitFor();
  assert.deepEqual(await capabilities.locator("dd").allTextContents(), ["0", "1"]);
  assert.deepEqual(await progress(manualHref), manualState);

  const role = await post("/roles", {
    name: `E1-G workflow manager ${suffix}`, permission_keys: ["customers.view", "sites.view", "sites.manage"],
  });
  const email = `e1g-${suffix}@example.com`;
  const password = randomBytes(24).toString("base64url");
  await post("/users", { email, display_name: "Review operator", temporary_password: password, force_password_change: false,
    assignments: [{ role_id: role.id, scope_type: "site", customer_id: manualCustomer.id, site_id: manualSite.id }] });
  const restricted = await openPage();
  await request(restricted, "POST", "/auth/login", { email, password });
  await restricted.page.goto(origin + manualHref);
  await heading(restricted.page, "Setup summary").waitFor();
  await restricted.page.getByText("Restricted by your permissions", { exact: true }).first().waitFor();
  assert.equal(await action(restricted.page, "Review remaining unmapped Services").count(), 0);
  assert.equal(await action(restricted.page, "Review outstanding Knowledge Gaps").count(), 0);
  await action(restricted.page, "Continue to Showcase").click();
  await heading(restricted.page, "Showcase").waitFor();
  assert.equal((await progress(manualHref)).completed_at, null);

  const contextUrl = api + "/context";
  const activeCustomer = page.getByLabel("Active customer", { exact: true });
  const activeSite = page.getByLabel("Active site", { exact: true });
  const storedContext = () => page.evaluate(() => {
    const key = Object.keys(localStorage).find(key => key.startsWith("atlas_active_context:"));
    return JSON.parse(localStorage.getItem(key));
  });
  const assertWorkspace = async (customerId, siteId) => {
    assert.equal(await activeCustomer.inputValue(), customerId);
    assert.equal(await activeSite.inputValue(), siteId);
    assert.deepEqual(await storedContext(), { customerId, siteId });
  };
  async function openWithStaleContext() {
    await page.route(contextUrl, async route => {
      const response = await route.fetch();
      const context = await response.json();
      assert.ok(context.sites.some(site => site.id === siteId));
      await route.fulfill({ response, json: { ...context, sites: context.sites.filter(site => site.id !== siteId) } });
    }, { times: 1 });
    await page.goto(origin + workshopHref);
    await loaded.waitFor();
  }

  await openWithStaleContext();
  let captureContext, releaseContext, settleContext;
  const capturedContext = new Promise(resolve => { captureContext = resolve; });
  const heldContext = new Promise(resolve => { releaseContext = resolve; });
  const settledContext = new Promise(resolve => { settleContext = resolve; });
  let heldRequest;
  await page.route(contextUrl, async route => {
    heldRequest = route.request();
    try {
      const response = await route.fetch();
      captureContext(response.ok());
      await heldContext;
      await route.fulfill({ response });
    } catch (error) {
      if (!heldRequest.failure()) throw error;
    } finally {
      settleContext();
    }
  }, { times: 1 });
  const gapRequests = [];
  const watchGaps = req => {
    if (new URL(req.url()).pathname === "/api/knowledge-gaps") gapRequests.push(req.url());
  };
  page.on("request", watchGaps);
  await gapAction.click();
  assert.equal(await capturedContext, true);
  const cancelledContext = page.waitForEvent("requestfailed", { predicate: request => request === heldRequest });
  await link(page, "Atlas Impact home").click();
  await page.waitForURL("**/dashboard");
  await activeCustomer.selectOption(manualCustomer.id);
  await activeSite.selectOption(otherSite.id);
  await assertWorkspace(manualCustomer.id, otherSite.id);
  releaseContext();
  await settledContext;
  await cancelledContext;
  assert.equal(new URL(page.url()).pathname, "/dashboard");
  await assertWorkspace(manualCustomer.id, otherSite.id);
  assert.deepEqual(gapRequests, []);
  page.off("request", watchGaps);

  await openWithStaleContext();
  await page.route(contextUrl, route => route.fulfill({ status: 503, json: { detail: "Workspace temporarily unavailable" } }), { times: 1 });
  await gapAction.click();
  await page.getByRole("alert").filter({ hasText: "Workspace temporarily unavailable" }).waitFor();
  assert.equal(new URL(page.url()).pathname, workshopHref);
  assert.deepEqual(await storedContext(), { customerId: manualCustomer.id, siteId: otherSite.id });
  await page.route(contextUrl, async route => {
    const response = await route.fetch();
    const context = await response.json();
    await route.fulfill({ response, json: { ...context, sites: context.sites.filter(site => site.id !== siteId) } });
  }, { times: 1 });
  await gapAction.click();
  await page.getByRole("alert").filter({ hasText: "The confirmed Customer and Site are no longer available" }).waitFor();
  assert.equal(new URL(page.url()).pathname, workshopHref);
  assert.deepEqual(await storedContext(), { customerId: manualCustomer.id, siteId: otherSite.id });
  const drilldown = page.waitForRequest(req => {
    const url = new URL(req.url());
    return url.pathname === "/api/knowledge-gaps" && url.searchParams.get("requirement_level") === "required_or_conditional";
  });
  await gapAction.press("Enter");
  await page.waitForURL("**/knowledge-gaps?requirement_level=required_or_conditional&status=open_or_deferred");
  const drilldownRequest = await drilldown;
  assert.equal(drilldownRequest.headers()["x-atlas-customer-id"], customerId);
  assert.equal(drilldownRequest.headers()["x-atlas-site-id"], siteId);
  assert.equal(new URL(drilldownRequest.url()).searchParams.get("include_customer_wide"), "true");
  await assertWorkspace(customerId, siteId);
  const switched = page.waitForRequest(req => new URL(req.url()).pathname === "/api/knowledge-gaps"
    && req.headers()["x-atlas-customer-id"] === manualCustomer.id);
  await activeCustomer.selectOption(manualCustomer.id);
  assert.equal((await switched).headers()["x-atlas-site-id"], manualSite.id);
  await assertWorkspace(manualCustomer.id, manualSite.id);
  assert.deepEqual(await progress(workshopHref), initial);
  await page.goBack();
  await loaded.waitFor();

  await action(page, "Save & exit").click();
  await page.waitForURL("**/dashboard");
  await assertWorkspace(customerId, siteId);
  await link(page, "Resume").click();
  await resumeWithKeyboard(page, stage);
  await loaded.waitFor();
  const beforeFailedSave = await progress(workshopHref);
  const saveUrl = api + workshopHref + "/save";
  await page.route(saveUrl, route => route.fulfill({ status: 503, json: { detail: "Setup could not be saved" } }), { times: 1 });
  await action(page, "Save & exit").click();
  await page.getByRole("alert").filter({ hasText: "Setup could not be saved" }).waitFor();
  assert.equal(new URL(page.url()).pathname, workshopHref);
  assert.deepEqual(await progress(workshopHref), beforeFailedSave);

  await page.goto(origin + "/dashboard");
  await activeCustomer.selectOption(manualCustomer.id);
  await openWithStaleContext();
  await page.route(contextUrl, route => route.fulfill({ status: 503, json: { detail: "Workspace temporarily unavailable" } }), { times: 1 });
  await action(page, "Save & exit").click();
  await page.waitForURL("**/dashboard");
  const savedNotice = page.getByRole("status").filter({ hasText: "Setup progress was saved." });
  await savedNotice.waitFor();
  await assertWorkspace(manualCustomer.id, manualSite.id);
  const saved = await progress(workshopHref);
  assert.equal(saved.status, "saved");
  assert.equal(saved.current_stage, "review_ready");
  assert.equal(saved.version, beforeFailedSave.version + 1);
  assert.deepEqual(saved.stage_decisions, initial.stage_decisions);
  const resume = link(savedNotice, "Resume saved setup");
  assert.equal(await resume.getAttribute("href"), workshopHref);
  await resume.click();
  await resumeWithKeyboard(page, stage);
  await loaded.waitFor();
  const resumed = await progress(workshopHref);
  await request(b, "POST", workshopHref + "/save", { version: resumed.version });
  await next.click();
  const conflict = page.getByRole("alert").filter({ hasText: "Setup progress changed" });
  await conflict.waitFor();
  assert.equal(await conflict.evaluate(el => el === document.activeElement), true);
  await action(page, "Reload progress").click();
  await resumeWithKeyboard(page, stage);
  await loaded.waitFor();
  const before = await get(reviewPath(workshopHref));
  await next.click();
  await heading(page, "Showcase").waitFor();
  await page.getByText("This setup stage is pending in this preview.").waitFor();
  assert.equal(await page.getByRole("navigation", { name: "Setup stages" }).locator('[aria-current="step"] small').innerText(), "Pending");
  const after = await progress(workshopHref);
  assert.equal(after.status, "in_progress");
  assert.equal(after.completed_at, null);
  assert.deepEqual(after.stage_decisions, { ...initial.stage_decisions, review_ready: "completed" });
  assert.deepEqual(await get(reviewPath(workshopHref)), before);
  await action(page.getByRole("navigation", { name: "Setup stages" }), stage).click();
  await loaded.waitFor();
  assert.equal(await next.count(), 0);
  await action(page, "Return to current stage").click();
  await heading(page, "Showcase").waitFor();
  assert.deepEqual(await progress(workshopHref), after);
  assert.deepEqual(writes, ["save", "resume", "save", "save", "resume", "review-ready/decision", "resume", "review-ready/decision"]
    .map(endpoint => `POST /api${workshopHref}/${endpoint}`));
  return { layouts, stageDecisions: after.stage_decisions, currentStage: after.current_stage,
    staleReadDiscarded: true, confirmedKnowledgeGapContext: true, restrictedProgression: true,
    abandonedHandoffDiscarded: true, workspaceFailureSaveRecovered: true, nestedRevisits: true, writes };
}
