"""Synthetic future-provider policy tests plus genuine existing crypto fixtures.

Future-only cryptography is mocked at verifier output; it is never represented as
real signing acceptance. Bootstrap and published package paths use actual crypto.
"""
import asyncio
import base64
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from pathlib import Path
import time
import uuid

import pytest
from sqlalchemy import select, func

from app.services import catalogue_future_authorization as future, catalogue_chain as chain
from app.services import catalogue_source as source, official_catalogue_ingestion as ingestion, trusted_catalogue as trust
from app.services.catalogue_trust import BOOTSTRAP_POLICY_PROPOSAL
from app.services.catalogue_publication_evidence import PublicObservationReviewExpectations
from app.services.connector_verification import GithubSigstoreVerifier
from app.services.official_provenance import VerifiedTimestamp, PackageArtifactContext
from tests.test_official_catalogue_ingestion import official_http, PINS, POINTER, SELECTION_BUNDLE
from tests.test_catalogue_bootstrap_authorization import bootstrap_provider
from tests.test_catalogue_publication_evidence import provider, review_document
from tests.test_catalogue_source import Response, Session, RAW, BUNDLE
from tests.test_trusted_catalogue import db, allow_attempt

FIXTURE = Path(__file__).parent / 'fixtures/future_publication'
LOCAL = Path(__file__).parent / 'fixtures/local_release'
ORIGINAL = (FIXTURE / 'preflight.json').read_bytes()
POLICY = (FIXTURE / 'policy.json').read_bytes()
VERIFIED = json.loads((FIXTURE / 'verified-output.json').read_bytes())
VALUE = json.loads(ORIGINAL)
SOURCE = VALUE['source']['commit']
ISSUED = VALUE['freshness']['issued_at']


def stamp(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc)


@pytest.fixture
def approval(monkeypatch):
    policy = future.FuturePublicationPolicy(
        PublicObservationReviewExpectations(replace(BOOTSTRAP_POLICY_PROPOSAL.consumer_review, reviewed_producer_revision=VALUE['source']['verifier_revision']), 80, BOOTSTRAP_POLICY_PROPOSAL.rulesets),
        VALUE['source']['verifier_revision'], hashlib.sha256(POLICY).hexdigest(), 25016263801, 900, 300,
        'SYNTHETIC TEST DECISION ONLY', 'SYNTHETIC TEST BINDING ONLY', 'disabled-pending-permanent-archive-decision')
    monkeypatch.setattr(future, 'APPROVED_FUTURE_POLICY', policy)
    monkeypatch.setattr(future, 'APPROVED_FUTURE_POLICY_SHA256', hashlib.sha256(ingestion.canonical(asdict(policy))).hexdigest())
    return policy


@pytest.fixture
def original(monkeypatch, approval):
    root_proof = GithubSigstoreVerifier().verify_selection(POINTER, SELECTION_BUNDLE)
    selected = replace(root_proof, source_commit=SOURCE,
        invocation_uri=source.REPOSITORY.replace('benchristian88/', 'https://github.com/benchristian88/') + '/actions/runs/60/attempts/1',
        witnessed_at=(VerifiedTimestamp('Tlog', 'https://rekor.sigstore.dev', stamp(ISSUED + 100)),))
    monkeypatch.setattr(future, '_verified_output', lambda *a, **kw: deepcopy(VERIFIED))
    return {'preflight.json': ORIGINAL, 'preflight.sigstore.json': b'SYNTHETIC-NOT-A-SIGNATURE', 'policy.json': POLICY}, selected


def test_no_downloaded_or_environment_approval(monkeypatch):
    monkeypatch.setenv('APPROVED_FUTURE_POLICY_SHA256', 'a' * 64)
    with pytest.raises(source.SourceError, match='owner_approval_required'):
        future.approved_future_policy()
    with pytest.raises(source.SourceError, match='owner_approval_required'):
        future.authenticate_original({'policy.json': POLICY}, None, published_at='2026-11-04T00:00:00Z')


def test_original_authenticated_profile_and_historical_binding(original):
    files, proof = original
    assert future.authenticate_original(files, proof, published_at=stamp(ISSUED + 200).isoformat()) == VALUE


@pytest.mark.parametrize('field', ['issuer', 'buildSignerDigest', 'sourceRepositoryIdentifier', 'sourceRepositoryOwnerIdentifier',
    'sourceRepositoryDigest', 'sourceRepositoryRef', 'sourceRepositoryVisibilityAtSigning', 'runnerEnvironment',
    'buildConfigURI', 'buildConfigDigest', 'buildTrigger', 'runInvocationURI', 'subjectAlternativeName', 'buildSignerURI'])
