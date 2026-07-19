import uuid
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

from app.models import (
    Asset, AssetInterface, AssetRelationship, AssetType, CustomFieldDefinition,
    KnowledgeChange, KnowledgeCompletenessSummary, KnowledgeGap,
    KnowledgeRequirementDefinition, RelationshipType,
)
from app.services.knowledge_completeness import evaluate_asset, evaluate_asset_safely, evaluate_rule
from app.services.knowledge_requirement_references import validate_rule_config
from app.main import app


class CompletenessSession:
    def __init__(self, *records):
        self.records = list(records)

    def add(self, value):
        self.records.append(value)

    def flush(self):
        now = datetime.now(timezone.utc)
        for value in self.records:
            if getattr(value, "id", None) is None:
                value.id = uuid.uuid4()
            if hasattr(value, "created_at") and value.created_at is None:
                value.created_at = now
            if hasattr(value, "updated_at") and value.updated_at is None:
                value.updated_at = now

    def begin_nested(self):
        return nullcontext()

    def get(self, model, record_id):
        return next((value for value in self.records if isinstance(value, model) and value.id == record_id), None)

    def _entity(self, statement):
        return statement.column_descriptions[0]["entity"]

    def scalars(self, statement):
        model = self._entity(statement)
        description = statement.column_descriptions[0]
        if description.get("name") == "id" and getattr(description.get("expr"), "key", None) == "id":
            return [value.id for value in self.records if isinstance(value, model)]
        rows = [value for value in self.records if isinstance(value, model)]
        sql = str(statement)
        params = statement.compile().params
        def param(prefix):
            return next((value for key, value in params.items() if key.startswith(prefix)), None)
        if model is KnowledgeRequirementDefinition:
            rows = [value for value in rows if value.active and value.entity_type == "asset"]
        elif model is KnowledgeGap:
            entity_id = param("entity_id")
            requirement_id = param("requirement_definition_id")
            if entity_id: rows = [value for value in rows if value.entity_id == entity_id]
            if requirement_id and "NOT IN" not in sql: rows = [value for value in rows if value.requirement_definition_id == requirement_id]
            if "NOT IN" in sql:
                applicable = {value for value in params.values() if isinstance(value, uuid.UUID)}
                applicable.update(item for value in params.values() if isinstance(value, (list, tuple, set)) for item in value if isinstance(item, uuid.UUID))
                rows = [value for value in rows if value.requirement_definition_id not in applicable]
            elif "status IN" in sql:
                rows = [value for value in rows if value.status in {"open", "deferred", "exception"}]
        elif model is AssetInterface:
            asset_id = param("asset_id")
            if asset_id: rows = [value for value in rows if value.asset_id == asset_id]
        elif model is AssetRelationship:
            endpoint_ids = {value for value in params.values() if isinstance(value, uuid.UUID)}
            rows = [value for value in rows if value.source_asset_id in endpoint_ids or value.target_asset_id in endpoint_ids]
        elif model is CustomFieldDefinition:
            pass
        return rows

    def scalar(self, statement):
        model = self._entity(statement)
        if model is AssetType:
            key = next((value for value in statement.compile().params.values() if isinstance(value, str)), None)
            return next((value for value in self.records if isinstance(value, AssetType) and (key is None or value.key == key)), None)
        rows = self.scalars(statement)
        return rows[0] if rows else None


def records():
    customer_id, site_id = uuid.uuid4(), uuid.uuid4()
    asset_type = AssetType(id=uuid.uuid4(), key="workload", name="Workload", active=True, system_defined=False, sort_order=1)
    asset = Asset(id=uuid.uuid4(), workspace_id=uuid.uuid4(), customer_id=customer_id, site_id=site_id, name="docker01", asset_type="workload", status="active", source="manual", metadata_={})
    requirement = KnowledgeRequirementDefinition(id=uuid.uuid4(), key="workload_hostname", name="Hostname", entity_type="asset", asset_type_id=asset_type.id, requirement_level="required", severity="high", rule_type="field_present", rule_config_json={"field": "hostname"}, active=True, system_defined=False, sort_order=1, configuration_valid=True)
    return asset_type, asset, requirement


def test_repeated_evaluation_is_idempotent_and_resolves_automatically():
    asset_type, asset, requirement = records()
    db = CompletenessSession(asset_type, asset, requirement)
    first = evaluate_asset(db, asset)
    db.flush()
    assert first.completeness_status == "incomplete"
    assert len([row for row in db.records if isinstance(row, KnowledgeGap)]) == 1
    opened_changes = len([row for row in db.records if isinstance(row, KnowledgeChange) and row.change_type == "knowledge_gap_opened"])

    evaluate_asset(db, asset)
    assert len([row for row in db.records if isinstance(row, KnowledgeGap)]) == 1
    assert len([row for row in db.records if isinstance(row, KnowledgeChange) and row.change_type == "knowledge_gap_opened"]) == opened_changes

    asset.hostname = "docker01.home"
    final = evaluate_asset(db, asset)
    gap = next(row for row in db.records if isinstance(row, KnowledgeGap))
    assert gap.status == "resolved"
    assert final.completeness_status == "complete"


