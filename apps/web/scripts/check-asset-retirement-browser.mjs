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
const secondActive = { ...active, id: id(8), name: 'Second active fixture' };
const type = { id: id(5), key: 'server', name: 'Server', category_id: id(6), active: true };
const category = { id: id(6), name: 'Compute', key: 'compute', active: true, show_in_topology: true };
const message = 'This interface is linked to retained discovery history and cannot be deleted. If its asset is out of service, use Retire in reconciliation when available. Retirement preserves history and does not enable interface deletion.';
const browser = await chromium.launch({ executablePath: process.env.ATLAS_CHROME_PATH, headless: true });
try {
  for (const width of [1440, 800, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 } });
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', dialog => dialog.accept());
    const firstTopology = Promise.withResolvers();
    const lateRetiredFocus = Promise.withResolvers();
    let topologyRequests = 0;
    let withConnectivity = false;
    let secondAssetRetired = false;
    await page.route('**/api/**', async route => {
      const url = new URL(route.request().url()), path = url.pathname.replace(/^\/api/, '');
      const includeRetired = url.searchParams.get('include_retired') === 'true';
      const assets = includeRetired ? [active, retired] : [active];
      const topologyAssets = withConnectivity && includeRetired ? [{ ...retired, name: 'A retired fixture' }, active] : [...assets];
      if (withConnectivity && (!secondAssetRetired || includeRetired)) {
        topologyAssets.push(secondAssetRetired ? { ...secondActive, name: 'A newly retired fixture', status: 'retired' } : secondActive);
      }
      let body = [], status = 200;
      if (path === '/setup/status') body = { state: 'INITIALISED' };
      else if (path === '/auth/me') body = { id: id(99), display_name: 'Fixture operator', email: 'operator@example.test', permissions, assignments: [{ scope_type: 'global', permissions }] };
      else if (path === '/context') body = { global_access: true, customers: [customer], sites: [site] };
      else if (path === '/customers') body = [customer];
      else if (path === '/sites') body = [site];
      else if (path === '/asset-types') body = [type];
      else if (path === '/asset-categories') body = [category];
      else if (path === '/assets/summary') body = { total: assets.length, by_asset_type: [{ asset_type_id: type.id, asset_type_name: type.name, count: assets.length }] };
      else if (path === '/assets') body = assets;
      else if (path === `/assets/${active.id}`) body = active;
      else if (path.endsWith('/knowledge-summary')) body = { groups: [], conflict_count: 0, unresolved_count: 0 };
      else if (path.endsWith('/fact-history')) body = { facts: {} };
      else if (path === '/asset-interfaces') body = [{ id: id(7), asset_id: active.id, name: 'eth0', ip_address: '192.0.2.3', is_primary: true }];
      else if (path === `/asset-interfaces/${id(7)}` && route.request().method() === 'DELETE') { status = 409; body = { detail: message }; }
      else if (path === '/topology') {
        if (++topologyRequests === 1) await firstTopology.promise;
        body = { assets: topologyAssets, customers: [customer], sites: [site], asset_types: [type], categories: withConnectivity ? [category] : [], networks: [], asset_interfaces: [], relationships: [], relationship_types: [], platform_links: [], structural_edges: [] };
      } else if (path === '/topology/connectivity') {
        const focused = topologyAssets.find(asset => asset.id === url.searchParams.get('focus_asset_id'));
        if (focused?.id === retired.id && url.searchParams.get('hops') === '2') await lateRetiredFocus.promise;
        if (!focused) { status = 404; body = { detail: 'Asset not found' }; }
        else {
          const key = `asset:${focused.id}`;
          body = { focus_key: key, nodes: [{ key, entity_type: 'asset', entity_id: focused.id, name: focused.name }], edges: [] };
        }
      }
      await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    });
    await page.goto(`${base}/assets`);
    try { await page.getByText('Active fixture', { exact: true }).first().waitFor({ timeout: 10000 }); } catch (error) { console.log(await page.locator('body').innerText(), errors, page.url()); throw error; }
    assert.equal(await page.getByText('Retired fixture', { exact: true }).count(), 0);
    const assetFilters = page.locator('.catalogue-more-filters');
    const assetRetired = assetFilters.getByLabel('Include retired', { exact: true });
    assert.equal(await assetRetired.isVisible(), false);
    assert.equal(await page.getByRole('checkbox', { name: 'Include retired', exact: true }).count(), 0);
    await assetFilters.locator('summary').click();
    assert.equal(await assetRetired.isChecked(), false);
    const includes = (path, value) => page.waitForResponse(response => {
      const url = new URL(response.url());
      return url.pathname === path && url.searchParams.get('include_retired') === String(value);
    });
    await Promise.all([includes('/api/assets', true), includes('/api/assets/summary', true), assetRetired.click()]);
    await page.getByText('Retired fixture', { exact: true }).first().waitFor();
    assert.equal(new URL(page.url()).searchParams.get('include_retired'), 'true');
    await assetRetired.click();
    await page.getByText('Retired fixture', { exact: true }).first().waitFor({ state: 'detached' });
    assert.equal(new URL(page.url()).searchParams.has('include_retired'), false);
    await page.goBack();
    await page.getByText('Retired fixture', { exact: true }).first().waitFor();
    await page.reload();
    await page.getByText('Retired fixture', { exact: true }).first().waitFor();

    await page.goto(`${base}/topology`);
    const loading = page.getByText('Loading infrastructure…', { exact: true });
    await loading.waitFor();
    const filters = page.getByRole('button', { name: /^Filters/ });
    const panel = page.locator('.topology-filter-popover');
    const topologyRetired = panel.getByRole('checkbox', { name: 'Include retired' });
    assert.equal(await page.getByRole('checkbox', { name: 'Include retired' }).count(), 0);
    await filters.click();
    assert.equal(await topologyRetired.isChecked(), false);
    assert.equal(await topologyRetired.evaluate(el => el === document.activeElement), true);
    const panelBox = await panel.boundingBox();
    assert.ok(panelBox.x >= 0 && panelBox.x + panelBox.width <= width);
    await Promise.all([includes('/api/topology', true), topologyRetired.check()]);
    firstTopology.resolve();
    await loading.waitFor({ state: 'detached' });
    assert.equal(await panel.getByRole('group', { name: 'Asset categories' }).count(), 0);
    assert.equal(await filters.innerText(), 'Filters · 1');
    await page.keyboard.press('Escape');
    for (const view of ['Platform', 'Network & VLAN', 'Overview']) {
      await page.getByRole('button', { name: view, exact: true }).click();
      await filters.click();
      assert.equal(await topologyRetired.isChecked(), true);
      assert.equal(await panel.getByRole('checkbox', { name: 'Networks' }).count(), 0);
      await page.keyboard.press('Escape');
    }
    await Promise.all([includes('/api/topology', true), page.getByRole('button', { name: 'Refresh' }).click()]);
    await filters.click();
    assert.equal(await topologyRetired.isChecked(), true);
    await Promise.all([includes('/api/topology', false), panel.getByRole('button', { name: 'Reset to defaults' }).click()]);
    assert.equal(await topologyRetired.isChecked(), false);
    assert.equal(await filters.innerText(), 'Filters');

    withConnectivity = true;
    await page.goto(`${base}/topology`);
    const button = name => page.getByRole('button', { name, exact: true });
    const focus = page.getByLabel('Focus', { exact: true });
    const matchesFocus = (request, asset, includeRetired, hops = 1) => {
      const url = new URL(request.url());
      return url.pathname === '/api/topology/connectivity' && url.searchParams.get('focus_asset_id') === asset.id &&
        !url.searchParams.has('focus_network_id') && url.searchParams.get('include_retired') === String(includeRetired) &&
        url.searchParams.get('hops') === String(hops);
    };
    const assertFocus = async asset => {
      const focusedNode = page.locator(`[data-node-key="asset:${asset.id}"].is-focus`);
      await focusedNode.waitFor();
      assert.equal(await focus.inputValue(), asset.id);
      assert.equal(await focusedNode.getAttribute('aria-pressed'), 'true');
    };
    const changeFocus = async (action, asset, includeRetired, hops) => {
      const [response] = await Promise.all([
        page.waitForResponse(response => matchesFocus(response, asset, includeRetired, hops)),
        action(),
      ]);
      assert.ok(response.ok());
      await assertFocus(asset);
    };
    await changeFocus(() => button('Connectivity').click(), active, false);
    await filters.click();
    await changeFocus(() => topologyRetired.check(), retired, true);
    await page.keyboard.press('Escape');
    await changeFocus(() => focus.selectOption(secondActive.id), secondActive, true);
    await changeFocus(() => focus.selectOption(retired.id), retired, true);
    await Promise.all([
      page.waitForRequest(request => matchesFocus(request, retired, true, 2)),
      button('2 hops').click(),
    ]);
    await filters.click();
    await changeFocus(() => topologyRetired.uncheck(), active, false, 2);
    assert.equal(await focus.locator(`option[value="${retired.id}"]`).count(), 0);
    const late = page.waitForResponse(response => matchesFocus(response, retired, true, 2));
    lateRetiredFocus.resolve();
    await (await late).finished();
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await page.locator('.topology-graph-node.is-focus').getAttribute('data-node-key'), `asset:${active.id}`);
    await changeFocus(() => topologyRetired.check(), active, true, 2);
    await page.keyboard.press('Escape');
    await changeFocus(() => focus.selectOption(retired.id), retired, true, 2);
    await filters.click();
    await changeFocus(() => button('Reset to defaults').click(), active, false, 2);
    assert.equal(await topologyRetired.isChecked(), false);
    assert.equal(await filters.innerText(), 'Filters');
    await changeFocus(() => topologyRetired.check(), active, true, 2);
    await page.keyboard.press('Escape');
    await changeFocus(() => focus.selectOption(secondActive.id), secondActive, true, 2);
    await filters.click();
    await changeFocus(() => button('Reset to defaults').click(), secondActive, false, 2);
    await changeFocus(() => topologyRetired.check(), secondActive, true, 2);
    secondAssetRetired = true;
    await changeFocus(() => topologyRetired.uncheck(), active, false, 2);
    await changeFocus(() => topologyRetired.check(), active, true, 2);

    await page.goto(`${base}/assets/${active.id}`);
    await page.locator('.interface-row').getByRole('button', { name: 'Delete', exact: true }).click();
    await page.getByText(message, { exact: true }).waitFor();
    assert.equal(await page.locator('.interface-row').count(), 1);
    assert.deepEqual(errors, []);
    console.log(`PASS ${width}px: Asset filter placement and URL history, Topology loading/empty filters, retired focus fallback and reset, Interface refusal`);
    await context.close();
  }
} finally { await browser.close(); }