def test_wrong_authenticated_certificate_rejected(original, monkeypatch, field):
    output = deepcopy(VERIFIED)
    output[0]['verificationResult']['signature']['certificate'][field] = 'attacker'
    monkeypatch.setattr(future, '_verified_output', lambda *a, **kw: output)
    with pytest.raises(source.SourceError):
        future.authenticate_original(*original, published_at=stamp(ISSUED + 200).isoformat())


@pytest.mark.parametrize('kind', ['policy', 'actor', 'attempt', 'source', 'bypass', 'missing-bypass', 'digest', 'operation', 'acceptance', 'order'])
def test_original_context_tampering_rejected(original, kind):
    files, proof = original
    files = dict(files); value = deepcopy(VALUE)
    if kind == 'policy': files['policy.json'] += b'\n'
    elif kind == 'actor': value['security']['run']['actor']['id'] += 1
    elif kind == 'attempt': value['execution']['run_attempt'] = 2
    elif kind == 'source': value['source']['commit'] = 'd' * 40
    elif kind == 'bypass': value['rulesets']['observations'][0]['bypass_actors'] = [{'actor_id': 1}]
    elif kind == 'missing-bypass': del value['rulesets']['observations'][0]['bypass_actors']
    elif kind == 'digest': value['source']['policy_sha256'] = 'd' * 64
    elif kind == 'operation': value['execution']['operation'] = 'recover'
    elif kind == 'acceptance': value['execution']['acceptance_only'] = True
    elif kind == 'order': value['freshness']['observation_started'] = value['freshness']['expires_at']
    files['preflight.json'] = ingestion.canonical(value)
    with pytest.raises(ValueError):
        future.authenticate_original(files, proof, published_at=stamp(ISSUED + 200).isoformat())


@pytest.mark.parametrize('kind', ['early-log', 'expired-log', 'no-log', 'wrong-log', 'early-selection', 'late-selection', 'early-release', 'late-release', 'missing-release'])
def test_historical_time_fail_closed(original, monkeypatch, kind):
    files, proof = original; output = deepcopy(VERIFIED); published = stamp(ISSUED + 200).isoformat()
    if kind in ('early-log', 'expired-log'):
        output[0]['verificationResult']['verifiedTimestamps'][0]['timestamp'] = stamp(ISSUED - 1 if kind == 'early-log' else ISSUED + 901).isoformat()
    elif kind == 'no-log': output[0]['verificationResult']['verifiedTimestamps'] = []
    elif kind == 'wrong-log': output[0]['verificationResult']['verifiedTimestamps'][0]['uri'] = 'https://attacker.invalid'
    elif kind in ('early-selection', 'late-selection'):
        proof = replace(proof, witnessed_at=(VerifiedTimestamp('Tlog', 'https://rekor.sigstore.dev', stamp(ISSUED if kind == 'early-selection' else ISSUED + 901)),))
    elif kind == 'early-release': published = stamp(ISSUED + 99).isoformat()
    elif kind == 'late-release': published = stamp(ISSUED + 401).isoformat()
    else: published = None
    monkeypatch.setattr(future, '_verified_output', lambda *a, **kw: output)
    with pytest.raises(source.SourceError):
        future.authenticate_original(files, proof, published_at=published)


