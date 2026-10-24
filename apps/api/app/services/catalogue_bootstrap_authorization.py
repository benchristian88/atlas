"""Restricted historical authorization only; no acceptance or execution authority.

The caller supplies genuine Phase 1 provenance and an explicit Atlas approval.
Phase 2A performs all public reads/checks unchanged. Only missing bypass arrays
for this exact original publication may be tolerated under ADR 0013.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services import catalogue_publication_evidence as public, catalogue_source as source
from app.services.catalogue_trust import (
    AtlasApprovedBootstrapPolicy, BOOTSTRAP_EXCEPTION_MODE, BOOTSTRAP_POLICY_PROPOSAL,
    BootstrapPublicationIdentity, BootstrapTrustPolicyProposal,
    BOOTSTRAP_APPROVAL_REFERENCE,
)
from app.services.official_catalogue_selection import StructurallyValidSelection, parse_official_catalogue_selection
from app.services.official_provenance import REPOSITORY_URI, VerifiedProvenance


@dataclass(frozen=True, slots=True)
class BootstrapExceptionAuthorization:
    """Not general publication authorization, an immutable selection or a revision.

    Root identity is compared with the policy here, NOT authenticated transport.
    Catalogue build source is retained as a required acceptance pin, NOT verified
    by this selection-only authorization decision. The Phase 3 adapter must
    independently complete those checks before using the B1.3 trust store.
    """
    policy_version: str
    approval_reference: str
    identity: BootstrapPublicationIdentity
    selection: StructurallyValidSelection
    public_observations: public.VerifiedPublicObservations
    missing_bypass_ruleset_ids: tuple[int, ...]
    exception_mode: str = field(init=False, default=BOOTSTRAP_EXCEPTION_MODE)
    historical_proof_limitation: str = field(init=False, default=(
        "Historical bypass_actors for the five pinned rulesets are not independently recoverable; "
        "public observations do not prove continuous historical or current hidden bypass protections."
    ))
    required_next_checks: tuple[str, ...] = field(init=False, default=(
        "actual_immutable_release_and_exact_release_asset_ids",
        "original_catalogue_selection_and_bundle_bytes",
        "both_genuine_sigstore_profiles_and_original_catalogue_build_source",
        "authenticated_bootstrap_root_and_ref_transport",
        "safe_live_current_pointer_confirmation",
        "trusted_contiguous_history_rollback_and_restore_protection",
        "separate_transactional_catalogue_acceptance",
        "separate_package_eligibility_and_explicit_installation_authority",
    ))


def _require(condition, code):
    source.require(condition, "bootstrap_authorization_" + code)


def _approved_expectations(policy):
    _require(type(policy) is AtlasApprovedBootstrapPolicy, "consumer_policy_approval_required")
    _require(type(policy.approval_reference) is str and 0 < len(policy.approval_reference) <= 256
             and policy.approval_reference.strip() == policy.approval_reference
             and all(32 <= ord(c) < 127 for c in policy.approval_reference), "approval_reference_required")
    _require(policy.approval_reference == BOOTSTRAP_APPROVAL_REFERENCE, "consumer_decision_mismatch")
    proposal = policy.proposal
    _require(type(proposal) is BootstrapTrustPolicyProposal, "consumer_policy_required")
    _require(type(proposal.exception_mode) is str and proposal.exception_mode == BOOTSTRAP_EXCEPTION_MODE,
             "exception_mode_required")
    expected = public.PublicObservationReviewExpectations(proposal.consumer_review, proposal.workflow_id, proposal.rulesets)
    # Existing schema validation also excludes bool/float IDs and checks the
    # independent release-owned verifier/roots. It does not itself approve pins.
    public._expectations(expected)
    _require(type(proposal.identity) is BootstrapPublicationIdentity
             and type(proposal.identity.sequence) is int and type(proposal.identity.selection_attempt) is int
             and proposal == BOOTSTRAP_POLICY_PROPOSAL, "consumer_pin_mismatch")
    return expected


async def evaluate_bootstrap_exception(
    selection: StructurallyValidSelection, provenance: VerifiedProvenance, *,
    root_commit: str, policy: AtlasApprovedBootstrapPolicy, reader: source.GithubReader,
) -> BootstrapExceptionAuthorization:
    """Evaluate one original selection; reject missing approval before any GET.

    No producer response can select the policy or waive another failure. The
    exception neither consumes nor clears Phase 2A's immutable blockers, and has
    no generic future-publication authorization entry point.
    """
    expected = _approved_expectations(policy)
    identity = BOOTSTRAP_POLICY_PROPOSAL.identity
    _require(type(selection) is StructurallyValidSelection, "structural_selection_required")
    # Reparse original bytes: a dataclass replaced independently of its bytes is
    # not a structural or authenticated candidate.
    _require(parse_official_catalogue_selection(selection.source_bytes) == selection, "selection_bytes_mismatch")
    _require(selection.sequence == identity.sequence and selection.pointer_sha256 == identity.pointer_sha256
             and selection.sha256 == identity.catalogue_sha256 and selection.release_tag == identity.release_tag
             and selection.release_id == identity.release_id and selection.asset_id == identity.catalogue_asset_id
             and selection.previous_pointer_sha256 is None, "historical_identity_mismatch")
    _require(type(root_commit) is str and root_commit == identity.root_commit, "root_identity_mismatch")
    _require(type(provenance) is VerifiedProvenance
             and provenance.artifact_sha256 == selection.pointer_sha256, "authenticated_pointer_required")
    _require(provenance.source_commit == identity.selection_source
             and provenance.invocation_uri == (
                 f"{REPOSITORY_URI}/actions/runs/{identity.selection_run_id}/attempts/{identity.selection_attempt}"
             ), "original_selection_required")
    # All public failures, including conflicting PRESENT bypass arrays, propagate
    # unchanged. Only WITHHELD arrays are eligible for this named exception.
    observations = await public.verify_public_observations(provenance, expected=expected, reader=reader)
    return BootstrapExceptionAuthorization(
        policy.proposal.policy_version, policy.approval_reference, identity, selection, observations,
        tuple(row.ruleset_id for row in observations.rulesets if row.bypass_actors is None),
    )
