"""Deterministic, idempotent Asset knowledge-completeness evaluation."""

from __future__ import annotations

import ipaddress
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    Asset,
    AssetInterface,
    AssetRelationship,
    AssetType,
    KnowledgeAssertion,
    KnowledgeCompletenessSummary,
    KnowledgeGap,
    KnowledgeRequirementDefinition,
    RelationshipType,
)
from app.services.custom_fields import custom_field_values
from app.services.knowledge_changes import record_change
from app.services.knowledge_requirement_references import validate_rule_config
from app.utils.json_values import to_json_value

ACTIVE_GAP_STATUSES = {"open", "deferred", "exception"}
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RuleResult:
    satisfied: bool
    applicable: bool = True
    details: dict[str, Any] | None = None
    invalid: bool = False


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _custom_values(db: Session, asset: Asset) -> tuple[dict[str, Any], dict[uuid.UUID, Any]]:
    by_key = custom_field_values(db, asset)
    from app.models import CustomFieldDefinition
    by_id = {
        definition.id: by_key.get(definition.key)
        for definition in db.scalars(select(CustomFieldDefinition))
        if definition.key in by_key
    }
    return by_key, by_id


def _interfaces(db: Session, asset: Asset) -> list[AssetInterface]:
    return list(db.scalars(select(AssetInterface).where(AssetInterface.asset_id == asset.id)))


def _matching_interfaces(db: Session, asset: Asset, config: dict) -> list[AssetInterface]:
    rows = _interfaces(db, asset)
    role = config.get("interface_role")
    if role and not config.get("allow_any_role", True):
        rows = [row for row in rows if row.name.casefold() == str(role).casefold()]
    return rows


def _relationship_matches(db: Session, asset: Asset, config: dict) -> list[AssetRelationship]:
    rows = list(db.scalars(select(AssetRelationship).where(or_(
        AssetRelationship.source_asset_id == asset.id,
        AssetRelationship.target_asset_id == asset.id,
    ))))
    direction = config.get("direction", "outgoing")
    if direction == "outgoing":
        rows = [row for row in rows if row.source_asset_id == asset.id]
    elif direction == "incoming":
        rows = [row for row in rows if row.target_asset_id == asset.id]
    relation_ids = []
    for raw in config.get("relationship_type_ids", []):
        try:
            relation_ids.append(uuid.UUID(str(raw)))
        except ValueError:
            continue
    allowed_keys = {
        item.key for item_id in relation_ids
        if (item := db.get(RelationshipType, item_id)) is not None and item.active
    }
    rows = [row for row in rows if row.relationship_type in allowed_keys]
    allowed_type_ids = []
    for raw in config.get("allowed_target_asset_type_ids", []):
        try:
            allowed_type_ids.append(uuid.UUID(str(raw)))
        except ValueError:
            continue
    if allowed_type_ids:
        allowed_keys = {
            item.key for item_id in allowed_type_ids
            if (item := db.get(AssetType, item_id)) is not None and item.active
        }
        filtered = []
        for row in rows:
            other_id = row.target_asset_id if row.source_asset_id == asset.id else row.source_asset_id
            other = db.get(Asset, other_id)
            if other and other.asset_type in allowed_keys:
                filtered.append(row)
        rows = filtered
    allowed_source_type_ids = []
    for raw in config.get("allowed_source_asset_type_ids", []):
        try:
            allowed_source_type_ids.append(uuid.UUID(str(raw)))
        except ValueError:
            continue
    if allowed_source_type_ids:
        allowed_source_keys = {
            item.key for item_id in allowed_source_type_ids
            if (item := db.get(AssetType, item_id)) is not None and item.active
        }
        rows = [
            row for row in rows
            if (source := db.get(Asset, row.source_asset_id)) is not None
            and source.asset_type in allowed_source_keys
        ]
    return rows


