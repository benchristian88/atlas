import uuid

import pytest
from pydantic import ValidationError

from app.main import app
from app.models import (
    Base, CriticalityLevel, RelationshipType, Service, ServiceType,
)
from app.permissions import PERMISSIONS, ROLE_PERMISSION_KEYS, VIEWER
from app.routes.services import _applicable_relationship, _slug
from app.schemas import ServiceCreate
from app.services.knowledge_completeness import evaluate_service_rule


class ServiceRuleDatabase:
    def __init__(self, *records, scalar_value=0):
        self.records = {(type(record), record.id): record for record in records}
        self.scalar_value = scalar_value

    def get(self, model, record_id):
        return self.records.get((model, record_id))

    def scalar(self, statement):
        return self.scalar_value


def service_records(*, external=False):
    customer_id = uuid.uuid4()
    service_type = ServiceType(
        id=uuid.uuid4(), key="external_service" if external else "infrastructure_service",
        name="External Service" if external else "Infrastructure Service",
        active=True, system_defined=True, sort_order=10,
        requires_asset_dependency=not external,
    )
    criticality = CriticalityLevel(
        id=uuid.uuid4(), key="high", name="High", rank=75,
        default_rto_minutes=240, default_rpo_minutes=60,
        active=True, system_defined=True, sort_order=10,
    )
    service = Service(
        id=uuid.uuid4(), customer_id=customer_id, site_id=None,
        name="DNS", slug="dns", purpose="Resolve homelab names",
        service_type_id=service_type.id, criticality_level_id=criticality.id,
        lifecycle_status="active", operational_status="operational",
        source="manual",
    )
    return service_type, criticality, service


def test_service_schema_validates_recovery_values_and_urls():
    service_type, criticality, _ = service_records()
    values = {
        "customer_id": str(uuid.uuid4()), "name": "DNS",
        "service_type_id": service_type.id,
        "criticality_level_id": criticality.id,
        "rto_minutes": 0, "rpo_minutes": 15,
        "documentation_url": "https://docs.example.test/dns",
    }
    assert ServiceCreate.model_validate(values).rto_minutes == 0
    with pytest.raises(ValidationError):
        ServiceCreate.model_validate({**values, "rto_minutes": -1})
    with pytest.raises(ValidationError):
        ServiceCreate.model_validate({**values, "runbook_url": "javascript:alert(1)"})


def test_service_rules_support_fields_criticality_and_external_exception():
    service_type, criticality, service = service_records(external=True)
    db = ServiceRuleDatabase(service_type, criticality, service)
    assert evaluate_service_rule(db, service, "service_field_present", {"field": "purpose"}).satisfied
    assert evaluate_service_rule(db, service, "criticality_rank", {"minimum_rank": 75}).satisfied
    dependency = evaluate_service_rule(db, service, "service_asset_dependency_exists", {"minimum": 1})
    assert dependency.satisfied
    assert dependency.details["external_service_exception"] is True
    conditional = evaluate_service_rule(db, service, "service_field_present", {"field": "owner_name", "applicable_criticality_rank_min": 100})
    assert conditional.applicable is False


def test_service_rules_support_dependencies_and_one_of_without_executable_code():
    service_type, criticality, service = service_records()
    db = ServiceRuleDatabase(service_type, criticality, service, scalar_value=1)
    assert evaluate_service_rule(db, service, "service_asset_dependency_exists", {"minimum": 1}).satisfied
    assert evaluate_service_rule(db, service, "service_dependency_exists", {"minimum": 1}).satisfied
    assert evaluate_service_rule(db, service, "service_business_function_exists", {"minimum": 1}).satisfied
    one_of = evaluate_service_rule(db, service, "one_of", {"rules": [
        {"rule_type": "service_field_present", "rule_config": {"field": "technical_contact"}},
        {"rule_type": "service_field_present", "rule_config": {"field": "purpose"}},
    ]})
    assert one_of.satisfied


def test_relationship_applicability_is_required_for_typed_dependencies():
    relation = RelationshipType(
        id=uuid.uuid4(), key="runs_on", name="Runs on",
        source_label="Runs on", target_label="Hosts", directional=True,
        active=True, system_defined=True, sort_order=10,
        allowed_source_asset_type_keys=[], allowed_target_asset_type_keys=[],
    )
    db = ServiceRuleDatabase(relation, scalar_value=uuid.uuid4())
    assert _applicable_relationship(db, relation.id, "service", "asset") is relation
    db.scalar_value = None
    with pytest.raises(Exception) as error:
        _applicable_relationship(db, relation.id, "service", "business_function")
    assert getattr(error.value, "status_code", None) == 422


def test_c1_routes_permissions_and_slug_contract_are_registered():
    expected = {
        "/api/services": {"GET", "POST"},
        "/api/services/summary": {"GET"},
        "/api/services/{service_id}": {"GET", "PATCH"},
        "/api/services/{service_id}/asset-dependencies": {"GET", "POST"},
        "/api/services/{service_id}/service-dependencies": {"GET", "POST"},
        "/api/services/{service_id}/completeness": {"GET"},
        "/api/services/{service_id}/evaluate-completeness": {"POST"},
        "/api/services/{service_id}/graph": {"GET"},
        "/api/business-functions": {"GET", "POST"},
        "/api/service-types": {"GET", "POST"},
        "/api/criticality-levels": {"GET", "POST"},
    }
    for path, methods in expected.items():
        matches = [route.methods for route in app.routes if getattr(route, "path", None) == path]
        assert matches, path
        assert methods.issubset(set().union(*matches))
    for key in ("services.view", "services.create", "service_dependencies.manage", "business_functions.view", "service_types.manage", "criticality_levels.manage", "service_completeness.evaluate"):
        assert key in PERMISSIONS
    assert "services.view" in ROLE_PERMISSION_KEYS[VIEWER]
    assert "services.create" not in ROLE_PERMISSION_KEYS[VIEWER]
    assert _slug("Identity & Access") == "identity-access"


def test_service_dependency_database_constraint_rejects_self_reference_and_preserves_history_shape():
    dependencies = Base.metadata.tables["service_dependencies"]
    checks = " ".join(str(constraint.sqltext) for constraint in dependencies.constraints if hasattr(constraint, "sqltext"))
    assert "source_service_id <> target_service_id" in checks
    assert dependencies.c.valid_to.nullable
    assert dependencies.c.target_service_id.foreign_keys
