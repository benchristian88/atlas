"""Static I0 schema/specification validation, without runtime or Atlas mutations."""
from copy import deepcopy
from collections import defaultdict
import hashlib
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import quote, urlsplit

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

CONTRACTS = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((CONTRACTS / path).read_text())


from atlas_connector_sdk.contracts import schema_bytes
SCHEMAS = {name: json.loads(schema_bytes(name)) for name in ("aip-v1", "connector-manifest-v1")}
VALIDATORS = {name: Draft202012Validator(schema, format_checker=FormatChecker())
              for name, schema in SCHEMAS.items()}
MANIFESTS = {p.stem: json.loads(p.read_text()) for p in (CONTRACTS / "manifests").glob("*.json")}
FIXTURES = {p.stem: json.loads(p.read_text()) for p in (CONTRACTS / "fixtures").glob("*.json")}


def unique(rows, key, context):
    values = [row[key] for row in rows]
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {context}")
    return {row[key]: row for row in rows}


from atlas_connector_sdk.contracts import validate_manifest
from atlas_connector_sdk.aip import validate_batch, validate_example_stream, body_hash


@pytest.mark.parametrize("name", SCHEMAS)
def test_schemas_are_valid_draft_2020_12(name):
    Draft202012Validator.check_schema(SCHEMAS[name])


def test_required_format_validators_are_installed():
    assert {"date-time", "uri", "uuid"} <= FormatChecker().checkers.keys()


@pytest.mark.parametrize("manifest", MANIFESTS.values(), ids=MANIFESTS.keys())
def test_reference_manifests(manifest):
    validate_manifest(manifest)
    assert manifest["source_versions"]["qualification"] == "example"
    assert manifest["source_versions"]["qualified_versions"] == []
    assert manifest["capabilities"]["discover"] == "read_only"


@pytest.mark.parametrize("fixture", FIXTURES.values(), ids=FIXTURES.keys())
def test_aip_fixtures(fixture):
    validate_batch(fixture, MANIFESTS[fixture["connector"]["id"]])


def streams():
    grouped = defaultdict(list)
    for fixture in FIXTURES.values():
        grouped[fixture["run_id"]].append(fixture)
    return list(grouped.values())


@pytest.mark.parametrize("messages", streams(), ids=["proxmox-complete", "proxmox-partial", "proxmox-failed", "docker", "unifi"])
def test_complete_example_streams(messages):
    validate_example_stream(messages, MANIFESTS[messages[0]["connector"]["id"]])


@pytest.mark.parametrize("key", ["frontend", "javascript", "css", "html", "remote_ui", "ui_assets", "atlas_migrations"])
def test_manifests_reject_executable_frontend_and_migrations(key):
    bad = deepcopy(MANIFESTS["docker"])
    bad[key] = {"url": "https://example.test/executable.js"}
    assert not VALIDATORS["connector-manifest-v1"].is_valid(bad)


@pytest.mark.parametrize("key", ["playbook", "path", "git_url", "galaxy_identifier", "command", "arguments"])
def test_runtime_entry_points_do_not_accept_arbitrary_execution(key):
    bad = deepcopy(MANIFESTS["docker"])
    bad["implementation"]["entry_points"][key] = "arbitrary"
    assert not VALIDATORS["connector-manifest-v1"].is_valid(bad)


@pytest.mark.parametrize("key", ["customer_id", "site_id", "credentials", "token", "services", "business_functions", "playbook", "inventory"])
def test_aip_cannot_select_tenancy_credentials_business_or_runtime(key):
    bad = deepcopy(FIXTURES["docker-complete-1"])
    bad[key] = "forbidden-input"
    assert not VALIDATORS["aip-v1"].is_valid(bad)


@pytest.mark.parametrize("mutation", ["object", "relationship", "undeclared_fact", "wrong_type", "wrong_class", "wrong_cardinality", "wrong_value", "wrong_applicability", "atlas_type", "truth"])
def test_fixture_mutations_are_rejected(mutation):
    bad = deepcopy(FIXTURES["docker-complete-1"])
    entity = bad["assets"][2]
    fact = entity["facts"][0]
    if mutation == "object": entity["object_class"] = "docker.undeclared"
    elif mutation == "relationship": bad["relationships"][0]["relationship_class"] = "docker.undeclared"
    elif mutation == "undeclared_fact": fact["key"] = "docker.undeclared"
    elif mutation == "wrong_type": fact.update(value_type="integer", value=1)
    elif mutation == "wrong_class": fact["class"] = "operational"
    elif mutation == "wrong_cardinality": fact.update(cardinality="multi", value=["photos"])
    elif mutation == "wrong_value": fact["value"] = {"arbitrary": "blob"}
    elif mutation == "wrong_applicability": entity["facts"].append(bad["assets"][0]["facts"][0])
    elif mutation == "atlas_type": entity["asset_type"] = "application"
    elif mutation == "truth": bad["relationships"][0]["truth_classification"] = "declared"
    with pytest.raises((ValueError, ValidationError)):
        validate_batch(bad, MANIFESTS["docker"])


