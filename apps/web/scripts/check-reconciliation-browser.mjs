// Fixture-backed reconciliation acceptance. All API traffic is intercepted;
// no operator reconciliation decisions or discovery records are touched.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const origin = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3149";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-reconciliation-validation/browser";
await mkdir(output, { recursive: true });
const id = number => `00000000-0000-4000-8000-${String(number).padStart(12, "0")}`;
const customer = { id: id(1), name: "Acceptance customer" };
const site = { id: id(2), customer_id: customer.id, name: "Acceptance site" };
const version = "1".repeat(64);
const base = { customer_id: customer.id, site_id: site.id, status: "open", entity_type: "asset", category: "changed", current: null, current_value_json: null, proposed: "Observed value", observed_value_json: { value: "Observed value" }, can_accept: false, can_reject: true, can_defer: true, source_name: "Fixture source", assertion_predicate: "generic.fact", candidate_external_id: "opaque identity", version, warning: null, blockers: [], blocked_reason: null };
const permissions = ["reconciliation.view", "reconciliation.decide", "assets.view", "relationships.create", "networks.view", "networks.create", "networks.edit"];
const targetName = "Proxmox host with a long descriptive operational name ".repeat(3).trim();
const summarySources = ["A", "B"].map((name, index) => ({ assertion_id: id(80 + index), source_id: id(90 + index), source_name: `Proxmox ${name}`, last_observed_at: "2026-11-01T00:00:00Z", accepted_at: "2026-11-01T01:00:00Z", value: null }));
const relationshipValue = { relationship_type: "runs_on", label: "Runs on", direction: "outgoing", target_id: id(71), target_name: targetName, href: `/assets/${id(71)}` };
const summaryBase = { source_count: 2, assertion_count: 2, historical_count: 0, conflict: false, unresolved: false, last_observed_at: "2026-11-01T00:00:00Z" };
const knowledgeGroups = [
  { ...summaryBase, predicate: "asset_type", label: "Asset Type", cardinality: "single", state: "observed", awaiting_acceptance: true, canonical_value: "lxc_container", canonical_display_value: "LXC Container", canonical_consistency: "missing_acceptance", accepted_values: [], accepted_groups: [], latest_observations: summarySources, observation_groups: [{ key: "type", display_value: "LXC Container", assertions: summarySources, source_count: 2 }] },
  { ...summaryBase, predicate: "runs_on", label: "Runs on", cardinality: "multi", state: "accepted", canonical_consistency: "not_applicable", accepted_values: summarySources, latest_observations: summarySources, accepted_groups: [{ key: "relation", relationship: relationshipValue, assertions: summarySources, source_count: 2 }], observation_groups: [{ key: "relation", relationship: relationshipValue, assertions: summarySources, source_count: 2 }] },
];
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
const checks = [], errors = [], requests = [];
let activePage;
try {
  for (const theme of ["light", "dark"]) for (const accent of [null, "#2563EB", "#7C3AED"]) {
    const context = await browser.newContext({ colorScheme: theme });
    const page = await context.newPage();
    activePage = page;
    if (process.env.ATLAS_BROWSER_DEBUG) {
      page.on("console", message => process.stdout.write(`BROWSER ${message.text()}\n`));
      await page.addInitScript(() => {
        for (const method of ["pushState", "replaceState"]) {
          const original = history[method];
          history[method] = function (...args) { console.log(method, args[2]); return original.apply(this, args); };
        }
        document.addEventListener("click", event => console.log("click", event.target.closest("a,button,summary")?.outerHTML));
        document.addEventListener("input", event => console.log("input", event.target.tagName, event.target.value));
      });
    }
    page.setDefaultTimeout(15000);
    page.on("pageerror", error => errors.push(error.message));
    let parentAccepted = false, childrenAccepted = false, interfaceLinked = false, linkAttempts = 0;
    let snapshotMode = false, snapshotRevision = 3, snapshotAccepted = false;
    function snapshotGroup() {
      const current = snapshotRevision === 3 ? "Curated" : "New manual value";
      const fact = { ...base, id: id(20), label: "Name", assertion_predicate: "name", current, proposed: "Observed",
        current_value_json: { field: "name", value: current }, observed_value_json: { field: "name", value: "Observed" },
        version: String(snapshotRevision).repeat(64), can_accept: !snapshotAccepted, status: snapshotAccepted ? "accepted" : "open" };
      return { ...group(), parent: null, default_expanded: true, matching_record_count: 1,
        sections: [{ key: "facts", label: "Facts", total: 1, blocked_count: 0, warnings: [], items: [fact], next_offset: null }],
        decision_items: [{ id: fact.id, version: fact.version }] };
    }
    function group(host = false) {
      const parent = { ...base, id: id(host ? 11 : 10), label: "New asset", category: "newly_discovered", status: !host && parentAccepted ? "accepted" : "open", can_accept: true };
      const facts = Array.from({ length: 6 }, (_, index) => ({ ...base, id: id(20 + index), label: `Fact ${index + 1}`, can_accept: parentAccepted, blocked_reason: parentAccepted ? null : "Requires Workload to exist", blockers: parentAccepted ? [] : [{ entity_id: id(10), item_id: id(10), name: "Workload" }] }));
      const relationship = { ...base, id: id(30), entity_type: "asset_relationship", label: "Runs on → Host", blocked_reason: "Requires Host to exist", blockers: [{ entity_id: id(11), item_id: id(11), name: "Host" }] };
      const network = { ...base, id: id(interfaceLinked ? 33 : 31), version: linkAttempts ? "2".repeat(64) : version, entity_type: "asset_interface", label: "Interface net0", category: interfaceLinked ? "changed" : "newly_discovered", assertion_predicate: "configuration", can_accept: parentAccepted && interfaceLinked, technical_identity: !interfaceLinked, can_link_technical: parentAccepted && !interfaceLinked, link_asset_id: parentAccepted ? id(50) : null, link_blocked_reason: "Accept or link the source Asset before linking its interface", current: interfaceLinked ? { name: "net0", mac_address: "02:00:00:00:00:01", ip_address: "192.0.2.8" } : null, proposed: { name: "net0", mac_address: "02:00:00:00:00:02", ip_address: "192.0.2.9" }, blocked_reason: parentAccepted ? interfaceLinked ? null : "Link the existing interface before applying changes" : "Requires Workload to exist" };
      const bridge = { ...base, id: id(32), entity_type: "asset_interface", label: "net0 · Bridge", proposed: "bridge0", assertion_predicate: "generic.bridge", can_accept: interfaceLinked, blocked_reason: interfaceLinked ? null : "Requires net0 to exist" };
      const sections = host ? [] : [
        ...(!childrenAccepted ? [{ key: "facts", label: "Facts", total: 6, blocked_count: parentAccepted ? 0 : 6, warnings: parentAccepted ? [] : ["Requires Workload to exist"], items: facts, next_offset: null }] : []),
        { key: "relationships", label: "Relationships", total: 1, blocked_count: 1, warnings: ["Requires Host to exist"], items: [relationship], next_offset: null },
        ...(!childrenAccepted ? [{ key: "network", label: "Network", total: 2, blocked_count: parentAccepted ? 1 : 2, warnings: ["Requires net0 to exist"], items: [network, bridge], next_offset: null }] : []),
      ];
      const records = [...sections.flatMap(section => section.items), ...(parent.status === "open" ? [parent] : [])];
      return { id: parent.id, customer_id: customer.id, site_id: site.id, name: host ? "Host" : "Workload", type_label: "Virtual Machine", entity_type: "asset", entity_id: parentAccepted && !host ? id(50) : null, asset_type: "virtual_machine", icon_key: "server", accent_key: "teal", parent, default_expanded: parent.status === "open", matching_record_count: records.length, status_counts: { open: records.length }, sections, accept_all_available: true, decision_items: records.map(row => ({ id: row.id, version: row.version })), bulk_limit: 1000 };
    }
    await page.route("**/api/**", async route => {
      const request = route.request(), url = new URL(request.url()), path = url.pathname.replace(/^\/api/, "");
      requests.push({ path, query: url.search, method: request.method() });
      let body = [], status = 200;
      if (snapshotMode && path === "/reconciliation-entities") body = { entities: [snapshotGroup()], entity_total: 1, record_total: 1, limit: 50, next_cursor: null, by_status: {}, by_category: {} };
      else if (snapshotMode && path === `/reconciliation-entities/${id(10)}`) body = snapshotGroup();
      else if (snapshotMode && [ `/reconciliation-items/${id(20)}/accept`, `/reconciliation-entities/${id(10)}/accept` ].includes(path)) {
        const bulk = path.includes("reconciliation-entities"), payload = request.postDataJSON();
        const reviewed = bulk ? payload.items[0].version : payload.expected_version;
        const fresh = reviewed === String(snapshotRevision).repeat(64);
        if (fresh) snapshotAccepted = true;
        if (bulk) body = { accepted: fresh ? [{ id: id(20), label: "Name" }] : [], failed: fresh ? [] : [{ id: id(20), label: "Name", reason: "This proposal changed; refresh before deciding" }], blocked: [], already_resolved: [] };
        else { status = fresh ? 200 : 409; body = fresh ? {} : { detail: "This proposal changed; refresh before deciding" }; }
      }
      else if (path === "/setup/status") body = { state: "INITIALISED" };
      else if (path === "/auth/me") body = { id: id(90), email: "reviewer@example.test", display_name: "Acceptance reviewer", theme_mode: theme, accent_colour: accent, permissions, assignments: [{ scope_type: "global", permissions, role_name: "Reviewer" }] };
      else if (path === "/context") body = { global_access: true, customers: [customer], sites: [site] };
      else if (path === "/assets") body = [];
      else if (path === `/assets/${id(70)}`) body = { id: id(70), customer_id: customer.id, site_id: site.id, name: "esphome", asset_type: "lxc_container", status: "active", source: "discovery", metadata: {}, custom_fields: {} };
      else if (path === `/assets/${id(70)}/knowledge-summary`) body = { asset_id: id(70), groups: knowledgeGroups, conflict_count: 0, unresolved_count: 0, consistency_issue_count: 1 };
      else if (path === `/assets/${id(70)}/fact-history`) body = { facts: { runs_on: summarySources.map(entry => ({ ...entry, value: { relationship: "Runs on", target: targetName }, is_accepted: true })) } };
      else if (path === "/assertions") body = summarySources.map(entry => ({ ...entry, id: entry.assertion_id, predicate: "runs_on", value_json: { target_asset_id: id(71) }, is_source_current: true, is_accepted: true, confirmation_status: "confirmed", truth_classification: "observed" }));
      else if (path === "/asset-interfaces") {
        if (url.searchParams.get("asset_id") === id(50)) {
          assert.equal(url.searchParams.get("limit"), "100");
          body = [{ id: id(60), asset_id: id(50), name: "net0", mac_address: "02:00:00:00:00:01", ip_address: "192.0.2.8" },
            { id: id(61), asset_id: id(51), name: "Hidden other-owner interface" }];
        }
      }
      else if (path === "/reconciliation-entities") {
        let entities = [group()];
        if (url.searchParams.get("search")?.toLowerCase() === "host") entities = [group(true)];
        else if (url.searchParams.get("search") && !"workload".includes(url.searchParams.get("search").toLowerCase())) entities = [];
        const section = url.searchParams.get("section");
        if (section) entities = entities.filter(entity => entity.sections.some(candidate => candidate.key === section)).map(entity => ({ ...entity, sections: entity.sections.filter(candidate => candidate.key === section) }));
        body = { entities, entity_total: entities.length ? 2 : 0, record_total: childrenAccepted ? 2 : parentAccepted ? 10 : 11, limit: 50, next_cursor: null, by_status: {}, by_category: {} };
      }
      else if (path === `/reconciliation-entities/${id(11)}`) body = group(true);
      else if (path === `/reconciliation-entities/${id(10)}`) body = group();
      else if (path === `/reconciliation-items/${id(10)}/accept`) {
        assert.equal(request.postDataJSON().expected_version, version);
        parentAccepted = true; body = {};
      }
      else if (path === `/reconciliation-items/${id(31)}/link-technical`) {
        assert.equal(request.postDataJSON().expected_version, linkAttempts ? "2".repeat(64) : version);
        assert.equal(request.postDataJSON().entity_id, id(60));
        linkAttempts += 1;
        if (linkAttempts === 1) { status = 409; body = { detail: "This proposal changed; refresh before deciding" }; }
        else { interfaceLinked = true; body = {}; }
      }
      else if (path === `/reconciliation-entities/${id(10)}/accept`) {
        assert.ok(request.postDataJSON().items.length >= 2);
        childrenAccepted = true;
        body = { accepted: Array.from({ length: 8 }, (_, index) => ({ id: id(100 + index), label: "Accepted change" })), already_resolved: [], blocked: [{ id: id(30), label: "Runs on → Host", reason: "Requires Host to exist" }], failed: [] };
      }
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.goto(`${origin}/reconciliation`);
    await page.getByText("11 reconciliation records grouped into 2 entities", { exact: false }).waitFor();
    const card = page.getByRole("article", { name: "Review Workload", exact: true });
    await card.getByRole("button", { name: "Accept asset", exact: true }).waitFor();
    assert.equal(await card.locator("details").first().getAttribute("open"), "");
    assert.equal(await card.getByRole("button", { name: "Accept", exact: true }).first().isDisabled(), true);
    await card.locator(".review-section summary").filter({ hasText: "Facts" }).click();
    await card.getByText("Fact 1", { exact: true }).waitFor({ state: "visible" });
    await card.locator(".review-section summary").filter({ hasText: "Facts" }).click();
    assert.equal(await card.getByText("Fact 1", { exact: true }).isVisible(), false);
    assert.equal(await card.locator(".review-section-warnings").filter({ hasText: "Requires Workload" }).isVisible(), true);
    for (const width of [1440, 1024, 800, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${theme} ${accent} ${width}: overflow`);
      assert.equal(await page.locator(".page-header h1").evaluate(node => getComputedStyle(node).fontSize), "28px");
      if (accent === null && [1440, 390].includes(width)) await page.screenshot({ path: `${output}/reconciliation-${theme}-${width}.png`, fullPage: true });
      checks.push({ theme, accent, width });
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await card.getByRole("link", { name: "Review Host", exact: true }).click();
    await page.waitForURL(url => url.searchParams.get("entity") === id(11));
    const host = page.getByRole("article", { name: "Review Host", exact: true });
    await host.waitFor();
    assert.equal(await host.evaluate(node => node === document.activeElement), true);
    await page.goBack();
    await page.waitForURL(url => !url.searchParams.has("entity"));
    await card.waitFor();
    await page.goForward();
    await page.waitForURL(url => url.searchParams.get("entity") === id(11));
    await host.waitFor();
    await page.reload();
    await host.waitFor();
    assert.equal(await host.locator("details").first().getAttribute("open"), "");
    await page.getByRole("link", { name: "Return to previous entity" }).click();
    await page.waitForURL(url => url.searchParams.get("entity") === id(10));
    await card.getByRole("button", { name: "Accept asset", exact: true }).click();
    await card.getByText("Accepted", { exact: true }).first().waitFor();
    await card.locator(".review-section summary").filter({ hasText: "Facts" }).click();
    await page.waitForFunction(identifier => !document.querySelector(`[aria-labelledby="review-item-${identifier}"] button`).disabled, id(20));
    assert.equal(await card.getByRole("article", { name: "Fact 1", exact: true }).getByRole("button", { name: "Accept", exact: true }).isEnabled(), true);
    const technical = card.getByRole("article", { name: "Interface net0", exact: true });
    const disclosure = technical.locator("summary").filter({ hasText: "Link existing interface" });
    await disclosure.focus(); await page.keyboard.press("Enter");
    const selector = technical.getByLabel("Existing interface", { exact: true });
    await selector.locator(`option[value="${id(60)}"]`).waitFor({ state: "attached" });
    assert.equal(await selector.locator(`option[value="${id(61)}"]`).count(), 0);
    assert.equal(await technical.getByRole("button", { name: "Link interface", exact: true }).isDisabled(), true);
    // macOS headless native selects use type-ahead; arrow keys open an OS
    // popup that does not commit its selection in this automation environment.
    await selector.focus(); await page.keyboard.press("n"); await page.keyboard.press("Tab");
    assert.equal(await selector.inputValue(), id(60));
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
      if (accent === null) await page.screenshot({ path: `${output}/technical-link-${theme}-${width}.png`, fullPage: true });
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await technical.getByRole("button", { name: "Link interface", exact: true }).focus(); await page.keyboard.press("Enter");
    await page.getByRole("alert").filter({ hasText: "This proposal changed" }).waitFor();
    await page.reload();
    await disclosure.focus(); await page.keyboard.press("Enter");
    await selector.locator(`option[value="${id(60)}"]`).waitFor({ state: "attached" });
    assert.equal(await selector.inputValue(), "");
    await selector.focus(); await page.keyboard.press("n"); await page.keyboard.press("Tab");
    await technical.getByRole("button", { name: "Link interface", exact: true }).focus(); await page.keyboard.press("Enter");
    await page.getByText("Identity linked. Accepted configuration is preserved; observed configuration and source facts still need review.", { exact: true }).waitFor();
    await card.getByRole("button", { name: "Accept interface changes", exact: true }).waitFor();
    assert.equal(await card.getByText("02:00:00:00:00:01", { exact: true }).count(), 1);
    await card.getByRole("button", { name: "Accept all", exact: true }).click();
    await page.getByText("Workload: 8 accepted · 0 already resolved · 1 waiting · 0 failed").waitFor();
    await page.getByText("Runs on → Host: Requires Host to exist", { exact: true }).waitFor();
    await page.waitForFunction(() => !document.querySelector("main")?.textContent.includes("Loading entity reviews"));
    assert.equal(await card.getByText("Runs on → Host", { exact: true }).count(), 1);
    await page.getByRole("searchbox", { name: "Search entities" }).fill("Host");
    await page.waitForURL(url => url.searchParams.get("search") === "Host");
    await host.waitFor();
    await page.locator(".catalogue-more-filters summary").click();
    await page.getByLabel("Review section", { exact: true }).selectOption("relationships");
    await page.waitForURL(url => url.searchParams.get("section") === "relationships");
    await page.getByText("No reconciliation items in this queue.", { exact: true }).waitFor();
    // Simulate another operator's committed PATCH between review and decision.
    // HTTP/PostgreSQL tests establish backend truth; this checks display/token
    // forwarding and refresh behavior for both browser decision paths.
    snapshotMode = true;
    for (const mode of ["individual", "bulk"]) {
      snapshotRevision = 3; snapshotAccepted = false;
      await page.goto(`${origin}/reconciliation`);
      const fact = card.getByRole("article", { name: "Name", exact: true });
      await fact.locator(".review-value").getByText("Curated", { exact: true }).waitFor();
      snapshotRevision = 4;
      if (mode === "individual") {
        await fact.getByRole("button", { name: "Accept", exact: true }).click();
        await page.getByRole("alert").filter({ hasText: "This proposal changed" }).waitFor();
        await page.reload();
      } else {
        await card.getByRole("button", { name: "Accept all", exact: true }).click();
        await page.getByText("Workload: 0 accepted · 0 already resolved · 0 waiting · 1 failed").waitFor();
      }
      await fact.locator(".review-value").getByText("New manual value", { exact: true }).waitFor();
      assert.equal(await fact.locator(".review-value").getByText("Curated", { exact: true }).count(), 0);
      await fact.locator(".review-provenance summary").click();
      await fact.getByText('{"field":"name","value":"New manual value"}', { exact: true }).waitFor();
      await (mode === "individual" ? fact.getByRole("button", { name: "Accept", exact: true }) : card.getByRole("button", { name: "Accept all", exact: true })).click();
      await fact.getByText("Accepted", { exact: true }).waitFor();
      assert.equal(snapshotAccepted, true);
      checks.push({ surface: "canonical-review", mode, theme, accent });
    }
    snapshotMode = false;
    await page.goto(`${origin}/assets/${id(70)}`);
    const typeKnowledge = page.getByRole("article", { name: "Asset Type knowledge", exact: true });
    await typeKnowledge.getByText("Not selected", { exact: true }).waitFor();
    assert.equal(await typeKnowledge.getByText("Unresolved", { exact: true }).count(), 0);
    await typeKnowledge.getByText("Observed", { exact: true }).waitFor();
    const relationKnowledge = page.getByRole("article", { name: "Runs on knowledge", exact: true });
    assert.equal(await relationKnowledge.locator(".knowledge-accepted a").count(), 1);
    const targetLink = relationKnowledge.getByRole("link", { name: `Runs on: ${targetName}`, exact: true }).first();
    assert.equal(await targetLink.getAttribute("href"), `/assets/${id(71)}`);
    await targetLink.focus();
    assert.equal(await targetLink.evaluate(node => node === document.activeElement), true);
    await relationKnowledge.locator(".knowledge-accepted summary").focus(); await page.keyboard.press("Enter");
    await relationKnowledge.locator(".knowledge-accepted").getByText("Proxmox A", { exact: true }).waitFor();
    await relationKnowledge.locator(".knowledge-accepted").getByText("Proxmox B", { exact: true }).waitFor();
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
      if (accent === null) await page.screenshot({ path: `${output}/asset-knowledge-${theme}-${width}.png`, fullPage: true });
      checks.push({ surface: "asset-knowledge", theme, accent, width });
    }
    await page.getByRole("tab", { name: "History", exact: true }).click();
    await page.locator(".knowledge-timeline").waitFor();
    await page.getByRole("tab", { name: "Raw assertions", exact: true }).click();
    await page.locator(".assertion-group summary").filter({ hasText: "runs on" }).click();
    assert.equal(await page.locator(".assertions-table code").filter({ hasText: id(71) }).count(), 2);
    await context.close();
    process.stdout.write(`PASS ${theme} ${accent || "default"}: reconciliation keyboard links/stale refresh/navigation; AK-01/AK-02 values/provenance/history/raw; responsive layouts\n`);
  }
  assert.deepEqual(errors, [], "No browser runtime errors");
  await writeFile(`${output}/report.json`, JSON.stringify({ checks, errors, requests: requests.length }, null, 2));
  process.stdout.write(`PASS ${checks.length} viewport/theme/accent states; screenshots and report: ${output}\n`);
} catch (error) {
  await writeFile(`${output}/failure.json`, JSON.stringify({ errors, requests, url: activePage?.url(), text: await activePage?.locator("body").innerText() }, null, 2));
  await activePage?.screenshot({ path: `${output}/failure.png`, fullPage: true });
  throw error;
} finally { await browser.close(); }
