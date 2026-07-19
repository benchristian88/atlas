"""Meaningful knowledge change timeline and asset fact history."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.authorization import Principal, RequestContext, require_permission, require_scope, scope_condition
from app.database import get_db
from app.models import (
    Asset,
    DataSource,
    DiscoveryRun,
    KnowledgeAssertion,
    KnowledgeChange,
    ReconciliationItem,
    User,
)
from app.routes.crud_helpers import not_found
from app.schemas import (
    AssetFactHistoryResponse,
    KnowledgeChangeListResponse,
    KnowledgeChangeResponse,
    KnowledgeChangeSummaryResponse,
)
from app.utils.json_values import to_json_value

router = APIRouter(tags=["changes"])


def _change_response(db: Session, change: KnowledgeChange) -> dict:
    result = KnowledgeChangeResponse.model_validate(change).model_dump()
    source = db.get(DataSource, change.data_source_id) if change.data_source_id else None
    run = db.get(DiscoveryRun, change.discovery_run_id) if change.discovery_run_id else None
    item = db.get(ReconciliationItem, change.reconciliation_item_id) if change.reconciliation_item_id else None
    actor = db.get(User, change.actor_user_id) if change.actor_user_id else None
    result["source_name"] = source.name if source else None
    result.update(
        {
            "entity_name": change.entity_name_snapshot,
            "previous_value": to_json_value(change.previous_value_json),
            "new_value": to_json_value(change.new_value_json),
            "discovery_run_status": run.status if run else None,
            "reconciliation_status": item.status if item else None,
            "actor_display_name": (actor.display_name or actor.email) if actor else None,
            "attention_required": bool(item and item.status in {"open", "deferred"}),
            "links": {
                **({"asset": f"/assets/{change.entity_id}"} if change.entity_type == "asset" and change.entity_id else {}),
                **({"reconciliation": "/reconciliation"} if item else {}),
                **({"discovery_run": f"/discovery-runs/{run.id}"} if run else {}),
            },
        }
    )
    return to_json_value(result)


def _filtered_changes(
    *,
    context: RequestContext,
    principal: Principal,
    customer_id: uuid.UUID | None,
    site_id: uuid.UUID | None,
    change_type: str | None,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    source_id: uuid.UUID | None,
    run_id: uuid.UUID | None,
    occurred_from: datetime | None,
    occurred_to: datetime | None,
    search: str | None,
    attention_required: bool | None,
):
    query = select(KnowledgeChange).where(
        scope_condition(
            principal,
            "changes.view",
            KnowledgeChange.customer_id,
            KnowledgeChange.site_id,
        )
    )
    effective_customer = context.customer_id or customer_id
    effective_site = context.site_id or site_id
    if effective_customer:
        query = query.where(KnowledgeChange.customer_id == effective_customer)
    if effective_site:
        query = query.where(KnowledgeChange.site_id == effective_site)
    if change_type:
        query = query.where(KnowledgeChange.change_type == change_type)
    if entity_type:
        query = query.where(KnowledgeChange.entity_type == entity_type)
    if entity_id:
        query = query.where(KnowledgeChange.entity_id == entity_id)
    if source_id:
        query = query.where(KnowledgeChange.data_source_id == source_id)
    if run_id:
        query = query.where(KnowledgeChange.discovery_run_id == run_id)
    if occurred_from:
        query = query.where(KnowledgeChange.occurred_at >= occurred_from)
    if occurred_to:
        query = query.where(KnowledgeChange.occurred_at <= occurred_to)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                KnowledgeChange.entity_name_snapshot.ilike(pattern),
                KnowledgeChange.summary.ilike(pattern),
                KnowledgeChange.predicate.ilike(pattern),
            )
        )
    if attention_required is not None:
        attention_ids = select(ReconciliationItem.id).where(
            ReconciliationItem.status.in_(("open", "deferred"))
        )
        if attention_required:
            query = query.where(KnowledgeChange.reconciliation_item_id.in_(attention_ids))
        else:
            query = query.where(
                or_(
                    KnowledgeChange.reconciliation_item_id.is_(None),
                    KnowledgeChange.reconciliation_item_id.not_in(attention_ids),
                )
            )
    return query


@router.get("/changes", response_model=KnowledgeChangeListResponse)
def list_changes(
    context: RequestContext,
    principal: Principal = Depends(require_permission("changes.view")),
    customer_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    change_type: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    data_source_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    attention_required: bool | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = _filtered_changes(
        context=context,
        principal=principal,
        customer_id=customer_id,
        site_id=site_id,
        change_type=change_type,
        entity_type=entity_type,
        entity_id=entity_id,
        source_id=data_source_id,
        run_id=run_id,
        occurred_from=date_from,
        occurred_to=date_to,
        search=search,
        attention_required=attention_required,
    )
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = db.scalars(
        query.order_by(KnowledgeChange.occurred_at.desc(), KnowledgeChange.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return {
        "items": [_change_response(db, row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/changes/summary", response_model=KnowledgeChangeSummaryResponse)
def changes_summary(
    context: RequestContext,
    principal: Principal = Depends(require_permission("changes.view")),
    customer_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    query = _filtered_changes(
        context=context,
        principal=principal,
        customer_id=customer_id,
        site_id=site_id,
        change_type=None,
        entity_type=None,
        entity_id=None,
        source_id=None,
        run_id=None,
        occurred_from=None,
        occurred_to=None,
        search=None,
        attention_required=None,
    )
    rows = list(db.scalars(query))
    now = datetime.now(timezone.utc)
    by_type: dict[str, int] = {}
    attention_count = 0
    for change in rows:
        by_type[change.change_type] = by_type.get(change.change_type, 0) + 1
        item = db.get(ReconciliationItem, change.reconciliation_item_id) if change.reconciliation_item_id else None
        attention_count += int(bool(item and item.status in {"open", "deferred"}))
    return {
        "total": len(rows),
        "by_type": by_type,
        "last_24_hours": sum(change.occurred_at >= now - timedelta(days=1) for change in rows),
        "last_7_days": sum(change.occurred_at >= now - timedelta(days=7) for change in rows),
        "unresolved_attention_count": attention_count,
    }


@router.get("/assets/{asset_id}/fact-history", response_model=AssetFactHistoryResponse)
def asset_fact_history(
    asset_id: uuid.UUID,
    principal: Principal = Depends(require_permission("assets.view")),
    db: Session = Depends(get_db),
):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise not_found("Asset")
    require_scope(
        principal,
        "assets.view",
        asset.customer_id,
        asset.site_id,
        hide_existence=True,
    )
    rows = db.scalars(
        select(KnowledgeAssertion)
        .where(
            KnowledgeAssertion.subject_type == "asset",
            KnowledgeAssertion.subject_id == asset.id,
        )
        .order_by(
            KnowledgeAssertion.predicate,
            KnowledgeAssertion.last_observed_at.desc(),
        )
    )
    facts: dict[str, list[dict]] = {}
    for assertion in rows:
        source = db.get(DataSource, assertion.data_source_id) if assertion.data_source_id else None
        history_value = assertion.value_json
        if assertion.object_type == "asset" and assertion.object_id:
            subject = db.get(Asset, assertion.subject_id) if assertion.subject_id else asset
            target = db.get(Asset, assertion.object_id)
            history_value = {
                "source": subject.name if subject else assertion.subject_external_id or "Unavailable",
                "relationship": assertion.predicate.replace("_", " "),
                "target": target.name if target else assertion.object_external_id or "Unavailable",
            }
        facts.setdefault(assertion.predicate, []).append(
            to_json_value(
                {
                    "predicate": assertion.predicate,
                    "value": history_value,
                    "truth_classification": assertion.truth_classification,
                    "source_name": source.name if source else None,
                    "discovery_run_id": assertion.discovery_run_id,
                    "assertion_id": assertion.id,
                    "confirmation_status": assertion.confirmation_status,
                    "first_observed_at": assertion.first_observed_at,
                    "last_observed_at": assertion.last_observed_at,
                    "is_current": assertion.is_current,
                    "retracted_at": assertion.retracted_at,
                }
            )
        )
    return {"asset_id": asset.id, "facts": facts}
