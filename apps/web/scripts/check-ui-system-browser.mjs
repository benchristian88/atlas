// Fixture-backed UI architecture acceptance. No live API requests or records.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
const { chromium } = await import(process.env.ATLAS_PLAYWRIGHT_MODULE ? pathToFileURL(process.env.ATLAS_PLAYWRIGHT_MODULE).href : 'playwright');
const origin = process.env.ATLAS_BROWSER_BASE_URL || 'http://127.0.0.1:3125';
const output = process.env.ATLAS_BROWSER_OUTPUT || '/tmp/atlas-ui-system-browser';
await mkdir(output, { recursive: true });
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const customer = {id:id(1),name:'Home lab'}, site={id:id(2),customer_id:customer.id,name:'Home'};
const category={id:id(3),key:'compute',name:'Compute',icon_key:'server',accent_key:'teal',active:true,show_in_topology:true,sort_order:1};
const type={id:id(4),key:'host',name:'Host',active:true,category_id:category.id,category_name:category.name,topology_position_id:null};
const serviceType={id:id(5),key:'custom_service',name:'Infrastructure capability',active:true,icon_key:'database',accent_key:'purple',requires_asset_dependency:true,sort_order:1};
const criticality={id:id(6),key:'high',name:'High',rank:75,active:true};
const asset={id:id(10),name:'PVE host with a deliberately long descriptive name for layout acceptance',customer_id:customer.id,site_id:site.id,asset_type:type.key,hostname:'pve1.home.example.test',vendor:'Proxmox',model:'Home server',status:'maintenance',source:'manual',description:'Curated infrastructure supporting household services.',completeness_status:'not_evaluated',open_knowledge_gap_count:0,custom_fields:{},metadata:{}};
const service={id:id(20),name:'Household DNS',description:'Resolves internal and external names.',purpose:'Keep household name resolution available.',customer_id:customer.id,site_id:site.id,service_type_id:serviceType.id,service_type_name:serviceType.name,service_type_icon_key:serviceType.icon_key,service_type_accent_key:serviceType.accent_key,criticality_level_id:criticality.id,criticality_name:'High',operational_status:'maintenance',lifecycle_status:'active',source:'manual',asset_dependency_count:1,business_function_count:1,completeness_status:'not_evaluated'};
const bf={id:id(30),name:'Household connectivity',description:'Keep household devices connected and services discoverable.',customer_id:customer.id,site_id:site.id,active:true,service_count:1,icon_key:'home',accent_key:'teal'};
const network={id:id(40),name:'Management',customer_id:customer.id,site_id:site.id,network_type:'vlan',vlan_id:99,cidr:'10.0.99.0/24',icon_key:'network',accent_key:'cyan'};
const nodes=[[asset,'asset','/assets'],[service,'service','/services'],[bf,'business_function','/business-functions']].map(([record,kind,path])=>({...record,key:`${kind}:${record.id}`,entity_id:record.id,entity_type:kind,href:`${path}/${record.id}`,operational_state:kind==='asset'?record.status:record.operational_status,subtitle:kind==='asset'?type.name:record.service_type_name}));
const graph={nodes,edges:[{key:'service-asset:1',source_key:nodes[1].key,target_key:nodes[0].key,edge_family:'service_asset',label:'Provided by'},{key:'service-function:1',source_key:nodes[1].key,target_key:nodes[2].key,edge_family:'service_business_function',label:'Supports'}],warnings:[],truncated:false};
const permissions=['assets.view','assets.create','assets.edit','assets.delete','asset_types.view','asset_types.manage','custom_fields.view','customers.view','sites.view','networks.view','networks.create','networks.edit','networks.delete','relationships.view','relationship_types.view','services.view','services.create','services.edit','services.archive','service_types.view','service_types.manage','criticality_levels.view','business_functions.view','business_functions.manage','service_dependencies.view','knowledge_gaps.view','changes.view','reconciliation.view','integrations.view','system_settings.manage'];
const routes=['/dashboard','/assets',`/assets/${asset.id}`,'/services','/business-functions','/networks','/knowledge-graph','/topology','/admin/service-types','/profile','/login'];
const assetPath = `/assets/${asset.id}`;
const target = { ...asset, id: id(11), name: `Storage host ${'longendpoint'.repeat(7)}` };
const otherSite = { ...site, id: id(12), name: 'Other site' };
const otherSiteAsset = { ...target, id: id(13), site_id: otherSite.id, name: 'Other site asset' };
const otherCustomerAsset = { ...target, id: id(14), customer_id: id(15), name: 'Other customer asset' };
const relationshipType = { key: 'backs_up_to', name: 'Backs up to', active: true, allowed_target_asset_type_keys: [type.key] };
const edges = [
 { id: id(51), source_asset_id: asset.id, target_asset_id: target.id, target_asset_name: target.name, relationship_type: relationshipType.key, notes: 'Nightly backup on the storage host' },
 { id: id(52), source_asset_id: target.id, target_asset_id: asset.id, source_asset_name: target.name, relationship_type: relationshipType.key, notes: null },
];
const gapNames = ['Missing backup schedule', 'Missing management URL', 'Missing recovery instructions'];
const assetCompleteness = {
 summary: { completeness_status: 'incomplete', required_total: 3, required_satisfied: 1, recommended_total: 1, recommended_satisfied: 0, open_gap_count: 3, exception_count: 0 },
 active_gaps: gapNames.map((name, index) => ({
  id: id(61 + index), requirement_name: name, summary: 'Record the information used by operators during maintenance.',
  status: 'open', severity: 'high', requirement_level: index === 2 ? 'recommended' : 'required',
 })),
 resolved_gaps: [],
};
const relationshipMutations = ['relationships.create', 'relationships.delete'];
const assetOnly = process.argv.includes('--asset-detail');

