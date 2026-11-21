"""Hold Proxmox guest-slot evidence on the source side of the canonical boundary."""

from collections import defaultdict
import uuid
from dataclasses import dataclass, field

from fastapi import HTTPException
from sqlalchemy import select

from app.models import (
    Asset, AssetInterface, AssetRelationship, DiscoveryRun, EntitySourceLink,
    KnowledgeAssertion, Network, ReconciliationItem, RelationshipType,
)
from app.services.entity_resolution import scoped_source_links
from app.services.knowledge_assertions import mark_superseded
from app.services.proxmox_guest_bindings import GUEST_KEY, STALE_PROPOSAL, GuestBindings, interface_guest
from app.utils.json_values import to_json_value

REVIEW_TYPE = "source_identity"
REVIEW_LABEL = "Identity review"
REVIEW_REQUIRED = "This source key requires a guest identity decision"
PROPOSAL_HELD = "This source proposal cannot be applied in its current state"
PRESENCE_PREDICATE = "source_key_present"
PREVIEW_LIMIT = 8


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


def review_snapshot(db, principal, item):
    """Only proven, currently readable scopes can reveal retained details."""
    snapshot = dict(item.current_value_json or {})
    if not principal.can("networks.view", item.customer_id, item.site_id):
        snapshot.pop("interfaces", None)
        snapshot.pop("more_interfaces", None)
    relationships = snapshot.pop("relationships", [])
    snapshot.pop("more_relationships", None)
    if principal.can("relationships.view", item.customer_id, item.site_id):
        visible = []
        for row in relationships[:PREVIEW_LIMIT]:
            try:
                target = db.get(Asset, uuid.UUID(row["target_asset_id"]))
            except (AttributeError, KeyError, TypeError, ValueError):
                continue
            if (target and (target.customer_id, target.site_id) == (item.customer_id, item.site_id)
                    and principal.can("assets.view", target.customer_id, target.site_id)):
                visible.append({"type": row["type"], "target": row["target"]})
        if visible:
            snapshot["relationships"] = visible
        # An undisplayed endpoint cannot be reauthorized, including the overflow.
    return snapshot


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


def linked_retired_guests(db, scope, source_id, *, keys, owner_id=None, bindings):
    query = scoped_source_links(data_source_id=source_id, customer_id=scope.customer_id, site_id=scope.site_id)
    query = query.join(Asset, Asset.id == EntitySourceLink.entity_id).where(
        EntitySourceLink.entity_type == "asset")
    for link, asset in db.execute(query.add_columns(Asset).where(
        (EntitySourceLink.external_id.in_(keys)) | (EntitySourceLink.entity_id == owner_id)
    )):
        if GUEST_KEY.fullmatch(link.external_id) and bindings.needs_review(asset, link):
            return True
    return False


def require_applicable_proposal(db, item, claim):
    """Recheck while the caller holds source and canonical decision locks."""
    require_ordinary_item(item)
    if not claim.data_source_id or item.entity_type not in {"asset", "asset_interface", "asset_relationship"}:
        return
    bindings = GuestBindings.for_scope(db, item, claim.data_source_id)
    if bindings is None:
        return
    if bindings.stale(claim, item=item):
        raise HTTPException(409, STALE_PROPOSAL)
    keys = {key for kind, key in bindings.claim_aliases(claim, claim.identity_epoch) if kind == "asset"}
    keys.update(proposal_guest_keys(item, claim))
    owner_id = None
    if item.entity_type == "asset_interface":
        slot, owner = interface_guest(claim.subject_external_id), bindings.interface_owner(claim)
        if slot and owner and slot != owner:
            raise HTTPException(409, "The Interface key and observed owner disagree")
        links = scoped_source_links(data_source_id=claim.data_source_id, customer_id=item.customer_id, site_id=item.site_id)
        owner_id = db.scalar(links.with_only_columns(EntitySourceLink.interface_owner_id).where(
            EntitySourceLink.entity_type == "asset_interface", EntitySourceLink.external_id == claim.subject_external_id))
    if not keys and owner_id is None:
        return
    held = _pending_reviews(item, claim.data_source_id).where(
        ReconciliationItem.candidate_external_id.in_(keys) | (ReconciliationItem.entity_id == owner_id))
    if db.execute(held.limit(1)).first() or linked_retired_guests(
        db, item, claim.data_source_id, keys=keys, owner_id=owner_id, bindings=bindings
    ):
        raise HTTPException(409, PROPOSAL_HELD)


