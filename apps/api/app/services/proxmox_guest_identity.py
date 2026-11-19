"""Hold Proxmox guest-slot evidence on the source side of the canonical boundary."""

from collections import defaultdict
from dataclasses import dataclass, field
import re

from fastapi import HTTPException
from sqlalchemy import select

from app.models import (
    Asset, AssetInterface, AssetRelationship, DiscoveryRun, EntitySourceLink, Integration,
    KnowledgeAssertion, Network, ReconciliationItem, RelationshipType,
)
from app.services.entity_resolution import scoped_source_links
from app.services.knowledge_assertions import mark_superseded
from app.utils.json_values import to_json_value

REVIEW_TYPE = "source_identity"
REVIEW_LABEL = "Identity review"
REVIEW_REQUIRED = "This source key requires a guest identity decision"
PROPOSAL_HELD = "This source proposal cannot be applied in its current state"
PRESENCE_PREDICATE = "source_key_present"
GUEST_KEY = re.compile(r"guest/(lxc|qemu)/[1-9][0-9]{0,8}")
INTERFACE_KEY = re.compile(r"(guest/(?:lxc|qemu)/[1-9][0-9]{0,8})/interface/net[0-9]{1,2}")
PREVIEW_LIMIT = 8


def is_proxmox_source(db, scope, source_id):
    return db.scalar(select(Integration.id).where(
        Integration.data_source_id == source_id, Integration.customer_id == scope.customer_id,
        Integration.site_id == scope.site_id, Integration.connector_id == "proxmox")) is not None


def _pending_reviews(scope, source_id):
    return select(ReconciliationItem, KnowledgeAssertion).join(
        KnowledgeAssertion, KnowledgeAssertion.id == ReconciliationItem.assertion_id
    ).where(
        ReconciliationItem.customer_id == scope.customer_id, ReconciliationItem.site_id == scope.site_id,
        ReconciliationItem.entity_type == REVIEW_TYPE, ReconciliationItem.status == "open",
        KnowledgeAssertion.customer_id == scope.customer_id, KnowledgeAssertion.site_id == scope.site_id,
        KnowledgeAssertion.data_source_id == source_id, KnowledgeAssertion.subject_type == REVIEW_TYPE,
        KnowledgeAssertion.predicate == PRESENCE_PREDICATE,
    )


def require_ordinary_item(item):
    if item.entity_type == REVIEW_TYPE:
        raise HTTPException(409, REVIEW_REQUIRED)


def review_snapshot(principal, item):
    """Apply canonical detail permissions to the retained review snapshot."""
    snapshot = dict(item.current_value_json)
    for permission, fields in (
        ("networks.view", ("interfaces", "more_interfaces")),
        ("relationships.view", ("relationships", "more_relationships")),
    ):
        if not principal.can(permission, item.customer_id, item.site_id):
            for field in fields:
                snapshot.pop(field, None)
    return snapshot


def interface_guest(external_id):
    match = INTERFACE_KEY.fullmatch(external_id or "")
    return match[1] if match else None


def proposal_guest_keys(item, claim):
    """Use typed endpoints/owners and the published Interface slot syntax."""
    if item.entity_type == "asset":
        keys = {claim.subject_external_id or item.candidate_external_id}
    elif item.entity_type == "asset_relationship":
        keys = {claim.subject_external_id, claim.object_external_id}
    elif item.entity_type == "asset_interface":
        value = claim.value_json if isinstance(claim.value_json, dict) else {}
        keys = (value.get("asset_external_id"), interface_guest(claim.subject_external_id))
    else:
        keys = set()
    return {key for key in keys if isinstance(key, str) and GUEST_KEY.fullmatch(key)}


def linked_retired_guests(db, scope, source_id, *, keys, owner_id=None):
    query = scoped_source_links(data_source_id=source_id, customer_id=scope.customer_id, site_id=scope.site_id)
    query = query.join(Asset, Asset.id == EntitySourceLink.entity_id).where(
        EntitySourceLink.entity_type == "asset", Asset.status == "retired")
    for link in db.scalars(query.where(
        (EntitySourceLink.external_id.in_(keys)) | (EntitySourceLink.entity_id == owner_id)
    )):
        if GUEST_KEY.fullmatch(link.external_id):
            return True
    return False


