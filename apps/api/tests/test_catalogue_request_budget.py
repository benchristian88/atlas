"""Actual anonymous reader adapters; synthetic HTTP/future proofs, genuine package.

Count REST requests separately from constructed release/CDN transfers. No live
network, persistent cache, provider credential or replacement signature is used.
"""
import asyncio
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.services import catalogue_chain as chain, catalogue_source as source, trusted_catalogue as trust
from tests.test_catalogue_future import (future_http, original, approval, official_http,
    bootstrap_provider, provider, review_document, db, ingestion, SOURCE)
from tests.test_remote_connector_packages import (remote_http, remote_approval, selected,
    install_harness, payload, routes, request)
from tests.test_catalogue_source import Session, Response
from tests.test_knowledge_integrity_migration import migrated_history, HEAD
from sqlalchemy import select, func


def api_requests(http):
    return [url for url in http['requests'] if url.startswith(source.API + '/')]


def test_fresh_chain_then_genuine_remote_activation_has_40_api_requests(
        db, selected, install_harness, remote_http):
    # selected performs a real trust.refresh into fresh PostgreSQL, 1 then 2.
    assert trust.status(db)['sequence'] == 2
    refresh_count = len(api_requests(remote_http))
    principal, store, _ = install_harness
    result = asyncio.run(routes._install('proxmox', payload(selected), request(), principal, db))
    assert result['version'] == '0.2.2' and result['verification_status'] == 'verified'
    assert store.verify_connector('proxmox', '0.2.2', selected.package.bundle_digest)['state'] == 'verified'
    calls = api_requests(remote_http)
    assert refresh_count == 34
    assert len(calls) - refresh_count == 6
    assert len(calls) <= 40
    assert len(remote_http['requests']) == 68  # 40 REST + 14 release + 14 CDN GETs.
    assert calls.count(source.BASE + ingestion.CURRENT) == 4
    assert remote_http['requests'][-1] == source.BASE + ingestion.CURRENT
    assert not any('/releases/assets/' in url for url in calls)
    for path in ('/actions/runs/60', '/actions/runs/60/attempts/1'):
        assert calls.count(source.BASE + path) == 1


def test_concurrent_chain_operations_have_independent_observations_and_final_reads(future_http):
    async def run():
        return await asyncio.gather(*(chain.retrieve_chain({}, operation_id=uuid.uuid4()) for _ in range(2)))
    results = asyncio.run(run())
    assert results[0].operation_id != results[1].operation_id
    calls = Counter(api_requests(future_http))
    assert sum(calls.values()) == 68
    assert calls[source.BASE + '/branches/main'] == 2
    assert calls[source.BASE + '/actions/runs/60'] == 2
    assert calls[source.BASE + ingestion.CURRENT] == 4


@pytest.mark.skipif(not os.getenv('ATLAS_TEST_DATABASE_URL'), reason='requires disposable migrated PostgreSQL')
def test_concurrent_future_refresh_coalesces_without_sharing_reader_state(migrated_history, future_http, monkeypatch, tmp_path):
    state = migrated_history
    state.migrate('upgrade', HEAD)
    monkeypatch.setenv('ATLAS_STATE_DIR', str(tmp_path / 'state'))
    entered, resume = Event(), Event()
    retrieve = source.retrieve_candidate
    async def paused(*args, **kwargs):
        entered.set()
        assert await asyncio.to_thread(resume.wait, 20), 'test refresh was not released'
        return await retrieve(*args, **kwargs)
    monkeypatch.setattr(source, 'retrieve_candidate', paused)
    def refresh():
        with state.session() as session:
            return trust.refresh(session)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(refresh)
        try:
            assert entered.wait(20)
            second = pool.submit(refresh).result(timeout=20)
            assert second['result'] == 'in_progress'
            assert not future_http['requests']
        finally:
            resume.set()
        assert first.result(timeout=60)['result'] == 'accepted'
    assert len(api_requests(future_http)) == 34
    with state.session() as session:
        assert session.scalar(select(func.count()).select_from(trust.Revision)) == 2


def test_transient_failed_get_is_retried_once_then_reused_without_poisoning_snapshot():
    reader = chain.FutureGithubReader()
    values = [Response(status=500), Response(b'{"protected":true}')]
    reader.session = Session(lambda _: values.pop(0))
    reader.deadline = time.monotonic() + 30
    async def run():
        assert await reader.publication_metadata('/branches/main') == {'protected': True}
        assert await reader.publication_metadata('/branches/main') == {'protected': True}
        assert len(reader.session.calls) == 2
    asyncio.run(run())


