import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";

export async function checkStageNavigation({ a, b, origin, api, action, heading }) {
  const { page } = a;
  const rail = page.getByRole("navigation", { name: "Setup stages" });
  const returnButton = () => action(page, "Return to current stage");
  const suffix = randomUUID().slice(0, 8);
  async function request(actor, path, method = "GET", data, status = 200) {
    const response = await actor.context.request.fetch(api + path, { method, data });
    assert.equal(response.status(), status, await response.text());
    return response.json();
  }
  const get = path => request(a, path);
  const post = (path, data, status) => request(a, path, "POST", data, status);
  const progress = async path => (await get(path)).progress;
  const customer = await post("/customers", { name: `Stage navigation ${suffix}` }, 201);
  async function start(profile) {
    const site = await post("/sites", { customer_id: customer.id, name: `${profile} revisit` }, 201);
    const path = `/onboarding/${customer.id}/${site.id}`;
    const draft = await post(path + "/start");
    const confirmed = await request(a, path + "/environment", "PATCH", {
      version: draft.version, environment_profile: profile,
    });
    await post(path + "/capabilities/skip", { version: confirmed.version });
    return path;
  }

  const review = await start("blank");
  const capabilities = await start("homelab");
  for (const [command, data] of [
    ["integrations/decision", { decision: "skipped" }],
    ["discovery-review/decision", { decision: "skipped" }],
    ["link-services/decision", { action: "skip" }],
  ]) {
    await post(review + "/" + command, { ...data, version: (await progress(review)).version });
  }
  const writes = [];
  const trackWrite = request => {
    const path = new URL(request.url()).pathname;
    // Capabilities preview is read-only, although the selection is sent as a POST.
    if (path.startsWith("/api/") && request.method() !== "GET" && !path.endsWith("/capabilities/preview")) {
      writes.push(`${request.method()} ${path}`);
    }
  };
  page.on("request", trackWrite);
  try {
    const initial = await progress(review);
    const cursorUrl = api + review;
    await page.goto(origin + review);
    await heading(page, "Setup summary").waitFor();
    await action(page, "Back to Link Services").click();
    await action(page, "Back to Discovery Review").click();
    await heading(page, "Discovery review").waitFor();

    await page.route(cursorUrl, route => route.fulfill({
      status: 503, json: { detail: "Workflow read unavailable" },
    }), { times: 1 });
    await returnButton().click();
    const unavailable = page.getByRole("alert").filter({ hasText: "Current setup progress could not be verified." });
    await unavailable.waitFor();
    await heading(page, "Discovery review").waitFor();
    assert.equal(await heading(page, "Review & Ready").count(), 0);
    assert.equal(await action(unavailable, "Reload progress").isEnabled(), true);
    assert.deepEqual(await progress(review), initial);

    const captured = Promise.withResolvers();
    const release = Promise.withResolvers();
    const settled = Promise.withResolvers();
    await page.route(cursorUrl, async route => {
      let interceptionError;
      try {
        const response = await route.fetch();
        const state = await response.json();
        captured.resolve({ request: route.request(), progress: state.progress });
        await release.promise;
        await route.fulfill({ response });
      } catch (error) {
        captured.reject(error);
        if (!route.request().failure()) interceptionError = error;
      } finally {
        settled.resolve(interceptionError);
      }
    }, { times: 1 });
    try {
      await returnButton().click();
      const earlier = await captured.promise;
      assert.deepEqual(earlier.progress, initial);
      const cancelled = page.waitForEvent("requestfailed", { predicate: req => req === earlier.request });
      await action(rail, "Link Services").click();
      await heading(page, "Link Services").waitFor();
      await cancelled;

      const advanced = await request(b, review + "/review-ready/decision", "POST", { version: initial.version });
      assert.equal(advanced.current_stage, "showcase");
      assert.equal(advanced.version, initial.version + 1);
      assert.equal(advanced.completed_at, null);
      const verified = page.waitForResponse(response =>
        response.url() === cursorUrl && response.request().method() === "GET" && response.ok());
      await returnButton().click();
      assert.deepEqual((await (await verified).json()).progress, advanced);
      await heading(page, "Showcase").waitFor();
      release.resolve();
      assert.equal(await settled.promise, undefined);
      assert.match(await rail.locator('[aria-current="step"]').innerText(), /Showcase\s+Pending/);
      assert.deepEqual(await progress(review), advanced);
      assert.deepEqual(writes, []);
    } finally {
      release.resolve();
    }

    const original = await progress(capabilities);
    const capUrl = capabilities + "/capabilities";
    const definitions = await get(capUrl);
    const group = definitions.catalogue.functions[0];
    const service = group.services[0];
    const card = page.locator(`[data-definition-id="${group.id}"]`);
    const row = card.locator(`[data-definition-id="${service.id}"]`);
    const [types, levels] = await Promise.all([get("/service-types?active_only=true"), get("/criticality-levels?active_only=true")]);
    const values = {
      Name: `Local revisit service ${suffix}`,
      Description: "Preserve this local edit during an Environment visit.",
      "Service Type": types.find(type => type.key !== definitions.default_service_type_keys[service.service_type_name]).key,
      Criticality: levels.find(level => level.key !== definitions.default_criticality_key).key,
    };
    async function edit(name) {
      await action(row, `Edit ${name}`).click();
      return row.getByRole("form");
    }
    async function customise() {
      const form = await edit(service.name);
      await form.getByLabel("Name", { exact: true }).fill(values.Name);
      await form.getByLabel("Description", { exact: true }).fill(values.Description);
      await form.getByLabel("Service Type", { exact: true }).selectOption(values["Service Type"]);
      await form.getByLabel("Criticality", { exact: true }).selectOption(values.Criticality);
      await action(form, "Save edit").click();
    }
    async function assertLocalEdits() {
      assert.equal(await row.getByRole("checkbox", { name: `Select ${values.Name}`, exact: true }).isChecked(), true);
      const form = await edit(values.Name);
      for (const [label, value] of Object.entries(values)) {
        assert.equal(await form.getByLabel(label, { exact: true }).inputValue(), value);
      }
      await action(form, "Cancel edit").click();
    }

    await page.goto(origin + capabilities);
    await action(page, "Back to Capabilities").click();
    await action(card, `Show Services for ${group.name}`).click();
    const defaultSelection = row.getByRole("checkbox", { name: `Select ${service.name}`, exact: true });
    await defaultSelection.check();
    await customise();
    const unsavedEditor = await edit(values.Name);
    const unsavedDescription = unsavedEditor.getByLabel("Description", { exact: true });
    await unsavedDescription.fill("An edit still open in the form");
    await action(rail, "Environment").click();
    await heading(page, "Environment").waitFor();
    await action(rail, "Capabilities").click();
    assert.equal(await unsavedDescription.inputValue(), "An edit still open in the form");
    await action(unsavedEditor, "Cancel edit").click();
    await assertLocalEdits();

    await action(page, "Back to Environment").click();
    await heading(page, "Environment").waitFor();
    await returnButton().click();
    await heading(page, "Add integrations").waitFor();
    await action(page, "Back to Capabilities").click();
    await assertLocalEdits();
    assert.deepEqual(await progress(capabilities), original);
    assert.equal((await get(capUrl)).draft, null);
    assert.deepEqual(writes, []);

    page.once("dialog", dialog => dialog.dismiss());
    await action(page, "Restore recommended selection").click();
    await assertLocalEdits();
    page.once("dialog", dialog => dialog.accept());
    await action(page, "Restore recommended selection").click();
    await defaultSelection.waitFor();
    await defaultSelection.check();
    await customise();
    await action(page, "Save & exit").click();
    await page.waitForURL("**/dashboard");
    const saved = await progress(capabilities);
    assert.equal(saved.status, "saved");
    assert.equal(saved.version, original.version + 1);
    assert.equal(saved.current_stage, original.current_stage);
    assert.deepEqual(saved.stage_decisions, original.stage_decisions);
    await page.goto(origin + capabilities);
    await action(page, "Resume setup").click();
    await action(page, "Back to Capabilities").click();
    await action(card, `Show Services for ${group.name}`).click();
    await assertLocalEdits();
    assert.deepEqual(writes, [`PUT /api${capUrl}/draft`, `POST /api${capabilities}/resume`]);
    return { currentStage: "showcase", version: initial.version + 1, failedReturnStayedOnRevisit: true,
      supersededReturnDiscarded: true, retainedCapabilityEdits: true, explicitResetAndResume: true };
  } finally {
    page.off("request", trackWrite);
  }
}
