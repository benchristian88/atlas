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
const browser=await chromium.launch({executablePath:process.env.ATLAS_CHROME_PATH,headless:true});
const checks=[],errors=[],calls=[];
try {
 for(const theme of ['light','dark']) for(const accent of [null,'#2563EB','#7C3AED']) {
  const context=await browser.newContext({colorScheme:theme});
  const page=await context.newPage();page.setDefaultTimeout(12000);
  page.on('pageerror',error=>errors.push(error.message));
  let currentPath='';
  await page.route('**/api/**',async route=>{
   const url=new URL(route.request().url()),path=url.pathname.replace(/^\/api/,'');
   calls.push({path,query:url.search,method:route.request().method()});
   let body=[],status=200;
   if(path==='/auth/me') { if(currentPath==='/login') {status=401;body={detail:'Not signed in'};} else body={id:id(90),email:'operator@example.test',display_name:'Acceptance operator',theme_mode:theme,accent_colour:accent,permissions,assignments:[{scope_type:'global',role_name:'Administrator',permissions}]}; }
   else if(path==='/context')body={global_access:true,customers:[customer],sites:[site]};
   else if(path==='/dashboard/summary')body={assets:1,services:1,business_functions:1,open_knowledge_gap_count:0};
   else if(path==='/assets/summary')body={total:1,by_asset_type:[{asset_type_id:type.id,asset_type_name:type.name,count:1}]};
   else if(path==='/services/summary')body={total:1,critical:0,missing_owner:1,missing_dependencies:0,missing_recovery_targets:1,incomplete:0};
   else if(path.startsWith('/operational-graph'))body=graph;
   else if(path==='/topology')body={assets:[asset],asset_types:[type],categories:[category],networks:[network],sites:[site],asset_interfaces:[],relationships:[],relationship_types:[],platform_links:[],topology_positions:[],truncated:false};
   else if(path==='/assets')body=[asset];
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
   else if(path.endsWith('/completeness'))body={summary:{completeness_status:'not_evaluated',required_total:0,required_satisfied:0},active_gaps:[],resolved_gaps:[]};
   else if(path.endsWith('/fact-history'))body={facts:{}};
   else if(path.endsWith('/knowledge-summary'))body={predicates:[],conflict_count:0,unresolved_count:0};
   await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  });
  for(const width of [1440,1024,800,390]) {
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
  await context.close();process.stdout.write(`Checked ${theme}, ${accent||'default'}: ${routes.length*4} route/viewport states\n`);
 }
 assert.deepEqual(errors,[],'No runtime exceptions');
 await writeFile(`${output}/report.json`,JSON.stringify({checks,errors,requests:calls.length},null,2));
 process.stdout.write(`PASS: ${checks.length} responsive/theme/accent route states; report: ${output}/report.json\n`);
} finally {await browser.close();}
