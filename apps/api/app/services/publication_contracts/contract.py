# SPDX-License-Identifier: Apache-2.0
"""Publication policy and pure transitions. Validation is never authentication."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from atlas_connector_sdk.contracts import strict_json
from app.services.official_catalogue import MAX_CATALOGUE_BYTES, MAX_INTEGER, REPOSITORY, parse_official_catalogue
import json

def canonical_json(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
from app.services.connector_contracts import ConnectorPackageError

def positive_integer(value):
    return type(value) is int and 0 < value <= MAX_INTEGER

def validate_catalogue(value):
    return parse_official_catalogue(canonical_json(value)).document

REPOSITORY_ID = 1414494920
OWNER_ID = 93822871
SOURCE_REF = "refs/heads/main"
CHANNEL_REF = "refs/heads/catalogue-current"
API = f"https://api.github.com/repos/{REPOSITORY}"
POINTER_ENDPOINT = API + "/git/ref/heads/catalogue-current"
PUBLICATION_WORKFLOW = ".github/workflows/catalogue-publish.yml"
ENVIRONMENT = "catalogue-publication"
AUTHORIZATION_MODE = "single-maintainer-v1"
APP_PERMISSIONS = {"contents": "write", "actions": "read", "administration": "read", "metadata": "read"}
BOOTSTRAP_APP_PERMISSIONS = {**APP_PERMISSIONS, "workflows": "write"}
MAX_POINTER_BYTES = 1024
MAX_BUNDLE_BYTES = 1024 * 1024
POINTER_FIELDS = {"schema_version", "sequence", "release_tag", "release_id",
                  "asset_id", "sha256", "previous_pointer_sha256"}


class PublicationError(ConnectorPackageError, ValueError):
    """Stable diagnostics only; never interpolate provider responses or tokens."""


def require(condition, code):
    if not condition:
        raise PublicationError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def hexadecimal(value, length=64):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{%d}" % length, value) is not None


def snapshot_tag(sequence):
    require(positive_integer(sequence), "invalid_sequence")
    return f"catalogue-{sequence:06d}"


def parse_catalogue(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_CATALOGUE_BYTES, "catalogue_size")
    document = validate_catalogue(strict_json(raw, maximum=MAX_CATALOGUE_BYTES))
    require(canonical_json(document) == raw, "noncanonical_catalogue")
    return document


def pointer_bytes(value):
    require(isinstance(value, dict) and value.keys() == POINTER_FIELDS, "pointer_fields")
    require(value["schema_version"] == "1.0", "pointer_schema")
    for name in ("sequence", "release_id", "asset_id"):
        require(positive_integer(value[name]), "pointer_integer")
    require(value["release_tag"] == snapshot_tag(value["sequence"]), "pointer_tag")
    require(hexadecimal(value["sha256"]), "pointer_digest")
    previous = value["previous_pointer_sha256"]
    require((value["sequence"] == 1 and previous is None)
            or (value["sequence"] > 1 and hexadecimal(previous)), "pointer_predecessor")
    raw = canonical_json(value)
    require(len(raw) <= MAX_POINTER_BYTES, "pointer_size")
    return raw


def parse_pointer(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_POINTER_BYTES, "pointer_size")
    value = strict_json(raw, maximum=MAX_POINTER_BYTES)
    require(pointer_bytes(value) == raw, "noncanonical_pointer")
    return value


def retain_history(previous, candidate):
    """Full manifests and explicit tombstones persist; omission is not withdrawal."""
    def index(document):
        return {(e["manifest"]["id"], e["manifest"]["version"]): e for e in document["entries"]}
    old, new = index(previous), index(candidate)
    require(old.keys() <= new.keys(), "historical_entry_missing")
    for identity, entry in old.items():
        other = new[identity]
        require(all(entry[k] == other[k] for k in ("manifest", "release_tag", "release_asset_id")),
                "historical_identity_changed")
        require(entry["status"] != "withdrawn" or other["status"] == "withdrawn", "withdrawal_reactivated")


def sequence_transition(previous_raw, candidate_raw):
    """Contiguous allocation; equal sequence is only an exact-byte resume."""
    candidate = parse_catalogue(candidate_raw)
    if previous_raw is None:
        require(candidate["sequence"] == 1, "sequence_gap")
        return "first"
    previous = parse_catalogue(previous_raw)
    require(candidate["sequence"] >= previous["sequence"], "sequence_rollback")
    if candidate["sequence"] == previous["sequence"]:
        require(candidate_raw == previous_raw, "sequence_substitution")
        return "unchanged"
    require(previous["sequence"] < MAX_INTEGER, "sequence_exhausted")
    require(candidate["sequence"] == previous["sequence"] + 1, "sequence_gap")
    retain_history(previous, candidate)
    return "advance"


def pointer_transition(previous_raw, candidate_raw):
    candidate = parse_pointer(candidate_raw)
    if previous_raw is None:
        require(candidate["sequence"] == 1, "pointer_gap")
        return "first"
    previous = parse_pointer(previous_raw)
    require(candidate["sequence"] >= previous["sequence"], "pointer_rollback")
    if candidate["sequence"] == previous["sequence"]:
        require(previous_raw == candidate_raw, "pointer_substitution")
        return "unchanged"
    require(candidate["sequence"] == previous["sequence"] + 1, "pointer_gap")
    require(candidate["previous_pointer_sha256"] == digest(previous_raw), "pointer_chain_mismatch")
    return "advance"


@dataclass(frozen=True)
class Authority:
    """GitHub API policy observation, explicitly NOT cryptographic human proof."""
    run_id: int
    source_commit: str
    environment_id: int
    actor_id: int


def check_policy(policy, *, operation="publish", local=False):
    """No mode inference, dummy IDs, legacy reviewer fallback or implicit bootstrap."""
    require(isinstance(policy, dict) and type(policy.get("enabled")) is bool, "publication_disabled")
    require(local or policy["enabled"], "publication_disabled")
    require(operation in {"publish", "recover", "bootstrap"}, "unsupported_publication_operation")
    require(not local or operation == "bootstrap", "unsupported_local_operation")
    require(policy.get("authorization_mode") == AUTHORIZATION_MODE and "reviewer_ids" not in policy,
            "unsupported_authorization_mode")
    require(positive_integer(policy.get("allowed_maintainer_id")), "maintainer_unconfigured")
    for field in ("environment_id", "package_environment_id", "app_id", "app_installation_id", "app_bot_user_id"):
        require(positive_integer(policy.get(field)), "publication_identity_unconfigured")
    require(isinstance(policy.get("app_slug"), str)
            and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", policy["app_slug"]), "publication_app_unconfigured")
    require(policy["allowed_maintainer_id"] != policy["app_bot_user_id"], "unsupported_maintainer_identity")
    bootstrap = policy.get("bootstrap")
    if operation == "bootstrap":
        mode = policy.get("bootstrap_operation", "disabled")
        require(mode in {"disabled", "stage", "activate"}, "bootstrap_operation_disabled")
        require(local or mode != "disabled", "bootstrap_operation_disabled")
        if mode in {"disabled", "stage"}:
            require(bootstrap == {"sequence": None, "pointer_sha256": None}, "bootstrap_staging_pins_must_be_unset")
            return
        require(isinstance(bootstrap, dict) and type(bootstrap.get("sequence")) is int
                and bootstrap["sequence"] == 1, "bootstrap_sequence")
    require(isinstance(bootstrap, dict) and positive_integer(bootstrap.get("sequence"))
            and hexadecimal(bootstrap.get("pointer_sha256")), "approved_bootstrap_required")


def check_repository(repository):
    require(isinstance(repository, dict) and type(repository.get("id")) is int and repository["id"] == REPOSITORY_ID
            and isinstance(repository.get("owner"), dict) and type(repository["owner"].get("id")) is int
            and repository["owner"]["id"] == OWNER_ID
            and repository.get("full_name") == REPOSITORY and repository.get("private") is False,
            "publication_repository")


def publisher_permissions(operation, *, acceptance_only=False):
    """Exact temporary bootstrap profile; signer acceptance needs only baseline."""
    require(operation in {"publish", "recover", "bootstrap"} and type(acceptance_only) is bool,
            "unsupported_publication_operation")
    return BOOTSTRAP_APP_PERMISSIONS if operation == "bootstrap" and not acceptance_only else APP_PERMISSIONS


def check_app(policy, app, token_repositories, token_identity, *, operation="publish"):
    """Public App metadata plus JWT-authenticated pinned token-action observations.

    The action, not caller-supplied metadata alone, binds the actual key to the
    configured App/installation. Correct-but-stolen keys cannot be detected here;
    they still cannot satisfy the separate human dispatch and signature gates.
    """
    check_policy(policy, operation=operation)
    require(isinstance(app, dict) and type(app.get("id")) is int and app["id"] == policy["app_id"]
            and app.get("slug") == policy["app_slug"] and isinstance(app.get("owner"), dict)
            and app["owner"].get("id") == OWNER_ID
            and app.get("permissions") == publisher_permissions(operation),
            "publication_app_identity")
    require(isinstance(token_identity, dict) and type(token_identity.get("installation_id")) is int
            and token_identity == {"app_slug": policy["app_slug"], "installation_id": policy["app_installation_id"]},
            "publication_app_installation")
    require(isinstance(token_repositories, dict) and type(token_repositories.get("total_count")) is int
            and token_repositories["total_count"] == 1 and isinstance(token_repositories.get("repositories"), list)
            and len(token_repositories["repositories"]) == 1, "publication_app_scope")
    check_repository(token_repositories["repositories"][0])


def check_rulesets(policy, rulesets, *, operation="publish", include_bootstrap_lock=False):
    """Deliberately narrow supported configuration; unknown combinations fail shut."""
    check_policy(policy, operation=operation)
    require(isinstance(rulesets, list) and all(isinstance(r, dict) for r in rulesets), "publication_ruleset_evidence")
    required = {
        "atlas-main": ("branch", ["refs/heads/main"], {"pull_request", "required_status_checks", "deletion", "non_fast_forward"}),
        "atlas-catalogue-current": ("branch", [CHANNEL_REF], {"creation", "update", "deletion", "non_fast_forward"}),
        "atlas-history-lock": ("branch", [CHANNEL_REF], {"deletion", "non_fast_forward"}),
        "atlas-publication-tags": ("tag", ["refs/tags/catalogue-*", "refs/tags/*-v*"], {"creation", "update", "deletion"}),
    }
    if operation == "bootstrap" or include_bootstrap_lock:
        required["atlas-bootstrap-lock"] = ("tag", ["refs/tags/catalogue-bootstrap-root"], {"update", "deletion"})
    for name, (target, included, types) in required.items():
        matches = [r for r in rulesets if r.get("name") == name]
        require(len(matches) == 1, "publication_ruleset_missing")
        rule = matches[0]
        require(rule.get("target") == target and rule.get("enforcement") == "active"
                and rule.get("conditions") == {"ref_name": {"include": included, "exclude": []}}, "publication_ruleset_scope")
        bypass = [] if name in {"atlas-main", "atlas-history-lock", "atlas-bootstrap-lock"} else [{"actor_id": policy["app_id"], "actor_type": "Integration", "bypass_mode": "always"}]
        require(rule.get("bypass_actors") == bypass, "publication_ruleset_bypass")
        rules = rule.get("rules")
        require(isinstance(rules, list) and all(isinstance(r, dict) and isinstance(r.get("type"), str) for r in rules)
                and len({r["type"] for r in rules}) == len(rules), "publication_ruleset_evidence")
        require(types <= {r.get("type") for r in rules}, "publication_ruleset_protection")
        if name == "atlas-main":
            pr = next(r for r in rules if r["type"] == "pull_request")["parameters"]
            require(type(pr.get("required_approving_review_count")) is int
                    and pr["required_approving_review_count"] == 0 and pr.get("dismiss_stale_reviews_on_push") is True
                    and pr.get("require_last_push_approval") is False, "publication_source_review_mode")
            checks = next(r for r in rules if r["type"] == "required_status_checks")["parameters"]
            require(checks.get("strict_required_status_checks_policy") is True
                    and any(c.get("context") == "validate" and c.get("integration_id") == 15368
                            for c in checks.get("required_status_checks", [])),
                    "publication_required_checks")


def check_authority(policy, repository, branch, environment, run, attempt, workflow, user, checks,
                    *, run_id, source_commit, historical=False, package_tag=None, operation="publish"):
    """Compare independent API observations to external policy and authenticated context.

    Package runs authenticate the configured App's tag build, never human consent.
    Only the manual selection run constitutes single-maintainer authorization.
    """
    check_policy(policy, operation=operation)
    check_repository(repository)
    require(all(isinstance(value, dict) for value in (branch, environment, run, attempt, workflow, user, checks)),
            "missing_authority_evidence")
    require(branch.get("name") == "main" and branch.get("protected") is True, "unprotected_source_ref")
    require(positive_integer(run_id), "invalid_run_identity")
    require(hexadecimal(source_commit, 40), "invalid_source_commit")
    expected_workflow = ".github/workflows/release.yml" if package_tag else PUBLICATION_WORKFLOW
    event, source_branch = ("push", package_tag) if package_tag else ("workflow_dispatch", "main")
    ref = "refs/tags/" + package_tag if package_tag else SOURCE_REF
    expected_actor = policy["app_bot_user_id"] if package_tag else policy["allowed_maintainer_id"]
    expected_type = "Bot" if package_tag else "User"
    require(type(user.get("id")) is int and user["id"] == expected_actor and user.get("type") == expected_type
            and isinstance(user.get("login"), str) and bool(user["login"]), "unsupported_actor_identity")
    if package_tag:
        require(user["login"] == policy["app_slug"] + "[bot]", "publication_app_actor")
    observed_workflows = []
    for observed in (run, attempt):
        require(observed.get("id") == run_id and type(observed.get("id")) is int, "invalid_run_identity")
        require(type(observed.get("run_attempt")) is int and observed["run_attempt"] == 1,
                "fresh_dispatch_run_required")
        check_repository(observed.get("repository"))
        check_repository(observed.get("head_repository"))
        # GitHub returns either the path alone or path@ref. No loose prefix match.
        require(observed.get("event") == event and observed.get("head_branch") == source_branch
                and observed.get("path") in {expected_workflow, expected_workflow + "@" + ref,
                                             expected_workflow + "@" + source_branch},
                "untrusted_publication_run")
        require(observed.get("head_sha") == source_commit
                and (historical or branch.get("commit", {}).get("sha") == source_commit), "publication_source_changed")
        require(observed.get("url") == f"{API}/actions/runs/{run_id}"
                and observed.get("html_url") == f"https://github.com/{REPOSITORY}/actions/runs/{run_id}",
                "invalid_run_identity")
        for field in ("actor", "triggering_actor"):
            actor = observed.get(field)
            require(isinstance(actor, dict) and type(actor.get("id")) is int and actor["id"] == expected_actor
                    and actor.get("type") == expected_type and actor.get("login") == user["login"],
                    "unauthorized_triggering_identity")
        require(positive_integer(observed.get("workflow_id")), "untrusted_workflow_identity")
        observed_workflows.append(observed["workflow_id"])
    require(observed_workflows == [workflow.get("id"), workflow.get("id")]
            and type(workflow.get("id")) is int and workflow.get("path") == expected_workflow
            and workflow.get("state") == "active"
            and workflow.get("url") == f"{API}/actions/workflows/{workflow['id']}", "untrusted_workflow_identity")
    rows = checks.get("check_runs")
    require(type(checks.get("total_count")) is int and checks["total_count"] == 1
            and isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], dict), "required_ci_evidence")
    check = rows[0]
    require(check.get("name") == "validate" and check.get("head_sha") == source_commit
            and check.get("status") == "completed" and check.get("conclusion") == "success"
            and isinstance(check.get("app"), dict) and check["app"].get("id") == 15368, "required_ci_failed")
    environment_key = "package_environment_id" if package_tag else "environment_id"
    environment_name = "connector-release" if package_tag else ENVIRONMENT
    require(type(environment.get("id")) is int and environment.get("id") == policy[environment_key]
            and environment.get("name") == environment_name and environment.get("can_admins_bypass") is False,
            "unsupported_environment_protection")
    branch_policy = {"protected_branches": not bool(package_tag), "custom_branch_policies": bool(package_tag)}
    require(environment.get("deployment_branch_policy") == branch_policy, "unsupported_environment_branches")
    rules = environment.get("protection_rules")
    require(isinstance(rules, list) and all(isinstance(r, dict) for r in rules)
            and not any(r.get("type") == "required_reviewers" for r in rules), "unsupported_environment_reviewers")
    return Authority(run_id, source_commit, environment["id"], expected_actor)
