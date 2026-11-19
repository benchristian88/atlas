"""Read-only asset knowledge: acceptance, observations and logical presentation."""
from __future__ import annotations

import json
import uuid

from sqlalchemy import select

from app.models import Asset, AssetType, DataSource, EntitySourceLink, KnowledgeAssertion, RelationshipType, User
from app.services.proxmox_guest_bindings import historical_relationship_link
from app.services.predicate_definitions import ASSET_FIELD_PREDICATES, predicate_cardinality, predicate_label
from app.utils.json_values import to_json_value


def _uuid(value):
    try:
        return uuid.UUID(str(value)) if value else None
    except (ValueError, TypeError):
        return None


def _key(value):
    return json.dumps(to_json_value(value), sort_keys=True, separators=(",", ":"))


def knowledge_sources(db, owner, source_ids):
    """Asset knowledge may attribute local/site-wide sources, never foreign ones."""
    return {row.id: row for row in db.scalars(select(DataSource).where(
        DataSource.id.in_(source_ids), DataSource.customer_id == owner.customer_id))
        if row.site_id in {None, owner.site_id}}


class SummaryValues:
    """Batch referenced metadata; never guess canonical identities from names."""
    def __init__(self, db, asset, rows, principal):
        self.asset, self.principal, self.db = asset, principal, db
        self.types = {row.key: row.name for row in db.scalars(select(AssetType))}
        self.relationships = {row.key: row.name for row in db.scalars(select(RelationshipType))}
        source_ids = {row.data_source_id for row in rows if row.data_source_id}
        self.sources = knowledge_sources(db, asset, source_ids)
        actor_ids = {row.accepted_by_user_id for row in rows if row.accepted_by_user_id}
        self.actors = {row.id: row for row in db.scalars(select(User).where(User.id.in_(actor_ids)))}
        externals = {self.external(row) for row in rows if self.is_relationship(row) and self.external(row)}
        self.links = {}
        for row in db.scalars(select(EntitySourceLink).where(
            EntitySourceLink.customer_id == asset.customer_id, EntitySourceLink.site_id == asset.site_id,
            EntitySourceLink.entity_type == "asset", EntitySourceLink.data_source_id.in_(source_ids),
            EntitySourceLink.external_id.in_(externals))):
            self.links.setdefault((row.data_source_id, row.external_id), []).append(row)
        identifiers = {self.identifier(row) for row in rows if self.is_relationship(row)} - {None}
        self.targets = {row.id: row for row in db.scalars(select(Asset).where(Asset.id.in_(identifiers),
            Asset.customer_id == asset.customer_id, Asset.site_id.is_not_distinct_from(asset.site_id)))
                        if row.customer_id == asset.customer_id and row.site_id == asset.site_id
                        and (principal is None or principal.can("assets.view", row.customer_id, row.site_id))}

    def is_relationship(self, row):
        return row.object_type == "asset" or (row.fact_metadata is None and row.predicate in self.relationships)

    @staticmethod
    def external(row):
        value = row.value_json if isinstance(row.value_json, dict) else {}
        return row.object_external_id or value.get("target_external_id")

    def identifier(self, row):
        value = row.value_json if isinstance(row.value_json, dict) else {}
        # Outgoing from the canonical subject; contradictory legacy JSON is not
        # authority for another relationship direction.
        if value.get("source_asset_id") and _uuid(value["source_asset_id"]) != self.asset.id:
            return None
        if row.object_id:
            return row.object_id
        for field in ("target_asset_id", "resolved_target_asset_id", "target_id"):
            if value.get(field):
                return _uuid(value[field])
        links = self.links.get((row.data_source_id, self.external(row)), ())
        link = historical_relationship_link(self.db, row, links)
        return link.entity_id if link else None

    def relationship(self, row):
        if not self.is_relationship(row):
            return None
        target = self.targets.get(self.identifier(row))
        return {"relationship_type": row.predicate,
                "label": self.relationships.get(row.predicate, predicate_label(row.predicate)),
                "direction": "outgoing", "target_id": target.id if target else None,
                "target_name": target.name if target else "Unavailable asset" if self.identifier(row) else "Unresolved asset",
                "href": f"/assets/{target.id}" if target else None}

    def value_key(self, row):
        relationship = self.relationship(row)
        if relationship:
            # Only verified targets permit cross-source equivalence. Identical
            # unresolved external references remain independent claims.
            return _key([str(self.asset.customer_id), str(self.asset.site_id), str(self.asset.id), row.predicate,
                         str(relationship["target_id"])]) if relationship["target_id"] else _key(["unresolved", str(row.id)])
        return _key({"value": row.value_json, "object_type": row.object_type,
                     "object_id": row.object_id, "object_external_id": row.object_external_id})

    def display(self, predicate, value):
        if predicate == "asset_type" and isinstance(value, str):
            return self.types.get(value, predicate_label(value))
        if value is None or value == "":
            return "—"
        if isinstance(value, (dict, list)):
            return "Structured value — see Raw assertions"
        return str(value)

    def present(self, row, accepted_keys):
        relationship = self.relationship(row)
        source = self.sources.get(row.data_source_id)
        actor = self.actors.get(row.accepted_by_user_id)
        value = to_json_value(row.value_json)
        if relationship:
            # Never echo unverified target names/IDs from legacy JSON. Complete
            # original values remain in the existing raw assertions endpoint.
            value = {"relationship": row.predicate, "target_id": relationship["target_id"],
                     "target_name": relationship["target_name"]}
        elif value is None:
            value = row.object_external_id
        return {"assertion_id": row.id, "value": value, "display_value": relationship["target_name"] if relationship else self.display(row.predicate, value),
                "relationship": relationship, "truth_classification": row.truth_classification,
                "confirmation_status": row.confirmation_status, "source_id": source.id if source else None,
                "source_name": source.name if source else None, "first_observed_at": row.first_observed_at,
                "last_observed_at": row.last_observed_at, "accepted_at": row.accepted_at, "confirmed_at": row.accepted_at,
                "accepted_by_user_id": row.accepted_by_user_id,
                "accepted_by_name": (actor.display_name or actor.email) if actor else None,
                "actor_name": (actor.display_name or actor.email) if actor else None,
                "is_source_current": bool(row.is_source_current if row.is_source_current is not None else row.is_current),
                "is_accepted": bool(row.is_accepted),
                "conflicts_with_accepted": bool(accepted_keys and self.value_key(row) not in accepted_keys)}

    def logical_values(self, rows, accepted_keys):
        groups = {}
        for row in rows:
            key = self.value_key(row)
            entry = self.present(row, accepted_keys)
            group = groups.setdefault(key, {"key": key, "value": entry["value"], "display_value": entry["display_value"],
                "relationship": entry["relationship"], "assertions": []})
            group["assertions"].append(entry)
        for group in groups.values():
            group["source_count"] = len({entry["source_id"] for entry in group["assertions"] if entry["source_id"]})
        return list(groups.values())


