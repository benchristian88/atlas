import json
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError
import pytest

from app.schemas import RelationshipTypeCreate, RelationshipTypeUpdate
from app.topology_classes import DEFAULT_TOPOLOGY_CLASSES, TOPOLOGY_CLASSES
from app.services.infrastructure_topology import connectivity
from tests.test_infrastructure_topology import fixture_topology


def test_bounded_registry_defaults_and_partial_patch():
    registry = json.loads((Path(__file__).parents[2] / 'web/lib/topology-classes.json').read_text())
    assert {r['key'] for r in registry} == TOPOLOGY_CLASSES
    assert {r['key'] for r in registry if r['enabled_by_default']} == DEFAULT_TOPOLOGY_CLASSES
    payload = dict(key='paired_with', name='Paired with', source_label='Pairs with', target_label='Paired with')
    assert RelationshipTypeCreate(**payload).topology_class == 'other'
    assert 'topology_class' not in RelationshipTypeUpdate(name='Renamed').model_dump(exclude_unset=True)
    for layer in TOPOLOGY_CLASSES:
        assert RelationshipTypeCreate(**payload, topology_class=layer).topology_class == layer
    for invalid in ('unknown', 'Physical / network', '', None, ['platform']):
        with pytest.raises(ValidationError):
            RelationshipTypeCreate(**payload, topology_class=invalid)
        with pytest.raises(ValidationError):
            RelationshipTypeUpdate(topology_class=invalid)


def layered_topology():
    t = fixture_topology()
    t['assets'] = [dict(id=n, name=n, asset_type='custom') for n in ('NPM', 'PVE1', 'App', 'Authentik', 'PBS', 'Router B', 'Hidden path', 'Fibre', 'Talks', 'Paired')]
    t['asset_interfaces'] = [dict(id='nic', asset_id='NPM', network_id='n1', name='eth0', ip_address=None)]
    t['relationships'] = []
    t['relationship_types'] = []
    for key, layer, source, target in (
        ('runs_on', 'platform', 'NPM', 'PVE1'),
        ('proxies', 'logical_operational', 'NPM', 'App'),
        ('authenticates', 'logical_operational', 'NPM', 'Authentik'),
        ('backs_up_to', 'data_resilience', 'PVE1', 'PBS'),
        ('routes', 'other', 'NPM', 'Router B'),
        ('connects_to', 'physical_network', 'App', 'Hidden path'),
        ('connected_by_fibre', 'physical_network', 'PVE1', 'Fibre'),
        ('talks_to', 'logical_operational', 'NPM', 'Talks'),
        ('paired_with', 'other', 'NPM', 'Paired'),
    ):
        t['relationship_types'].append(dict(key=key, topology_class=layer, source_label=f'Configured {key}', directional=True))
        t['relationships'].append(dict(id=key, relationship_type=key, source_asset_id=source, target_asset_id=target))
    return t


def names(graph):
    return {n['name'] for n in graph['nodes']}


def test_default_paths_and_custom_physical_keep_labels_direction_and_hops():
    t = layered_topology()
    assert names(connectivity(t, 'NPM', show_networks=False)) == {'NPM', 'PVE1'}
    g = connectivity(t, 'NPM', hops=2, show_networks=False, limit=3)
    assert names(g) == {'NPM', 'PVE1', 'Fibre'}
    assert not g['truncated']  # Disabled App sorts before PVE1 but consumes no slot.
    edge = next(e for e in g['edges'] if e['key'] == 'relationship:connected_by_fibre')
    assert edge['label'] == 'Configured connected_by_fibre' and edge['directional']
    assert edge in connectivity(t, 'Fibre')['edges']  # Reverse traversal preserves semantics.


@pytest.mark.parametrize('layer, expected', [
    ('logical_operational', {'App', 'Authentik', 'Talks', 'Hidden path'}),
    ('data_resilience', {'PBS'}),
    ('other', {'Router B', 'Paired'}),
])
def test_optional_overlays_constrain_traversal(layer, expected):
    t = layered_topology()
    defaults = names(connectivity(t, 'NPM', hops=2, show_networks=False))
    graph = connectivity(t, 'NPM', hops=2, show_networks=False, topology_classes=[*DEFAULT_TOPOLOGY_CLASSES, layer])
    assert names(graph) - defaults == expected
    assert len(graph['nodes']) == len(defaults | expected)  # No inferred routing nodes.


def test_interface_membership_and_explicit_empty_selection():
    t = layered_topology()
    assert 'Management' in names(connectivity(t, 'NPM'))
    assert names(connectivity(t, 'NPM', topology_classes=['platform'])) == {'NPM', 'PVE1'}
    assert names(connectivity(t, None, focus_network_id='n1', topology_classes=[])) == {'Management'}
    assert names(connectivity(t, 'NPM', topology_classes=[])) == {'NPM'}
    assert names(connectivity(t, None, focus_network_id='n1')) == {'Management', 'NPM'}
    with pytest.raises(HTTPException) as exc:
        connectivity(t, 'NPM', topology_classes=['arbitrary'])
    assert exc.value.status_code == 422


def test_classification_is_metadata_not_english_name_or_key():
    t = layered_topology()
    for definition in t['relationship_types']:
        if definition['key'] == 'proxies':
            definition['topology_class'] = 'physical_network'
        if definition['key'] == 'runs_on':
            definition['topology_class'] = 'other'
    assert names(connectivity(t, 'NPM', show_networks=False)) == {'NPM', 'App'}
