"""Pin the approved file and exercise validation independently of a database."""
from hashlib import sha256
import json

import pytest

from app.services.homelab_catalogue import FIXTURE, load_catalogue, validate_catalogue


def test_exact_approved_catalogue():
    assert sha256(FIXTURE.read_bytes()).hexdigest() == "522ed04d254700308c4384554a7bb536a23db41c02f42796a0135296f2279b18"
    catalogue = load_catalogue()
    assert catalogue.versions == {
        "schema_version": 1, "content_version": "1.0.0", "catalogue_id": "atlas.homelab.capabilities",
    }
    assert len(catalogue.functions) == 8 and all(function.preselected for function in catalogue.functions)
    services = [service for function in catalogue.functions for service in function.services]
    assert len(services) == len(catalogue.associations) == 42
    assert sum(service.preselected for service in services) == 24
    assert sum(service.selection_tier == "extended" for service in services) == 18
    assert {service.criticality_name for service in services} == {"Medium"}


@pytest.mark.parametrize("change,match", [
    (lambda raw: raw.update(schema_version=2), "schema_version"),
    (lambda raw: raw["functions"].pop(), "at least 8"),
    (lambda raw: raw["functions"][0].update(sort_order=3), "order or default"),
    (lambda raw: raw["functions"][0].update(name=" \t\n "), "Value must not be blank"),
    (lambda raw: raw["functions"][0]["services"][0].update(name=" \t\n "), "Value must not be blank"),
    (lambda raw: raw["functions"][1]["services"][0].update(name="INTERNET / Access"), "generated Service slug"),
    (lambda raw: raw["functions"][0]["services"][0].update(service_type_name="Router"), "Unknown starter Service Type"),
    (lambda raw: raw["functions"][0]["services"][0].update(preselected=False), "Only Standard"),
    (lambda raw: raw["functions"][0]["services"][0].update(criticality_name="High"), "criticality_name"),
    (lambda raw: raw["functions"][0]["services"][1].update(id="svc.internet-access"), "distinct Service IDs"),
    (lambda raw: raw["associations"][0].update(service_id="svc.other"), "approved endpoints"),
    (lambda raw: raw["associations"].reverse(), "approved endpoints"),
])
def test_malformed_fixture_is_rejected(change, match):
    raw = json.loads(FIXTURE.read_bytes())
    change(raw)
    with pytest.raises(ValueError, match=match):
        validate_catalogue(json.dumps(raw).encode())


@pytest.mark.parametrize("duplicate", ["home connectivity", "  Home Connectivity\t", "\tHOME CONNECTIVITY  "])
def test_bundled_business_function_names_reject_case_and_whitespace_duplicates(duplicate):
    raw = json.loads(FIXTURE.read_bytes())
    raw["functions"][1]["name"] = duplicate
    with pytest.raises(ValueError, match="Duplicate Business Function name"):
        validate_catalogue(json.dumps(raw).encode())


def test_bundled_business_function_names_reject_postgres_unicode_collision():
    raw = json.loads(FIXTURE.read_bytes())
    raw["functions"][0]["name"] = "I"
    raw["functions"][1]["name"] = "İ"
    with pytest.raises(ValueError, match="Bundled Business Function names must contain only ASCII characters"):
        validate_catalogue(json.dumps(raw).encode())


def test_distinct_business_function_names_keep_their_trimmed_display_values():
    raw = json.loads(FIXTURE.read_bytes())
    raw["functions"][0]["name"] = "  Network Operations\t"
    raw["functions"][1]["name"] = "NETWORK SECURITY"
    catalogue = validate_catalogue(json.dumps(raw).encode())
    assert [function.name for function in catalogue.functions[:2]] == ["Network Operations", "NETWORK SECURITY"]


def test_ascii_rule_is_limited_to_bundled_business_function_names():
    raw = json.loads(FIXTURE.read_bytes())
    raw["functions"][0]["description"] = "Réseau domestique"
    raw["functions"][0]["services"][0]["name"] = "Accès Internet"
    catalogue = validate_catalogue(json.dumps(raw).encode())
    assert catalogue.functions[0].description == "Réseau domestique"
    assert catalogue.functions[0].services[0].name == "Accès Internet"


def test_duplicate_key_is_rejected_and_content_can_version_independently():
    raw = FIXTURE.read_bytes()
    with pytest.raises(ValueError, match="Duplicate"):
        validate_catalogue(raw.replace(b'"schema_version": 1', b'"schema_version": 1, "schema_version": 1'))
    catalogue = validate_catalogue(raw.replace(b'"1.0.0"', b'"1.1.0"'))
    assert catalogue.content_version == "1.1.0" and catalogue.schema_version == 1