@pytest.mark.parametrize('kind', ['digest', 'asset-id', 'mutable', 'source'])
def test_immutable_release_substitution_is_not_hidden_by_observation_reuse(future_http, kind):
    release = future_http['values']['/releases/tags/catalogue-000002']
    if kind == 'digest': release['assets'][0]['digest'] = 'sha256:' + 'a' * 64
    elif kind == 'asset-id': release['assets'][0]['id'] += 100
    elif kind == 'mutable': release['immutable'] = False
    else: release['target_commitish'] = 'c' * 40
    with pytest.raises(ValueError):
        asyncio.run(chain.retrieve_chain({}, operation_id=uuid.uuid4()))


def test_failed_public_observation_is_never_cached_and_results_are_not_shared_mutable_objects():
    reader = chain.FutureGithubReader()
    values = [Response(status=403), Response(b'{"created_at":"original"}')]
    reader.session = Session(lambda _: values.pop(0))
    reader.deadline = time.monotonic() + 30
    async def run():
        with pytest.raises(source.SourceError, match='source_forbidden'):
            await reader.publication_metadata('/actions/runs/60')
        assert not reader._observations
        result = await reader.publication_metadata('/actions/runs/60')
        result['created_at'] = 'tampered'
        assert await reader.publication_metadata('/actions/runs/60') == {'created_at': 'original'}
        assert len(reader.session.calls) == 2
        reader.deadline = time.monotonic() - 1
        with pytest.raises(source.SourceError, match='source_timeout'):
            await reader.publication_metadata('/actions/runs/60')
    asyncio.run(run())


def test_reader_close_and_reentry_clear_all_observations_and_asset_bindings(monkeypatch):
    values = iter([b'{"generation":1}', b'{"generation":2}'])
    async def enter(reader):
        reader.session = Session(lambda _: Response(next(values)))
        reader.deadline = time.monotonic() + 30
        return reader
    monkeypatch.setattr(source.GithubReader, '__aenter__', enter)
    reader = chain.FutureGithubReader()
    async def run():
        async with reader:
            assert await reader.publication_metadata('/branches/main') == {'generation': 1}
            reader._assets[123] = ('test-only',)
        assert not reader._observations and not reader._assets and reader._observation_bytes == 0
        async with reader:
            assert await reader.publication_metadata('/branches/main') == {'generation': 2}
    asyncio.run(run())


def test_final_current_reread_is_uncached_even_after_failed_refresh(future_http):
    future_http['after'][ingestion.CURRENT] = deepcopy(future_http['values'][ingestion.CURRENT])
    future_http['after'][ingestion.CURRENT]['object']['sha'] = 'e' * 40
    future_http['after'][ingestion.CURRENT]['object']['url'] = source.BASE + '/git/commits/' + 'e' * 40
    with pytest.raises(source.SourceError, match='channel_changed'):
        asyncio.run(chain.retrieve_chain({}, operation_id=uuid.uuid4()))
    future_http['after'].clear()
    candidate = asyncio.run(chain.retrieve_chain({}, operation_id=uuid.uuid4()))
    assert candidate.revisions[-1].selection.sequence == 2
    calls = Counter(api_requests(future_http))
    assert calls[source.BASE + '/branches/main'] == 2
    assert calls[source.BASE + ingestion.CURRENT] == 4


@pytest.mark.parametrize('kind', ['extra-entry', 'executable-mode', 'substituted-blob'])
def test_derived_git_tree_still_authenticates_exact_inventory_modes_and_bytes(future_http, kind):
    commit = future_http['values']['/git/commits/' + future_http['selection_commit']]
    pointer_path = '/contents/current.json?ref=' + future_http['selection_commit']
    if kind == 'substituted-blob':
        future_http['values'][pointer_path]['sha'] = 'a' * 40
    else:
        files = {name: ingestion.blob_sha(raw) for name, raw in [
            ('current.json', future_http['pointer']), ('current.sigstore.json', b'SYNTHETIC-SELECTION-2')]}
        if kind == 'extra-entry': files['extra'] = 'a' * 40
        tree = b''.join((b'100755 ' if kind == 'executable-mode' and name == 'current.json' else b'100644 ')
            + name.encode() + b'\0' + bytes.fromhex(sha) for name, sha in sorted(files.items()))
        sha = hashlib.sha1(b'tree ' + str(len(tree)).encode() + b'\0' + tree).hexdigest()
        commit['tree'].update(sha=sha, url=source.BASE + '/git/trees/' + sha)
    with pytest.raises(source.SourceError):
        asyncio.run(chain.retrieve_chain({}, operation_id=uuid.uuid4()))


@pytest.mark.parametrize('url', ['https://github.com/another/repo/releases/download/v1/a',
    'https://github.com/' + source.REPOSITORY + '/releases/latest/download/a',
    'https://github.com/' + source.REPOSITORY + '/releases/download/catalogue-000002/../a',
    'https://github.com/' + source.REPOSITORY + '/releases/download/catalogue-000002/a?redirect=evil'])
def test_release_download_routes_cannot_escape_fixed_official_identity(url):
    with pytest.raises(source.SourceError, match='invalid_source_destination'):
        source.checked_url(url, release_download=True)
