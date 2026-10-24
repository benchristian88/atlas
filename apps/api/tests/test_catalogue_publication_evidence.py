"""Real offline selection crypto, synthetic public HTTP observations.

Synthetic provider data tests public-field policy only; it never mocks signature
success or claims genuine provider/authorization acceptance. No live GitHub in CI.
"""
import asyncio
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import catalogue_publication_evidence as evidence, catalogue_source as source, trusted_catalogue
from app.services.catalogue_trust import parse_catalogue_trust_policy_candidate
from app.services.connector_verification import GithubSigstoreVerifier, VerificationEvidence
from app.services.official_catalogue import MAX_INTEGER
from app.services.official_provenance import TrustProfile
from tests.test_catalogue_source import Response, reader as http_reader
from tests.test_catalogue_trust import review_document

FIXTURES = Path(__file__).parent / "fixtures/official_catalogue"
RUN = 39896288128
SHA = "8ce0b80c74d6ceb8ce75ac7ec8693f5bba78b305"
WORKFLOW = ".github/workflows/catalogue-publish.yml"
LATEST = f"/actions/runs/{RUN}"
ATTEMPT = LATEST + "/attempts/1"
WORKFLOW_PATH = "/actions/workflows/401"
CHECKS = f"/commits/{SHA}/check-runs?check_name=validate&filter=latest&per_page=2&page=1"
ENVIRONMENT = "/environments/catalogue-publication"
APP = "/apps/review-candidate-app"
RULE_LIST = "/rulesets?includes_parents=true&per_page=6&page=1"


@pytest.fixture(scope="module")
def authenticated_selection():
    # Actual pinned verifier, unchanged genuine Phase 1 bytes/bundle/roots.
    return GithubSigstoreVerifier().verify_selection(
        (FIXTURES / "current.json").read_bytes(), (FIXTURES / "current.sigstore.json").read_bytes())


@pytest.fixture
def provider(review_document):
    expected = evidence.PublicObservationReviewExpectations(
        parse_catalogue_trust_policy_candidate(json.dumps(review_document).encode()),
        401, evidence.RulesetReviewIdentities(501, 502, 503, 504, 505))
    repository = {"id": 1414494920, "owner": {"id": 93822871},
                  "full_name": "benchristian88/atlas-connectors", "private": False}
    actor = {"id": 101, "login": "review-maintainer", "type": "User"}
    run = {"id": RUN, "run_attempt": 1, "event": "workflow_dispatch", "head_branch": "main",
        "head_sha": SHA, "repository": repository, "head_repository": repository,
        "url": source.BASE + LATEST, "html_url": f"https://github.com/{source.REPOSITORY}/actions/runs/{RUN}",
        "workflow_id": 401, "path": WORKFLOW, "actor": actor, "triggering_actor": actor}
    values = {
        LATEST: deepcopy(run), ATTEMPT: deepcopy(run), "/users/review-maintainer": deepcopy(actor),
        WORKFLOW_PATH: {"id": 401, "path": WORKFLOW, "state": "active", "url": source.BASE + WORKFLOW_PATH,
            "html_url": f"https://github.com/{source.REPOSITORY}/blob/main/{WORKFLOW}"},
        "": repository, "/branches/main": {"name": "main", "protected": True, "commit": {"sha": "c" * 40}},
        CHECKS: {"total_count": 1, "check_runs": [{"id": 601, "name": "validate", "head_sha": SHA,
            "status": "completed", "conclusion": "success", "app": {"id": 15368}}]},
        ENVIRONMENT: {"id": 201, "name": "catalogue-publication", "can_admins_bypass": False,
            "deployment_branch_policy": {"protected_branches": True, "custom_branch_policies": False},
            "protection_rules": [{"id": 701, "type": "branch_policy"}]},
        APP: {"id": 301, "slug": "review-candidate-app", "owner": {"id": 93822871},
            "permissions": {"contents": "write", "administration": "read", "actions": "read", "metadata": "read"}},
        RULE_LIST: [],
    }
    specs = [
        (501, "atlas-main", "branch", ["refs/heads/main"], [
            {"type": "pull_request", "parameters": {"required_approving_review_count": 0,
                "dismiss_stale_reviews_on_push": True, "require_last_push_approval": False}},
            {"type": "required_status_checks", "parameters": {"strict_required_status_checks_policy": True,
                "required_status_checks": [{"context": "validate", "integration_id": 15368}]}},
            {"type": "deletion"}, {"type": "non_fast_forward"}]),
        (502, "atlas-history-lock", "branch", ["refs/heads/catalogue-current"],
            [{"type": "deletion"}, {"type": "non_fast_forward"}]),
        (503, "atlas-bootstrap-lock", "tag", ["refs/tags/catalogue-bootstrap-root"],
            [{"type": "update"}, {"type": "deletion"}]),
        (504, "atlas-catalogue-current", "branch", ["refs/heads/catalogue-current"],
            [{"type": kind} for kind in ("creation", "update", "deletion", "non_fast_forward")]),
        (505, "atlas-publication-tags", "tag", ["refs/tags/catalogue-*", "refs/tags/*-v*"],
            [{"type": kind} for kind in ("creation", "update", "deletion")]),
    ]
    for identifier, name, target, include, rules in specs:
        identity = {"id": identifier, "name": name, "source_type": "Repository", "source": source.REPOSITORY,
                    "enforcement": "active"}
        values[RULE_LIST].append(deepcopy(identity))
        values[f"/rulesets/{identifier}?includes_parents=true"] = {**identity, "target": target,
            "conditions": {"ref_name": {"include": include, "exclude": []}}, "rules": rules}
    return expected, values


