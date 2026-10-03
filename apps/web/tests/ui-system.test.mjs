import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { resolveStatus, STATUS_REGISTRY } from '../lib/status.mjs';
import { defaultEntityAccent, resolveEntityIdentity } from '../lib/entity-identity.mjs';
import { PRESENTATION_ACCENTS } from '../lib/presentation.mjs';
import { loadComponent } from './helpers/components.mjs';
const render = (file, name, props) => renderToStaticMarkup(React.createElement(loadComponent(new URL(`../components/${file}.js`, import.meta.url))[name], props));

test('status semantics are central, bounded and consistent across dot and badge adapters', () => {
  for (const [state, tone] of [['maintenance','info'], ['operational','success'], ['outage','danger'], ['degraded','warning'], ['unknown','neutral']]) {
    assert.equal(resolveStatus(state).tone, tone);
    const dot = render('operations-primitives','RecordedStatus',{state});
    const badge = render('status-badge','StatusBadge',{status:state});
    assert.ok(dot.includes(`data-status-tone="${tone}"`));
    assert.ok(badge.includes(`data-status-tone="${tone}"`));
    assert.match(dot, /Recorded status:/);
  }
  assert.equal(resolveStatus('Needs review').value, 'needs_review');
  assert.equal(resolveStatus(null).label, 'Unknown');
  assert.equal(resolveStatus('__proto__').tone, 'neutral');
  assert.equal(resolveStatus('future state').label, 'future state');
  assert.ok(Object.isFrozen(STATUS_REGISTRY));
});

test('identity inherits managed Service Type presentation and has durable safe defaults', () => {
  const type = {id:'type-1',icon_key:'database',accent_key:'purple'};
  assert.deepEqual(resolveEntityIdentity('service',{id:'dns',status:'outage'},type),{icon_key:'database',accent_key:'purple'});
  assert.deepEqual(resolveEntityIdentity('service',{service_type_id:'type-1',service_type_icon_key:'database',service_type_accent_key:'purple'}),{icon_key:'database',accent_key:'purple'});
  const base = {id:'00000000-0000-4000-8000-000000000020'};
  const first = resolveEntityIdentity('business_function',base);
  assert.deepEqual(first,resolveEntityIdentity('business_function',{...base,name:'Renamed',customer_id:'other',status:'failed'}));
  assert.equal(defaultEntityAccent(base.id), "blue");
  assert.ok(PRESENTATION_ACCENTS.includes(defaultEntityAccent(base.id)));
  assert.equal(resolveEntityIdentity('network',{icon_key:'<svg>',accent_key:'#fff'}).icon_key,'network');
  assert.equal(resolveEntityIdentity('asset',{}, {icon_key:'cloud',accent_key:'cyan'}).icon_key,'cloud');
  assert.deepEqual(resolveEntityIdentity("asset", {entity_id:"a", icon_key:"cloud", accent_key:"rose"}), {icon_key:"cloud", accent_key:"rose"});
  assert.equal(resolveEntityIdentity('business_function').icon_key,'home');
});

test('PageHeader renders one heading and optional context, identity and actions safely', () => {
  const html=render('page-header','PageHeader',{title:'A long <entity>',actions:React.createElement('button',null,'Add'),metadata:'Site A',variant:'canvas'});
  assert.equal((html.match(/<h1>/g)||[]).length,1);
  assert.match(html,/A long &lt;entity&gt;/);
  assert.match(html,/page-header-canvas/);
  assert.match(html,/page-header-actions/);
  assert.doesNotMatch(html,/page-description|eyebrow/);
  assert.doesNotMatch(render("page-header","PageHeader",{title:"Read only",actions:React.createElement(React.Fragment,null,false)}),/page-header-actions/);
});

test('Buttons default to non-submit and expose loading/disabled and icon names', () => {
  const html=render('button','Button',{loading:true,variant:'primary',children:'Saving'});
  assert.match(html,/type="button"/);assert.match(html,/disabled/);assert.match(html,/aria-busy="true"/);
  const link=render('button','Button',{href:'/assets',disabled:true,children:'Assets'});
  assert.match(link,/aria-disabled="true"/);assert.match(link,/tabindex="-1"/);
  assert.match(render('button','IconButton',{label:'Close form',icon:'close'}),/aria-label="Close form"/);
  assert.throws(()=>render('button','IconButton',{icon:'close'}),/requires an accessible label/);
});

test('DataTable preserves zero/false, renderer context, captions, states and actions', () => {
  const columns=[{key:'count',label:'Count'},{key:'active',label:'Active',render:(row,related,index)=>`${row.active}:${related.name}:${index}`}];
  const html=render('data-table','DataTable',{label:'Types',columns,rows:[{id:'1',count:0,active:false}],related:{name:'Type'},actions:row=>React.createElement('button',null,`Edit ${row.id}`)});
  for(const expected of ['<caption','scope="col"','>0<','false:Type:0','Edit 1','role="region"','tabindex="0"'])assert.ok(html.includes(expected),expected);
  assert.doesNotMatch(html,/Sample/);
  for(const [props,text] of [[{loading:true},'Loading…'],[{error:'Unavailable'},'role="alert"'],[{empty:'No types'},'No types']])assert.ok(render('data-table','DataTable',{label:'Types',columns,...props}).includes(text));
});

test('Assets use the shared identity-rich linked row without nesting action controls in links', () => {
  const html=render('entity-catalogue','AssetCatalogueRow',{asset:{id:'a',name:'Server',status:'maintenance',hostname:'pve1'},assetType:{name:'Host',icon_key:'server'},actions:React.createElement('button',null,'Delete')});
  assert.match(html,/href="\/assets\/a"/);assert.match(html,/entity-identity/);assert.match(html,/asset-icon/);
  assert.match(html,/Maintenance/);assert.match(html,/pve1/);
  assert.ok(html.indexOf('</a>')<html.indexOf('>Delete</button>'));
});
