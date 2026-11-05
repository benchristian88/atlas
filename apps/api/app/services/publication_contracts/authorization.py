# SPDX-License-Identifier: Apache-2.0
"""One run-level security preflight. Parsing is never signature authentication."""
import time

from atlas_connector_sdk.contracts import strict_json
from .contract import (OWNER_ID, REPOSITORY, REPOSITORY_ID,
    PUBLICATION_WORKFLOW, canonical_json, check_authority, check_policy, check_rulesets,
    digest, hexadecimal, positive_integer, publisher_permissions, require)
from .rulesets import EXPECTED, validate_detail, validate_list

SCHEMA = "atlas-publication-preflight/v2"
WORKFLOW = ".github/workflows/catalogue-verifier.yml"
PREDICATE = "https://atlas-impact.dev/attestations/publication-preflight/v2"
SUBJECT = "preflight.json"
VERIFIER_APP_ID = 5424851
VERIFIER_INSTALLATION_ID = 174088125
PUBLISHER_APP_ID = 5422372
PUBLISHER_INSTALLATION_ID = 174027755
MAX_AUTHORIZATION_BYTES = 256 * 1024
MAX_REQUEST_BYTES = 16384
MAX_PREFLIGHT_AGE_SECONDS = 900
MAX_RUN_SECONDS = 1800
AUTHORITY = {"repository_id": REPOSITORY_ID, "owner_id": OWNER_ID,
    "maintainer_id": OWNER_ID, "publisher_app_id": PUBLISHER_APP_ID,
    "publisher_installation_id": PUBLISHER_INSTALLATION_ID,
    "verifier_app_id": VERIFIER_APP_ID, "verifier_installation_id": VERIFIER_INSTALLATION_ID}


def fields(value, names):
    require(isinstance(value, dict) and value.keys() == set(names), "authorization_fields")


def integer(value):
    require(positive_integer(value), "authorization_integer")


def hash_value(value, length=64):
    require(hexadecimal(value, length), "authorization_digest")


def parse(raw, maximum):
    require(type(raw) is bytes and 0 < len(raw) <= maximum, "authorization_size")
    value = strict_json(raw.decode("utf-8"), maximum=maximum)
    require(canonical_json(value) == raw, "authorization_noncanonical")
    return value


def check_trust(trust, *, acceptance_only=False):
    fields(trust, {"schema", "live_signer_accepted", "signer_revision", "ruleset_ids",
                   "verification_environment_id", "max_observation_age_seconds"})
    require(type(acceptance_only) is bool and trust["schema"] == "atlas-publication-verifier-trust/v2"
            and type(trust["live_signer_accepted"]) is bool
            and (trust["live_signer_accepted"] or acceptance_only), "verifier_live_acceptance_required")
    hash_value(trust["signer_revision"], 40)
    fields(trust["ruleset_ids"], EXPECTED)
    for identity in trust["ruleset_ids"].values():
        integer(identity)
    require(len(set(trust["ruleset_ids"].values())) == 5, "authorization_ruleset_ids")
    integer(trust["verification_environment_id"])
    require(type(trust["max_observation_age_seconds"]) is int
            and 1 <= trust["max_observation_age_seconds"] <= MAX_PREFLIGHT_AGE_SECONDS,
            "authorization_age_policy")


def check_publication_policy(policy, operation):
    check_policy(policy, operation=operation)
    require(policy["allowed_maintainer_id"] == OWNER_ID and policy["app_id"] == PUBLISHER_APP_ID
            and policy["app_installation_id"] == PUBLISHER_INSTALLATION_ID,
            "authorization_publication_identity")


def check_request(value):
    fields(value, {"source_commit", "policy_sha256", "run_id", "run_attempt", "operation", "acceptance_only"})
    hash_value(value["source_commit"], 40)
    hash_value(value["policy_sha256"])
    integer(value["run_id"])
    require(type(value["run_attempt"]) is int and value["run_attempt"] == 1, "authorization_attempt")
    require(type(value["operation"]) is str and value["operation"] in {"bootstrap", "publish", "recover"},
            "authorization_operation")
    require(type(value["acceptance_only"]) is bool, "authorization_acceptance_mode")
    return value


def dispatch_context(environ, operation, *, acceptance_only=False):
    expected = {"GITHUB_REPOSITORY": REPOSITORY, "GITHUB_REPOSITORY_ID": str(REPOSITORY_ID),
        "GITHUB_REPOSITORY_OWNER_ID": str(OWNER_ID), "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main", "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": REPOSITORY + "/" + PUBLICATION_WORKFLOW + "@refs/heads/main",
        "RUNNER_ENVIRONMENT": "github-hosted"}
    require(all(environ.get(k) == v for k, v in expected.items()), "verification_context")
    source, run = environ.get("GITHUB_SHA"), environ.get("GITHUB_RUN_ID", "")
    hash_value(source, 40)
    require(type(run) is str and run.isascii() and run.isdigit() and str(int(run)) == run,
            "verification_context")
    request = {"source_commit": source, "run_id": int(run), "run_attempt": 1,
               "operation": operation, "acceptance_only": acceptance_only, "policy_sha256": "0" * 64}
    check_request(request)
    return request