def evaluate(provider, authenticated_selection, *, overrides=None):
    expected, values = provider
    def respond(url):
        path = url.removeprefix(source.BASE) if url.startswith(source.BASE) else url.removeprefix(source.API)
        assert path in values, "Unexpected endpoint or untrusted remote URL"
        if overrides and path in overrides:
            return overrides[path]
        return Response(json.dumps(values[path]).encode())
    reader = http_reader(respond)
    result = asyncio.run(evidence.verify_public_observations(authenticated_selection, expected=expected, reader=reader))
    return result, reader


def test_consistent_public_observations_are_immutable_partial_evidence(provider, authenticated_selection):
    result, reader = evaluate(provider, authenticated_selection)
    assert result.selection_provenance is authenticated_selection
    assert authenticated_selection.profile is TrustProfile.SELECTION
    assert result.latest_run.run_id == result.first_attempt.run_id == RUN
    assert result.latest_run.actor == result.first_attempt.triggering_actor == result.account
    assert result.account.user_id == 101 != result.repository.owner_id
    assert result.branch.current_head_sha != SHA == result.source_ci.source_commit
    assert result.workflow.workflow_id == 401 and len(reader.session.calls) == 15
    assert result.observation_started_at <= result.observation_completed_at
    assert result.authorization_blockers == ("reviewed_ruleset_evidence_required", "consumer_trust_approval_required")
    assert all(row.bypass_actors is None for row in result.rulesets)
    assert not isinstance(result, (source.AuthenticatedCandidate, VerificationEvidence))
    for target, field in [(result, "authorization_blockers"), (result.latest_run, "run_id"),
                          (result.account, "login"), (result.rulesets[0], "visible_rules_json")]:
        with pytest.raises(FrozenInstanceError):
            setattr(target, field, None)
    provider[1][LATEST]["head_sha"] = "d" * 40
    assert result.latest_run.source_commit == SHA


@pytest.mark.parametrize("run_path", [LATEST, ATTEMPT])
@pytest.mark.parametrize("field,value,code", [
    ("id", RUN + 1, "run_identity"), ("id", str(RUN), "run_identity"),
    ("run_attempt", 2, "first_attempt_required"), ("run_attempt", None, "first_attempt_required"),
    ("run_attempt", True, "first_attempt_required"), ("run_attempt", 1.0, "first_attempt_required"),
    ("event", "push", "run_source"), ("head_sha", "a" * 40, "run_source"),
    ("head_branch", "feature/main", "run_source"), ("workflow_id", 402, "workflow"),
    ("path", WORKFLOW + ".evil", "workflow"), ("path", ".github/workflows/reusable.yml", "workflow"),
    ("url", source.BASE + ATTEMPT, "run_urls"),
    ("url", source.BASE + LATEST + "?x=1", "run_urls"),
    ("html_url", "https://github.com.evil.test/" + LATEST, "run_urls"),
    ("html_url", f"https://github.com/{source.REPOSITORY}" + ATTEMPT, "run_urls"),
])
def test_both_run_records_must_match_authenticated_context(provider, authenticated_selection, run_path, field, value, code):
    provider[1][run_path][field] = value
    with pytest.raises(source.SourceError, match="^publication_evidence_" + code + "$"):
        evaluate(provider, authenticated_selection)


