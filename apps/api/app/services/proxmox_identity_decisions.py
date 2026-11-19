"""Operator decisions for a single locked Proxmox guest binding."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import String, cast, literal_column, select

from atlas_connector_sdk.aip import body_hash
from app.authorization import refresh_principal
from app.models import (Asset, AssetInterface, AssetRelationship, AssetType, ConnectorMapping, Customer, DataSource,
    EntitySourceLink, Integration, KnowledgeAssertion, Network, ProxmoxGuestIdentityDecision, ReconciliationItem,
    RelationshipType, Site)
from app.services.connector_mappings import mapping_state
from app.services.knowledge_locks import SUBJECT_MODELS, lock_subjects
from app.services.proxmox_guest_bindings import GUEST_KEY, GuestBindings, attribution_epoch, historical_link, interface_guest
from app.services.proxmox_guest_identity import REVIEW_TYPE, _pending_reviews
from app.services.proxmox_identity_evidence import UNAVAILABLE_EVIDENCE, accepted_endpoint_evidence, reviewed_evidence
from app.utils.json_values import to_json_value

READ_GRANTS = ("reconciliation.view", "assets.view")
DECISION_GRANTS = {
    "reactivate": ("reconciliation.decide", "assets.edit"),
    "replace": ("reconciliation.decide", "assets.edit", "assets.create", "networks.view", "networks.edit"),
}
CHANGED = "This identity review changed; refresh and review the comparison before deciding."
MISSING_GUEST = "Run discovery with this guest included to review it as a replacement."
ACTIVE_ASSET = "This Asset is active. Confirm the same guest, or review its lifecycle before choosing a replacement."
OWNERSHIP_CONFLICT = "Review the source bindings and Interface ownership before choosing a replacement."
MAPPING_REQUIRED = "Run discovery with a valid guest name and active Asset type mapping before choosing a replacement."
LIFECYCLE_REQUIRED = "Review the current Asset lifecycle before choosing an identity decision."


def _scoped(item, row):
    return row is not None and (row.customer_id, row.site_id) == (item.customer_id, item.site_id)


def _permitted(principal, item, grants):
    return all(principal.can(key, item.customer_id, item.site_id) for key in grants)


def require_visible(principal, context, item):
    if (item is None or item.entity_type != REVIEW_TYPE
            or context.customer_id not in {None, item.customer_id} or context.site_id not in {None, item.site_id}
            or not _permitted(principal, item, READ_GRANTS)):
        raise HTTPException(404, "Record not found")


def _row_revision(db, model, row):
    if row is None:
        return None
    if db.get_bind().dialect.name == "postgresql":
        return db.scalar(select(cast(literal_column(f"{model.__tablename__}.xmin"), String)).where(model.id == row.id))
    return to_json_value(getattr(row, "updated_at", None))


@dataclass
class ReleasePlan:
    records: list = field(default_factory=list)
    withheld: dict = field(default_factory=dict)
    relationship_types: dict = field(default_factory=dict)
    proof_claims: dict = field(default_factory=dict)
    guest_type: str | None = None
    valid_guest_observation: bool = False
    conflicting_owner: bool = False


class IdentityReview:
    """Compute eligibility and the version using the same inputs for GET and POST."""

    def __init__(self, db, item, claim):
        self.db, self.item, self.claim = db, item, claim
        self.key = item.candidate_external_id
        self.source = db.get(DataSource, claim.data_source_id) if claim and claim.data_source_id else None
        self.asset = db.get(Asset, item.entity_id) if item.entity_id else None
        self.asset = self.asset if _scoped(item, self.asset) else None
        self.integration = None
        self.evidence = None
        self.binding = None
        self.bindings = None
        self.links = {}
        self.owner_links = []
        self.other_slots = []
        self.targets = defaultdict(set)
        self.mapping_rows = []
        self.pinned_mappings = {}
        self.allowed_mappings = {}
        self.types = {}
        self.referenced_links = set()
        self.plan = ReleasePlan()
        self.customer = db.get(Customer, item.customer_id)
        self.site = db.get(Site, item.site_id) if item.site_id else None
        self.decision = db.get(ProxmoxGuestIdentityDecision, item.id) if item.status == "accepted" else None
        if self.asset is not None:
            self.targets["asset"].add(self.asset.id)
        if (not item.site_id or not _scoped(item, self.source) or not _scoped(item, claim)
                or not GUEST_KEY.fullmatch(self.key or "")):
            return
        self.integration = db.scalar(select(Integration).where(Integration.data_source_id == self.source.id,
            Integration.customer_id == item.customer_id, Integration.site_id == item.site_id,
            Integration.connector_id == "proxmox").execution_options(populate_existing=True))
        if self.integration is None:
            return
        self.evidence = reviewed_evidence(db, item, claim, self.integration)
        if self.evidence is None:
            return
        self.bindings = GuestBindings(db, item, self.source.id)
        self.links = {key: link for key in self.bindings.links if (link := self.bindings.current(key))}
        self.binding = self.links.get(("asset", self.key))
        if self.binding is None or self.asset is None or self.binding.entity_id != self.asset.id:
            return
        self.owner_links = sorted((link for (kind, _), link in self.links.items()
            if kind == "asset_interface" and link.interface_owner_id == self.asset.id), key=lambda link: link.id)
        self.other_slots = sorted((link for (kind, key), link in self.links.items()
            if kind == "asset" and key != self.key and GUEST_KEY.fullmatch(key) and link.entity_id == self.asset.id),
            key=lambda link: link.id)
        self.referenced_links.update(self.owner_links + self.other_slots + [self.binding])
        self._load_mappings()
        self._plan_release()
        self._collect_subjects()

    def _load_mappings(self):
        provenance = self.evidence.run.execution_provenance
        manifest = provenance["manifest"]
        self.pinned_mappings = {(row["kind"], row["source_key"]): row for row in provenance.get("mappings", [])}
        self.mapping_rows = list(self.db.scalars(select(ConnectorMapping).where(
            ConnectorMapping.connector_id == manifest["id"], ConnectorMapping.connector_version == manifest["version"])
            .order_by(ConnectorMapping.id).execution_options(populate_existing=True)))
        keys = defaultdict(set)
        for row in self.pinned_mappings.values():
            if row["target_key"]:
                keys[row["kind"]].add(row["target_key"])
        for row in self.mapping_rows:
            if row.target_key:
                keys[row.kind].add(row.target_key)
        for kind, model in (("asset", AssetType), ("relationship", RelationshipType)):
            self.types[kind] = list(self.db.scalars(select(model).where(model.key.in_(keys[kind])).order_by(model.id)
                .execution_options(populate_existing=True)))
        for row in mapping_state(self.db, manifest):
            key = row["kind"], row["source_key"]
            pinned = self.pinned_mappings.get(key)
            if (pinned and row["resolved"] and not row["ignored"]
                    and all(row[field] == pinned.get(field) for field in ("target_key", "resolved", "ignored"))):
                self.allowed_mappings[key] = row["target_key"]

    def _endpoint_class(self, key):
        evidence = self.evidence
        if (positive := evidence.observations.get(("asset", key))) is not None:
            member = evidence.membership.get(("asset", key))
            if (member is None or not _scoped(self.item, member) or member.data_source_id != self.source.id
                    or member.coverage_key != evidence.run.coverage_key or member.observed_at != positive[1]
                    or member.evidence_record_id is None):
                return None
            link = self.links.get(("asset", key))
            if member.entity_id is not None and (link is None or member.entity_id != link.entity_id):
                return None
            return positive[0]["object_class"]
        binding = self.links.get(("asset", key))
        if (binding is None or binding.opened_epoch > evidence.run.identity_epoch
                or binding.created_at > evidence.run.completed_at):
            return None
        for record, claim in accepted_endpoint_evidence(self.db, evidence.run, key, binding):
            epoch = attribution_epoch(self.db, claim)
            if epoch is None or historical_link(self.bindings.links[("asset", key)], epoch) != binding:
                continue
            if isinstance(record.payload_json, dict) and body_hash(record.payload_json) == record.payload_hash:
                self.plan.proof_claims[claim.id] = (record.id, record.payload_hash)
                return record.payload_json.get("object_class")
        return None

    def _plan_release(self):
        evidence, plan = self.evidence, self.plan
        provenance = evidence.run.execution_provenance
        manifest = provenance["manifest"]
        declarations = {row["key"]: row for row in manifest["relationship_classes"]}
        guest_class = "proxmox." + GUEST_KEY.fullmatch(self.key)[1]
        pending = set(self.db.scalars(_pending_reviews(self.item, self.source.id).with_only_columns(
            ReconciliationItem.candidate_external_id))) - {self.key}
        if evidence.guest:
            guest = evidence.guest.payload_json
            name = guest.get("name")
            plan.valid_guest_observation = (guest["object_class"] == guest_class
                and guest_class in provenance["object_classes"] and isinstance(name, str) and 0 < len(name.strip()) <= 255)
            if plan.valid_guest_observation:
                plan.guest_type = self.allowed_mappings.get(("asset", guest_class))
        for record in evidence.held:
            value = record.payload_json
            reason = None
            if record.entity_kind == "asset":
                if not plan.valid_guest_observation:
                    reason = "invalid_guest_observation"
                elif plan.guest_type is None:
                    reason = "asset_mapping_unavailable"
            elif record.entity_kind == "asset_interface":
                alias = ("asset_interface", record.external_id)
                owner = value["asset_external_id"]
                typed_slot = interface_guest(record.external_id)
                link = self.links.get(alias)
                net_key = value.get("network_external_id")
                net_link = self.links.get(("network", net_key))
                net_member = evidence.membership.get(("network", net_key))
                self.referenced_links.update(link for link in (link, net_link) if link is not None)
                if link and link.interface_owner_id != self.asset.id and (owner == self.key or typed_slot == self.key):
                    plan.conflicting_owner = True
                    reason = "interface_owner_conflict"
                elif owner != self.key or typed_slot not in {None, self.key}:
                    reason = "interface_owner_mismatch"
                elif (self.bindings.latest({alias}) > evidence.run.identity_epoch
                        or net_key and net_link is None and net_member is None
                        or net_member is not None and (not _scoped(self.item, net_member)
                            or net_member.data_source_id != self.source.id or net_member.coverage_key != evidence.run.coverage_key
                            or net_member.entity_id is not None and (net_link is None or net_link.network_id != net_member.entity_id))):
                    reason = "interface_reference_changed"
            else:
                declaration = declarations[value["relationship_class"]]
                endpoints = {side: value[side]["external_id"] for side in ("source", "target")}
                allowed = self.allowed_mappings.get(("relationship", value["relationship_class"]))
                for key in endpoints.values():
                    if link := self.links.get(("asset", key)):
                        self.referenced_links.add(link)
                if self.key not in endpoints.values() or list(endpoints.values()).count(self.key) != 1:
                    reason = "invalid_relationship_guest"
                elif not allowed:
                    reason = "relationship_mapping_unavailable"
                else:
                    for side, key in endpoints.items():
                        if key == self.key:
                            object_class = guest_class if evidence.guest is None or plan.valid_guest_observation else None
                        else:
                            other = self.links.get(("asset", key))
                            asset = self.db.get(Asset, other.entity_id) if other else None
                            if (key in pending or (GUEST_KEY.fullmatch(key) and asset and self.bindings.needs_review(asset, other))
                                    or self.bindings.latest({("asset", key)}) > evidence.run.identity_epoch):
                                reason = "other_identity_pending_or_changed"
                                break
                            object_class = self._endpoint_class(key)
                        if object_class not in declaration[side + "_object_classes"]:
                            reason = "relationship_reference_unverified"
                            break
                    if reason is None:
                        if declaration["direction"] == "target_to_source":
                            endpoints["source"], endpoints["target"] = endpoints["target"], endpoints["source"]
                        plan.relationship_types[record.id] = allowed, endpoints["source"], endpoints["target"]
            if reason:
                plan.withheld[record.id] = reason
            else:
                plan.records.append(record)

    def _collect_subjects(self):
        for link in self.referenced_links:
            self.targets["asset"].update(identifier for identifier in (link.entity_id, link.interface_owner_id) if identifier)
            if link.interface_id:
                self.targets["asset_interface"].add(link.interface_id)
            if link.network_id:
                self.targets["network"].add(link.network_id)
        interfaces = select(AssetInterface.network_id).where(AssetInterface.id.in_(self.targets["asset_interface"]),
            AssetInterface.network_id.is_not(None))
        self.targets["network"].update(self.db.scalars(interfaces))
        assets = self.targets["asset"]
        self.targets["asset_relationship"].update(self.db.scalars(select(AssetRelationship.id).where(
            AssetRelationship.customer_id == self.item.customer_id, AssetRelationship.site_id == self.item.site_id,
            AssetRelationship.source_asset_id.in_(assets), AssetRelationship.target_asset_id.in_(assets))))

    def lock_references(self):
        lock_subjects(self.db, self.targets)
        rows_by_model = {Customer: [self.customer], Site: [self.site], ConnectorMapping: self.mapping_rows,
            AssetType: self.types.get("asset", []), RelationshipType: self.types.get("relationship", [])}
        for model, rows in rows_by_model.items():
            ids = [row.id for row in rows if row is not None]
            if ids:
                list(self.db.scalars(select(model).where(model.id.in_(ids)).order_by(model.id)
                    .with_for_update(read=True, of=model).execution_options(populate_existing=True)))

    def version(self):
        item, claim, evidence = self.item, self.claim, self.evidence
        references = [[link.id, link.entity_type, link.external_id, link.entity_id, link.interface_id, link.interface_owner_id,
                       link.network_id, link.opened_epoch, link.ended_epoch] for link in sorted(self.referenced_links, key=lambda row: row.id)]
        subjects = [[kind, identifier, _row_revision(self.db, model, self.db.get(model, identifier))]
            for kind, model in SUBJECT_MODELS.items() for identifier in sorted(self.targets[kind])]
        value = [item.id, item.status, item.updated_at, item.assertion_id, item.entity_id, self.key,
            item.current_value_json, self.asset.status if self.asset else None,
            self.asset.identity_retirement_revision if self.asset else None, subjects, references,
            self.integration.id if self.integration else None,
            [[row.id, row.updated_at, row.status] for row in (self.customer, self.site) if row],
            sorted((kind, key, target) for (kind, key), target in self.allowed_mappings.items()),
            [[row.id, _row_revision(self.db, ConnectorMapping, row)] for row in self.mapping_rows],
            [[row.id, _row_revision(self.db, model, row)] for kind, model in (("asset", AssetType), ("relationship", RelationshipType))
             for row in self.types.get(kind, [])],
            [claim.updated_at, claim.value_json, claim.is_source_current, claim.retracted_at, claim.superseded_by_id] if claim else None,
            [evidence.run.id, evidence.run.finalisation_hash, evidence.run.execution_provenance, evidence.receipt_hashes,
             [[row.id, row.payload_hash] for row in evidence.held]] if evidence else None,
            sorted(self.plan.withheld.items()), sorted(self.plan.proof_claims.items())]
        return body_hash(to_json_value(value))

    def blocked(self, outcome):
        if self.item.status != "open":
            return "This identity review has already been decided."
        if not self.evidence:
            return UNAVAILABLE_EVIDENCE
        if (self.binding is None or self.asset is None or self.binding.entity_id != self.asset.id
                or self.bindings.latest({("asset", self.key)}) > self.evidence.run.identity_epoch):
            return "The current guest binding has changed. Run discovery to review current evidence."
        if self.evidence.guest and not self.plan.valid_guest_observation:
            return UNAVAILABLE_EVIDENCE
        if self.asset.status not in {"active", "retired"}:
            return LIFECYCLE_REQUIRED
        if outcome == "reactivate":
            return None if self.plan.valid_guest_observation or self.plan.records else UNAVAILABLE_EVIDENCE
        if self.asset.status == "active":
            return ACTIVE_ASSET
        if self.evidence.guest is None:
            return MISSING_GUEST
        if self.plan.guest_type is None:
            return MAPPING_REQUIRED
        if not self.customer or not self.site or self.site.customer_id != self.customer.id or (
                self.customer.status, self.site.status) != ("active", "active"):
            return "A replacement Asset requires an active Customer and Site."
        if (self.other_slots or self.plan.conflicting_owner
                or any(interface_guest(row.external_id) not in {None, self.key} for row in self.owner_links)):
            return OWNERSHIP_CONFLICT
        return None

    def action_reason(self, principal, outcome):
        if not _permitted(principal, self.item, DECISION_GRANTS[outcome]):
            return "You do not have the required permissions in this Customer and Site."
        return self.blocked(outcome)

    def present(self, principal):
        from app.services.proxmox_guest_identity import _evidence_preview, review_snapshot

        evidence = self.evidence
        observed = {"name": None, "guest_observed": None}
        if evidence:
            can_view_network = _permitted(principal, self.item, ("networks.view",))
            visible_records = [row for row in evidence.held if row.entity_kind == "asset"
                or row.entity_kind == "asset_interface" and can_view_network
                or row.entity_kind == "relationship" and self._relationship_visible(principal, row)]
            observed = _evidence_preview(evidence.guest, visible_records)
            observed["guest_observed"] = evidence.guest is not None
            if not can_view_network:
                observed.pop("interfaces")
                observed.pop("asset_interface_count")
            if not _permitted(principal, self.item, ("relationships.view",)):
                observed.pop("relationships")
                observed.pop("relationship_count")
        outcome = self.decision.outcome if self.decision else None
        reasons = {outcome: self.action_reason(principal, outcome) for outcome in DECISION_GRANTS}
        return {
            "current": review_snapshot(self.db, principal, self.item), "observed": observed,
            "review": {"expected_version": self.version(), "current_asset_status": self.asset.status if self.asset else None,
                "observed_at": evidence.anchor.observed_at if evidence else None,
                "outcome": outcome, "actions": reasons, "withheld": self._visible_withheld(principal)},
            "discovery_run_id": evidence.run.id if evidence else None,
        }

    def _relationship_visible(self, principal, row):
        if not _permitted(principal, self.item, ("relationships.view",)):
            return False
        for side in ("source", "target"):
            key = row.payload_json[side]["external_id"]
            member = self.evidence.membership.get(("asset", key))
            identifier = member.entity_id if member and _scoped(self.item, member) else None
            if identifier is None:
                binding = historical_link(self.bindings.links.get(("asset", key), ()), self.evidence.run.identity_epoch)
                identifier = binding.entity_id if binding and binding.created_at <= self.evidence.run.completed_at else None
            asset = self.db.get(Asset, identifier) if identifier else None
            if not _scoped(self.item, asset) or not principal.can("assets.view", asset.customer_id, asset.site_id):
                return False
        return True

    def _visible_withheld(self, principal):
        if not self.evidence:
            return {}
        withheld = self.plan.withheld
        if self.decision:
            from app.models import KnowledgeChange
            change = self.db.scalar(select(KnowledgeChange).where(
                KnowledgeChange.reconciliation_item_id == self.item.id,
                KnowledgeChange.change_type.in_(("identity_confirmed", "identity_replaced", "lifecycle_changed"))))
            entries = (change.metadata_json or {}).get("withheld_evidence", []) if change else []
            withheld = {entry["id"]: entry["reason"] for entry in entries}
        by_reason = defaultdict(int)
        for row in self.evidence.held:
            reason = withheld.get(row.id) or withheld.get(str(row.id))
            if reason and (row.entity_kind == "asset"
                    or row.entity_kind == "asset_interface" and _permitted(principal, self.item, ("networks.view",))
                    or row.entity_kind == "relationship" and self._relationship_visible(principal, row)):
                by_reason[reason] += 1
        return dict(by_reason)


def lock_review(db, item_id, principal, context, payload):
    item = db.get(ReconciliationItem, item_id)
    require_visible(principal, context, item)
    if principal.user.force_password_change or not _permitted(principal, item, DECISION_GRANTS[payload.outcome]):
        raise HTTPException(403, "You do not have the required permissions in this Customer and Site.")
    claim = db.get(KnowledgeAssertion, item.assertion_id)
    source_id = claim.data_source_id if _scoped(item, claim) else None
    integration = db.scalar(select(Integration).where(Integration.data_source_id == source_id,
        Integration.customer_id == item.customer_id, Integration.site_id == item.site_id,
        Integration.connector_id == "proxmox").with_for_update().execution_options(populate_existing=True)) if source_id else None
    source = db.get(DataSource, source_id, with_for_update={"key_share": True}, populate_existing=True) if integration else None
    if not _scoped(item, source):
        raise HTTPException(409, UNAVAILABLE_EVIDENCE)
    # The callback lock order is Integration -> Run -> Source. From here, read
    # sealed run provenance only. Taking a Run writer lock here would invert it.
    item = db.get(ReconciliationItem, item_id, populate_existing=True)
    require_visible(principal, context, item)
    claim = db.get(KnowledgeAssertion, item.assertion_id, populate_existing=True)
    if not _scoped(item, claim) or claim.data_source_id != source.id:
        raise HTTPException(409, CHANGED)
    initial = IdentityReview(db, item, claim)
    initial.lock_references()
    item = db.get(ReconciliationItem, item_id, with_for_update=True, populate_existing=True)
    require_visible(principal, context, item)
    claim_ids = set(initial.plan.proof_claims) | {item.assertion_id}
    if payload.outcome == "reactivate" and initial.asset:
        claim_ids.update(db.scalars(select(KnowledgeAssertion.id).where(
            KnowledgeAssertion.customer_id == item.customer_id, KnowledgeAssertion.site_id == item.site_id,
            KnowledgeAssertion.subject_type == "asset", KnowledgeAssertion.subject_id == initial.asset.id,
            KnowledgeAssertion.predicate == "status")))
    claims = {claim.id: claim for claim in db.scalars(select(KnowledgeAssertion).where(KnowledgeAssertion.id.in_(claim_ids))
        .order_by(KnowledgeAssertion.id).with_for_update().execution_options(populate_existing=True))}
    principal = refresh_principal(principal, db)
    require_visible(principal, context, item)
    if principal.user.force_password_change or not _permitted(principal, item, DECISION_GRANTS[payload.outcome]):
        raise HTTPException(403, "You do not have the required permissions in this Customer and Site.")
    review = IdentityReview(db, item, claims.get(item.assertion_id))
    if (review.source is not source or review.integration is not integration
            or any(ids - initial.targets[kind] for kind, ids in review.targets.items())
            or set(review.plan.proof_claims) - claims.keys() or review.version() != payload.expected_version):
        raise HTTPException(409, CHANGED)
    if reason := review.blocked(payload.outcome):
        raise HTTPException(409, reason)
    return review, principal


def _replace_binding(review, epoch):
    """This is the only writer of ended_epoch, scoped to this locked case's guest."""
    from app.services.reconciliation import construct_discovered_asset

    db, item, old = review.db, review.item, review.binding
    old_asset = review.asset
    if (review.blocked("replace") or old.entity_type != "asset" or old.external_id != review.key
            or old.entity_id != item.entity_id or old_asset.status != "retired"
            or old.data_source_id != review.source.id or old.ended_epoch is not None or not _scoped(item, old)):
        raise HTTPException(409, CHANGED)
    for link in review.owner_links:
        if (link.entity_type != "asset_interface" or link.data_source_id != old.data_source_id or not _scoped(item, link)
                or link.interface_owner_id != old.entity_id or link.ended_epoch is not None
                or interface_guest(link.external_id) not in {None, old.external_id}):
            raise HTTPException(409, OWNERSHIP_CONFLICT)
    guest = review.evidence.guest
    attributes = {"name": guest.payload_json["name"], "asset_type": review.plan.guest_type}
    asset = construct_discovered_asset(db, review.customer, review.site, review.key, attributes)
    ended = [old, *review.owner_links]
    for link in ended:
        link.ended_epoch = epoch
    db.flush()  # Release the partial uniqueness slot. The decision FK is deferred.
    binding = EntitySourceLink(customer_id=item.customer_id, site_id=item.site_id, data_source_id=old.data_source_id,
        entity_type="asset", entity_id=asset.id, external_id=old.external_id, opened_epoch=epoch,
        external_type=guest.payload_json["object_class"], first_observed_at=guest.observed_at, last_observed_at=guest.observed_at)
    db.add(binding)
    db.flush()
    return asset, binding, [link.id for link in ended]


