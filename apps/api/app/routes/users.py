from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.auth import hash_password
from app.authorization import (
    Principal,
    _load_principal,
    require_global,
    require_permission,
    require_scope,
)
from app.database import get_db
from app.models import (
    AccessAssignment,
    Customer,
    Permission,
    Role,
    RolePermission,
    Site,
    User,
)
from app.permissions import MASTER_ADMINISTRATOR
from app.presenters import user_response_data
from app.schemas import (
    AccessAssignmentInput,
    AdminPasswordResetRequest,
    UserAdminResponse,
    UserCreate,
    UserUpdate,
)
from app.routes.crud_helpers import flush

router = APIRouter(prefix="/users", tags=["users"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="User not found")


def _user_response(user: User, db: Session) -> UserAdminResponse:
    return UserAdminResponse.model_validate(
        user_response_data(_load_principal(user, db), administrative=True)
    )


def _validate_assignments(
    db: Session,
    actor: Principal,
    assignments: list[AccessAssignmentInput],
) -> list[tuple[AccessAssignmentInput, Role]]:
    if not assignments:
        raise HTTPException(status_code=422, detail="At least one role assignment is required")
    validated: list[tuple[AccessAssignmentInput, Role]] = []
    identities: set[tuple] = set()
    for assignment in assignments:
        identity = (
            assignment.role_id,
            assignment.scope_type,
            assignment.customer_id,
            assignment.site_id,
        )
        if identity in identities:
            raise HTTPException(status_code=422, detail="Duplicate role assignment")
        identities.add(identity)
        role = db.get(Role, assignment.role_id)
        if role is None or not role.active:
            raise HTTPException(status_code=422, detail="Role is not available")
        if assignment.scope_type == "global":
            require_global(actor, "users.assign_roles")
        else:
            customer = db.get(Customer, assignment.customer_id)
            if customer is None:
                raise HTTPException(status_code=422, detail="Assignment customer does not exist")
            if assignment.site_id is not None:
                site = db.get(Site, assignment.site_id)
                if site is None or site.customer_id != customer.id:
                    raise HTTPException(
                        status_code=422,
                        detail="Assignment site does not belong to the customer",
                    )
            require_scope(
                actor,
                "users.assign_roles",
                assignment.customer_id,
                assignment.site_id,
            )
        role_permissions = set(
            db.scalars(
                select(Permission.key)
                .join(
                    RolePermission,
                    RolePermission.permission_id == Permission.id,
                )
                .where(RolePermission.role_id == role.id)
            )
        )
        missing_permissions = sorted(
            permission
            for permission in role_permissions
            if not actor.can(
                permission,
                assignment.customer_id,
                assignment.site_id,
            )
        )
        if missing_permissions:
            raise HTTPException(
                status_code=403,
                detail=(
                    "A role cannot be assigned with permissions you do not hold "
                    "in the target scope"
                ),
            )
        validated.append((assignment, role))
    return validated


def _ensure_target_manageable(actor: Principal, target: Principal) -> None:
    """Prevent lower-privilege administrators from taking over stronger accounts."""

    for grant in target.grants:
        if any(
            not actor.can(permission, grant.customer_id, grant.site_id)
            for permission in grant.permissions
        ):
            raise HTTPException(
                status_code=403,
                detail="You cannot administer an account with permissions above your own",
            )


def _has_global_master(db: Session, user_id: uuid.UUID) -> bool:
    return bool(
        db.scalar(
            select(func.count())
            .select_from(AccessAssignment)
            .join(Role, Role.id == AccessAssignment.role_id)
            .where(
                AccessAssignment.user_id == user_id,
                AccessAssignment.scope_type == "global",
                Role.name == MASTER_ADMINISTRATOR,
                Role.active.is_(True),
            )
        )
    )


def _usable_master_count(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count(func.distinct(User.id)))
            .select_from(User)
            .join(AccessAssignment, AccessAssignment.user_id == User.id)
            .join(Role, Role.id == AccessAssignment.role_id)
            .where(
                User.is_active.is_(True),
                AccessAssignment.scope_type == "global",
                Role.name == MASTER_ADMINISTRATOR,
                Role.active.is_(True),
            )
        )
        or 0
    )


def _would_keep_master(
    db: Session, target: User, new_active: bool, assignments: list[AccessAssignmentInput]
) -> bool:
    if not _has_global_master(db, target.id) or _usable_master_count(db) > 1:
        return True
    if not new_active:
        return False
    master_role_id = db.scalar(select(Role.id).where(Role.name == MASTER_ADMINISTRATOR))
    return any(
        item.role_id == master_role_id and item.scope_type == "global"
        for item in assignments
    )


def _lock_master_invariant(db: Session) -> None:
    # The protected role row is a stable, shared serialization point. This
    # prevents two concurrent demotions from each observing two active masters.
    db.scalar(
        select(Role.id)
        .where(Role.name == MASTER_ADMINISTRATOR)
        .with_for_update()
    )


def _replace_assignments(
    db: Session, user_id: uuid.UUID, assignments: list[AccessAssignmentInput]
) -> None:
    db.execute(delete(AccessAssignment).where(AccessAssignment.user_id == user_id))
    for assignment in assignments:
        db.add(
            AccessAssignment(
                user_id=user_id,
                role_id=assignment.role_id,
                scope_type=assignment.scope_type,
                customer_id=assignment.customer_id,
                site_id=assignment.site_id,
            )
        )


