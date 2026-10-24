"""Verified public observations, never complete publication authorization.

Callers supply genuine Phase 1 evidence and independent review expectations.
No policy loader, approved identities, credentials, persistence or promotion live
here. Hidden bypass evidence and consumer trust approval remain separate gates.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
import re
import time

from app.services import catalogue_source as source
from app.services.catalogue_trust import CatalogueTrustPolicyReviewCandidate, parse_catalogue_trust_policy_candidate
from app.services.official_catalogue import MAX_INTEGER
from app.services.official_provenance import (
    REPOSITORY_URI, TrustProfile, VerifiedProvenance,
)

WORKFLOW = ".github/workflows/catalogue-publish.yml"
CHECK_APP_ID = 15368
RULESET_LIST = "/rulesets?includes_parents=true&per_page=6&page=1"


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
class PublicObservationReviewExpectations:
    """Explicit evaluation inputs, NOT an activated CatalogueTrustPolicy."""
    consumer_review: CatalogueTrustPolicyReviewCandidate
    workflow_id: int
    rulesets: RulesetReviewIdentities


@dataclass(frozen=True, slots=True)
class PublicAccountObservation:
    user_id: int
    login: str
    user_type: str


@dataclass(frozen=True, slots=True)
class PublicRepositoryObservation:
    repository_id: int
    owner_id: int
    full_name: str
    private: bool


@dataclass(frozen=True, slots=True)
class PublicRunObservation:
    endpoint: str
    run_id: int
    run_attempt: int
    source_commit: str
    branch: str
    event: str
    api_url: str
    html_url: str
    workflow_id: int
    path: str
    repository: PublicRepositoryObservation
    head_repository: PublicRepositoryObservation
    actor: PublicAccountObservation
    triggering_actor: PublicAccountObservation


@dataclass(frozen=True, slots=True)
class PublicWorkflowObservation:
    workflow_id: int
    path: str
    state: str
    api_url: str
    html_url: str


@dataclass(frozen=True, slots=True)
class PublicBranchObservation:
    name: str
    protected: bool
    current_head_sha: str


@dataclass(frozen=True, slots=True)
class PublicCheckObservation:
    check_id: int
    name: str
    source_commit: str
    status: str
    conclusion: str
    app_id: int


@dataclass(frozen=True, slots=True)
class PublicEnvironmentObservation:
    environment_id: int
    name: str
    can_admins_bypass: bool
    protected_branches: bool
    custom_branch_policies: bool
    # (numeric rule identity, supported rule type, optional wait timer minutes)
    protection_rules: tuple[tuple[int, str, int | None], ...]


@dataclass(frozen=True, slots=True)
class PublicPublisherObservation:
    app_id: int
    slug: str
    owner_id: int
    permissions: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class PublicRulesetObservation:
    ruleset_id: int
    name: str
    target: str
    enforcement: str
    included_refs: tuple[str, ...]
    # Canonical bytes retain checked visible parameters without mutable dicts.
    visible_rules_json: bytes
    # None means WITHHELD, not an empty list. Present arrays must match review.
    bypass_actors: tuple[tuple[int, str, str], ...] | None


@dataclass(frozen=True, slots=True)
class VerifiedPublicObservations:
    """Partial evidence only, even when every public GET/field is consistent.

    This is deliberately neither AuthenticatedCandidate nor package verification
    evidence. No acceptance consumer is provided. Blockers cannot be constructor
    inputs, and a present bypass array does not approve a consumer trust policy.
    """
    selection_provenance: VerifiedProvenance
    review_expectations: PublicObservationReviewExpectations
    observation_started_at: datetime
    observation_completed_at: datetime
    latest_run: PublicRunObservation
    first_attempt: PublicRunObservation
    account: PublicAccountObservation
    workflow: PublicWorkflowObservation
    repository: PublicRepositoryObservation
    branch: PublicBranchObservation
    source_ci: PublicCheckObservation
    environment: PublicEnvironmentObservation
    publisher: PublicPublisherObservation
    rulesets: tuple[PublicRulesetObservation, ...]
    authorization_blockers: tuple[str, ...] = field(init=False, default=(
        "reviewed_ruleset_evidence_required", "consumer_trust_approval_required",
    ))


def _require(condition, code):
    source.require(condition, "publication_evidence_" + code)


def _integer(value):
    return type(value) is int and 0 < value <= MAX_INTEGER


def _object(value, code):
    _require(type(value) is dict, code)
    return value


def _expectations(expected):
    _require(type(expected) is PublicObservationReviewExpectations
             and type(expected.consumer_review) is CatalogueTrustPolicyReviewCandidate
             and type(expected.rulesets) is RulesetReviewIdentities, "review_expectations_required")
    # Reuse Phase 1's strict schema, including independent Atlas release pins.
    review = parse_catalogue_trust_policy_candidate(json.dumps(asdict(expected.consumer_review)).encode())
    _require(review == expected.consumer_review and _integer(expected.workflow_id), "review_expectations")
    ids = tuple(value for _, value in expected.rulesets.named())
    _require(all(_integer(value) for value in ids) and len(set(ids)) == 5, "review_ruleset_identities")
    return review


def _selection(provenance, review):
    _require(type(provenance) is VerifiedProvenance and provenance.profile == TrustProfile.SELECTION
             and provenance.subject_name == "current.json" and provenance.repository == REPOSITORY_URI
             and provenance.repository_id == str(review.repository_id)
             and provenance.owner_id == str(review.owner_id)
             and provenance.workflow_identity == f"{REPOSITORY_URI}/{WORKFLOW}@refs/heads/main"
             and provenance.source_ref == "refs/heads/main"
             and provenance.oidc_issuer == review.signing.oidc_issuer
             and provenance.runner_environment == review.signing.runner_environment
             and provenance.predicate_type == review.signing.predicate_type
             and provenance.verifier_version == review.signing.verifier_version
             and provenance.trust_root_id == review.signing.trust_root_id
             and provenance.trust_root_sha256 == review.signing.trust_root_sha256,
             "selection_provenance_required")
    _require(type(provenance.source_commit) is str
             and re.fullmatch(r"[a-f0-9]{40}", provenance.source_commit) is not None, "source_commit")
    match = re.fullmatch(re.escape(REPOSITORY_URI) + r"/actions/runs/([1-9][0-9]{0,15})/attempts/1",
                         provenance.invocation_uri) if type(provenance.invocation_uri) is str else None
    _require(match is not None and _integer(int(match[1])), "selection_invocation")
    return int(match[1])


def _repository(value, review):
    value = _object(value, "repository")
    owner = _object(value.get("owner"), "repository")
    _require(_integer(value.get("id")) and value["id"] == review.repository_id
             and _integer(owner.get("id")) and owner["id"] == review.owner_id
             and value.get("full_name") == source.REPOSITORY and value.get("private") is False,
             "repository")
    return PublicRepositoryObservation(value["id"], owner["id"], value["full_name"], False)


def _account(value, review):
    value = _object(value, "actor")
    login = value.get("login")
    _require(_integer(value.get("id")) and value["id"] == review.allowed_maintainer_id
             and value.get("type") == "User" and type(login) is str and len(login) <= 39
             and re.fullmatch(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", login) is not None, "actor")
    return PublicAccountObservation(value["id"], login, "User")


def _run(value, endpoint, run_id, provenance, expected, review):
    value = _object(value, "run")
    _require(_integer(value.get("id")) and value["id"] == run_id, "run_identity")
    _require(type(value.get("run_attempt")) is int and value["run_attempt"] == 1, "first_attempt_required")
    repository = _repository(value.get("repository"), review)
    head_repository = _repository(value.get("head_repository"), review)
    _require(value.get("event") == "workflow_dispatch" and value.get("head_branch") == "main"
             and value.get("head_sha") == provenance.source_commit, "run_source")
    _require(value.get("url") == f"{source.BASE}/actions/runs/{run_id}"
             and value.get("html_url") == f"{REPOSITORY_URI}/actions/runs/{run_id}", "run_urls")
    _require(_integer(value.get("workflow_id")) and value["workflow_id"] == expected.workflow_id
             and value.get("path") in (WORKFLOW, WORKFLOW + "@main", WORKFLOW + "@refs/heads/main"),
             "workflow")
    actor, triggering = (_account(value.get(key), review) for key in ("actor", "triggering_actor"))
    _require(actor == triggering, "actor_conflict")
    return PublicRunObservation(endpoint, run_id, 1, provenance.source_commit, "main", "workflow_dispatch",
        value["url"], value["html_url"], value["workflow_id"], value["path"], repository, head_repository, actor, triggering)


def _environment(value, review):
    value = _object(value, "environment")
    branch_policy = _object(value.get("deployment_branch_policy"), "environment")
    _require(_integer(value.get("id")) and value["id"] == review.publication_environment_id
             and value.get("name") == "catalogue-publication" and value.get("can_admins_bypass") is False
             and branch_policy.keys() == {"protected_branches", "custom_branch_policies"}
             and branch_policy["protected_branches"] is True
             and branch_policy["custom_branch_policies"] is False, "environment")
    rules = value.get("protection_rules")
    _require(type(rules) is list and 1 <= len(rules) <= 2, "environment_rules")
    result = []
    for row in rules:
        row = _object(row, "environment_rules")
        kind = row.get("type")
        _require(_integer(row.get("id")) and kind in ("branch_policy", "wait_timer"), "environment_rules")
        timer = row.get("wait_timer") if kind == "wait_timer" else None
        _require(kind != "wait_timer" or type(timer) is int and 0 <= timer <= 43200, "environment_rules")
        result.append((row["id"], kind, timer))
    _require(len({row[1] for row in result}) == len(result)
             and any(row[1] == "branch_policy" for row in result), "environment_rules")
    return PublicEnvironmentObservation(value["id"], value["name"], False, True, False, tuple(sorted(result)))


def _ruleset_identity(value, name, identifier):
    value = _object(value, "ruleset_identity")
    _require(_integer(value.get("id")) and value["id"] == identifier and value.get("name") == name
             and value.get("source_type") == "Repository" and value.get("source") == source.REPOSITORY
             and value.get("enforcement") == "active", "ruleset_identity")
    return value


def _ruleset(value, name, identifier, review):
    value = _ruleset_identity(value, name, identifier)
    scopes = {
        "atlas-main": ("branch", ("refs/heads/main",), {"pull_request", "required_status_checks", "deletion", "non_fast_forward"}),
        "atlas-history-lock": ("branch", ("refs/heads/catalogue-current",), {"deletion", "non_fast_forward"}),
        "atlas-bootstrap-lock": ("tag", ("refs/tags/catalogue-bootstrap-root",), {"update", "deletion"}),
        "atlas-catalogue-current": ("branch", ("refs/heads/catalogue-current",), {"creation", "update", "deletion", "non_fast_forward"}),
        "atlas-publication-tags": ("tag", ("refs/tags/catalogue-*", "refs/tags/*-v*"), {"creation", "update", "deletion"}),
    }
    target, included, kinds = scopes[name]
    _require(value.get("target") == target and value.get("conditions") == {
        "ref_name": {"include": list(included), "exclude": []}}, "ruleset_scope")
    rules = value.get("rules")
    _require(type(rules) is list and len(kinds) <= len(rules) <= len(kinds) + 1
             and all(type(row) is dict and type(row.get("type")) is str for row in rules), "ruleset_protection")
    observed_kinds = {row["type"] for row in rules}
    # The producer requires these protections and permits an additional tag
    # non-fast-forward lock. It is visible hardening, not a substitute rule.
    _require(len(observed_kinds) == len(rules) and kinds <= observed_kinds <= kinds | {"non_fast_forward"},
             "ruleset_protection")
    for row in rules:
        kind = row["type"]
        parameters = row.get("parameters", {})
        _require(type(parameters) is dict, "ruleset_parameters")
        if kind == "pull_request":
            _require(type(parameters.get("required_approving_review_count")) is int
                     and parameters["required_approving_review_count"] == 0
                     and parameters.get("dismiss_stale_reviews_on_push") is True
                     and parameters.get("require_last_push_approval") is False, "ruleset_review_mode")
        elif kind == "required_status_checks":
            checks = parameters.get("required_status_checks")
            _require(parameters.get("strict_required_status_checks_policy") is True
                     and type(checks) is list and len(checks) == 1 and type(checks[0]) is dict
                     and checks[0].get("context") == "validate"
                     and type(checks[0].get("integration_id")) is int
                     and checks[0]["integration_id"] == CHECK_APP_ID
                     and parameters.get("do_not_enforce_on_create", False) is False, "ruleset_required_ci")
        else:
            _require(not parameters, "ruleset_parameters")
    bypass = None
    if "bypass_actors" in value:
        expected_bypass = [] if name in {"atlas-main", "atlas-history-lock", "atlas-bootstrap-lock"} else [
            {"actor_id": review.publisher_app_id, "actor_type": "Integration", "bypass_mode": "always"}]
        rows = value["bypass_actors"]
        _require(type(rows) is list and all(type(row) is dict and _integer(row.get("actor_id")) for row in rows)
                 and rows == expected_bypass, "ruleset_bypass")
        bypass = tuple((row["actor_id"], row["actor_type"], row["bypass_mode"]) for row in rows)
    visible = [{"type": row["type"], "parameters": row.get("parameters", {})} for row in rules]
    raw = json.dumps(sorted(visible, key=lambda row: row["type"]), sort_keys=True, separators=(",", ":")).encode()
    return PublicRulesetObservation(identifier, name, target, "active", included, raw, bypass)


async def verify_public_observations(
    provenance: VerifiedProvenance, *, expected: PublicObservationReviewExpectations,
    reader: source.GithubReader,
) -> VerifiedPublicObservations:
    """Evaluate public evidence with an operation-local bounded GithubReader.

    ``provenance`` must come from Phase 1's genuine verifier, not parsed DSSE or a
    downloaded receipt. Typed results, like Phase 1 results, are internal evidence
    boundaries rather than protection against arbitrary in-process Python code.
    Neither a schema-valid review candidate nor this return value approves trust.
    """
    review = _expectations(expected)
    run_id = _selection(provenance, review)
    started = source.utcnow()
    latest_path = f"/actions/runs/{run_id}"
    first_path = latest_path + "/attempts/1"
    latest = _run(await reader.publication_metadata(latest_path), latest_path, run_id, provenance, expected, review)
    first = _run(await reader.publication_metadata(first_path), first_path, run_id, provenance, expected, review)
    _require(latest.actor == first.actor, "actor_conflict")
    account = _account(await reader.publication_metadata("/users/" + latest.actor.login), review)
    _require(account == latest.actor, "account_conflict")
    value = _object(await reader.publication_metadata(f"/actions/workflows/{expected.workflow_id}"), "workflow")
    _require(_integer(value.get("id")) and value["id"] == expected.workflow_id
             and value.get("path") == WORKFLOW and value.get("state") == "active"
             and value.get("url") == f"{source.BASE}/actions/workflows/{expected.workflow_id}"
             and value.get("html_url") == f"{REPOSITORY_URI}/blob/main/{WORKFLOW}", "workflow")
    workflow = PublicWorkflowObservation(value["id"], WORKFLOW, "active", value["url"], value["html_url"])
    repository = _repository(await reader.publication_metadata(""), review)
    value = _object(await reader.publication_metadata("/branches/main"), "branch")
    commit = _object(value.get("commit"), "branch")
    _require(value.get("name") == "main" and value.get("protected") is True
             and type(commit.get("sha")) is str and re.fullmatch(r"[a-f0-9]{40}", commit["sha"]) is not None,
             "unprotected_main")
    # Historical selection source need not equal current main HEAD.
    branch = PublicBranchObservation("main", True, commit["sha"])
    value = _object(await reader.publication_metadata(
        f"/commits/{provenance.source_commit}/check-runs?check_name=validate&filter=latest&per_page=2&page=1"), "ci")
    checks = value.get("check_runs")
    _require(type(value.get("total_count")) is int and value["total_count"] == 1
             and type(checks) is list and len(checks) == 1 and type(checks[0]) is dict, "ci_count")
    check = checks[0]
    app = _object(check.get("app"), "ci")
    _require(_integer(check.get("id")) and check.get("name") == "validate"
             and check.get("head_sha") == provenance.source_commit and check.get("status") == "completed"
             and check.get("conclusion") == "success" and type(app.get("id")) is int
             and app["id"] == CHECK_APP_ID, "ci")
    ci = PublicCheckObservation(check["id"], "validate", provenance.source_commit, "completed", "success", CHECK_APP_ID)
    environment = _environment(await reader.publication_metadata("/environments/catalogue-publication"), review)
    value = _object(await reader.publication_metadata("/apps/" + review.publisher_app_slug), "publisher")
    owner = _object(value.get("owner"), "publisher")
    permissions = {"contents": "write", "actions": "read", "administration": "read", "metadata": "read"}
    _require(_integer(value.get("id")) and value["id"] == review.publisher_app_id
             and value.get("slug") == review.publisher_app_slug and _integer(owner.get("id"))
             and owner["id"] == review.owner_id and value.get("permissions") == permissions, "publisher")
    publisher = PublicPublisherObservation(value["id"], value["slug"], owner["id"], tuple(sorted(permissions.items())))
    listed = await reader.publication_metadata(RULESET_LIST)
    _require(type(listed) is list and len(listed) == 5, "ruleset_inventory")
    identities = dict(expected.rulesets.named())
    _require(all(type(row) is dict and type(row.get("name")) is str and row["name"] in identities for row in listed)
             and len({row["name"] for row in listed}) == 5, "ruleset_inventory")
    for row in listed:
        _ruleset_identity(row, row["name"], identities[row["name"]])
    rulesets = []
    for name, identifier in sorted(identities.items()):
        rulesets.append(_ruleset(await reader.publication_metadata(f"/rulesets/{identifier}?includes_parents=true"),
                                name, identifier, review))
    source.require(time.monotonic() < reader.deadline, "source_timeout")
    return VerifiedPublicObservations(provenance, expected, started, source.utcnow(), latest, first, account,
        workflow, repository, branch, ci, environment, publisher, tuple(rulesets))
