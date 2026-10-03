"""Managed presentation order using existing global reference-data permissions."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, require_global, require_permission
from app.database import get_db
from app.models import AssetType, TopologyPosition
from app.routes.crud_helpers import commit, flush
from app.schemas import TopologyPositionCreate, TopologyPositionMove, TopologyPositionResponse, TopologyPositionUpdate

router = APIRouter(prefix="/topology-positions", tags=["topology positions"])


def ordered_positions(db, active_only=False):
    counts = (select(AssetType.topology_position_id.label("position_id"), func.count().label("count"))
              .group_by(AssetType.topology_position_id).subquery())
    query = (select(TopologyPosition, func.coalesce(counts.c.count, 0))
             .outerjoin(counts, counts.c.position_id == TopologyPosition.id)
             .order_by(TopologyPosition.sort_order, TopologyPosition.id))
    if active_only:
        query = query.where(TopologyPosition.active.is_(True))
    return [TopologyPositionResponse.model_validate(item).model_copy(update={"asset_types_count": count})
            for item, count in db.execute(query)]


def response(db, item):
    result = TopologyPositionResponse.model_validate(item)
    result.asset_types_count = db.scalar(select(func.count()).select_from(AssetType).where(AssetType.topology_position_id == item.id)) or 0
    return result


def lock_order(db):
    # Also serialize appends into an empty table. Readers remain unblocked.
    # The deferred unique constraint permits an atomic swap of occupied ranks.
    db.execute(text("LOCK TABLE topology_positions IN SHARE ROW EXCLUSIVE MODE"))


def audit(db, principal, request, item, action, **metadata):
    add_audit_event(db, action=f"topology_position.{action}", target_type="topology_position", target_id=item.id,
                   actor=principal.user, summary=f"Topology position {action}",
                   metadata={"key": item.key, "name": item.name, **metadata}, request=request)


def get_position(db, position_id):
    item = db.get(TopologyPosition, position_id)
    if item is None:
        raise HTTPException(404, "Topology position not found")
    return item


@router.get("", response_model=list[TopologyPositionResponse])
def list_positions(principal: Principal = Depends(require_permission("asset_types.view")),
                   active_only: bool = Query(False), db: Session = Depends(get_db)):
    return ordered_positions(db, active_only)


@router.post("", response_model=TopologyPositionResponse, status_code=201)
def create_position(payload: TopologyPositionCreate, request: Request,
                    principal: Principal = Depends(require_permission("asset_types.manage")), db: Session = Depends(get_db)):
    require_global(principal, "asset_types.manage")
    if payload.key == "automatic":
        raise HTTPException(422, "Automatic is an unassigned Asset Type, not a topology position")
    lock_order(db)
    last = db.scalar(select(func.max(TopologyPosition.sort_order)))
    item = TopologyPosition(**payload.model_dump(), sort_order=0 if last is None else last + 1)
    db.add(item)
    flush(db, "Topology position")
    audit(db, principal, request, item, "created")
    commit(db, "Topology position")
    db.refresh(item)
    return response(db, item)


@router.patch("/{position_id}", response_model=TopologyPositionResponse)
def update_position(position_id: uuid.UUID, payload: TopologyPositionUpdate, request: Request,
                    principal: Principal = Depends(require_permission("asset_types.manage")), db: Session = Depends(get_db)):
    require_global(principal, "asset_types.manage")
    item = get_position(db, position_id)
    changes = payload.model_dump(exclude_unset=True)
    if any(value is None and key != "description" for key, value in changes.items()):
        raise HTTPException(422, "Position name and active state must not be null")
    for key, value in changes.items():
        setattr(item, key, value)
    audit(db, principal, request, item, "updated", changed_fields=sorted(changes))
    commit(db, "Topology position")
    db.refresh(item)
    return response(db, item)


@router.post("/{position_id}/move", response_model=list[TopologyPositionResponse])
def move_position(position_id: uuid.UUID, payload: TopologyPositionMove, request: Request,
                  principal: Principal = Depends(require_permission("asset_types.manage")), db: Session = Depends(get_db)):
    require_global(principal, "asset_types.manage")
    lock_order(db)
    positions = list(db.scalars(select(TopologyPosition).order_by(TopologyPosition.sort_order, TopologyPosition.id)))
    index = next((i for i, item in enumerate(positions) if item.id == position_id), None)
    if index is None:
        raise HTTPException(404, "Topology position not found")
    target = index + (-1 if payload.direction == "up" else 1)
    if 0 <= target < len(positions):
        item, neighbour = positions[index], positions[target]
        item.sort_order, neighbour.sort_order = neighbour.sort_order, item.sort_order
        audit(db, principal, request, item, "moved", direction=payload.direction, neighbour_id=str(neighbour.id))
    commit(db, "Topology position")
    return ordered_positions(db)


@router.delete("/{position_id}", status_code=204)
def delete_position(position_id: uuid.UUID, request: Request,
                    principal: Principal = Depends(require_permission("asset_types.manage")), db: Session = Depends(get_db)):
    require_global(principal, "asset_types.manage")
    lock_order(db)
    item = get_position(db, position_id)
    if db.scalar(select(func.count()).select_from(AssetType).where(AssetType.topology_position_id == item.id)):
        raise HTTPException(409, "Reassign this position's Asset Types before deleting it")
    audit(db, principal, request, item, "deleted")
    db.delete(item)
    commit(db, "Topology position")
    return Response(status_code=204)
