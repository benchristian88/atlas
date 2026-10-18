"""Read-only, generic entity review over independent reconciliation records.

Source identities are opaque equality keys. Ownership comes from canonical source
links and Interface configuration assertions, never from their spelling. The
request-local index batches context/label lookups; rendering does not resolve or
persist identities. Only the existing decision service writes accepted knowledge.
"""
from __future__ import annotations

import base64
import binascii
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import heapq
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import select, tuple_

from app.authorization import scope_condition
from app.models import (Asset, AssetInterface, AssetType, DataSource, EntitySourceLink,
                        KnowledgeAssertion, Network, ReconciliationItem, RelationshipType)
from app.schemas import ReconciliationItemResponse
from app.services.predicate_definitions import predicate_label
from app.services.asset_icons import icon_fields
from app.services.reconciliation_listing import filtered_items
from app.utils.json_values import to_json_value

ACTIVE = {"open", "deferred"}
SECTION_LABELS = {"facts": "Facts", "relationships": "Relationships", "network": "Network"}
SECTION_LIMIT = 20
BULK_LIMIT = 1000


def fact_label(predicate, metadata=None):
    """Presentation metadata wins; unknown namespaces get the same safe fallback."""
    label = (metadata or {}).get("label")
    if isinstance(label, str) and 0 < len(label.strip()) <= 255:
        return label.strip()
    return predicate_label(predicate.rsplit(".", 1)[-1])


def _object(value):
    return value if isinstance(value, dict) else {}


def _name(value, fallback):
    return value.strip() if isinstance(value, str) and 0 < len(value.strip()) <= 255 else fallback


