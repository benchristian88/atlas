"""Accepted remote selection, immutable download, existing PackageStore adapter.

No remote bytes enter the store until currentness, release identity and genuine
package provenance are checked. Installed packages remain entirely local/offline.
"""
from contextlib import asynccontextmanager
from dataclasses import replace, dataclass, asdict
import base64
import hashlib
from pathlib import Path
import tempfile
import time

from sqlalchemy import select

from app.models import ConnectorCatalogueRevision as Revision, ConnectorCatalogueState as State
from app.services import catalogue_source as source, catalogue_future_authorization as future
from app.services import official_catalogue_ingestion as ingestion
from app.services.catalogue_chain import FutureGithubReader, _actor, _budget
from app.services.connector_catalogue import CataloguePackage
from app.services.connector_contracts import validate_manifest
from app.services.connector_store import MAX_ARCHIVE_BYTES
from app.services.connector_verification import GithubSigstoreVerifier, VerificationEvidence, verify_digest
from app.services.official_catalogue import parse_official_catalogue
from app.services.official_provenance import PackageArtifactContext, MAX_BUNDLE_BYTES, TEMP_ROOT


@dataclass(frozen=True)
class RemoteInstallationPolicy:
    publication_policy_sha256: str
    approval_reference: str
    packaging_mode: str = 'docker_compose'


# Separate release-owned executable eligibility approval. Publication approval
# alone never activates remote executable installation.
APPROVED_REMOTE_INSTALLATION = None
APPROVED_REMOTE_INSTALLATION_SHA256 = None


def approved_remote_installation():
    future.approved_future_policy()
    value = APPROVED_REMOTE_INSTALLATION
    source.require(type(value) is RemoteInstallationPolicy and APPROVED_REMOTE_INSTALLATION_SHA256 is not None,
                   'remote_installation_owner_approval_required')
    source.require(hashlib.sha256(ingestion.canonical(asdict(value))).hexdigest() == APPROVED_REMOTE_INSTALLATION_SHA256
        and value.publication_policy_sha256 == future.APPROVED_FUTURE_POLICY_SHA256
        and value.packaging_mode == 'docker_compose'
        and type(value.approval_reference) is str and 0 < len(value.approval_reference) <= 256,
        'remote_installation_approval_pin_mismatch')
    return value


@dataclass(frozen=True)
class RemoteSelection:
    package: CataloguePackage
    sequence: int
    catalogue_digest: str
    release_tag: str
    asset_id: int
    selection_commit: str
    pointer: bytes
    pointer_bundle: bytes


def select_remote(db, connector_id, version, *, lock=False):
    approved_remote_installation()
    statement = select(State).where(State.id == 1).execution_options(populate_existing=True)
    if lock:
        statement = statement.with_for_update()
    state = db.scalar(statement)
    source.require(state is not None and state.highest_sequence is not None and state.highest_sequence >= 2
        and state.last_confirmed_current_at is not None and not state.source_conflict and not state.last_error_code
        and state.operation_id is None, 'remote_catalogue_confirmation_required')
    revision = db.get(Revision, state.highest_sequence)
    source.require(revision is not None and hashlib.sha256(revision.original_bytes).hexdigest() == state.highest_digest
        and revision.content_digest == state.highest_digest
        and revision.publication_evidence.get('consumer_policy_sha256') == future.APPROVED_FUTURE_POLICY_SHA256,
        'remote_catalogue_evidence_required')
    document = parse_official_catalogue(revision.original_bytes).document
    entries = [e for e in document['entries'] if e['manifest']['id'] == connector_id and e['manifest']['version'] == version]
    source.require(len(entries) == 1 and entries[0]['status'] == 'active', 'remote_package_not_eligible')
    entry, publication = entries[0], revision.publication_evidence
    manifest = entry['manifest']
    validate_manifest(manifest, activation=True)
    try:
        pointer = base64.b64decode(publication['selection_bytes_base64'], validate=True)
        pointer_bundle = base64.b64decode(publication['pointer_bundle_base64'], validate=True)
        selection = ingestion.parse_official_catalogue_selection(pointer)
        source.require(selection.sequence == revision.sequence and selection.sha256 == revision.content_digest
            and selection.pointer_sha256 == publication['pointer_sha256'] and ingestion._sha(publication['selection_commit']),
            'remote_catalogue_evidence_required')
    except (KeyError, TypeError, ValueError):
        raise source.SourceError('remote_catalogue_evidence_required') from None
    package = CataloguePackage(connector_id, version, manifest['distribution']['bundle_digest'], manifest, 'official', True)
    return RemoteSelection(package, revision.sequence, revision.content_digest, entry['release_tag'],
        entry['release_asset_id'], publication['selection_commit'], pointer, pointer_bundle)


def require_confirmation(selection, payload):
    source.require(payload.source == 'official' and payload.confirm == 'install'
        and payload.version == selection.package.version
        and 'sha256:' + payload.digest == selection.package.bundle_digest
        and payload.catalogue_sequence == selection.sequence and payload.catalogue_digest == selection.catalogue_digest
        and payload.release_asset_id == selection.asset_id, 'remote_install_confirmation_mismatch')


