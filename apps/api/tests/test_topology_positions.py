import uuid

from pydantic import ValidationError
import pytest

from app.schemas import AssetTypeCreate, AssetTypeUpdate, TopologyPositionCreate, TopologyPositionUpdate
from app.services.infrastructure_topology import connectivity
from tests.test_infrastructure_topology import fixture_topology


def test_fk_validation_and_patch_defaults():
    payload = dict(key='custom', name='Custom', category_id=uuid.uuid4())
    assert AssetTypeCreate(**payload).topology_position_id is None
    assert AssetTypeUpdate(name='Renamed').model_dump(exclude_unset=True) == {'name': 'Renamed'}
    position_id = uuid.uuid4()
    assert AssetTypeCreate(**payload, topology_position_id=position_id).topology_position_id == position_id
    assert AssetTypeUpdate(topology_position_id=None).model_dump(exclude_unset=True) == {'topology_position_id': None}
    for invalid in ('platform', '', 60, ['platform']):
        with pytest.raises(ValidationError):
            AssetTypeCreate(**payload, topology_position_id=invalid)
    with pytest.raises(ValidationError):
        TopologyPositionUpdate(key='mutable')
    with pytest.raises(ValidationError):
        TopologyPositionCreate(key='INVALID', name='Invalid')
    with pytest.raises(ValidationError):
        TopologyPositionUpdate(sort_order=20)


def test_metadata_cannot_change_traversal_or_canonical_direction():
    topology = fixture_topology()
    before = connectivity(topology, 'AdGuard')
    position = dict(id=str(uuid.uuid4()), key='custom', name='Any name', sort_order=900, active=False)
    for item in topology['asset_types']:
        item['topology_position'] = position
    after = connectivity(topology, 'AdGuard')
    for graph in (before, after):
        for node in graph['nodes']:
            if node['entity_type'] == 'asset':
                assert node.pop('topology_position') in (None, position)
    assert before == after