def simulation_hold_keys(db, run, external_ids):
    """A simulation cannot submit evidence for a retained live guest identity."""
    bindings = GuestBindings.for_scope(db, run, run.data_source_id)
    if bindings is None:
        return set()
    keys = {key for key in external_ids if key and GUEST_KEY.fullmatch(key)}
    held = set(db.scalars(_pending_reviews(run, run.data_source_id).with_only_columns(
        ReconciliationItem.candidate_external_id)))
    guarded = held | {key for kind, key in bindings.boundaries if kind == "asset"}
    current = defaultdict(list)
    for kind, key in bindings.links:
        if kind == "asset" and GUEST_KEY.fullmatch(key) and (link := bindings.current((kind, key))):
            current[link.entity_id].append((key, link))
    for asset in db.scalars(select(Asset).where(Asset.id.in_(current))):
        guarded.update(key for key, link in current[asset.id] if bindings.needs_review(asset, link))
    if keys & guarded:
        raise HTTPException(409, PROPOSAL_HELD)
    return guarded


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
    relationships = db.execute(select(AssetRelationship.id, RelationshipType.name, Asset.id, Asset.name).select_from(AssetRelationship)
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
            "relationships": [{"relationship_id": identifier, "type": label, "target_asset_id": target_id, "target": name}
                              for identifier, label, target_id, name in relationships[:PREVIEW_LIMIT]],
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


def valid_guest_name(name):
    return isinstance(name, str) and 0 < len(name.strip()) <= 255


def observes_guest_at_seal(run, key, records, binding, bindings):
    """Classify a hold after AIP reference validation using its original evidence."""
    provenance = run.execution_provenance
    guest_class = f"proxmox.{GUEST_KEY.fullmatch(key)[1]}"
    if guest_class not in provenance["object_classes"]:
        return False
    guest = next((row for row in records if row.entity_kind == "asset"), None)
    if guest:
        payload = guest.payload_json
        return (guest.external_id == key and payload["object_class"] == guest_class
                and valid_guest_name(payload.get("name")))
    declarations = {row["key"]: row for row in provenance["manifest"]["relationship_classes"]}
    mapped_relationships = {row["source_key"] for row in provenance["mappings"] if row["kind"] == "relationship"
        and row["resolved"] and not row["ignored"] and row["target_key"]}
    for row in records:
        payload = row.payload_json
        if row.entity_kind == "relationship":
            relationship_class = payload["relationship_class"]
            sides = [side for side in ("source", "target") if payload[side]["external_id"] == key]
            if (len(sides) == 1 and relationship_class in mapped_relationships
                    and guest_class in declarations[relationship_class][sides[0] + "_object_classes"]):
                return True
        elif (row.entity_kind == "asset_interface" and payload["asset_external_id"] == key
                and interface_guest(row.external_id) in {None, key}):
            links = [link for link in bindings.links.get(("asset_interface", row.external_id), ())
                if link.opened_epoch <= run.identity_epoch
                and (run.completed_at is None or link.created_at <= run.completed_at)
                and (link.ended_epoch is None or run.identity_epoch < link.ended_epoch)]
            if not links or (len(links) == 1 and links[0].interface_owner_id == binding.entity_id):
                return True
    return False


def _record_review(db, run, asset, key, records, previous, *, positive, previous_positive):
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
        value_json={"guest_observed": guest is not None, "identity_positive": positive,
                    "held_evidence_ids": [str(row.id) for row in records]},
        is_current=True, is_source_current=True, is_accepted=False,
    )
    db.add(claim)
    db.flush()
    if previous_claim:
        previous_run = db.get(DiscoveryRun, previous_claim.discovery_run_id)
        # A diagnostic hold cannot displace a positive. With comparable
        # positives, preserve both claims and keep the preview stable on a tie.
        closed_at = max(anchor.observed_at, previous_claim.last_observed_at)
        if ((previous_positive and not positive)
                or (previous_positive == positive and run.started_at <= previous_run.started_at)):
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


def classify_guest_holds(db, run, links, evidence, *, bindings=None):
    """Classify under Source and canonical subject locks before writing reviews."""
    result = GuestHolds()
    if run.execution_provenance["connector_id"] != "proxmox":
        return result
    bindings = bindings or GuestBindings(db, run, run.data_source_id)

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
        Asset.site_id == run.site_id))}
    for key, (asset_id, object_class) in sorted(candidate_assets.items()):
        asset, previous = targets.get(asset_id), reviews.get(key)
        if asset and not bindings.needs_review(asset, links[("asset", key)]):
            asset = None
        if asset is None and previous is None:
            continue
        result.by_key[key] = GuestHold(object_class, asset, previous, references[key])
        result.cases.add(key)
        result.observations.update(references[key])
    return result


def record_guest_holds(db, run, holds, evidence, integration, bindings):
    """Record validated evidence in the same transaction as the run seal."""
    from app.services.proxmox_identity_evidence import held_observes_guest, reviewed_evidence

    prior = [hold.previous_review for hold in holds.by_key.values() if hold.previous_review]
    if prior:
        for model, identifiers in (
            (ReconciliationItem, [item.id for item, _ in prior]),
            (KnowledgeAssertion, [claim.id for _, claim in prior]),
        ):
            list(db.scalars(select(model).where(model.id.in_(identifiers)).order_by(model.id).with_for_update()))
    for key, hold in holds.by_key.items():
        records = [evidence[identity] for identity in sorted(hold.observations)]
        binding = bindings.current(("asset", key))
        positive = observes_guest_at_seal(run, key, records, binding, bindings)
        previous_positive = False
        if hold.previous_review:
            item, claim = hold.previous_review
            marker = claim.value_json.get("identity_positive") if isinstance(claim.value_json, dict) else None
            if isinstance(marker, bool):
                previous_positive = marker
            else:
                previous = reviewed_evidence(db, item, claim, integration)
                previous_positive = previous is not None and held_observes_guest(previous, key, binding, bindings)
        created = _record_review(db, run, hold.retired_asset, key, records, hold.previous_review,
            positive=positive, previous_positive=previous_positive)
        holds.items_created += int(created)
        holds.assertions_created += 1
