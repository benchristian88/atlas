// Production browser acceptance using isolated authorized API fixtures only.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { showcaseFixture, id } from "../tests/fixtures/showcase.mjs";
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const base = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:3110";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-showcase-browser";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: process.env.ATLAS_CHROME_PATH });
const permissions = ["assets.view", "relationships.view", "networks.view", "customers.view", "sites.view"];
const reports = [];
try {
  for (const [size, theme] of [["small", "light"], ["medium", "light"], ["large", "light"], ["medium", "dark"]]) {
    const data = showcaseFixture(size), site = data.sites[0], customer = data.customers[0];
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
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.goto(`${base}/topology`);
    await page.getByRole("button", { name: "Platform", exact: true }).click();
    await page.locator(".topology-platform-card").first().waitFor();
    const platformBefore = await page.locator(".topology-platform-section").allTextContents();
    await page.getByRole("button", { name: "Showcase", exact: true }).click();
    const scene = page.locator(".showcase-scene"), button = page.getByRole("button", { name: "Export PNG", exact: true });
    await scene.waitFor(); await button.waitFor();
    await page.waitForFunction(() => !document.querySelector(".showcase-actions button")?.disabled);
    assert.equal(await scene.getAttribute("viewBox"), "0 0 1920 1080");
    assert.equal(await scene.evaluate(el => getComputedStyle(el).colorScheme), "light");
    assert.equal(await scene.locator("image").count(), 2 + data.assets.filter(a => a.asset_type === "platform").length, "Logo, cached Asset icon and Type fallback images are embedded");
    // Platform was visited above; only Showcase's resource preparation is
    // constrained to one fetch per URL. Its embedded previews share that result.
    assert.ok(await scene.locator("[data-showcase-asset]").evaluateAll(tiles => tiles.every(tile => [...tile.querySelectorAll(":scope > text")].every(text => text.getComputedTextLength() <= (Number(text.getAttribute("x")) === 35 ? 89.5 : 154.5)))), "Tile labels respect fixed text budgets");
    const text = await scene.textContent();
    assert.ok(text.includes(site.name));
    for (const hidden of ["192.0.2.99", "private.example.test", "Recorded:", "Export PNG", "Cluster"]) assert.ok(!text.includes(hidden), hidden);
    for (const forbidden of ["Focus", "Filters", "Refresh", "Hide details panel", "Expand Infrastructure Topology"]) assert.equal(await page.getByRole("button", { name: forbidden, exact: true }).count(), 0);
    const geometry = await scene.evaluate(el => [...el.querySelectorAll("[data-showcase-item]")].map(n => [n.getAttribute("data-showcase-item"), n.getAttribute("transform")]));
    const countBefore = requests.length;
    await page.setViewportSize({ width: 1000, height: 900 });
    assert.deepEqual(await scene.evaluate(el => [...el.querySelectorAll("[data-showcase-item]")].map(n => [n.getAttribute("data-showcase-item"), n.getAttribute("transform")])), geometry);
    assert.equal(requests.length, countBefore);
    await page.setViewportSize({ width: 1800, height: 1200 });
    await page.screenshot({ path: `${output}/${size}-${theme}.png`, fullPage: true });
    await scene.screenshot({ path: `${output}/${size}-${theme}-scene.png` });
    if (size !== "small") {
      const media = page.locator('[data-showcase-kind="category"]').filter({ hasText: "Media & Photos" });
      assert.equal(await media.count(), 2);
      await media.first().screenshot({ path: `${output}/${size}-${theme}-host-local-category.png` });
      const ap = page.locator('[data-showcase-kind="type"]').filter({ hasText: "Wireless Access Point" });
      assert.match(await ap.textContent(), /5 devices/); assert.match(await ap.textContent(), /\+1/);
      await ap.screenshot({ path: `${output}/${size}-${theme}-wireless-group.png` });
    }
    const beforeExport = networkRequests.length;
    await context.setOffline(true);
    const downloadPromise = page.waitForEvent("download"); await button.click(); const download = await downloadPromise;
    assert.equal(download.suggestedFilename(), "the-workshop-atlas-showcase.png");
    const path = `${output}/${size}-${theme}-export.png`; await download.saveAs(path);
    const png = await readFile(path);
    assert.equal(png.subarray(1, 4).toString(), "PNG"); assert.equal(png.readUInt32BE(16), 3840); assert.equal(png.readUInt32BE(20), 2160);
    assert.equal(networkRequests.length, beforeExport, "Export makes no network requests and works offline");
    await context.setOffline(false);
    let parity;
    if (size === "medium" && theme === "light") {
      await page.setViewportSize({ width: 4300, height: 2800 });
      await page.locator(".showcase-frame").evaluate(frame => { frame.style.width = "3840px"; frame.style.border = "0"; frame.style.borderRadius = "0"; });
      const preview = await scene.screenshot({ path: `${output}/preview-at-export-resolution.png` });
      parity = await page.evaluate(async ([first, second]) => {
        const pixels = async data => {
          const image = new Image(); image.src = `data:image/png;base64,${data}`; await image.decode();
          const canvas = document.createElement("canvas"); canvas.width = 3840; canvas.height = 2160;
          const ctx = canvas.getContext("2d"); ctx.drawImage(image, 0, 0); return ctx.getImageData(0, 0, 3840, 2160).data;
        };
        const [a, b] = await Promise.all([pixels(first), pixels(second)]);
        let difference = 0, changed = 0;
        for (let i = 0; i < a.length; i += 4) {
          const delta = Math.abs(a[i] - b[i]) + Math.abs(a[i + 1] - b[i + 1]) + Math.abs(a[i + 2] - b[i + 2]);
          difference += delta; if (delta > 120) changed++;
        }
        return { meanChannelDifference: difference / (3840 * 2160 * 3), changedPixelFraction: changed / (3840 * 2160) };
      }, [preview.toString("base64"), png.toString("base64")]);
      assert.ok(parity.meanChannelDifference < 2 && parity.changedPixelFraction < .02, JSON.stringify(parity));
    }
    assert.deepEqual(errors, []);
    await page.getByRole("button", { name: "Platform", exact: true }).click();
    assert.deepEqual(await page.locator(".topology-platform-section").allTextContents(), platformBefore);
    const exported = await context.newPage(); await exported.setContent(`<img style="width:100%;height:auto" src="data:image/png;base64,${png.toString("base64")}" />`);
    await exported.locator("img").waitFor(); await exported.screenshot({ path: `${output}/${size}-${theme}-export-opened.png` });
    reports.push({ size, theme, assets: data.assets.length, dimensions: [3840, 2160], parity, errors });
    if (size === "small") {
      // No partial or empty export when the complete current-site source empties.
      data.assets = []; data.structural_edges = []; data.platform_links = [];
      await page.getByRole("button", { name: "Refresh", exact: true }).click();
      await page.locator(".topology-platform-card").first().waitFor({ state: "detached" });
      await page.getByRole("button", { name: "Showcase", exact: true }).click();
      await page.getByText("No Assets recorded for this site yet.", { exact: true }).waitFor();
      assert.equal(await page.getByRole("button", { name: "Export PNG", exact: true }).count(), 0);
    }
    await context.close();
  }
  // Both themes must yield exactly the same composition pixels.
  assert.deepEqual(await readFile(`${output}/medium-light-export.png`), await readFile(`${output}/medium-dark-export.png`));
  await writeFile(`${output}/report.json`, JSON.stringify(reports, null, 2));
  console.log(JSON.stringify(reports));
} finally { await browser.close(); }
