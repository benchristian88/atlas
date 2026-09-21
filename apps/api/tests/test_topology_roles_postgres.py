"""Real managed-reference API and authorized topology projection checks."""
import os
import uuid

import pytest
from sqlalchemy import select

from app.authorization import Principal, ScopeGrant, get_principal
from app.main import app
from app.models import Asset, AssetType, AssetRelationship
from tests.test_administration import make_principal
from tests.test_infrastructure_topology_postgres import db, client, seed_scope

pytestmark = pytest.mark.skipif(not os.getenv('ATLAS_TEST_DATABASE_URL'), reason='requires disposable migrated PostgreSQL')


def test_custom_roles_api_lifecycle_and_topology_projection(client, db):
    principal = make_principal('asset_types.view', 'asset_types.manage', 'assets.view', 'relationships.view', 'networks.view')
    principal.user.email = "topology-roles@example.test"
    db.add(principal.user)
    db.flush()
    app.dependency_overrides[get_principal] = lambda: principal
    sites, assets, _ = seed_scope(db)
    category = db.scalar(select(AssetType).where(AssetType.key == 'server')).category_id
    records=[]
    for i, (name, role) in enumerate([('Custom Edge Appliance','security_edge'),('Custom Fabric Device','aggregation_network'),('Custom Compute Engine','platform'),('Custom Runtime','workload')]):
        payload=dict(key=f'arbitrary_{i}',name=name,category_id=str(category),topology_role=role)
        response=client.post('/api/asset-types',json=payload)
        assert response.status_code==201,response.text
        record=response.json();records.append(record)
        assert record['topology_role']==role
        for invalid in (None,'invalid',60,''):
            assert client.patch(f"/api/asset-types/{record['id']}",json={'topology_role':invalid}).status_code==422
            assert client.post('/api/asset-types',json={**payload,'topology_role':invalid}).status_code==422
        assert client.patch(f"/api/asset-types/{record['id']}",json={'description':'Keep role'}).json()['topology_role']==role
    default=client.post('/api/asset-types',json=dict(key='weird',name='Weird Appliance',category_id=str(category)))
    assert default.status_code==201 and default.json()['topology_role']=='automatic'
    custom=[]
    for i,record in enumerate(records):
        asset=Asset(workspace_id=assets[0].workspace_id,customer_id=sites[0].customer_id,site_id=sites[0].id,name=f'Object {i}',asset_type=record['key'])
        db.add(asset);db.flush();custom.append(asset)
    for source,target,key in [(0,1,'connects_to'),(1,2,'connects_to'),(3,2,'runs_on')]:
        db.add(AssetRelationship(source_asset_id=custom[source].id,target_asset_id=custom[target].id,relationship_type=key,customer_id=sites[0].customer_id,site_id=sites[0].id))
    db.flush()
    graph=client.get('/api/topology/connectivity',params={'focus_asset_id':str(custom[2].id),'hops':2}).json()
    assert {n['entity_id']:n['topology_role'] for n in graph['nodes']}=={str(a.id):r['topology_role'] for a,r in zip(custom,records)}
    containment=next(e for e in graph['edges'] if e['platform_parent_key'])
    assert containment['source_key']==f'asset:{custom[3].id}' and containment['target_key']==containment['platform_parent_key']==f'asset:{custom[2].id}'
    topology=client.get('/api/topology').json()
    assert {r['key']:r['topology_role'] for r in topology['asset_types'] if r['key'].startswith('arbitrary_')}=={r['key']:r['topology_role'] for r in records}
    url=f"/api/asset-types/{records[0]['id']}"
    assert client.patch(url,json={'topology_role':'endpoint','active':False}).json()['topology_role']=='endpoint'
    assert next(r for r in client.get('/api/asset-types').json() if r['id']==records[0]['id'])['topology_role']=='endpoint'
    scoped=Principal(principal.user,(ScopeGrant(assignment_id=uuid.uuid4(),role_id=uuid.uuid4(),role_name='Site',scope_type='site',customer_id=sites[0].customer_id,site_id=sites[0].id,permissions=frozenset({'asset_types.view','asset_types.manage','assets.view','relationships.view','networks.view'})),))
    app.dependency_overrides[get_principal]=lambda:scoped
    assert client.patch(url,json={'topology_role':'platform'}).status_code==403
    assert client.post('/api/asset-types',json=dict(key='denied',name='Denied',category_id=str(category))).status_code==403
    for asset in assets[2:]:
        assert client.get('/api/topology/connectivity',params={'focus_asset_id':str(asset.id)}).status_code==404
