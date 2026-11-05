"""Original v2 signed authorization under independent Atlas release-owned pins.

Owner-approved Catalogue 2 signer/policy and accepted historical/selection
contracts are pinned in release code. Remote bytes and environment variables
cannot approve themselves. ADR 0013 remains restricted to sequence one.
"""
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import re
import stat
import tempfile
import time

from app import attestation_distribution as distribution
from app.services import catalogue_source as source, official_provenance as crypto
from app.services.catalogue_publication_evidence import PublicObservationReviewExpectations, _expectations
from app.services.catalogue_trust import BOOTSTRAP_POLICY_PROPOSAL
from app.services.official_catalogue_ingestion import canonical
from app.services.publication_contracts.authorization import check_authorization, parse, WORKFLOW, PREDICATE

ARCHIVE_LIMITS = {'preflight.json': 262144, 'preflight.sigstore.json': 1048576, 'policy.json': 16384}


@dataclass(frozen=True)
class FuturePublicationPolicy:
    expectations: PublicObservationReviewExpectations
    signer_revision: str
    policy_sha256: str
    verification_environment_id: int
    selection_seconds: int
    publication_seconds: int
    historical_decision: str
    selection_binding_decision: str
    recovery_decision: str


# Owner-authorised Catalogue 2 consumer acceptance. Reuse the independently
# approved numeric identities and verifier/root review; only reviewed S changes.
# Remote executable installation has its own separate release-owned approval.
APPROVED_FUTURE_POLICY = FuturePublicationPolicy(
    expectations=PublicObservationReviewExpectations(
        consumer_review=replace(BOOTSTRAP_POLICY_PROPOSAL.consumer_review,
            reviewed_producer_revision='4be90c5292f931497473595a0958cc5e0f9d1beb'),
        workflow_id=BOOTSTRAP_POLICY_PROPOSAL.workflow_id,
        rulesets=BOOTSTRAP_POLICY_PROPOSAL.rulesets),
    signer_revision='4be90c5292f931497473595a0958cc5e0f9d1beb',
    policy_sha256='c9a88eeb6c7e6d0a7f1a08eaa07eeed5ea251449db7104f7757626842cf1bbe9',
    verification_environment_id=25016263801,
    selection_seconds=900,
    publication_seconds=300,
    historical_decision=(
        'https://github.com/benchristian88/atlas/blob/76031dc6358a81c3babd15f74d407e22f0778dee/'
        'docs/decisions/0018-catalogue-durable-publication-evidence.md#historical-authorization'),
    selection_binding_decision=(
        'https://github.com/benchristian88/atlas/blob/76031dc6358a81c3babd15f74d407e22f0778dee/'
        'docs/decisions/0018-catalogue-durable-publication-evidence.md#selection-binding'),
    recovery_decision='disabled-pending-permanent-archive-decision',
)
# sha256(canonical(asdict(APPROVED_FUTURE_POLICY))); literal approval, never repaired at runtime.
APPROVED_FUTURE_POLICY_SHA256 = '83766234eaf1caa24ad067eae414ca3ab381bdbcf9842b10359e200e9dc7324d'


def approved_future_policy():
    value = APPROVED_FUTURE_POLICY
    source.require(type(value) is FuturePublicationPolicy and APPROVED_FUTURE_POLICY_SHA256 is not None,
                   'future_publication_owner_approval_required')
    source.require(hashlib.sha256(canonical(asdict(value))).hexdigest() == APPROVED_FUTURE_POLICY_SHA256,
                   'future_publication_approval_pin_mismatch')
    _expectations(value.expectations)
    source.require(value.expectations.consumer_review.reviewed_producer_revision == value.signer_revision,
                   "future_publication_reviewed_successor_required")
    source.require(type(value.signer_revision) is str and re.fullmatch('[a-f0-9]{40}', value.signer_revision)
        and type(value.policy_sha256) is str and re.fullmatch('[a-f0-9]{64}', value.policy_sha256)
        and type(value.verification_environment_id) is int and value.verification_environment_id > 0,
        'future_publication_independent_pins_required')
    source.require(all(type(v) is int and 1 <= v <= 1800 for v in
        (value.selection_seconds, value.publication_seconds)), 'future_publication_time_policy_required')
    source.require(all(type(v) is str and 0 < len(v) <= 256 for v in
        (value.historical_decision, value.selection_binding_decision))
        and value.recovery_decision == 'disabled-pending-permanent-archive-decision',
        'future_publication_decisions_required')
    return value


