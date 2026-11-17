"""Bounded Interface detail projection; observations never resolve membership."""
from sqlalchemy import and_, func, or_, select

from app.authorization import scope_condition
from app.models import DataSource, KnowledgeAssertion, Network
from app.schemas import AssetInterfaceResponse
from app.services.knowledge_summary import knowledge_sources


PREDICATES = ("proxmox.vlan_tag", "proxmox.bridge_name")


def interface_details(db, asset, interfaces, principal):
    """At most one accepted and one unaccepted observation per fact/Interface.

    Match the Knowledge summary's acceptance and active-observation selection.
    Rank in SQL so retained history/source count cannot grow the response. A
    source-current flag is eligibility, never evidence of present-day freshness.
    """
    if not interfaces:
        return []
    claim = KnowledgeAssertion
    accepted = and_(claim.is_accepted.is_(True), claim.confirmation_status != "rejected")
    observed = and_(claim.is_accepted.is_(False), claim.is_source_current.is_(True),
                    claim.confirmation_status.not_in(["rejected", "superseded"]))
    ranked = select(claim.subject_id, claim.predicate, claim.value_json, claim.data_source_id,
        claim.last_observed_at, claim.is_accepted, claim.accepted_at,
        func.row_number().over(partition_by=(claim.subject_id, claim.predicate, claim.is_accepted),
            order_by=(claim.last_observed_at.desc(), claim.id.desc())).label("position")).outerjoin(
                DataSource, DataSource.id == claim.data_source_id).where(
                claim.subject_type == "asset_interface", claim.subject_id.in_([row.id for row in interfaces]),
                claim.customer_id == asset.customer_id, claim.site_id.is_not_distinct_from(asset.site_id),
                claim.predicate.in_(PREDICATES), claim.truth_classification == "observed",
                or_(claim.data_source_id.is_(None), and_(DataSource.customer_id == asset.customer_id,
                    or_(DataSource.site_id.is_(None), DataSource.site_id == asset.site_id))),
                claim.retracted_at.is_(None), or_(accepted, observed)).subquery()
    facts = list(db.execute(select(ranked).where(ranked.c.position == 1).order_by(
        ranked.c.subject_id, ranked.c.predicate, ranked.c.is_accepted.desc())))
    sources = knowledge_sources(db, asset, {row.data_source_id for row in facts if row.data_source_id})
    networks = {row.id: row for row in db.scalars(select(Network).where(
        Network.id.in_({row.network_id for row in interfaces if row.network_id}),
        Network.customer_id == asset.customer_id,
        or_(Network.site_id.is_(None), Network.site_id == asset.site_id),
        scope_condition(principal, "networks.view", Network.customer_id, Network.site_id)))}
    by_interface = {}
    for row in facts:
        # Only the two declared scalar types are suitable for this narrow view.
        # Never echo unexpected legacy structured values or raw evidence.
        if row.predicate == "proxmox.vlan_tag":
            valid = type(row.value_json) is int and 0 <= row.value_json <= 4094
        else:
            valid = isinstance(row.value_json, str) and 0 < len(row.value_json) <= 255
        if not valid:
            continue
        source = sources.get(row.data_source_id)
        by_interface.setdefault(row.subject_id, []).append({
            "predicate": row.predicate, "value": row.value_json, "is_accepted": row.is_accepted,
            "source_name": source.name if source else None, "last_observed_at": row.last_observed_at,
            "accepted_at": row.accepted_at if row.is_accepted else None})
    result = []
    for interface in interfaces:
        network = networks.get(interface.network_id)
        result.append({**AssetInterfaceResponse.model_validate(interface).model_dump(),
            "network_id": network.id if network else None,
            "assigned_network": {"id": network.id, "name": network.name, "vlan_id": network.vlan_id} if network else None,
            "observed_facts": by_interface.get(interface.id, [])})
    return result
