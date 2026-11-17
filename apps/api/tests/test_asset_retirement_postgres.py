"""AT-B01: migrated PostgreSQL, production sessions and real HTTP routes."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
import uuid

from fastapi import HTTPException
import pytest
from sqlalchemy import event, func, select

from app.authorization import ActiveContext, get_active_context, get_principal
from app.models import Asset, AssetInterface, AssetRelationship, AuditEvent, EntitySourceLink, KnowledgeAssertion
from app.routes import asset_interfaces, topology, operational_graph
from app.services.entity_resolution import ensure_asset_link, ensure_technical_link
from tests.test_reconciliation_integrity_postgres import committed, review, pytestmark
from tests.test_reconciliation_final_integrity import absence


@pytest.fixture
def inventory(committed):
    s = committed
    for router in (asset_interfaces.router, topology.router, operational_graph.router):
        s.app.include_router(router)
    s.principal = replace(s.principal, grants=(replace(s.principal.grants[0], permissions=s.principal.grants[0].permissions | {
        'assets.create', 'assets.delete', 'networks.delete', 'relationships.view', 'customers.view', 'sites.view',
        'services.view', 'business_functions.view'}),))
    s.app.dependency_overrides[get_principal] = lambda: s.principal
    return s


def test_retirement_collection_history_and_edges(inventory):
    s = inventory
    with s.session() as db:
        ensure_asset_link(db, data_source_id=s.sources[0].id, asset=db.get(Asset, s.asset.id), external_id='source-0')
        db.add(AssetRelationship(source_asset_id=s.asset.id, target_asset_id=s.other.id,
            customer_id=s.customer.id, site_id=s.site.id, relationship_type='runs_on'))
        db.commit()
    identifier, claim_id = absence(s)
    row, _ = review(s, identifier)
    assert s.client.post(f'/reconciliation-items/{identifier}/accept', json={'expected_version': row['version'], 'disposition': 'retire'}).status_code == 200
    for included in (False, True):
        query = f'include_retired={str(included).lower()}'
        listed = s.client.get(f'/assets?{query}').json()
        assert (str(s.asset.id) in [r['id'] for r in listed]) == included
        assert s.client.get(f'/assets/summary?{query}').json()['total'] == 1 + included
        assert len(s.client.get(f'/assets?search=Curated&limit=1&{query}').json()) == int(included)
        assert len(s.client.get(f'/assets?limit=1&offset=1&{query}').json()) == int(included)
        top = s.client.get(f'/topology?{query}').json()
        assert len(top['asset_interfaces']) == int(included)
        assert len(top['relationships']) == int(included)
        graph = s.client.get(f'/operational-graph?focus_type=asset&focus_id={s.other.id}&{query}').json()
        assert len(graph['nodes']) == 1 + included
        assert len(graph['edges']) == int(included)
        assert s.client.get(f'/operational-graph?focus_type=asset&focus_id={s.asset.id}&{query}').status_code == (200 if included else 404)
        assert s.client.get(f'/topology/connectivity?focus_asset_id={s.asset.id}&{query}').status_code == (200 if included else 404)
        landscape = s.client.get(f'/operational-graph/landscape?{query}').json()
        assert len(landscape['nodes']) == 1 + included
    for suffix in ('', '/fact-history', '/knowledge-summary'):
        assert s.client.get(f'/assets/{s.asset.id}{suffix}').status_code == 200
    with s.session() as db:
        assert db.get(Asset, s.asset.id).status == 'retired'
        assert db.get(KnowledgeAssertion, claim_id) is not None
        assert db.scalar(select(EntitySourceLink.id).where(EntitySourceLink.entity_id == s.asset.id))
        assert db.scalar(select(KnowledgeAssertion.value_json).where(KnowledgeAssertion.subject_id == s.asset.id,
            KnowledgeAssertion.predicate == 'status', KnowledgeAssertion.is_accepted.is_(True))) == 'retired'


@pytest.mark.parametrize('status', ['active', 'missing', 'inactive', 'unknown', 'stale'])
def test_other_statuses_remain_visible(inventory, status):
    s = inventory
    assert s.client.patch(f'/assets/{s.asset.id}', json={'status': status}).status_code == 200
    assert len(s.client.get('/assets').json()) == 2
    assert len(s.client.get('/topology').json()['assets']) == 2
    assert len(s.client.get('/operational-graph/landscape').json()['nodes']) == 2


@pytest.mark.parametrize('same_customer', [False, True])
def test_include_retired_preserves_scope(inventory, same_customer):
    s = inventory
    assert s.client.patch(f'/assets/{s.asset.id}', json={'status': 'retired'}).status_code == 200
    s.principal = replace(s.principal, grants=(replace(s.principal.grants[0], scope_type='site',
        customer_id=s.customer.id if same_customer else uuid.uuid4(), site_id=uuid.uuid4()),))
    s.app.dependency_overrides[get_active_context] = lambda: ActiveContext(None, None)
    assert s.client.get('/assets?include_retired=true').json() == []
    assert s.client.get('/assets/summary?include_retired=true').json()['total'] == 0
    assert s.client.get('/topology?include_retired=true').json()['assets'] == []
    assert s.client.get(f'/operational-graph?focus_type=asset&focus_id={s.asset.id}&include_retired=true').status_code == 404
    assert s.client.delete(f'/assets/{s.asset.id}').status_code == 404
    assert s.client.delete(f'/asset-interfaces/{s.interface.id}').status_code == 404


@pytest.mark.parametrize('disabled', [False, True])
def test_interface_source_guard_and_rollback(inventory, disabled):
    s = inventory
    with s.session() as db:
        source = db.get(type(s.sources[0]), s.sources[0].id)
        ensure_technical_link(db, source=source, target=db.get(AssetInterface, s.interface.id),
            entity_type='asset_interface', external_id='fixture/eth0', observed_at=s.interface.created_at)
        if disabled:
            source.status = 'disabled'
        db.commit()
    response = s.client.delete(f'/asset-interfaces/{s.interface.id}')
    assert response.status_code == 409
    assert 'retained discovery history' in response.json()['detail']
    assert 'fk_' not in response.text and 'fixture/eth0' not in response.text
    with s.session() as db:
        assert db.get(AssetInterface, s.interface.id)
        assert db.scalar(select(EntitySourceLink.id).where(EntitySourceLink.interface_id == s.interface.id))
        assert not db.scalar(select(AuditEvent.id).where(AuditEvent.target_id == s.interface.id, AuditEvent.event_type == 'asset_interface.deleted'))


def test_observed_asset_guard_and_manual_deletion(inventory):
    s = inventory
    with s.session() as db:
        ensure_asset_link(db, data_source_id=s.sources[0].id, asset=db.get(Asset, s.other.id), external_id='fixture/host')
        db.get(AssetInterface, s.interface.id).network_id = s.network.id
        db.commit()
    assert s.client.delete(f'/assets/{s.other.id}').status_code == 409
    assert s.client.delete(f'/asset-interfaces/{s.interface.id}').status_code == 204
    # Automatic manual declarations do not block legitimate mistake deletion.
    assert s.client.patch(f'/assets/{s.asset.id}', json={'status': 'active', 'description': 'manual'}).status_code == 200
    assert s.client.delete(f'/assets/{s.asset.id}').status_code == 204
    with s.session() as db:
        assert db.get(Asset, s.other.id)
        assert db.scalar(select(EntitySourceLink.id).where(EntitySourceLink.entity_id == s.other.id))


@pytest.mark.parametrize('first', ['link', 'delete'])
def test_concurrent_link_and_delete_are_serialized(inventory, first):
    s = inventory
    held, attempted = Event(), Event()
    def before(conn, cursor, sql, parameters, context, many):
        actor = context.execution_options.get('test_actor')
        if actor in {'link', 'delete'} and actor != first and 'FROM assets' in sql and 'FOR UPDATE' in sql:
            attempted.set()
    def after(conn, cursor, sql, parameters, context, many):
        if context.execution_options.get('test_actor') == first and 'FROM assets' in sql and 'FOR UPDATE' in sql and not held.is_set():
            held.set()
            assert attempted.wait(8)
    def link():
        with s.session() as db:
            db.connection(execution_options={'test_actor': 'link'})
            try:
                # Deliberately retain a stale object to challenge deletion-first.
                ensure_asset_link(db, data_source_id=s.sources[0].id, asset=s.other, external_id='race/host')
                db.commit()
                return 200
            except HTTPException as exc:
                db.rollback()
                return exc.status_code
    def delete():
        return s.client.delete(f'/assets/{s.other.id}', headers={'x-test-actor': 'delete'}).status_code
    event.listen(s.engine, 'before_cursor_execute', before)
    event.listen(s.engine, 'after_cursor_execute', after)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            operations = {'link': link, 'delete': delete}
            a = pool.submit(operations[first])
            assert held.wait(8)
            b = pool.submit(operations['delete' if first == 'link' else 'link'])
            results = [a.result(timeout=20), b.result(timeout=20)]
            assert results == ([200, 409] if first == 'link' else [204, 409])
    finally:
        event.remove(s.engine, 'before_cursor_execute', before)
        event.remove(s.engine, 'after_cursor_execute', after)
    with s.session() as db:
        assert (db.get(Asset, s.other.id) is not None) == (first == 'link')
        assert bool(db.scalar(select(EntitySourceLink.id).where(EntitySourceLink.entity_id == s.other.id))) == (first == 'link')
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.target_id == s.other.id,
            AuditEvent.event_type == 'asset.deleted')) == int(first == 'delete')


def test_manual_creation_artifacts_allow_deletion(inventory):
    s = inventory
    created = s.client.post('/assets', json={'customer_id': str(s.customer.id), 'site_id': str(s.site.id),
        'name': 'Unused manual mistake', 'asset_type': 'virtual_machine'})
    assert created.status_code == 201
    identifier = uuid.UUID(created.json()['id'])
    with s.session() as db:
        assert db.scalar(select(KnowledgeAssertion.id).where(KnowledgeAssertion.subject_id == identifier))
    assert s.client.delete(f'/assets/{identifier}').status_code == 204


def test_unrelated_integrity_error_is_not_labelled_discovery_history(inventory):
    """Inject an unrelated integrity error; real request rollback still runs."""
    from types import SimpleNamespace
    from sqlalchemy.exc import IntegrityError
    s = inventory
    def reject(conn, cursor, sql, parameters, context, many):
        if sql.startswith('DELETE FROM asset_interfaces'):
            raise IntegrityError(sql, {}, SimpleNamespace(diag=SimpleNamespace(constraint_name='unrelated_dependency')))
    event.listen(s.engine, 'before_cursor_execute', reject)
    try:
        response = s.client.delete(f'/asset-interfaces/{s.interface.id}')
        assert response.status_code == 409
        assert response.json()['detail'] == 'Asset interface conflicts with an existing record or dependency'
    finally:
        event.remove(s.engine, 'before_cursor_execute', reject)
    with s.session() as db:
        assert db.get(AssetInterface, s.interface.id)
        assert not db.scalar(select(AuditEvent.id).where(AuditEvent.target_id == s.interface.id,
            AuditEvent.event_type == 'asset_interface.deleted'))


def test_unknown_coverage_does_not_retire_or_create_absence(inventory):
    from datetime import datetime, timezone
    from app.models import DiscoveryRun, ReconciliationItem
    from app.services.discovery_observations import record_observed_entity, reconcile_complete_snapshot
    s = inventory
    with s.session() as db:
        ensure_asset_link(db, data_source_id=s.sources[0].id, asset=db.get(Asset, s.asset.id), external_id='coverage/guest')
        now = datetime.now(timezone.utc)
        common = dict(customer_id=s.customer.id, site_id=s.site.id, data_source_id=s.sources[0].id,
            status='completed', is_complete_snapshot=True, coverage_key='coverage', started_at=now, finished_at=now)
        baseline = DiscoveryRun(**common, completeness_status='complete')
        db.add(baseline); db.flush()
        record_observed_entity(db, run=baseline, entity_type='asset', external_id='coverage/guest',
            entity_id=s.asset.id, evidence_record_id=None, observed_at=now)
        db.commit()
        unknown = DiscoveryRun(**common, completeness_status='unknown')
        db.add(unknown); db.flush()
        result = reconcile_complete_snapshot(db, run=unknown, user_id=s.principal.user.id)
        db.commit()
        assert result.no_longer_observed_count == 0
    with s.session() as db:
        assert db.get(Asset, s.asset.id).status == 'active'
        assert not db.scalar(select(ReconciliationItem.id).where(ReconciliationItem.customer_id == s.customer.id,
            ReconciliationItem.category == 'no_longer_observed'))
