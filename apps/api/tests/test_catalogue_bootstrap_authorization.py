"""Genuine offline signatures plus SYNTHETIC public GitHub observations.

Provider responses here are synthetic; production policy is approved by ADR 0013.
These tests do not demonstrate online historical authorization or acceptance.
"""
import asyncio
from dataclasses import FrozenInstanceError, asdict, replace
import json
from types import SimpleNamespace

import pytest

from app.services import catalogue_bootstrap_authorization as bootstrap
from app.services import catalogue_publication_evidence as public, catalogue_source as source, trusted_catalogue
from app.services.catalogue_trust import (
    AtlasApprovedBootstrapPolicy, BOOTSTRAP_EXCEPTION_MODE, BOOTSTRAP_POLICY_PROPOSAL as PROPOSAL,
    parse_catalogue_trust_policy_candidate,
    approved_bootstrap_policy,
)
from app.services.connector_verification import GithubSigstoreVerifier, VerificationEvidence
from app.services.official_catalogue_selection import (
    OfficialCatalogueSelectionError, parse_official_catalogue_selection as parse,
)
from app.services.official_provenance import ProvenanceError, REPOSITORY_URI, TrustProfile
from tests.test_catalogue_publication_evidence import (
    APP, ATTEMPT, CHECKS, ENVIRONMENT, FIXTURES, LATEST, RULE_LIST, WORKFLOW_PATH,
    authenticated_selection, provider, review_document,
)
from tests.test_catalogue_source import Response, reader as http_reader

RAW = (FIXTURES / "current.json").read_bytes()
ROOT = PROPOSAL.identity.root_commit
TEST_APPROVAL = approved_bootstrap_policy()


@pytest.fixture
def bootstrap_provider(provider):
    """Reuse Phase 2A's synthetic response shapes, with proposal review inputs."""
    _, values = provider
    for path in (LATEST, ATTEMPT):
        values[path]["workflow_id"] = PROPOSAL.workflow_id
        for key in ("actor", "triggering_actor"):
            values[path][key]["id"] = PROPOSAL.consumer_review.allowed_maintainer_id
    values["/users/review-maintainer"]["id"] = PROPOSAL.consumer_review.allowed_maintainer_id
    workflow = values.pop(WORKFLOW_PATH)
    path = f"/actions/workflows/{PROPOSAL.workflow_id}"
    workflow.update(id=PROPOSAL.workflow_id, url=source.BASE + path)
    values[path] = workflow
    values[ENVIRONMENT]["id"] = PROPOSAL.consumer_review.publication_environment_id
    app = values.pop(APP)
    app.update(id=PROPOSAL.consumer_review.publisher_app_id, slug=PROPOSAL.consumer_review.publisher_app_slug)
    values["/apps/" + PROPOSAL.consumer_review.publisher_app_slug] = app
    for row in values[RULE_LIST]:
        old = row["id"]
        identifier = dict(PROPOSAL.rulesets.named())[row["name"]]
        row["id"] = identifier
        detail = values.pop(f"/rulesets/{old}?includes_parents=true")
        detail["id"] = identifier
        values[f"/rulesets/{identifier}?includes_parents=true"] = detail
    return values


def evaluate(values, provenance, *, selection=None, root=ROOT, policy=TEST_APPROVAL, overrides=None):
    def respond(url):
        path = url.removeprefix(source.BASE) if url.startswith(source.BASE) else url.removeprefix(source.API)
        assert path in values, "Unexpected endpoint"
        if overrides and path in overrides:
            return overrides[path]
        return Response(json.dumps(values[path]).encode())
    return asyncio.run(bootstrap.evaluate_bootstrap_exception(
        parse(RAW) if selection is None else selection, provenance,
        root_commit=root, policy=policy, reader=http_reader(respond)))