async function verifyAssetLayout(page, width, theme) {
 const detail = page.locator('.entity-detail-page');
 const relationships = detail.locator('section.ops-card.entity-section', { has: page.getByRole('heading', { name: 'Relationships', exact: true }) });
 const add = relationships.locator(':scope > header').getByRole('button', { name: 'Add relationship' });
 await add.waitFor();
 assert.equal(await relationships.count(), 1);
 const legacyCards = detail.locator('section.form-card, section.table-card')
  .filter({ has: page.getByText(/^(Relationships|\d+ relationships|Add relationship)$/) });
 assert.equal(await legacyCards.count(), 0);
 assert.equal(await detail.getByRole('heading', { name: 'Knowledge completeness', exact: true }).count(), 1);
 assert.deepEqual(await detail.locator(':scope > *').evaluateAll(items => items.slice(0, 4).map(
  item => item.querySelector('h1, h2')?.textContent || item.textContent.trim(),
 )), [asset.name, 'Asset updated successfully.', 'Knowledge completeness', 'Asset details']);
 for (const name of gapNames) assert.equal(await detail.locator('.completeness-panel').getByText(name, { exact: true }).count(), 1);
 assert.equal(await relationships.getByText('2 relationships', { exact: true }).count(), 1);
 const rows = relationships.locator('.relationship-row');
 assert.deepEqual(await rows.locator(':scope > span').allTextContents(), [
  `${asset.name} → Backs up to → ${target.name} — Nightly backup on the storage host`,
  `${target.name} → Backs up to → ${asset.name}`,
 ]);
 const checkBounds = () => page.evaluate(() => {
  const fits = (element, card) => {
   const bounds = element.getBoundingClientRect();
   const parent = card.getBoundingClientRect();
   return bounds.width > 0 && bounds.left >= parent.left && bounds.right <= parent.right && bounds.right <= innerWidth;
  };
  const card = document.querySelector('.asset-relationships');
  return {
   page: document.documentElement.scrollWidth <= innerWidth,
   completeness: [...document.querySelectorAll('.completeness-panel, .completeness-panel .gap-row')].every(el => el.scrollWidth <= el.clientWidth),
   relationships: card.scrollWidth <= card.clientWidth,
   actions: [...card.querySelectorAll('button')].every(button => fits(button, card) && button.getBoundingClientRect().height >= 36),
   fields: [...card.querySelectorAll('input, select, textarea')].every(field => fits(field, card)),
  };
 });
 assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
 const expectedBounds = { page: true, completeness: true, relationships: true, actions: true, fields: true };
 assert.deepEqual(await checkBounds(), expectedBounds, `Collapsed at ${theme} ${width}px`);
 await page.screenshot({ path: `${output}/asset-detail-${theme}-${width}.png`, fullPage: true });
 await add.focus();
 assert.equal(await add.evaluate(node => getComputedStyle(node).outlineStyle), 'solid');
 await page.keyboard.press('Enter');
 const form = relationships.locator(':scope > form');
 const targetInput = form.getByRole('combobox', { name: /^Target asset/ });
 await targetInput.waitFor();
 assert.equal(await targetInput.evaluate(node => node === document.activeElement), true);
 assert.deepEqual(await targetInput.locator('option').evaluateAll(options => options.map(option => option.value)), ['', target.id]);
 assert.equal(await rows.count(), 2);
 assert.deepEqual(await checkBounds(), expectedBounds, `Expanded at ${theme} ${width}px`);
 assert.equal(await form.locator('.form-grid').evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').length), width === 390 ? 1 : 2);
 await page.keyboard.press('Tab');
 assert.equal(await form.getByRole('combobox', { name: /^Relationship type/ }).evaluate(node => node === document.activeElement), true);
 await page.screenshot({ path: `${output}/asset-relationships-expanded-${theme}-${width}.png`, fullPage: true });
 const cancel = form.getByRole('button', { name: 'Cancel' });
 await cancel.focus();
 await page.keyboard.press('Enter');
 await form.waitFor({ state: 'detached' });
 assert.equal(await add.evaluate(node => node === document.activeElement), true);
}

async function verifyRelationshipRefresh(page, fixture, mutate) {
 const card = page.locator('.asset-relationships');
 let releaseRelationships;
 fixture.waitForRelationships = new Promise(resolve => { releaseRelationships = resolve; });
 try {
  await mutate();
  await page.getByRole('status').filter({hasText:'Loading asset…'}).waitFor();
  assert.equal(await card.count(), 0);
 } finally {
  releaseRelationships();
  fixture.waitForRelationships = undefined;
 }
 await card.locator('h2:focus').waitFor();
 const heading = card.getByRole('heading', {name:'Relationships', exact:true});
 assert.equal(await heading.evaluate(node => node === document.activeElement && node.isConnected), true);
 assert.equal(await heading.getAttribute('tabindex'), '-1');
}

async function verifyAssetMutations(page, fixture, width, theme) {
 const card = page.locator('.asset-relationships');
 const add = card.getByRole('button', { name: 'Add relationship', exact: true });
 await add.click();
 const form = card.locator('form');
 const targetInput = form.getByRole('combobox', { name: /^Target asset/ });
 const relationshipInput = form.getByRole('combobox', { name: /^Relationship type/ });
 const notes = form.getByRole('textbox', { name: /^Notes/ });
 await add.click();
 assert.equal(await targetInput.evaluate(node => node.validity.valueMissing), true);
 assert.equal(await targetInput.evaluate(node => node === document.activeElement && !node.validity.valid), true);
 assert.equal(fixture.writes.length, 0);
 await targetInput.selectOption(target.id);
 await add.click();
 assert.equal(await relationshipInput.evaluate(node => node.validity.valueMissing), true);
 assert.equal(await relationshipInput.evaluate(node => node === document.activeElement && !node.validity.valid), true);
 assert.equal(fixture.writes.length, 0);
 await relationshipInput.selectOption(relationshipType.key);
 await notes.fill('Verified backup');
 fixture.rejectWrite = 500;
 const pageBanner = page.locator('.entity-detail-page > [role="alert"]');
 await add.focus();
 if (width === 390) {
  assert.equal(await page.locator('.completeness-panel').evaluate(node => node.getBoundingClientRect().bottom <= 0), true);
 }
 await page.keyboard.press('Enter');
 const unexpectedError = form.getByRole('group', {name:'Atlas could not create this relationship.'});
 await unexpectedError.waitFor();
 assert.equal(await unexpectedError.evaluate(node => node === document.activeElement), true);
 assert.equal(await page.getByText('Fixture unexpected server response.').count(), 0);
 fixture.rejectWrite = true;
 const cancel = form.getByRole('button', {name:'Cancel'});
 await page.keyboard.press('Tab');
 assert.equal(await cancel.evaluate(node => node === document.activeElement), true);
 await page.keyboard.press('Tab');
 assert.equal(await add.evaluate(node => node === document.activeElement), true);
 await page.keyboard.press('Enter');
 const summary = form.getByRole('group', {name:'Could not save relationship. Fixture relationship write rejected.'});
 await summary.waitFor();
 assert.equal(await summary.evaluate(node => {
  const {top, bottom, left, right} = node.getBoundingClientRect();
  return top >= 0 && bottom <= innerHeight && left >= 0 && right <= innerWidth;
 }), true);
 assert.equal(await summary.evaluate(node => node === document.activeElement), true);
 assert.equal(await pageBanner.count(), 0);
 assert.equal(await page.getByText('Could not save relationship. Fixture relationship write rejected.', {exact:true}).count(), 1);
 await page.screenshot({path:`${output}/asset-relationship-save-error-${theme}-${width}.png`});
 assert.equal(await targetInput.inputValue(), target.id);
 assert.equal(await relationshipInput.inputValue(), relationshipType.key);
 assert.equal(await notes.inputValue(), 'Verified backup');
 await page.keyboard.press('Shift+Tab');
 assert.equal(await notes.evaluate(node => node === document.activeElement), true);
 await notes.press('End');
 await notes.press('Space');
 assert.equal(await notes.inputValue(), 'Verified backup ');
 assert.equal(await notes.evaluate(node => node === document.activeElement), true);
 await notes.press('Backspace');
 await add.focus();
 await page.keyboard.press('Shift+Tab');
 assert.equal(await cancel.evaluate(node => node === document.activeElement), true);
 await page.keyboard.press('Enter');
 await form.waitFor({state:'detached'});
 assert.equal(await add.evaluate(node => node === document.activeElement), true);
 await page.keyboard.press('Enter');
 await form.waitFor();
 assert.equal(await summary.count(), 0);
 assert.equal(await targetInput.inputValue(), target.id);
 assert.equal(await relationshipInput.inputValue(), relationshipType.key);
 assert.equal(await notes.inputValue(), 'Verified backup');
 assert.deepEqual(await page.locator('.entity-detail-page > *').evaluateAll(items => items.slice(1, 4).map(
  item => item.querySelector('h2')?.textContent || item.textContent.trim(),
 )), ['Asset updated successfully.', 'Knowledge completeness', 'Asset details']);
 const payload = { source_asset_id: asset.id, target_asset_id: target.id, relationship_type: relationshipType.key, notes: 'Verified backup' };
 const creation = { method: 'POST', path: '/asset-relationships', payload };
 assert.deepEqual(fixture.writes, [creation, creation]);
 assert.equal(fixture.reads, 1);
 fixture.rejectWrite = false;
 await verifyRelationshipRefresh(page, fixture, async () => {
  await add.focus();
  await page.keyboard.press('Enter');
 });
 await card.getByText('3 relationships', { exact: true }).waitFor();
 await card.locator('.relationship-row').filter({hasText:'Verified backup'}).waitFor();
 assert.equal(await form.count(), 0);
 assert.equal(fixture.reads, 2);

 const remove = card.locator('.relationship-row').filter({ hasText: 'Verified backup' }).getByRole('button', { name: 'Delete' });
 let confirmation;
 const confirmDelete = (accept) => async () => {
  page.once('dialog', dialog => {
   confirmation = dialog.message();
   return accept ? dialog.accept() : dialog.dismiss();
  });
  await remove.focus();
  await page.keyboard.press('Enter');
  assert.equal(confirmation, `Delete the ${relationshipType.key} relationship?`);
 };
 await confirmDelete(false)();
 assert.equal(fixture.writes.length, 3);
 assert.equal(await remove.evaluate(node => node === document.activeElement), true);
 fixture.rejectWrite = true;
 await confirmDelete(true)();
 await pageBanner.getByText('Fixture relationship write rejected.').waitFor();
 assert.deepEqual(await page.locator('.entity-detail-page > *').evaluateAll(items => items.slice(1, 5).map(
  item => item.querySelector('h2')?.textContent || item.textContent.trim(),
 )), ['Asset updated successfully.', 'Fixture relationship write rejected.', 'Knowledge completeness', 'Asset details']);
 fixture.rejectWrite = false;
 await verifyRelationshipRefresh(page, fixture, confirmDelete(true));
 await card.getByText('2 relationships', { exact: true }).waitFor();
 assert.equal(await remove.count(), 0);
 assert.equal(await pageBanner.count(), 0);
 const deletion = { method: 'DELETE', path: `/asset-relationships/${id(53)}`, payload: null };
 assert.deepEqual(fixture.writes, [
  creation, creation, creation,
  deletion, deletion,
 ]);
 assert.equal(fixture.reads, 3);
 assert.equal(fixture.completenessReads, 3);
 fixture.rejectEvaluation = true;
 await page.getByRole('button', { name: 'Re-evaluate' }).click();
 await page.locator('.completeness-panel').getByRole('alert').getByText('Fixture evaluation rejected.').waitFor();
 assert.equal(fixture.completenessReads, 3);
 fixture.rejectEvaluation = false;
 await page.getByRole('button', { name: 'Re-evaluate' }).click();
 await page.locator('.completeness-panel').getByText('Updated backup schedule', { exact: true }).waitFor();
 assert.equal(fixture.completenessReads, 4);
 assert.equal(fixture.reads, 3);
}

const browser=await chromium.launch({executablePath:process.env.ATLAS_CHROME_PATH,headless:true});
const checks=[],assetChecks=[],errors=[],calls=[];
try {
 for(const theme of ['light','dark']) for(const accent of assetOnly ? [null] : [null,'#2563EB','#7C3AED']) {
  const context=await browser.newContext({colorScheme:theme});
  const page=await context.newPage();page.setDefaultTimeout(12000);
  page.on('pageerror',error=>errors.push(error.message));
  let currentPath='';
  let assetFixture;
  await page.route('**/api/**',async route=>{
   const url=new URL(route.request().url()),path=url.pathname.replace(/^\/api/,'');
   const method = route.request().method();
   calls.push({path,query:url.search,method});
   let body=[],status=200;
   if(path==='/setup/status')body={state:'INITIALISED'};
   else if(path==='/auth/me') {
    if(currentPath==='/login') {status=401;body={detail:'Not signed in'};}
    else {
     const grants = assetFixture?.grants || permissions;
     const assignments = assetFixture ? [
      { scope_type:'site', customer_id:customer.id, site_id:site.id, permissions:grants },
      { scope_type:'site', customer_id:customer.id, site_id:otherSite.id, permissions:relationshipMutations },
     ] : [{ scope_type:'global', role_name:'Administrator', permissions:grants }];
     body={id:id(90),email:'operator@example.test',display_name:'Acceptance operator',theme_mode:theme,accent_colour:accent,permissions:[...new Set(assignments.flatMap(assignment => assignment.permissions))],assignments};
    }
   }
   else if(path==='/context')body={global_access:true,customers:[customer],sites:[site]};
   else if(path==='/dashboard/summary')body={assets:1,non_retired_assets:1,services:1,business_functions:1,open_knowledge_gap_count:0};
   else if(path==='/assets/summary')body={total:1,by_asset_type:[{asset_type_id:type.id,asset_type_name:type.name,count:1}]};
   else if(path==='/services/summary')body={total:1,critical:0,missing_owner:1,missing_dependencies:0,missing_recovery_targets:1,incomplete:0};
   else if(path.startsWith('/operational-graph'))body=graph;
   else if(path==='/topology')body={assets:[asset],asset_types:[type],categories:[category],networks:[network],sites:[site],asset_interfaces:[],relationships:[],relationship_types:[],platform_links:[],topology_positions:[],truncated:false};
   else if(path==='/assets')body=assetFixture ? [asset, target, otherSiteAsset, otherCustomerAsset] : [asset];
   else if(path===`/assets/${asset.id}`)body=asset;
   else if(path==='/asset-types')body=[type];
   else if(path==='/asset-categories')body=[category];
   else if(path==='/service-types')body=[serviceType];
   else if(path==='/criticality-levels')body=[criticality];
   else if(path==='/services')body=[service];
   else if(path===`/services/${service.id}`)body=service;
   else if(path==='/business-functions')body=[bf];
   else if(path===`/business-functions/${bf.id}`)body=bf;
   else if(path==='/networks')body=[network];
   else if(path==='/changes')body={items:[],total:0};
   else if(path==='/dependency-analysis')body={focus:nodes[1],focus_key:nodes[1].key,results:[],warnings:[],truncated:false};
   else if(path.endsWith('/graph'))body=graph;
   else if(path===`${assetPath}/completeness` && assetFixture) {
    assetFixture.completenessReads++;
    body = assetFixture.completeness;
   }
   else if(path===`${assetPath}/evaluate-completeness` && method==='POST' && assetFixture) {
    if (assetFixture.rejectEvaluation) {
     status = 409;
     body = { detail: 'Fixture evaluation rejected.' };
    } else {
     assetFixture.completeness.active_gaps[0].requirement_name = 'Updated backup schedule';
    }
   }
   else if(path==='/relationship-types' && assetFixture) body=[relationshipType];
   else if(path==='/asset-relationships' && method==='GET' && assetFixture) {
    assert.equal(url.searchParams.get('asset_id'), asset.id);
    await assetFixture.waitForRelationships;
    assetFixture.reads++;
    body = assetFixture.edges;
   }
   else if(assetFixture && path.startsWith('/asset-relationships') && ['POST', 'DELETE'].includes(method)) {
    const payload = method === 'POST' ? route.request().postDataJSON() : null;
    assetFixture.writes.push({method,path,payload});
    if (assetFixture.rejectWrite === 500) {
     status = 500;
     body = { detail: 'Fixture unexpected server response.' };
    } else if (assetFixture.rejectWrite) {
     status = 409;
     body = { detail: 'Fixture relationship write rejected.' };
    } else if (method === 'POST') {
     status = 201;
     body = { ...payload, id: id(53) };
     assetFixture.edges.push(body);
    } else {
     assetFixture.edges = assetFixture.edges.filter(edge => !path.endsWith(edge.id));
     await route.fulfill({status:204});
     return;
    }
   }
   else if(path.endsWith('/completeness'))body={summary:{completeness_status:'not_evaluated',required_total:0,required_satisfied:0},active_gaps:[],resolved_gaps:[]};
   else if(path.endsWith('/fact-history'))body={facts:{}};
   else if(path.endsWith('/knowledge-summary'))body={predicates:[],conflict_count:0,unresolved_count:0};
   await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  });
  for(const width of assetOnly ? [] : [1440,1024,800,390]) {
   await page.setViewportSize({width,height:1000});
   for(const path of routes) {
    currentPath=path;await page.goto(origin+path);
    await page.locator('.page-header h1, #login-title').first().waitFor();
    await page.waitForTimeout(80);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${path}: ${theme} ${accent} ${width} overflow`);
    if(path!=='/login')assert.equal(await page.locator('.page-header h1').first().evaluate(n=>getComputedStyle(n).fontSize),'28px');
    assert.equal(await page.evaluate(()=>document.fonts.check('14px "Inter Variable"')),true,'Local Inter loaded');
    assert.equal(await page.locator('body').evaluate(n=>getComputedStyle(n).fontFamily.includes('Inter Variable')),true);
    assert.equal(await page.evaluate(()=>performance.getEntriesByType('resource').filter(r=>/\.woff2?/.test(r.name)).every(r=>r.name.startsWith(location.origin))),true,'Fonts served locally');
    assert.equal(await page.locator('body').innerText().then(t=>/Local development|Sample data|will be added here|Homelab Ready hardening/.test(t)),false);
    const focus=page.locator('main :is(a,button,summary,input,select):not([disabled]), .login-form input').filter({visible:true}).first();
    if(await focus.count()) {await page.keyboard.press('Tab');await focus.focus();assert.equal(await focus.evaluate(n=>getComputedStyle(n).outlineStyle),'solid',`${path} focus`);}
    if(path==='/assets') {assert.equal(await page.locator('.catalogue-row .asset-icon').count(),1);assert.equal(await page.locator('main table').count(),0);}
    if(path==='/services') {assert.equal(await page.locator('.catalogue-row [data-presentation-icon="database"]').count(),1);assert.equal(await page.locator('.catalogue-row [data-status-tone="info"]').count(),1);}
    if(path==='/business-functions')assert.equal(await page.locator('.catalogue-row [data-presentation-icon="home"]').count(),1);
    if(['/networks','/admin/service-types'].includes(path)) {assert.equal(await page.locator('table caption').count(),1);assert.equal(await page.locator('th[scope="col"]').count()>0,true);}
    if((width===1440&&theme==='light'&&accent===null)||(width===390&&theme==='dark'&&accent==='#2563EB'))await page.screenshot({path:`${output}/${path.replaceAll('/','-')||'root'}-${theme}-${width}.png`,fullPage:true});
    checks.push({path,theme,accent,width});
   }
  }
  if (!assetOnly) process.stdout.write(`Checked ${theme}, ${accent||'default'}: ${routes.length*4} route/viewport states\n`);
  if (accent === null) {
   currentPath = assetPath;
   const startAsset = async (grants, rows = edges, waitForRelationships) => {
    assetFixture = {
     grants, edges: [...rows], writes: [], reads: 0, completenessReads: 0,
     completeness: structuredClone(assetCompleteness), waitForRelationships,
    };
    await page.goto(origin + assetPath + '?updated=1');
    return assetFixture;
   };
   const operator = [...permissions, ...relationshipMutations, 'knowledge_completeness.evaluate', 'knowledge_gaps.defer', 'knowledge_gaps.exception'];
   for (const width of [1600, 1280, 900, 390]) {
    await page.setViewportSize({width,height:1000});
    const fixture = await startAsset(operator);
    await verifyAssetLayout(page, width, theme);
    assert.equal(fixture.reads, 1);
    assert.equal(fixture.completenessReads, 1);
    assetChecks.push({ theme, width, scenario: 'populated and expanded' });
    if (width === 1280 || width === 390) {
     if (width === 390) await page.setViewportSize({width, height:844});
     await verifyAssetMutations(page, fixture, width, theme);
     assetChecks.push({ theme, width, scenario: 'validation, creation, deletion, evaluation and errors' });
    }
   }
   const card = page.locator('.asset-relationships');
   let releaseRelationships;
   const loadGate = new Promise(resolve => { releaseRelationships = resolve; });
   const createOnly = await startAsset([...permissions, 'relationships.create'], [], loadGate);
   try {
    await page.getByRole('status').filter({hasText:'Loading asset…'}).waitFor();
    assert.equal(await card.count(), 0);
   } finally {
    releaseRelationships();
   }
   await card.getByText('No relationships yet.', {exact:true}).waitFor();
   assert.equal(await card.getByText('0 relationships', {exact:true}).count(), 1);
   const add = card.getByRole('button', {name:'Add relationship', exact:true});
   await add.click();
   const form = card.locator('form');
   await form.getByRole('combobox', {name:/^Target asset/}).selectOption(target.id);
   await form.getByRole('combobox', {name:/^Relationship type/}).selectOption(relationshipType.key);
   await verifyRelationshipRefresh(page, createOnly, () => add.click());
   await card.getByText('1 relationships', {exact:true}).waitFor();
   assert.equal(await form.count(), 0);
   assert.equal(await card.getByRole('button', {name:'Delete', exact:true}).count(), 0);
   assert.deepEqual(createOnly.writes, [{
    method:'POST', path:'/asset-relationships',
    payload:{source_asset_id:asset.id, target_asset_id:target.id, relationship_type:relationshipType.key, notes:null},
   }]);
   assert.equal(createOnly.reads, 2);
   assetChecks.push({ theme, width:390, scenario:'loading and empty' });
   for (const grants of [[], ['relationships.create'], ['relationships.delete']]) {
    await startAsset([...permissions, ...grants]);
    await card.getByText('2 relationships', {exact:true}).waitFor();
    assert.equal(await card.locator('.relationship-row').count(), 2);
    assert.deepEqual(await card.locator('header > *').evaluateAll(children => children.map(child => child.tagName)),
     grants.includes('relationships.create') ? ['DIV', 'BUTTON'] : ['DIV']);
    assert.equal(await card.getByRole('button', {name:'Delete', exact:true}).count(), grants.includes('relationships.delete') ? 2 : 0);
    assert.equal(await card.getByRole('heading', {name:'Relationships', exact:true}).getAttribute('tabindex'), grants.length ? '-1' : null);
    assert.equal(await page.getByRole('button', {name:'Re-evaluate'}).count(), 0);
    if (grants.length === 0) await card.screenshot({path:`${output}/asset-relationships-read-only-${theme}-390.png`});
    assetChecks.push({ theme, width:390, scenario:grants[0] || 'read-only' });
   }
   const deleteOnly = await startAsset([...permissions, 'relationships.delete'], [edges[0]]);
   const finalDelete = card.getByRole('button', {name:'Delete', exact:true});
   await finalDelete.waitFor();
   await verifyRelationshipRefresh(page, deleteOnly, async () => {
    page.once('dialog', dialog => dialog.accept());
    await finalDelete.focus();
    await page.keyboard.press('Enter');
   });
   await card.getByText('No relationships yet.', {exact:true}).waitFor();
   assert.equal(await card.getByRole('button').count(), 0);
   assert.deepEqual(deleteOnly.writes, [{method:'DELETE', path:`/asset-relationships/${edges[0].id}`, payload:null}]);
   assert.equal(deleteOnly.reads, 2);
   assetChecks.push({ theme, width:390, scenario:'delete-only restores focus after deleting the last relationship' });
   const fixture = await startAsset(permissions.filter(permission => !['relationships.view', 'knowledge_gaps.view'].includes(permission)));
   await page.getByRole('heading', {name:'Asset details', exact:true}).waitFor();
   assert.equal(await card.count(), 0);
   assert.equal(await page.locator('.completeness-panel').count(), 0);
   assert.equal(fixture.reads, 0);
   assert.equal(fixture.completenessReads, 0);
   assetChecks.push({ theme, width:390, scenario:'view denied' });
  }
  await context.close();
 }
 assert.deepEqual(errors,[],'No runtime exceptions');
 await writeFile(`${output}/report.json`,JSON.stringify({checks,assetChecks,errors,requests:calls.length},null,2));
 process.stdout.write(`PASS: ${checks.length} responsive/theme/accent route states and ${assetChecks.length} Asset detail scenarios; report: ${output}/report.json\n`);
} finally {await browser.close();}