class DownloadedPackageVerifier:
    def __init__(self, selection, bundle):
        self.selection, self.bundle = selection, bundle

    def verify(self, raw, package):
        expected = self.selection.package
        source.require(package.connector_id == expected.connector_id and package.version == expected.version
            and package.bundle_digest == expected.bundle_digest and package.manifest == expected.manifest
            and package.source == 'official', 'remote_package_identity_mismatch')
        verify_digest(raw, expected.bundle_digest)
        provenance = package.manifest['distribution']['provenance']
        proof = GithubSigstoreVerifier().verify_package(raw, self.bundle,
            PackageArtifactContext(package.connector_id, package.version, package.bundle_digest.removeprefix('sha256:'),
                                   provenance['source_commit']))
        return VerificationEvidence('github-artifact-attestation-sigstore', package.bundle_digest, 'atlas-official',
            repository=source.REPOSITORY, workflow=provenance['workflow'], source_commit=proof.source_commit,
            release_identity=self.selection.release_tag)


@asynccontextmanager
async def downloaded_package(selection):
    approved_remote_installation()
    policy = future.approved_future_policy()
    package = selection.package
    tag = selection.release_tag
    commit = package.manifest['distribution']['provenance']['source_commit']
    async with FutureGithubReader(budget=240) as reader:
        # Reauthenticate retained signed selection before treating it as current.
        _budget(reader)
        proof = GithubSigstoreVerifier().verify_selection(selection.pointer, selection.pointer_bundle)
        source.require(proof.artifact_sha256 == hashlib.sha256(selection.pointer).hexdigest(), 'remote_selection_mismatch')
        before = await ingestion.read_ref(reader, ingestion.CURRENT, expected=selection.selection_commit)
        await reader.repository()
        release = await reader.selection_metadata('/releases/tags/' + tag)
        identifier = release.get('id')
        source.require(type(identifier) is int and 0 < identifier <= 2**53 - 1
            and release.get('tag_name') == tag and release.get('draft') is False and release.get('prerelease') is False
            and release.get('immutable') is True and release.get('target_commitish') == commit
            and release.get('url') == f'{source.BASE}/releases/{identifier}'
            and release.get('html_url') == f'https://github.com/{source.REPOSITORY}/releases/tag/{tag}',
            'remote_release_not_immutable')
        _actor(release.get('author'), policy.expectations.consumer_review)
        names = {f'{package.connector_id}-{package.version}.tar.gz': MAX_ARCHIVE_BYTES,
            'manifest.json': 262144, 'index.json': 262144, 'SHA256SUMS': 16384, 'package.sigstore.json': MAX_BUNDLE_BYTES}
        source.require(type(release.get('assets')) is list and len(release['assets']) == len(names)
            and all(type(a) is dict and type(a.get('name')) is str for a in release['assets'])
            and {a['name'] for a in release['assets']} == names.keys(), 'remote_release_inventory')
        assets = {name: reader.asset(release, name, tag=tag, maximum=limit) for name, limit in names.items()}
        source.require(len({a['id'] for a in assets.values()}) == len(names)
            and assets[f'{package.connector_id}-{package.version}.tar.gz']['id'] == selection.asset_id,
            'remote_package_asset_mismatch')
        for asset in assets.values():
            _actor(asset.get('uploader'), policy.expectations.consumer_review)
        raw = await reader.download(assets[f'{package.connector_id}-{package.version}.tar.gz'], maximum=MAX_ARCHIVE_BYTES)
        manifest_raw = await reader.download(assets['manifest.json'], maximum=262144)
        source.require(source.decode(manifest_raw) == package.manifest, 'remote_package_manifest_mismatch')
        bundle = await reader.download(assets['package.sigstore.json'], maximum=MAX_BUNDLE_BYTES)
        verifier = DownloadedPackageVerifier(selection, bundle)
        _budget(reader)
        verifier.verify(raw, package)
        await ingestion.release_source(reader, tag, commit)
        after = await reader.selection_metadata(f'/releases/{identifier}')
        # Mutable download counters are excluded; exact numeric identity/digests remain bound.
        source.require(all(after.get(k) == release.get(k) for k in ingestion.RELEASE_KEYS)
            and type(after.get('assets')) is list and len(after['assets']) == len(names), 'remote_release_changed')
        for name, limit in names.items():
            source.require(all(reader.asset(after, name, tag=tag, maximum=limit).get(k) == assets[name].get(k)
                for k in ingestion.ASSET_KEYS), 'remote_release_changed')
        source.require(await ingestion.read_ref(reader, ingestion.CURRENT, expected=selection.selection_commit) == before,
                       'channel_changed')
        source.require(time.monotonic() < reader.deadline, 'source_timeout')
    # Only the API installer can write the protected store. Native permission
    # failures remain errors; no chmod, privilege helper or runtime writer added.
    with tempfile.TemporaryDirectory(prefix='atlas-remote-package-', dir=TEMP_ROOT) as directory:
        path = Path(directory) / 'package.tar.gz'
        with path.open('xb') as stream:
            stream.write(raw)
        path.chmod(0o400)
        yield replace(package, archive_path=path), verifier
