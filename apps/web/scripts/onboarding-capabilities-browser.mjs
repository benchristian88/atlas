import assert from "node:assert/strict";
import { accentThemeStyle } from "../lib/accent-theme.mjs";

export async function checkCapabilities({
  a, b, c, origin, api, output, workshopHref, selectedCustomer, workshopSite, blankHref,
  login, openPage, credentials, action, link, heading, resumeWithKeyboard,
}) {
  const { page, context } = a;
  const pair = `${api}${workshopHref}`;
  const url = `${pair}/capabilities`;
  const cards = page.locator('[data-definition-id^="bf."]');
  const capture = (name, options = {}) => page.screenshot({ path: `${output}/${name}.png`, ...options });
  const summaries = [];
  const layouts = [];
  const requests = [];
  const canonical = (name, customer = selectedCustomer, site = workshopSite) => context.request.get(`${api}/${name}`, {
    headers: { "X-Atlas-Customer-ID": customer, "X-Atlas-Site-ID": site },
  }).then((response) => json(response));

  async function json(response, status = 200) {
    assert.equal(response.status(), status, await response.text());
    return response.json();
  }

  async function counts(functions, services, associations) {
    const region = page.getByRole("region", { name: "Selection summary" });
    await region.locator("dd").first().waitFor();
    assert.deepEqual(await region.locator("dd").allTextContents(), [functions, services, associations].map(String));
    summaries.push({ functions, services, associations });
  }

  async function edit(id, values, restore = false) {
    const row = page.locator(`[data-definition-id="${id}"]`);
    const button = row.locator("button[aria-label^='Edit ']").first();
    await button.click();
    const form = row.getByRole("form");
    const name = form.getByLabel("Name", { exact: true });
    await name.waitFor();
    assert.equal(await name.evaluate((element) => element === document.activeElement), true);
    for (const [label, value] of Object.entries(values)) {
      const field = form.getByLabel(label, { exact: true });
      if (["Service Type", "Criticality"].includes(label)) await field.selectOption(value);
      else await field.fill(value);
    }
    if (restore) await action(form, "Restore catalogue defaults").click();
    else await action(form, "Save edit").click();
    await form.waitFor({ state: "detached" });
    await button.evaluate((node) => node.focus());
    return row;
  }

  async function review() {
    await action(page, "Review selection").click();
    const title = heading(page, "Review capabilities");
    await title.waitFor();
    assert.equal(await title.evaluate((element) => element === document.activeElement), true);
    await page.getByText("Atlas validated this selection.", { exact: true }).waitFor();
  }

  async function confirmDialog(button, accept = true) {
    page.once("dialog", (dialog) => accept ? dialog.accept() : dialog.dismiss());
    await button.click();
  }

  // Assert real requests and preserve their exact payloads for the evidence report.
  page.on("request", (request) => {
    if (request.url().startsWith(`${url}/`) && ["POST", "PUT"].includes(request.method())) {
      const endpoint = request.url().slice(url.length + 1);
      const payload = request.postDataJSON();
      requests.push({ endpoint, payload });
      assert.equal(request.headers()["x-atlas-site-id"], undefined);
    }
  });
  await page.goto(`${origin}${workshopHref}`);
  await page.getByRole("radio", { name: /Homelab/ }).check();
  await action(page, "Confirm Environment").click();
  await heading(page, "What does your Homelab support?").waitFor();
  const initial = await json(await context.request.get(url));
  assert.equal(initial.catalogue.content_version, "1.0.0");
  assert.equal(initial.catalogue.schema_version, 1);
  assert.equal(await cards.count(), 8);
  await counts(8, 24, 24);

  const [group, ...others] = initial.catalogue.functions;
  const standard = group.services.find((service) => service.selection_tier === "standard");
  const extended = group.services.find((service) => service.selection_tier === "extended");
  const groupCard = cards.first();
  const groupCheck = groupCard.getByRole("checkbox", { name: `Select ${group.name}`, exact: true });
  const selectStandard = groupCard.getByRole("checkbox", { name: `Select ${standard.name}`, exact: true });
  const selectExtended = groupCard.getByRole("checkbox", { name: `Select ${extended.name}`, exact: true });
  const expand = groupCard.getByRole("button", { name: `Show Services for ${group.name}`, exact: true });
  await page.setViewportSize({ width: 1600, height: 1050 });
  await capture("capabilities-desktop", { fullPage: true });
  await groupCheck.focus();
  await page.keyboard.press("Tab");
  assert.equal(await expand.evaluate((node) => node === document.activeElement), true);
  await page.keyboard.press("Shift+Tab");
  assert.equal(await groupCheck.evaluate((node) => node === document.activeElement), true);
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  assert.equal(await groupCheck.isChecked(), true);
  const collapse = groupCard.getByRole("button", { name: `Hide Services for ${group.name}`, exact: true });
  assert.equal(await collapse.getAttribute("aria-expanded"), "true");
  assert.equal(await collapse.evaluate((button) => Boolean(document.getElementById(button.getAttribute("aria-controls")))), true);
  await heading(groupCard, "Standard capabilities Recommended").waitFor();
  await heading(groupCard, "Extended capabilities Optional").waitFor();
  assert.equal(await selectStandard.isChecked(), true);
  assert.equal(await selectExtended.isChecked(), false);
  await capture("capabilities-expanded", { fullPage: true });
  await collapse.click();
  await expand.click();

  await groupCheck.focus();
  await page.keyboard.press("Space");
  assert.equal(await groupCheck.evaluate((node) => node.matches(":focus-visible")), true);
  assert.equal(await selectStandard.isChecked(), false);
  await groupCheck.check();
  assert.equal(await selectStandard.isChecked(), true);
  await groupCheck.uncheck();
  await selectExtended.check();
  assert.equal(await groupCheck.isChecked(), true);
  assert.equal(await selectStandard.isChecked(), false);
  const groupDefaultCount = group.services.filter((service) => service.preselected).length;
  await counts(8, 24 - groupDefaultCount + 1, 24 - groupDefaultCount + 1);
  await action(groupCard, "Select all Services").click();
  await counts(8, 24 - groupDefaultCount + group.services.length, 24 - groupDefaultCount + group.services.length);
  await action(page, "Restore recommended selection").click();
  await counts(8, 24, 24);

  const seed = await json(await context.request.post(`${api}/business-functions`, {
    data: { customer_id: selectedCustomer, name: group.name, description: "Existing canonical record" },
  }), 201);
  const types = await json(await context.request.get(`${api}/service-types?active_only=true`));
  const levels = await json(await context.request.get(`${api}/criticality-levels?active_only=true`));
  const serviceType = types.find(({ key }) => key !== initial.default_service_type_keys[standard.service_type_name]);
  const criticality = levels.find(({ key }) => key !== initial.default_criticality_key);
  const serviceName = "Lab Internet — Tāmaki";
  const functionName = "Ngā hononga — 家庭";
  const functionDescription = "Connectivity owned by the household.\nConfirm coverage for each occupied room.";
  const serviceRow = page.locator(`[data-definition-id="${standard.id}"]`);
  await action(serviceRow, `Edit ${standard.name}`).click();
  const editor = serviceRow.getByRole("form");
  assert.equal(await editor.getByLabel("Name", { exact: true }).evaluate((node) => node === document.activeElement), true);
  assert.equal(await editor.getByLabel("Service Type", { exact: true }).inputValue(), initial.default_service_type_keys[standard.service_type_name]);
  await capture("capabilities-inline-editor", { fullPage: true });
  await action(editor, "Cancel edit").click();
  await page.waitForFunction((label) => document.activeElement?.getAttribute("aria-label") === label, `Edit ${standard.name}`);
  await edit(standard.id, { Name: serviceName });
  await confirmDialog(action(page, "Restore recommended selection"), false);
  assert.equal(await serviceRow.getByRole("checkbox", { name: `Select ${serviceName}` }).isChecked(), true);
  await edit(standard.id, {}, true);
  await serviceRow.getByRole("checkbox", { name: `Select ${standard.name}`, exact: true }).waitFor();
  await edit(standard.id, { Name: serviceName, "Service Type": serviceType.key, Criticality: criticality.key });

  // Switching views leaves the selection and editor data in the active session.
  await action(page, "Back to Environment").click();
  await heading(page, "Environment").waitFor();
  assert.equal(await page.getByRole("combobox").count(), 0);
  await action(page, "Return to current stage").click();
  await page.getByRole("checkbox", { name: `Select ${serviceName}`, exact: true }).waitFor();

  for (const definition of others) {
    await page.getByRole("checkbox", { name: `Select ${definition.name}`, exact: true }).uncheck();
  }
  for (const definition of group.services.filter((service) => service.preselected && service.id !== standard.id)) {
    await page.getByRole("checkbox", { name: `Select ${definition.name}`, exact: true }).uncheck();
  }
  await counts(1, 1, 1);
  const warning = groupCard.getByText(`A Business Function named “${group.name}” already exists.`, { exact: false });
  await warning.waitFor();
  await capture("capabilities-existing-name", { fullPage: true });

  const olderPreview = Promise.withResolvers();
  const releasePreview = Promise.withResolvers();
  const oldPreviewFinished = Promise.withResolvers();
  await page.route(`${url}/preview`, async (route) => {
    const response = await route.fetch();
    olderPreview.resolve(await json(response));
    await releasePreview.promise;
    await route.fulfill({ response }).catch(() => {});
    oldPreviewFinished.resolve();
  }, { times: 1 });
  await edit(standard.id, { Description: "A pending preview" });
  assert.ok((await olderPreview.promise).warnings.some(({ definition_id }) => definition_id === group.id));
  await edit(group.id, { Name: "Temporary unique Function" });
  await review();
  releasePreview.resolve();
  await oldPreviewFinished.promise;
  assert.equal(await page.getByText(/already exists/).count(), 0);
  await action(page, "Back to selection").click();
  await edit(group.id, {}, true);

  // Responsive/theme checks use the expanded catalogue, including long edited text and form controls.
  const longDescription = "Extended description for validating responsive wrapping. ".repeat(18);
  const longName = "LongCapabilityName".repeat(10);
  await edit(standard.id, { Name: longName, Description: longDescription });
  for (const [theme, accent] of [["light", "#2563EB"], ["dark", "#7C3AED"]]) {
    for (const width of [1600, 1280, 900, 390]) {
      await page.setViewportSize({ width, height: 950 });
      await page.emulateMedia({ colorScheme: theme });
      // Use the same scoped theme/accent properties as Atlas's authenticated shell.
      await page.locator("html").evaluate((element, mode) => { element.dataset.theme = mode; }, theme);
      await page.locator(".app-shell").evaluate((element, tokens) => {
        for (const [name, value] of Object.entries(tokens)) element.style.setProperty(name, value);
      }, accentThemeStyle(accent, theme));
      await action(serviceRow, `Edit ${longName}`).click();
      const bounds = await page.evaluate(() => ({
        page: document.documentElement.scrollWidth <= innerWidth,
        controls: [...document.querySelectorAll('input:not([type="hidden"]), textarea, select, button')]
          .filter((element) => element.getClientRects().length)
          .every((element) => {
            const box = element.getBoundingClientRect();
            return box.width > 0 && box.left >= 0 && box.right <= innerWidth;
          }),
      }));
      assert.deepEqual(bounds, { page: true, controls: true }, `${theme} ${accent} ${width}px`);
      if (width === 390 && theme === "dark") await capture("capabilities-mobile", { fullPage: true });
      await action(serviceRow, "Cancel edit").click();
      layouts.push({ theme, accent, width, ...bounds });
    }
  }
  await page.setViewportSize({ width: 1600, height: 1050 });
  await edit(standard.id, { Name: serviceName });
  await review();
  assert.equal(await page.getByText(serviceName, { exact: true }).count(), 1);
  assert.equal(await page.getByText(serviceType.name, { exact: true }).count(), 1);
  assert.equal(await page.getByText(criticality.name, { exact: true }).count(), 1);
  await capture("capabilities-review", { fullPage: true });
  await action(page, "Back to selection").click();
  await counts(1, 1, 1);
  await action(page, "Save & exit").click();
  await page.waitForURL("**/dashboard");
  const saved = await json(await context.request.get(url));
  assert.equal(saved.draft.services[0].name, serviceName);
  assert.equal(saved.draft.services[0].description, longDescription);
  assert.equal(saved.draft.services[0].service_type_key, serviceType.key);
  assert.equal(saved.draft.services[0].criticality_key, criticality.key);
  assert.deepEqual(saved.draft.functions, [{ id: group.id }]);
  assert.deepEqual(saved.draft.associations, initial.catalogue.associations
    .filter((link) => link.service_id === standard.id).map(({ id }) => id));
  assert.equal(requests.find(({ endpoint }) => endpoint === "draft").payload.save_and_exit, true);
  assert.equal((await canonical("services")).length, 0);
  assert.equal((await canonical("business-functions")).length, 1);
  const dashboardEntry = page.getByRole("region", { name: "Guided setup", exact: true });
  await heading(dashboardEntry, "Continue your Homelab setup").waitFor();
  assert.equal(await dashboardEntry.getByText("Step 2 of 7 · Capabilities", { exact: true }).count(), 1);
  assert.equal(await dashboardEntry.evaluate((el) => el.previousElementSibling?.querySelector("h1")?.textContent), "Dashboard");
  await capture("dashboard-resume", { fullPage: true });
  await link(dashboardEntry, "Resume").click();
  await resumeWithKeyboard(page, "Capabilities");
  await page.getByText("Saved selection restored.", { exact: true }).waitFor();
  await page.reload();
  await counts(1, 1, 1);
  await page.getByText("Saved selection restored.", { exact: true }).waitFor();
  await expand.click();
  assert.equal(await page.getByText(longDescription, { exact: true }).count(), 1);

  // Two real administrators share one workflow version. An explicit reload adopts
  // the other user's draft only after confirmation; the attempted Apply writes no entities.
  await edit(group.id, { Description: "Unsaved primary administrator edit" });
  await review();
  await b.page.goto(`${origin}${workshopHref}`);
  await heading(b.page, "What does your Homelab support?").waitFor();
  const versionBefore = (await json(await b.context.request.get(url))).version;
  const otherDraft = structuredClone(saved.draft);
  otherDraft.functions[0].description = "Saved by the second administrator";
  await json(await b.context.request.put(`${url}/draft`, { data: { version: versionBefore, selection: otherDraft } }));
  const priorApplies = requests.filter(({ endpoint }) => endpoint === "apply").length;
  await action(page, "Apply capabilities").click();
  const conflict = page.getByRole("alert").filter({ hasText: "Shared setup progress" });
  await conflict.waitFor();
  assert.equal(await conflict.evaluate((element) => element === document.activeElement), true);
  assert.equal(requests.filter(({ endpoint }) => endpoint === "apply").length, priorApplies);
  await capture("capabilities-save-conflict", { fullPage: true });
  await confirmDialog(action(page, "Reload saved progress"), false);
  await heading(page, "Review capabilities").waitFor();
  await confirmDialog(action(page, "Reload saved progress"));
  await page.getByText("Saved by the second administrator", { exact: true }).waitFor();

  // A warning allows deliberate Apply, while the real uniqueness constraint rejects it.
  await review();
  const rejected = page.waitForResponse((response) => response.url() === `${url}/apply` && response.status() === 409);
  await action(page, "Apply capabilities").click();
  await rejected;
  await page.getByRole("alert").filter({ hasText: "identifier is unavailable" }).waitFor();
  await capture("capabilities-canonical-conflict", { fullPage: true });
  assert.equal((await canonical("services")).length, 0);
  assert.equal((await json(await context.request.get(url))).draft.services[0].name, serviceName);
  await action(page, "Back to selection").click();
  await edit(group.id, { Name: functionName, Description: functionDescription });
  await review();
  assert.equal(await page.getByText(functionName, { exact: true }).count(), 1);
  for (const width of [390, 1600]) {
    await page.setViewportSize({ width, height: 950 });
    for (const [name, description] of [[functionName, functionDescription], [serviceName, longDescription]]) {
      const disclosure = page.getByText(`Customised description for ${name}`, { exact: true });
      await disclosure.focus();
      await page.keyboard.press("Enter");
      const details = disclosure.locator("..");
      assert.equal(await details.getAttribute("open"), "");
      assert.equal(await details.locator("p").textContent(), description);
      assert.equal(await details.locator("p").isVisible(), true);
    }
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await capture(`capabilities-review-descriptions-${width}`, { fullPage: true });
    for (const name of [functionName, serviceName]) {
      await page.getByText(`Customised description for ${name}`, { exact: true }).click();
    }
  }

  // Forward Apply to the actual API, wait for commit, then drop the response.
  // A page reload must offer replay with identical UUID and version.
  let original;
  let committed;
  await page.route(`${url}/apply`, async (route) => {
    original = route.request().postDataJSON();
    const response = await route.fetch({ maxRetries: 0 });
    committed = await json(response);
    await route.abort("connectionreset");
  }, { times: 1 });
  const confirm = action(page, "Apply capabilities");
  await confirm.focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Enter");
  await page.getByRole("alert").filter({ hasText: "could not confirm whether Apply finished" }).waitFor();
  assert.deepEqual(committed.created, { functions: 1, services: 1, associations: 1 });
  assert.equal(requests.filter(({ endpoint, payload }) => endpoint === "apply" && payload.submission_id === original.submission_id).length, 1);
  assert.equal((await json(await context.request.get(pair))).progress.current_stage, "integrations");
  await page.reload();
  const repeat = page.waitForRequest((request) => request.url() === `${url}/apply`);
  await action(page, "Retry this Apply").click();
  assert.deepEqual((await repeat).postDataJSON(), original);
  await heading(page, "Add integrations").waitFor();
  assert.equal(await heading(page, "Add integrations").evaluate((element) => element === document.activeElement), true);
  await page.getByRole("status").filter({ hasText: "Created 1 Business Function, 1 Service and 1 Supports association" }).waitFor();

  const [service] = await canonical("services");
  const functions = await canonical("business-functions");
  assert.equal((await canonical("services")).length, 1);
  assert.equal(functions.length, 2);
  const created = functions.find(({ name }) => name === functionName);
  assert.ok(created);
  assert.equal(created.description, functionDescription);
  assert.equal(service.description, longDescription);
  assert.deepEqual({ name: service.name, customer: service.customer_id, site: service.site_id, type: service.service_type_id,
    criticality: service.criticality_level_id }, {
    name: serviceName, customer: selectedCustomer, site: null, type: serviceType.id, criticality: criticality.id,
  });
  assert.equal(created.site_id, null);
  assert.equal(created.customer_id, selectedCustomer);
  const links = await json(await context.request.get(`${api}/services/${service.id}/business-functions`));
  assert.equal(links.length, 1);
  assert.equal(links[0].business_function_id, created.id);
  assert.equal(links[0].relationship_label, "Supports");
  assert.equal(links[0].site_id, null);
  const firstProgress = (await json(await context.request.get(pair))).progress;

  await action(page, "Open capability catalogue").click();
  await counts(0, 0, 0);
  assert.equal(await action(page, "Skip capabilities").count(), 0);
  await groupCheck.check();
  await counts(1, 0, 0);
  await edit(group.id, { Name: "Additional Household Connectivity" });
  await review();
  await action(page, "Apply capabilities").click();
  await page.getByRole("status").filter({ hasText: "Created 1 Business Function, 0 Services and 0 Supports associations" }).waitFor();
  const afterAdditional = (await json(await context.request.get(pair))).progress;
  assert.equal(afterAdditional.current_stage, firstProgress.current_stage);
  assert.deepEqual(afterAdditional.stage_decisions, firstProgress.stage_decisions);
  assert.equal((await canonical("business-functions")).length, 3);
  assert.equal((await canonical("business-functions")).find(({ id }) => id === seed.id).description, "Existing canonical record");
  assert.equal((await canonical("services")).length, 1);

  // A new Site in the same Customer can read the imported Customer-wide records
  // and allows exercising real partial grants, revocation and draft authorization.
  const restrictedSite = await json(await context.request.post(`${api}/sites`, {
    data: { customer_id: selectedCustomer, name: "Restricted workshop" },
  }), 201);
  const restrictedHref = `/onboarding/${selectedCustomer}/${restrictedSite.id}`;
  const restricted = `${api}${restrictedHref}/capabilities`;
  assert.deepEqual((await canonical("services", selectedCustomer, restrictedSite.id)).map(({ id }) => id), [service.id]);
  const start = await json(await context.request.post(`${api}${restrictedHref}/start`));
  await json(await context.request.patch(`${api}${restrictedHref}/environment`, {
    data: { version: start.version, environment_profile: "homelab" },
  }));
  // The API regression suite covers a stale PostgreSQL draft. Present that
  // response shape here and verify the explicit replacement flag on a real PUT.
  const restrictedDefaults = await json(await context.request.get(restricted));
  await json(await context.request.put(`${restricted}/draft`, {
    data: { version: restrictedDefaults.version, selection: restrictedDefaults.defaults },
  }));
  await page.route(restricted, async (route) => {
    const response = await route.fetch();
    const body = await json(response);
    body.draft_stale = true;
    body.draft.content_version = "0.9.0";
    await route.fulfill({ response, json: body });
  }, { times: 1 });
  await page.goto(`${origin}${restrictedHref}`);
  await page.getByText(/The saved draft uses an earlier catalogue version/).waitFor();
  assert.equal(await action(page, "Save & exit").isDisabled(), true);
  await action(page, "Review current catalogue").click();
  const replace = page.waitForRequest((request) => request.url() === `${restricted}/draft` && request.method() === "PUT");
  await action(page, "Save & exit").click();
  assert.equal((await replace).postDataJSON().replace_stale_draft, true);
  await page.waitForURL("**/dashboard");
  const savedReplacement = await json(await context.request.get(restricted));
  assert.equal(savedReplacement.draft.content_version, initial.catalogue.content_version);
  const resumedReplacement = await json(await context.request.post(`${api}${restrictedHref}/resume`, {
    data: { version: savedReplacement.version },
  }));
  const classifiedDraft = structuredClone(savedReplacement.draft);
  classifiedDraft.services.find(({ id }) => id === standard.id).service_type_key = serviceType.key;
  await json(await context.request.put(`${restricted}/draft`, {
    data: { version: resumedReplacement.version, selection: classifiedDraft },
  }));
  const permissionKeys = ["customers.view", "sites.view", "sites.manage", "business_functions.manage", "services.create", "services.view"];
  const role = await json(await context.request.post(`${api}/roles`, {
    data: { name: "Capability test role", permission_keys: permissionKeys },
  }), 201);
  const limited = credentials("capabilities-limited@example.com", "Limited operator");
  await json(await context.request.post(`${api}/users`, { data: {
    email: limited.email, display_name: limited.name, temporary_password: limited.password, force_password_change: false,
    assignments: [{ role_id: role.id, scope_type: "customer", customer_id: selectedCustomer }],
  } }), 201);
  const d = await openPage();
  const requestsForReference = [];
  d.page.on("request", (request) => {
    if (/\/(service-types|criticality-levels)\?active_only=true$/.test(request.url())) requestsForReference.push(request.url());
  });
  await login(d.page, limited);
  await d.page.goto(`${origin}${restrictedHref}`);
  await heading(d.page, "What does your Homelab support?").waitFor();
  const limitedApi = await json(await d.context.request.get(restricted));
  assert.equal(limitedApi.permissions.can_create_associations, false);
  assert.equal(limitedApi.permissions.can_create_functions, true);
  assert.equal(limitedApi.permissions.can_view_service_types, false);
  assert.deepEqual(requestsForReference, []);
  await d.page.getByText(/Your permissions prevent creation of Supports associations/).waitFor();
  const limitedGroup = d.page.locator(`[data-definition-id="${group.id}"]`);
  await action(limitedGroup, `Show Services for ${group.name}`).click();
  assert.equal(await action(limitedGroup, "Select all Services").isDisabled(), true);
  assert.equal(await limitedGroup.getByRole("checkbox", { name: `Select ${extended.name}`, exact: true }).isDisabled(), true);
  await d.page.getByText(/· restricted/).first().waitFor();
  await d.page.getByText(/Some selected Services use customised classifications/).waitFor();
  assert.equal(await action(d.page, "Save & exit").isDisabled(), true);
  await action(limitedGroup, `Edit ${standard.name}`).click();
  const limitedEditor = limitedGroup.getByRole("form");
  assert.equal(await limitedEditor.getByLabel("Service Type", { exact: true }).isDisabled(), true);
  await action(limitedEditor, "Restore catalogue defaults").click();
  await action(d.page, "Review selection").click();
  assert.equal(await action(d.page, "Apply capabilities").isDisabled(), true);
  await action(d.page, "Back to selection").click();
  for (const definition of initial.catalogue.functions) {
    await d.page.getByRole("checkbox", { name: `Select ${definition.name}`, exact: true }).uncheck();
  }
  await d.page.getByRole("checkbox", { name: `Select ${group.name}`, exact: true }).check();
  await action(d.page, "Review selection").click();
  await d.page.getByText("Atlas validated this selection.", { exact: true }).waitFor();
  assert.equal(await action(d.page, "Apply capabilities").isEnabled(), true);
  await action(d.page, "Back to selection").click();
  // Save remains possible with partial creation grants. Another user revoking
  // Site management closes the editing session on the next write.
  assert.equal(await action(d.page, "Save & exit").isEnabled(), true);
  await json(await context.request.patch(`${api}/roles/${role.id}`, {
    data: { permission_keys: permissionKeys.filter((key) => key !== "sites.manage") },
  }));
  await action(d.page, "Save & exit").click();
  await d.page.getByRole("alert").filter({ hasText: "Your access changed" }).waitFor();
  d.page.once("dialog", (dialog) => dialog.accept());
  await action(d.page, "Reload saved progress").click();
  await d.page.getByText("You can view the catalogue and Site progress.", { exact: false }).waitFor();
  assert.equal(await action(d.page, "Save & exit").count(), 0);
  assert.equal(await (await json(await d.context.request.get(restricted))).draft, null);
  await c.page.goto(`${origin}${restrictedHref}`);
  await heading(c.page, "What does your Homelab support?").waitFor();
  assert.equal(await action(c.page, "Review selection").count(), 0);
  assert.equal(await c.page.getByRole("checkbox", { name: `Select ${group.name}`, exact: true }).isDisabled(), true);
  const wrong = `${api}/onboarding/${selectedCustomer}/${blankHref.split("/").at(-1)}/capabilities`;
  assert.equal((await d.context.request.get(wrong)).status(), 404);
  await d.page.goto(wrong.slice(api.length).replace(/\/capabilities$/, "").replace(/^/, origin));
  await d.page.getByRole("alert").filter({ hasText: "Guided setup is unavailable" }).waitFor();

  // A Blank Site has no starter cards and can make the canonical no-create decision.
  await b.page.goto(`${origin}${blankHref}`);
  await heading(b.page, "Capabilities").waitFor();
  if (await action(b.page, "Resume setup").count()) await resumeWithKeyboard(b.page, "Capabilities");
  await b.page.getByText("Blank is a manual setup.", { exact: false }).waitFor();
  assert.equal(await b.page.locator('[data-definition-id^="bf."]').count(), 0);
  await action(b.page, "Skip capabilities").click();
  await heading(b.page, "Add integrations").waitFor();
  const blankStatus = await json(await b.context.request.get(`${api}${blankHref}`));
  assert.equal(blankStatus.progress.stage_decisions.capabilities, "skipped");

  async function confirmedSite(customerId, name) {
    const site = await json(await context.request.post(`${api}/sites`, {
      data: { customer_id: customerId, name },
    }), 201);
    const path = `/onboarding/${customerId}/${site.id}`;
    const pair = `${api}${path}`;
    const start = await json(await context.request.post(`${pair}/start`));
    await json(await context.request.patch(`${pair}/environment`, {
      data: { version: start.version, environment_profile: "homelab" },
    }));
    return { site, href: `${origin}${path}`, capabilities: `${pair}/capabilities` };
  }

  const emptySelection = { ...initial.defaults, functions: [], services: [], associations: [] };
  const draftRoundTrips = [];
  for (const [label, includeFunction] of [["Service-only", false], ["Unlinked endpoints", true]]) {
    const customer = await json(await context.request.post(`${api}/customers`, {
      data: { name: `E1-C.1 ${label}` },
    }), 201);
    const { site, href, capabilities } = await confirmedSite(customer.id, "Draft compatibility");
    const status = await json(await context.request.get(capabilities));
    const selectedFunction = { id: group.id, name: `${label} Function`, description: `${label} Function description.` };
    const selectedService = {
      id: standard.id, name: `${label} Service`, description: `${label} Service description.`,
      criticality_key: initial.default_criticality_key,
    };
    const selection = {
      ...emptySelection, functions: includeFunction ? [selectedFunction] : [], services: [selectedService],
    };
    await json(await context.request.put(`${capabilities}/draft`, { data: { version: status.version, selection } }));
    const before = (await json(await context.request.get(capabilities))).draft;
    assert.deepEqual(before, selection);
    const expected = [Number(includeFunction), 1, 0];
    const previewed = page.waitForResponse((response) => response.url() === `${capabilities}/preview`);
    await page.goto(href);
    await page.getByText("Saved selection restored.", { exact: true }).waitFor();
    await counts(...expected);
    const previewResponse = await previewed;
    await json(previewResponse);
    assert.deepEqual(previewResponse.request().postDataJSON().selection, before);
    if (!includeFunction) {
      await cards.first().getByText("Selected Services will be imported without this Business Function.", { exact: true }).waitFor();
    }
    await action(cards.first(), `Show Services for ${includeFunction ? selectedFunction.name : group.name}`).click();
    const row = page.locator(`[data-definition-id="${standard.id}"]`);
    assert.equal(await row.getByRole("checkbox", { name: `Select ${selectedService.name}`, exact: true }).isChecked(), true);
    assert.equal(await row.getByText(selectedService.description, { exact: true }).isVisible(), true);
    await action(page, "Save & exit").click();
    await page.waitForURL("**/dashboard");
    const after = (await json(await context.request.get(capabilities))).draft;
    assert.deepEqual(after, before);
    assert.deepEqual(await canonical("services", customer.id, site.id), []);
    assert.deepEqual(await canonical("business-functions", customer.id, site.id), []);
    await page.goto(href);
    await resumeWithKeyboard(page, "Capabilities");
    await page.getByText("Saved selection restored.", { exact: true }).waitFor();
    await counts(...expected);
    await review();
    assert.equal(await heading(page, "Services without a Supports association").isVisible(), true);
    assert.equal(await page.getByRole("list", { name: "Services that support this Business Function" }).count(), 0);
    assert.equal(await page.getByText(selectedFunction.name, { exact: true }).count(), Number(includeFunction));
    const serviceDisclosure = page.getByText(`Customised description for ${selectedService.name}`, { exact: true });
    await serviceDisclosure.click();
    assert.equal(await page.getByText(selectedService.description, { exact: true }).isVisible(), true);
    const applying = page.waitForResponse((response) => response.url() === `${capabilities}/apply`);
    await action(page, "Apply capabilities").click();
    const { created } = await json(await applying);
    assert.deepEqual(created, { functions: expected[0], services: expected[1], associations: expected[2] });
    await heading(page, "Add integrations").waitFor();
    const savedFunctions = await canonical("business-functions", customer.id, site.id);
    const savedServices = await canonical("services", customer.id, site.id);
    assert.deepEqual(savedFunctions.map(({ name, description }) => ({ name, description })),
      selection.functions.map(({ name, description }) => ({ name, description })));
    assert.deepEqual(savedServices.map(({ name, description }) => ({ name, description })),
      selection.services.map(({ name, description }) => ({ name, description })));
    assert.deepEqual(await json(await context.request.get(`${api}/services/${savedServices[0].id}/business-functions`)), []);
    draftRoundTrips.push({ label, before, after, created });
  }

  const inactive = await json(await context.request.post(`${api}/service-types`, {
    data: { key: "e1c1_test_type", name: "E1-C.1 test classification" },
  }), 201);
  const invalidSite = await confirmedSite(selectedCustomer, "Classification recovery");
  const invalidStatus = await json(await context.request.get(invalidSite.capabilities));
  const affected = [standard, others[0].services[0]];
  await json(await context.request.put(`${invalidSite.capabilities}/draft`, { data: {
    version: invalidStatus.version,
    selection: {
      ...emptySelection,
      services: affected.map(({ id }) => ({ id, service_type_key: inactive.key })),
    },
  } }));
  assert.equal((await json(await context.request.post(`${api}/service-types/${inactive.id}/deactivate`))).active, false);
  await page.setViewportSize({ width: 390, height: 950 });
  const validation = page.waitForResponse((response) => response.url() === `${invalidSite.capabilities}/preview`);
  await page.goto(invalidSite.href);
  assert.equal((await json(await validation, 422)).detail.definition_id, standard.id);
  const feedback = page.getByRole("region", { name: "Unavailable classifications" });
  await feedback.getByRole("alert").waitFor();
  assert.equal(await action(page, "Save & exit").isDisabled(), true);
  assert.equal(await cards.first().getByRole("button", { name: `Show Services for ${group.name}`, exact: true })
    .getAttribute("aria-expanded"), "false");
  for (const service of affected) {
    const target = feedback.getByRole("button", { name: `Edit classifications for ${service.name}`, exact: true });
    await target.waitFor();
    assert.match(await target.locator("..").innerText(), /Service Type unavailable/);
  }
  await capture("capabilities-unavailable-classifications-mobile", { fullPage: true });
  for (const service of affected) {
    await action(page, "Review selection").click();
    await heading(page, "Review capabilities").waitFor();
    await feedback.waitFor();
    assert.equal(await action(page, "Apply capabilities").isDisabled(), true);
    const target = feedback.getByRole("button", { name: `Edit classifications for ${service.name}`, exact: true });
    await target.focus();
    assert.equal(await target.evaluate((node) => node.getBoundingClientRect().right <= innerWidth), true);
    await page.keyboard.press("Enter");
    const row = page.locator(`[data-definition-id="${service.id}"]`);
    const editor = row.getByRole("form");
    const select = editor.getByLabel("Service Type", { exact: true });
    await select.waitFor();
    assert.equal(await select.evaluate((node) => node === document.activeElement), true);
    assert.equal(await select.getAttribute("aria-invalid"), "true");
    const validKey = initial.default_service_type_keys[service.service_type_name];
    await select.selectOption(validKey);
    await action(editor, "Save edit").click();
    await editor.waitFor({ state: "detached" });
  }
  await feedback.waitFor({ state: "detached" });
  await counts(0, 2, 0);
  assert.equal(await action(page, "Save & exit").isEnabled(), true);
  await review();
  assert.equal(await action(page, "Apply capabilities").isEnabled(), true);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);

  // The disabled preview is covered by the real API suite; verify the web entry
  // remains absent when both adapter requests report the disabled route.
  await page.route("**/api/onboarding/**", (route) => route.fulfill({ status: 404, json: { detail: "Record not found" } }));
  const noEntry = page.waitForResponse((response) => response.url() === `${api}/onboarding/contexts`);
  await page.goto(`${origin}/dashboard`);
  await heading(page, "Dashboard").waitFor();
  assert.equal((await noEntry).status(), 404);
  assert.equal(await link(page, "Guided setup").count(), 0);
  assert.equal(await link(page, "Resume").count(), 0);
  await page.unroute("**/api/onboarding/**");

  return {
    layouts, summaries, realApply: committed.created, replayUsedSameRequest: true, concurrentAdministrators: true,
    supersededPreview: true, staleDraftReplacement: true,
    customerWide: true, persistedClassification: { serviceType: serviceType.key, criticality: criticality.key },
    draftRoundTrips, reviewedDescriptions: { functionDescription, serviceDescription: longDescription },
    correctedClassifications: affected.map(({ id }) => id),
    applyRequests: requests.filter(({ endpoint }) => endpoint === "apply").map(({ payload }) => payload),
  };
}
