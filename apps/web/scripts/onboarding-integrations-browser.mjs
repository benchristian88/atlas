import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { randomBytes, randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const run = promisify(execFile);
const apiDirectory = fileURLToPath(new URL("../../api/", import.meta.url));

async function waitForSettledRun(context, api, id, expected) {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    const response = await context.request.get(`${api}/discovery-runs/${id}`);
    assert.equal(response.status(), 200);
    const run = await response.json();
    if (run.dispatch_state === "settled") {
      assert.equal(run.status, expected);
      return run;
    }
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  assert.fail("Discovery did not settle in the disposable runtime");
}

export async function checkIntegrations({ a, b, c, origin, api, output, workshopHref, blankHref, action, heading, resumeWithKeyboard }) {
  const { page, context } = a;
  page.setDefaultTimeout(15000);
  await page.setViewportSize({ width: 1280, height: 1000 });
  const calls = [];
  page.on("request", request => {
    const path = new URL(request.url()).pathname;
    if (request.method() === "POST" && path.startsWith("/api/")) calls.push(path);
  });
  const card = (id) => page.locator(`[data-connector-id="${id}"]`);
  const integration = name => page.getByRole("listitem").filter({ has: heading(page, name) });
  const screenshot = (name, options = {}) => page.screenshot({ path: `${output}/e1d-${name}.png`, fullPage: true, ...options });
  const database = async (command, href) => {
    const ids = href.split("/").slice(-2);
    const { stdout } = await run(process.env.ATLAS_E1D_TEST_PYTHON || ".venv/bin/python",
      ["-m", "tests.seed_onboarding_integration_browser", command, ...ids], { cwd: apiDirectory });
    return stdout ? JSON.parse(stdout) : null;
  };
  const status = async (href = workshopHref) => {
    const response = await context.request.get(`${api}${href}`);
    assert.equal(response.status(), 200);
    return (await response.json()).progress;
  };
  const uncertain = page.getByText("Atlas has not confirmed the earlier discovery request.", { exact: false });

  await page.goto(`${origin}${workshopHref}`);
  await heading(page, "Add integrations").waitFor();
  if (await action(page, "Resume setup").count()) await resumeWithKeyboard(page, "Add integrations");
  await action(card("i3-fixture"), "Configure").waitFor();
  assert.equal(calls.filter(path => /integration-catalogue|\/run$|\/integrations$/.test(path)).length, 0);
  const configured = heading(page, "Configured integrations");
  const available = heading(page, "Available connectors");
  assert.equal(await configured.evaluate((element, later) => Boolean(element.compareDocumentPosition(later) & Node.DOCUMENT_POSITION_FOLLOWING), await available.elementHandle()), true);
  await screenshot("available-connectors");

  const refreshPath = "**/api/integration-catalogue/refresh";
  await page.route(refreshPath, route => route.fulfill({ json: { result: "failed", code: "source_unavailable" } }), { times: 1 });
  await action(page, "Refresh catalogue").click();
  await page.getByRole("alert").filter({ hasText: "The official catalogue could not be verified." }).waitFor();
  assert.equal(calls.filter(path => path.endsWith("/refresh")).length, 1);
  assert.ok(await action(card("i3-fixture"), "Configure").isEnabled());

  await action(card("proxmox"), "Install").click();
  const dialog = page.getByRole("dialog");
  await dialog.waitFor();
  await dialog.getByText("Package activation applies to the entire Atlas instance.").waitFor();
  await dialog.screenshot({ path: `${output}/e1d-installation-review.png` });
  assert.equal(calls.filter(path => path.endsWith("/install")).length, 0);
  await dialog.getByRole("checkbox", { name: "I confirm installation of this package." }).check();
  await action(dialog, "Verify and install").click();
  await dialog.waitFor({ state: "hidden" });
  await action(card("proxmox"), "Configure").waitFor();
  await page.waitForFunction(() => document.activeElement?.textContent === "Configure");
  assert.equal(calls.filter(path => path.endsWith("/install")).length, 1);
  assert.equal(calls.filter(path => path.endsWith("/activate")).length, 0);

  await database("history", workshopHref);
  await action(page, "Reload integration status").click();
  const existing = integration("Existing Proxmox history");
  await existing.getByText("Completed", { exact: true }).waitFor();
  assert.equal(await action(existing, "Run discovery").count(), 0);
  assert.equal(calls.filter(path => path.endsWith("/run")).length, 0);
  await screenshot("existing-proxmox");

  const layouts = [];
  for (const [theme, accent] of [["light", "#2563EB"], ["dark", "#7C3AED"]]) {
    const updated = await context.request.patch(`${api}/auth/profile`, { data: {
      display_name: "Onboarding Administrator", theme_mode: theme, accent_colour: accent,
    } });
    assert.equal(updated.status(), 200);
    await page.reload();
    await available.waitFor();
    await page.waitForFunction(expected => document.documentElement.dataset.theme === expected, theme);
    for (const width of [1600, 1280, 900, 390]) {
      await page.setViewportSize({ width, height: 980 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      assert.equal(await action(page, "Back to Capabilities").count(), 1);
      assert.equal(await action(page, "Open capability catalogue").count(), 0);
      if (width === 390) await configured.evaluate(element => element.scrollIntoView({ block: "center" }));
      await screenshot(`integrations-${theme}-${width}`, { fullPage: width !== 390 });
      layouts.push({ theme, accent, width });
    }
  }
  await action(page, "Back to Capabilities").focus();
  await page.keyboard.press("Enter");
  await heading(page, "Capabilities").waitFor();
  await page.waitForFunction(() => document.activeElement?.textContent === "Capabilities");
  await action(page, "Return to current stage").click();
  await heading(page, "Add integrations").waitFor();
  await page.setViewportSize({ width: 1280, height: 980 });
  const baseline = await database("snapshot", workshopHref);

  const fixtureButton = action(card("i3-fixture"), "Configure");
  await fixtureButton.focus();
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.activeElement?.textContent === "Connector and scope");
  await page.keyboard.press("Tab");
  assert.equal(await page.getByLabel("Integration name").evaluate(el => el === document.activeElement), true);
  await page.keyboard.press("Shift+Tab");
  assert.equal(await page.getByLabel("Integration name").evaluate(el => el === document.activeElement), false);
  await action(page, "Cancel configuration").click();
  await page.waitForFunction(() => document.activeElement?.hasAttribute("data-configure"));

  const openForm = async (name, scenario) => {
    await fixtureButton.click();
    await page.getByLabel("Integration name").fill(name);
    await action(page, "Continue").click();
    const form = page.getByRole("form", { name: "Configure I3 test fixture" });
    await action(form, "Continue").click();
    assert.ok(await form.getByLabel("Endpoint", { exact: true }).isVisible());
    await form.getByLabel("Endpoint", { exact: true }).fill("https://example.test");
    await form.getByLabel("Token id", { exact: true }).fill("fixture-identity");
    const secret = form.getByLabel("Token secret · Write-only", { exact: true });
    assert.equal(await secret.getAttribute("type"), "password");
    await secret.fill(randomBytes(24).toString("hex"));
    await form.getByLabel("Scenario", { exact: true }).fill(scenario);
    return { form, secret };
  };

  const { form, secret } = await openForm("Guided verified discovery", "invalid");
  await form.screenshot({ path: `${output}/e1d-shared-form.png`,
    mask: [secret, form.getByLabel("Token id", { exact: true })] });
  await action(form, "Continue").click();
  assert.equal(await action(form, "Review").isDisabled(), true);
  await action(form, "Test Connection").click();
  await page.getByRole("alert").filter({ hasText: "Connection test failed." }).waitFor();
  assert.equal(await action(form, "Review").isDisabled(), true);
  await action(form, "Back").click();
  await form.getByLabel("Scenario", { exact: true }).fill("brief");
  await action(form, "Continue").click();
  await action(form, "Test Connection").click();
  await form.getByText("Connection authenticated successfully.", { exact: true }).waitFor();
  await action(form, "Back").click();
  await form.getByLabel("Endpoint", { exact: true }).fill("https://example.test:443");
  await action(form, "Continue").click();
  assert.equal(await action(form, "Review").isDisabled(), true);
  await action(form, "Test Connection").click();
  await form.getByText("Connection authenticated successfully.", { exact: true }).waitFor();
  await action(form, "Review").click();

  const savePath = "**/api/integrations";
  await page.route(savePath, async route => {
    assert.equal(route.request().method(), "POST");
    const payload = route.request().postDataJSON();
    assert.equal(payload.site_id, workshopHref.split("/").at(-1));
    assert.equal(payload.start_initial_discovery, false);
    assert.ok(payload.expected_connector_digest);
    await route.fulfill({ status: 422, json: { detail: "Fixture rejected the save." } });
  }, { times: 1 });
  const save = action(form, "Save & discover");
  await save.click();
  await page.getByRole("alert").filter({ hasText: "Fixture rejected the save." }).waitFor();
  assert.deepEqual((await database("snapshot", workshopHref)).integrations, baseline.integrations);

  const runPath = "**/api/integrations/*/run";
  await page.route(runPath, route => route.fulfill({ status: 409, json: { detail: { code: "runtime_unavailable" } } }), { times: 1 });
  await save.focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Enter");
  const saved = integration("Guided verified discovery");
  await action(saved, "Retry discovery").waitFor();
  assert.equal(await uncertain.count(), 0);
  const stored = await database("snapshot", workshopHref);
  assert.equal(stored.integrations.length, baseline.integrations.length + 1);
  const created = stored.integrations.find(row => row.name === "Guided verified discovery");
  assert.equal(created.schedule, "manual");
  assert.equal(stored.runs.length, baseline.runs.length);
  assert.equal(calls.filter(path => path === "/api/integrations").length, 2);
  await screenshot("dispatch-failed-retry");
  await action(saved, "Retry discovery").click();
  await saved.getByText("Running", { exact: true }).waitFor({ timeout: 25000 });
  await screenshot("running-discovery");
  assert.ok(await action(page, "Continue to Discovery Review").isEnabled());
  await action(page, "Save & exit").click();
  await page.waitForURL("**/dashboard");
  await page.goto(`${origin}${workshopHref}`);
  await resumeWithKeyboard(page, "Add integrations");
  await saved.getByText("Completed", { exact: true }).waitFor({ timeout: 30000 });
  const afterResume = await database("snapshot", workshopHref);
  const [discovered] = afterResume.runs.filter(row => row.integrationId === created.id);
  assert.ok(discovered.id);
  assert.equal(discovered.status, "completed");
  assert.equal(discovered.observations, 1);
  assert.equal(afterResume.assets, baseline.assets);
  assert.equal(afterResume.acceptedSourceLinks, baseline.acceptedSourceLinks);
  assert.ok(afterResume.reconciliationItems > baseline.reconciliationItems);
  assert.equal(afterResume.reconciliationDecisions, baseline.reconciliationDecisions);
  assert.equal(afterResume.actions.filter(action => action === "integration.discovery_requested").length, 1);

  await openForm("Direct Save and discover", "brief");
  await action(form, "Continue").click();
  await action(form, "Test Connection").click();
  await form.getByText("Connection authenticated successfully.", { exact: true }).waitFor();
  await action(form, "Review").click();
  await save.click();
  await page.getByRole("status").filter({ hasText: "Integration saved. Discovery requested." }).waitFor();
  const direct = integration("Direct Save and discover");
  await direct.getByText(/Queued|Running/).waitFor();
  await action(page, "Save & exit").click();
  await page.waitForURL("**/dashboard");
  await page.goto(`${origin}${workshopHref}`);
  await resumeWithKeyboard(page, "Add integrations");
  await direct.getByText("Completed", { exact: true }).waitFor({ timeout: 30000 });
  const afterDirect = await database("snapshot", workshopHref);
  const directIntegration = afterDirect.integrations.find(row => row.name === "Direct Save and discover");
  const directRuns = afterDirect.runs.filter(row => row.integrationId === directIntegration.id);
  assert.equal(directIntegration.schedule, "manual");
  assert.equal(directRuns.length, 1);
  assert.equal(directRuns[0].status, "completed");
  assert.equal(directRuns[0].observations, 1);
  assert.equal(afterDirect.assets, baseline.assets);
  assert.equal(afterDirect.acceptedSourceLinks, baseline.acceptedSourceLinks);
  assert.equal(afterDirect.reconciliationDecisions, baseline.reconciliationDecisions);

  await openForm("Lost save response", "failed");
  await action(form, "Continue").click();
  await action(form, "Test Connection").click();
  await form.getByText("Connection authenticated successfully.", { exact: true }).waitFor();
  await action(form, "Review").click();
  await page.route(savePath, async route => {
    assert.equal((await route.fetch()).status(), 201);
    await route.abort();
  }, { times: 1 });
  await save.click();
  await page.getByRole("status").filter({ hasText: "Atlas found the saved integration." }).waitFor();
  const recovered = integration("Lost save response");
  await action(recovered, "Run discovery").waitFor();
  const afterLostSave = await database("snapshot", workshopHref);
  const recoveredIntegration = afterLostSave.integrations.find(row => row.name === "Lost save response");
  assert.equal(afterLostSave.runs.filter(row => row.integrationId === recoveredIntegration.id).length, 0);
  await page.route(runPath, async route => {
    const response = await route.fetch();
    assert.equal(response.status(), 202);
    await waitForSettledRun(context, api, (await response.json()).id, "failed");
    await route.abort();
  }, { times: 1 });
  await action(recovered, "Run discovery").click();
  await uncertain.waitFor({ timeout: 35000 });
  await recovered.getByText("Failed", { exact: true }).waitFor({ timeout: 30000 });
  assert.equal(await action(recovered, "Retry discovery").isDisabled(), true);
  await screenshot("discovery-response-unknown");
  const afterLostRun = await database("snapshot", workshopHref);
  assert.equal(afterLostRun.runs.filter(row => row.integrationId === recoveredIntegration.id).length, 1);
  assert.equal(afterLostRun.integrations.length, baseline.integrations.length + 3);

  await action(page, "Use available run and continue").click();
  await heading(page, "Discovery review").waitFor();
  assert.equal(await heading(page, "Discovery review").evaluate(el => el === document.activeElement), true);
  await heading(page, "Discovery status").waitFor();
  await screenshot("discovery-review-entry");
  const completed = await status();
  assert.equal(completed.stage_decisions.integrations, "completed");
  await action(page.getByRole("navigation", { name: "Setup stages" }), "Add integrations").click();
  await heading(page, "Add integrations").waitFor();
  assert.equal(await uncertain.count(), 0);
  assert.equal(await action(page, "Continue without integrations").count(), 0);
  await action(page, "Return to current stage").click();
  await heading(page, "Discovery review").waitFor();
  assert.deepEqual(await status(), completed);

  await c.page.goto(`${origin}${blankHref}`);
  await heading(c.page, "Add integrations").waitFor();
  assert.equal(await action(c.page, "Refresh catalogue").count(), 0);
  assert.equal(await action(c.page, "Configure").count(), 0);
  assert.equal(await action(c.page, "Continue without integrations").count(), 0);
  await b.page.goto(`${origin}${blankHref}`);
  await heading(b.page, "Add integrations").waitFor();
  const blankBefore = await database("snapshot", blankHref);
  await b.page.screenshot({ path: `${output}/e1d-manual-only.png`, fullPage: true });
  await action(b.page, "Continue without integrations").click();
  await heading(b.page, "Discovery review").waitFor();
  const blankAfter = await database("snapshot", blankHref);
  assert.deepEqual(blankAfter.integrations, blankBefore.integrations);
  assert.deepEqual(blankAfter.runs, blankBefore.runs);
  assert.equal((await status(blankHref)).stage_decisions.integrations, "skipped");

  const edgeCases = await checkContinuationAndRecovery({
    page, context, other: b.context, origin, api, action, heading, integration, database, status,
    resumeWithKeyboard, customerId: workshopHref.split("/").at(-2), calls, uncertain,
  });

  return { layouts, integration: directIntegration.id, discovery: directRuns[0].id, observations: directRuns[0].observations,
    retryIntegration: created.id, retryDiscovery: discovered.id, recoveredIntegration: recoveredIntegration.id,
    afterResume, afterDirect, afterLostRun, blankBefore, blankAfter, edgeCases };
}

async function checkContinuationAndRecovery({
  page, context, other, origin, api, action, heading, integration, database, status,
  resumeWithKeyboard, customerId, calls, uncertain,
}) {
  const request = async (actor, method, path, expected, data, headers) => {
    const response = await actor.request.fetch(`${api}${path}`, { method, data, headers });
    assert.equal(response.status(), expected, `${method} ${path}`);
    return response.json();
  };
  async function newSite(name) {
    const site = await request(context, "POST", "/sites", 201, { name, customer_id: customerId });
    const href = `/onboarding/${customerId}/${site.id}`;
    const started = await request(context, "POST", href + "/start", 200);
    const confirmed = await request(context, "PATCH", href + "/environment", 200, {
      version: started.version, environment_profile: "blank",
    });
    await request(context, "POST", href + "/capabilities/skip", 200, { version: confirmed.version });
    return { id: site.id, href, headers: { "X-Atlas-Customer-ID": customerId, "X-Atlas-Site-ID": site.id } };
  }
  const forms = await request(context, "GET", "/integration-forms", 200);
  const connector = forms.find(form => form.connector_id === "i3-fixture");
  const add = (actor, site, name, scenario = "complete") => request(actor, "POST", "/integrations", 201, {
    creation_key: randomUUID(), name, connector_id: connector.connector_id, customer_id: customerId, site_id: site.id,
    config: { endpoint: "https://example.test", token_id: "fixture-identity", verify_tls: true, scenario },
    credentials: { token_secret: randomBytes(24).toString("hex") },
    selected_scopes: connector.discovery_scopes.filter(scope => scope.default_enabled).map(scope => scope.key),
    start_initial_discovery: false, expected_connector_digest: connector.digest,
  }, site.headers);
  const start = (actor, site, id, expected = 202) =>
    request(actor, "POST", `/integrations/${id}/run`, expected, undefined, site.headers);
  const retire = (connection, site) =>
    request(other, "DELETE", `/integrations/${connection.id}`, 200, { confirmed: true }, site.headers);
  const continueWith = async (button, expected, runId) => {
    const response = page.waitForResponse(item => item.url().endsWith("/integrations/decision"));
    await action(page, button).click();
    const result = await response;
    assert.equal(result.status(), expected);
    assert.equal(result.request().postDataJSON().discovery_run_id, runId);
  };
  const checkStatus = async () => {
    const response = page.waitForResponse(item => item.url().endsWith("/integrations?include_discovery=true") && item.ok());
    await action(page, "Check operation status").click();
    await response;
    await uncertain.waitFor();
    await action(page, "Check operation status").and(page.locator(":enabled")).waitFor();
  };

  const eligibility = await newSite("Discovery eligibility");
  const retired = await add(context, eligibility, "A retired");
  const retiredRun = await start(context, eligibility, retired.id);
  await waitForSettledRun(context, api, retiredRun.id, "completed");
  await retire(retired, eligibility);
  await page.goto(origin + eligibility.href);
  await integration("A retired").getByText("Retired", { exact: true }).waitFor();
  await page.getByText("Start discovery from a configured integration or continue without integrations.").waitFor();
  assert.equal(await action(page, "Continue to Discovery Review").count(), 0);
  assert.ok(await action(page, "Continue without integrations").isEnabled());

  const live = await add(context, eligibility, "B live");
  const liveRun = await start(context, eligibility, live.id);
  await waitForSettledRun(context, api, liveRun.id, "completed");
  const fallback = await add(context, eligibility, "C live");
  const fallbackRun = await start(context, eligibility, fallback.id);
  await waitForSettledRun(context, api, fallbackRun.id, "completed");
  await action(page, "Reload integration status").click();
  await integration("B live").getByText("Completed", { exact: true }).waitFor();
  const beforeDecision = await status(eligibility.href);
  await retire(live, eligibility);
  const beforeContinue = await database("snapshot", eligibility.href);
  await continueWith("Continue to Discovery Review", 422, liveRun.id);
  await page.getByRole("alert").filter({ hasText: "The discovery run is no longer eligible." }).waitFor();
  await integration("B live").getByText("Retired", { exact: true }).waitFor();
  assert.deepEqual(await status(eligibility.href), beforeDecision);
  await continueWith("Continue to Discovery Review", 200, fallbackRun.id);
  await heading(page, "Discovery review").waitFor();
  const afterContinue = await database("snapshot", eligibility.href);
  assert.deepEqual(afterContinue.integrations, beforeContinue.integrations);
  assert.deepEqual(afterContinue.runs, beforeContinue.runs);

  const recovery = await newSite("Discovery recovery");
  const sibling = await newSite("Other Site discovery");
  const target = await add(context, recovery, "A uncertain request", "brief");
  await page.goto(origin + recovery.href);
  const launchesBefore = calls.filter(path => path.endsWith("/run")).length;
  const savesBefore = calls.filter(path => path === "/api/integrations").length;
  await page.route(`**/api/integrations/${target.id}/run`, route => route.abort(), { times: 1 });
  await action(integration("A uncertain request"), "Run discovery").click();
  await uncertain.waitFor();
  await page.reload();
  await uncertain.waitFor();
  await action(page, "Save & exit").click();
  await page.waitForURL("**/dashboard");
  await page.goto(origin + recovery.href);
  await resumeWithKeyboard(page, "Add integrations");
  await uncertain.waitFor();
  const beforeOther = await database("snapshot", recovery.href);
  assert.deepEqual(beforeOther.integrations.map(row => row.id), [target.id]);
  assert.equal(beforeOther.runs.length, 0);
  assert.ok(await action(page, "Continue without integrations").isEnabled());

  const foreign = await add(other, sibling, "Other Site integration");
  const foreignRun = await start(other, sibling, foreign.id);
  await waitForSettledRun(other, api, foreignRun.id, "completed");
  await checkStatus();
  assert.equal(await action(page, "Use available run and continue").count(), 0);
  assert.equal(await heading(page, "Other Site integration").count(), 0);

  const independent = await add(other, recovery, "B other integration");
  const independentRun = await start(other, recovery, independent.id);
  await waitForSettledRun(other, api, independentRun.id, "completed");
  await checkStatus();
  await page.getByText("A discovery run is available for B other integration.", { exact: false }).waitFor();

  const otherRun = await start(other, recovery, target.id);
  const active = await start(other, recovery, target.id, 409);
  assert.equal(active.detail.code, "run_already_active");
  assert.equal(active.detail.run_id, otherRun.id);
  await checkStatus();
  await integration("A uncertain request").getByText(/Queued|Running/).waitFor();
  const completed = await waitForSettledRun(other, api, otherRun.id, "completed");
  assert.equal(completed.created_by_user_id, (await request(other, "GET", "/auth/me", 200)).id);
  await checkStatus();
  await page.getByText("A discovery run is available for A uncertain request.", { exact: false }).waitFor();
  await continueWith("Use available run and continue", 200, otherRun.id);
  await heading(page, "Discovery review").waitFor();
  assert.equal(calls.filter(path => path.endsWith("/run")).length, launchesBefore + 1);
  assert.equal(calls.filter(path => path === "/api/integrations").length, savesBefore);
  const afterRecovery = await database("snapshot", recovery.href);
  assert.deepEqual(afterRecovery.runs.map(run => run.id).sort(), [independentRun.id, otherRun.id].sort());
  assert.deepEqual(afterRecovery.integrations.map(row => row.id).sort(), [target.id, independent.id].sort());
  assert.equal(afterRecovery.assets, 0);
  assert.equal(afterRecovery.acceptedSourceLinks, 0);
  assert.equal(afterRecovery.reconciliationDecisions, 0);
  return {
    retiredRun: retiredRun.id, staleCandidate: liveRun.id, selectedAfterRefresh: fallbackRun.id,
    interruptedRunsBeforeOtherAdministrator: beforeOther.runs.length, independentlyStartedRun: otherRun.id,
    otherIntegrationRun: independentRun.id, otherSiteRun: foreignRun.id, afterRecovery,
  };
}
