// AT-B03 UI regression fixtures only. No live Atlas knowledge is accessed.
// Run against a local web server; ATLAS_PLAYWRIGHT_MODULE may select an existing install.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE
  ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : "playwright");
const base = process.env.ATLAS_BROWSER_BASE_URL || "http://127.0.0.1:31484";
const output = process.env.ATLAS_BROWSER_OUTPUT || "/tmp/atlas-customer-site-deletion-browser";
await mkdir(output, { recursive: true });
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const customer = { id: id(1), name: "Fixture Customer", status: "active" };
const contextSite = { id: id(2), customer_id: customer.id, name: "Fixture Site", status: "active" };
const permissions = ["customers.view", "customers.manage", "sites.view", "sites.manage"];
const evidence = { intercepted_responses: true, checks: [], page_errors: [], requests: [], console_errors: [] };
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
try {
  for (const kind of ["Customer", "Site"]) {
    const collection = `${kind.toLowerCase()}s`;
    const rows = ["Unused", "Blocked"].map((label, index) => ({
      id: id(10 + index), name: `${label} ${kind}`, status: "active",
      ...(kind === "Site" ? { customer_id: customer.id } : {}),
    }));
    const detail = `This ${kind} can't be deleted because other records or retained history depend on it. To stop using it, set its status to Inactive.`;
    let viewer = false, loadFailure = false, deleteRequests = 0;
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on("pageerror", error => evidence.page_errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") evidence.console_errors.push(message.text()); });
    await page.route("**/api/**", async route => {
      const request = route.request(), path = new URL(request.url()).pathname;
      evidence.requests.push({ method: request.method(), path });
      let body = [], status = 200;
      if (path === "/api/setup/status") {
        body = { state: "INITIALISED", authorized: false };
      } else if (path === "/api/auth/me") {
        const effective = viewer ? permissions.filter(key => key.endsWith(".view")) : permissions;
        body = { id: id(99), display_name: "Fixture Operator", email: "fixture@example.com",
          permissions: effective, assignments: [{ scope_type: "global", permissions: effective }] };
      } else if (path === "/api/context") {
        body = { customers: [customer], sites: [contextSite], global_access: true };
      } else if (request.method() === "DELETE" && path.startsWith(`/api/${collection}/`)) {
        deleteRequests++;
        const row = rows.find(item => path.endsWith(`/${item.id}`));
        if (row.name.startsWith("Blocked")) { status = 409; body = { detail }; }
        else { rows.splice(rows.indexOf(row), 1); status = 204; body = null; }
      } else if (path === `/api/${collection}`) {
        body = rows;
        if (loadFailure) { status = 503; body = { detail: "Fixture load unavailable" }; }
      } else if (path === "/api/customers") body = [customer];
      else if (path === "/api/sites") body = [contextSite];
      const headers = { "access-control-allow-origin": new URL(base).origin,
        "access-control-allow-credentials": "true", "access-control-allow-methods": "GET,DELETE,OPTIONS",
        "access-control-allow-headers": "content-type,x-atlas-customer-id,x-atlas-site-id" };
      if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers });
      await route.fulfill({ status, headers, contentType: "application/json", body: status === 204 ? "" : JSON.stringify(body) });
    });
    await page.goto(`${base}/admin/${collection}`);
    const caption = page.locator(".table-meta [role=status]");
    await page.getByRole("row").filter({ hasText: `Unused ${kind}` }).waitFor();
    assert.equal(await caption.innerText(), "2 records");
    const unused = page.getByRole("row").filter({ hasText: `Unused ${kind}` });
    let confirmation;
    page.once("dialog", async dialog => { confirmation = dialog.message(); await dialog.dismiss(); });
    await unused.getByRole("button", { name: "Delete", exact: true }).click();
    assert.match(confirmation, new RegExp(`Delete “Unused ${kind}”`));
    assert.equal(deleteRequests, 0);
    assert.equal(await unused.count(), 1);
    page.once("dialog", dialog => dialog.accept());
    await unused.getByRole("button", { name: "Delete", exact: true }).click();
    await unused.waitFor({ state: "detached" });
    assert.equal(deleteRequests, 1);
    assert.equal(await caption.innerText(), "1 records");
    const blocked = page.getByRole("row").filter({ hasText: `Blocked ${kind}` });
    page.once("dialog", dialog => dialog.accept());
    await blocked.getByRole("button", { name: "Delete", exact: true }).click();
    await page.getByRole("alert").filter({ hasText: detail }).waitFor();
    assert.equal(await blocked.count(), 1);
    assert.equal(await caption.innerText(), "1 records");
    assert.equal(await page.getByText("Records could not be loaded.", { exact: true }).count(), 0);
    await page.screenshot({ path: `${output}/${collection}-blocked.png`, fullPage: true });

    viewer = true;
    await page.reload();
    const unavailable = page.getByRole("group", { name: "Delete unavailable", exact: true });
    await unavailable.waitFor();
    await unavailable.focus();
    assert.equal(await unavailable.evaluate(element => element === document.activeElement), true);
    const explanation = `You don't have permission to delete this ${kind}.`;
    const describedBy = await unavailable.getAttribute("aria-describedby");
    assert.equal(await page.locator(`[id="${describedBy}"]`).innerText(), explanation);
    assert.equal(await unavailable.getByRole("button", { name: "Delete", exact: true }).isDisabled(), true);
    assert.equal(await unavailable.getAttribute("title"), explanation);
    await page.screenshot({ path: `${output}/${collection}-permission.png`, fullPage: true });

    loadFailure = true;
    await page.getByRole("button", { name: "Refresh", exact: true }).click();
    await page.getByText("Records could not be loaded.", { exact: true }).waitFor();
    assert.equal(await page.getByRole("alert").first().innerText(), "Fixture load unavailable");
    assert.equal(await blocked.count(), 1);
    evidence.checks.push({ kind, confirmation_cancelled_without_request: true,
      successful_delete_removed_row: true, blocked_delete_preserved_rows_and_caption: true,
      keyboard_accessible_permission_reason: true, genuine_load_error_preserved: true });
    await page.close();
  }
  assert.deepEqual(evidence.page_errors, []);
} finally {
  if (evidence.checks.length !== 2) {
    const page = browser.contexts().flatMap(context => context.pages())[0];
    if (page) {
      evidence.failure_page_text = await page.locator("body").innerText();
      await page.screenshot({ path: `${output}/failure.png`, fullPage: true });
    }
  }
  await writeFile(`${output}/results.json`, JSON.stringify(evidence, null, 2));
  await browser.close();
}
console.log(JSON.stringify(evidence, null, 2));