def _verified_output(raw, bundle, *, source_commit, run_id, policy):
    """Only the hash-checked offline verifier supplies the authenticated statement."""
    crypto._bundle(bundle)
    try:
        lock = distribution.distribution_lock()
        roots = distribution.checked_root(lock)
        binary = distribution.checked_binary(lock)
    except (OSError, ValueError, KeyError):
        raise source.SourceError('publication_verifier_unavailable') from None
    info = crypto.TEMP_ROOT.lstat()
    source.require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
        and info.st_uid == 0 and bool(info.st_mode & stat.S_ISVTX), 'publication_temporary_root')
    with tempfile.TemporaryDirectory(prefix='atlas-publication-', dir=crypto.TEMP_ROOT) as name:
        work = Path(name)
        deadline = time.monotonic() + crypto.TIMEOUT_SECONDS
        version = crypto._run([str(binary), '--version'], work, deadline)
        source.require(version.splitlines() and version.splitlines()[0] == b'gh version 2.102.1 (2026-10-20)',
                       'publication_verifier_version')
        for filename, content in [('artifact', raw), ('bundle.json', bundle), ('roots.jsonl', roots)]:
            crypto._write_private(work / filename, content)
        command = [str(binary), 'attestation', 'verify', str(work / 'artifact'),
            '--bundle', str(work / 'bundle.json'), '--custom-trusted-root', str(work / 'roots.jsonl'),
            '--repo', source.REPOSITORY, '--hostname', 'github.com',
            '--signer-workflow', source.REPOSITORY + '/' + WORKFLOW, '--signer-digest', policy.signer_revision,
            '--source-digest', source_commit, '--source-ref', 'refs/heads/main',
            '--cert-oidc-issuer', crypto.OIDC_ISSUER, '--deny-self-hosted-runners',
            '--predicate-type', PREDICATE, '--digest-alg', 'sha256', '--format', 'json']
        return source.decode(crypto._run(command, work, deadline))