def require_applicable_proposal(db, item, claim):
    """Recheck while the caller holds source and canonical decision locks."""
    require_ordinary_item(item)
    if not claim.data_source_id or item.entity_type not in {"asset", "asset_interface", "asset_relationship"}:
        return
    keys = proposal_guest_keys(item, claim)
    owner_id = None
    if item.entity_type == "asset_interface":
        links = scoped_source_links(data_source_id=claim.data_source_id, customer_id=item.customer_id, site_id=item.site_id)
        owner_id = db.scalar(links.with_only_columns(EntitySourceLink.interface_owner_id).where(
            EntitySourceLink.entity_type == "asset_interface", EntitySourceLink.external_id == claim.subject_external_id))
    if (not keys and owner_id is None) or not is_proxmox_source(db, item, claim.data_source_id):
        return
    held = _pending_reviews(item, claim.data_source_id).where(
        ReconciliationItem.candidate_external_id.in_(keys) | (ReconciliationItem.entity_id == owner_id))
    if db.execute(held.limit(1)).first() or linked_retired_guests(
        db, item, claim.data_source_id, keys=keys, owner_id=owner_id
    ):
        raise HTTPException(409, PROPOSAL_HELD)


def simulation_hold_keys(db, run, external_ids):
    """A simulation cannot submit evidence for a retained live guest identity."""
    if not is_proxmox_source(db, run, run.data_source_id):
        return set()
    keys = {key for key in external_ids if key and GUEST_KEY.fullmatch(key)}
    held = set(db.scalars(_pending_reviews(run, run.data_source_id).with_only_columns(
        ReconciliationItem.candidate_external_id)))
    if keys & held or (keys and linked_retired_guests(db, run, run.data_source_id, keys=keys)):
        raise HTTPException(409, PROPOSAL_HELD)
    return held


@dataclass
class GuestHold:
    object_class: str
    retired_asset: Asset | None
    previous_review: tuple[ReconciliationItem, KnowledgeAssertion] | None
    observations: set[tuple[str, str]]


@dataclass
class GuestHolds:
    by_key: dict[str, GuestHold] = field(default_factory=dict)
    cases: set[str] = field(default_factory=set)
    observations: set[tuple[str, str]] = field(default_factory=set)
    assertions_created: int = 0
    items_created: int = 0

    def relationship_endpoint_class(self, relationship_id, guest_key):
        hold = self.by_key.get(guest_key)
        if hold and ("relationship", relationship_id) in hold.observations:
            return hold.object_class
        return None


def _accepted_snapshot(db, scope, asset):
    rows = db.execute(select(AssetInterface, Network.name).outerjoin(
        Network, (Network.id == AssetInterface.network_id) &
        (Network.customer_id == scope.customer_id) & (Network.site_id == scope.site_id)
    ).where(AssetInterface.asset_id == asset.id).order_by(AssetInterface.name, AssetInterface.id)
      .limit(PREVIEW_LIMIT + 1)).all()
    relationships = db.execute(select(RelationshipType.name, Asset.name).select_from(AssetRelationship)
        .join(RelationshipType, RelationshipType.key == AssetRelationship.relationship_type)
        .join(Asset, Asset.id == AssetRelationship.target_asset_id)
        .where(AssetRelationship.source_asset_id == asset.id, AssetRelationship.customer_id == scope.customer_id,
            AssetRelationship.site_id == scope.site_id, Asset.customer_id == scope.customer_id, Asset.site_id == scope.site_id)
        .order_by(RelationshipType.name, Asset.name, AssetRelationship.id).limit(PREVIEW_LIMIT + 1)).all()
    return {"name": asset.name, "lifecycle_status": asset.status, "asset_id": asset.id,
            "interfaces": [{"name": nic.name, "mac_address": nic.mac_address,
                            "ip_address": nic.ip_address, "assigned_network": network}
                           for nic, network in rows[:PREVIEW_LIMIT]],
            "more_interfaces": len(rows) > PREVIEW_LIMIT,
            "relationships": [{"type": label, "target": name} for label, name in relationships[:PREVIEW_LIMIT]],
            "more_relationships": len(relationships) > PREVIEW_LIMIT}


def _evidence_preview(guest, records):
    keys = {
        "asset_interface": ("external_id", "name", "mac_address", "ip_address", "network_external_id"),
        "relationship": ("external_id", "relationship_class", "source", "target"),
    }
    preview = {"name": guest.payload_json["name"] if guest else None}
    for kind, fields in keys.items():
        matching = [row for row in records if row.entity_kind == kind]
        preview["interfaces" if kind == "asset_interface" else "relationships"] = [
            {key: row.payload_json[key] for key in fields if key in row.payload_json}
            for row in matching[:PREVIEW_LIMIT]]
        preview[f"{kind}_count"] = len(matching)
    return preview