@pytest.mark.parametrize("run_path", [LATEST, ATTEMPT])
@pytest.mark.parametrize("representation", [WORKFLOW, WORKFLOW + "@main", WORKFLOW + "@refs/heads/main"])
def test_only_supported_run_path_forms(provider, authenticated_selection, run_path, representation):
    provider[1][run_path]["path"] = representation
    evaluate(provider, authenticated_selection)


@pytest.mark.parametrize("path", [LATEST, ATTEMPT])
def test_omitted_attempt_rejects(provider, authenticated_selection, path):
    provider[1][path].pop("run_attempt")
    with pytest.raises(source.SourceError, match="publication_evidence_first_attempt_required"):
        evaluate(provider, authenticated_selection)


@pytest.mark.parametrize("endpoint,key", [("", None), (LATEST, "repository"), (LATEST, "head_repository"),
                                         (ATTEMPT, "repository"), (ATTEMPT, "head_repository")])
@pytest.mark.parametrize("mutation", ["id", "owner", "private", "name", "missing"])
def test_repository_and_head_repository_identities(provider, authenticated_selection, endpoint, key, mutation):
    value = provider[1][endpoint] if endpoint == "" else provider[1][endpoint][key]
    if mutation == "id":
        value["id"] += 1
    elif mutation == "owner":
        value["owner"]["id"] = True
    elif mutation == "private":
        value["private"] = True
    elif mutation == "name":
        value["full_name"] = "attacker/atlas-connectors"
    else:
        value.pop("owner")
    with pytest.raises(source.SourceError, match="publication_evidence_repository"):
        evaluate(provider, authenticated_selection)


@pytest.mark.parametrize("run_path", [LATEST, ATTEMPT])
@pytest.mark.parametrize("actor_field", ["actor", "triggering_actor"])
@pytest.mark.parametrize("mutation", ["wrong_id", "owner_as_maintainer", "bot", "app", "missing", "bad_login"])
def test_both_human_actor_observations(provider, authenticated_selection, run_path, actor_field, mutation):
    actor = deepcopy(provider[1][run_path][actor_field])
    if mutation == "wrong_id":
        actor["id"] = 102
    elif mutation == "owner_as_maintainer":
        actor["id"] = 93822871
    elif mutation in ("bot", "app"):
        actor["type"] = mutation.title()
    elif mutation == "missing":
        actor = None
    else:
        actor["login"] = "../review-maintainer?token=private"
    provider[1][run_path][actor_field] = actor
    with pytest.raises(source.SourceError, match="publication_evidence_actor"):
        evaluate(provider, authenticated_selection)


@pytest.mark.parametrize("target", ["original", "triggering", "attempt", "account"])
def test_conflicting_logins_with_same_numeric_id_fail(provider, authenticated_selection, target):
    if target == "account":
        provider[1]["/users/review-maintainer"]["login"] = "renamed"
    elif target == "attempt":
        provider[1][ATTEMPT]["actor"] = {"id": 101, "type": "User", "login": "renamed"}
        provider[1][ATTEMPT]["triggering_actor"] = {"id": 101, "type": "User", "login": "renamed"}
    else:
        key = "actor" if target == "original" else "triggering_actor"
        provider[1][LATEST][key] = {"id": 101, "type": "User", "login": "renamed"}
    with pytest.raises(source.SourceError, match="publication_evidence_(actor_conflict|account_conflict)"):
        evaluate(provider, authenticated_selection)


@pytest.mark.parametrize("field,value", [("id", 999), ("id", "101"), ("type", "Bot"), ("type", "App")])
def test_independent_account_lookup(provider, authenticated_selection, field, value):
    provider[1]["/users/review-maintainer"][field] = value
    with pytest.raises(source.SourceError, match="publication_evidence_actor"):
        evaluate(provider, authenticated_selection)


@pytest.mark.parametrize("field,value", [("id", 402), ("id", True), ("state", "disabled_manually"),
    ("path", WORKFLOW + "@main"), ("path", WORKFLOW + ".backup"), ("path", ".github/workflows/other.yml"),
    ("url", source.API + "/repos/attacker/fork/actions/workflows/401"),
    ("html_url", "https://evil.test/workflow")])
def test_independent_workflow_lookup(provider, authenticated_selection, field, value):
    provider[1][WORKFLOW_PATH][field] = value
    with pytest.raises(source.SourceError, match="publication_evidence_workflow"):
        evaluate(provider, authenticated_selection)