def authenticate_original(files, selection, *, published_at):
    policy = approved_future_policy()
    source.require(type(files) is dict and files.keys() == ARCHIVE_LIMITS.keys(), 'publication_archive_inventory')
    source.require(all(type(files[n]) is bytes and 0 < len(files[n]) <= limit
                       for n, limit in ARCHIVE_LIMITS.items()), 'publication_archive_size')
    source.require(type(selection) is crypto.VerifiedProvenance and selection.profile == crypto.TrustProfile.SELECTION,
                   'publication_authenticated_selection_required')
    match = re.fullmatch(re.escape(crypto.REPOSITORY_URI) + r'/actions/runs/([1-9][0-9]{0,15})/attempts/1',
                         selection.invocation_uri)
    source.require(match is not None and int(match[1]) <= 2**53 - 1, 'publication_selection_invocation')
    run_id = int(match[1])
    raw, bundle, policy_raw = (files[n] for n in ARCHIVE_LIMITS)
    source.require(hashlib.sha256(policy_raw).hexdigest() == policy.policy_sha256, 'publication_policy_pin_mismatch')
    review = policy.expectations.consumer_review
    producer_policy = source.decode(policy_raw)
    # Exact bytes are independently pinned; compare every consumer identity too.
    source.require(all(producer_policy.get(k) == v for k, v in {
        'allowed_maintainer_id': review.allowed_maintainer_id, 'environment_id': review.publication_environment_id,
        'package_environment_id': review.package_environment_id, 'app_id': review.publisher_app_id,
        'app_slug': review.publisher_app_slug, 'app_bot_user_id': review.publisher_bot_user_id}.items()),
        'publication_policy_identity_mismatch')
    value = parse(raw, ARCHIVE_LIMITS['preflight.json'])
    trust = {'schema': 'atlas-publication-verifier-trust/v2', 'live_signer_accepted': True,
        'signer_revision': policy.signer_revision, 'ruleset_ids': dict(policy.expectations.rulesets.named()),
        'verification_environment_id': policy.verification_environment_id, 'max_observation_age_seconds': 900}
    expected = {'source_commit': selection.source_commit, 'policy_sha256': policy.policy_sha256,
        'run_id': run_id, 'run_attempt': 1, 'operation': 'publish', 'acceptance_only': False}
    source.require(check_authorization(value, trust, producer_policy) == expected, 'publication_original_context')
    output = _verified_output(raw, bundle, source_commit=selection.source_commit, run_id=run_id, policy=policy)
    try:
        source.require(type(output) is list and len(output) == 1, 'publication_verifier_result')
        verified = output[0]['verificationResult']
        cert = verified['signature']['certificate']
        expected_cert = {'issuer': crypto.OIDC_ISSUER, 'buildSignerDigest': policy.signer_revision,
            'sourceRepositoryURI': crypto.REPOSITORY_URI, 'sourceRepositoryIdentifier': crypto.REPOSITORY_ID,
            'sourceRepositoryOwnerIdentifier': crypto.OWNER_ID, 'sourceRepositoryOwnerURI': crypto.OWNER_URI,
            'sourceRepositoryDigest': selection.source_commit, 'sourceRepositoryRef': 'refs/heads/main',
            'sourceRepositoryVisibilityAtSigning': 'public', 'runnerEnvironment': 'github-hosted',
            'buildConfigURI': crypto.REPOSITORY_URI + '/.github/workflows/catalogue-publish.yml@refs/heads/main',
            'buildConfigDigest': selection.source_commit, 'buildTrigger': 'workflow_dispatch',
            'runInvocationURI': selection.invocation_uri}
        identity = cert.get('subjectAlternativeName')
        source.require(all(cert.get(k) == v for k, v in expected_cert.items()) and type(identity) is str
            and identity.count('@') == 1 and identity.partition('@')[0] == crypto.REPOSITORY_URI + '/' + WORKFLOW
            and bool(identity.partition('@')[2]) and cert.get('buildSignerURI') == identity,
            'publication_certificate_mismatch')
        digest = hashlib.sha256(raw).hexdigest()
        source.require(verified['statement'] == {'_type': 'https://in-toto.io/Statement/v1',
            'subject': [{'name': 'preflight.json', 'digest': {'sha256': digest}}], 'predicateType': PREDICATE,
            'predicate': {'schema': 'atlas-publication-preflight-predicate/v2', 'preflight_sha256': digest}},
            'publication_statement_mismatch')
        stamps = verified['verifiedTimestamps']
        source.require(type(stamps) is list and 1 <= len(stamps) <= 8 and all(s['type'] == 'Tlog'
            and s['uri'] in {'https://rekor.sigstore.dev', 'https://log2025-1.rekor.sigstore.dev'} for s in stamps),
            'publication_witness_required')
        times = tuple(crypto._timestamp(s['timestamp']) for s in stamps)
        fresh = value['freshness']
        issued = datetime.fromtimestamp(fresh['issued_at'], timezone.utc)
        expires = datetime.fromtimestamp(fresh['expires_at'], timezone.utc)
        started = datetime.fromtimestamp(fresh['observation_started'], timezone.utc)
        selected = tuple(s.timestamp for s in selection.witnessed_at)
        source.require(1 <= len(selected) <= 8 and all(issued <= t < expires for t in times)
            and max(times) <= min(selected) and max(selected) <= issued + timedelta(seconds=policy.selection_seconds),
            'publication_historical_time')
        published = crypto._timestamp(published_at)
        source.require(max(selected) <= published <= max(selected) + timedelta(seconds=policy.publication_seconds),
                       'publication_historical_time')
        for run in (value['security']['run'], value['security']['attempt']):
            source.require(crypto._timestamp(run['created_at']) <= started, 'publication_original_run_time')
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        raise source.SourceError('publication_original_evidence_invalid') from None
    return value