def test_exact_bootstrap_with_genuine_signature_and_synthetic_public_evidence(bootstrap_provider, authenticated_selection):
    result = evaluate(bootstrap_provider, authenticated_selection)
    assert type(result) is bootstrap.BootstrapExceptionAuthorization
    assert result.exception_mode == BOOTSTRAP_EXCEPTION_MODE
    assert result.policy_version == PROPOSAL.policy_version
    assert result.approval_reference == TEST_APPROVAL.approval_reference
    assert result.identity == PROPOSAL.identity
    assert result.selection.source_bytes == RAW
    assert result.public_observations.selection_provenance is authenticated_selection
    assert authenticated_selection.artifact_sha256 == result.identity.pointer_sha256
    assert result.public_observations.first_attempt.run_id == result.identity.selection_run_id
    assert set(result.missing_bypass_ruleset_ids) == {i for _, i in PROPOSAL.rulesets.named()}
    assert "not independently recoverable" in result.historical_proof_limitation
    assert "authenticated_bootstrap_root_and_ref_transport" in result.required_next_checks
    assert "both_genuine_sigstore_profiles_and_original_catalogue_build_source" in result.required_next_checks
    assert result.public_observations.authorization_blockers == (
        "reviewed_ruleset_evidence_required", "consumer_trust_approval_required")
    assert not isinstance(result, (public.VerifiedPublicObservations, source.AuthenticatedCandidate, VerificationEvidence))
    for target, name in [(result, "required_next_checks"), (result, "exception_mode"),
                         (result.identity, "sequence"), (PROPOSAL, "consumer_review"),
                         (TEST_APPROVAL, "approval_reference")]:
        with pytest.raises(FrozenInstanceError):
            setattr(target, name, None)


def test_proposal_remains_schema_valid_review_material():
    assert parse_catalogue_trust_policy_candidate(json.dumps(asdict(PROPOSAL.consumer_review)).encode()) == PROPOSAL.consumer_review
    assert PROPOSAL.consumer_review.policy_id == "single-maintainer-v1"


@pytest.mark.parametrize("mutation", [
    {"sequence": 2, "release_tag": "catalogue-000002", "previous_pointer_sha256": "a" * 64},
    {"sequence": 3, "release_tag": "catalogue-000003", "previous_pointer_sha256": PROPOSAL.identity.pointer_sha256},
    {"release_id": 421426994}, {"asset_id": 667867352}, {"sha256": "a" * 64},
])
def test_changed_canonical_pointer_and_later_sequence_reject_before_http(authenticated_selection, mutation):
    value = json.loads(RAW)
    value.update(mutation)
    changed = parse((json.dumps(value, sort_keys=True, indent=2) + "\n").encode())
    with pytest.raises(source.SourceError, match="bootstrap_authorization_historical_identity_mismatch"):
        evaluate({}, authenticated_selection, selection=changed)


def test_structural_values_cannot_be_detached_from_original_bytes(authenticated_selection):
    with pytest.raises(source.SourceError, match="selection_bytes_mismatch"):
        evaluate({}, authenticated_selection, selection=replace(parse(RAW), release_id=999))
    with pytest.raises(OfficialCatalogueSelectionError, match="noncanonical_pointer"):
        evaluate({}, authenticated_selection, selection=replace(parse(RAW), source_bytes=RAW + b"\n"))


@pytest.mark.parametrize("field,value,code", [
    ("artifact_sha256", "a" * 64, "authenticated_pointer_required"),
    ("source_commit", "a" * 40, "original_selection_required"),
    ("source_commit", PROPOSAL.consumer_review.reviewed_producer_revision, "original_selection_required"),
    ("invocation_uri", REPOSITORY_URI + "/actions/runs/39912401767/attempts/1", "original_selection_required"),
    ("invocation_uri", REPOSITORY_URI + "/actions/runs/39896288128/attempts/2", "original_selection_required"),
    ("profile", TrustProfile.CATALOGUE, "publication_evidence_selection_provenance_required"),
    ("repository_id", "999", "publication_evidence_selection_provenance_required"),
    ("owner_id", "999", "publication_evidence_selection_provenance_required"),
    ("workflow_identity", REPOSITORY_URI + "/.github/workflows/other.yml@refs/heads/main", "publication_evidence_selection_provenance_required"),
])
def test_verified_evidence_consistency_failures_do_not_mock_crypto(authenticated_selection, field, value, code):
    # Mutated typed evidence exercises binding checks only, not signature success.
    with pytest.raises(source.SourceError, match=code):
        evaluate({}, replace(authenticated_selection, **{field: value}))


def test_wrong_root_claim_and_missing_provenance_reject(authenticated_selection):
    with pytest.raises(source.SourceError, match="root_identity_mismatch"):
        evaluate({}, authenticated_selection, root="a" * 40)
    with pytest.raises(source.SourceError, match="authenticated_pointer_required"):
        evaluate({}, None)


@pytest.mark.parametrize("policy", [None, PROPOSAL, PROPOSAL.consumer_review, {}, "single-maintainer-v1"])
def test_missing_consumer_approval_rejects_before_http(authenticated_selection, policy):
    with pytest.raises(source.SourceError, match="consumer_policy_approval_required"):
        evaluate({}, authenticated_selection, policy=policy)


