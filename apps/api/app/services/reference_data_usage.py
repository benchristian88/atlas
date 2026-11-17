"""Selected operational context for usage attached to global definitions."""

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.authorization import ActiveContext, CurrentPrincipal, get_active_context
from app.database import get_db


def _usage_context(
    principal: CurrentPrincipal,
    x_atlas_customer_id: Annotated[uuid.UUID | None, Header()] = None,
    x_atlas_site_id: Annotated[uuid.UUID | None, Header()] = None,
    db: Session = Depends(get_db),
) -> ActiveContext | None:
    try:
        return get_active_context(principal, x_atlas_customer_id, x_atlas_site_id, db)
    except HTTPException as exc:
        if exc.status_code != 403:
            raise
        # An unavailable operational context has no visible usage. It must not
        # gate the separate permission to read or manage global definitions.
        return None


ReferenceUsageContext = Annotated[ActiveContext | None, Depends(_usage_context)]