def asset_knowledge_summary(db, asset, principal=None):
    rows = list(db.scalars(select(KnowledgeAssertion).where(KnowledgeAssertion.subject_type == "asset",
        KnowledgeAssertion.subject_id == asset.id, KnowledgeAssertion.customer_id == asset.customer_id,
        KnowledgeAssertion.site_id.is_not_distinct_from(asset.site_id)).order_by(
            KnowledgeAssertion.predicate, KnowledgeAssertion.last_observed_at.desc(), KnowledgeAssertion.id.desc())))
    values = SummaryValues(db, asset, rows, principal)
    grouped = {}
    for assertion in rows:
        grouped.setdefault(assertion.predicate, []).append(assertion)
    # An operational type without assertions is a consistency state, not an
    # invented historical acceptance or an absent operational Asset Type.
    if asset.asset_type:
        grouped.setdefault("asset_type", [])
    predicates = []
    for predicate in sorted(grouped, key=lambda key: (values.relationships.get(key, predicate_label(key)), key)):
        assertions = grouped[predicate]
        active = [row for row in assertions if row.retracted_at is None
                  and row.confirmation_status not in {"rejected", "superseded"}
                  and bool(row.is_source_current if row.is_source_current is not None else row.is_current)]
        accepted = [row for row in assertions if row.is_accepted and row.retracted_at is None and row.confirmation_status != "rejected"]
        observations = [row for row in active if row.truth_classification != "declared"]
        active_keys = {values.value_key(row) for row in active}
        accepted_keys = {values.value_key(row) for row in accepted}
        observation_keys = {values.value_key(row) for row in observations}
        cardinality = predicate_cardinality(predicate, object_type=next((row.object_type for row in assertions if row.object_type),
            "asset" if predicate in values.relationships else None))
        conflict = bool(cardinality == "single" and accepted_keys and observation_keys - accepted_keys)
        unresolved = bool(cardinality == "single" and not accepted_keys and len(active_keys) > 1)
        accepted_values = [values.present(row, accepted_keys) for row in accepted]
        canonical = to_json_value(getattr(asset, predicate)) if predicate in ASSET_FIELD_PREDICATES else None
        consistency = ("not_applicable" if predicate not in ASSET_FIELD_PREDICATES else "missing_acceptance" if not accepted
                       else "matches" if any(row.value_json == canonical for row in accepted) else "mismatch")
        source_count = len({row.data_source_id for row in active if row.data_source_id in values.sources})
        predicates.append({"predicate": predicate, "label": values.relationships.get(predicate, predicate_label(predicate)),
            "cardinality": cardinality, "accepted": accepted_values[0] if accepted_values else None,
            "accepted_values": accepted_values, "latest_observations": [values.present(row, accepted_keys) for row in observations],
            "accepted_groups": values.logical_values(accepted, accepted_keys),
            "observation_groups": values.logical_values(observations, accepted_keys),
            "canonical_value": canonical, "canonical_display_value": values.display(predicate, canonical),
            "canonical_consistency": consistency, "awaiting_acceptance": bool(observations and not accepted),
            "state": "conflicting" if conflict else "unresolved" if unresolved else "accepted" if accepted else "observed" if observations else "historical" if assertions else "unknown",
            "active_source_count": source_count, "source_count": source_count,
            "distinct_active_value_count": len(active_keys), "assertion_count": len(assertions),
            "historical_count": len(assertions) - len(active), "conflict": conflict, "unresolved": unresolved,
            "last_observed_at": max((row.last_observed_at for row in active), default=None),
            "freshness": "current" if active else "historical" if assertions else "unknown"})
    return to_json_value({"asset_id": asset.id, "groups": predicates,
        "conflict_count": sum(row["conflict"] for row in predicates), "unresolved_count": sum(row["unresolved"] for row in predicates),
        "consistency_issue_count": sum(row["canonical_consistency"] in {"missing_acceptance", "mismatch"} for row in predicates)})