def evaluate_rule(
    db: Session,
    asset: Asset,
    rule_type: str,
    config: dict[str, Any],
    *,
    depth: int = 0,
) -> RuleResult:
    valid, errors, _ = validate_rule_config(db, rule_type, config, depth=depth)
    if not valid:
        return RuleResult(False, details={"configuration_errors": errors}, invalid=True)
    applicable = config.get("applicable_when")
    if applicable and getattr(asset, applicable["field"], None) not in applicable["values"]:
        return RuleResult(True, applicable=False, details={"reason": "Applicability condition did not match"})
    unless = config.get("unless")
    if unless:
        waived = evaluate_rule(db, asset, unless["rule_type"], unless.get("rule_config", {}), depth=depth + 1)
        if waived.satisfied and waived.applicable:
            return RuleResult(True, details={"reason": "Unless condition satisfied", "unless": waived.details})

    if rule_type == "field_present":
        value = getattr(asset, config["field"], None)
        satisfied = not _blank(value) if not config.get("allow_blank", False) else value is not None
        return RuleResult(satisfied, details={"field": config["field"], "value": value})
    if rule_type in {"field_value_in", "explicit_state_or_exception"}:
        value = getattr(asset, config["field"], None)
        return RuleResult(value in config["values"], details={"field": config["field"], "value": value, "allowed_values": config["values"]})
    if rule_type in {"custom_field_present", "custom_field_value_in"}:
        _, by_id = _custom_values(db, asset)
        field_id = uuid.UUID(str(config["custom_field_definition_id"]))
        value = by_id.get(field_id)
        satisfied = not _blank(value)
        if rule_type == "custom_field_value_in":
            satisfied = value in config["values"]
        return RuleResult(satisfied, details={"custom_field_definition_id": field_id, "value": value})
    if rule_type in {"interface_exists", "minimum_interface_count"}:
        count = len(_matching_interfaces(db, asset, config))
        return RuleResult(count >= config.get("minimum", 1), details={"matching_count": count, "minimum": config.get("minimum", 1)})
    if rule_type == "interface_has_ip":
        families = set(config.get("allowed_address_families", ["ipv4", "ipv6"]))
        matches = []
        for interface in _matching_interfaces(db, asset, config):
            if not interface.ip_address or (config.get("require_primary") and not interface.is_primary):
                continue
            try:
                family = "ipv4" if ipaddress.ip_address(interface.ip_address).version == 4 else "ipv6"
            except ValueError:
                continue
            if family in families:
                matches.append(interface)
        return RuleResult(len(matches) >= config.get("minimum", 1), details={"matching_count": len(matches), "minimum": config.get("minimum", 1), "address_families": sorted(families)})
    if rule_type in {"relationship_exists", "relationship_target_type", "minimum_relationship_count"}:
        rows = _relationship_matches(db, asset, config)
        return RuleResult(len(rows) >= config.get("minimum", 1), details={"matching_count": len(rows), "minimum": config.get("minimum", 1), "direction": config.get("direction", "outgoing")})
    if rule_type == "one_of":
        results = [evaluate_rule(db, asset, item["rule_type"], item.get("rule_config", {}), depth=depth + 1) for item in config["rules"]]
        return RuleResult(any(item.satisfied for item in results), details={"alternatives": [to_json_value(item.details) for item in results]})
    if rule_type == "freshness_within_days":
        accepted_truth = config.get("accepted_truth_classifications", ["observed", "declared"])
        assertion = db.scalar(select(KnowledgeAssertion).where(
            KnowledgeAssertion.subject_type == "asset",
            KnowledgeAssertion.subject_id == asset.id,
            KnowledgeAssertion.predicate == config["predicate"],
            KnowledgeAssertion.truth_classification.in_(accepted_truth),
            KnowledgeAssertion.retracted_at.is_(None),
            or_(KnowledgeAssertion.is_accepted.is_(True), KnowledgeAssertion.is_source_current.is_(True)),
        ).order_by(KnowledgeAssertion.last_observed_at.desc()))
        cutoff = datetime.now(timezone.utc) - timedelta(days=config["maximum_age_days"])
        return RuleResult(bool(assertion and assertion.last_observed_at >= cutoff), details={"predicate": config["predicate"], "last_observed_at": assertion.last_observed_at if assertion else None, "maximum_age_days": config["maximum_age_days"], "gap_kind": "stale" if assertion else "absent"})
    return RuleResult(False, details={"configuration_errors": ["Rule is not available"]}, invalid=True)