@pytest.mark.parametrize("key,value", [("default", "forbidden-secret-default"), ("options", ["forbidden-secret-option"])])
def test_secret_descriptors_cannot_contain_values(key, value):
    bad = deepcopy(MANIFESTS["proxmox"])
    bad["connection_fields"][2][key] = value
    assert not VALIDATORS["connector-manifest-v1"].is_valid(bad)


@pytest.mark.parametrize("status,completeness,mode,valid", [
    ("completed", "complete", "full", True), ("completed", "partial", "full", True),
    ("completed", "partial", "partial", True), ("failed", "failed", "full", True),
    ("cancelled", "unknown", "partial", True), ("failed", "complete", "full", False),
    ("completed", "complete", "partial", False), ("cancelled", "complete", "full", False),
])
def test_completion_maps_to_existing_lifecycle_gate(status, completeness, mode, valid):
    message = deepcopy(FIXTURES["proxmox-complete-completion"])
    message.update(status=status, completeness=completeness)
    message["coverage"]["snapshot_mode"] = mode
    if status == "failed": message["errors"] = [{"code": "source_unavailable"}]
    assert VALIDATORS["aip-v1"].is_valid(message) == valid
    if valid:
        # Existing service tests separately prove the database baseline semantics.
        run_fields = (status, mode == "full", completeness)
        assert (run_fields == ("completed", True, "complete")) == (status == "completed" and completeness == "complete")


def test_receipts_replay_and_cross_batch_reference_validation():
    messages = [deepcopy(FIXTURES[key]) for key in ("proxmox-complete-1", "proxmox-complete-2", "proxmox-complete-completion")]
    expected = validate_example_stream(messages, MANIFESTS["proxmox"])
    assert validate_example_stream(messages[::-1] + [deepcopy(messages[0])], MANIFESTS["proxmox"]) == expected
    with pytest.raises(ValueError, match="incomplete_receipts"):
        validate_example_stream(messages[1:], MANIFESTS["proxmox"])
    changed = deepcopy(messages[0]); changed["assets"][0]["name"] = "Changed"
    with pytest.raises(ValueError, match="conflicting_receipt"):
        validate_example_stream(messages + [changed], MANIFESTS["proxmox"])
    messages[1]["interfaces"][0]["asset_external_id"] = "unknown"
    with pytest.raises(ValueError, match="invalid_interface_binding"):
        validate_example_stream(messages, MANIFESTS["proxmox"])


def test_unchanged_identities_are_deterministic_and_container_recreation_keeps_workload():
    inputs = read("identity-examples.json")
    def identities(source):
        p, d, u = (source[k] for k in ("proxmox", "docker", "unifi-network"))
        engine, project, service = (quote(d[k], safe="") for k in ("engine_id", "project", "service"))
        return {"proxmox": [f"node/{quote(p['node'], safe='')}", f"qemu/{p['vmid']}", f"storage/{quote(p['storage'], safe='')}"],
                "docker": [f"engine/{engine}", f"engine/{engine}/project/{project}", f"engine/{engine}/project/{project}/service/{service}/replica/{d['replica_ordinal']}"],
                "unifi-network": [f"site/{quote(u['source_site_id'], safe='')}/device/{quote(k, safe='')}" for k in u["device_ids"]]}
    expected = identities(inputs)
    assert identities(read("identity-examples.json")) == expected
    for connector, ids in expected.items():
        fixtures = [row for row in FIXTURES.values() if row["connector"]["id"] == connector and row["run_id"] in {
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "cccccccc-cccc-4ccc-8ccc-cccccccccccc"}]
        assert set(ids) == {a["external_id"] for row in fixtures if row["message_type"] == "observations" for a in row["assets"]}
    recreated = deepcopy(inputs); recreated["docker"]["container_id"] = "fedcba9876543210" * 4
    assert identities(recreated)["docker"] == expected["docker"]
    docker = FIXTURES["docker-complete-1"]
    assert all(inputs["docker"]["container_id"] not in a["external_id"] for a in docker["assets"])
    assert next(f["value"] for f in docker["assets"][2]["facts"] if f["key"] == "docker.container_id") == inputs["docker"]["container_id"]


