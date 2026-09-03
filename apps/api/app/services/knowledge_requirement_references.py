"""Validation and display helpers for database-driven completeness rules."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AssetType,
    CustomFieldDefinition,
    KnowledgeRequirementDefinition,
    RelationshipType,
)
from app.utils.json_values import to_json_value

SUPPORTED_RULE_TYPES = frozenset({
    "field_present", "field_value_in", "custom_field_present",
    "custom_field_value_in", "interface_exists", "interface_has_ip",
    "relationship_exists", "relationship_target_type",
    "minimum_relationship_count", "minimum_interface_count", "one_of",
    "explicit_state_or_exception", "freshness_within_days", "owner_exists",
    "service_field_present", "service_asset_dependency_exists",
    "service_dependency_exists", "service_business_function_exists",
    "criticality_rank",
})
SUPPORTED_ASSET_FIELDS = frozenset({
    "name", "asset_type", "hostname", "ip_address", "status", "vendor",
    "model", "description", "source",
})
SUPPORTED_SERVICE_FIELDS = frozenset({
    "name", "service_type_id", "purpose", "description", "lifecycle_status",
    "operational_status", "criticality_level_id", "rto_minutes", "rpo_minutes",
    "owner_name", "technical_contact", "support_group", "recovery_notes",
    "runbook_url", "documentation_url", "backup_notes", "notes",
})


def _uuid(value: Any, label: str, errors: list[str]) -> uuid.UUID | None:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError):
        errors.append(f"{label} must be a valid UUID")
        return None


def _uuid_list(config: dict, key: str, errors: list[str]) -> list[uuid.UUID]:
    raw = config.get(key, [])
    if not isinstance(raw, list):
        errors.append(f"{key} must be a list")
        return []
    return [item for value in raw if (item := _uuid(value, key, errors)) is not None]


def _missing_ids(db: Session, model, ids: list[uuid.UUID]) -> list[uuid.UUID]:
    if not ids:
        return []
    existing = set(db.scalars(select(model.id).where(model.id.in_(ids))))
    return [item for item in ids if item not in existing]


def validate_rule_config(
    db: Session, rule_type: str, config: Any, *, depth: int = 0
) -> tuple[bool, list[str], str]:
    errors: list[str] = []
    if rule_type not in SUPPORTED_RULE_TYPES:
        return False, [f"Unsupported rule type: {rule_type}"], "Invalid rule"
    if not isinstance(config, dict):
        return False, ["rule_config_json must be an object"], "Invalid rule"
    if depth > 3:
        return False, ["Nested rules cannot exceed three levels"], "Invalid rule"
    if rule_type == "owner_exists":
        return False, ["owner_exists is reserved until the ownership model is available"], "Requires an owner"

    if "applicable_criticality_rank_min" in config and (
        not isinstance(config["applicable_criticality_rank_min"], int)
        or config["applicable_criticality_rank_min"] < 0
    ):
        errors.append("applicable_criticality_rank_min must be a non-negative integer")

    if rule_type in {"field_present", "field_value_in", "explicit_state_or_exception"}:
        field = config.get("field")
        if field not in SUPPORTED_ASSET_FIELDS:
            errors.append("field must reference a supported Asset field")
        if rule_type != "field_present" and not isinstance(config.get("values"), list):
            errors.append("values must be a list")
    elif rule_type == "service_field_present":
        if config.get("field") not in SUPPORTED_SERVICE_FIELDS:
            errors.append("field must reference a supported Service field")
    elif rule_type in {"service_asset_dependency_exists", "service_dependency_exists", "service_business_function_exists"}:
        if not isinstance(config.get("minimum", 1), int) or config.get("minimum", 1) < 1:
            errors.append("minimum must be an integer of at least 1")
    elif rule_type == "criticality_rank":
        if not isinstance(config.get("minimum_rank"), int) or config.get("minimum_rank", -1) < 0:
            errors.append("minimum_rank must be a non-negative integer")
    elif rule_type in {"custom_field_present", "custom_field_value_in"}:
        field_id = _uuid(config.get("custom_field_definition_id"), "custom_field_definition_id", errors)
        if field_id:
            field = db.get(CustomFieldDefinition, field_id)
            if field is None:
                errors.append("Referenced Custom Field Definition does not exist")
            elif not field.active:
                errors.append("Referenced Custom Field Definition is inactive")
        if rule_type == "custom_field_value_in" and not isinstance(config.get("values"), list):
            errors.append("values must be a list")
    elif rule_type in {"interface_exists", "minimum_interface_count"}:
        if not isinstance(config.get("minimum", 1), int) or config.get("minimum", 1) < 1:
            errors.append("minimum must be an integer of at least 1")
    elif rule_type == "interface_has_ip":
        if not isinstance(config.get("minimum", 1), int) or config.get("minimum", 1) < 1:
            errors.append("minimum must be an integer of at least 1")
        families = config.get("allowed_address_families", ["ipv4", "ipv6"])
        if not isinstance(families, list) or not set(families).issubset({"ipv4", "ipv6"}):
            errors.append("allowed_address_families may contain only ipv4 and ipv6")
    elif rule_type in {"relationship_exists", "relationship_target_type", "minimum_relationship_count"}:
        relation_ids = _uuid_list(config, "relationship_type_ids", errors)
        if not relation_ids:
            errors.append("Select at least one Relationship Type")
        if missing := _missing_ids(db, RelationshipType, relation_ids):
            errors.append(f"Unknown Relationship Type IDs: {', '.join(map(str, missing))}")
        inactive_relationships = [item for item_id in relation_ids if (item := db.get(RelationshipType, item_id)) is not None and not item.active]
        if inactive_relationships:
            errors.append(f"Inactive Relationship Types: {', '.join(item.name for item in inactive_relationships)}")
        target_ids = _uuid_list(config, "allowed_target_asset_type_ids", errors)
        if missing := _missing_ids(db, AssetType, target_ids):
            errors.append(f"Unknown target Asset Type IDs: {', '.join(map(str, missing))}")
        inactive_types = [item for item_id in target_ids if (item := db.get(AssetType, item_id)) is not None and not item.active]
        if inactive_types:
            errors.append(f"Inactive target Asset Types: {', '.join(item.name for item in inactive_types)}")
        source_ids = _uuid_list(config, "allowed_source_asset_type_ids", errors)
        if missing := _missing_ids(db, AssetType, source_ids):
            errors.append(f"Unknown source Asset Type IDs: {', '.join(map(str, missing))}")
        inactive_source_types = [item for item_id in source_ids if (item := db.get(AssetType, item_id)) is not None and not item.active]
        if inactive_source_types:
            errors.append(f"Inactive source Asset Types: {', '.join(item.name for item in inactive_source_types)}")
        if config.get("direction", "outgoing") not in {"outgoing", "incoming", "either"}:
            errors.append("direction must be outgoing, incoming, or either")
        if not isinstance(config.get("minimum", 1), int) or config.get("minimum", 1) < 1:
            errors.append("minimum must be an integer of at least 1")
    elif rule_type == "one_of":
        rules = config.get("rules")
        if not isinstance(rules, list) or not 2 <= len(rules) <= 3:
            errors.append("one_of requires two or three nested rules")
        else:
            for index, nested in enumerate(rules, start=1):
                if not isinstance(nested, dict):
                    errors.append(f"Nested rule {index} must be an object")
                    continue
                valid, nested_errors, _ = validate_rule_config(
                    db,
                    nested.get("rule_type", ""),
                    nested.get("rule_config", {}),
                    depth=depth + 1,
                )
                if not valid:
                    errors.extend(f"Rule {index}: {error}" for error in nested_errors)
    elif rule_type == "freshness_within_days":
        if not isinstance(config.get("predicate"), str) or not config.get("predicate"):
            errors.append("predicate is required")
        if not isinstance(config.get("maximum_age_days"), int) or config.get("maximum_age_days", 0) < 1:
            errors.append("maximum_age_days must be an integer of at least 1")

    unless = config.get("unless")
    if unless is not None:
        if not isinstance(unless, dict):
            errors.append("unless must be a structured rule")
        else:
            valid, nested_errors, _ = validate_rule_config(
                db, unless.get("rule_type", ""), unless.get("rule_config", {}), depth=depth + 1
            )
            if not valid:
                errors.extend(f"Unless: {error}" for error in nested_errors)
    applicable = config.get("applicable_when")
    if applicable is not None and (
        not isinstance(applicable, dict)
        or applicable.get("field") not in SUPPORTED_ASSET_FIELDS
        or not isinstance(applicable.get("values"), list)
    ):
        errors.append("applicable_when requires a supported field and values list")
    return not errors, errors, interpret_rule(db, rule_type, config)


def interpret_rule(db: Session, rule_type: str, config: dict) -> str:
    minimum = config.get("minimum", 1)
    if rule_type == "field_present":
        return f"Requires Asset field {config.get('field', 'unknown')}"
    if rule_type == "service_field_present":
        return f"Requires Service field {config.get('field', 'unknown')}"
    if rule_type == "service_asset_dependency_exists":
        return f"Requires at least {minimum} active Asset dependency/dependencies"
    if rule_type == "service_dependency_exists":
        return f"Requires at least {minimum} active Service dependency/dependencies"
    if rule_type == "service_business_function_exists":
        return f"Requires at least {minimum} linked Business Function(s)"
    if rule_type == "criticality_rank":
        return f"Applies at criticality rank {config.get('minimum_rank', '?')} or higher"
    if rule_type == "field_value_in":
        return f"Requires {config.get('field', 'field')} to be one of {', '.join(map(str, config.get('values', [])))}"
    if rule_type.startswith("custom_field"):
        field = db.get(CustomFieldDefinition, _safe_uuid(config.get("custom_field_definition_id")))
        return f"Requires custom field {field.name if field else 'Unavailable'}"
    if rule_type.startswith("interface") or rule_type == "minimum_interface_count":
        role = config.get("interface_role")
        role_text = f" {role}" if role and not config.get("allow_any_role", True) else " matching"
        return f"Requires at least {minimum}{role_text} interface(s)"
    if "relationship" in rule_type:
        ids = [_safe_uuid(item) for item in config.get("relationship_type_ids", [])]
        names = [item.name for item_id in ids if item_id and (item := db.get(RelationshipType, item_id))]
        target_ids = [_safe_uuid(item) for item in config.get("allowed_target_asset_type_ids", [])]
        target_names = [item.name for item_id in target_ids if item_id and (item := db.get(AssetType, item_id))]
        target_text = f" to {', '.join(target_names)}" if target_names else ""
        return f"Requires at least {minimum} {config.get('direction', 'outgoing')} relationship(s): {', '.join(names) or 'Unavailable'}{target_text}"
    if rule_type == "one_of":
        return "Requires any one of the configured alternatives"
    if rule_type == "freshness_within_days":
        return f"Requires {config.get('predicate', 'knowledge')} observed within {config.get('maximum_age_days', '?')} days"
    if rule_type == "explicit_state_or_exception":
        return f"Requires an allowed {config.get('field', 'state')} or an explicit exception"
    return rule_type.replace("_", " ").title()


def _safe_uuid(value: Any) -> uuid.UUID | None:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def requirement_references_id(requirement: KnowledgeRequirementDefinition, reference_id: uuid.UUID) -> bool:
    def contains(value: Any) -> bool:
        if isinstance(value, dict):
            return any(contains(item) for item in value.values())
        if isinstance(value, list):
            return any(contains(item) for item in value)
        return _safe_uuid(value) == reference_id
    return requirement.asset_type_id == reference_id or requirement.service_type_id == reference_id or contains(requirement.rule_config_json)


def requirements_referencing(db: Session, reference_id: uuid.UUID) -> list[KnowledgeRequirementDefinition]:
    return [
        item for item in db.scalars(select(KnowledgeRequirementDefinition))
        if requirement_references_id(item, reference_id)
    ]


def invalidate_referencing_requirements(db: Session, reference_id: uuid.UUID, label: str) -> int:
    rows = requirements_referencing(db, reference_id)
    for item in rows:
        item.configuration_valid = False
        item.configuration_error = f"Referenced {label} is inactive"
    return len(rows)


def requirement_config_json(value: Any) -> dict[str, Any]:
    return to_json_value(value or {})
