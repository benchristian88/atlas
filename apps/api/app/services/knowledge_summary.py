"""Read model for concise asset knowledge roll-ups."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, DataSource, KnowledgeAssertion, User
from app.services.predicate_definitions import predicate_cardinality, predicate_label
from app.utils.json_values import to_json_value


def _value(assertion: KnowledgeAssertion, db: Session) -> Any:
    if assertion.value_json is not None:
        return to_json_value(assertion.value_json)
    if assertion.object_type == "asset":
        target = db.get(Asset, assertion.object_id) if assertion.object_id else None
        return {
            "relationship": assertion.predicate,
            "target_id": str(assertion.object_id) if assertion.object_id else None,
            "target_name": (
                target.name
                if target
                else assertion.object_external_id or "Unavailable"
            ),
        }
    return assertion.object_external_id


def _value_key(assertion: KnowledgeAssertion) -> str:
    return json.dumps(
        to_json_value(
            {
                "value": assertion.value_json,
                "object_type": assertion.object_type,
                "object_id": assertion.object_id,
                "object_external_id": assertion.object_external_id,
            }
        ),
        sort_keys=True,
        separators=(",", ":"),
    )


def _summary_value(
    db: Session,
    assertion: KnowledgeAssertion,
    *,
    accepted_keys: set[str] | None = None,
) -> dict[str, Any]:
    source = db.get(DataSource, assertion.data_source_id) if assertion.data_source_id else None
    actor = db.get(User, assertion.accepted_by_user_id) if assertion.accepted_by_user_id else None
    return to_json_value(
        {
            "assertion_id": assertion.id,
            "value": _value(assertion, db),
            "truth_classification": assertion.truth_classification,
            "confirmation_status": assertion.confirmation_status,
            "source_id": assertion.data_source_id,
            "source_name": source.name if source else None,
            "first_observed_at": assertion.first_observed_at,
            "last_observed_at": assertion.last_observed_at,
            "accepted_at": assertion.accepted_at,
            "confirmed_at": assertion.accepted_at,
            "accepted_by_user_id": assertion.accepted_by_user_id,
            "accepted_by_name": (actor.display_name or actor.email) if actor else None,
            "actor_name": (actor.display_name or actor.email) if actor else None,
            "is_source_current": bool(
                assertion.is_source_current
                if assertion.is_source_current is not None
                else assertion.is_current
            ),
            "is_accepted": bool(assertion.is_accepted),
            "conflicts_with_accepted": bool(
                accepted_keys and _value_key(assertion) not in accepted_keys
            ),
        }
    )


def asset_knowledge_summary(
    db: Session, asset: Asset
) -> dict[str, Any]:
    rows = list(
        db.scalars(
            select(KnowledgeAssertion)
            .where(
                KnowledgeAssertion.subject_type == "asset",
                KnowledgeAssertion.subject_id == asset.id,
            )
            .order_by(
                KnowledgeAssertion.predicate,
                KnowledgeAssertion.last_observed_at.desc(),
                KnowledgeAssertion.id.desc(),
            )
        )
    )
    grouped: dict[str, list[KnowledgeAssertion]] = {}
    for assertion in rows:
        grouped.setdefault(assertion.predicate, []).append(assertion)

    predicates = []
    for predicate in sorted(grouped, key=lambda value: (predicate_label(value), value)):
        assertions = grouped[predicate]
        active = [
            item
            for item in assertions
            if item.retracted_at is None
            and item.confirmation_status not in {"rejected", "superseded"}
            and bool(
                item.is_source_current
                if item.is_source_current is not None
                else item.is_current
            )
        ]
        accepted = [
            item
            for item in assertions
            if bool(item.is_accepted)
            and item.retracted_at is None
            and item.confirmation_status != "rejected"
        ]
        observations = [
            item for item in active if item.truth_classification != "declared"
        ]
        active_keys = {_value_key(item) for item in active}
        observation_keys = {_value_key(item) for item in observations}
        accepted_keys = {_value_key(item) for item in accepted}
        cardinality = predicate_cardinality(
            predicate,
            object_type=next(
                (item.object_type for item in assertions if item.object_type), None
            ),
        )
        conflict = bool(
            cardinality == "single"
            and accepted_keys
            and any(key not in accepted_keys for key in observation_keys)
        )
        unresolved = bool(
            cardinality == "single"
            and not accepted_keys
            and (len(active_keys) > 1 or len(active) > 1)
        )
        accepted_values = [
            _summary_value(db, item, accepted_keys=accepted_keys)
            for item in accepted
        ]
        predicates.append(
            {
                "predicate": predicate,
                "label": predicate_label(predicate),
                "cardinality": cardinality,
                "accepted": accepted_values[0] if accepted_values else None,
                "accepted_values": accepted_values,
                "latest_observations": [
                    _summary_value(db, item, accepted_keys=accepted_keys)
                    for item in observations
                ],
                "active_source_count": len(
                    {
                        str(item.data_source_id) if item.data_source_id else "unavailable"
                        for item in active
                    }
                ),
                "source_count": len(
                    {
                        str(item.data_source_id) if item.data_source_id else "unavailable"
                        for item in active
                    }
                ),
                "distinct_active_value_count": len(active_keys),
                "assertion_count": len(assertions),
                "historical_count": len(assertions) - len(active),
                "conflict": conflict,
                "unresolved": unresolved,
                "last_observed_at": max(
                    (item.last_observed_at for item in active), default=None
                ),
                "freshness": (
                    "current" if active else "historical" if assertions else "unknown"
                ),
            }
        )
    return to_json_value(
        {
            "asset_id": asset.id,
            "groups": predicates,
            "conflict_count": sum(item["conflict"] for item in predicates),
            "unresolved_count": sum(item["unresolved"] for item in predicates),
        }
    )
