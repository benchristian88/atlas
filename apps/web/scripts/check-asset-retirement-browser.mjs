// Real browser and production UI; every API response is a synthetic fixture.
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : 'playwright');
const base = process.env.ATLAS_BROWSER_BASE_URL || 'http://127.0.0.1:3117';
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const customer = { id: id(1), name: 'Fixture customer' }, site = { id: id(2), customer_id: id(1), name: 'Fixture site' };
const permissions = ['assets.view', 'asset_types.view', 'customers.view', 'sites.view', 'networks.view', 'networks.delete', 'relationships.view'];
const active = { id: id(3), customer_id: id(1), site_id: id(2), name: 'Active fixture', asset_type: 'server', status: 'active', source: 'manual', metadata: {} };
const retired = { ...active, id: id(4), name: 'Retired fixture', status: 'retired' };
const type = { id: id(5), key: 'server', name: 'Server', category_id: id(6), active: true };
const message = 'This interface is linked to retained discovery history and cannot be deleted. If its asset is out of service, use Retire in reconciliation when available. Retirement preserves history and does not enable interface deletion.';
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
try {
  for (const width of [1440, 800]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 } });
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', dialog => dialog.accept());
    await page.route('**/api/**', async route => {
      const url = new URL(route.request().url()), path = url.pathname.replace(/^\/api/, '');
      const assets = url.searchParams.get('include_retired') === 'true' ? [active, retired] : [active];
      let body = [], status = 200;
      if (path === '/setup/status') body = { state: 'INITIALISED' };
      else if (path === '/auth/me') body = { id: id(99), display_name: 'Fixture operator', email: 'operator@example.test', permissions, assignments: [{ scope_type: 'global', permissions }] };
      else if (path === '/context') body = { global_access: true, customers: [customer], sites: [site] };
      else if (path === '/customers') body = [customer];
      else if (path === '/sites') body = [site];
      else if (path === '/asset-types') body = [type];
      else if (path === '/asset-categories') body = [{ id: id(6), name: 'Compute', key: 'compute', active: true, show_in_topology: true }];
      else if (path === '/assets/summary') body = { total: assets.length, by_asset_type: [{ asset_type_id: type.id, asset_type_name: type.name, count: assets.length }] };
      else if (path === '/assets') body = assets;
      else if (path === `/assets/${active.id}`) body = active;
      else if (path.endsWith('/knowledge-summary')) body = { groups: [], conflict_count: 0, unresolved_count: 0 };
      else if (path.endsWith('/fact-history')) body = { facts: {} };
      else if (path === '/asset-interfaces') body = [{ id: id(7), asset_id: active.id, name: 'eth0', ip_address: '192.0.2.3', is_primary: true }];
      else if (path === `/asset-interfaces/${id(7)}` && route.request().method() === 'DELETE') { status = 409; body = { detail: message }; }
      else if (path === '/topology') body = { assets, customers: [customer], sites: [site], asset_types: [type], categories: [], networks: [], asset_interfaces: [], relationships: [], relationship_types: [], platform_links: [], structural_edges: [] };
      else if (path.startsWith('/operational-graph')) body = { nodes: [], edges: [], warnings: [], focus_key: '', truncated: false };
      await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    });
    await page.goto(`${base}/assets`);
    try { await page.getByText('Active fixture', { exact: true }).first().waitFor({ timeout: 10000 }); } catch (error) { console.log(await page.locator('body').innerText(), errors, page.url()); throw error; }
    assert.equal(await page.getByText('Retired fixture', { exact: true }).count(), 0);
    await page.locator('summary').filter({ hasText: /^Filters/ }).click();
    await page.getByLabel('Include retired', { exact: true }).click();
    await page.getByText('Retired fixture', { exact: true }).first().waitFor();
    await page.getByLabel('Include retired', { exact: true }).click();
    await page.getByText('Retired fixture', { exact: true }).first().waitFor({ state: 'detached' });
    for (const [view, endpoint] of [['topology', '/api/topology'], ['knowledge-graph', '/api/operational-graph/landscape']]) {
      await page.goto(`${base}/${view}`);
      await Promise.all([
        page.waitForResponse(r => new URL(r.url()).pathname === endpoint && new URL(r.url()).searchParams.get('include_retired') === 'true'),
        page.getByLabel('Include retired', { exact: true }).check(),
      ]);
      if (view === 'topology') {
        await Promise.all([
          page.waitForResponse(r => new URL(r.url()).pathname === endpoint && new URL(r.url()).searchParams.get('include_retired') === 'false'),
          page.getByLabel('Include retired', { exact: true }).uncheck(),
        ]);
      } else {
        // Knowledge may reuse its correctly keyed default-view cache.
        await page.getByLabel('Include retired', { exact: true }).uncheck();
        assert.equal(await page.getByLabel('Include retired', { exact: true }).isChecked(), false);
      }
    }
    await page.goto(`${base}/assets/${active.id}`);
    await page.locator('.interface-row').getByRole('button', { name: 'Delete', exact: true }).click();
    await page.getByText(message, { exact: true }).waitFor();
    assert.equal(await page.locator('.interface-row').count(), 1);
    assert.deepEqual(errors, []);
    console.log(`PASS ${width}px: Asset filtering, Topology/Knowledge requests, Interface refusal`);
    await context.close();
  }
} finally { await browser.close(); }
