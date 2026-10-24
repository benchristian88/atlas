"""Consumer policy review and explicit approval types. No active policy or loader.

Parsed policy inputs and the constant proposal are review candidates. Producer
documents, downloaded metadata, environment variables and provider observations
cannot supply approval. Structural validity never supplies publication or executable authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
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


@dataclass(frozen=True, slots=True)
class RulesetReviewIdentities:
    main: int
    history_lock: int
    bootstrap_lock: int
    catalogue_current: int
    publication_tags: int

    def named(self) -> tuple[tuple[str, int], ...]:
        return tuple(("atlas-" + name.replace("_", "-"), value) for name, value in asdict(self).items())


@dataclass(frozen=True, slots=True)
class BootstrapPublicationIdentity:
    sequence: int
    pointer_sha256: str
    catalogue_sha256: str
    release_tag: str
    release_id: int
    catalogue_asset_id: int
    root_commit: str
    selection_run_id: int
    selection_attempt: int
    selection_source: str
    catalogue_build_source: str


@dataclass(frozen=True, slots=True)
class BootstrapTrustPolicyProposal:
    """Atlas-owned review proposal; containing pins does not approve them."""
    policy_version: str
    exception_mode: str
    consumer_review: CatalogueTrustPolicyReviewCandidate
    workflow_id: int
    rulesets: RulesetReviewIdentities
    identity: BootstrapPublicationIdentity


@dataclass(frozen=True, slots=True)
class AtlasApprovedBootstrapPolicy:
    """Explicit code-owned approval input, never parsed from producer data.

    No production instance exists. A later reviewed Atlas change must approve the
    complete proposal and supply its decision reference. This internal type is
    not a defense against arbitrary Python execution, just like verified evidence.
    """
    proposal: BootstrapTrustPolicyProposal
    approval_reference: str


BOOTSTRAP_EXCEPTION_MODE = "atlas-bootstrap-sequence1-exception-v1"
# Versioned consumer proposal ONLY. No runtime consumer instantiates an approval.
# These review inputs do not acquire authority from the producer configuration.
BOOTSTRAP_POLICY_PROPOSAL = BootstrapTrustPolicyProposal(
    policy_version="atlas-bootstrap-consumer-policy-proposal-v1",
    exception_mode=BOOTSTRAP_EXCEPTION_MODE,
    consumer_review=CatalogueTrustPolicyReviewCandidate(
        schema_version="1.0", policy_id=POLICY_ID, allowed_maintainer_id=93822871,
        repository_id=1414494920, owner_id=93822871,
        publication_environment_id=24999137498, package_environment_id=24617213627,
        publisher_app_id=5422372, publisher_app_slug="atlas-catalogue-publisher",
        publisher_bot_user_id=346232650,
        reviewed_producer_revision="51f8693fbcca1e4c6c9615662bca368839ea0757",
        bootstrap=BootstrapReviewCandidate(1, "a275f63d0ac818a193826478328ee324be62353addc5c97a2ed0a28d217b5372"),
        signing=SigningReviewCandidate(
            OIDC_ISSUER, "github-hosted", PREDICATE, "2.102.1", "sigstore-public-good-2026-10-21",
            "3c2cc7f357dc064ec527fdcd78da6e9245c21a381e1abaa0f2b62b186bcac1a1")),
    workflow_id=392548804,
    rulesets=RulesetReviewIdentities(25618213, 25618809, 25628137, 25618684, 25618901),
    identity=BootstrapPublicationIdentity(
        sequence=1, pointer_sha256="a275f63d0ac818a193826478328ee324be62353addc5c97a2ed0a28d217b5372",
        catalogue_sha256="55533ca67e7e9a14f82961e0a8c34ad78e2596049b3db02fde787494e3975afd",
        release_tag="catalogue-000001", release_id=421426993, catalogue_asset_id=667867351,
        root_commit="a1597730687be993d766ddb465a0d3362aef2d02",
        selection_run_id=39896288128, selection_attempt=1,
        selection_source="8ce0b80c74d6ceb8ce75ac7ec8693f5bba78b305",
        catalogue_build_source="91dfd86f18d0b59ff977bb1e8a5fef42c5329943"),
)


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