@pytest.mark.parametrize("mode", [None, "", "skip_ruleset_verification", "atlas-bootstrap-sequence1-exception-v2"])
def test_missing_or_unknown_exception_mode_rejects(authenticated_selection, mode):
    policy = replace(TEST_APPROVAL, proposal=replace(PROPOSAL, exception_mode=mode))
    with pytest.raises(source.SourceError, match="exception_mode_required"):
        evaluate({}, authenticated_selection, policy=policy)


@pytest.mark.parametrize("reference", [None, "", " ", "producer\nreceipt", "x" * 257])
def test_approval_reference_required(authenticated_selection, reference):
    with pytest.raises(source.SourceError, match="approval_reference_required"):
        evaluate({}, authenticated_selection, policy=replace(TEST_APPROVAL, approval_reference=reference))


@pytest.mark.parametrize("reference", ["producer-approval", "owner-approved", "atlas-owner-2026-10-26-adr-0013"])
def test_arbitrary_caller_approval_string_cannot_activate_policy(authenticated_selection, reference):
    with pytest.raises(source.SourceError, match="consumer_decision_mismatch"):
        evaluate({}, authenticated_selection, policy=replace(TEST_APPROVAL, approval_reference=reference))


@pytest.mark.parametrize("field,value", [
    ("allowed_maintainer_id", 999), ("publication_environment_id", 999), ("package_environment_id", 999),
    ("publisher_app_id", 999), ("publisher_app_slug", "producer-selected-app"), ("publisher_bot_user_id", 999),
    ("reviewed_producer_revision", "a" * 40),
])
def test_even_an_approval_wrapper_cannot_expand_proposed_authority(authenticated_selection, field, value):
    proposal = replace(PROPOSAL, consumer_review=replace(PROPOSAL.consumer_review, **{field: value}))
    with pytest.raises(source.SourceError, match="consumer_pin_mismatch"):
        evaluate({}, authenticated_selection, policy=replace(TEST_APPROVAL, proposal=proposal))


@pytest.mark.parametrize("field,value", [
    ("sequence", 2), ("pointer_sha256", "a" * 64), ("catalogue_sha256", "a" * 64),
    ("catalogue_build_source", "a" * 40), ("root_commit", "a" * 40),
    ("release_id", 999), ("catalogue_asset_id", 999), ("selection_source", "a" * 40),
    ("selection_run_id", 39912401767), ("selection_attempt", 2),
])
def test_exception_cannot_be_retargeted_by_replacing_review_pins(authenticated_selection, field, value):
    proposal = replace(PROPOSAL, identity=replace(PROPOSAL.identity, **{field: value}))
    with pytest.raises(source.SourceError, match="consumer_pin_mismatch"):
        evaluate({}, authenticated_selection, policy=replace(TEST_APPROVAL, proposal=proposal))


@pytest.mark.parametrize("field,value", [("workflow_id", 999), ("rulesets", replace(PROPOSAL.rulesets, main=999)),
                                        ("policy_version", "producer-policy-v1")])
def test_workflow_ruleset_and_policy_versions_are_consumer_pins(authenticated_selection, field, value):
    with pytest.raises(source.SourceError, match="consumer_pin_mismatch"):
        evaluate({}, authenticated_selection, policy=replace(TEST_APPROVAL, proposal=replace(PROPOSAL, **{field: value})))


@pytest.mark.parametrize("case,code", [
    ("actor", "actor"), ("workflow", "workflow"), ("ci_failed", "ci"), ("ci_missing", "ci_count"),
    ("app", "publisher"), ("environment", "environment"), ("repository", "repository"),
    ("rerun", "first_attempt_required"), ("source", "run_source"), ("protection", "ruleset_protection"),
    ("ci_protection", "ruleset_required_ci"),
])
def test_public_failures_propagate_without_waiver(bootstrap_provider, authenticated_selection, case, code):
    if case == "actor":
        bootstrap_provider[LATEST]["actor"]["id"] = 999
        bootstrap_provider[LATEST]["allowed_maintainer_id"] = 999  # producer override has no authority
    elif case == "workflow":
        bootstrap_provider[LATEST]["workflow_id"] = 999
    elif case == "ci_failed":
        bootstrap_provider[CHECKS]["check_runs"][0]["conclusion"] = "failure"
    elif case == "ci_missing":
        bootstrap_provider[CHECKS] = {"total_count": 0, "check_runs": []}
    elif case == "app":
        bootstrap_provider["/apps/" + PROPOSAL.consumer_review.publisher_app_slug]["id"] = 999
    elif case == "environment":
        bootstrap_provider[ENVIRONMENT]["id"] = 999
    elif case == "repository":
        bootstrap_provider[""]["id"] = 999
    elif case == "rerun":
        bootstrap_provider[LATEST]["run_attempt"] = 2
    elif case == "source":
        bootstrap_provider[ATTEMPT]["head_sha"] = "a" * 40
    elif case == "protection":
        bootstrap_provider[f"/rulesets/{PROPOSAL.rulesets.main}?includes_parents=true"]["rules"].pop()
    else:
        bootstrap_provider[f"/rulesets/{PROPOSAL.rulesets.main}?includes_parents=true"]["rules"][1]["parameters"]["strict_required_status_checks_policy"] = False
    with pytest.raises(source.SourceError, match="^publication_evidence_" + code + "$"):
        evaluate(bootstrap_provider, authenticated_selection)


