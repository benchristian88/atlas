"""Genuine Proxmox 0.2.2 crypto/store behind synthetic future catalogue approval.

No source system or deployed Atlas instance is contacted. Runtime verification
reads the real temporary store independently; health/provider metadata are fixtures.
"""
import asyncio
from copy import deepcopy
from dataclasses import replace, asdict
import json
import os
from pathlib import Path
import sys
import uuid

from fastapi import HTTPException
import pytest
from sqlalchemy import select, func

from app.models import InstalledConnectorPackage, AuditEvent
from app.routes import integrations as routes
from app.services import remote_connector_packages as remote, connector_lifecycle as lifecycle, trusted_catalogue as trust
from app.services.connector_store import PackageStore
from app.services.integration_connections import installed_manifest
from app.services.connector_catalogue import catalogue_manifest, accepted_official_metadata
from app.services.official_provenance import GithubAttestationVerifier
from tests.test_catalogue_future import future_http, original, approval, official_http, bootstrap_provider, provider, review_document, db, LOCAL
from tests.test_administration import make_principal, request
from scripts.seed_system import seed_system

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'apps/runtime/ansible'))
from atlas_runtime.server import Runtime


@pytest.fixture
def remote_http(future_http):
    values = future_http['values']
    release = json.loads((LOCAL / 'release.json').read_bytes())
    tag = 'proxmox-v0.2.2'
    values['/releases/tags/' + tag] = release
    values[f"/releases/{release['id']}"] = deepcopy(release)
    values['/git/ref/tags/' + tag] = json.loads((LOCAL / 'tag-ref.json').read_bytes())
    for asset in release['assets']:
        path = LOCAL / asset['name']
        if path.is_file():
            values[f"/releases/assets/{asset['id']}"] = path.read_bytes()
    return future_http


@pytest.fixture
def remote_approval(approval, monkeypatch):
    import hashlib
    from app.services import catalogue_future_authorization as future, official_catalogue_ingestion as ingestion
    value = remote.RemoteInstallationPolicy(future.APPROVED_FUTURE_POLICY_SHA256, 'SYNTHETIC INSTALLATION APPROVAL ONLY')
    monkeypatch.setattr(remote, 'APPROVED_REMOTE_INSTALLATION', value)
    monkeypatch.setattr(remote, 'APPROVED_REMOTE_INSTALLATION_SHA256', hashlib.sha256(ingestion.canonical(asdict(value))).hexdigest())
    return value


@pytest.fixture
def selected(db, remote_http, remote_approval):
    assert trust.refresh(db)['result'] == 'accepted'
    return remote.select_remote(db, 'proxmox', '0.2.2')


def payload(selection, **changes):
    values = dict(source='official', version=selection.package.version,
        digest=selection.package.bundle_digest.removeprefix('sha256:'), catalogue_sequence=selection.sequence,
        catalogue_digest=selection.catalogue_digest, release_asset_id=selection.asset_id, confirm='install')
    return routes.PackageSelection(**(values | changes))


def test_genuine_existing_package_crypto_is_not_mocked():
    manifest = json.loads((LOCAL / 'manifest.json').read_bytes())
    from app.services.official_provenance import PackageArtifactContext
    proof = GithubAttestationVerifier().verify_package((LOCAL / 'proxmox-0.2.2.tar.gz').read_bytes(),
        (LOCAL / 'package.sigstore.json').read_bytes(), PackageArtifactContext('proxmox', '0.2.2',
        manifest['distribution']['bundle_digest'].removeprefix('sha256:'), manifest['distribution']['provenance']['source_commit']))
    assert proof.source_commit == 'e58788a667c0c0006477ac149e8ad28aedda0745'


def test_download_genuine_package_into_existing_store(selected, tmp_path):
    async def install():
        async with remote.downloaded_package(selected) as (package, verifier):
            stored = PackageStore(tmp_path / 'store').install(package, verifier)
            assert stored.version == '0.2.2'
            assert stored.verification['method'] == 'github-artifact-attestation-sigstore'
        assert not package.archive_path.exists()
        # Offline validation does not use provider availability.
        assert PackageStore(tmp_path / 'store').verify_connector('proxmox', stored.version, stored.bundle_digest)['state'] == 'verified'
    asyncio.run(install())