def _gap_response_summary(requirement: KnowledgeRequirementDefinition, asset: Asset) -> str:
    return f"{asset.name} is missing {requirement.name.lower()}."


def _change(db: Session, *, asset: Asset, gap: KnowledgeGap | None, change_type: str, summary: str, actor_user_id: uuid.UUID | None = None, previous: Any = None, new: Any = None) -> None:
    record_change(db, customer_id=asset.customer_id, site_id=asset.site_id, change_type=change_type, entity_type="asset", entity_id=asset.id, entity_name=asset.name, predicate="knowledge_completeness", previous_value=previous, new_value=new, actor_user_id=actor_user_id, summary=summary, metadata={"knowledge_gap_id": gap.id if gap else None, "requirement_definition_id": gap.requirement_definition_id if gap else None})


def _active_gap(db: Session, requirement_id: uuid.UUID, asset_id: uuid.UUID) -> KnowledgeGap | None:
    return db.scalar(select(KnowledgeGap).where(
        KnowledgeGap.requirement_definition_id == requirement_id,
        KnowledgeGap.entity_type == "asset",
        KnowledgeGap.entity_id == asset_id,
        KnowledgeGap.status.in_(ACTIVE_GAP_STATUSES),
    ))


def evaluate_asset(
    db: Session,
    asset_or_id: Asset | uuid.UUID,
    *,
    trigger_context: str | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> KnowledgeCompletenessSummary:
    asset = asset_or_id if isinstance(asset_or_id, Asset) else db.get(Asset, asset_or_id)
    if asset is None:
        raise ValueError("Asset not found")
    now = datetime.now(timezone.utc)
    asset_type = db.scalar(select(AssetType).where(AssetType.key == asset.asset_type))
    requirements = list(db.scalars(select(KnowledgeRequirementDefinition).where(
        KnowledgeRequirementDefinition.entity_type == "asset",
        KnowledgeRequirementDefinition.active.is_(True),
        or_(
            KnowledgeRequirementDefinition.asset_type_id.is_(None),
            KnowledgeRequirementDefinition.asset_type_id == (asset_type.id if asset_type else None),
        ),
    ).order_by(KnowledgeRequirementDefinition.sort_order, KnowledgeRequirementDefinition.name)))
    applicable_ids: set[uuid.UUID] = set()
    counts = {"required_total": 0, "required_satisfied": 0, "recommended_total": 0, "recommended_satisfied": 0}

    for requirement in requirements:
        try:
            result = evaluate_rule(db, asset, requirement.rule_type, requirement.rule_config_json or {})
        except Exception as exc:  # one malformed rule must not break the entity
            result = RuleResult(False, details={"configuration_errors": [str(exc)]}, invalid=True)
        requirement.configuration_valid = not result.invalid
        requirement.configuration_error = "; ".join((result.details or {}).get("configuration_errors", [])) or None
        if not result.applicable:
            gap = _active_gap(db, requirement.id, asset.id)
            if gap:
                previous_gap_status = gap.status
                gap.status = "superseded"
                gap.resolution_reason = "Requirement is no longer applicable"
                gap.resolved_at = now
                gap.last_state_changed_at = now
                gap.last_evaluated_at = now
                _change(
                    db, asset=asset, gap=gap,
                    change_type="knowledge_requirement_changed",
                    summary=f"{requirement.name} no longer applies to {asset.name}.",
                    actor_user_id=actor_user_id,
                    previous=previous_gap_status, new="superseded",
                )
            continue
        applicable_ids.add(requirement.id)
        category = "recommended" if requirement.requirement_level == "recommended" else "required"
        counts[f"{category}_total"] += 1
        gap = _active_gap(db, requirement.id, asset.id)
        if gap and gap.status == "exception" and gap.exception_expires_at and gap.exception_expires_at <= now:
            gap.status = "open"
            gap.last_state_changed_at = now
            _change(db, asset=asset, gap=gap, change_type="knowledge_gap_exception_expired", summary=f"Exception expired: {gap.summary}", previous="exception", new="open")
        if gap and gap.status == "deferred" and gap.deferred_until and gap.deferred_until <= now:
            gap.status = "open"
            gap.last_state_changed_at = now
        active_exception = bool(gap and gap.status == "exception" and (gap.exception_expires_at is None or gap.exception_expires_at > now))
        if result.satisfied:
            # An explicit exception remains an exception until it is reopened;
            # do not silently roll it into the naturally-satisfied count.
            if not active_exception:
                counts[f"{category}_satisfied"] += 1
            if gap and not active_exception:
                gap.status = "resolved"
                gap.resolved_at = now
                gap.resolution_reason = "Automatically satisfied by current operational knowledge"
                gap.last_state_changed_at = now
                gap.last_evaluated_at = now
                _change(db, asset=asset, gap=gap, change_type="knowledge_gap_resolved", summary=f"{asset.name} now satisfies {requirement.name.lower()}.", previous="open", new="resolved")
            elif gap:
                gap.last_evaluated_at = now
            continue
        if gap is None:
            gap = KnowledgeGap(
                customer_id=asset.customer_id, site_id=asset.site_id,
                requirement_definition_id=requirement.id, entity_type="asset",
                entity_id=asset.id, asset_type_id_snapshot=asset_type.id if asset_type else None,
                status="open", severity=requirement.severity,
                requirement_level=requirement.requirement_level,
                summary=_gap_response_summary(requirement, asset),
                details_json=to_json_value({**(result.details or {}), "why_it_applies": requirement.description, "trigger_context": trigger_context, "configuration_invalid": result.invalid}),
                first_detected_at=now, last_evaluated_at=now, last_state_changed_at=now,
            )
            db.add(gap)
            db.flush()
            _change(db, asset=asset, gap=gap, change_type="knowledge_gap_opened", summary=gap.summary, previous=None, new="open")
        else:
            gap.last_evaluated_at = now
            gap.details_json = to_json_value({**(result.details or {}), "why_it_applies": requirement.description, "trigger_context": trigger_context, "configuration_invalid": result.invalid})
            gap.severity = requirement.severity
            gap.requirement_level = requirement.requirement_level

    for obsolete in db.scalars(select(KnowledgeGap).where(
        KnowledgeGap.entity_type == "asset", KnowledgeGap.entity_id == asset.id,
        KnowledgeGap.status.in_(ACTIVE_GAP_STATUSES),
        KnowledgeGap.requirement_definition_id.not_in(applicable_ids or {uuid.UUID(int=0)}),
    )):
        previous_gap_status = obsolete.status
        obsolete.status = "superseded"
        obsolete.resolution_reason = "Asset profile or requirement applicability changed"
        obsolete.resolved_at = now
        obsolete.last_evaluated_at = now
        obsolete.last_state_changed_at = now
        _change(
            db, asset=asset, gap=obsolete,
            change_type="knowledge_requirement_changed",
            summary=f"{asset.name} no longer has an applicable requirement for {obsolete.summary}",
            actor_user_id=actor_user_id, previous=previous_gap_status, new="superseded",
        )

    active_gaps = list(db.scalars(select(KnowledgeGap).where(
        KnowledgeGap.entity_type == "asset", KnowledgeGap.entity_id == asset.id,
        KnowledgeGap.status.in_(ACTIVE_GAP_STATUSES),
    )))
    open_gaps = [item for item in active_gaps if item.status in {"open", "deferred"}]
    required_open = [item for item in open_gaps if item.requirement_level in {"required", "conditional"}]
    recommended_open = [item for item in open_gaps if item.requirement_level == "recommended"]
    exceptions = [item for item in active_gaps if item.status == "exception"]
    if any(item.severity == "critical" for item in required_open):
        status = "critical_gaps"
    elif required_open:
        status = "incomplete"
    elif exceptions:
        status = "exception_accepted"
    elif recommended_open:
        status = "operationally_complete"
    else:
        status = "complete"
    summary = db.scalar(select(KnowledgeCompletenessSummary).where(
        KnowledgeCompletenessSummary.entity_type == "asset",
        KnowledgeCompletenessSummary.entity_id == asset.id,
    ))
    if summary is None:
        summary = KnowledgeCompletenessSummary(entity_type="asset", entity_id=asset.id, customer_id=asset.customer_id, site_id=asset.site_id, completeness_status="not_evaluated")
        db.add(summary)
        db.flush()
    previous_status = summary.completeness_status
    summary.required_total = counts["required_total"]
    summary.required_satisfied = counts["required_satisfied"]
    summary.recommended_total = counts["recommended_total"]
    summary.recommended_satisfied = counts["recommended_satisfied"]
    summary.critical_gap_count = sum(item.severity == "critical" for item in open_gaps)
    summary.high_gap_count = sum(item.severity == "high" for item in open_gaps)
    summary.open_gap_count = len(open_gaps)
    summary.exception_count = len(exceptions)
    summary.completeness_status = status
    summary.customer_id = asset.customer_id
    summary.site_id = asset.site_id
    summary.last_evaluated_at = now
    if previous_status != status:
        _change(db, asset=asset, gap=None, change_type="completeness_status_changed", summary=f"{asset.name} completeness changed from {previous_status.replace('_', ' ')} to {status.replace('_', ' ')}.", actor_user_id=actor_user_id, previous=previous_status, new=status)
    return summary


def evaluate_asset_safely(
    db: Session,
    asset_or_id: Asset | uuid.UUID,
    *,
    trigger_context: str | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> KnowledgeCompletenessSummary | None:
    """Evaluate in a savepoint so an ancillary evaluator defect cannot lose a valid edit."""
    asset_id = asset_or_id.id if isinstance(asset_or_id, Asset) else asset_or_id
    try:
        with db.begin_nested():
            return evaluate_asset(
                db,
                asset_or_id,
                trigger_context=trigger_context,
                actor_user_id=actor_user_id,
            )
    except Exception:
        logger.exception("Completeness evaluation failed for asset %s", asset_id)
        asset = db.get(Asset, asset_id)
        if asset is None:
            return None
        summary = db.scalar(select(KnowledgeCompletenessSummary).where(
            KnowledgeCompletenessSummary.entity_type == "asset",
            KnowledgeCompletenessSummary.entity_id == asset.id,
        ))
        if summary is None:
            summary = KnowledgeCompletenessSummary(
                entity_type="asset", entity_id=asset.id,
                customer_id=asset.customer_id, site_id=asset.site_id,
            )
            db.add(summary)
        summary.completeness_status = "not_evaluated"
        summary.last_evaluated_at = None
        return summary


def evaluate_assets_for_asset_type(db: Session, asset_type_id: uuid.UUID | None, *, limit: int = 100, actor_user_id: uuid.UUID | None = None) -> int:
    query = select(Asset).order_by(Asset.updated_at.desc()).limit(limit)
    if asset_type_id is not None:
        asset_type = db.get(AssetType, asset_type_id)
        if asset_type is None:
            return 0
        query = query.where(Asset.asset_type == asset_type.key)
    assets = list(db.scalars(query))
    for asset in assets:
        evaluate_asset(db, asset, trigger_context="requirement_profile_changed", actor_user_id=actor_user_id)
    return len(assets)


def get_entity_completeness_context(db: Session, entity_type: str, entity_id: uuid.UUID) -> dict[str, Any]:
    summary = db.scalar(select(KnowledgeCompletenessSummary).where(KnowledgeCompletenessSummary.entity_type == entity_type, KnowledgeCompletenessSummary.entity_id == entity_id))
    gaps = list(db.scalars(select(KnowledgeGap).where(KnowledgeGap.entity_type == entity_type, KnowledgeGap.entity_id == entity_id, KnowledgeGap.status.in_(ACTIVE_GAP_STATUSES))))
    return to_json_value({
        "completeness_status": summary.completeness_status if summary else "not_evaluated",
        "critical_gap_count": summary.critical_gap_count if summary else 0,
        "relevant_topology_gap_summaries": [item.summary for item in gaps if "relationship" in str(item.details_json).lower()],
        "active_exception_count": sum(item.status == "exception" for item in gaps),
        "last_evaluated_at": summary.last_evaluated_at if summary else None,
    })
