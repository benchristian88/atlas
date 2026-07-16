from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.authorization import Principal, require_global, require_permission
from app.database import get_db
from app.models import AccessAssignment, Permission, Role, RolePermission
from app.schemas import (
    PermissionResponse,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
)
from app.routes.crud_helpers import commit, flush

router = APIRouter(prefix="/roles", tags=["roles and permissions"])
permissions_router = APIRouter(prefix="/permissions", tags=["roles and permissions"])


def _role_response(role: Role, db: Session) -> RoleResponse:
    permissions = list(
        db.scalars(
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id)
            .order_by(Permission.category, Permission.key)
        )
    )
    return RoleResponse.model_validate(
        {
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "system_defined": role.system_defined,
            "active": role.active,
            "sort_order": role.sort_order,
            "permissions": permissions,
        }
    )


def _permissions_for_keys(db: Session, keys: list[str]) -> list[Permission]:
    unique_keys = set(keys)
    permissions = list(db.scalars(select(Permission).where(Permission.key.in_(unique_keys))))
    found = {item.key for item in permissions}
    missing = sorted(unique_keys - found)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown permission keys: {', '.join(missing)}",
        )
    return permissions


def _set_permissions(db: Session, role: Role, permissions: list[Permission]) -> None:
    db.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
    for permission in permissions:
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))


def _ensure_permissions_assignable(
    principal: Principal, permissions: list[Permission]
) -> None:
    missing = sorted(
        permission.key
        for permission in permissions
        if not principal.can(permission.key, None, None)
    )
    if missing:
        raise HTTPException(
            status_code=403,
            detail="A role cannot contain permissions you do not hold globally",
        )


@permissions_router.get("", response_model=list[PermissionResponse])
def list_permissions(
    principal: Principal = Depends(require_permission("roles.view")),
    db: Session = Depends(get_db),
):
    require_global(principal, "roles.view")
    return list(db.scalars(select(Permission).order_by(Permission.category, Permission.key)))


@router.get("", response_model=list[RoleResponse])
def list_roles(
    principal: Principal = Depends(require_permission("roles.view")),
    db: Session = Depends(get_db),
):
    require_global(principal, "roles.view")
    roles = list(db.scalars(select(Role).order_by(Role.sort_order, Role.name)))
    return [_role_response(role, db) for role in roles]


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    request: Request,
    principal: Principal = Depends(require_permission("roles.manage")),
    db: Session = Depends(get_db),
):
    require_global(principal, "roles.manage")
    permissions = _permissions_for_keys(db, payload.permission_keys)
    _ensure_permissions_assignable(principal, permissions)
    role = Role(
        name=payload.name.strip(),
        description=payload.description,
        system_defined=False,
        active=payload.active,
        sort_order=payload.sort_order,
    )
    db.add(role)
    flush(db, "Role")
    _set_permissions(db, role, permissions)
    add_audit_event(
        db,
        action="role.created",
        target_type="role",
        target_id=role.id,
        actor=principal.user,
        summary="Custom role created",
        metadata={"name": role.name, "permissions": sorted(payload.permission_keys)},
        request=request,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A role with this name already exists") from exc
    db.refresh(role)
    return _role_response(role, db)


@router.get("/{role_id}", response_model=RoleResponse)
def get_role(
    role_id: uuid.UUID,
    principal: Principal = Depends(require_permission("roles.view")),
    db: Session = Depends(get_db),
):
    require_global(principal, "roles.view")
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    return _role_response(role, db)


@router.patch("/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("roles.manage")),
    db: Session = Depends(get_db),
):
    require_global(principal, "roles.manage")
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    current_permissions = list(
        db.scalars(
            select(Permission)
            .join(
                RolePermission,
                RolePermission.permission_id == Permission.id,
            )
            .where(RolePermission.role_id == role.id)
        )
    )
    _ensure_permissions_assignable(principal, current_permissions)
    changes = payload.model_dump(exclude_unset=True, exclude={"permission_keys"})
    if role.system_defined and ({"name", "active"} & changes.keys() or payload.permission_keys is not None):
        raise HTTPException(
            status_code=409,
            detail="Built-in role identity and permissions are protected",
        )
    permission_keys = payload.permission_keys
    permissions = _permissions_for_keys(db, permission_keys) if permission_keys is not None else None
    if permissions is not None:
        _ensure_permissions_assignable(principal, permissions)
    for key, value in changes.items():
        setattr(role, key, value)
    if permissions is not None:
        _set_permissions(db, role, permissions)
    add_audit_event(
        db,
        action="role.updated",
        target_type="role",
        target_id=role.id,
        actor=principal.user,
        summary="Role definition updated",
        metadata={"changed_fields": sorted(payload.model_fields_set)},
        request=request,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Role could not be updated") from exc
    db.refresh(role)
    return _role_response(role, db)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_permission("roles.manage")),
    db: Session = Depends(get_db),
) -> Response:
    require_global(principal, "roles.manage")
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    current_permissions = list(
        db.scalars(
            select(Permission)
            .join(
                RolePermission,
                RolePermission.permission_id == Permission.id,
            )
            .where(RolePermission.role_id == role.id)
        )
    )
    _ensure_permissions_assignable(principal, current_permissions)
    if role.system_defined:
        raise HTTPException(status_code=409, detail="Built-in roles cannot be deleted")
    if db.scalar(
        select(func.count()).select_from(AccessAssignment).where(AccessAssignment.role_id == role.id)
    ):
        raise HTTPException(status_code=409, detail="Role is assigned to one or more users")
    add_audit_event(
        db,
        action="role.deleted",
        target_type="role",
        target_id=role.id,
        actor=principal.user,
        summary="Unused custom role deleted",
        metadata={"name": role.name},
        request=request,
    )
    db.delete(role)
    commit(db, "Role")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