@pytest.mark.parametrize("mutation", ["none", "multiple", "count", "count_bool", "failed", "incomplete",
    "wrong_app", "bool_app", "wrong_sha", "wrong_name", "missing_app", "wrong_id"])
def test_source_validate_check_is_exact_and_unique(provider, authenticated_selection, mutation):
    checks = provider[1][CHECKS]
    check = checks["check_runs"][0]
    if mutation == "none":
        checks.update(total_count=0, check_runs=[])
    elif mutation == "multiple":
        checks["check_runs"].append(deepcopy(check))
        checks["total_count"] = 2
    elif mutation == "count":
        checks["total_count"] = 2
    elif mutation == "count_bool":
        checks["total_count"] = True
    elif mutation == "failed":
        check["conclusion"] = "failure"
    elif mutation == "incomplete":
        check["status"] = "in_progress"
    elif mutation in ("wrong_app", "bool_app"):
        check["app"]["id"] = 1 if mutation == "wrong_app" else True
    elif mutation == "wrong_sha":
        check["head_sha"] = "c" * 40
    elif mutation == "wrong_name":
        check["name"] = "Validate"
    elif mutation == "wrong_id":
        check["id"] = 1.0
    else:
        check.pop("app")
    with pytest.raises(source.SourceError, match="publication_evidence_ci"):
        evaluate(provider, authenticated_selection)


@pytest.mark.parametrize("field,value", [("protected", False), ("protected", 1), ("name", "other"),
                                        ("commit", {"sha": "invalid"})])
def test_protected_main_required(provider, authenticated_selection, field, value):
    provider[1]["/branches/main"][field] = value
    with pytest.raises(source.SourceError, match="publication_evidence_unprotected_main"):
        evaluate(provider, authenticated_selection)


@pytest.mark.parametrize("field,value", [("id", 202), ("name", "connector-release"), ("can_admins_bypass", True),
    ("protection_rules", []), ("protection_rules", [{"id": 1, "type": "required_reviewers", "reviewers": []}]),
    ("protection_rules", [{"id": 1, "type": "unknown"}]),
    ("deployment_branch_policy", {"protected_branches": True, "custom_branch_policies": True}),
    ("deployment_branch_policy", {"protected_branches": 1, "custom_branch_policies": False})])
def test_environment_identity_and_supported_rules(provider, authenticated_selection, field, value):
    provider[1][ENVIRONMENT][field] = value
    with pytest.raises(source.SourceError, match="publication_evidence_environment"):
        evaluate(provider, authenticated_selection)


@pytest.mark.parametrize("field,value", [("id", 999), ("slug", "other-app"), ("owner", {"id": 999}),
    ("permissions", {"contents": "write"}),
    ("permissions", {"contents": "write", "administration": "write", "actions": "read", "metadata": "read"}),
    ("permissions", {"contents": "write", "administration": "read", "actions": "read", "metadata": "read", "workflows": "write"})])
def test_publisher_identity_and_exact_public_permissions(provider, authenticated_selection, field, value):
    provider[1][APP][field] = value
    with pytest.raises(source.SourceError, match="publication_evidence_publisher"):
        evaluate(provider, authenticated_selection)


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "wrong_id", "disabled", "wrong_source"])
def test_ruleset_inventory_is_complete_and_pinned(provider, authenticated_selection, mutation):
    rows = provider[1][RULE_LIST]
    if mutation == "missing":
        rows.pop()
    elif mutation == "extra":
        rows.append(deepcopy(rows[0]))
    elif mutation == "duplicate":
        rows[-1] = deepcopy(rows[0])
    elif mutation == "wrong_id":
        rows[0]["id"] = 900
    elif mutation == "disabled":
        rows[0]["enforcement"] = "disabled"
    else:
        rows[0]["source"] = "attacker/fork"
    with pytest.raises(source.SourceError, match="publication_evidence_ruleset"):
        evaluate(provider, authenticated_selection)


@pytest.mark.parametrize("identifier", [501, 502, 503, 504, 505])
@pytest.mark.parametrize("mutation", ["id", "name", "enforcement", "scope", "protection", "bypass", "bypass_null"])
def test_each_ruleset_visible_protection_and_returned_bypass(provider, authenticated_selection, identifier, mutation):
    row = provider[1][f"/rulesets/{identifier}?includes_parents=true"]
    if mutation == "id":
        row["id"] = 999
    elif mutation == "name":
        row["name"] = "substitute"
    elif mutation == "enforcement":
        row["enforcement"] = "disabled"
    elif mutation == "scope":
        row["conditions"]["ref_name"]["exclude"] = ["refs/heads/main"]
    elif mutation == "protection":
        row["rules"].pop()
    elif mutation == "bypass_null":
        row["bypass_actors"] = None
    else:
        row["bypass_actors"] = [{"actor_id": 999, "actor_type": "Integration", "bypass_mode": "always"}]
    with pytest.raises(source.SourceError, match="publication_evidence_ruleset"):
        evaluate(provider, authenticated_selection)


