// Production browser acceptance using isolated authorized API fixtures only.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { showcaseFixture, showcaseRealShapeFixture, showcaseReferenceFixture, showcaseTallFixture, showcaseWideFixture, showcaseUltrawideFixture, showcaseExteriorRoutingFixture, showcaseDenseRoutingFixture, showcaseLiveRoutingFixture, showcaseReadableFixture, id } from "../tests/fixtures/showcase.mjs";
import { showcaseLayout, showcaseModel, showcaseFilename, SHOWCASE_MAX_UPSCALE, SHOWCASE_CONTENT_TOP } from "../lib/showcase.mjs";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const base = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3110";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-showcase-browser";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: process.env.ATLAS_CHROME_PATH });
const permissions = ["assets.view", "relationships.view", "networks.view", "customers.view", "sites.view"];
const reports = [];
try {
  for (const [size, theme] of [["small", "light"], ["readable", "light"], ["exterior", "light"], ["dense-routing", "light"], ["live-routing", "light"], ["medium", "light"], ["large", "light"], ["real-shape", "light"], ["reference", "light"], ["adaptive", "light"], ["maximum", "light"], ["wide", "light"], ["ultrawide", "light"], ["both", "light"], ["wide", "dark"], ["medium", "dark"], ["adaptive", "dark"]]) {
    const data = size === "readable" ? showcaseReadableFixture() : size === "exterior" ? showcaseExteriorRoutingFixture() : size === "dense-routing" ? showcaseDenseRoutingFixture() : size === "live-routing" ? showcaseLiveRoutingFixture() : size === "reference" ? showcaseReferenceFixture() : size === "real-shape" ? showcaseRealShapeFixture() : size === "adaptive" ? showcaseTallFixture(60) : size === "maximum" ? showcaseTallFixture(74) : size === "wide" ? showcaseWideFixture() : size === "ultrawide" ? showcaseUltrawideFixture() : size === "both" ? showcaseWideFixture(18, 70) : showcaseFixture(size);
    const layout = showcaseLayout(showcaseModel(data, id(2))), exportWidth = layout.sceneWidth * 2, exportHeight = layout.sceneHeight * 2;
    assert.ok(layout.complete);
    if (["reference", "real-shape", "wide", "ultrawide", "readable"].includes(size)) {
      assert.equal(layout.sceneHeight, 1080);
      assert.equal(layout.diagnostics.collapsedGroupCount, 0);
      assert.ok(layout.items.every(n => !n.hiddenCount));
    }
    if (["exterior", "dense-routing", "live-routing"].includes(size)) {
      assert.ok(layout.diagnostics.fallbackRouteCount > 0);
      assert.ok(layout.scale > 1 && layout.scale <= SHOWCASE_MAX_UPSCALE); assert.equal(layout.sceneWidth, 1920); assert.equal(layout.sceneHeight, 1080);
      assert.equal(layout.diagnostics.visibleAssetTileCount, data.assets.length);
      assert.equal(layout.diagnostics.workloadCollapseAttempted, false);
    }
    const site = data.sites[0], customer = data.customers[0];
    // Exercise optional cached-icon and type-icon failure without blocking export.
    data.assets[0].cached_icon_url = `/api/assets/${data.assets[0].id}/icon`;
    data.assets[1].cached_icon_url = `/api/assets/${data.assets[1].id}/icon`;
    data.asset_types[0].default_icon_url = "https://icons.example.test/missing.png";
    data.asset_types.find(t => t.key === "platform").default_icon_url = "https://icons.example.test/type.png";
    const context = await browser.newContext({ viewport: { width: 1800, height: 1200 }, colorScheme: theme, reducedMotion: "reduce" });
    const page = await context.newPage(), errors = [], requests = [], networkRequests = [];
    page.on("request", request => { if (request.url().startsWith("http")) networkRequests.push(request.url()); });
    page.on("pageerror", e => errors.push(e.message));
    await page.route("https://icons.example.test/**", async route => route.request().url().endsWith("/type.png")
      ? route.fulfill({ contentType: "image/png", headers: { "access-control-allow-origin": "*" }, body: await readFile(new URL("../public/branding/favicon-32x32.png", import.meta.url)) })
      : route.fulfill({ status: 404, body: "" }));
    await page.route("**/api/**", async route => {
      const url = new URL(route.request().url()); requests.push(url.pathname);
      if (url.pathname.endsWith("/icon")) return url.pathname.includes(data.assets[1].id)
        ? route.fulfill({ contentType: "image/png", body: await readFile(new URL("../public/branding/favicon-32x32.png", import.meta.url)) })
        : route.fulfill({ status: 404, body: "" });
      let body = [];
      if (url.pathname === "/api/auth/me") body = { id: id(999), display_name: "Showcase fixture", email: "fixture@example.test", theme_mode: theme, permissions, assignments: [{ scope_type: "global", permissions }] };
      if (url.pathname === "/api/context") body = { customers: [customer], sites: [site], selected_customer_id: customer.id, selected_site_id: site.id, global_access: true };
      if (url.pathname === "/api/topology") {
        assert.equal(route.request().headers()["x-atlas-site-id"], site.id);
        assert.equal(route.request().headers()["x-atlas-customer-id"], customer.id);
        body = data;
      }
      if (url.pathname === "/api/topology/connectivity") {
        // Complete authorized renderer fixture, deliberately without the API's
        // neighbourhood cap. The separate regression harness exercises the real
        // Python traversal for 1/2/3 hops, classes, focus and Networks controls.
        const enabled = new Set(url.searchParams.getAll("category_ids"));
        const types = new Map(data.asset_types.map(t => [t.key, t]));
        const assets = data.assets.filter(a => enabled.has(types.get(a.asset_type).category_id));
        const nodes = assets.map(a => ({ key: `asset:${a.id}`, entity_type: "asset", entity_id: a.id,
          name: a.name, topology_position: types.get(a.asset_type).topology_position, distance: 2,
          eligible_child_count: data.structural_edges.filter(e => e.platform_parent_key === `asset:${a.id}`).length }));
        if (url.searchParams.get("show_networks") === "true") nodes.push(...data.networks.map(n => ({ key: `network:${n.id}`, name: n.name, entity_type: "network", entity_id: n.id, distance: 2 })));
        const keys = new Set(nodes.map(n => n.key));
        const edges = data.structural_edges.filter(e => keys.has(e.source_key) && keys.has(e.target_key));
        body = { nodes, edges, focus_key: `asset:${url.searchParams.get("focus_asset_id")}`, truncated: false, node_limit: 100, edge_limit: 500 };
      }
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.goto(`${base}/topology`);
    await page.getByRole("button", { name: "Platform", exact: true }).click();
    await page.locator(".topology-platform-card").first().waitFor();
    const platformBefore = await page.locator(".topology-platform-section").allTextContents();
    if (["reference", "real-shape", "wide", "ultrawide", "readable"].includes(size)) {
      await page.getByRole("button", { name: "Connectivity", exact: true }).click();
      await page.getByRole("button", { name: /^Filters/ }).click();
      await page.getByRole("checkbox", { name: /^Edge Devices/ }).check();
      await page.keyboard.press("Escape");
      await page.getByRole("checkbox", { name: "Networks", exact: true }).uncheck();
      await page.getByRole("button", { name: "Expand Infrastructure Topology", exact: true }).click();
      await page.getByRole("button", { name: "3 hops", exact: true }).click();
      await page.getByRole("button", { name: "Hide details panel", exact: true }).click();
      await page.locator("[data-node-key]").first().waitFor();
      for (let i = 0; i < data.assets.length * 2; i++) {
        const controls = page.locator(".topology-disclosure-badge, .topology-disclosure-more");
        if (!await controls.count()) break;
        await controls.first().click();
      }
      assert.equal(await page.locator("[data-node-key]").count(), data.assets.length);
      assert.equal(await page.locator('[data-node-key^="network:"]').count(), 0);
      assert.equal(await page.locator(".topology-disclosure-badge, .topology-disclosure-more").count(), 0);
      await page.getByRole("button", { name: "Fit", exact: true }).click();
      await page.screenshot({ path: `${output}/${size}-connectivity-networks-off-expanded.png`, fullPage: true });
      await page.getByRole("button", { name: "Close expanded Infrastructure Topology", exact: true }).click();
    }
    await page.getByRole("button", { name: "Showcase", exact: true }).click();
    const scene = page.locator(".showcase-scene"), button = page.getByRole("button", { name: "Export PNG", exact: true });
    await scene.waitFor(); await button.waitFor();
    await page.waitForFunction(() => !document.querySelector(".showcase-actions button")?.disabled);
    assert.equal(await scene.getAttribute("viewBox"), `0 0 ${layout.sceneWidth} ${layout.sceneHeight}`);
    assert.equal(await scene.evaluate(el => getComputedStyle(el).colorScheme), "light");
    assert.equal(await scene.locator("image").count(), 2 + data.assets.filter(a => a.asset_type === "platform").length, "Logo, cached Asset icon and Type fallback images are embedded");
    // Platform was visited above; only Showcase's resource preparation is
    // constrained to one fetch per URL. Its embedded previews share that result.
    const tiles = await scene.locator("[data-showcase-asset]").evaluateAll(tiles => tiles.map(tile => ({
      id: tile.getAttribute("data-showcase-asset"), title: tile.querySelector(":scope > title").textContent,
      labels: [...tile.querySelectorAll(":scope > text")].map(text => ({ text: text.textContent,
        lines: [...text.querySelectorAll("tspan")].map(line => ({ text: line.textContent, length: line.getComputedTextLength() })),
        fontSize: text.getAttribute("font-size") })),
      budget: Number(tile.getAttribute("data-text-width")), artworkWidth: Number(tile.querySelector("image, svg")?.getAttribute("width")), icons: tile.querySelectorAll("image, path, circle, rect").length,
    })));
    for (const tile of tiles) {
      const asset = data.assets.find(a => a.id === tile.id);
      assert.equal(tile.title, asset.name, "Accessible title contains the full name only");
      assert.equal(tile.labels.length, 1, "Every tile contains one Asset name, no Type or metadata");
      assert.ok(tile.labels[0].lines.length >= 1 && tile.labels[0].lines.length <= 2);
      assert.ok(tile.labels[0].lines.every(line => line.length <= tile.budget + .5), "Every name line respects its measured text budget");
      assert.equal(Number(tile.labels[0].fontSize), 15, "Asset font size stays unchanged before uniform scene scaling");
      if (tile.labels[0].text.includes("…")) assert.ok(tile.labels[0].lines.length === 2 && tile.labels[0].lines[1].text.endsWith("…"), "Ellipsis is only used after the two-line capacity is exhausted");
      assert.ok(tile.icons > 0);
      assert.equal(tile.artworkWidth, 20, "Compact artwork retains a 20px viewport");
    }
    if (["reference", "real-shape", "wide", "ultrawide", "exterior", "dense-routing", "live-routing", "readable"].includes(size)) {
      assert.equal(tiles.length, data.assets.length, "Every normal-size-site Asset has an explicit tile");
      assert.equal(new Set(tiles.map(tile => tile.labels[0].text)).size, data.assets.length,
        "Compact numbered hosts/workloads retain distinguishable name endings");
      assert.ok(!(await scene.textContent()).match(/\+\d+/), "No workload/endpoint roll-up in a normal Showcase");
    }
    if (size === "readable") {
      assert.equal(tiles.length, 44);
      for (const tile of tiles) assert.equal(tile.labels[0].lines.map(line => line.text).join(" "), tile.title, "Realistic common names remain complete, including two-line names");
      assert.ok(tiles.some(tile => tile.labels[0].lines.length === 2));
    }
    assert.equal(await page.getByLabel("Showcase diagnostics", { exact: true }).count(), 0, "Production pages do not expose detailed diagnostics");
    const content = scene.locator(":scope > g");
    assert.equal(await content.getAttribute("transform"), `translate(${layout.x} ${layout.y}) scale(${layout.scale})`);
    const contentBounds = await content.evaluate(el => {
      const b = el.getBBox(), m = el.ownerSVGElement.getCTM().inverse().multiply(el.getCTM());
      return { left: m.e + b.x * m.a, top: m.f + b.y * m.d,
        right: m.e + (b.x + b.width) * m.a, bottom: m.f + (b.y + b.height) * m.d };
    });
    assert.ok(contentBounds.left >= 32 - .5 && contentBounds.right <= layout.sceneWidth - 32 + .5);
    assert.ok(contentBounds.top >= SHOWCASE_CONTENT_TOP - .5 && contentBounds.bottom <= layout.sceneHeight - 32 + .5);
    if (size === "live-routing") {
      assert.ok(layout.scale > 1);
      assert.ok(contentBounds.top < SHOWCASE_CONTENT_TOP + 24, "Shallow graph sits beneath the header");
    }
    for (const route of layout.routes) assert.equal(await scene.locator(`[data-showcase-connector="${route.key}"]`).getAttribute("d"), route.path);
    const invalidEndpoints = await scene.evaluate(svg => {
      const rectangles = new Map(), matrixFor = el => svg.getCTM().inverse().multiply(el.getCTM());
      const boxFor = el => {
        const b = el.getBBox(), m = matrixFor(el);
        return { left: m.e + b.x * m.a, right: m.e + (b.x + b.width) * m.a,
          top: m.f + b.y * m.d, bottom: m.f + (b.y + b.height) * m.d };
      };
      for (const group of svg.querySelectorAll('[data-showcase-kind="category"]')) rectangles.set(group.dataset.showcaseItem, boxFor(group.querySelector(":scope > rect")));
      for (const tile of svg.querySelectorAll("[data-showcase-asset]")) {
        const rectangle = tile.parentElement.dataset.showcaseKind === "asset" ? tile.parentElement.querySelector(":scope > rect") : tile.querySelector(":scope > rect");
        rectangles.set(`asset:${tile.dataset.showcaseAsset}`, boxFor(rectangle));
      }
      const invalid = [];
      for (const path of svg.querySelectorAll("[data-showcase-connector]")) for (const role of ["source", "target"]) {
        const key = path.dataset[role === "source" ? "showcaseSource" : "showcaseTarget"], b = rectangles.get(key);
        const p = path.getPointAtLength(role === "source" ? 0 : path.getTotalLength()), m = matrixFor(path);
        const x = m.e + p.x * m.a, y = m.f + p.y * m.d;
        if (!b || !((Math.abs(x - b.left) < .1 || Math.abs(x - b.right) < .1) && y >= b.top - .1 && y <= b.bottom + .1 ||
          (Math.abs(y - b.top) < .1 || Math.abs(y - b.bottom) < .1) && x >= b.left - .1 && x <= b.right + .1)) invalid.push({ relationship: path.dataset.showcaseConnector, role, key, x, y });
      }
      return invalid;
    });
    assert.deepEqual(invalidEndpoints, [], "Every SVG connector terminates on a visible tile or legitimate group boundary");
    if (["exterior", "dense-routing", "live-routing"].includes(size)) {
      const rendered = await scene.locator("[data-showcase-asset]").evaluateAll(tiles => tiles.map(tile => {
        const box = tile.getBBox(), matrix = tile.ownerSVGElement.getCTM().inverse().multiply(tile.getCTM());
        return { left: matrix.e + box.x * matrix.a, top: matrix.f + box.y * matrix.d,
          right: matrix.e + (box.x + box.width) * matrix.a, bottom: matrix.f + (box.y + box.height) * matrix.d };
      }));
      assert.equal(rendered.length, data.assets.length);
      assert.ok(rendered.every(r => r.left >= 0 && r.top >= 100 && r.right <= layout.sceneWidth && r.bottom <= layout.sceneHeight));
    }
    const previewRatio = await scene.evaluate(el => el.getBoundingClientRect().width / el.getBoundingClientRect().height);
    assert.ok(Math.abs(previewRatio - layout.sceneWidth / layout.sceneHeight) < .001, "Preview preserves the selected aspect ratio");
    assert.equal(await scene.locator("[data-showcase-connector][stroke-dasharray]").count(), 0);
    for (const group of layout.items.filter(n => n.kind === "category")) {
      assert.ok(group.members.length >= 2);
      assert.equal(group.memberColumns, group.members.length < 5 ? 1 : 2);
      const rendered = scene.locator(`[data-showcase-item="${group.key}"]`);
      const transforms = await rendered.locator("[data-showcase-asset]").evaluateAll(tiles => tiles.map(tile => tile.getAttribute("transform")));
      assert.deepEqual(transforms, group.preview.map((_, i) => `translate(${12 + (i % group.memberColumns) * (group.memberWidth + group.memberGap)} ${group.memberTop + Math.floor(i / group.memberColumns) * group.memberRow})`));
    }
    for (const group of await scene.locator('[data-showcase-kind="category"]').all()) assert.ok(!/\b\d+ workloads?\b/.test(await group.textContent()));
    for (const group of layout.items.filter(n => n.kind === "category" && n.hiddenCount)) {
      const element = scene.locator("[data-showcase-item]").filter({ has: page.locator("title", { hasText: group.name }) });
      assert.ok((await element.allTextContents()).some(text => text.includes(`+${group.hiddenCount}`)));
    }
    const text = await scene.textContent();
    for (const network of data.networks) assert.ok(!text.includes(network.name), "Logical Networks never enter Showcase");
    assert.ok(text.includes(site.name));
    for (const hidden of ["192.0.2.99", "private.example.test", "Recorded:", "Export PNG", "Cluster"]) assert.ok(!text.includes(hidden), hidden);
    for (const forbidden of ["Focus", "Filters", "Refresh", "Hide details panel", "Expand Infrastructure Topology"]) assert.equal(await page.getByRole("button", { name: forbidden, exact: true }).count(), 0);
    const geometry = await scene.evaluate(el => [...el.querySelectorAll("[data-showcase-item]")].map(n => [n.getAttribute("data-showcase-item"), n.getAttribute("transform")]));
    const countBefore = requests.length;
    await page.setViewportSize({ width: 1000, height: 900 });
    assert.deepEqual(await scene.evaluate(el => [...el.querySelectorAll("[data-showcase-item]")].map(n => [n.getAttribute("data-showcase-item"), n.getAttribute("transform")])), geometry);
    assert.equal(requests.length, countBefore);
    for (const element of [scene, page.locator(".showcase-frame")]) {
      const box = await element.boundingBox();
      assert.ok(box.x >= 0 && box.x + box.width <= 1000, "Full preview stays within the narrow page");
      assert.ok(await element.evaluate(el => el.scrollWidth <= el.clientWidth + 1), "No internal horizontal scrollbar");
    }
    await page.setViewportSize({ width: 1800, height: 1200 });
    await page.screenshot({ path: `${output}/${size}-${theme}.png`, fullPage: true });
    await scene.screenshot({ path: `${output}/${size}-${theme}-scene.png` });
    if (size === "readable") {
      const member = data.assets.find(n => n.name === "Proxmox Data Center Manager");
      await scene.locator('[data-showcase-kind="category"]').filter({ has: page.locator(`[data-showcase-asset="${member.id}"]`) })
        .screenshot({ path: `${output}/readable-workload-names.png` });
    }
    if (["medium", "large", "real-shape"].includes(size)) {
      const media = page.locator('[data-showcase-kind="category"]').filter({ hasText: "Media & Photos" });
      assert.equal(await media.count(), size === "real-shape" ? 3 : size === "medium" ? 1 : 2);
      await media.first().screenshot({ path: `${output}/${size}-${theme}-host-local-category.png` });
    }
    const beforeExport = networkRequests.length;
    await context.setOffline(true);
    const downloadPromise = page.waitForEvent("download"); await button.click(); const download = await downloadPromise;
    assert.equal(download.suggestedFilename(), showcaseFilename(site.name));
    const path = `${output}/${size}-${theme}-export.png`; await download.saveAs(path);
    const png = await readFile(path);
    assert.equal(png.subarray(1, 4).toString(), "PNG"); assert.equal(png.readUInt32BE(16), exportWidth); assert.equal(png.readUInt32BE(20), exportHeight);
    assert.equal(networkRequests.length, beforeExport, "Export makes no network requests and works offline");
    await context.setOffline(false);
    let parity;
    if (["medium", "real-shape", "reference", "adaptive", "maximum", "wide", "ultrawide", "both", "exterior", "dense-routing", "live-routing", "readable"].includes(size) && theme === "light") {
      await page.setViewportSize({ width: exportWidth + 460, height: exportHeight + 640 });
      await page.locator(".showcase-frame").evaluate((frame, width) => { frame.style.width = `${width}px`; frame.style.border = "0"; frame.style.borderRadius = "0"; }, exportWidth);
      const preview = await scene.screenshot({ path: `${output}/${size}-preview-at-export-resolution.png` });
      parity = await page.evaluate(async ([first, second, exportWidth, exportHeight]) => {
        const pixels = async data => {
          const image = new Image(); image.src = `data:image/png;base64,${data}`; await image.decode();
          const canvas = document.createElement("canvas"); canvas.width = exportWidth; canvas.height = exportHeight;
          const ctx = canvas.getContext("2d"); ctx.drawImage(image, 0, 0); return ctx.getImageData(0, 0, exportWidth, exportHeight).data;
        };
        const [a, b] = await Promise.all([pixels(first), pixels(second)]);
        let difference = 0, changed = 0;
        for (let i = 0; i < a.length; i += 4) {
          const delta = Math.abs(a[i] - b[i]) + Math.abs(a[i + 1] - b[i + 1]) + Math.abs(a[i + 2] - b[i + 2]);
          difference += delta; if (delta > 120) changed++;
        }
        return { meanChannelDifference: difference / (exportWidth * exportHeight * 3), changedPixelFraction: changed / (exportWidth * exportHeight) };
      }, [preview.toString("base64"), png.toString("base64"), exportWidth, exportHeight]);
      assert.ok(parity.meanChannelDifference < 2 && parity.changedPixelFraction < .02, JSON.stringify(parity));
    }
    assert.deepEqual(errors, []);
    await page.getByRole("button", { name: "Platform", exact: true }).click();
    assert.deepEqual(await page.locator(".topology-platform-section").allTextContents(), platformBefore);
    const exported = await context.newPage(); await exported.setContent(`<img style="width:100%;height:auto" src="data:image/png;base64,${png.toString("base64")}" />`);
    await exported.locator("img").waitFor(); await exported.screenshot({ path: `${output}/${size}-${theme}-export-opened.png` });
    reports.push({ size, theme, assets: data.assets.length, logicalDimensions: [layout.sceneWidth, layout.sceneHeight], dimensions: [exportWidth, exportHeight], scale: layout.scale, diagnostics: layout.diagnostics, parity, errors });
    if (size === "small") {
      // No partial or empty export when the complete current-site source empties.
      data.assets = []; data.structural_edges = []; data.platform_links = [];
      await page.getByRole("button", { name: "Refresh", exact: true }).click();
      await page.locator(".topology-platform-card").first().waitFor({ state: "detached" });
      await page.getByRole("button", { name: "Showcase", exact: true }).click();
      await page.getByText("No Assets recorded for this site yet.", { exact: true }).waitFor();
      assert.equal(await page.getByRole("button", { name: "Export PNG", exact: true }).count(), 0);
    }
    if (size === "maximum") {
      await page.setViewportSize({ width: 1800, height: 1200 });
      Object.assign(data, showcaseWideFixture(28));
      const unsupported = showcaseLayout(showcaseModel(data, id(2)));
      assert.equal(unsupported.complete, false);
      reports.push({ size: "unsupported", diagnostics: unsupported.diagnostics });
      await page.getByRole("button", { name: "Refresh", exact: true }).click();
      await page.getByRole("button", { name: "Showcase", exact: true }).click();
      await page.getByText(/Showcase incomplete:/).waitFor();
      assert.equal(await page.getByRole("button", { name: "Export PNG", exact: true }).count(), 0);
      assert.equal(await page.locator(".showcase-scene").count(), 0);
      assert.equal(await page.getByLabel("Showcase diagnostics", { exact: true }).count(), 0);
      assert.ok(!(await page.locator(".main-content").count()) || !(await page.locator(".main-content").textContent()).includes("requiredScale"));
      await page.screenshot({ path: `${output}/oversized-incomplete.png`, fullPage: true });
    }
    await context.close();
  }
  // Both themes must yield exactly the same composition pixels.
  assert.deepEqual(await readFile(`${output}/wide-light-export.png`), await readFile(`${output}/wide-dark-export.png`));
  assert.deepEqual(await readFile(`${output}/medium-light-export.png`), await readFile(`${output}/medium-dark-export.png`));
  assert.deepEqual(await readFile(`${output}/adaptive-light-export.png`), await readFile(`${output}/adaptive-dark-export.png`));
  await writeFile(`${output}/report.json`, JSON.stringify(reports, null, 2));
  console.log(JSON.stringify(reports));
} finally { await browser.close(); }