@pytest.fixture
def future_http(official_http, original, monkeypatch):
    files, future_proof = original
    values = official_http['values']
    commit = 'd' * 40
    document = json.loads(RAW); document['sequence'] = 2; document['entries'][0]['status'] = 'withdrawn'
    manifest = json.loads((LOCAL / 'manifest.json').read_bytes())
    document['entries'].append({'status': 'active', 'release_tag': 'proxmox-v0.2.2', 'release_asset_id': 693849044, 'manifest': manifest})
    catalogue = ingestion.canonical(document)
    pointer = ingestion.canonical({'schema_version': '1.0', 'sequence': 2, 'release_tag': 'catalogue-000002',
        'release_id': 902, 'asset_id': 903, 'sha256': hashlib.sha256(catalogue).hexdigest(),
        'previous_pointer_sha256': hashlib.sha256(POINTER).hexdigest()})
    bundle = b'SYNTHETIC-SELECTION-2'
    blobs = {name: ingestion.blob_sha(raw) for name, raw in [('current.json', pointer), ('current.sigstore.json', bundle)]}
    tree_raw = b''.join(b'100644 ' + n.encode() + b'\0' + bytes.fromhex(sha) for n, sha in sorted(blobs.items()))
    tree_sha = hashlib.sha1(b'tree ' + str(len(tree_raw)).encode() + b'\0' + tree_raw).hexdigest()
    def obj(sha, kind): return {'sha': sha, 'type': kind, 'url': f'{source.BASE}/git/{kind}s/{sha}'}
    values[ingestion.CURRENT]['object'] = obj(commit, 'commit')
    values[f'/git/commits/{commit}'] = {'sha': commit, 'url': f'{source.BASE}/git/commits/{commit}',
        'parents': [{'sha': PINS.root_commit, 'url': f'{source.BASE}/git/commits/{PINS.root_commit}'}], 'tree': obj(tree_sha, 'tree')}
    values[f'/git/trees/{tree_sha}'] = {'sha': tree_sha, 'url': f'{source.BASE}/git/trees/{tree_sha}', 'truncated': False,
        'tree': [{'path': n, 'type': 'blob', 'mode': '100644', 'sha': sha, 'url': f'{source.BASE}/git/blobs/{sha}'} for n, sha in blobs.items()]}
    for name, raw in [('current.json', pointer), ('current.sigstore.json', bundle)]:
        path = f'/contents/{name}?ref={commit}'
        values[path] = {'name': name, 'path': name, 'type': 'file', 'sha': blobs[name], 'size': len(raw), 'encoding': 'base64',
            'content': base64.b64encode(raw).decode(), 'url': source.BASE + path}
    actor = {'id': 346232650, 'login': 'atlas-catalogue-publisher[bot]', 'type': 'Bot'}
    release = {'id': 902, 'tag_name': 'catalogue-000002', 'url': source.BASE + '/releases/902',
        'html_url': 'https://github.com/' + source.REPOSITORY + '/releases/tag/catalogue-000002', 'draft': False,
        'prerelease': False, 'immutable': True, 'target_commitish': SOURCE, 'published_at': stamp(ISSUED + 200).isoformat(),
        'assets': [], 'author': actor}
    data = {'catalogue-000002.json': catalogue, 'catalogue.sigstore.json': b'SYNTHETIC-CATALOGUE-2',
            'current.json': pointer, 'current.sigstore.json': bundle, **files}
    for identifier, (name, raw) in enumerate(data.items(), 903):
        release['assets'].append({'id': identifier, 'name': name, 'size': len(raw), 'state': 'uploaded',
            'url': f'{source.BASE}/releases/assets/{identifier}', 'digest': 'sha256:' + hashlib.sha256(raw).hexdigest(),
            'browser_download_url': f'https://github.com/{source.REPOSITORY}/releases/download/catalogue-000002/{name}', 'uploader': actor})
        values[f'/releases/assets/{identifier}'] = raw
    values['/releases/902'] = release; values['/releases/tags/catalogue-000002'] = deepcopy(release)
    path = '/git/ref/tags/catalogue-000002'
    values[path] = {'ref': 'refs/tags/catalogue-000002', 'url': source.BASE + path.replace('/ref/', '/refs/'), 'object': obj(SOURCE, 'commit')}
    security = VALUE['security']
    for name, path in [('run', '/actions/runs/60'), ('attempt', '/actions/runs/60/attempts/1'), ('workflow', '/actions/workflows/80'),
        ('user', '/users/benchristian88'), ('checks', f'/commits/{SOURCE}/check-runs?check_name=validate&filter=latest&per_page=2&page=1')]:
        values[path] = deepcopy(security[name])
    verify_selection, verify_catalogue = GithubSigstoreVerifier.verify_selection, GithubSigstoreVerifier.verify_catalogue
    def selection(self, raw, signed):
        if raw == pointer and signed == bundle:
            return replace(future_proof, artifact_sha256=hashlib.sha256(pointer).hexdigest())
        return verify_selection(self, raw, signed)
    def build(self, raw, signed, **kw):
        if raw == catalogue and signed == data['catalogue.sigstore.json']:
            genuine = verify_catalogue(self, RAW, BUNDLE, subject_name='catalogue-000001.json')
            return replace(genuine, artifact_sha256=hashlib.sha256(raw).hexdigest(), subject_name='catalogue-000002.json', source_commit=SOURCE)
        return verify_catalogue(self, raw, signed, **kw)
    monkeypatch.setattr(GithubSigstoreVerifier, 'verify_selection', selection)
    monkeypatch.setattr(GithubSigstoreVerifier, 'verify_catalogue', build)
    # Keep the production reader/get/redirect/digest adapters intact. Only the
    # HTTP session is synthetic; every actual API and distribution GET is counted.
    enter = source.GithubReader.__aenter__
    official_http['requests'] = []
    async def release_enter(reader):
        await enter(reader)
        respond = reader.session.respond
        def route(url):
            official_http['requests'].append(url)
            failure = official_http.get('http_failures', {}).get(url)
            if failure is not None:
                return failure
            prefix = f'https://github.com/{source.REPOSITORY}/releases/download/'
            if url.startswith(prefix):
                tag, name = url.removeprefix(prefix).split('/')
                matches = {a['id'] for path, value in values.items() if re.fullmatch(r'/releases/[0-9]+', path)
                    and type(value) is dict
                    and value.get('tag_name') == tag for a in value.get('assets', []) if a['name'] == name}
                assert len(matches) == 1, 'Ambiguous fixture asset'
                identifier, = matches
                return Response(status=302, headers={'Location': f'https://release-assets.githubusercontent.com/{identifier}'})
            if url.startswith('https://release-assets.githubusercontent.com/'):
                identifier = int(url.rsplit('/', 1)[1])
                path = f'/releases/assets/{identifier}'
                raw = official_http['override'].get(path, values[path])
                return raw if isinstance(raw, Response) else Response(raw)
            return respond(url)
        reader.session = Session(route)
        return reader
    monkeypatch.setattr(source.GithubReader, '__aenter__', release_enter)
    official_http.update(pointer=pointer, catalogue=catalogue, future_proof=future_proof, selection_commit=commit)
    return official_http