@pytest.mark.parametrize('change', [{'digest': 'a' * 64}, {'catalogue_sequence': 3}, {'catalogue_digest': 'b' * 64},
    {'release_asset_id': 1}, {'version': '0.2.0'}, {'confirm': None}, {'source': 'bootstrap'}])
def test_exact_review_confirmation_required(selected, change):
    with pytest.raises(ValueError, match='confirmation_mismatch'):
        remote.require_confirmation(selected, payload(selected, **change))


@pytest.mark.parametrize('kind', ['mutable', 'asset', 'author', 'uploader', 'digest', 'manifest', 'signature', 'channel'])
def test_remote_tamper_never_enters_store(selected, remote_http, tmp_path, kind):
    values = remote_http['values']; tag = 'proxmox-v0.2.2'
    release = values['/releases/tags/' + tag]
    if kind == 'mutable': release['immutable'] = False
    elif kind == 'asset':
        next(a for a in release['assets'] if a['name'].endswith('.tar.gz'))['id'] += 1
    elif kind == 'author': release['author']['id'] = 1
    elif kind == 'uploader': release['assets'][0]['uploader']['id'] = 1
    elif kind in ('digest', 'manifest', 'signature'):
        name = {'digest': 'proxmox-0.2.2.tar.gz', 'manifest': 'manifest.json', 'signature': 'package.sigstore.json'}[kind]
        asset = next(a for a in release['assets'] if a['name'] == name)
        raw = values[f"/releases/assets/{asset['id']}"] + b'altered'
        values[f"/releases/assets/{asset['id']}"] = raw
        if kind == 'signature':
            import hashlib
            asset.update(size=len(raw), digest='sha256:' + hashlib.sha256(raw).hexdigest())
    else:
        remote_http['after']['/git/ref/heads/catalogue-current'] = deepcopy(values['/git/ref/heads/catalogue-current'])
        remote_http['after']['/git/ref/heads/catalogue-current']['object']['sha'] = 'e' * 40
    async def install():
        async with remote.downloaded_package(selected) as (package, verifier):
            PackageStore(tmp_path / 'store').install(package, verifier)
    with pytest.raises(ValueError):
        asyncio.run(install())
    assert not (tmp_path / 'store').exists()


@pytest.fixture
def install_harness(db, selected, tmp_path, monkeypatch):
    seed_system(db)
    # Explicit test-operator managed reference records; production never creates
    # taxonomy implicitly from downloaded Connector declarations.
    from app.models import AssetType, RelationshipType
    from app.services.connector_mappings import declarations, target
    for kind, declaration, recommended in declarations(selected.package.manifest):
        if recommended and target(db, kind, recommended) is None:
            model = AssetType if kind == 'asset' else RelationshipType
            kwargs = {'key': recommended, 'name': declaration['label'], 'active': True}
            if kind == 'relationship': kwargs['directional'] = declaration['direction'] != 'undirected'
            db.add(model(**kwargs))
    db.flush()
    principal = make_principal('integration_runtime.manage', 'integration_runtime.view')
    principal.user.email = 'remote-' + uuid.uuid4().hex + '@example.test'
    db.add(principal.user); db.commit()
    store = PackageStore(tmp_path / 'store')
    independent = Runtime('test-only-runtime-control', store.root, 'docker_compose')
    health = {'status': 'healthy', 'packaging_mode': 'docker_compose', 'baseline_version': '1.2.0',
        'baseline_id': 'atlas-ansible-i4a-v1', 'baseline_digest': 'b' * 64,
        'protocol_version': 'integration-runtime-v1', 'capabilities': {'aip_versions': ['1.0'],
        'runtime_kind': 'ansible', 'dependencies': selected.package.manifest['implementation']['dependencies']}}
    async def report(): return deepcopy(health)
    async def verify(reference): return independent.verify_connector(reference)
    monkeypatch.setattr(lifecycle, 'package_store', lambda: store)
    monkeypatch.setattr(routes.runtime, 'health', report)
    monkeypatch.setattr(routes.runtime, 'verify_connector', verify)
    return principal, store, health