def workflow_identity(value, path):
    if type(value) is not str:
        return False
    workflow, separator, ref = value.partition("@")
    return workflow == path and separator == "@" and bool(ref) and "@" not in ref


def check_observations(observations, policy, operation, ids):
    require(isinstance(observations, list), "authorization_rulesets")
    listed = validate_list(observations)
    require(listed == ids, "authorization_ruleset_ids")
    require([row["name"] for row in observations] == sorted(EXPECTED), "authorization_ruleset_order")
    for row in observations:
        validate_detail(row, row["name"], listed[row["name"]])
    check_rulesets(policy, observations, operation=operation, include_bootstrap_lock=True)


def check_security(value, policy, request, trust):
    fields(value, {"repository", "branch", "environment", "run", "attempt", "workflow", "user", "checks",
                   "verification_environment", "publisher_app", "immutable_releases"})
    check_authority(policy, *(value[k] for k in
        ("repository", "branch", "environment", "run", "attempt", "workflow", "user", "checks")),
        run_id=request["run_id"], source_commit=request["source_commit"], operation=request["operation"])
    references = value["run"].get("referenced_workflows")
    require(isinstance(references, list) and len(references) == 1 and isinstance(references[0], dict)
        and references[0].get("path") == REPOSITORY + "/" + WORKFLOW + "@" + trust["signer_revision"]
        and references[0].get("sha") == trust["signer_revision"], "verification_reusable_workflow")
    app = value["publisher_app"]
    require(isinstance(app, dict) and type(app.get("id")) is int and app["id"] == PUBLISHER_APP_ID
        and app.get("slug") == policy["app_slug"] == "atlas-catalogue-publisher"
        and app.get("owner", {}).get("id") == OWNER_ID
        and app.get("permissions") == publisher_permissions(request["operation"],
            acceptance_only=request["acceptance_only"]),
        "verification_publisher_app")
    environment = value["verification_environment"]
    require(isinstance(environment, dict) and type(environment.get("id")) is int
        and environment["id"] == trust["verification_environment_id"]
        and environment.get("name") == "catalogue-verification" and environment.get("can_admins_bypass") is False
        and environment.get("deployment_branch_policy") == {"protected_branches": True, "custom_branch_policies": False}
        and isinstance(environment.get("protection_rules"), list)
        and all(isinstance(row, dict) for row in environment["protection_rules"])
        and not any(row.get("type") == "required_reviewers" for row in environment["protection_rules"]),
        "verification_environment")
    require(isinstance(value["immutable_releases"], dict)
            and value["immutable_releases"].get("enabled") is True, "verification_immutable_releases")


def check_authorization(value, trust, policy):
    fields(value, {"schema", "authority", "source", "execution", "rulesets", "security", "freshness"})
    require(value["schema"] == SCHEMA, "authorization_schema")
    fields(value["authority"], AUTHORITY)
    require(all(type(value["authority"][k]) is int and value["authority"][k] == v for k, v in AUTHORITY.items()),
            "authorization_authority")
    source, execution = value["source"], value["execution"]
    fields(source, {"commit", "policy_sha256", "verifier_revision", "signer_workflow"})
    require(source["verifier_revision"] == trust["signer_revision"] and source["signer_workflow"] == WORKFLOW,
            "authorization_signer")
    fields(execution, {"workflow", "run_id", "run_attempt", "operation", "acceptance_only"})
    check_trust(trust, acceptance_only=execution["acceptance_only"])
    require(execution["workflow"] == PUBLICATION_WORKFLOW, "authorization_workflow")
    request = check_request({"source_commit": source["commit"], "policy_sha256": source["policy_sha256"],
        **{k: execution[k] for k in ("run_id", "run_attempt", "operation", "acceptance_only")}})
    check_publication_policy(policy, request["operation"])
    check_security(value["security"], policy, request, trust)
    rules = value["rulesets"]
    fields(rules, {"ids", "observations", "sha256", "approved_bypass_actors"})
    require(canonical_json(rules["ids"]) == canonical_json(trust["ruleset_ids"])
        and canonical_json(rules["approved_bypass_actors"]) == canonical_json(EXPECTED), "authorization_ruleset_policy")
    check_observations(rules["observations"], policy, request["operation"], trust["ruleset_ids"])
    require(rules["sha256"] == digest(canonical_json(rules["observations"])), "authorization_ruleset_digest")
    fresh = value["freshness"]
    fields(fresh, {"observation_started", "observation_completed", "issued_at", "expires_at"})
    for timestamp in fresh.values():
        integer(timestamp)
    start, end, issued, expires = (fresh[k] for k in
        ("observation_started", "observation_completed", "issued_at", "expires_at"))
    require(start <= end <= issued < expires <= start + trust["max_observation_age_seconds"],
            "authorization_freshness_order")
    return request
