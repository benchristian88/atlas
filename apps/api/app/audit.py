"""Safe, durable audit-event creation helpers."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditEvent, User

_SENSITIVE_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "cookie",
    "authorization",
    "hash",
    "credential",
)


def _safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[redacted]"
            if any(fragment in str(key).lower() for fragment in _SENSITIVE_FRAGMENTS)
            else _safe_value(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_safe_value(item) for item in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def add_audit_event(
    db: Session,
    *,
    action: str,
    target_type: str,
    actor: User | None = None,
    actor_email: str | None = None,
    target_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    success: bool = True,
    summary: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    request: Request | None = None,
) -> AuditEvent:
    """Add an event to the caller's transaction without committing it."""

    event = AuditEvent(
        workspace_id=workspace_id,
        user_id=actor.id if actor is not None else None,
        actor_email=(actor.email if actor is not None else actor_email),
        actor_display_name=actor.display_name if actor is not None else None,
        event_type=action,
        target_type=target_type,
        target_id=target_id,
        customer_id=customer_id,
        site_id=site_id,
        success=success,
        summary=summary,
        source_ip=(request.client.host if request is not None and request.client else None),
        request_id=(
            getattr(request.state, "request_id", None) if request is not None else None
        ),
        metadata_=_safe_value(dict(metadata or {})),
    )
    db.add(event)
    return event
