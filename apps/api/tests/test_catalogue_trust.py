"""Schema review fixtures only: no approved or active consumer policy exists."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from types import SimpleNamespace

import pytest

from app import attestation_distribution as distribution
from app.services import catalogue_source
from app.services.catalogue_trust import (
    IDENTITY_FIELDS, MAX_POLICY_BYTES, CatalogueTrustPolicyError,
    CatalogueTrustPolicyReviewCandidate, parse_catalogue_trust_policy_candidate as parse,
)
from app.services.official_catalogue import MAX_INTEGER
from app.services.official_provenance import OIDC_ISSUER, PREDICATE


@pytest.fixture
def review_document():
    # Intentionally synthetic identities, not copied producer authority. The
    # maintainer deliberately differs from the owner; only explicit input sets it.
    lock = distribution.distribution_lock()
    return {
        "schema_version": "1.0", "policy_id": "single-maintainer-v1", "allowed_maintainer_id": 101,
        "repository_id": 1414494920, "owner_id": 93822871,
        "publication_environment_id": 201, "package_environment_id": 202,
        "publisher_app_id": 301, "publisher_app_slug": "review-candidate-app", "publisher_bot_user_id": 302,
        "reviewed_producer_revision": "b" * 40,
        "bootstrap": {"sequence": 1, "pointer_sha256": "a" * 64},
        "signing": {"oidc_issuer": OIDC_ISSUER, "runner_environment": "github-hosted", "predicate_type": PREDICATE,
            "verifier_version": distribution.VERIFIER_VERSION, "trust_root_id": lock["root_id"],
            "trust_root_sha256": lock["root_sha256"]},
    }


def encode(value):
    return json.dumps(value).encode()


def test_supported_schema_is_immutable_review_material_only(review_document):
    candidate = parse(encode(review_document))
    assert type(candidate) is CatalogueTrustPolicyReviewCandidate
    assert candidate.policy_id == "single-maintainer-v1"
    assert candidate.allowed_maintainer_id == 101 != candidate.owner_id
    assert parse(encode(review_document), expected=candidate) == candidate
    review_document["bootstrap"]["sequence"] = 2
    assert candidate.bootstrap.sequence == 1
    for target, field, value in [(candidate, "allowed_maintainer_id", 999),
        (candidate.bootstrap, "sequence", 2), (candidate.signing, "trust_root_sha256", "0" * 64)]:
        with pytest.raises(FrozenInstanceError):
            setattr(target, field, value)


@pytest.mark.parametrize("mode", [None, "", "independent-reviewer-v1", "single-maintainer-v2", True, {}, []])
def test_unknown_or_missing_policy_mode_rejected(review_document, mode):
    if mode is None:
        del review_document["policy_id"]
    else:
        review_document["policy_id"] = mode
    with pytest.raises(CatalogueTrustPolicyError, match="unsupported_trust_policy_mode"):
        parse(encode(review_document))


@pytest.mark.parametrize("field", ["schema_version", *IDENTITY_FIELDS, "publisher_app_slug",
    "reviewed_producer_revision", "bootstrap", "signing"])
def test_required_fields_cannot_be_inferred(review_document, field):
    del review_document[field]
    with pytest.raises(CatalogueTrustPolicyError, match="trust_policy_fields"):
        parse(encode(review_document))


@pytest.mark.parametrize("field", IDENTITY_FIELDS)
@pytest.mark.parametrize("value", [True, False, None, 1.0, "1", 0, -1, MAX_INTEGER + 1, {}, []])
def test_all_identity_fields_are_literal_positive_safe_integers(review_document, field, value):
    review_document[field] = value
    with pytest.raises(CatalogueTrustPolicyError, match="trust_policy_identity"):
        parse(encode(review_document))


@pytest.mark.parametrize("field", ["repository_id", "owner_id"])
def test_numeric_repository_identity_cannot_change(review_document, field):
    review_document[field] += 1
    with pytest.raises(CatalogueTrustPolicyError, match="trust_policy_repository"):
        parse(encode(review_document))


def test_maintainer_cannot_be_publisher_bot(review_document):
    review_document["allowed_maintainer_id"] = review_document["publisher_bot_user_id"]
    with pytest.raises(CatalogueTrustPolicyError, match="trust_policy_maintainer"):
        parse(encode(review_document))


@pytest.mark.parametrize("slug", ["", "App", "../app", "app[bot]", "a" * 101, None, True, {}])
def test_app_slug_validation(review_document, slug):
    review_document["publisher_app_slug"] = slug
    with pytest.raises(CatalogueTrustPolicyError, match="trust_policy_app_slug"):
        parse(encode(review_document))


@pytest.mark.parametrize("revision", ["B" * 40, "b" * 39, "b" * 41, "g" * 40, None, True, {}])
def test_reviewed_implementation_revision_required(review_document, revision):
    review_document["reviewed_producer_revision"] = revision
    with pytest.raises(CatalogueTrustPolicyError, match="trust_policy_producer_revision"):
        parse(encode(review_document))


@pytest.mark.parametrize("bootstrap", [None, {}, {"sequence": 1}, {"sequence": 1, "pointer_sha256": "a" * 64, "enabled": True},
    {"sequence": True, "pointer_sha256": "a" * 64}, {"sequence": 0, "pointer_sha256": "a" * 64},
    {"sequence": 1.0, "pointer_sha256": "a" * 64}, {"sequence": MAX_INTEGER + 1, "pointer_sha256": "a" * 64},
    *[{"sequence": 1, "pointer_sha256": d} for d in [None, True, [], "A" * 64, "a" * 63, "a" * 65, "g" * 64]],
])
def test_bootstrap_exact_fields_and_digest(review_document, bootstrap):
    review_document["bootstrap"] = bootstrap
    with pytest.raises(CatalogueTrustPolicyError, match="trust_policy_bootstrap"):
        parse(encode(review_document))


@pytest.mark.parametrize("field,value", [("oidc_issuer", "https://attacker.test"),
    ("runner_environment", "self-hosted"), ("predicate_type", "https://attacker.test/predicate"),
    ("verifier_version", "2.102.2"), ("trust_root_id", "downloaded-root"),
    ("trust_root_sha256", "0" * 64), ("trust_root_sha256", "A" * 64)])
def test_independent_signing_and_root_pins_cannot_be_redefined(review_document, field, value):
    review_document["signing"][field] = value
    with pytest.raises(CatalogueTrustPolicyError, match="trust_policy_signing_requirements"):
        parse(encode(review_document))


@pytest.mark.parametrize("mutation", ["missing", "extra", "null"])
def test_signing_fields_exact(review_document, mutation):
    if mutation == "missing":
        del review_document["signing"]["oidc_issuer"]
    elif mutation == "extra":
        review_document["signing"]["root_url"] = "https://producer.test/root"
    else:
        review_document["signing"] = None
    with pytest.raises(CatalogueTrustPolicyError, match="trust_policy_signing_fields"):
        parse(encode(review_document))


@pytest.mark.parametrize("field", ["allowed_maintainer_id", "publication_environment_id", "package_environment_id",
    "publisher_app_id", "publisher_bot_user_id", "publisher_app_slug", "reviewed_producer_revision", "bootstrap"])
def test_producer_or_provider_data_cannot_override_explicit_expected_candidate(review_document, field):
    expected = parse(encode(review_document))
    incoming = deepcopy(review_document)
    if field == "bootstrap":
        incoming[field]["pointer_sha256"] = "c" * 64
    elif field == "publisher_app_slug":
        incoming[field] = "other-app"
    elif field == "reviewed_producer_revision":
        incoming[field] = "c" * 40
    else:
        incoming[field] += 1000
    with pytest.raises(CatalogueTrustPolicyError, match="trust_policy_expectation_mismatch"):
        parse(encode(incoming), expected=expected)
    assert expected == parse(encode(review_document))


@pytest.mark.parametrize("extra", ["enabled", "authorization_mode", "reviewer_ids", "policy_override", "root_url"])
def test_producer_configuration_is_not_consumer_schema(review_document, extra):
    review_document[extra] = True
    with pytest.raises(CatalogueTrustPolicyError, match="trust_policy_fields"):
        parse(encode(review_document))


def test_environment_does_not_supply_or_override_policy(review_document, monkeypatch):
    expected = parse(encode(review_document))
    monkeypatch.setenv("ATLAS_CATALOGUE_TRUST_POLICY", encode({**review_document, "allowed_maintainer_id": 999}).decode())
    monkeypatch.setenv("ALLOWED_MAINTAINER_ID", "999")
    assert parse(encode(review_document), expected=expected) == expected
    with pytest.raises(CatalogueTrustPolicyError):
        parse(b"")


def test_valid_candidate_creates_no_publication_authority(review_document):
    candidate = parse(encode(review_document))
    # Even a correctly named policy and immutable publication cannot open B1.3.
    with pytest.raises(catalogue_source.SourceError, match="current_channel_policy_unavailable"):
        catalogue_source.require_publication(SimpleNamespace(publication={"immutable": True, "policy": candidate.policy_id}))
    assert catalogue_source.POLICY == "atlas-catalogue-channel-v1-blocked"


def test_missing_independent_release_pins_fail_closed(review_document, monkeypatch):
    def unavailable():
        raise OSError("untrusted filesystem diagnostic")
    monkeypatch.setattr(distribution, "distribution_lock", unavailable)
    with pytest.raises(CatalogueTrustPolicyError, match="^trust_policy_release_pins_unavailable$"):
        parse(encode(review_document))


@pytest.mark.parametrize("raw", [None, "{}", bytearray(b"{}"), b"", b"x" * (MAX_POLICY_BYTES + 1),
    b"\xff", b"\xef\xbb\xbf{}", b'{"policy_id":"single-maintainer-v1","policy_id":"single-maintainer-v1"}',
    b'{"policy_id":NaN}', b"[]", b"null", b"[" * 2000])
def test_strict_bounded_policy_json(raw):
    with pytest.raises(CatalogueTrustPolicyError):
        parse(raw)


@pytest.mark.parametrize("schema", [None, True, 1, 1.0, "2.0", {}])
def test_schema_version_exact(review_document, schema):
    review_document["schema_version"] = schema
    with pytest.raises(CatalogueTrustPolicyError, match="trust_policy_schema"):
        parse(encode(review_document))