@router.get("", response_model=list[UserAdminResponse])
def list_users(
    principal: Principal = Depends(require_permission("users.view")),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    require_global(principal, "users.view")
    users = list(db.scalars(select(User).order_by(User.email).limit(limit).offset(offset)))
    return [_user_response(user, db) for user in users]


@router.post("", response_model=UserAdminResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    principal: Principal = Depends(require_permission("users.create")),
    db: Session = Depends(get_db),
):
    if not principal.can_anywhere("users.assign_roles"):
        raise HTTPException(status_code=403, detail="Role assignment permission is required")
    validated = _validate_assignments(db, principal, payload.assignments)
    email = str(payload.email).strip().lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="A user with this email already exists")
    user = User(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.temporary_password),
        is_active=True,
        force_password_change=payload.force_password_change,
        failed_login_count=0,
        session_version=1,
        auth_provider="local",
        mfa_enabled=False,
    )
    db.add(user)
    flush(db, "User")
    _replace_assignments(db, user.id, [item for item, _ in validated])
    add_audit_event(
        db,
        action="user.created",
        target_type="user",
        target_id=user.id,
        actor=principal.user,
        summary="User account created",
        metadata={
            "email": email,
            "assignments": [item.model_dump(mode="json") for item, _ in validated],
        },
        request=request,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="User could not be created") from exc
    db.refresh(user)
    return _user_response(user, db)


@router.get("/{user_id}", response_model=UserAdminResponse)
def get_user(
    user_id: uuid.UUID,
    principal: Principal = Depends(require_permission("users.view")),
    db: Session = Depends(get_db),
):
    require_global(principal, "users.view")
    user = db.get(User, user_id)
    if user is None:
        raise _not_found()
    return _user_response(user, db)


@router.patch("/{user_id}", response_model=UserAdminResponse)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    request: Request,
    principal: Principal = Depends(require_permission("users.edit")),
    db: Session = Depends(get_db),
):
    require_global(principal, "users.edit")
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise _not_found()
    target_principal = _load_principal(user, db)
    _ensure_target_manageable(principal, target_principal)
    changes = payload.model_dump(exclude_unset=True, exclude={"assignments"})
    if "is_active" in changes and changes["is_active"] != user.is_active:
        require_global(principal, "users.disable")
    assignments_payload = payload.assignments
    if assignments_payload is None:
        assignments_payload = [
            AccessAssignmentInput(
                role_id=grant.role_id,
                scope_type=grant.scope_type,
                customer_id=grant.customer_id,
                site_id=grant.site_id,
            )
            for grant in target_principal.grants
        ]
    else:
        if not principal.can_anywhere("users.assign_roles"):
            raise HTTPException(status_code=403, detail="Role assignment permission is required")
        _validate_assignments(db, principal, assignments_payload)
    new_active = changes.get("is_active", user.is_active)
    _lock_master_invariant(db)
    if not _would_keep_master(db, user, new_active, assignments_payload):
        raise HTTPException(
            status_code=409,
            detail="The final active Master Administrator cannot be disabled or demoted",
        )
    previous = {
        "display_name": user.display_name,
        "is_active": user.is_active,
        "force_password_change": user.force_password_change,
        "assignments": [
            {
                "role_id": str(grant.role_id),
                "scope_type": grant.scope_type,
                "customer_id": str(grant.customer_id) if grant.customer_id else None,
                "site_id": str(grant.site_id) if grant.site_id else None,
            }
            for grant in target_principal.grants
        ],
    }
    for key, value in changes.items():
        setattr(user, key, value)
    if payload.assignments is not None:
        _replace_assignments(db, user.id, payload.assignments)
    if changes.get("is_active") is False:
        user.session_version += 1
    add_audit_event(
        db,
        action="user.updated",
        target_type="user",
        target_id=user.id,
        actor=principal.user,
        success=True,
        summary="User profile, state, or access assignments updated",
        metadata={
            "before": previous,
            "after": {
                "display_name": user.display_name,
                "is_active": user.is_active,
                "force_password_change": user.force_password_change,
                "assignments": [
                    assignment.model_dump(mode="json")
                    for assignment in assignments_payload
                ],
            },
            "changed_fields": sorted(payload.model_fields_set),
        },
        request=request,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="User could not be updated") from exc
    db.refresh(user)
    return _user_response(user, db)


@router.post("/{user_id}/reset-password", response_model=UserAdminResponse)
def reset_password(
    user_id: uuid.UUID,
    payload: AdminPasswordResetRequest,
    request: Request,
    principal: Principal = Depends(require_permission("users.edit")),
    db: Session = Depends(get_db),
):
    require_global(principal, "users.edit")
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise _not_found()
    _ensure_target_manageable(principal, _load_principal(user, db))
    user.password_hash = hash_password(payload.temporary_password)
    user.force_password_change = payload.force_password_change
    user.failed_login_count = 0
    user.locked_until = None
    user.session_version += 1
    add_audit_event(
        db,
        action="user.password_reset",
        target_type="user",
        target_id=user.id,
        actor=principal.user,
        summary="Temporary password set; existing sessions invalidated",
        request=request,
    )
    db.commit()
    db.refresh(user)
    return _user_response(user, db)