def _reactivate(review, user_id, now):
    from app.services.data_sources import manual_inventory_source
    from app.services.knowledge_assertions import accept_assertion, record_assertion

    asset = review.asset
    if asset.status == "active":
        return None
    source = manual_inventory_source(review.db, asset.customer_id, asset.site_id)
    asset.status = "active"
    claim, _ = record_assertion(review.db, customer_id=asset.customer_id, site_id=asset.site_id,
        subject_type="asset", subject_id=asset.id, predicate="status", value="active",
        truth_classification="declared", data_source_id=source.id, observed_at=now, coalesce=False)
    accept_assertion(review.db, claim, user_id=user_id, accepted_at=now)
    return claim


def release_proposals(review, asset, epoch, user_id):
    """Create fresh, unaccepted claims with the original receipt provenance."""
    from app.services.knowledge_assertions import record_assertion
    from app.services.reconciliation import create_item, relationship_resolution
    from app.services.simulated_discovery import propose_technical_observation

    db, item, source = review.db, review.item, review.source
    run = review.evidence.run
    bindings = GuestBindings(db, item, source.id)
    for record in review.plan.records:
        payload = record.payload_json
        attribution = dict(customer_id=item.customer_id, site_id=item.site_id, data_source_id=source.id,
            discovery_run_id=run.id, evidence_record_id=record.id, observed_at=record.observed_at,
            guest_bindings=bindings, identity_epoch=epoch, reviewed_release=True)
        if record.entity_kind == "asset":
            fields = [("name", payload["name"], None), ("asset_type", review.plan.guest_type, None)]
            fields.extend((key, payload[key], None) for key in ("hostname", "status") if key in payload)
            fields.extend((fact["key"], fact["value"], {name: fact[name] for name in ("value_type", "class", "cardinality")})
                         for fact in payload["facts"])
            for predicate, value, metadata in fields:
                claim, _ = record_assertion(db, subject_type="asset", subject_id=asset.id, subject_external_id=review.key,
                    predicate=predicate, value=value, fact_metadata=metadata, **attribution)
                current = None if metadata else {"field": predicate, "value": getattr(asset, predicate)}
                create_item(db, assertion=claim, category="changed", entity_type="asset", entity_id=asset.id,
                    candidate_external_id=review.key, current_value=current, observed_value={"field": predicate, "value": value},
                    recommended_action="Review source fact" if metadata else f"Review Asset {predicate}")
        elif record.entity_kind == "asset_interface":
            link = bindings.current(("asset_interface", record.external_id))
            interface = db.get(AssetInterface, link.interface_id) if link else None
            propose_technical_observation(db, run=run, source=source, evidence=record, observation=payload,
                entity_type="asset_interface", target=interface, user_id=user_id, guest_bindings=bindings, release_epoch=epoch)
        else:
            key, src, dst = review.plan.relationship_types[record.id]
            src_link, dst_link = (bindings.current(("asset", external)) for external in (src, dst))
            claim, _ = record_assertion(db, subject_type="asset", subject_external_id=src,
                subject_id=src_link.entity_id if src_link else None, object_type="asset", object_external_id=dst,
                object_id=dst_link.entity_id if dst_link else None, predicate=key,
                truth_classification=payload["truth_classification"], confidence=payload["confidence"], **attribution)
            proposal, _ = create_item(db, assertion=claim, category="inferred_relationship", entity_type="asset_relationship",
                entity_id=None, candidate_external_id=src, current_value=None,
                observed_value={"source_external_id": src, "target_external_id": dst, "relationship_type": key},
                recommended_action="Review relationship observation")
            current = relationship_resolution(db, proposal, persist_links=False, refresh=True, bindings=bindings)
            if current["current_relationship_id"] and proposal.current_value_json["relationship_type"] != key:
                proposal.category = "contradiction"
    db.flush()


