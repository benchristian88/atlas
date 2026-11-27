import assert from "node:assert/strict";
import { randomBytes, randomUUID } from "node:crypto";

export async function checkLinkServices({ a, b, c, origin, api, output, action, heading, openPage, resumeWithKeyboard }) {
  const { page } = a;
  const request = async (actor, method, path, data, status = 200) => {
    const response = await actor.context.request.fetch(api + path, { method, data });
    assert.equal(response.status(), status, `${method} ${path} ${await response.text()}`);
    return status === 204 ? null : response.json();
  };
  const get = (path, actor = a) => request(actor, "GET", path);
  const post = (path, data, status = 201) => request(a, "POST", path, data, status);
  const suffix = randomUUID().slice(0, 8);
  const customer = await post("/customers", { name: `Link Services acceptance ${suffix}` });
  const site = await post("/sites", { customer_id: customer.id, name: "Mapping Site" });
  const sibling = await post("/sites", { customer_id: customer.id, name: "Other Site" });
  const path = `/onboarding/${customer.id}/${site.id}`;
  const stage = "Link Services";

  async function enter(href) {
    const started = await post(href + "/start", undefined, 200);
    let state = await request(a, "PATCH", href + "/environment", { version: started.version, environment_profile: "blank" });
    state = await post(href + "/capabilities/skip", { version: state.version }, 200);
    state = await post(href + "/integrations/decision", { version: state.version, decision: "skipped" }, 200);
    return post(href + "/discovery-review/decision", { version: state.version, decision: "skipped" }, 200);
  }

  const [types, levels, relationshipTypes] = await Promise.all([
    get("/service-types"), get("/criticality-levels"), get("/relationship-types"),
  ]);
  const createService = (name, local) => post("/services", {
    customer_id: customer.id, site_id: local ? site.id : null, name,
    service_type_id: types.find(type => type.key === "application_service").id,
    criticality_level_id: levels.find(level => level.key === "medium").id,
  });
  const createAsset = (name, type = "virtual_machine", siteId = site.id, hostname) => post("/assets", {
    customer_id: customer.id, site_id: siteId, name, asset_type: type, hostname,
  });
  const wide = await createService(`Customer capability ${"LongServiceName".repeat(7)}`, false);
  const local = await createService("Site capability", true);
  const unmapped = await createService("Unmapped capability", true);
  const base = await createAsset("Existing mapping");
  const remote = await createAsset("Remote mapping", "virtual_machine", sibling.id);
  const box = await createAsset(`Backup provider ${"LongAssetName".repeat(7)}`, "physical_server");
  const vm = await createAsset("Shared virtual provider");
  const willRetire = await createAsset("Retiring provider");
  const recover = await createAsset("Unconfirmed provider");
  const spare = await createAsset("Unsubmitted provider");
  const dependencyPath = service => `/services/${service.id}/asset-dependencies`;
  const ordinary = asset => post(dependencyPath(wide), {
    asset_id: asset.id, relationship_type_id: relationshipTypes.find(type => type.key === "runs_on").id,
  });
  await ordinary(base);
  const remoteEdge = await ordinary(remote);
  await enter(path);

  const step = heading(page, stage);
  const ready = heading(page, "Review & Ready");
  const serviceButton = (surface, service) => surface.getByRole("button").filter({ hasText: service.name });
  const mappingDialog = (name) => page.getByRole("dialog", { name });
  const checkbox = asset => page.getByRole("checkbox", { name: new RegExp(asset.name) });
  const virtualAssetContext = asset => ["Virtual Machine", asset.hostname?.trim(), `ID ${asset.id}`].filter(Boolean).join(" · ");
  const virtualAssetLabel = asset => `${asset.name} · ${virtualAssetContext(asset)}`;
  const removeAsset = asset => action(page, `Remove ${virtualAssetLabel(asset)} mapping`);
  const searchAssets = page.getByRole("searchbox", { name: "Search Assets" });
  const layout = [];
  const scoped = path + "/link-services";
  const mapAdd = (service, asset) => scoped + `/services/${service.id}/assets/${asset.id}`;
  const mutations = [];
  page.on("request", req => {
    if (["POST", "DELETE"].includes(req.method()) && req.url().includes("/link-services/services/")) mutations.push(req.url());
  });

  async function openService(service, surface = page) {
    await serviceButton(surface, service).click();
    await heading(surface, service.name).waitFor();
  }

  function linkCount(term, count) {
    return page.locator("dl").filter({ has: page.getByText("Asset mappings", { exact: true }) })
      .locator("div").filter({ has: page.getByText(term, { exact: true }) }).getByText(String(count), { exact: true });
  }

  async function confirmAdd() {
    await action(page, "Add selected Assets").click();
    const dialog = mappingDialog("Add Asset mappings");
    await dialog.waitFor();
    return dialog;
  }

  await page.goto(origin + path);
  await step.waitFor();
  await linkCount("Services linked", 1).waitFor();
  await linkCount("Services unlinked", 2).waitFor();
  await linkCount("Asset mappings", 1).waitFor();
  const serviceSearch = page.getByRole("searchbox", { name: "Search Services" });
  const filter = page.getByRole("combobox", { name: "Mapping status" });
  assert.equal(await filter.inputValue(), "all");
  await filter.selectOption("linked");
  await serviceButton(page, local).waitFor({ state: "detached" });
  await filter.selectOption("unlinked");
  await serviceButton(page, wide).waitFor({ state: "detached" });
  await filter.selectOption("all");
  await serviceSearch.fill("Customer capability");
  await serviceButton(page, local).waitFor({ state: "detached" });
  assert.equal(await serviceSearch.evaluate(input => input === document.activeElement), true);
  await serviceSearch.fill("");
  await page.route(`**${scoped}/services/${wide.id}?*`, route => route.abort(), { times: 1 });
  await openService(wide);
  const readFailure = page.getByRole("alert").filter({ hasText: "Asset mappings could not be loaded" });
  await readFailure.waitFor();
  assert.equal(await readFailure.evaluate(alert => alert === document.activeElement), true);
  await action(page, "Reload asset mappings").click();
  await page.getByText(remote.name, { exact: true }).waitFor();
  await page.getByText(virtualAssetContext(remote), { exact: false }).waitFor();
  assert.equal(await removeAsset(remote).count(), 0);

  await searchAssets.fill("backup");
  await checkbox(vm).waitFor({ state: "detached" });
  assert.equal(await searchAssets.evaluate(input => input === document.activeElement), true);
  await page.getByRole("combobox", { name: "Asset Type" }).selectOption("physical_server");
  await checkbox(box).check();
  await checkbox(vm).waitFor({ state: "detached" });
  await searchAssets.fill("");
  await page.getByRole("combobox", { name: "Asset Type" }).selectOption("");
  await checkbox(vm).check();
  await page.getByText("2 selected", { exact: true }).waitFor();

  // Switching Services clears both the selected IDs and the Asset filters.
  await openService(local);
  await checkbox(box).waitFor();
  assert.equal(await checkbox(box).isChecked(), false);
  await page.getByText("0 selected", { exact: true }).waitFor();
  await openService(wide);
  await checkbox(box).check();
  await checkbox(vm).check();
  const addDialog = await confirmAdd();
  await addDialog.getByText(wide.name, { exact: true }).waitFor();
  await addDialog.getByText(box.name, { exact: true }).waitFor();
  await addDialog.getByText(vm.name, { exact: true }).waitFor();
  assert.equal(await action(addDialog, "Cancel").evaluate(button => button === document.activeElement), true);
  await addDialog.screenshot({ path: `${output}/e1f-add-confirmation.png` });
  assert.equal(mutations.length, 0);
  await addDialog.locator("form").evaluate(form => {
    for (let attempt = 0; attempt < 2; attempt++) form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  });
  await linkCount("Asset mappings", 3).waitFor();
  assert.equal(mutations.length, 2);
  const initial = await get(dependencyPath(wide));
  assert.deepEqual(new Set(initial.map(row => row.asset_id)), new Set([base.id, box.id, vm.id, remote.id]));
  await checkbox(box).waitFor({ state: "detached" });
  await openService(local);
  await checkbox(vm).check();
  await action(await confirmAdd(), "Confirm add").click();
  await linkCount("Services linked", 2).waitFor();
  assert.deepEqual((await get(dependencyPath(local))).map(row => row.asset_id), [vm.id]);

  const remove = removeAsset(vm);
  await remove.click();
  const removeDialog = mappingDialog("Remove mapping");
  await removeDialog.getByText(local.name, { exact: true }).waitFor();
  await removeDialog.getByText(vm.name, { exact: true }).waitFor();
  assert.equal(await action(removeDialog, "Cancel").evaluate(button => button === document.activeElement), true);
  await page.keyboard.press("Escape");
  await removeDialog.waitFor({ state: "hidden" });
  assert.equal(await remove.evaluate(button => button === document.activeElement), true);
  assert.equal((await get(dependencyPath(local))).length, 1);
  await remove.click();
  await action(removeDialog, "Confirm removal").click();
  await page.getByText(`Removed · ${vm.name}`).waitFor();
  await linkCount("Asset mappings", 3).waitFor();
  assert.equal((await get(dependencyPath(local))).length, 0);
  assert.equal((await get(dependencyPath(wide))).find(row => row.asset_id === remote.id).id, remoteEdge.id);

  await checkbox(vm).check();
  await checkbox(willRetire).check();
  const partial = await confirmAdd();
  await request(b, "PATCH", `/assets/${willRetire.id}`, { status: "retired" });
  await action(partial, "Confirm add").click();
  await page.getByRole("alert").filter({ hasText: "This Asset is retired" }).waitFor();
  assert.deepEqual((await get(dependencyPath(local))).map(row => row.asset_id), [vm.id]);
  await page.getByText("Review selection", { exact: true }).click();
  await action(page, `Deselect ${virtualAssetLabel(willRetire)}`).click();
  await page.getByText("0 selected", { exact: true }).waitFor();

  let removedResponse = 0;
  await page.route(api + mapAdd(local, recover), async route => {
    const response = await route.fetch();
    assert.equal(response.status(), 200);
    removedResponse += 1;
    await route.abort();
  }, { times: 1 });
  await checkbox(recover).check();
  await checkbox(spare).check();
  await action(await confirmAdd(), "Confirm add").click();
  const check = action(page, "Check current mappings");
  await check.waitFor();
  assert.equal(removedResponse, 1);
  assert.equal(await action(page, "Add selected Assets").isDisabled(), true);
  assert.equal(mutations.filter(url => url.endsWith(spare.id)).length, 0);
  await page.reload();
  await openService(local);
  await check.waitFor();
  await check.click();
  await page.getByText(/Current saved mappings refreshed/).waitFor();
  assert.deepEqual(new Set((await get(dependencyPath(local))).map(row => row.asset_id)), new Set([vm.id, recover.id]));
  assert.equal(mutations.filter(url => url.endsWith(recover.id)).length, 1);
  assert.equal(await checkbox(spare).isChecked(), false);

  await checkbox(spare).check();
  await page.getByText(/Unsubmitted selections are cleared/).waitFor();
  await action(page, "Save & exit").click();
  await page.waitForURL("**/dashboard");
  await page.goto(origin + path);
  await resumeWithKeyboard(page, stage);
  await openService(local);
  await checkbox(spare).waitFor();
  assert.equal(await checkbox(spare).isChecked(), false);
  await page.getByText(recover.name, { exact: true }).waitFor();

  for (const [theme, accent] of [["light", "#2563EB"], ["dark", "#7C3AED"]]) {
    const profile = await get("/auth/me");
    await request(a, "PATCH", "/auth/profile", { display_name: profile.display_name, theme_mode: theme, accent_colour: accent });
    await page.reload();
    await openService(wide);
    await page.getByText(remote.name, { exact: true }).waitFor();
    for (const width of [1440, 1024, 800, 390]) {
      await page.setViewportSize({ width, height: 950 });
      assert.equal(await page.locator("html").getAttribute("data-theme"), theme);
      assert.equal(await page.locator(".app-shell").evaluate(el => el.style.getPropertyValue("--accent")), accent);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
      await page.screenshot({ path: `${output}/e1f-${theme}-${width}.png`, fullPage: true });
      layout.push({ theme, accent, width });
    }
  }

  await c.page.goto(origin + path);
  await openService(wide, c.page);
  await c.page.getByText(/Read-only mapping access/).waitFor();
  assert.equal(await action(c.page, "Add selected Assets").count(), 0);
  assert.equal(await action(c.page, "Skip").count(), 0);
  await c.page.screenshot({ path: `${output}/e1f-read-only.png`, fullPage: true });

  const reviewedService = await createService("Confirmation integrity", true);
  const relationship = key => relationshipTypes.find(type => type.key === key).id;
  const reviewed = await post(dependencyPath(reviewedService), { asset_id: vm.id, relationship_type_id: relationship("runs_on") });
  const removalUrl = api + scoped + `/services/${reviewedService.id}/mappings/${reviewed.id}`;
  const removedByOther = await post(dependencyPath(reviewedService), { asset_id: recover.id, relationship_type_id: relationship("runs_on") });
  await page.setViewportSize({ width: 1440, height: 950 });
  await page.reload();
  await openService(reviewedService);
  await remove.click();
  await removeDialog.getByText(reviewed.relationship_type_name, { exact: true }).waitFor();
  const changed = await request(b, "PATCH", `/service-asset-dependencies/${reviewed.id}`, {
    relationship_type_id: relationship("depends_on"),
  });
  await removeDialog.screenshot({ path: `${output}/e1f1-stale-removal.png` });
  const rejected = page.waitForResponse(response => response.url() === removalUrl && response.status() === 409);
  await action(removeDialog, "Confirm removal").click();
  assert.equal((await (await rejected).json()).detail.code, "link_mapping_changed");
  const stale = page.getByRole("alert").filter({ hasText: "This relationship changed since confirmation" });
  await stale.waitFor();
  assert.equal(await stale.evaluate(el => el === document.activeElement), true);
  assert.equal(mutations.filter(url => url === removalUrl).length, 1);
  const stillCurrent = (await get(dependencyPath(reviewedService))).find(edge => edge.id === reviewed.id);
  assert.equal(stillCurrent.relationship_type_id, changed.relationship_type_id);
  assert.equal(stillCurrent.valid_to, null);
  await remove.click();
  await removeDialog.getByText(changed.relationship_type_name, { exact: true }).waitFor();
  await action(removeDialog, "Confirm removal").click();
  await page.getByText(`Removed · ${virtualAssetLabel(vm)}`, { exact: true }).waitFor();
  assert.equal(mutations.filter(url => url === removalUrl).length, 2);

  await removeAsset(recover).click();
  await request(b, "DELETE", `/service-asset-dependencies/${removedByOther.id}`, undefined, 204);
  await action(removeDialog, "Confirm removal").click();
  await page.getByRole("alert").filter({ hasText: "This mapping is no longer available" }).waitFor();
  await removeAsset(recover).waitFor({ state: "detached" });
  assert.deepEqual(await get(dependencyPath(reviewedService)), []);
  const history = await get(dependencyPath(reviewedService) + "?include_history=true");
  assert.equal(history.length, 2);
  assert.ok(history.every(edge => edge.valid_to));

  const identityService = await createService("Identity precision", true);
  const identityAsset = (name, hostname) => createAsset(`Identity ${name}`, "virtual_machine", site.id, hostname);
  const hosted = await Promise.all(["primary.lab", "standby.lab"].map(hostname => identityAsset("00 duplicate", hostname)));
  const blankHostnames = [undefined, null, "", " ", "\t", "\r\n\u00a0\u2003"];
  const missing = await Promise.all(blankHostnames.map(hostname => identityAsset("01 missing", hostname)));
  const long = await identityAsset(`02 ${"LongAssetName".repeat(14)}`, `${"longhost".repeat(23)}.lab`);
  for (let index = 0; index < 15; index++) await identityAsset(`03 filler ${index}`);
  const identical = (await Promise.all([1, 2].map(() => identityAsset("04 identical", "shared.lab"))))
    .sort((first, second) => first.id.localeCompare(second.id));
  const ordinaryAsset = await identityAsset("05 ordinary");
  await page.reload();
  await openService(identityService);
  const filtered = page.waitForResponse(response => {
    const url = new URL(response.url());
    return url.pathname.endsWith(`/services/${identityService.id}`)
      && url.searchParams.get("search") === "Identity"
      && url.searchParams.get("asset_type") === "virtual_machine";
  });
  await searchAssets.fill("Identity");
  await page.getByRole("combobox", { name: "Asset Type" }).selectOption("virtual_machine");
  assert.equal((await filtered).status(), 200);
  const checkboxWithIdentity = asset => page.getByRole("checkbox", {
    name: `${asset.name} ${virtualAssetContext(asset)}`, exact: true,
  });
  async function assertIdentity(asset) {
    const box = checkboxWithIdentity(asset);
    await box.waitFor();
    const row = box.locator("..");
    assert.equal(await row.locator("strong").innerText(), asset.name);
    assert.equal(await row.locator("small").innerText(), virtualAssetContext(asset));
  }
  const longRow = checkboxWithIdentity(long).locator("..");
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 950 });
    for (const asset of [...hosted, ...missing, long, identical[0]]) await assertIdentity(asset);
    assert.equal(await checkboxWithIdentity(identical[1]).count(), 0);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    const label = longRow.locator("small");
    assert.equal(await label.evaluate(el => el.scrollWidth <= el.clientWidth), true);
    if (width === 390) {
      assert.equal(await label.evaluate(el => el.getBoundingClientRect().height > parseFloat(getComputedStyle(el).fontSize) * 2), true);
      assert.equal(await longRow.locator("strong").evaluate(el => {
        const bounds = el.parentElement.getBoundingClientRect();
        const range = document.createRange();
        range.selectNodeContents(el);
        const lines = [...range.getClientRects()];
        return lines.length > 1 && lines.every(line => line.left >= bounds.left - 1 && line.right <= bounds.right + 1);
      }), true);
    }
    await longRow.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${output}/e1f2-asset-identity-${width}.png`, fullPage: true });
  }
  await checkboxWithIdentity(hosted[1]).press("Space");
  await page.getByText("1 selected", { exact: true }).waitFor();
  assert.equal(await checkboxWithIdentity(hosted[1]).isChecked(), true);
  const tabOnly = missing[4];
  await checkboxWithIdentity(tabOnly).check();
  await checkboxWithIdentity(long).check();
  const assetPages = page.getByRole("navigation", { name: "Available Asset pages" });
  await action(assetPages, "Next").click();
  await assertIdentity(identical[1]);
  assert.equal(await checkboxWithIdentity(identical[0]).count(), 0);
  await checkboxWithIdentity(identical[1]).check();
  await assertIdentity(ordinaryAsset);
  await checkboxWithIdentity(ordinaryAsset).check();
  const exactSelection = [hosted[1], tabOnly, long, identical[1], ordinaryAsset];
  const identityDialog = await confirmAdd();
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 950 });
    assert.deepEqual(await identityDialog.locator("li strong").allInnerTexts(), exactSelection.map(asset => asset.name));
    assert.deepEqual(await identityDialog.locator("li small").allInnerTexts(), exactSelection.map(virtualAssetContext));
    assert.equal(await identityDialog.evaluate(el => el.scrollWidth <= el.clientWidth), true);
    await identityDialog.screenshot({ path: `${output}/e1f2-identity-confirmation-${width}.png` });
  }
  await action(identityDialog, "Confirm add").focus();
  await page.keyboard.press("Enter");
  const expectedUrls = exactSelection.map(asset => api + mapAdd(identityService, asset));
  await page.getByText(`Added · ${virtualAssetLabel(ordinaryAsset)}`, { exact: true }).waitFor();
  assert.deepEqual(mutations.filter(url => url.includes(identityService.id)), expectedUrls);
  const linked = (await get(dependencyPath(identityService))).map(edge => edge.asset_id).sort();
  assert.deepEqual(linked, exactSelection.map(asset => asset.id).sort());
  for (const asset of exactSelection) {
    const linkedRow = removeAsset(asset).locator("..");
    assert.equal(await linkedRow.locator("strong").innerText(), asset.name);
    assert.equal(await linkedRow.locator("small").innerText(), `${virtualAssetContext(asset)} · Depends on`);
  }
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);

  const beforeConflict = (await get(path)).progress;
  const saved = await request(b, "POST", path + "/save", { version: beforeConflict.version });
  await request(b, "POST", path + "/resume", { version: saved.version });
  const continueButton = action(page, "Continue to Review & Ready");
  await continueButton.click();
  const continueDialog = mappingDialog("Continue Link Services");
  await continueDialog.getByText(/Services still have no Asset mappings/).waitFor();
  await action(continueDialog, "Acknowledge and continue").click();
  const conflict = page.getByRole("alert").filter({ hasText: "Setup progress changed" });
  await conflict.waitFor();
  assert.equal(await conflict.evaluate(alert => alert === document.activeElement), true);
  await action(page, "Reload progress").click();
  await step.waitFor();
  await serviceButton(page, unmapped).waitFor();
  await continueButton.click();
  await action(continueDialog, "Acknowledge and continue").click();
  await ready.waitFor();
  await heading(page, "Setup summary").waitFor();
  const advanced = (await get(path)).progress;
  assert.equal(advanced.stage_decisions.link_services, "attention");
  assert.equal(advanced.current_stage, "review_ready");
  await action(page.getByRole("navigation", { name: "Setup stages" }), stage).click();
  await openService(wide);
  assert.equal(await continueButton.count(), 0);
  await action(page, "Return to current stage").click();
  await ready.waitFor();
  assert.deepEqual((await get(path)).progress, advanced);

  const emptyCustomer = await post("/customers", { name: `Blank mapping acceptance ${suffix}` });
  const emptySite = await post("/sites", { customer_id: emptyCustomer.id, name: "Blank Site" });
  const emptyPath = `/onboarding/${emptyCustomer.id}/${emptySite.id}`;
  await enter(emptyPath);
  await page.goto(origin + emptyPath);
  await page.getByText("No authorised Services in this setup.").waitFor();
  await linkCount("Asset mappings", 0).waitFor();
  await page.screenshot({ path: `${output}/e1f-empty.png`, fullPage: true });

  const role = await post("/roles", {
    name: `Workflow only ${suffix}`, permission_keys: ["customers.view", "sites.view", "sites.manage"],
  });
  const email = `e1f-${suffix}@example.com`;
  const password = randomBytes(24).toString("base64url");
  await post("/users", { email, display_name: "Workflow operator", temporary_password: password, force_password_change: false,
    assignments: [{ role_id: role.id, scope_type: "site", customer_id: emptyCustomer.id, site_id: emptySite.id }] });
  const restricted = await openPage();
  await request(restricted, "POST", "/auth/login", { email, password });
  await restricted.page.goto(origin + path);
  await restricted.page.getByText(/setup is unavailable/i).first().waitFor();
  await restricted.page.goto(origin + emptyPath);
  await restricted.page.getByText("Service inventory is unavailable with your current permissions.").waitFor();
  await action(restricted.page, "Skip").click();
  await heading(restricted.page, "Review & Ready").waitFor();
  assert.equal((await get(emptyPath)).progress.stage_decisions.link_services, "skipped");

  return { layout, attention: advanced.stage_decisions.link_services,
    confirmationIntegrity: { dependencyId: reviewed.id, concurrentlyRemovedId: removedByOther.id, serviceId: reviewedService.id },
    assetIdentity: {
      serviceId: identityService.id, linkedAssetIds: linked, widths: [1440, 390],
      absentHostnameId: missing[0].id, tabOnlyHostnameId: tabOnly.id,
    },
    skipped: (await get(emptyPath)).progress.stage_decisions.link_services, mutationRequests: mutations.length };
}
