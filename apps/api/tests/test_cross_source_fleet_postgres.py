"""Permanent 34-identity AIP/HTTP regression, with committed isolated-schema state."""
import json
from dataclasses import replace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app.models import Asset,AssetInterface,AssetRelationship,Customer,DataSource,EntitySourceLink,EvidenceRecord,KnowledgeAssertion,Network,ReconciliationItem
from app.authorization import ActiveContext,get_principal,get_active_context
from app.database import get_db
from app.routes import knowledge
from app.services import aip_ingestion as aip
from app.services.entity_resolution import ensure_asset_link,ensure_technical_link
from app.services.knowledge_assertions import record_assertion,accept_assertion
from tests.test_i3_discovery import configured,new_run
from tests.i3_fixtures import message


import os,pytest
from sqlalchemy import create_engine
from app.database import SessionLocal
from tests.test_knowledge_integrity_migration import migrated_history, HEAD
pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")
@pytest.fixture
def db(migrated_history):
    migrated_history.migrate('upgrade', HEAD)
    with SessionLocal(bind=migrated_history.engine) as session:
        yield session


def test_fleet_cross_source_identity_review(db,configured):
    integration,principal,*_=configured
    principal=replace(principal,grants=(replace(principal.grants[0],permissions=principal.grants[0].permissions|{'reconciliation.view','assets.view','assets.edit','networks.view','relationships.create'}),))
    customer=db.get(Customer,integration.customer_id)
    source=DataSource(customer_id=customer.id,site_id=integration.site_id,name='Existing A',source_type='connector')
    network=Network(customer_id=customer.id,site_id=integration.site_id,name='Fleet LAN',network_type='lan')
    assets=[Asset(workspace_id=customer.workspace_id,customer_id=customer.id,site_id=integration.site_id,name=f'Fleet {i:02}',asset_type='hypervisor_node' if i==0 else 'virtual_machine',source='discovery') for i in range(34)]
    db.add_all([source,network,*assets]);db.flush()
    interfaces=[AssetInterface(asset_id=a.id,network_id=network.id,name='eth0',is_primary=False) for a in assets]
    db.add_all(interfaces);db.flush()
    ensure_technical_link(db,source=source,target=network,entity_type='network',external_id='a/lan',observed_at=assets[0].created_at)
    for i,(a,interface) in enumerate(zip(assets,interfaces)):
        ensure_asset_link(db,data_source_id=source.id,asset=a,external_id=f'a/{i}')
        ensure_technical_link(db,source=source,target=interface,entity_type='asset_interface',external_id=f'a/{i}/eth0',observed_at=a.created_at)
        claim,_=record_assertion(db,customer_id=customer.id,site_id=integration.site_id,subject_type='asset',subject_id=a.id,subject_external_id=f'a/{i}',predicate='name',value=a.name,data_source_id=source.id)
        accept_assertion(db,claim,user_id=principal.user.id)
    db.commit()
    original_ids={a.name:(a.id,it.id) for a,it in zip(assets,interfaces)}
    def payload_for(run):
        p=message(run,assets=False)
        p['assets']=[{'external_id':f'b/{i}','object_class':'i3-fixture.node' if i==0 else 'i3-fixture.qemu','name':a.name,'status':'active','facts':([] if i==0 else [{'key':'i3-fixture.tags','value_type':'string','class':'configuration','cardinality':'multi','value':[f'serial-{i}']}])} for i,a in enumerate(assets)]
        p['networks']=[{'external_id':'b/lan','object_class':'i3-fixture.network','name':'Fleet LAN','network_type':'lan','facts':[]}]
        p['interfaces']=[{'external_id':f'b/{i}/eth0','object_class':'i3-fixture.interface','name':'eth0','asset_external_id':f'b/{i}','network_external_id':'b/lan','is_primary':False,'facts':[]} for i in range(len(assets))]
        p['relationships']=[{'external_id':f'b/runs/{i}','relationship_class':'i3-fixture.runs_on','source':{'kind':'asset','external_id':f'b/{i}'},'target':{'kind':'asset','external_id':'b/0'},'truth_classification':'observed','confidence':1.0} for i in range(1,len(assets))]
        return p
    run=new_run(db,configured);p=payload_for(run)
    aip.accept_batch(db,run,p);aip.finalise(db,run,integration,message(run,completion='partial'));run.dispatch_state='settled';db.commit()
    evidence_before=db.scalar(select(func.count()).select_from(EvidenceRecord).where(EvidenceRecord.customer_id==customer.id))
    app=FastAPI();app.include_router(knowledge.router)
    def request_db():
        with SessionLocal(bind=db.get_bind()) as session:
            yield session
    app.dependency_overrides[get_db]=request_db
    app.dependency_overrides[get_principal]=lambda:principal
    app.dependency_overrides[get_active_context]=lambda:ActiveContext(customer.id,integration.site_id)
    with TestClient(app) as client:
        def group(name):
            r=client.get('/reconciliation-entities',params={'search':name,'limit':100});assert r.status_code==200,r.text
            return next(g for g in r.json()['entities'] if g['name']==name)
        def rows(g):
            return ([g['parent']] if g['parent'] else [])+[r for section in g['sections'] for r in section['items']]
        net=group('Fleet LAN')['parent']
        r=client.post(f"/reconciliation-items/{net['id']}/link-technical",json={'entity_id':str(network.id),'expected_version':net['version']});assert r.status_code==200,r.text
        for a in assets:
            parent=group(a.name)['parent'];assert parent['category']=='possible_duplicate'
            r=client.post(f"/reconciliation-items/{parent['id']}/link-asset",json={'asset_id':str(a.id),'expected_version':parent['version']});assert r.status_code==200,r.text
            row=next(r for r in rows(group(a.name)) if r['technical_identity'])
            r=client.post(f"/reconciliation-items/{row['id']}/link-technical",json={'entity_id':str(original_ids[a.name][1]),'expected_version':row['version']});assert r.status_code==200,r.text
        successes=0
        for name in ['Fleet LAN',*[a.name for a in assets]]:
            g=group(name)
            r=client.post(f"/reconciliation-entities/{g['id']}/accept",json={'items':g['decision_items']});assert r.status_code==200,r.text
            result=r.json();assert not result['failed'] and not result['blocked'],result
            successes+=len(result['accepted'])
    db.expire_all()
    assert {a.name:(a.id,db.scalar(select(AssetInterface.id).where(AssetInterface.asset_id==a.id))) for a in assets}==original_ids
    assert db.scalar(select(func.count()).select_from(Asset).where(Asset.customer_id==customer.id))==len(original_ids)
    assert db.scalar(select(func.count()).select_from(AssetInterface).join(Asset).where(Asset.customer_id==customer.id))==len(original_ids)
    assert db.scalar(select(func.count()).select_from(AssetRelationship).where(AssetRelationship.customer_id==customer.id))==len(original_ids)-1
    assert db.scalar(select(func.count()).select_from(EvidenceRecord).where(EvidenceRecord.customer_id==customer.id))==evidence_before
    second=new_run(db,configured);aip.accept_batch(db,second,payload_for(second));aip.finalise(db,second,integration,message(second,completion='partial'));db.flush()
    unresolved=db.scalar(select(func.count()).select_from(ReconciliationItem).join(KnowledgeAssertion).where(ReconciliationItem.customer_id==customer.id,ReconciliationItem.status=='open',ReconciliationItem.category.in_(['possible_duplicate','newly_discovered']),KnowledgeAssertion.data_source_id==integration.data_source_id))
    assert unresolved==0
    db.commit()
    with SessionLocal(bind=db.get_bind()) as fresh:
        persisted=list(fresh.scalars(select(Asset).where(Asset.customer_id==customer.id)))
        assert {a.name:(a.id,fresh.scalar(select(AssetInterface.id).where(AssetInterface.asset_id==a.id))) for a in persisted}==original_ids
        assert fresh.scalar(select(func.count()).select_from(EntitySourceLink).where(EntitySourceLink.customer_id==customer.id))==len(original_ids)*4+2
        assert fresh.scalar(select(func.count()).select_from(EvidenceRecord).where(EvidenceRecord.customer_id==customer.id))==evidence_before*2
    print('FLEET_PROBE',json.dumps({'verified_canonical_assets':len(original_ids),'stable_interfaces':len(interfaces),'relationships':len(original_ids)-1,'independent_reviews_accepted':successes,'retained_original_evidence':evidence_before,'repeat_identity_proposals':unresolved}))
