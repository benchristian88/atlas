import json
from pathlib import Path
import uuid

from pydantic import ValidationError
import pytest

from app.schemas import AssetTypeCreate, AssetTypeUpdate
from app.topology_roles import TOPOLOGY_ROLES
from app.services.infrastructure_topology import connectivity
from tests.test_infrastructure_topology import fixture_topology


def test_registry_validation_and_patch_defaults():
    registry = json.loads((Path(__file__).parents[2] / 'web/lib/topology-roles.json').read_text())
    assert {r['key'] for r in registry} == TOPOLOGY_ROLES
    payload = dict(key='custom', name='Custom', category_id=uuid.uuid4())
    assert AssetTypeCreate(**payload).topology_role == 'automatic'
    assert AssetTypeUpdate(name='Renamed').model_dump(exclude_unset=True) == {'name': 'Renamed'}
    for role in TOPOLOGY_ROLES:
        assert AssetTypeCreate(**payload, topology_role=role).topology_role == role
    for invalid in ('platform_host', 'Platform / host', '', None, 60, ['platform']):
        with pytest.raises(ValidationError):
            AssetTypeCreate(**payload, topology_role=invalid)
        with pytest.raises(ValidationError):
            AssetTypeUpdate(topology_role=invalid)


def test_metadata_is_additive_and_cannot_change_traversal_or_canonical_direction():
    topology = fixture_topology()
    before = connectivity(topology, 'AdGuard')
    for item in topology['asset_types']:
        item['topology_role'] = 'security_edge'
    after = connectivity(topology, 'AdGuard')
    for graph in (before, after):
        for n in graph['nodes']:
            if n['entity_type'] == 'asset':
                assert n.pop('topology_role') in ('automatic', 'security_edge')
    assert before == after
    for edge in after['edges']:
        if edge['key'].startswith('relationship:'):
            assert edge['topology_layer'] in ('platform', 'physical_network')
            if edge['platform_parent_key']:
                assert edge['platform_parent_key'] in (edge['source_key'], edge['target_key'])
