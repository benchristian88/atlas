"""Database-managed Service Type and Criticality reference data."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, require_global, require_permission
from app.database import get_db
from app.models import CriticalityLevel, Service, ServiceType
from app.routes.crud_helpers import commit, flush, not_found
from app.schemas import (
    CriticalityLevelCreate,
    CriticalityLevelResponse,
    CriticalityLevelUpdate,
    ServiceTypeCreate,
    ServiceTypeResponse,
    ServiceTypeUpdate,
)

service_types_router = APIRouter(prefix="/service-types", tags=["service types"])
criticality_router = APIRouter(prefix="/criticality-levels", tags=["criticality levels"])


def _service_type_response(db: Session, item: ServiceType) -> dict:
    result = ServiceTypeResponse.model_validate(item).model_dump()
    result["in_use_count"] = int(db.scalar(
        select(func.count()).select_from(Service).where(Service.service_type_id == item.id)
    ) or 0)
    return result


def _criticality_response(db: Session, item: CriticalityLevel) -> dict:
    result = CriticalityLevelResponse.model_validate(item).model_dump()
    result["in_use_count"] = int(db.scalar(
        select(func.count()).select_from(Service).where(Service.criticality_level_id == item.id)
    ) or 0)
    return result


@service_types_router.get("", response_model=list[ServiceTypeResponse])
def list_service_types(
    active_only: bool = Query(default=False),
    principal: Principal = Depends(require_permission("service_types.view")),
    db: Session = Depends(get_db),
):
    query = select(ServiceType).order_by(ServiceType.sort_order, ServiceType.name)
    if active_only:
        query = query.where(ServiceType.active.is_(True))
    return [_service_type_response(db, item) for item in db.scalars(query)]


@service_types_router.post("", response_model=ServiceTypeResponse, status_code=status.HTTP_201_CREATED)
def create_service_type(
    payload: ServiceTypeCreate,
    request: Request,
    principal: Principal = Depends(require_permission("service_types.manage")),
    db: Session = Depends(get_db),
):
    require_global(principal, "service_types.manage")
    item = ServiceType(**payload.model_dump(), system_defined=False, created_by_user_id=principal.user.id, updated_by_user_id=principal.user.id)
    db.add(item)
    flush(db, "Service type")
    add_audit_event(db, action="service_type.created", target_type="service_type", target_id=item.id, actor=principal.user, summary="Service type created", metadata={"key": item.key}, request=request)
    commit(db, "Service type")
    db.refresh(item)
    return _service_type_response(db, item)


@service_types_router.patch("/{type_id}", response_model=ServiceTypeResponse)
def update_service_type(
    type_id: uuid.UUID,
    payload: ServiceTypeUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("service_types.manage")),
    db: Session = Depends(get_db),
):
    require_global(principal, "service_types.manage")
    item = db.get(ServiceType, type_id)
    if item is None:
        raise not_found("Service type")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(item, key, value)
    item.updated_by_user_id = principal.user.id
    if "requires_asset_dependency" in changes:
        from app.services.knowledge_completeness import evaluate_services_for_service_type
        evaluate_services_for_service_type(db, item.id, actor_user_id=principal.user.id)
    add_audit_event(db, action="service_type.updated", target_type="service_type", target_id=item.id, actor=principal.user, summary="Service type updated", metadata={"changed_fields": sorted(changes)}, request=request)
    commit(db, "Service type")
    db.refresh(item)
    return _service_type_response(db, item)


def _set_service_type_state(type_id: uuid.UUID, active: bool, request: Request, principal: Principal, db: Session):
    require_global(principal, "service_types.manage")
    item = db.get(ServiceType, type_id)
    if item is None:
        raise not_found("Service type")
    item.active = active
    item.updated_by_user_id = principal.user.id
    add_audit_event(db, action=f"service_type.{'activated' if active else 'deactivated'}", target_type="service_type", target_id=item.id, actor=principal.user, summary=f"Service type {'activated' if active else 'deactivated'}", request=request)
    commit(db, "Service type")
    return _service_type_response(db, item)


@service_types_router.post("/{type_id}/activate", response_model=ServiceTypeResponse)
def activate_service_type(type_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("service_types.manage")), db: Session = Depends(get_db)):
    return _set_service_type_state(type_id, True, request, principal, db)


@service_types_router.post("/{type_id}/deactivate", response_model=ServiceTypeResponse)
def deactivate_service_type(type_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("service_types.manage")), db: Session = Depends(get_db)):
    return _set_service_type_state(type_id, False, request, principal, db)


@criticality_router.get("", response_model=list[CriticalityLevelResponse])
def list_criticality_levels(active_only: bool = Query(default=False), principal: Principal = Depends(require_permission("criticality_levels.view")), db: Session = Depends(get_db)):
    query = select(CriticalityLevel).order_by(CriticalityLevel.rank.desc(), CriticalityLevel.sort_order, CriticalityLevel.name)
    if active_only:
        query = query.where(CriticalityLevel.active.is_(True))
    return [_criticality_response(db, item) for item in db.scalars(query)]


@criticality_router.post("", response_model=CriticalityLevelResponse, status_code=status.HTTP_201_CREATED)
def create_criticality_level(payload: CriticalityLevelCreate, request: Request, principal: Principal = Depends(require_permission("criticality_levels.manage")), db: Session = Depends(get_db)):
    require_global(principal, "criticality_levels.manage")
    item = CriticalityLevel(**payload.model_dump(), system_defined=False)
    db.add(item)
    flush(db, "Criticality level")
    add_audit_event(db, action="criticality_level.created", target_type="criticality_level", target_id=item.id, actor=principal.user, summary="Criticality level created", metadata={"key": item.key}, request=request)
    commit(db, "Criticality level")
    db.refresh(item)
    return _criticality_response(db, item)


@criticality_router.patch("/{level_id}", response_model=CriticalityLevelResponse)
def update_criticality_level(level_id: uuid.UUID, payload: CriticalityLevelUpdate, request: Request, principal: Principal = Depends(require_permission("criticality_levels.manage")), db: Session = Depends(get_db)):
    require_global(principal, "criticality_levels.manage")
    item = db.get(CriticalityLevel, level_id)
    if item is None:
        raise not_found("Criticality level")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(item, key, value)
    if "rank" in changes:
        from app.services.knowledge_completeness import evaluate_service
        for service in db.scalars(select(Service).where(Service.criticality_level_id == item.id)):
            evaluate_service(db, service, trigger_context="criticality_rank_changed", actor_user_id=principal.user.id)
    add_audit_event(db, action="criticality_level.updated", target_type="criticality_level", target_id=item.id, actor=principal.user, summary="Criticality level updated", metadata={"changed_fields": sorted(changes)}, request=request)
    commit(db, "Criticality level")
    db.refresh(item)
    return _criticality_response(db, item)


def _set_criticality_state(level_id: uuid.UUID, active: bool, request: Request, principal: Principal, db: Session):
    require_global(principal, "criticality_levels.manage")
    item = db.get(CriticalityLevel, level_id)
    if item is None:
        raise not_found("Criticality level")
    item.active = active
    add_audit_event(db, action=f"criticality_level.{'activated' if active else 'deactivated'}", target_type="criticality_level", target_id=item.id, actor=principal.user, summary=f"Criticality level {'activated' if active else 'deactivated'}", request=request)
    commit(db, "Criticality level")
    return _criticality_response(db, item)


@criticality_router.post("/{level_id}/activate", response_model=CriticalityLevelResponse)
def activate_criticality_level(level_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("criticality_levels.manage")), db: Session = Depends(get_db)):
    return _set_criticality_state(level_id, True, request, principal, db)


@criticality_router.post("/{level_id}/deactivate", response_model=CriticalityLevelResponse)
def deactivate_criticality_level(level_id: uuid.UUID, request: Request, principal: Principal = Depends(require_permission("criticality_levels.manage")), db: Session = Depends(get_db)):
    return _set_criticality_state(level_id, False, request, principal, db)
