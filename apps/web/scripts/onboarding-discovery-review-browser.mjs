import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { randomBytes, randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const run = promisify(execFile);
const apiDirectory = fileURLToPath(new URL("../../api/", import.meta.url));
const reviewPath = "/reconciliation-entities/discovery-review";
const hostName = "Review host with a long operational name for the backup and recovery infrastructure in the workshop";
const asset = (name, host) => ({ name, external_id: name, asset_type: "virtual_machine",
  relationships: host ? [{ relationship_type: "runs_on", target_external_id: host }] : [] });

function luminance(color) {
  const channels = color.match(/\d+(?:\.\d+)?/g).slice(0, 3).map(value => Number(value) / 255);
  return channels.map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)
    .reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0);
}

export async function checkDiscoveryReview({ a, b, c, origin, api, output, workshopHref, blankHref, action, heading, resumeWithKeyboard }) {
  const { page, context } = a;
  const [customerId, siteId] = workshopHref.split("/").slice(-2);
  const headers = { "X-Atlas-Customer-ID": customerId, "X-Atlas-Site-ID": siteId };
  const shot = (name, options) => page.screenshot({ path: `${output}/e1e-${name}.png`, fullPage: true, ...options });
  const json = async (actor, method, path, expected, data, scope = headers) => {
    const response = await actor.request.fetch(api + path, { method, data, headers: scope });
    assert.equal(response.status(), expected, `${method} ${path}: ${await response.text()}`);
    return response.json();
  };
  const snapshot = async (href = workshopHref) => {
    const { stdout } = await run(process.env.ATLAS_E1D_TEST_PYTHON || ".venv/bin/python",
      ["-m", "tests.seed_onboarding_integration_browser", "review-snapshot", ...href.split("/").slice(-2)], { cwd: apiDirectory });
    return JSON.parse(stdout);
  };
  const list = () => json(context, "GET", reviewPath + "?limit=100", 200);
  const progress = href => json(context, "GET", href, 200);
  const observe = (observations, { complete = false, customer = customerId, site = siteId, source } = {}) =>
    json(b.context, "POST", "/discovery/simulate", 200, { customer_id: customer, site_id: site,
      is_complete_snapshot: complete, observations, data_source_id: source }, { "X-Atlas-Customer-ID": customer, "X-Atlas-Site-ID": site });
  const refresh = async () => {
    const response = page.waitForResponse(item => item.url().includes(reviewPath + "?") && item.ok());
    await action(page, "Refresh Discovery Review").click();
    await response;
  };
  const proposalButton = name => page.getByRole("button", { name: new RegExp(`^Review proposal for ${name} ·`) }).first();
  const completeStatus = await snapshot();
  assert.ok(completeStatus.evidence > 0);
  assert.equal(completeStatus.assets.length, 0);
  assert.equal(completeStatus.relationships, 0);
  assert.ok(Object.values(completeStatus.proposals).every(row => !row.accepted_assertion && row.status === "open"));
  const author = (await json(context, "GET", "/auth/me", 200)).id;
  const forms = await json(context, "GET", "/integration-forms", 200);
  const fixture = forms.find(form => form.connector_id === "i3-fixture");
  const activeIntegration = await json(context, "POST", "/integrations", 201, {
    creation_key: randomUUID(), name: "Discovery in progress", connector_id: fixture.connector_id,
    customer_id: customerId, site_id: siteId, config: {
      endpoint: "https://example.test", token_id: "fixture-identity", verify_tls: true, scenario: "slow",
    }, credentials: { token_secret: randomBytes(24).toString("hex") },
    selected_scopes: fixture.discovery_scopes.filter(scope => scope.default_enabled).map(scope => scope.key),
    start_initial_discovery: false, expected_connector_digest: fixture.digest,
  });
  const activeRun = await json(context, "POST", `/integrations/${activeIntegration.id}/run`, 202);
  const initialSimulated = await observe(
    [asset("Review guest", hostName), asset(hostName), asset("Retirement target")], { complete: true },
  );

  await page.goto(origin + workshopHref);
  await heading(page, "Discovery review").waitFor();
  await heading(page, "Eligible proposals").waitFor();
  const running = page.getByRole("listitem").filter({ hasText: "Discovery in progress" });
  await running.getByText(/Queued|Running/).waitFor();
  await page.getByText("Completed", { exact: true }).first().waitFor();
  await shot("initial");

  const layouts = [];
  for (const [theme, accent] of [["light", "#2563EB"], ["dark", "#7C3AED"]]) {
    assert.equal((await context.request.patch(api + "/auth/profile", { data: {
      display_name: "Onboarding Administrator", theme_mode: theme, accent_colour: accent,
    } })).status(), 200);
    await page.reload();
    await heading(page, "Eligible proposals").waitFor();
    await page.waitForFunction(expected => document.documentElement.dataset.theme === expected, theme);
    assert.equal(await page.locator(".app-shell").evaluate(el => el.style.getPropertyValue("--accent")), accent);
    for (const width of [1600, 1280, 900, 390]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 980 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      if (width === 390) await heading(page, "Eligible proposals").evaluate(element => element.scrollIntoView({ block: "center" }));
      await shot(`review-${theme}-${width}`, { fullPage: width !== 390 });
      layouts.push({ theme, accent, width });
    }
  }
  await page.setViewportSize({ width: 1280, height: 980 });
  const initial = await list();
  const blocked = initial.items.find(row => row.entity_type === "asset_relationship" && row.entity_name === "Review guest");
  assert.ok(blocked && !blocked.batch_version);
  const eligible = heading(page, "Eligible proposals").locator("xpath=ancestor::section[1]");
  const needsReview = heading(page, "Needs review").locator("xpath=ancestor::section[1]");
  await eligible.screenshot({ path: `${output}/e1e-eligible.png` });
  await needsReview.screenshot({ path: `${output}/e1e-needs-review.png` });

  const calls = [];
  page.on("request", request => {
    if (request.method() === "POST" && /\/reconciliation-(items|entities)\//.test(request.url())) calls.push(request);
  });
  await proposalButton("Fixture node").focus();
  await page.keyboard.press("Enter");
  await heading(page, "Proposal details").waitFor();
  await page.waitForFunction(() => document.activeElement?.textContent === "Proposal details");
  await shot("individual-details");
  assert.equal(calls.length, 0);
  await action(page, "Accept").click();
  await page.getByText(/Decision recorded for Fixture node/).waitFor();
  const individualId = calls[0].url().split("/").at(-2);
  const afterIndividual = await snapshot();
  assert.deepEqual(afterIndividual.assets.map(row => row.name), ["Fixture node"]);
  assert.equal(afterIndividual.proposals[individualId].actor, author);
  assert.equal(afterIndividual.proposals[individualId].assertion_actor, author);
  assert.equal(afterIndividual.audits[individualId], author);
  await needsReview.getByText(/An existing asset match requires an individual identity decision/).waitFor();

  await action(page, "Accept all eligible on this page").click();
  const dialog = page.getByRole("dialog", { name: "Confirm eligible proposals" });
  await dialog.waitFor();
  const reviewed = new Set((await list()).items.filter(row => row.batch_version).map(row => row.id));
  await dialog.screenshot({ path: `${output}/e1e-bulk-confirmation.png` });
  const arrival = await observe([asset("Late arrival")]);
  const arrived = arrival.reconciliation_items[0];
  const batchUrl = "**/api" + reviewPath + "/accept";
  const waiting = Promise.withResolvers();
  const release = Promise.withResolvers();
  await page.route(batchUrl, async route => {
    waiting.resolve(route.request().postDataJSON());
    await release.promise;
    await route.continue();
  }, { times: 1 });
  await action(dialog, "Confirm batch acceptance").focus();
  await page.keyboard.press("Enter");
  const payload = await waiting.promise;
  assert.deepEqual(new Set(payload.items.map(row => row.id)), reviewed);
  assert.ok(!payload.items.some(row => row.id === blocked.id || row.id === arrived.id));
  try {
    assert.equal(await action(page, "Accept all eligible on this page").isDisabled(), true);
  } finally {
    release.resolve();
  }
  await page.getByText("Batch result", { exact: true }).waitFor();
  await page.getByText("1 newly eligible", { exact: true }).waitFor();
  await page.waitForFunction(() => document.activeElement?.textContent?.startsWith("Batch result"));
  assert.equal(calls.filter(request => request.url().endsWith(reviewPath + "/accept")).length, 1);
  await shot("batch-and-newly-eligible");

  const afterBatch = await snapshot();
  assert.equal(afterBatch.relationships, 0);
  assert.equal(afterBatch.proposals[blocked.id].status, "open");
  assert.equal(afterBatch.proposals[arrived.id].status, "open");
  for (const id of reviewed) {
    assert.equal(afterBatch.proposals[id].status, "accepted");
    assert.equal(afterBatch.proposals[id].actor, author);
    assert.equal(afterBatch.proposals[id].accepted_assertion, true);
    assert.equal(afterBatch.audits[id], author);
  }

  await page.getByRole("searchbox", { name: "Search entities" }).fill("Review guest");
  await page.getByText("Showing 1 of 1 matching proposals.").waitFor();
  await action(page, "Accept all eligible on this page").click();
  await action(dialog, "Confirm batch acceptance").click();
  await page.getByText("1 accepted · 0 already resolved · 0 waiting or needs review · 0 failed or changed").waitFor();
  const afterRelationship = await snapshot();
  assert.equal(afterRelationship.relationships, 1);
  assert.equal(afterRelationship.proposals[blocked.id].assertion_actor, author);
  assert.ok(afterRelationship.changes.includes(blocked.id));
  assert.equal(afterRelationship.audits[blocked.id], author);
  await action(page, "Clear filters").click();

  await proposalButton("Late arrival").click();
  await page.route(`**/api/reconciliation-items/${arrived.id}/accept`, async route => {
    assert.equal((await route.fetch()).status(), 200);
    await route.abort();
  }, { times: 1 });
  await action(page, "Accept").click();
  await page.getByText(/The decision response was lost or incomplete/).waitFor();
  await page.getByText(/Current Atlas records show 1 resolved/).waitFor();
  await page.reload();
  await page.getByText(/Current Atlas records show 1 resolved/).waitFor();
  await action(page, "Check proposal status").click();
  assert.equal(calls.filter(request => request.url().includes(arrived.id)).length, 1);
  await shot("uncertain-outcome");

  await observe([asset("Review guest", hostName), asset(hostName), asset("Leave for later")], { complete: true });
  await refresh();
  await proposalButton("Retirement target").click();
  await action(page, "Retire").waitFor();
  await shot("exception-controls");
  await action(page, "Retire").click();
  const retirement = page.getByRole("dialog", { name: "Confirm asset retirement" });
  await retirement.waitFor();
  const retirementColors = await action(retirement, "Confirm retirement").evaluate(button => {
    const { color, backgroundColor } = getComputedStyle(button);
    return [color, backgroundColor];
  });
  const [darker, lighter] = retirementColors.map(luminance).sort((left, right) => left - right);
  assert.ok((lighter + 0.05) / (darker + 0.05) >= 4.5, "Dark-theme retirement control contrast");
  await retirement.screenshot({ path: `${output}/e1e-retirement-confirmation.png` });
  await action(retirement, "Cancel").click();
  assert.equal((await snapshot()).assets.find(row => row.name === "Retirement target").status, "active");

  await c.page.goto(origin + workshopHref);
  await heading(c.page, "Discovery review").waitFor();
  await c.page.getByText("You can view setup progress for this Site.").waitFor();
  assert.equal(await action(c.page, "Accept all eligible on this page").count(), 0);
  assert.equal(await action(c.page, "Skip Discovery Review").count(), 0);
  await action(page, "Save & exit").click();
  await page.waitForURL("**/dashboard");
  await page.goto(origin + workshopHref);
  await resumeWithKeyboard(page, "Discovery review");
  await action(page, "Back to Add Integrations").click();
  await heading(page, "Add integrations").waitFor();
  await action(page, "Return to current stage").click();
  await heading(page, "Discovery review").waitFor();

  const beforeAdvance = await snapshot();
  await action(page, "Continue to Link Services").click();
  const acknowledge = page.getByRole("dialog", { name: "Continue with outstanding work" });
  await acknowledge.getByText(/outstanding proposals will remain available/).waitFor();
  await acknowledge.screenshot({ path: `${output}/e1e-outstanding-acknowledgement.png` });
  await action(acknowledge, "Acknowledge and continue").click();
  await heading(page, "Link Services").waitFor();
  await page.waitForFunction(() => document.activeElement?.textContent === "Link Services");
  await shot("link-services");
  const advanced = (await progress(workshopHref)).progress;
  assert.equal(advanced.stage_decisions.discovery_review, "attention");
  assert.equal(advanced.current_stage, "link_services");
  await action(page.getByRole("navigation", { name: "Setup stages" }), "Discovery review").click();
  await heading(page, "Discovery review").waitFor();
  await proposalButton("Retirement target").waitFor();
  assert.equal(await action(page, "Skip Discovery Review").count(), 0);
  assert.deepEqual((await progress(workshopHref)).progress, advanced);
  assert.deepEqual(await snapshot(), beforeAdvance);

  const conflictName = "Batch connector identity";
  const sources = (await json(context, "GET", "/data-sources", 200))
    .filter(source => source.source_type === "connector").slice(0, 2);
  assert.equal(sources.length, 2);
  for (const source of sources) {
    await observe([{ ...asset(conflictName), external_id: `batch-identity-${source.id}` }], { source: source.id });
  }
  await page.getByRole("searchbox", { name: "Search entities" }).fill(conflictName);
  await page.getByText("Showing 2 of 2 matching proposals.").waitFor();
  assert.equal(await eligible.getByText("Create a new asset", { exact: true }).count(), 2);
  await action(page, "Accept all eligible on this page").click();
  await action(dialog, "Confirm batch acceptance").click();
  await page.getByText("1 accepted · 0 already resolved · 1 waiting or needs review · 0 failed or changed").waitFor();
  await page.getByText("Waiting or needs review", { exact: true }).click();
  const identityReason = /An existing asset match requires an individual identity decision/;
  await page.getByRole("status").filter({ hasText: "Batch result" }).getByText(identityReason).waitFor();
  await needsReview.getByText(identityReason).waitFor();
  await shot("batch-identity-needs-review");

  const associationName = "Reviewed then matched";
  await observe([{ ...asset(associationName), external_id: "before-concurrent-asset" }]);
  await page.getByRole("searchbox", { name: "Search entities" }).fill(associationName);
  await eligible.getByText("Create a new asset", { exact: true }).waitFor();
  await action(page, "Accept all eligible on this page").click();
  await dialog.waitFor();
  await json(b.context, "POST", "/assets", 201, { customer_id: customerId, site_id: siteId,
    name: associationName, asset_type: "virtual_machine" });
  await action(dialog, "Confirm batch acceptance").click();
  await page.getByText("0 accepted · 0 already resolved · 0 waiting or needs review · 1 failed or changed").waitFor();
  await page.getByText("Failed or changed", { exact: true }).click();
  await page.getByText(/Review its current asset identity before confirming again/).waitFor();
  await eligible.getByText(`Associate with existing asset ${associationName}`, { exact: true }).waitFor();
  await action(page, "Accept all eligible on this page").click();
  await dialog.getByText(`${associationName} → ${associationName}`, { exact: true }).waitFor();
  await shot("batch-identity-reconfirmation");
  await action(dialog, "Cancel").click();

  await page.goto(origin + blankHref);
  await page.getByText(/Manual setup · No integrations/).waitFor();
  await shot("manual-only-and-skip");
  const [blankCustomer, blankSite] = blankHref.split("/").slice(-2);
  await observe([asset("Pending after skip")], { customer: blankCustomer, site: blankSite });
  await refresh();
  await proposalButton("Pending after skip").waitFor();
  await action(page, "Skip Discovery Review").click();
  await heading(page, "Link Services").waitFor();
  assert.equal((await progress(blankHref)).progress.stage_decisions.discovery_review, "skipped");
  const afterSkip = await snapshot(blankHref);
  assert.equal(afterSkip.assets.length, 0);
  assert.equal(Object.values(afterSkip.proposals)[0].status, "open");

  const cancellation = await context.request.post(api + `/discovery-runs/${activeRun.id}/cancel`, { headers });
  assert.equal(cancellation.status(), 200);
  return { layouts, actor: author, activeRun: activeRun.id, observations: initialSimulated.evidence_records_created,
    reviewed: [...reviewed], individual: individualId, relationship: blocked.id, noReruns: beforeAdvance.runs,
    afterIndividual, afterBatch, afterRelationship, afterSkip, advanced, batchIdentityFeedback: true };
}
