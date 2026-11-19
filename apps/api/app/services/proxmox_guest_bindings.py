"""Scoped binding intervals and guest-specific attribution boundaries."""

from collections import defaultdict
import re
from uuid import UUID

from sqlalchemy import select

from app.models import DiscoveryRun, EntitySourceLink, EvidenceRecord, Integration, ProxmoxGuestIdentityDecision


GUEST_KEY = re.compile(r"guest/(lxc|qemu)/[1-9][0-9]{0,8}")
INTERFACE_KEY = re.compile(r"(guest/(?:lxc|qemu)/[1-9][0-9]{0,8})/interface/net[0-9]{1,2}")
STALE_PROPOSAL = "This proposal predates a guest identity decision; review current discovery evidence"


def interface_guest(external_id):
    match = INTERFACE_KEY.fullmatch(external_id or "")
    return match[1] if match else None


def is_proxmox_source(db, scope, source_id):
    return db.scalar(select(Integration.id).where(
        Integration.data_source_id == source_id, Integration.customer_id == scope.customer_id,
        Integration.site_id == scope.site_id, Integration.connector_id == "proxmox")) is not None


def attribution_epoch(db, claim):
    if claim.identity_epoch is not None:
        return claim.identity_epoch
    run = db.get(DiscoveryRun, claim.discovery_run_id) if claim.discovery_run_id else None
    if (run is not None and (run.execution_provenance or {}).get("connector_id") == "proxmox"
            and run.status == "completed" and run.finalisation_hash
            and (run.customer_id, run.site_id, run.data_source_id) ==
                (claim.customer_id, claim.site_id, claim.data_source_id)):
        return run.identity_epoch
    return None


def historical_link(links, epoch):
    if epoch is None:
        # Unversioned provenance is sufficient only for an undisturbed alias.
        return next(iter(links)) if len(links) == 1 and links[0].opened_epoch == 0 and links[0].ended_epoch is None else None
    matches = [link for link in links if link.opened_epoch <= epoch
               and (link.ended_epoch is None or epoch < link.ended_epoch)]
    return matches[0] if len(matches) == 1 else None


def historical_relationship_link(db, claim, links, *, proxmox=None):
    """Use the attribution interval for Proxmox and retain undisturbed legacy aliases elsewhere."""
    if not links:
        return None
    epoch = attribution_epoch(db, claim)
    link = historical_link(links, epoch)
    if link is not None and epoch is None:
        if proxmox is None:
            proxmox = is_proxmox_source(db, claim, claim.data_source_id)
        if proxmox:
            return None
    return link


def recorded_relationship_endpoint(claim, value, side):
    pinned = claim.subject_id if side == "source" else claim.object_id
    if pinned is not None:
        return pinned
    stored = value.get(f"resolved_{side}_asset_id")
    try:
        return UUID(str(stored)) if stored else None
    except ValueError:
        return None