def decide_review(review, payload, principal, request):
    from app.audit import add_audit_event
    from app.services.knowledge_changes import record_change
    from app.services.knowledge_completeness import evaluate_asset_safely

    db, item, source = review.db, review.item, review.source
    now = datetime.now(timezone.utc)
    actor = principal.user
    epoch = source.identity_epoch + 1
    source.identity_epoch = epoch
    new_binding, ended, lifecycle_claim = None, [], None
    if payload.outcome == "replace":
        asset, new_binding, ended = _replace_binding(review, epoch)
    else:
        asset = review.asset
        lifecycle_claim = _reactivate(review, actor.id, now)
    db.add(ProxmoxGuestIdentityDecision(reconciliation_item_id=item.id, data_source_id=source.id,
        identity_epoch=epoch, old_binding_id=review.binding.id, replacement_binding_id=new_binding.id if new_binding else None,
        reviewed_assertion_id=review.claim.id, retirement_revision=review.asset.identity_retirement_revision, outcome=payload.outcome))
    item.status, item.decision_reason, item.decided_by_user_id, item.decided_at = "accepted", payload.reason, actor.id, now
    db.flush()
    release_proposals(review, asset, epoch, actor.id)
    evidence = review.evidence
    metadata = {"outcome": payload.outcome, "guest_key": review.key, "identity_epoch": epoch,
        "retirement_revision": review.asset.identity_retirement_revision,
        "old_asset_id": review.asset.id, "new_asset_id": asset.id if new_binding else None,
        "old_binding_id": review.binding.id, "new_binding_id": new_binding.id if new_binding else None,
        "ended_binding_ids": ended, "reviewed_run_id": evidence.run.id,
        "reviewed_assertion_id": review.claim.id, "reason": payload.reason}
    if new_binding:
        record_change(db, customer_id=item.customer_id, site_id=item.site_id, change_type="entity_accepted", entity_type="asset",
            entity_id=asset.id, entity_name=asset.name, summary=f"Created {asset.name} as a replacement guest",
            new_value={"name": asset.name, "asset_type": asset.asset_type, "status": asset.status,
                "customer_id": asset.customer_id, "site_id": asset.site_id, "workspace_id": asset.workspace_id},
            data_source_id=source.id, discovery_run_id=evidence.run.id, reconciliation_item_id=item.id, occurred_at=now,
            actor_user_id=actor.id, metadata={"origin": "proxmox_guest_identity", "evidence_id": evidence.guest.id})
    change_type = "identity_replaced" if new_binding else "lifecycle_changed" if lifecycle_claim else "identity_confirmed"
    summary = (f"Replaced the guest bound to {review.asset.name}" if new_binding
               else f"Reactivated {asset.name} as the same guest" if lifecycle_claim else f"Confirmed {asset.name} as the same guest")
    record_change(db, customer_id=item.customer_id, site_id=item.site_id, change_type=change_type, entity_type="asset",
        entity_id=review.asset.id, entity_name=review.asset.name, summary=summary,
        predicate="status" if lifecycle_claim else None, previous_value="retired" if lifecycle_claim else None,
        new_value="active" if lifecycle_claim else None, truth_classification="declared" if lifecycle_claim else None,
        data_source_id=source.id, discovery_run_id=evidence.run.id, occurred_at=now,
        assertion_id=lifecycle_claim.id if lifecycle_claim else review.claim.id, reconciliation_item_id=item.id, actor_user_id=actor.id,
        metadata={**metadata, "origin": "proxmox_guest_identity", "released_evidence_ids": [row.id for row in review.plan.records],
            "withheld_evidence": [{"id": eid, "reason": reason} for eid, reason in review.plan.withheld.items()]})
    add_audit_event(db, action=f"reconciliation.identity_{payload.outcome}", target_type="reconciliation_item",
        target_id=item.id, actor=actor, workspace_id=review.customer.workspace_id if review.customer else None,
        customer_id=item.customer_id, site_id=item.site_id, summary=summary, metadata=metadata, request=request)
    db.flush()
    if new_binding or lifecycle_claim:
        evaluate_asset_safely(db, asset, trigger_context="reconciliation_accepted", actor_user_id=actor.id)
    return {"id": item.id, "status": item.status, "outcome": payload.outcome}