@pytest.mark.parametrize("name,identifier", PROPOSAL.rulesets.named())
def test_each_pinned_ruleset_conflicting_bypass_rejects(bootstrap_provider, authenticated_selection, name, identifier):
    bootstrap_provider[f"/rulesets/{identifier}?includes_parents=true"]["bypass_actors"] = [
        {"actor_id": 999, "actor_type": "Integration", "bypass_mode": "always"}]
    with pytest.raises(source.SourceError, match="publication_evidence_ruleset_bypass"):
        evaluate(bootstrap_provider, authenticated_selection)


@pytest.mark.parametrize("complete", [False, True])
def test_present_correct_bypass_arrays_are_not_reclassified_as_missing(bootstrap_provider, authenticated_selection, complete):
    for name, identifier in PROPOSAL.rulesets.named():
        if not complete and name != "atlas-main":
            continue
        bypass = [] if name in {"atlas-main", "atlas-history-lock", "atlas-bootstrap-lock"} else [
            {"actor_id": PROPOSAL.consumer_review.publisher_app_id, "actor_type": "Integration", "bypass_mode": "always"}]
        bootstrap_provider[f"/rulesets/{identifier}?includes_parents=true"]["bypass_actors"] = bypass
    result = evaluate(bootstrap_provider, authenticated_selection)
    assert len(result.missing_bypass_ruleset_ids) == (0 if complete else 4)
    assert len(result.public_observations.authorization_blockers) == 2


@pytest.mark.parametrize("endpoint", [LATEST, ATTEMPT, CHECKS, ENVIRONMENT, RULE_LIST,
    f"/rulesets/{PROPOSAL.rulesets.main}?includes_parents=true"])
def test_any_unavailable_public_observation_still_rejects(bootstrap_provider, authenticated_selection, endpoint):
    with pytest.raises(source.SourceError, match="source_not_found"):
        evaluate(bootstrap_provider, authenticated_selection, overrides={endpoint: Response(status=404)})


def test_real_signature_rejects_changed_pointer_and_cross_profile_bundle():
    verifier = GithubSigstoreVerifier()
    with pytest.raises(ProvenanceError):
        verifier.verify_selection(RAW.replace(b"667867351", b"667867352"),
                                  (FIXTURES / "current.sigstore.json").read_bytes())
    with pytest.raises(ProvenanceError):
        verifier.verify_selection(RAW, (FIXTURES / "catalogue.sigstore.json").read_bytes())


def test_no_general_authorization_promotion_or_installation_authority(bootstrap_provider, authenticated_selection):
    result = evaluate(bootstrap_provider, authenticated_selection)
    for partial in (authenticated_selection, result.public_observations, result):
        with pytest.raises(source.SourceError, match="consumer_policy_approval_required"):
            evaluate({}, authenticated_selection, policy=partial)
    # Both original B1.3 gates remain even if an exception is attached to genuine
    # catalogue evidence. Database/store primitives are never reached.
    raw = (FIXTURES / "catalogue-000001.json").read_bytes()
    catalogue_provenance = GithubSigstoreVerifier().verify_catalogue(
        raw, (FIXTURES / "catalogue.sigstore.json").read_bytes())
    for immutable, code in [(False, "publication_not_immutable"), (True, "current_channel_policy_unavailable")]:
        candidate = SimpleNamespace(raw=raw, provenance=catalogue_provenance,
            publication={"immutable": immutable, "bootstrap_authorization": result})
        with pytest.raises(source.SourceError, match=code):
            trusted_catalogue._promote(None, None, candidate)
    # Using this result as package evidence fails the existing package profile.
    assert not isinstance(result, VerificationEvidence)
    assert not hasattr(result, "package_available")
    assert "separate_package_eligibility_and_explicit_installation_authority" in result.required_next_checks