def test_interface_relationship_and_nested_rules_use_database_references():
    asset_type, asset, _ = records()
    relationship_type = RelationshipType(id=uuid.uuid4(), key="runs_on", name="Runs on", active=True, system_defined=False, directional=True, sort_order=1)
    target = Asset(id=uuid.uuid4(), workspace_id=asset.workspace_id, customer_id=asset.customer_id, site_id=asset.site_id, name="pve1", asset_type="workload", status="active", source="manual", metadata_={})
    interface = AssetInterface(id=uuid.uuid4(), asset_id=asset.id, name="eth0", ip_address="192.0.2.4", is_primary=True)
    edge = AssetRelationship(id=uuid.uuid4(), source_asset_id=asset.id, target_asset_id=target.id, customer_id=asset.customer_id, site_id=asset.site_id, relationship_type="runs_on", legacy_cross_context=False, metadata_={})
    db = CompletenessSession(asset_type, asset, target, interface, relationship_type, edge)
    assert evaluate_rule(db, asset, "interface_has_ip", {"minimum": 1}).satisfied
    result = evaluate_rule(db, asset, "relationship_exists", {"relationship_type_ids": [str(relationship_type.id)], "direction": "outgoing", "minimum": 1})
    assert result.satisfied
    assert evaluate_rule(db, asset, "one_of", {"rules": [{"rule_type": "field_present", "rule_config": {"field": "hostname"}}, {"rule_type": "interface_has_ip", "rule_config": {"minimum": 1}}]}).satisfied


def test_reference_validation_rejects_missing_ids_and_owner_rule_is_disabled():
    db = CompletenessSession()
    valid, errors, _ = validate_rule_config(db, "relationship_exists", {"relationship_type_ids": [str(uuid.uuid4())], "minimum": 1})
    assert not valid
    assert any("Unknown Relationship Type" in error for error in errors)
    valid, errors, _ = validate_rule_config(db, "owner_exists", {})
    assert not valid
    assert "reserved" in errors[0]


def test_levels_severity_exceptions_and_deactivation_drive_stable_statuses():
    asset_type, asset, requirement = records()
    requirement.requirement_level = "recommended"
    db = CompletenessSession(asset_type, asset, requirement)
    summary = evaluate_asset(db, asset)
    db.flush()
    assert summary.completeness_status == "operationally_complete"

    requirement.requirement_level = "required"
    requirement.severity = "critical"
    summary = evaluate_asset(db, asset)
    gap = next(row for row in db.records if isinstance(row, KnowledgeGap) and row.status == "open")
    assert summary.completeness_status == "critical_gaps"

    gap.status = "exception"
    gap.exception_reason = "Uses host networking"
    gap.exception_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    summary = evaluate_asset(db, asset)
    assert summary.completeness_status == "exception_accepted"
    assert summary.required_satisfied == 0

    gap.exception_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    summary = evaluate_asset(db, asset)
    assert gap.status == "open"
    assert summary.completeness_status == "critical_gaps"

    requirement.active = False
    summary = evaluate_asset(db, asset)
    assert gap.status == "superseded"
    assert summary.completeness_status == "complete"


def test_unexpected_evaluator_failure_records_not_evaluated_without_losing_asset():
    asset_type, asset, requirement = records()

    class FailingSession(CompletenessSession):
        failed = False
        def scalars(self, statement):
            if self._entity(statement) is KnowledgeRequirementDefinition and not self.failed:
                self.failed = True
                raise RuntimeError("broken rule storage")
            return super().scalars(statement)

    db = FailingSession(asset_type, asset, requirement)
    summary = evaluate_asset_safely(db, asset)
    assert db.get(Asset, asset.id) is asset
    assert summary.completeness_status == "not_evaluated"


def test_knowledge_completeness_api_surface_is_registered_under_single_origin_api():
    expected = {
        "/api/asset-types/{asset_type_id}/knowledge-requirements": {"GET", "POST"},
        "/api/knowledge-requirements/{requirement_id}": {"PATCH", "DELETE"},
        "/api/knowledge-requirements/validate": {"POST"},
        "/api/assets/{asset_id}/evaluate-completeness": {"POST"},
        "/api/assets/{asset_id}/completeness": {"GET"},
        "/api/knowledge-gaps": {"GET"},
        "/api/knowledge-gaps/summary": {"GET"},
    }
    for path, methods in expected.items():
        matching = [route.methods for route in app.routes if getattr(route, "path", None) == path]
        assert matching, path
        assert methods.issubset(set().union(*matching))
