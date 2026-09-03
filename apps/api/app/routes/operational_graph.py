"""Generic focused operational graph API."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.authorization import Principal, RequestContext, require_any_permission
from app.database import get_db
from app.schemas import OperationalGraphResponse
from app.services.operational_graph import (
    EDGE_FAMILIES,
    GraphFocusNotFound,
    GraphProjectionRequest,
    OperationalGraphBuilder,
)

router = APIRouter(prefix="/operational-graph", tags=["operational graph"])


@router.get("", response_model=OperationalGraphResponse)
def get_operational_graph(
    context: RequestContext,
    focus_type: Literal["asset", "service", "business_function"],
    focus_id: uuid.UUID,
    max_depth: int = Query(default=1, ge=0, le=2),
    direction: Literal["both", "outgoing", "incoming"] = "both",
    node_limit: int = Query(default=250, ge=1, le=500),
    edge_family: list[str] | None = Query(default=None),
    principal: Principal = Depends(
        require_any_permission(
            "assets.view", "services.view", "business_functions.view"
        )
    ),
    db: Session = Depends(get_db),
):
    requested_families = set()
    for value in edge_family or []:
        requested_families.update(
            part.strip() for part in value.split(",") if part.strip()
        )
    unsupported = requested_families.difference(EDGE_FAMILIES)
    if unsupported:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported edge family: {sorted(unsupported)[0]}",
        )
    try:
        return OperationalGraphBuilder(db, principal).build(
            GraphProjectionRequest(
                focus_type=focus_type,
                focus_id=focus_id,
                max_depth=max_depth,
                direction=direction,
                node_limit=node_limit,
                edge_families=(
                    frozenset(requested_families)
                    if edge_family is not None
                    else EDGE_FAMILIES
                ),
                context=context,
            )
        )
    except GraphFocusNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        ) from exc
