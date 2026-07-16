from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.authorization import Principal, require_permission, scope_condition
from app.database import get_db
from app.models import AuditEvent
from app.schemas import AuditEventResponse

router = APIRouter(prefix="/audit-events", tags=["audit"])


@router.get("", response_model=list[AuditEventResponse])
def list_audit_events(
    principal: Principal = Depends(require_permission("audit.view")),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    actor: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    customer_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(AuditEvent).where(
        scope_condition(
            principal,
            "audit.view",
            AuditEvent.customer_id,
            AuditEvent.site_id,
        )
    )
    if date_from is not None:
        query = query.where(AuditEvent.created_at >= date_from)
    if date_to is not None:
        query = query.where(AuditEvent.created_at <= date_to)
    if actor:
        pattern = f"%{actor.strip()}%"
        query = query.where(
            or_(
                AuditEvent.actor_email.ilike(pattern),
                AuditEvent.actor_display_name.ilike(pattern),
            )
        )
    if action:
        query = query.where(AuditEvent.event_type == action)
    if entity_type:
        query = query.where(AuditEvent.target_type == entity_type)
    if customer_id:
        query = query.where(AuditEvent.customer_id == customer_id)
    if site_id:
        query = query.where(AuditEvent.site_id == site_id)
    return list(
        db.scalars(
            query.order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset)
        )
    )