def _record_review(db, run, asset, key, records, previous):
    from app.services.reconciliation import create_item

    item, previous_claim = previous if previous else (None, None)
    guest = next((row for row in records if row.entity_kind == "asset"), None)
    anchor = guest or max(records, key=lambda row: (row.observed_at, row.id))
    claim = KnowledgeAssertion(
        customer_id=run.customer_id, site_id=run.site_id, subject_type=REVIEW_TYPE,
        subject_external_id=key, predicate=PRESENCE_PREDICATE, truth_classification="observed",
        confirmation_status="unreviewed", data_source_id=run.data_source_id,
        discovery_run_id=run.id, evidence_record_id=anchor.id,
        first_observed_at=anchor.observed_at, last_observed_at=anchor.observed_at,
        value_json={"guest_observed": guest is not None,
                    "held_evidence_ids": [str(row.id) for row in records]},
        is_current=True, is_source_current=True, is_accepted=False,
    )
    db.add(claim)
    db.flush()
    if previous_claim:
        previous_run = db.get(DiscoveryRun, previous_claim.discovery_run_id)
        # The server's run start orders the evidence across completions. Source
        # clocks and request delivery order cannot make an older run win.
        closed_at = max(anchor.observed_at, previous_claim.last_observed_at)
        if (run.started_at, anchor.observed_at, run.id) <= (
                previous_run.started_at, previous_claim.last_observed_at, previous_run.id):
            mark_superseded(claim, previous_claim, closed_at)
            return False
        mark_superseded(previous_claim, claim, closed_at)
    observed = to_json_value(_evidence_preview(guest, records))
    if item:
        item.assertion_id = claim.id
        item.observed_value_json = observed
        return False
    create_item(db, assertion=claim, category="possible_duplicate", entity_type=REVIEW_TYPE,
        entity_id=asset.id, candidate_external_id=key,
        current_value=_accepted_snapshot(db, run, asset), observed_value=observed,
        recommended_action=REVIEW_REQUIRED)
    return True


def classify_guest_holds(db, run, links, evidence):
    """Classify under Source and canonical subject locks before writing reviews."""
    result = GuestHolds()
    if run.execution_provenance["connector_id"] != "proxmox":
        return result

    source_id = run.data_source_id
    reviews = {item.candidate_external_id: (item, claim)
               for item, claim in db.execute(_pending_reviews(run, source_id))}
    result.cases.update(reviews)

    references = defaultdict(set)
    interfaces_by_owner = defaultdict(set)
    for (kind, external), row in evidence.items():
        if kind == "asset":
            references[external].add((kind, external))
        elif kind == "asset_interface":
            references[row.payload_json["asset_external_id"]].add((kind, external))
            slot = interface_guest(external)
            if slot:
                references[slot].add((kind, external))
            link = links.get((kind, external))
            if link:
                interfaces_by_owner[link.interface_owner_id].add((kind, external))
        elif kind == "relationship":
            for side in ("source", "target"):
                references[row.payload_json[side]["external_id"]].add((kind, external))

    candidate_assets = {}
    for (kind, key), link in links.items():
        guest = GUEST_KEY.fullmatch(key) if kind == "asset" else None
        if guest:
            references[key].update(interfaces_by_owner.get(link.entity_id, ()))
            if references[key]:
                candidate_assets[key] = (link.entity_id, f"proxmox.{guest[1]}")
    targets = {asset.id: asset for asset in db.scalars(select(Asset).where(
        Asset.id.in_({asset_id for asset_id, _ in candidate_assets.values()}), Asset.customer_id == run.customer_id,
        Asset.site_id == run.site_id, Asset.status == "retired"))}
    for key, (asset_id, object_class) in sorted(candidate_assets.items()):
        asset, previous = targets.get(asset_id), reviews.get(key)
        if asset is None and previous is None:
            continue
        result.by_key[key] = GuestHold(object_class, asset, previous, references[key])
        result.cases.add(key)
        result.observations.update(references[key])
    return result


def record_guest_holds(db, run, holds, evidence):
    """Record validated evidence in the same transaction as the run seal."""
    prior = [hold.previous_review for hold in holds.by_key.values() if hold.previous_review]
    if prior:
        for model, identifiers in (
            (ReconciliationItem, [item.id for item, _ in prior]),
            (KnowledgeAssertion, [claim.id for _, claim in prior]),
        ):
            list(db.scalars(select(model).where(model.id.in_(identifiers)).order_by(model.id).with_for_update()))
    for key, hold in holds.by_key.items():
        records = [evidence[identity] for identity in sorted(hold.observations)]
        created = _record_review(db, run, hold.retired_asset, key, records, hold.previous_review)
        holds.items_created += int(created)
        holds.assertions_created += 1