@pytest.mark.parametrize("mutation", ["approvals", "last_push", "dismissal", "strict", "check_app", "check_name", "duplicate"])
def test_main_visible_rule_parameters(provider, authenticated_selection, mutation):
    rules = provider[1]["/rulesets/501?includes_parents=true"]["rules"]
    pr, checks = rules[0]["parameters"], rules[1]["parameters"]
    if mutation == "approvals":
        pr["required_approving_review_count"] = 1
    elif mutation == "last_push":
        pr["require_last_push_approval"] = True
    elif mutation == "dismissal":
        pr["dismiss_stale_reviews_on_push"] = False
    elif mutation == "strict":
        checks["strict_required_status_checks_policy"] = False
    elif mutation == "check_app":
        checks["required_status_checks"][0]["integration_id"] = True
    elif mutation == "check_name":
        checks["required_status_checks"][0]["context"] = "other"
    else:
        rules[-1] = deepcopy(rules[-2])
    with pytest.raises(source.SourceError, match="publication_evidence_ruleset"):
        evaluate(provider, authenticated_selection)


def test_visible_ci_creation_bypass_rejects(provider, authenticated_selection):
    provider[1]["/rulesets/501?includes_parents=true"]["rules"][1]["parameters"]["do_not_enforce_on_create"] = True
    with pytest.raises(source.SourceError, match="publication_evidence_ruleset_required_ci"):
        evaluate(provider, authenticated_selection)


@pytest.mark.parametrize("identifier", [503, 505])
def test_additional_tag_non_fast_forward_lock_supported(provider, authenticated_selection, identifier):
    provider[1][f"/rulesets/{identifier}?includes_parents=true"]["rules"].append({"type": "non_fast_forward"})
    result, _ = evaluate(provider, authenticated_selection)
    row = next(row for row in result.rulesets if row.ruleset_id == identifier)
    assert b"non_fast_forward" in row.visible_rules_json


def test_withheld_bypass_and_even_complete_public_arrays_cannot_authorize(provider, authenticated_selection):
    incomplete, _ = evaluate(provider, authenticated_selection)
    assert all(row.bypass_actors is None for row in incomplete.rulesets)
    for identifier in range(501, 506):
        provider[1][f"/rulesets/{identifier}?includes_parents=true"]["bypass_actors"] = [] if identifier <= 503 else [
            {"actor_id": 301, "actor_type": "Integration", "bypass_mode": "always"}]
    observed, _ = evaluate(provider, authenticated_selection)
    assert all(row.bypass_actors is not None for row in observed.rulesets)
    assert observed.authorization_blockers == incomplete.authorization_blockers
    with pytest.raises(source.SourceError, match="current_channel_policy_unavailable"):
        source.require_publication(SimpleNamespace(publication={"immutable": True, "observations": observed}))
    with pytest.raises(source.SourceError, match="publication_not_immutable"):
        source.require_publication(SimpleNamespace(publication={"immutable": False, "observations": observed}))
    with pytest.raises(source.SourceError, match="catalogue_evidence_mismatch"):
        trusted_catalogue._promote(None, None, SimpleNamespace(raw=(FIXTURES / "current.json").read_bytes(),
            provenance=authenticated_selection, publication={"immutable": True, "observations": observed}))


@pytest.mark.parametrize("expected", [None, {}, "single-maintainer-v1"])
def test_explicit_consumer_review_required_before_network(provider, authenticated_selection, expected):
    reader = http_reader(lambda _: pytest.fail("Missing review must fail before HTTP"))
    with pytest.raises(source.SourceError, match="publication_evidence_review_expectations_required"):
        asyncio.run(evidence.verify_public_observations(authenticated_selection, expected=expected, reader=reader))