def test_unifi_is_infrastructure_only_and_auth_examples_match_policy():
    batch = FIXTURES["unifi-complete-1"]
    assert {a["object_class"] for a in batch["assets"]} == {"unifi.gateway", "unifi.switch", "unifi.access_point"}
    assert "client" not in json.dumps(batch).lower()
    assert {f["key"] for f in MANIFESTS["proxmox"]["connection_fields"] if f["secret"]} == {"token_secret"}
    assert {f["key"] for f in MANIFESTS["docker"]["connection_fields"] if f["secret"]} == {"ssh_private_key"}


def test_partial_warnings_and_manifest_capability_prevent_complete_seal():
    messages = [deepcopy(FIXTURES[key]) for key in ("proxmox-partial-1", "proxmox-partial-completion")]
    for message in messages:
        message["coverage"]["snapshot_mode"] = "full"
    messages[1]["completeness"] = "complete"
    with pytest.raises(ValueError, match="incomplete_coverage"):
        validate_example_stream(messages, MANIFESTS["proxmox"])
    messages = [deepcopy(FIXTURES[key]) for key in ("docker-complete-1", "docker-complete-completion")]
    manifest = deepcopy(MANIFESTS["docker"])
    manifest["capabilities"]["complete_snapshot"] = False
    with pytest.raises(ValueError, match="incomplete_coverage"):
        validate_example_stream(messages, manifest)


def test_inferred_relationship_is_valid_and_empty_complete_inventory_is_explicit():
    batch = deepcopy(FIXTURES["docker-complete-1"])
    batch["relationships"][0].update(truth_classification="inferred", confidence=0.8)
    validate_batch(batch, MANIFESTS["docker"])
    for domain in ("assets", "networks", "interfaces", "relationships"):
        batch[domain] = []
    completion = FIXTURES["docker-complete-completion"]
    assert all(not rows for rows in validate_example_stream([batch, completion], MANIFESTS["docker"]).values())
    missing_batch = deepcopy(completion)
    missing_batch["last_sequence"] = 0
    with pytest.raises(ValueError, match="missing_observation_batch"):
        validate_example_stream([missing_batch], MANIFESTS["docker"])


def test_interface_with_no_known_network_is_a_valid_canonical_observation():
    batch = deepcopy(FIXTURES["docker-complete-1"])
    batch["interfaces"][0].pop("network_external_id")
    validate_example_stream([batch, FIXTURES["docker-complete-completion"]], MANIFESTS["docker"])


@pytest.mark.parametrize("value", ["1.01.0", "1.0", "1.0.0-01", "latest"])
def test_connector_versions_are_exact_semver(value):
    bad = deepcopy(MANIFESTS["docker"])
    bad["version"] = value
    assert not VALIDATORS["connector-manifest-v1"].is_valid(bad)


@pytest.mark.parametrize("key,value", [("run_id", "invalid-uuid"), ("observed_at", "2026-99-99")])
def test_uuid_and_timestamp_formats_are_enforced(key, value):
    bad = deepcopy(FIXTURES["docker-complete-1"])
    bad[key] = value
    assert not VALIDATORS["aip-v1"].is_valid(bad)


def test_documentation_cannot_be_an_executable_url():
    bad = deepcopy(MANIFESTS["docker"])
    bad["display"]["documentation_uri"] = "javascript:alert(1)"
    assert not VALIDATORS["connector-manifest-v1"].is_valid(bad)


def test_example_observations_have_no_credential_value_fields():
    forbidden = {"credentials", "password", "token", "token_secret", "api_key", "private_key", "ssh_private_key"}
    for fixture in FIXTURES.values():
        assert not forbidden.intersection(key for key, _ in walk(fixture))


def walk(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def test_schema_and_examples_do_not_embed_secrets_or_ansible_domain_concepts():
    for value in [*SCHEMAS.values(), *MANIFESTS.values(), *FIXTURES.values(), read("identity-examples.json")]:
        encoded = json.dumps(value)
        assert not re.search(r"BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY|Bearer\s+\S+|PVEAPIToken=", encoded)
        for key, child in walk(value):
            if isinstance(child, str) and child.startswith(("http://", "https://")):
                assert urlsplit(child).username is None and urlsplit(child).password is None
    forbidden = {"playbook", "playbook_path", "inventory", "ansible_inventory", "ansible_command", "extra_vars", "galaxy_identifier"}
    assert not forbidden.intersection(key for key, _ in walk(SCHEMAS["aip-v1"]))
    for manifest in MANIFESTS.values():
        domain = {k: v for k, v in manifest.items() if k != "implementation"}
        assert not forbidden.intersection(key for key, _ in walk(domain))
        for field in manifest["connection_fields"]:
            if field["secret"]:
                assert not {"default", "options"}.intersection(field)
    # The schema domain must be runtime-neutral too; packaging metadata may name a runtime.
    schema = deepcopy(SCHEMAS["connector-manifest-v1"])
    schema["properties"].pop("implementation")
    assert not forbidden.intersection(key for key, _ in walk(schema))
