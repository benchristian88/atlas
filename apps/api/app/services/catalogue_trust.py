"""Consumer policy schema review only. No approved policy, loader or activation.

All inputs and outputs are review candidates. Producer documents, downloaded
metadata, environment variables and provider observations cannot configure this
module. Structural validity never supplies publication or executable authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from atlas_connector_sdk.contracts import ContractError, strict_json

from app import attestation_distribution as distribution
from app.services.connector_contracts import ConnectorPackageError
from app.services.official_catalogue import MAX_INTEGER
from app.services.official_provenance import OIDC_ISSUER, OWNER_ID, PREDICATE, REPOSITORY_ID

MAX_POLICY_BYTES = 8192
POLICY_ID = "single-maintainer-v1"
POLICY_FIELDS = {"schema_version", "policy_id", "allowed_maintainer_id", "repository_id", "owner_id",
                 "publication_environment_id", "package_environment_id", "publisher_app_id",
                 "publisher_app_slug", "publisher_bot_user_id", "reviewed_producer_revision",
                 "bootstrap", "signing"}
IDENTITY_FIELDS = ("allowed_maintainer_id", "repository_id", "owner_id", "publication_environment_id",
                   "package_environment_id", "publisher_app_id", "publisher_bot_user_id")
SIGNING_FIELDS = {"oidc_issuer", "runner_environment", "predicate_type", "verifier_version",
                  "trust_root_id", "trust_root_sha256"}


class CatalogueTrustPolicyError(ConnectorPackageError):
    """Stable diagnostics; never echo candidate configuration."""


@dataclass(frozen=True, slots=True)
class BootstrapReviewCandidate:
    sequence: int
    pointer_sha256: str


@dataclass(frozen=True, slots=True)
class SigningReviewCandidate:
    oidc_issuer: str
    runner_environment: str
    predicate_type: str
    verifier_version: str
    trust_root_id: str
    trust_root_sha256: str


@dataclass(frozen=True, slots=True)
class CatalogueTrustPolicyReviewCandidate:
    """Schema-valid review material; explicitly NOT an approved trust policy."""
    schema_version: str
    policy_id: str
    allowed_maintainer_id: int
    repository_id: int
    owner_id: int
    publication_environment_id: int
    package_environment_id: int
    publisher_app_id: int
    publisher_app_slug: str
    publisher_bot_user_id: int
    reviewed_producer_revision: str
    bootstrap: BootstrapReviewCandidate
    signing: SigningReviewCandidate


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CatalogueTrustPolicyError(code)


def _positive_integer(value) -> bool:
    return type(value) is int and 0 < value <= MAX_INTEGER


def _hex(value, length: int) -> bool:
    return type(value) is str and re.fullmatch(r"[a-f0-9]{%d}" % length, value) is not None


def parse_catalogue_trust_policy_candidate(
    raw: bytes, *, expected: CatalogueTrustPolicyReviewCandidate | None = None,
) -> CatalogueTrustPolicyReviewCandidate:
    """Validate explicit review input, optionally against independent expectations.

    There is deliberately no default maintainer, App, environment, revision or
    bootstrap pin. Signing/root requirements must match the independent Atlas
    release distribution, never values obtained from the producer. ``expected``
    can constrain a review comparison; it does not approve or install a policy.
    """
    _require(type(raw) is bytes and 0 < len(raw) <= MAX_POLICY_BYTES, "trust_policy_bytes_required")
    _require(expected is None or type(expected) is CatalogueTrustPolicyReviewCandidate,
             "invalid_trust_policy_expectation")
    try:
        value = strict_json(raw.decode("utf-8"), maximum=MAX_POLICY_BYTES)
    except ContractError as error:
        raise CatalogueTrustPolicyError(error.code) from None
    except (ValueError, UnicodeError, RecursionError):
        raise CatalogueTrustPolicyError("invalid_trust_policy_json") from None
    _require(type(value) is dict, "trust_policy_fields")
    _require(type(value.get("policy_id")) is str and value["policy_id"] == POLICY_ID,
             "unsupported_trust_policy_mode")
    _require(value.keys() == POLICY_FIELDS, "trust_policy_fields")
    _require(type(value["schema_version"]) is str and value["schema_version"] == "1.0", "trust_policy_schema")
    for name in IDENTITY_FIELDS:
        _require(_positive_integer(value[name]), "trust_policy_identity")
    _require(value["repository_id"] == int(REPOSITORY_ID) and value["owner_id"] == int(OWNER_ID),
             "trust_policy_repository")
    _require(value["allowed_maintainer_id"] != value["publisher_bot_user_id"], "trust_policy_maintainer")
    _require(type(value["publisher_app_slug"]) is str and re.fullmatch(
        r"[a-z0-9][a-z0-9-]{0,99}", value["publisher_app_slug"]) is not None, "trust_policy_app_slug")
    _require(_hex(value["reviewed_producer_revision"], 40), "trust_policy_producer_revision")
    bootstrap = value["bootstrap"]
    _require(type(bootstrap) is dict and bootstrap.keys() == {"sequence", "pointer_sha256"},
             "trust_policy_bootstrap_fields")
    _require(_positive_integer(bootstrap["sequence"]) and _hex(bootstrap["pointer_sha256"], 64),
             "trust_policy_bootstrap")
    signing = value["signing"]
    _require(type(signing) is dict and signing.keys() == SIGNING_FIELDS, "trust_policy_signing_fields")
    try:
        lock = distribution.distribution_lock()
    except (OSError, ValueError, KeyError):
        raise CatalogueTrustPolicyError("trust_policy_release_pins_unavailable") from None
    _require(signing == {
        "oidc_issuer": OIDC_ISSUER, "runner_environment": "github-hosted", "predicate_type": PREDICATE,
        "verifier_version": distribution.VERIFIER_VERSION,
        "trust_root_id": lock["root_id"], "trust_root_sha256": lock["root_sha256"],
    }, "trust_policy_signing_requirements")
    candidate = CatalogueTrustPolicyReviewCandidate(**{
        **value, "bootstrap": BootstrapReviewCandidate(**bootstrap), "signing": SigningReviewCandidate(**signing),
    })
    _require(expected is None or candidate == expected, "trust_policy_expectation_mismatch")
    return candidate
