"""Bounded complete signed selection history; transactional trust promotion only.

Future history requires the release-owned Atlas publication approval. Each
ordinary snapshot must carry the original seven assets; no sequence-two bypass.
"""
import base64
from dataclasses import dataclass, field, asdict
import hashlib
import json
import re
import time
import uuid

from app.services import catalogue_source as source, official_catalogue_ingestion as ingestion
from app.services import catalogue_future_authorization as future
from app.services.catalogue_bootstrap_authorization import evaluate_bootstrap_exception
from app.services.catalogue_trust import approved_bootstrap_policy
from app.services.catalogue_publication_evidence import verify_public_observations
from app.services.connector_verification import GithubSigstoreVerifier
from app.services.official_catalogue import parse_official_catalogue
from app.services.official_catalogue_selection import parse_official_catalogue_selection
from app.services.official_provenance import MAX_BUNDLE_BYTES, TIMEOUT_SECONDS
from app.utils.json_values import to_json_value

MAX_CHAIN = 32
MAX_CHAIN_BYTES = 32 * 1024 * 1024
MAX_REVISION_EVIDENCE = 8 * 1024 * 1024
_SEAL = object()


class FutureGithubReader(source.GithubReader):
    """Separate routing extension; the frozen bootstrap reader stays restricted."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._observations = {}
        self._observation_bytes = 0
        self._assets = {}

    async def __aenter__(self):
        self._observations.clear()
        self._observation_bytes = 0
        self._assets.clear()
        return await super().__aenter__()

    async def __aexit__(self, *args):
        try:
            await super().__aexit__(*args)
        finally:
            self._observations.clear()
            self._observation_bytes = 0
            self._assets.clear()

    async def publication_metadata(self, path):
        # One bounded public observation set per refresh, revalidated separately
        # for every historical run. No ref/release reads or failed responses are
        # cached. Encoded values prevent callers mutating another check's input.
        source.require(type(path) is str, 'invalid_source_destination')
        source.require(time.monotonic() < self.deadline, 'source_timeout')
        if path not in self._observations:
            value = await super().publication_metadata(path)
            raw = json.dumps(value, separators=(',', ':'), allow_nan=False).encode()
            source.require(len(self._observations) < 128 and self._observation_bytes + len(raw) <= 4 * 1024 * 1024,
                           'publication_observation_limit')
            self._observations[path] = raw
            self._observation_bytes += len(raw)
        return source.decode(self._observations[path])

    def asset(self, release, name, *, tag=source.CHANNEL_TAG, maximum=source.MAX_CATALOGUE_BYTES):
        asset = super().asset(release, name, tag=tag, maximum=maximum)
        identity = (tag, name, asset['size'], asset['digest'])
        source.require(asset['id'] not in self._assets or self._assets[asset['id']] == identity,
                       'immutable_asset_identity_changed')
        source.require(len(self._assets) < MAX_CHAIN * 7 + 5 or asset['id'] in self._assets,
                       'catalogue_chain_limit')
        self._assets[asset['id']] = identity
        return asset

    async def download(self, asset, *, maximum=source.MAX_CATALOGUE_BYTES):
        identity = self._assets.get(asset.get('id'))
        source.require(identity is not None, 'invalid_asset_identity')
        tag, name, size, digest = identity
        source.require(asset.get('size') == size and asset.get('digest') == digest and asset.get('name') == name
                       and 0 < size <= maximum, 'immutable_asset_identity_changed')
        # Numeric release/asset identity is authenticated through the REST API.
        # The immutable bytes can use the constructed official download route;
        # neither browser_download_url nor another provider URL selects a route.
        url = f'https://github.com/{source.REPOSITORY}/releases/download/{tag}/{name}'
        raw = await self.get(url, maximum, asset=True, release_download=True)
        source.require(len(raw) == size, 'truncated_source_response')
        source.require(digest == 'sha256:' + hashlib.sha256(raw).hexdigest(), 'asset_digest_mismatch')
        return raw

    async def selection_metadata(self, path: str):
        """Fixed official selection transport endpoints; never provider URLs/refs."""
        source.require(type(path) is str and re.fullmatch(
            r"/(?:git/ref/(?:heads/catalogue-current|tags/(?:catalogue-bootstrap-root|catalogue-[0-9]{6,16}|[a-z][a-z0-9._-]{0,99}-v[0-9][A-Za-z0-9.+-]{0,63}))"
            r"|git/(?:commits|trees|tags)/[a-f0-9]{40}"
            r"|contents/current(?:\.sigstore)?\.json\?ref=[a-f0-9]{40}"
            r"|releases/(?:[1-9][0-9]{0,15}|tags/(?:catalogue-[0-9]{6,16}|[a-z][a-z0-9._-]{0,99}-v[0-9][A-Za-z0-9.+-]{0,63})))", path) is not None, "invalid_source_destination")
        maximum = 2 * MAX_BUNDLE_BYTES if path.startswith("/contents/") else source.METADATA_LIMIT
        raw = await self.get(source.BASE + path, maximum, reject_pagination=True)
        try:
            return source.decode(raw.decode("utf-8"))
        except UnicodeError:
            raise source.SourceError("invalid_source_metadata") from None



@dataclass(frozen=True)
class VerifiedRevision:
    raw: bytes = field(repr=False)
    provenance: object
    selection_provenance: object
    selection: object
    publication_json: bytes = field(repr=False)

    @property
    def publication(self):
        return source.decode(self.publication_json)


@dataclass(frozen=True)
class VerifiedCatalogueChain:
    revisions: tuple[VerifiedRevision, ...]
    operation_id: uuid.UUID
    confirmed_at: object
    policy_sha256: str
    _seal: object = field(init=False, default=None, repr=False, compare=False)

    @property
    def raw(self):
        return self.revisions[-1].raw

    @property
    def provenance(self):
        return self.revisions[-1].provenance


def require_chain(candidate, *, operation_id):
    future.approved_future_policy()
    source.require(type(candidate) is VerifiedCatalogueChain and candidate._seal is _SEAL,
                   'authenticated_selection_required')
    source.require(candidate.operation_id == operation_id and type(operation_id) is uuid.UUID,
                   'catalogue_operation_mismatch')
    source.require(candidate.policy_sha256 == future.APPROVED_FUTURE_POLICY_SHA256,
                   'future_publication_approval_pin_mismatch')
    source.require(1 <= len(candidate.revisions) <= MAX_CHAIN and candidate.confirmed_at <= source.utcnow()
        and (source.utcnow() - candidate.confirmed_at).total_seconds() < source.REFRESH_SECONDS,
        'catalogue_confirmation_expired')
    previous = None
    for index, revision in enumerate(candidate.revisions, 1):
        selection = parse_official_catalogue_selection(revision.selection.source_bytes)
        source.require(selection == revision.selection and selection.sequence == index
            and selection.previous_pointer_sha256 == previous
            and hashlib.sha256(revision.raw).hexdigest() == selection.sha256 == revision.provenance.artifact_sha256,
            'catalogue_chain_mismatch')
        previous = selection.pointer_sha256


def _budget(reader):
    source.require(reader.deadline - time.monotonic() > TIMEOUT_SECONDS + 2, 'source_timeout')


def _actor(value, review):
    source.require(type(value) is dict and type(value.get('id')) is int
        and value['id'] == review.publisher_bot_user_id and value.get('type') == 'Bot'
        and value.get('login') == review.publisher_app_slug + '[bot]', 'publication_actor_mismatch')


async def retrieve_chain(progress, *, operation_id):
    policy = future.approved_future_policy()
    source.require(type(operation_id) is uuid.UUID, 'catalogue_operation_required')
    bootstrap = approved_bootstrap_policy()
    root = bootstrap.proposal.identity.root_commit
    async with FutureGithubReader(budget=240) as reader:
        before = await ingestion.read_ref(reader, ingestion.CURRENT)
        source.require(before['object']['type'] == 'commit', 'invalid_selection_ref')
        commit, reverse, seen, total = before['object']['sha'], [], set(), 0
        while True:
            source.require(commit not in seen and len(reverse) < MAX_CHAIN, 'catalogue_chain_limit')
            seen.add(commit)
            raw, bundle, transport = await ingestion.read_commit(reader, commit, root_only=commit == root, derive_tree=True)
            total += len(raw) + len(bundle)
            source.require(total <= MAX_CHAIN_BYTES, 'catalogue_chain_limit')
            selection = parse_official_catalogue_selection(raw)
            reverse.append((commit, selection, bundle, transport))
            if commit == root:
                break
            source.require(len(transport['parents']) == 1, 'unapproved_selection_root')
            commit = transport['parents'][0]
        source.require(await ingestion.read_ref(reader, ingestion.ROOT_TAG, expected=root), 'unapproved_selection_root')
        revisions, previous, used_sources = [], None, set()
        verifier = GithubSigstoreVerifier()
        for index, (commit, selection, pointer_bundle, transport) in enumerate(reversed(reverse), 1):
            source.require(selection.sequence == index and selection.previous_pointer_sha256 == previous,
                           'catalogue_chain_mismatch')
            _budget(reader)
            selection_proof = verifier.verify_selection(selection.source_bytes, pointer_bundle)
            if index == 1:
                authorization = await evaluate_bootstrap_exception(selection, selection_proof,
                    root_commit=root, policy=bootstrap, reader=reader)
                build_source = bootstrap.proposal.identity.catalogue_build_source
                limits = None
            else:
                build_source, limits = selection_proof.source_commit, future.ARCHIVE_LIMITS
                source.require(build_source not in used_sources, 'publication_selection_source_reused')
            used_sources.add(selection_proof.source_commit)
            release_metadata = await reader.selection_metadata(f'/releases/{selection.release_id}')
            assets, release = await ingestion.selected_release(reader, selection, build_source, archive_limits=limits,
                                                               metadata=release_metadata)
            if index > 1:
                _actor(release_metadata.get('author'), policy.expectations.consumer_review)
                for asset in assets.values():
                    _actor(asset.get('uploader'), policy.expectations.consumer_review)
            raw = await reader.download(assets[selection.release_tag + '.json'])
            progress['last_download_at'] = source.utcnow()
            source.require(hashlib.sha256(raw).hexdigest() == selection.sha256, 'selected_catalogue_digest_mismatch')
            document = parse_official_catalogue(raw).document
            source.require(document['sequence'] == index and ingestion.canonical(document) == raw, 'noncanonical_catalogue')
            catalogue_bundle = await reader.download(assets['catalogue.sigstore.json'], maximum=MAX_BUNDLE_BYTES)
            _budget(reader)
            proof = verifier.verify_catalogue(raw, catalogue_bundle, subject_name=selection.release_tag + '.json')
            source.require(proof.source_commit == build_source, 'catalogue_build_source_mismatch')
            progress['last_authenticity_verified_at'] = proof.verified_at
            source.require(await reader.download(assets['current.json'], maximum=1024) == selection.source_bytes
                and await reader.download(assets['current.sigstore.json'], maximum=MAX_BUNDLE_BYTES) == pointer_bundle,
                'retained_selection_mismatch')
            evidence = {'pointer_sha256': selection.pointer_sha256, 'catalogue_sha256': selection.sha256,
                'selection_commit': commit, 'transport': transport, 'release': release,
                'selection_bytes_base64': base64.b64encode(selection.source_bytes).decode(),
                'pointer_bundle_base64': base64.b64encode(pointer_bundle).decode(),
                'catalogue_bundle_base64': base64.b64encode(catalogue_bundle).decode(),
                'policy': 'atlas-future-publication-v1', 'consumer_policy_sha256': future.APPROVED_FUTURE_POLICY_SHA256}
            if index == 1:
                evidence['bootstrap_authorization'] = to_json_value(asdict(authorization))
                evidence['bootstrap_authorization']['selection']['source_bytes'] = base64.b64encode(selection.source_bytes).decode()
            else:
                files = {name: await reader.download(assets[name], maximum=maximum) for name, maximum in limits.items()}
                total += sum(map(len, files.values()))
                _budget(reader)
                original = future.authenticate_original(files, selection_proof, published_at=release['published_at'])
                observations = await verify_public_observations(selection_proof, expected=policy.expectations, reader=reader)
                # Original run creation time must still agree with the signed observation.
                run_id = original['execution']['run_id']
                for key, path in [('run', f'/actions/runs/{run_id}'), ('attempt', f'/actions/runs/{run_id}/attempts/1')]:
                    current = await reader.publication_metadata(path)
                    source.require(current.get('created_at') == original['security'][key]['created_at'],
                                   'publication_original_run_time_changed')
                evidence.update(archive_base64={name: base64.b64encode(value).decode() for name, value in files.items()},
                    original_authorization_sha256=hashlib.sha256(files['preflight.json']).hexdigest(),
                    public_observations=to_json_value(asdict(observations)),
                    historical_decision=policy.historical_decision, selection_binding_decision=policy.selection_binding_decision,
                    recovery_decision=policy.recovery_decision)
                by_tag = await reader.selection_metadata('/releases/tags/' + selection.release_tag)
                after_assets, after_release = await ingestion.selected_release(reader, selection, build_source,
                    archive_limits=limits, metadata=by_tag)
                _actor(by_tag.get('author'), policy.expectations.consumer_review)
                for asset in after_assets.values():
                    _actor(asset.get('uploader'), policy.expectations.consumer_review)
                source.require(after_release == release,
                               'publication_release_identity_changed')
            transport['release_source'] = await ingestion.release_source(reader, selection.release_tag, build_source)
            # The root's exact pinned immutable release and downloaded bytes need
            # no second identical GET. Future releases have the independent by-tag
            # identity/readback above. Mutable current is always reread below.
            total += len(raw) + len(catalogue_bundle)
            source.require(total <= MAX_CHAIN_BYTES, 'catalogue_chain_limit')
            publication_json = ingestion.canonical(evidence)
            source.require(len(publication_json) <= MAX_REVISION_EVIDENCE, 'catalogue_evidence_too_large')
            revisions.append(VerifiedRevision(raw, proof, selection_proof, selection, publication_json))
            previous = selection.pointer_sha256
        source.require(await ingestion.read_ref(reader, ingestion.CURRENT) == before, 'channel_changed')
        source.require(time.monotonic() < reader.deadline, 'source_timeout')
        candidate = VerifiedCatalogueChain(tuple(revisions), operation_id, source.utcnow(), future.APPROVED_FUTURE_POLICY_SHA256)
        object.__setattr__(candidate, '_seal', _SEAL)
        require_chain(candidate, operation_id=operation_id)
        return candidate