class GuestBindings:
    """One scoped snapshot, constructed while the source writer lock is held for writes."""

    def __init__(self, db, scope, source_id):
        self.db = db
        self.links = defaultdict(list)
        self.guest_aliases_by_asset = defaultdict(set)
        self.boundaries = defaultdict(set)
        self.acknowledged = defaultdict(set)
        links = list(db.scalars(select(EntitySourceLink).where(
            EntitySourceLink.data_source_id == source_id, EntitySourceLink.customer_id == scope.customer_id,
            EntitySourceLink.site_id == scope.site_id).execution_options(populate_existing=True)))
        guests = {}
        for link in links:
            alias = (link.entity_type, link.external_id)
            self.links[alias].append(link)
            if alias[0] == "asset_interface" and link.opened_epoch:
                self.boundaries[alias].add(link.opened_epoch)
            if link.ended_epoch is not None:
                self.boundaries[alias].add(link.ended_epoch)
            if alias[0] == "asset" and GUEST_KEY.fullmatch(alias[1]):
                guests[link.id] = link
                self.guest_aliases_by_asset[link.entity_id].add(alias)
        for decision in db.scalars(select(ProxmoxGuestIdentityDecision).where(
                ProxmoxGuestIdentityDecision.data_source_id == source_id,
                ProxmoxGuestIdentityDecision.old_binding_id.in_(guests))):
            link = guests[decision.old_binding_id]
            self.boundaries[("asset", link.external_id)].add(decision.identity_epoch)
            if decision.outcome == "reactivate":
                self.acknowledged[link.id].add(decision.retirement_revision)

    @classmethod
    def for_scope(cls, db, scope, source_id):
        return cls(db, scope, source_id) if source_id and is_proxmox_source(db, scope, source_id) else None

    def aliases(self, *, subject_type, subject_external_id, object_type=None, object_external_id=None,
                owner_external_id=None, epoch=None):
        subject = (subject_type, subject_external_id)
        aliases = {("asset", key) for kind, key in (subject, (object_type, object_external_id))
                   if kind == "asset" and GUEST_KEY.fullmatch(key or "")}
        if subject_type == "asset_interface" and subject_external_id:
            slot = interface_guest(subject_external_id)
            aliases.update(("asset", key) for key in (slot, owner_external_id) if GUEST_KEY.fullmatch(key or ""))
            links = self.links.get(subject, ())
            link = historical_link(links, epoch) if epoch is not None else self.current(subject)
            if link:
                aliases.update(self.guest_aliases_by_asset.get(link.interface_owner_id, ()))
            if aliases or subject in self.boundaries:
                aliases.add(subject)
        return aliases

    def interface_owner(self, claim):
        if claim.subject_type != "asset_interface":
            return None
        value = claim.value_json if isinstance(claim.value_json, dict) else {}
        owner = value.get("asset_external_id") if claim.predicate == "configuration" and claim.fact_metadata is None else None
        if isinstance(owner, str) and owner:
            return owner
        if claim.evidence_record_id is None:
            return None
        evidence = self.db.get(EvidenceRecord, claim.evidence_record_id)
        if (evidence is not None and evidence.entity_kind == "asset_interface"
                and evidence.external_id == claim.subject_external_id
                and isinstance(evidence.payload_json, dict)
                and (evidence.customer_id, evidence.site_id, evidence.data_source_id, evidence.discovery_run_id) ==
                    (claim.customer_id, claim.site_id, claim.data_source_id, claim.discovery_run_id)):
            owner = evidence.payload_json.get("asset_external_id")
            return owner if isinstance(owner, str) and owner else None
        return None

    def claim_aliases(self, claim, epoch):
        return self.aliases(subject_type=claim.subject_type, subject_external_id=claim.subject_external_id,
            object_type=claim.object_type, object_external_id=claim.object_external_id,
            owner_external_id=self.interface_owner(claim), epoch=epoch)

    def current(self, alias):
        return next((link for link in self.links.get(alias, ()) if link.ended_epoch is None), None)

    def latest(self, aliases):
        return max((epoch for alias in aliases for epoch in self.boundaries.get(alias, ())), default=0)

    def crossed(self, aliases, before, after):
        return any(before < boundary <= after for alias in aliases for boundary in self.boundaries.get(alias, ()))

    def stale(self, claim, *, item=None):
        if (item is not None and item.entity_type == "asset_interface"
                and (claim.subject_type, claim.subject_external_id) != (item.entity_type, item.candidate_external_id)):
            return True
        epoch = attribution_epoch(self.db, claim) if self.boundaries else claim.identity_epoch
        aliases = self.claim_aliases(claim, epoch if epoch is not None else 0)
        if item is not None:
            value = item.observed_value_json if isinstance(item.observed_value_json, dict) else {}
            for key in (item.candidate_external_id if item.entity_type == "asset" else None,
                        value.get("source_external_id") if item.entity_type == "asset_relationship" else None,
                        value.get("target_external_id") if item.entity_type == "asset_relationship" else None):
                if isinstance(key, str) and GUEST_KEY.fullmatch(key):
                    aliases.add(("asset", key))
        if self.latest(aliases) > (epoch or 0):
            return True
        interface_alias = ("asset_interface", claim.subject_external_id)
        if claim.subject_type == "asset_interface" and (link := self.current(interface_alias)):
            aliases.add(interface_alias)
            # For an opaque key the observed owner comes from evidence. A link
            # opened later under another owner cannot supply that earlier proof.
            owner_key = self.interface_owner(claim) or interface_guest(claim.subject_external_id)
            if owner_key:
                owner = historical_link(self.links.get(("asset", owner_key), ()), epoch)
                if owner is None or owner.entity_id != link.interface_owner_id:
                    return True
            elif epoch is None or claim.subject_id != link.interface_id:
                return True
        endpoints = [(claim.subject_type, claim.subject_external_id, claim.subject_id),
                     (claim.object_type, claim.object_external_id, claim.object_id)]
        if item is not None and item.entity_type in {"asset", "asset_interface"}:
            endpoints.append((item.entity_type, claim.subject_external_id or item.candidate_external_id, item.entity_id))
        for kind, external, identifier in endpoints:
            if identifier is None or (kind, external) not in aliases:
                continue
            link = self.current((kind, external))
            if link and identifier != (link.entity_id if kind == "asset" else link.interface_id):
                return True
        return False

    def needs_review(self, asset, link):
        return (asset.status == "retired" or asset.identity_retirement_revision > 0
                and asset.identity_retirement_revision not in self.acknowledged.get(link.id, ()))
