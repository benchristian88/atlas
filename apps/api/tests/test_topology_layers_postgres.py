import os
import uuid

import pytest
from sqlalchemy import select

from app.authorization import Principal, ScopeGrant, get_principal
from app.main import app
from app.models import Asset, RelationshipType
from tests.test_administration import make_principal
from tests.test_infrastructure_topology_postgres import db, client, seed_scope

pytestmark = pytest.mark.skipif(not os.getenv('ATLAS_TEST_DATABASE_URL'), reason='requires disposable migrated PostgreSQL')


def authorize(db):
    principal = make_principal('relationship_types.view', 'relationship_types.manage', 'relationships.view', 'relationships.create', 'assets.view', 'networks.view')
    principal.user.email = 'layers@example.test'
    db.add(principal.user); db.flush()
    app.dependency_overrides[get_principal] = lambda: principal
    return principal


def test_custom_type_lifecycle_api_and_connectivity(client, db):
    authorize(db)
    sites, assets, _ = seed_scope(db)
    for key, name, layer in [('connected_by_fibre', 'Connected by fibre', 'physical_network'), ('talks_to', 'Talks to', 'logical_operational'), ('paired_with', 'Paired with', None)]:
        payload = dict(key=key, name=name, source_label=name, target_label=f'Inverse {name}', directional=False, allowed_source_asset_type_keys=['server'], applicability=[dict(source_entity_type='asset', target_entity_type='asset')])
        if layer:
            payload['topology_layer'] = layer
        result = client.post('/api/relationship-types', json=payload)
        assert result.status_code == 201, result.text
        record = result.json()
        assert record['topology_layer'] == (layer or 'other')
        target = Asset(workspace_id=assets[0].workspace_id, customer_id=sites[0].customer_id, site_id=sites[0].id, name=name, asset_type='server')
        db.add(target); db.flush()
        result = client.post('/api/asset-relationships', json=dict(source_asset_id=str(assets[0].id), target_asset_id=str(target.id), relationship_type=key))
        assert result.status_code == 201, result.text
        focus = {'focus_asset_id': str(assets[0].id), 'hops': 2}
        graph = client.get('/api/topology/connectivity', params=focus).json()
        assert (str(target.id) in {n['entity_id'] for n in graph['nodes']}) == (layer == 'physical_network')
        overlay = client.get('/api/topology/connectivity', params={**focus, 'topology_layers': f'platform,physical_network,{layer or "other"}'})
        assert overlay.status_code == 200, overlay.text
        assert str(target.id) in {n['entity_id'] for n in overlay.json()['nodes']}
        edge = next(e for e in overlay.json()['edges'] if e['key'] == f"relationship:{result.json()['id']}")
        assert edge['label'] == name and edge['directional'] is False
        # Classification does not filter the shared Knowledge Graph.
        kg = client.get('/api/operational-graph', params={'focus_type': 'asset', 'focus_id': str(assets[0].id)})
        assert kg.status_code == 200, kg.text
        before_kg = kg.json()
        url = f"/api/relationship-types/{record['id']}"
        changed = client.patch(url, json={'topology_layer': 'data_resilience', 'active': False})
        assert changed.status_code == 200, changed.text
        for field in ('id', 'key', 'name', 'source_label', 'target_label', 'directional', 'allowed_source_asset_type_keys', 'applicability'):
            assert changed.json()[field] == record[field]
        assert changed.json()['topology_layer'] == 'data_resilience'
        after_kg = client.get('/api/operational-graph', params={'focus_type': 'asset', 'focus_id': str(assets[0].id)}).json()
        for graph in (before_kg, after_kg):
            graph.pop('generated_at')
        assert after_kg == before_kg
        assert next(r for r in client.get('/api/relationship-types').json() if r['id'] == record['id'])['topology_layer'] == 'data_resilience'
        for invalid in ('invalid', '', None, ['platform']):
            assert client.patch(url, json={'topology_layer': invalid}).status_code == 422
            assert client.post('/api/relationship-types', json={**payload, 'topology_layer': invalid}).status_code == 422
    focus = {'focus_asset_id': str(assets[0].id)}
    assert client.get('/api/topology/connectivity', params={**focus, 'topology_layers': 'invalid'}).status_code == 422
    empty = client.get('/api/topology/connectivity', params={**focus, 'topology_layers': ''}).json()
    assert len(empty['nodes']) == 1 and not empty['edges']


def test_layer_writes_require_global_management_and_traversal_stays_scoped(client, db):
    principal = authorize(db)
    sites, assets, _ = seed_scope(db)
    row = db.scalar(select(RelationshipType).where(RelationshipType.key == 'runs_on'))
    scoped = Principal(principal.user, (ScopeGrant(assignment_id=uuid.uuid4(), role_id=uuid.uuid4(), role_name='Site', scope_type='site', customer_id=sites[0].customer_id, site_id=sites[0].id, permissions=frozenset({'assets.view','networks.view','relationships.view','relationship_types.view','relationship_types.manage'})),))
    app.dependency_overrides[get_principal] = lambda: scoped
    assert client.patch(f'/api/relationship-types/{row.id}', json={'topology_layer':'other'}).status_code == 403
    assert client.post('/api/relationship-types', json={'key':'scoped','name':'Scoped','source_label':'Scoped','target_label':'Scoped','topology_layer':'physical_network'}).status_code == 403
    params = {'focus_asset_id':str(assets[0].id), 'hops':2, 'topology_layers':'platform,physical_network,data_resilience,logical_operational,other'}
    graph = client.get('/api/topology/connectivity', params=params)
    assert graph.status_code == 200, graph.text
    assert {n['entity_id'] for n in graph.json()['nodes'] if n['entity_type']=='asset'} == {str(a.id) for a in assets[:2]}
    for asset in assets[2:]:
        assert client.get('/api/topology/connectivity', params={**params,'focus_asset_id':str(asset.id)}).status_code == 404
