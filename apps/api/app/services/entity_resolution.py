"""Conservative source-identity resolution for discovered Atlas assets."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, AssetInterface, DataSource, EntitySourceLink, Network


@dataclass(slots=True)
class AssetResolution:
    status: str
    asset: Asset | None = None
    candidates: list[Asset] = field(default_factory=list)


def normalized_name(value: str | None) -> str:
    return (value or "").strip().casefold()


def matching_asset_names(candidates, *, name, asset_type, hostname):
    expected_name = normalized_name(name)
    expected_hostname = normalized_name(hostname)
    return [
        candidate for candidate in candidates
        if normalized_name(candidate.name) == expected_name
        and (not asset_type or candidate.asset_type == asset_type)
        and (not expected_hostname or not candidate.hostname or normalized_name(candidate.hostname) == expected_hostname)
    ]


def asset_match_requires_review(matches, *, allow_existing_match):
    return bool(matches) and (len(matches) != 1 or not allow_existing_match)


class AssetIdentityCandidates:
    """A transaction-local inventory snapshot for repeated read-only resolution."""

    def __init__(self, db, customer_id, site_id):
        self.by_external = defaultdict(list)
        self.by_name = defaultdict(list)
        for asset in db.scalars(_site_assets(customer_id, site_id).execution_options(populate_existing=True)):
            self.by_external[asset.external_id].append(asset)
            self.by_name[normalized_name(asset.name)].append(asset)


def _site_assets(customer_id, site_id):
    return select(Asset).where(Asset.customer_id == customer_id, Asset.site_id == site_id)


def external_name_hint(external_id: str) -> str:
    value = external_id.strip()
    for separator in (":", "/"):
        if separator in value:
            value = value.rsplit(separator, 1)[-1]
    return value.strip()


def ensure_asset_link(
    db: Session,
    *,
    data_source_id: uuid.UUID,
    asset: Asset,
    external_id: str,
    external_type: str | None = None,
    observed_at: datetime | None = None,
) -> EntitySourceLink:
    observed_at = observed_at or datetime.now(timezone.utc)
    source = db.get(DataSource, data_source_id, with_for_update={"key_share": True})
    if source is None:
        raise HTTPException(status_code=409, detail="The data source no longer exists")
    # Source then canonical Asset: serialize linking with hard deletion.
    asset = db.get(Asset, asset.id, with_for_update=True, populate_existing=True)
    if asset is None:
        raise HTTPException(409, "The target asset no longer exists; refresh before linking")
    if source.customer_id != asset.customer_id or source.site_id not in {
        None,
        asset.site_id,
    }:
        raise HTTPException(
            status_code=409,
            detail="The data source and asset do not share a customer/site context",
        )
    link = db.scalar(
        select(EntitySourceLink).where(
            EntitySourceLink.data_source_id == data_source_id,
            EntitySourceLink.entity_type == "asset",
            EntitySourceLink.external_id == external_id,
            EntitySourceLink.ended_epoch.is_(None),
        )
    )
    if link is not None:
        if link.entity_id != asset.id:
            raise HTTPException(
                status_code=409,
                detail="This external identity is already linked to another asset",
            )
        link.last_observed_at = observed_at
        if external_type and not link.external_type:
            link.external_type = external_type
        return link
    link = EntitySourceLink(
        customer_id=asset.customer_id,
        site_id=asset.site_id,
        data_source_id=data_source_id,
        entity_type="asset",
        entity_id=asset.id,
        external_id=external_id,
        external_type=external_type,
        first_observed_at=observed_at,
        last_observed_at=observed_at,
    )
    db.add(link)
    db.flush()
    return link


def scoped_source_links(*, data_source_id, customer_id, site_id):
    return select(EntitySourceLink).where(EntitySourceLink.data_source_id == data_source_id,
        EntitySourceLink.customer_id == customer_id, EntitySourceLink.site_id == site_id,
        EntitySourceLink.ended_epoch.is_(None))


def technical_link(db, *, data_source_id, customer_id, site_id, entity_type, external_id):
    return db.scalar(scoped_source_links(data_source_id=data_source_id, customer_id=customer_id, site_id=site_id)
        .where(EntitySourceLink.entity_type == entity_type, EntitySourceLink.external_id == external_id))


def ensure_technical_link(db, *, source, target, entity_type, external_id, observed_at):
    """Explicit reconciliation acceptance only; no name-based cross-source merge."""
    # Serialize absent-link creation as well as existing-link checks. The unique
    # source/type/external constraint remains the final integrity boundary.
    db.get(DataSource, source.id, with_for_update={"key_share": True})
    if entity_type == "network":
        customer_id, site_id = target.customer_id, target.site_id
        owner_id, network_id, interface_id, interface_owner_id = None, target.id, None, None
    elif entity_type == "asset_interface":
        owner = db.get(Asset, target.asset_id)
        if owner is None:
            raise HTTPException(409, "Interface owner is unavailable")
        customer_id, site_id = owner.customer_id, owner.site_id
        owner_id, network_id, interface_id, interface_owner_id = None, None, target.id, owner.id
    else:
        raise HTTPException(409, "Unsupported technical source identity")
    if source.customer_id != customer_id or source.site_id not in {None, site_id} or site_id is None:
        raise HTTPException(409, "Source and target must share the customer and site")
    link = db.scalar(select(EntitySourceLink).where(EntitySourceLink.data_source_id == source.id,
        EntitySourceLink.entity_type == entity_type, EntitySourceLink.external_id == external_id,
        EntitySourceLink.ended_epoch.is_(None)))
    if link is not None:
        if ((link.customer_id, link.site_id) != (customer_id, site_id) or
                (link.entity_id, link.network_id, link.interface_id, link.interface_owner_id) != (owner_id, network_id, interface_id, interface_owner_id)):
            raise HTTPException(409, "The technical source identity already has a target")
        link.last_observed_at = observed_at
        return link
    opened_epoch = 0
    if entity_type == "asset_interface" and source.identity_epoch:
        from app.services.proxmox_guest_bindings import GuestBindings
        bindings = GuestBindings.for_scope(db, owner, source.id)
        if bindings:
            aliases = bindings.guest_aliases_by_asset.get(owner.id, set()) | {(entity_type, external_id)}
            opened_epoch = bindings.latest(aliases)
    link = EntitySourceLink(data_source_id=source.id, customer_id=customer_id, site_id=site_id,
        entity_type=entity_type, external_id=external_id, entity_id=owner_id, network_id=network_id,
        interface_id=interface_id, interface_owner_id=interface_owner_id, opened_epoch=opened_epoch,
        first_observed_at=observed_at, last_observed_at=observed_at)
    db.add(link)
    db.flush()
    return link


def resolve_asset_identity(
    db: Session,
    *,
    data_source_id: uuid.UUID,
    customer_id: uuid.UUID,
    site_id: uuid.UUID | None,
    external_id: str,
    name: str | None = None,
    asset_type: str | None = None,
    hostname: str | None = None,
    run_map: dict[str, AssetResolution] | None = None,
    allow_external_name_hint: bool = False,
    observed_at: datetime | None = None,
    persist_link: bool = True,
    allow_existing_match: bool | None = None,
    inventory: AssetIdentityCandidates | None = None,
) -> AssetResolution:
    if site_id is None:
        return AssetResolution("unresolved")

    link = db.scalar(
        select(EntitySourceLink).where(
            EntitySourceLink.data_source_id == data_source_id,
            EntitySourceLink.entity_type == "asset",
            EntitySourceLink.external_id == external_id,
            EntitySourceLink.ended_epoch.is_(None),
        )
    )
    if link is not None:
        asset = db.get(Asset, link.entity_id, populate_existing=True)
        if asset is None or asset.customer_id != customer_id or asset.site_id != site_id:
            raise HTTPException(
                status_code=409,
                detail="The external identity link has an invalid customer/site target",
            )
        if persist_link:
            link.last_observed_at = observed_at or datetime.now(timezone.utc)
        return AssetResolution("resolved_link", asset)

    if allow_existing_match is None:
        source = db.get(DataSource, data_source_id)
        allow_existing_match = source is None or source.source_type != "connector"
    assets = _site_assets(customer_id, site_id).execution_options(populate_existing=True)
    direct = (inventory.by_external.get(external_id, []) if inventory is not None
              else list(db.scalars(assets.where(Asset.external_id == external_id))))
    if asset_match_requires_review(direct, allow_existing_match=allow_existing_match):
        return AssetResolution("possible_duplicate", candidates=direct)
    if direct:
        if persist_link:
            ensure_asset_link(
                db,
                data_source_id=data_source_id,
                asset=direct[0],
                external_id=external_id,
                external_type=asset_type,
                observed_at=observed_at,
            )
        return AssetResolution("resolved_existing", direct[0])
    if run_map is not None and external_id in run_map:
        current = run_map[external_id]
        if current.asset is not None:
            return AssetResolution("resolved_same_run", current.asset)
        return current

    match_name = name
    if not match_name and allow_external_name_hint:
        match_name = external_name_hint(external_id)
    if not match_name:
        return AssetResolution("unresolved")

    candidates = inventory.by_name.get(normalized_name(match_name), ()) if inventory is not None else db.scalars(assets)
    strong = matching_asset_names(candidates, name=match_name, asset_type=asset_type, hostname=hostname)
    if asset_match_requires_review(strong, allow_existing_match=allow_existing_match):
        return AssetResolution("possible_duplicate", candidates=strong)
    if strong:
        if persist_link:
            ensure_asset_link(
                db,
                data_source_id=data_source_id,
                asset=strong[0],
                external_id=external_id,
                external_type=asset_type,
                observed_at=observed_at,
            )
        return AssetResolution("resolved_existing", strong[0])
    return AssetResolution("unresolved")