def test_complete_chain_genuine_bootstrap_and_isolated_future(future_http):
    operation = uuid.uuid4()
    candidate = asyncio.run(chain.retrieve_chain({}, operation_id=operation))
    chain.require_chain(candidate, operation_id=operation)
    assert len(candidate.revisions) == 2
    assert candidate.raw == future_http['catalogue']
    assert candidate.revisions[0].raw == RAW
    assert candidate.revisions[1].publication['archive_base64']['preflight.json'] == base64.b64encode(ORIGINAL).decode()
    with pytest.raises(source.SourceError):
        chain.require_chain(replace(candidate, operation_id=operation), operation_id=operation)


@pytest.mark.parametrize('kind', ['gap', 'cycle', 'missing-archive', 'wrong-archive', 'wrong-pointer', 'mutable', 'by-tag', 'channel'])
def test_chain_tampering_rejected(future_http, kind):
    values = future_http['values']; commit = future_http['selection_commit']
    if kind == 'gap': values[f'/git/commits/{commit}']['parents'] = []
    elif kind == 'cycle': values[f'/git/commits/{commit}']['parents'][0] = {'sha': commit, 'url': f'{source.BASE}/git/commits/{commit}'}
    elif kind == 'missing-archive': values['/releases/902']['assets'].pop()
    elif kind == 'wrong-archive': values['/releases/assets/907'] = b'altered'
    elif kind == 'wrong-pointer': values['/releases/assets/905'] = POINTER
    elif kind == 'mutable': values['/releases/902']['immutable'] = False
    elif kind == 'by-tag': values['/releases/tags/catalogue-000002']['id'] += 1
    else:
        future_http['after'][ingestion.CURRENT] = deepcopy(values[ingestion.CURRENT]); future_http['after'][ingestion.CURRENT]['object']['sha'] = 'e' * 40
    with pytest.raises(ValueError):
        asyncio.run(chain.retrieve_chain({}, operation_id=uuid.uuid4()))


def test_fresh_database_chain_acceptance_and_history(db, future_http):
    result = trust.refresh(db)
    assert result['result'] == 'accepted', result
    assert trust.status(db)['sequence'] == 2
    assert trust.status(db)['publication_policy'] == 'atlas-future-publication-v1'
    assert db.get(trust.Revision, 1).original_bytes == RAW
    assert db.get(trust.Revision, 2).original_bytes == future_http['catalogue']
    assert db.get(trust.State, 1).identity_history['proxmox/0.2.0']['withdrawn']
    allow_attempt(db)
    assert trust.refresh(db)['result'] == 'unchanged'
    assert db.scalar(select(func.count()).select_from(trust.Revision)) == 2


def test_failed_later_revision_does_not_accept_prefix(db, future_http):
    # Authentication succeeds; lifecycle rejects reinterpreted history at storage.
    document = json.loads(future_http['catalogue']); document['entries'][0]['manifest']['display']['name'] = 'substitution'
    candidate = asyncio.run(chain.retrieve_chain({}, operation_id=uuid.uuid4()))
    revision = candidate.revisions[-1]
    # Private storage transaction test explicitly bypasses authentication only to
    # exercise atomic rollback when the second lifecycle check rejects.
    with pytest.raises(ValueError), db.begin_nested():
        state = trust._lock(db)
        trust._store_revision(db, state, RAW, {}, candidate.revisions[0].publication, source.utcnow())
        trust._store_revision(db, state, ingestion.canonical(document), {}, revision.publication, source.utcnow())
    assert db.scalar(select(func.count()).select_from(trust.Revision)) == 0


def test_genuine_wrong_profile_cannot_authenticate_original_unsigned_preflight(approval):
    # The real offline executable must reject the genuine selection bundle when
    # presented as original preflight evidence. No future fixture is signed here.
    with pytest.raises(ValueError):
        future._verified_output(ORIGINAL, SELECTION_BUNDLE, source_commit=SOURCE, run_id=60, policy=approval)