def test_producer_responses_cannot_override_review(provider, authenticated_selection):
    # A consistent producer-selected actor is still the wrong reviewed authority.
    for path in (LATEST, ATTEMPT):
        for field in ("actor", "triggering_actor"):
            provider[1][path][field]["id"] = 999
        provider[1][path]["allowed_maintainer_id"] = 999
    provider[1]["/users/review-maintainer"]["id"] = 999
    with pytest.raises(source.SourceError, match="publication_evidence_actor"):
        evaluate(provider, authenticated_selection)
    assert provider[0].consumer_review.allowed_maintainer_id == 101


@pytest.mark.parametrize("value", [True, 1.0, "1", 0, -1, MAX_INTEGER + 1])
@pytest.mark.parametrize("target", ["workflow", "ruleset"])
def test_review_numeric_identity_types(provider, authenticated_selection, target, value):
    expected, values = provider
    expected = replace(expected, workflow_id=value) if target == "workflow" else replace(
        expected, rulesets=replace(expected.rulesets, main=value))
    with pytest.raises(source.SourceError, match="publication_evidence_review_"):
        evaluate((expected, values), authenticated_selection)


@pytest.mark.parametrize("field,value", [("profile", TrustProfile.CATALOGUE), ("repository_id", "999"),
    ("workflow_identity", "https://github.com/attacker/other"), ("source_commit", "bad"),
    ("invocation_uri", f"https://github.com/{source.REPOSITORY}/actions/runs/{RUN}/attempts/2")])
def test_structured_selection_context_checks_do_not_replace_crypto(provider, authenticated_selection, field, value):
    # Mutation of already verified evidence tests consistency checks, not crypto.
    with pytest.raises(source.SourceError, match="publication_evidence_"):
        evaluate(provider, replace(authenticated_selection, **{field: value}))


@pytest.mark.parametrize("response,code", [
    (Response(status=302, headers={"Location": source.BASE + LATEST}), "invalid_source_redirect"),
    (Response(b'{"id":1,"id":2}'), "invalid_source_metadata"),
    (Response(b'{"id":NaN}'), "invalid_source_metadata"),
    (Response(b"{malformed"), "invalid_source_metadata"),
    (Response(b"\xff"), "invalid_source_metadata"),
    (Response('{}'.encode('utf-16')), "invalid_source_metadata"),
    (Response(b'\xef\xbb\xbf{}'), "invalid_source_metadata"),
    (Response(b'{}', headers={"Link": '<https://attacker.test>; rel="next"'}), "incomplete_source_pagination"),
    (Response(b"x" * (source.METADATA_LIMIT + 1)), "source_response_too_large"),
    (Response(length=source.METADATA_LIMIT + 1), "source_response_too_large"),
    (Response(status=429, headers={"Retry-After": "300"}), "source_rate_limited"),
    (Response(status=403), "source_forbidden"), (Response(status=404), "source_not_found"),
    (Response(status=503, headers={"Retry-After": "120"}), "source_unavailable"),
])
def test_public_metadata_transport_fails_closed(provider, authenticated_selection, response, code):
    with pytest.raises(source.SourceError, match="^" + code + "$"):
        evaluate(provider, authenticated_selection, overrides={LATEST: response})


@pytest.mark.parametrize("path", ["https://api.github.com" + LATEST, "https://evil.test", "/repos/other/repo",
    "/actions/runs/01", "/actions/runs/1/attempts/2", "/actions/runs/1?x=1", "/actions/runs/1#x",
    "/users/../admin", "/users/name?x=1", "/users/" + "a" * 40, "/apps/a/other", "/apps/a%2fb",
    "/rulesets?per_page=100", "/rulesets/1", "/branches/other", "/commits/abc/check-runs",
    f"/actions/runs/{MAX_INTEGER + 1}", f"/actions/workflows/{MAX_INTEGER + 1}",
    f"/rulesets/{MAX_INTEGER + 1}?includes_parents=true", None])
def test_public_metadata_endpoint_allowlist(path):
    reader = http_reader(lambda _: pytest.fail("Invalid destination must fail before HTTP"))
    with pytest.raises(source.SourceError, match="invalid_source_destination"):
        asyncio.run(reader.publication_metadata(path))


@pytest.mark.parametrize("endpoint", [RULE_LIST, CHECKS])
def test_pagination_headers_reject_even_with_plausible_first_page(provider, authenticated_selection, endpoint):
    response = Response(json.dumps(provider[1][endpoint]).encode(), headers={
        "Link": '<https://api.github.com/somewhere?page=2>; rel="next"'})
    with pytest.raises(source.SourceError, match="incomplete_source_pagination"):
        evaluate(provider, authenticated_selection, overrides={endpoint: response})