def item_version(item, claim):
    # Includes the reviewed proposal and freshness, not just a timestamp. A
    # coalesced assertion can change without updating its reconciliation record.
    value = [str(item.id), item.status, item.updated_at, item.observed_value_json,
             claim.updated_at, claim.value_json, claim.is_source_current,
             claim.retracted_at, claim.superseded_by_id]
    return hashlib.sha256(json.dumps(to_json_value(value), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _encode(value):
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode()


def _decode(cursor, fingerprint):
    try:
        value = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
        if not isinstance(value, dict) or set(value) != {"filter", "snapshot", "after"} or value["filter"] != fingerprint:
            raise ValueError
        if not isinstance(value["snapshot"], list) or len(value["snapshot"]) != 2 or any(not isinstance(part, str) for part in value["snapshot"]):
            raise ValueError
        stamp, identifier = value["snapshot"]
        stamp = datetime.fromisoformat(stamp)
        if stamp.tzinfo is None or (value["after"] is not None and not isinstance(value["after"], str)):
            raise ValueError
        if value["after"] is not None:
            uuid.UUID(value["after"])
        return (stamp, uuid.UUID(identifier)), value["after"]
    except (ValueError, TypeError, KeyError, binascii.Error):
        raise HTTPException(422, "Invalid entity review cursor; refresh this queue") from None


class EntityReview:
    def __init__(self, db, context, principal, *, snapshot=None):
        self.db, self.context, self.principal = db, context, principal
        query = filtered_items(context, principal, item_status=None).join(
            KnowledgeAssertion, KnowledgeAssertion.id == ReconciliationItem.assertion_id).where(
                KnowledgeAssertion.customer_id == ReconciliationItem.customer_id,
                KnowledgeAssertion.site_id.is_not_distinct_from(ReconciliationItem.site_id))
        if snapshot:
            query = query.where(tuple_(ReconciliationItem.created_at, ReconciliationItem.id) <= snapshot)
        self.rows = list(db.execute(query.add_columns(KnowledgeAssertion).order_by(
            ReconciliationItem.created_at, ReconciliationItem.id)))
        self.items = {item.id: item for item, _ in self.rows}
        self.claims = {item.id: claim for item, claim in self.rows}
        self.snapshot = snapshot or max(((item.created_at, item.id) for item, _ in self.rows), default=None)

        def scoped(model):
            conditions = [scope_condition(principal, "reconciliation.view", model.customer_id, model.site_id)]
            if context.customer_id:
                conditions.append(model.customer_id == context.customer_id)
            if context.site_id:
                conditions.append(model.site_id == context.site_id)
            return select(model).where(*conditions)

        # Batch only identities referenced by the scoped review index, rather
        # than reading the customer's entire unrelated operational inventory.
        aliases, identifiers, source_ids = set(), defaultdict(set), set()
        for item, claim in self.rows:
            if claim.data_source_id:
                source_ids.add(claim.data_source_id)
            if item.entity_id and item.entity_type in {"asset", "network", "asset_interface"}:
                identifiers[item.entity_type].add(item.entity_id)
            if claim.subject_id:
                identifiers[claim.subject_type].add(claim.subject_id)
            if claim.object_id:
                identifiers[claim.object_type].add(claim.object_id)
            value = _object(item.observed_value_json)
            refs = [(claim.subject_type, claim.subject_external_id or item.candidate_external_id),
                    (claim.object_type, claim.object_external_id)]
            if item.entity_type == "asset_relationship":
                refs.extend([("asset", value.get("source_external_id")), ("asset", value.get("target_external_id"))])
            if item.entity_type == "asset_interface" and claim.predicate == "configuration":
                for configuration in (value, _object(claim.value_json)):
                    refs.extend([("asset", configuration.get("asset_external_id")), ("network", configuration.get("network_external_id"))])
            aliases.update((claim.data_source_id, kind, external) for kind, external in refs if claim.data_source_id and kind and external)
        self.links = {self.alias(row.customer_id, row.site_id, row.data_source_id, row.entity_type, row.external_id): row
                      for row in db.scalars(scoped(EntitySourceLink).where(tuple_(
                          EntitySourceLink.data_source_id, EntitySourceLink.entity_type, EntitySourceLink.external_id).in_(aliases)))}
        for link in self.links.values():
            for kind, identifier in (("asset", link.entity_id), ("asset", link.interface_owner_id),
                                     ("network", link.network_id), ("asset_interface", link.interface_id)):
                if identifier:
                    identifiers[kind].add(identifier)
        self.interfaces = {row.id: row for row in db.scalars(select(AssetInterface).where(
            AssetInterface.id.in_(identifiers["asset_interface"]),
            AssetInterface.asset_id.in_(scoped(Asset).with_only_columns(Asset.id))))}
        identifiers["asset"].update(row.asset_id for row in self.interfaces.values())
        self.assets = {row.id: row for row in db.scalars(scoped(Asset).where(Asset.id.in_(identifiers["asset"])))}
        self.networks = {row.id: row for row in db.scalars(scoped(Network).where(Network.id.in_(identifiers["network"])))}
        self.sources = {row.id: row for row in db.scalars(scoped(DataSource).where(DataSource.id.in_(source_ids)))}
        # Eight SELECTs independent of card count. Evidence, receipts, diagnostic
        # payloads, Integration configuration and credentials are never loaded.
        self.types = {row.key: row for row in db.scalars(select(AssetType))}
        self.relationship_types = {row.key: row for row in db.scalars(select(RelationshipType))}
        self.configurations = {}
        self.parents = {}
        for item, claim in self.rows:
            alias = self.alias_for(item, claim)
            if claim.predicate == "configuration" and claim.fact_metadata is None:
                self.configurations[alias] = (item, claim)
            if item.entity_type in {"asset", "network", "asset_interface"} and item.category in {"newly_discovered", "possible_duplicate"}:
                previous = self.parents.get(alias)
                if previous is None or self.parent_priority(item) > self.parent_priority(previous):
                    self.parents[alias] = item
        self.groups = defaultdict(list)
        self.group_for_item = {}
        for item, claim in self.rows:
            key = self.owner_key(item, claim)
            self.groups[key].append(item)
            self.group_for_item[item.id] = key
        # Prefer an entity's own record over its children as its durable anchor.
        self.anchors = {key: min(rows, key=lambda row: (
            row.entity_type != key[3], row.category not in {"newly_discovered", "possible_duplicate"},
            row.created_at, row.id)).id for key, rows in self.groups.items()}
        self.keys_by_id = {identifier: key for key, identifier in self.anchors.items()}
        self.parents_by_key = {}
        for parent in self.parents.values():
            key = self.group_for_item[parent.id]
            if parent.entity_type == key[3]:
                previous = self.parents_by_key.get(key)
                if previous is None or self.parent_priority(parent) > self.parent_priority(previous):
                    self.parents_by_key[key] = parent

    def parent_priority(self, item):
        return (item.status in ACTIVE, item.status == "accepted", self.claims[item.id].is_source_current,
                item.created_at, item.id)

    @staticmethod
    def alias(customer, site, source, kind, external):
        return (customer, site, source, kind, external)

    def alias_for(self, item, claim):
        return self.alias(item.customer_id, item.site_id, claim.data_source_id, item.entity_type,
                          claim.subject_external_id or item.candidate_external_id)

    def target(self, item, claim, kind=None, external=None, identifier=None):
        kind = kind or item.entity_type
        external = external if external is not None else claim.subject_external_id or item.candidate_external_id
        alias = self.alias(item.customer_id, item.site_id, claim.data_source_id, kind, external)
        link = self.links.get(alias)
        if link:
            identifier = {"asset": link.entity_id, "network": link.network_id, "asset_interface": link.interface_id}.get(kind)
        collections = {"asset": self.assets, "network": self.networks, "asset_interface": self.interfaces}
        result = collections.get(kind, {}).get(identifier)
        if kind == "asset_interface" and result:
            owner = self.assets.get(result.asset_id)
            return result if owner and (owner.customer_id, owner.site_id) == (item.customer_id, item.site_id) else None
        return result if result and (result.customer_id, result.site_id) == (item.customer_id, item.site_id) else None

    def identity_key(self, item, claim, kind, external, identifier=None):
        target = self.target(item, claim, kind, external, identifier)
        return (item.customer_id, item.site_id, None if target else claim.data_source_id, kind,
                target.id if target else external or item.id)

    def owner_key(self, item, claim):
        value = _object(item.observed_value_json)
        if item.entity_type == "asset_relationship":
            return self.identity_key(item, claim, "asset", claim.subject_external_id or value.get("source_external_id"), claim.subject_id)
        if item.entity_type == "asset_interface":
            interface = self.target(item, claim, identifier=item.entity_id or claim.subject_id)
            if interface:
                return (item.customer_id, item.site_id, None, "asset", interface.asset_id)
            config = self.configurations.get(self.alias_for(item, claim))
            owner = _object(config[1].value_json).get("asset_external_id") if config else None
            if owner:
                return self.identity_key(item, claim, "asset", owner)
        return self.identity_key(item, claim, item.entity_type,
                                 claim.subject_external_id or item.candidate_external_id, item.entity_id or claim.subject_id)

    def key_for(self, identifier):
        key = self.group_for_item.get(identifier)
        if key is None:
            raise HTTPException(404, "Reconciliation entity not found")
        return key

    def display(self, key):
        rows = self.groups.get(key, [])
        target = {"asset": self.assets, "network": self.networks, "asset_interface": self.interfaces}.get(key[3], {}).get(key[4])
        parent = self.parents_by_key.get(key)
        config = next((row for row in reversed(rows) if self.claims[row.id].predicate == "configuration"), None)
        proposal = _object((parent or config).observed_value_json) if parent or config else {}
        type_key = target.asset_type if isinstance(target, Asset) else proposal.get("asset_type")
        managed = self.types.get(type_key)
        icons = icon_fields(target, managed) if isinstance(target, Asset) else {}
        return {"name": target.name if target else _name(proposal.get("name"), key[3].replace("_", " ").title()),
                "entity_type": key[3], "entity_id": target.id if target else None,
                "asset_type": type_key, "type_label": managed.name if managed else key[3].replace("_", " ").title(),
                "icon_key": managed.category_record.icon_key if managed and managed.category_record else None,
                "accent_key": managed.category_record.accent_key if managed and managed.category_record else None,
                "cached_icon_url": icons.get("cached_icon_url"),
                "default_icon_url": managed.default_icon_url if managed else None}

    @staticmethod
    def section(item):
        return "relationships" if item.entity_type == "asset_relationship" else "network" if item.entity_type in {"asset_interface", "network"} else "facts"

    def prerequisites(self, item):
        claim = self.claims[item.id]
        value = _object(item.observed_value_json)
        dependencies = []
        if item.entity_type == "asset_relationship":
            dependencies = [("asset", claim.subject_external_id or value.get("source_external_id"), claim.subject_id),
                            ("asset", claim.object_external_id or value.get("target_external_id"), claim.object_id)]
        elif item.entity_type in {"asset", "network", "asset_interface"}:
            if claim.fact_metadata is not None or (item.entity_type == "asset" and item.category not in {"newly_discovered", "possible_duplicate"}):
                dependencies = [(item.entity_type, claim.subject_external_id or item.candidate_external_id, item.entity_id or claim.subject_id)]
            elif item.entity_type == "asset_interface":
                dependencies = [("asset", value.get("asset_external_id"), None)]
                if value.get("network_external_id"):
                    dependencies.append(("network", value["network_external_id"], None))
        result = []
        for kind, external, identifier in dependencies:
            target = self.target(item, claim, kind, external, identifier)
            if target:
                continue
            alias = self.alias(item.customer_id, item.site_id, claim.data_source_id, kind, external)
            parent = self.parents.get(alias)
            key = self.group_for_item.get(parent.id) if parent else None
            name = self.display(key)["name"] if key else kind.replace("_", " ").title()
            result.append({"item_id": parent.id if parent else None,
                           "entity_id": self.anchors.get(key), "name": name,
                           "reason": f"Requires {name} to exist"})
        return result

    def eligibility(self, item):
        claim = self.claims[item.id]
        blockers = self.prerequisites(item)
        reason = None
        if item.status not in ACTIVE:
            reason = "This item has already been decided"
        elif not self.principal.can("reconciliation.decide", item.customer_id, item.site_id):
            reason = "Permission required to decide this item"
        elif claim.retracted_at or claim.superseded_by_id or claim.is_source_current is False:
            reason = "This proposal is stale; review the latest observation"
        elif blockers:
            reason = "; ".join(row["reason"] for row in blockers)
        elif item.category == "no_longer_observed":
            reason = "Choose an individual lifecycle disposition"
        elif item.entity_type == "asset_relationship" and not self.principal.can("relationships.create", item.customer_id, item.site_id):
            reason = "Permission required to create relationships"
        elif item.entity_type in {"network", "asset_interface"}:
            permission = "networks.create" if item.category == "newly_discovered" and item.entity_id is None else "networks.edit"
            if not self.principal.can(permission, item.customer_id, item.site_id):
                reason = "Permission required to accept network information"
        return {"can_accept": reason is None, "blocked_reason": reason, "blockers": blockers,
                "can_reject": item.status in ACTIVE and self.principal.can("reconciliation.decide", item.customer_id, item.site_id),
                "can_defer": item.status == "open" and self.principal.can("reconciliation.decide", item.customer_id, item.site_id)}

    def present_item(self, item):
        claim = self.claims[item.id]
        source = self.sources.get(claim.data_source_id)
        if source and (source.customer_id != item.customer_id or source.site_id not in {None, item.site_id}):
            source = None
        label = fact_label(claim.predicate, claim.fact_metadata)
        proposed = claim.value_json if claim.fact_metadata is not None else item.observed_value_json
        if item.entity_type == "asset_relationship":
            value = _object(item.observed_value_json)
            managed = self.relationship_types.get(value.get("relationship_type"))
            key = self.identity_key(item, claim, "asset", claim.object_external_id or value.get("target_external_id"), claim.object_id)
            label = (managed.name if managed else "Relationship") + " → " + self.display(key)["name"]
        elif item.entity_type == "asset_interface":
            config = self.configurations.get(self.alias_for(item, claim))
            interface = self.target(item, claim, identifier=item.entity_id or claim.subject_id)
            name = interface.name if interface else _name(_object(config[1].value_json).get("name"), "Interface") if config else "Interface"
            label = f"{name} · {label}" if claim.fact_metadata is not None else f"Interface {name}"
            if claim.fact_metadata is None and isinstance(proposed, dict):
                proposed = dict(proposed)
                if proposed.get("network_external_id"):
                    key = self.identity_key(item, claim, "network", proposed["network_external_id"])
                    proposed["network"] = self.display(key)["name"]
        elif item.category in {"newly_discovered", "possible_duplicate"}:
            label = "New asset" if item.entity_type == "asset" else "New network"
        elif isinstance(proposed, dict) and "field" in proposed:
            label, proposed = fact_label(proposed["field"], claim.fact_metadata), proposed.get("value")
        current = item.current_value_json
        if item.entity_type == "asset_relationship" and isinstance(current, dict):
            managed = self.relationship_types.get(current.get("relationship_type"))
            try:
                target = self.assets.get(uuid.UUID(str(current.get("target_asset_id"))))
            except ValueError:
                target = None
            if target and (target.customer_id, target.site_id) != (item.customer_id, item.site_id):
                target = None
            current = f"{managed.name if managed else 'Relationship'} → {target.name if target else 'Asset'}"
        if isinstance(current, dict) and "field" in current:
            current = current.get("value")
        result = ReconciliationItemResponse.model_validate(item).model_dump()
        return to_json_value({**result, "source_name": source.name if source else None,
                              "data_source_id": claim.data_source_id, "discovery_run_id": claim.discovery_run_id,
                              "assertion_predicate": claim.predicate, "label": label, "proposed": proposed,
                              "last_observed_at": claim.last_observed_at,
                              "current": current, "version": item_version(item, claim),
                              "warning": item.category.replace("_", " ").capitalize() if item.category in {"contradiction", "possible_duplicate"} else None,
                              **self.eligibility(item)})

    def matches(self, item, filters):
        status = filters.get("item_status", "open")
        if status == "resolved":
            if item.status not in {"accepted", "rejected"}:
                return False
        elif status and item.status != status:
            return False
        claim = self.claims[item.id]
        return all(not filters.get(key) or actual == filters[key] for key, actual in (
            ("category", item.category), ("source_id", claim.data_source_id), ("run_id", claim.discovery_run_id),
            ("entity_type", item.entity_type), ("section", self.section(item))))

    def matching_groups(self, filters):
        search = filters.get("search", "").strip().casefold()
        result = {}
        for key, rows in self.groups.items():
            if search and search not in self.display(key)["name"].casefold():
                continue
            matching = [item for item in rows if self.matches(item, filters)]
            if matching:
                result[key] = matching
        return result

    def ordered(self):
        # Relationship targets and missing-owner prerequisites precede their
        # dependants. This is review order, not an operational dependency claim.
        needs = {key: set() for key in self.groups}
        for item, claim in self.rows:
            owner = self.group_for_item[item.id]
            for blocker in self.prerequisites(item):
                if blocker["entity_id"] in self.keys_by_id:
                    needs[owner].add(self.keys_by_id[blocker["entity_id"]])
            if item.entity_type == "asset_relationship":
                value = _object(item.observed_value_json)
                target = self.identity_key(item, claim, "asset", claim.object_external_id or value.get("target_external_id"), claim.object_id)
                if target in needs:
                    needs[owner].add(target)
            if item.entity_type == "asset_interface" and claim.predicate == "configuration":
                network = _object(item.observed_value_json).get("network_external_id")
                if network:
                    target = self.identity_key(item, claim, "network", network)
                    if target in needs:
                        needs[owner].add(target)
            needs[owner].discard(owner)
        dependants = defaultdict(set)
        for key, prerequisites in needs.items():
            for prerequisite in prerequisites:
                dependants[prerequisite].add(key)
        # UUID anchors make tie-breaking independent of mutable names/status.
        ready = [(str(self.anchors[key]), key) for key in needs if not needs[key]]
        heapq.heapify(ready)
        result, remaining = [], set(needs)
        while remaining:
            if ready:
                _, key = heapq.heappop(ready)
                if key not in remaining:
                    continue
            else:
                key = min(remaining, key=lambda entry: str(self.anchors[entry]))
            remaining.remove(key)
            result.append(key)
            for child in dependants[key]:
                needs[child].discard(key)
                if not needs[child]:
                    heapq.heappush(ready, (str(self.anchors[child]), child))
        return result

    def present_group(self, key, matching):
        parent = self.parents_by_key.get(key)
        child_rows = [row for row in matching if not parent or row.id != parent.id]
        sections = []
        for section, label in SECTION_LABELS.items():
            rows = [row for row in child_rows if self.section(row) == section]
            if not rows:
                continue
            blocked = [self.eligibility(row)["blocked_reason"] for row in rows if row.status in ACTIVE and not self.eligibility(row)["can_accept"]]
            sections.append({"key": section, "label": label, "total": len(rows),
                             "blocked_count": len(blocked), "warnings": sorted(set(blocked + [row.category.replace("_", " ").capitalize() for row in rows if row.category in {"contradiction", "possible_duplicate"}])),
                             "items": [self.present_item(row) for row in rows[:SECTION_LIMIT]],
                             "next_offset": SECTION_LIMIT if len(rows) > SECTION_LIMIT else None})
        decisions = [row for row in matching if row.status in ACTIVE]
        if parent and parent.status in ACTIVE and parent.id not in {row.id for row in decisions}:
            decisions.insert(0, parent)
        return to_json_value({"id": self.anchors[key], "customer_id": key[0], "site_id": key[1],
                              **self.display(key), "parent": self.present_item(parent) if parent else None,
                              "default_expanded": bool(parent and parent.status in ACTIVE),
                              "matching_record_count": len(matching), "status_counts": dict(Counter(row.status for row in matching)),
                              "sections": sections, "accept_all_available": 0 < len(decisions) <= BULK_LIMIT,
                              "decision_items": [{"id": row.id, "version": item_version(row, self.claims[row.id])} for row in decisions] if len(decisions) <= BULK_LIMIT else [],
                              "bulk_limit": BULK_LIMIT})


def entity_page(db, context, principal, *, limit, cursor=None, **filters):
    fingerprint = hashlib.sha256(json.dumps(to_json_value([context.customer_id, context.site_id, filters]), sort_keys=True).encode()).hexdigest()[:24]
    snapshot, after = _decode(cursor, fingerprint) if cursor else (None, None)
    review = EntityReview(db, context, principal, snapshot=snapshot)
    groups = review.matching_groups(filters)
    order = review.ordered()
    previous_cursor = None
    if after:
        anchor = uuid.UUID(after)
        if anchor not in review.keys_by_id:
            raise HTTPException(422, "Entity review cursor is no longer available; refresh this queue")
        position = order.index(review.keys_by_id[anchor]) + 1
        prefix = [key for key in order[:position] if key in groups]
        previous_start = max(0, len(prefix) - limit)
        previous_cursor = _encode({"filter": fingerprint, "snapshot": [review.snapshot[0].isoformat(), str(review.snapshot[1])],
                                   "after": str(review.anchors[prefix[previous_start - 1]]) if previous_start else None})
        order = order[position:]
    eligible = [key for key in order if key in groups]
    selected = eligible[:limit]
    next_cursor = _encode({"filter": fingerprint, "snapshot": [review.snapshot[0].isoformat(), str(review.snapshot[1])],
                           "after": str(review.anchors[selected[-1]])}) if len(eligible) > limit else None
    rows = [row for group in groups.values() for row in group]
    return {"entities": [review.present_group(key, groups[key]) for key in selected],
            "entity_total": len(groups), "record_total": len(rows), "limit": limit, "next_cursor": next_cursor,
            "previous_cursor": previous_cursor,
            "by_status": dict(Counter(row.status for row in rows)), "by_category": dict(Counter(row.category for row in rows))}