def test_route_activation_configuration_mapping_and_offline_execution(db, selected, install_harness, remote_http):
    principal, store, health = install_harness
    from app.services.connector_mappings import mapping_state
    mappings = mapping_state(db, selected.package.manifest, auto_map=True)
    assert all(row['resolved'] for row in mappings if row['required']), mappings
    result = asyncio.run(routes._install('proxmox', payload(selected), request(), principal, db))
    assert result['version'] == '0.2.2' and result['verification_status'] == 'verified'
    active = db.get(InstalledConnectorPackage, 'proxmox')
    assert active.bundle_digest == selected.package.bundle_digest.removeprefix('sha256:')
    assert active.verification_evidence['method'] == 'github-artifact-attestation-sigstore'
    assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == 'connector.activated')) == 1
    remote_http['values'].clear()  # No subsequent network available.
    assert installed_manifest(db, 'proxmox')[1] == selected.package.manifest
    assert catalogue_manifest(db, 'proxmox', '0.2.2') == selected.package.manifest


def test_native_install_fails_without_permission_weakening(db, selected, install_harness):
    principal, store, health = install_harness; health['packaging_mode'] = 'systemd'
    with pytest.raises(HTTPException) as error:
        asyncio.run(routes._install('proxmox', payload(selected), request(), principal, db))
    assert error.value.status_code == 409
    assert error.value.detail['code'] == 'remote_install_requires_docker'
    assert not store.root.exists() and db.get(InstalledConnectorPackage, 'proxmox') is None


def test_withdrawn_version_and_stale_or_conflicting_state_rejected(db, selected):
    with pytest.raises(ValueError, match='not_eligible'):
        remote.select_remote(db, 'proxmox', '0.2.0')
    db.get(trust.State, 1).last_confirmed_current_at = None
    with pytest.raises(ValueError, match='confirmation_required'):
        remote.select_remote(db, 'proxmox', '0.2.2')


def test_publication_approval_alone_does_not_authorize_remote_installation(approval):
    with pytest.raises(ValueError, match='remote_installation_owner_approval_required'):
        remote.approved_remote_installation()


@pytest.mark.parametrize('change', ['refresh-in-progress', 'currentness-invalidated', 'withdrawn'])
def test_locked_reselection_after_download_preserves_previous_activation(db, selected, install_harness, monkeypatch, change):
    from contextlib import asynccontextmanager
    from datetime import timedelta
    from app.services import catalogue_source as source, official_catalogue_ingestion as ingestion
    principal, _, _ = install_harness
    asyncio.run(routes._install('proxmox', payload(selected), request(), principal, db))
    active = db.get(InstalledConnectorPackage, 'proxmox')
    previous = (active.version, active.bundle_digest, active.activated_at)
    audit_count = db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == 'connector.activated'))
    download = remote.downloaded_package
    @asynccontextmanager
    async def changed(selection):
        async with download(selection) as package:
            state = db.get(trust.State, 1)
            if change == 'refresh-in-progress':
                state.operation_id = uuid.uuid4()
                state.lease_until = source.utcnow() + timedelta(seconds=300)
            elif change == 'currentness-invalidated':
                state.last_confirmed_current_at = None
            else:
                # Explicit storage-only race fixture, not fabricated signature
                # acceptance: model a withdrawal committed before locked selection.
                document = json.loads(db.get(trust.Revision, 2).original_bytes)
                document['sequence'] = 3
                next(e for e in document['entries'] if e['manifest']['version'] == '0.2.2')['status'] = 'withdrawn'
                trust._store_revision(db, state, ingestion.canonical(document), {},
                    db.get(trust.Revision, 2).publication_evidence, source.utcnow())
            db.flush()
            yield package
    monkeypatch.setattr(remote, 'downloaded_package', changed)
    with pytest.raises(HTTPException) as error:
        asyncio.run(routes._install('proxmox', payload(selected), request(), principal, db))
    assert error.value.status_code == 409
    db.expire_all()
    active = db.get(InstalledConnectorPackage, 'proxmox')
    assert (active.version, active.bundle_digest, active.activated_at) == previous
    assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == 'connector.activated')) == audit_count
