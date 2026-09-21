"""Managed metadata uses the real API and transactional PostgreSQL fixtures."""
import os
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.authorization import Principal, ScopeGrant, get_principal
from app.main import app
from app.models import Asset, AssetType, TopologyPosition, UNCATEGORIZED_ID
from tests.test_administration import make_principal
from tests.test_infrastructure_topology_postgres import db, client, seed_scope

pytestmark = pytest.mark.skipif(not os.getenv('ATLAS_TEST_DATABASE_URL'), reason='requires disposable migrated PostgreSQL')


def create(client, key, **kwargs):
    result = client.post('/api/topology-positions', json=dict(key=key, name=key.title(), **kwargs))
    assert result.status_code == 201, result.text
    return result.json()


def test_lifecycle_assignments_usage_and_projection(client, db):
    position = create(client, 'custom_position')
    url = f"/api/topology-positions/{position['id']}"
    assert position['asset_types_count'] == 0
    payload = dict(key='arbitrary', name='Thing One', category_id=str(UNCATEGORIZED_ID), topology_position_id=position['id'])
    result = client.post('/api/asset-types', json=payload)
    assert result.status_code == 201, result.text
    record = result.json(); type_url = f"/api/asset-types/{record['id']}"
    assert record['topology_position']['key'] == 'custom_position'
    assert client.patch(url, json={'key': 'changed'}).status_code == 422
    assert client.patch(url, json={'sort_order': 900}).status_code == 422
    assert client.delete(url).status_code == 409
    updated = client.patch(url, json={'name': 'Storage Fabric', 'description': 'Custom order', 'active': False}).json()
    assert updated['asset_types_count'] == 1 and not updated['active']
    assert position['id'] not in {p['id'] for p in client.get('/api/topology-positions?active_only=true').json()}
    assert client.patch(type_url, json={'topology_position_id': position['id']}).status_code == 200
    assert client.post('/api/asset-types', json={**payload, 'key': 'second', 'name': 'Thing Two'}).status_code == 422
    assert client.patch(type_url, json={'topology_position_id': str(uuid.uuid4())}).status_code == 422
    assert client.patch(type_url, json={'description': 'Preserve'}).json()['topology_position_id'] == position['id']
    sites, assets, _ = seed_scope(db)
    assets[0].asset_type = record['key']; db.flush()
    topology = client.get('/api/topology').json()
    assert next(t for t in topology['asset_types'] if t['id'] == record['id'])['topology_position']['name'] == 'Storage Fabric'
    graph = client.get(f'/api/topology/connectivity?focus_asset_id={assets[0].id}&category_ids={UNCATEGORIZED_ID}').json()
    assert next(n for n in graph['nodes'] if n['entity_id'] == str(assets[0].id))['topology_position']['active'] is False
    assert client.patch(url, json={'active': True}).json()['active']
    assert client.patch(type_url, json={'topology_position_id': None}).json()['topology_position'] is None
    assert client.delete(url).status_code == 204
    assert client.post('/api/topology-positions', json={'key': 'automatic', 'name': 'Automatic'}).status_code == 422
    assert client.patch(type_url, json={'topology_position_id': position['id']}).status_code == 422


def test_reorder_persists_unique_ranks_and_boundaries(client, db):
    records = [create(client, key) for key in ('a', 'b', 'c', 'd')]
    ids = {r['id'] for r in records}
    url = f"/api/topology-positions/{records[2]['id']}/move"
    def order(result):
        return [r['key'] for r in result if r['id'] in ids]
    assert order(client.post(url, json={'direction': 'up'}).json()) == ['a', 'c', 'b', 'd']
    assert order(client.post(url, json={'direction': 'up'}).json()) == ['c', 'a', 'b', 'd']
    assert order(client.get('/api/topology-positions').json()) == ['c', 'a', 'b', 'd']
    db.expire_all()
    actual = list(db.scalars(select(TopologyPosition).order_by(TopologyPosition.sort_order)))
    assert len({p.sort_order for p in actual}) == len(actual)
    for item, direction in ((actual[0], 'up'), (actual[-1], 'down')):
        before = client.get('/api/topology-positions').json()
        assert client.post(f'/api/topology-positions/{item.id}/move', json={'direction': direction}).json() == before
    assert client.post(url, json={'direction': 'sideways'}).status_code == 422


def test_global_permissions_required_for_all_writes(client):
    position = create(client, 'permission_fixture')
    url = f"/api/topology-positions/{position['id']}"
    actor = make_principal('assets.view')
    app.dependency_overrides[get_principal] = lambda: actor
    assert client.get('/api/topology-positions').status_code == 403
    grant = ScopeGrant(assignment_id=uuid.uuid4(), role_id=uuid.uuid4(), role_name='Scoped', scope_type='customer', customer_id=uuid.uuid4(), site_id=None, permissions=frozenset({'asset_types.view', 'asset_types.manage'}))
    app.dependency_overrides[get_principal] = lambda: Principal(actor.user, (grant,))
    assert client.get('/api/topology-positions').status_code == 200
    assert client.post('/api/topology-positions', json={'key': 'denied', 'name': 'Denied'}).status_code == 403
    assert client.patch(url, json={'name': 'Denied'}).status_code == 403
    assert client.post(url + '/move', json={'direction': 'up'}).status_code == 403
    assert client.delete(url).status_code == 403


def test_database_rejects_duplicate_ranks(client, db):
    first, second = create(client, 'rank_one'), create(client, 'rank_two')
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("UPDATE topology_positions SET sort_order=:rank WHERE id=:id"), dict(rank=first['sort_order'], id=second['id']))
        db.execute(text("SET CONSTRAINTS uq_topology_positions_sort_order IMMEDIATE"))


def test_reorder_flows_into_topology_without_asset_type_edits(client, db):
    first, second = create(client, 'alpha'), create(client, 'beta')
    sites, assets, _ = seed_scope(db)
    category = str(db.scalar(select(AssetType.category_id).where(AssetType.key == 'server')))
    records = []
    for index, position in enumerate((first, second)):
        result = client.post('/api/asset-types', json=dict(key=f'thing_{index}', name=f'Thing {index}', category_id=category, topology_position_id=position['id']))
        assert result.status_code == 201
        records.append(result.json())
        assets[index].asset_type = records[-1]['key']
    db.flush()
    actor = make_principal('assets.view', 'relationships.view', 'asset_types.view', 'asset_types.manage')
    actor = Principal(app.dependency_overrides[get_principal]().user, actor.grants)
    app.dependency_overrides[get_principal] = lambda: actor
    url = f'/api/topology/connectivity?focus_asset_id={assets[0].id}'
    before = client.get(url).json()
    assert client.post(f"/api/topology-positions/{second['id']}/move", json={'direction':'up'}).status_code == 200
    after = client.get(url).json()
    old_ranks = {n['entity_id']: n['topology_position']['sort_order'] for n in before['nodes']}
    new_ranks = {n['entity_id']: n['topology_position']['sort_order'] for n in after['nodes']}
    assert old_ranks[str(assets[0].id)] < old_ranks[str(assets[1].id)]
    assert new_ranks[str(assets[0].id)] > new_ranks[str(assets[1].id)]
    assert before['edges'] == after['edges']
    for record in records:
        item = db.get(AssetType, uuid.UUID(record['id']))
        assert str(item.topology_position_id) == record['topology_position_id']
