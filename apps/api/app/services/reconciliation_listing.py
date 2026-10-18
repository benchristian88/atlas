"""Bounded reconciliation browsing; presentation context never changes decisions."""
from __future__ import annotations

import base64
import binascii
from datetime import datetime
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.orm import aliased

from app.authorization import scope_condition
from app.models import KnowledgeAssertion, ReconciliationItem


def filtered_items(context, principal, *, item_status="open", category=None,
                   source_id=None, run_id=None, entity_type=None):
    query = select(ReconciliationItem).where(scope_condition(
        principal, "reconciliation.view", ReconciliationItem.customer_id, ReconciliationItem.site_id))
    if context.customer_id is not None:
        query = query.where(ReconciliationItem.customer_id == context.customer_id)
    if context.site_id is not None:
        query = query.where(ReconciliationItem.site_id == context.site_id)
    if item_status == "resolved":
        query = query.where(ReconciliationItem.status.in_(["accepted", "rejected"]))
    elif item_status:
        query = query.where(ReconciliationItem.status == item_status)
    if category:
        query = query.where(ReconciliationItem.category == category)
    if entity_type:
        query = query.where(ReconciliationItem.entity_type == entity_type)
    if source_id or run_id:
        query = query.join(KnowledgeAssertion, KnowledgeAssertion.id == ReconciliationItem.assertion_id)
        if source_id:
            query = query.where(KnowledgeAssertion.data_source_id == source_id)
        if run_id:
            query = query.where(KnowledgeAssertion.discovery_run_id == run_id)
    return query


def _position(item):
    return [item.created_at.isoformat(), str(item.id)]


def _decode(cursor):
    try:
        value = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
        if not isinstance(value, dict) or set(value) != {"snapshot", "before"}:
            raise ValueError
        positions = []
        for key in ("snapshot", "before"):
            if (not isinstance(value[key], list) or len(value[key]) != 2
                    or any(not isinstance(part, str) for part in value[key])):
                raise ValueError
            stamp, identifier = value[key]
            stamp = datetime.fromisoformat(stamp)
            if stamp.tzinfo is None:
                raise ValueError
            positions.append((stamp, uuid.UUID(identifier)))
        if positions[1] > positions[0]:
            raise ValueError
        return positions
    except (ValueError, TypeError, KeyError, binascii.Error):
        raise HTTPException(422, "Invalid reconciliation cursor") from None


def page_rows(db, query, *, limit, cursor):
    order = (ReconciliationItem.created_at.desc(), ReconciliationItem.id.desc())
    position = tuple_(ReconciliationItem.created_at, ReconciliationItem.id)
    before = None
    if cursor:
        snapshot, before = _decode(cursor)
    else:
        newest = db.scalar(query.order_by(*order).limit(1))
        if newest is None:
            return [], 0, None
        snapshot = (newest.created_at, newest.id)
    # Bound out newer arrivals until refresh; decisions/deletions do not shift
    # the next page. The ID is a stable tie-breaker for transaction timestamps.
    bounded = query.where(position <= snapshot)
    total = int(db.scalar(select(func.count()).select_from(bounded.subquery())) or 0)
    if before:
        bounded = bounded.where(position < before)
    rows = list(db.scalars(bounded.order_by(*order).limit(limit + 1)))
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = base64.urlsafe_b64encode(json.dumps({
            "snapshot": [snapshot[0].isoformat(), str(snapshot[1])],
            "before": _position(rows[-1]),
        }, separators=(",", ":")).encode()).decode()
    return rows, total, next_cursor


def initial_fact_context(db, context, principal, items):
    """Return at most one scoped parent per page fact, including across pages.

    Coalesced assertions can acquire a later run ID. Equal first-observation
    times plus no other claim for the predicate prevent later facts being
    presented as initial, even when current_value_json is null.
    """
    claims = {claim.id: claim for claim in db.scalars(select(KnowledgeAssertion).where(
        KnowledgeAssertion.id.in_([item.assertion_id for item in items])))}
    eligible = [item for item in items if item.category == "changed" and item.entity_type == "asset"
                and item.current_value_json is None and (claim := claims.get(item.assertion_id))
                and claim.fact_metadata is not None and claim.confirmation_status != "conflicted"
                and claim.data_source_id and claim.discovery_run_id and claim.subject_external_id]
    if not eligible:
        return {}, []
    keys = {(claims[item.assertion_id].data_source_id, claims[item.assertion_id].discovery_run_id,
             claims[item.assertion_id].subject_external_id) for item in eligible}
    parent_query = filtered_items(context, principal, item_status=None, category="newly_discovered", entity_type="asset")
    parent_keys = (ReconciliationItem.customer_id, ReconciliationItem.site_id,
                   KnowledgeAssertion.data_source_id, KnowledgeAssertion.discovery_run_id,
                   KnowledgeAssertion.subject_external_id)
    parents = list(db.execute(parent_query.add_columns(KnowledgeAssertion).join(
        KnowledgeAssertion, KnowledgeAssertion.id == ReconciliationItem.assertion_id).where(
        tuple_(KnowledgeAssertion.data_source_id, KnowledgeAssertion.discovery_run_id,
               KnowledgeAssertion.subject_external_id).in_(keys)).distinct(*parent_keys).order_by(
                   *parent_keys, ReconciliationItem.created_at, ReconciliationItem.id).limit(len(eligible))))
    prior = aliased(KnowledgeAssertion)
    candidates = {claim.id: claim for claim in db.scalars(select(KnowledgeAssertion).where(
        KnowledgeAssertion.id.in_([item.assertion_id for item in eligible]),
        ~select(prior.id).where(
            prior.id != KnowledgeAssertion.id,
            prior.customer_id == KnowledgeAssertion.customer_id,
            prior.site_id.is_not_distinct_from(KnowledgeAssertion.site_id),
            prior.subject_type == KnowledgeAssertion.subject_type,
            prior.predicate == KnowledgeAssertion.predicate,
            or_(prior.subject_external_id == KnowledgeAssertion.subject_external_id,
                (KnowledgeAssertion.subject_id.is_not(None) & (prior.subject_id == KnowledgeAssertion.subject_id))),
        ).exists(),
    ))}
    grouping, related = {}, {}
    for item in eligible:
        claim = candidates.get(item.assertion_id)
        if claim is None:
            continue
        for parent, anchor in parents:
            if (parent.customer_id == item.customer_id and parent.site_id == item.site_id
                    and anchor.data_source_id == claim.data_source_id
                    and anchor.discovery_run_id == claim.discovery_run_id
                    and anchor.subject_type == claim.subject_type
                    and anchor.subject_external_id == claim.subject_external_id
                    and anchor.first_observed_at == claim.first_observed_at
                    and parent.candidate_external_id == item.candidate_external_id):
                grouping[item.id] = parent.id
                related[parent.id] = parent
                break
    return grouping, list(related.values())
