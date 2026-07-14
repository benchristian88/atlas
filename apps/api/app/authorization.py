"""Central role, permission, and customer/site scope enforcement."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated, Iterable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import and_, false, or_, select, true
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.auth import CurrentUser
from app.database import get_db
from app.models import AccessAssignment, Customer, Permission, Role, RolePermission, Site, User


_CONTEXTUAL_PERMISSION_PREFIXES = (
    "customers.",
    "sites.",
    "assets.",
    "relationships.",
    "networks.",
    "integrations.",
)


def is_contextual_permission(permission: str) -> bool:
    return permission == "audit.view" or permission.startswith(
        _CONTEXTUAL_PERMISSION_PREFIXES
    )


@dataclass(frozen=True, slots=True)
class ScopeGrant:
    assignment_id: uuid.UUID
    role_id: uuid.UUID
    role_name: str
    scope_type: str
    customer_id: uuid.UUID | None
    site_id: uuid.UUID | None
    permissions: frozenset[str]

    def covers(
        self,
        customer_id: uuid.UUID | None,
        site_id: uuid.UUID | None,
    ) -> bool:
        if self.scope_type == "global":
            return True
        if customer_id is None:
            return False
        if self.scope_type == "customer":
            return self.customer_id == customer_id
        return (
            self.scope_type == "site"
            and self.customer_id == customer_id
            and self.site_id == site_id
        )


@dataclass(frozen=True, slots=True)
class Principal:
    user: User
    grants: tuple[ScopeGrant, ...]

    @property
    def permissions(self) -> frozenset[str]:
        return frozenset(
            permission
            for grant in self.grants
            for permission in grant.permissions
        )

    @property
    def has_global_access(self) -> bool:
        return any(grant.scope_type == "global" for grant in self.grants)

    @property
    def context_grants(self) -> tuple[ScopeGrant, ...]:
        return tuple(
            grant
            for grant in self.grants
            if any(is_contextual_permission(key) for key in grant.permissions)
        )

    @property
    def has_global_context_access(self) -> bool:
        return any(grant.scope_type == "global" for grant in self.context_grants)

    def can_anywhere(self, permission: str) -> bool:
        return any(permission in grant.permissions for grant in self.grants)

    def can_within_customer(self, permission: str, customer_id: uuid.UUID) -> bool:
        return any(
            permission in grant.permissions
            and (
                grant.scope_type == "global" or grant.customer_id == customer_id
            )
            for grant in self.grants
        )

    def can(
        self,
        permission: str,
        customer_id: uuid.UUID | None = None,
        site_id: uuid.UUID | None = None,
    ) -> bool:
        return any(
            permission in grant.permissions
            and (
                grant.covers(customer_id, site_id)
                or (
                    permission == "customers.view"
                    and site_id is None
                    and grant.scope_type == "site"
                    and grant.customer_id == customer_id
                )
            )
            for grant in self.grants
        )

    def can_access_context(
        self, customer_id: uuid.UUID, site_id: uuid.UUID | None = None
    ) -> bool:
        return any(
            grant.covers(customer_id, site_id)
            or (
                site_id is None
                and grant.scope_type == "site"
                and grant.customer_id == customer_id
            )
            for grant in self.context_grants
        )


def _load_principal(user: User, db: Session) -> Principal:
    assignment_rows = db.execute(
        select(AccessAssignment, Role)
        .join(Role, Role.id == AccessAssignment.role_id)
        .where(
            AccessAssignment.user_id == user.id,
            Role.active.is_(True),
        )
        .order_by(Role.sort_order, Role.name)
    ).all()
    role_ids = {role.id for _, role in assignment_rows}
    permissions_by_role: dict[uuid.UUID, set[str]] = {
        role_id: set() for role_id in role_ids
    }
    if role_ids:
        for role_id, key in db.execute(
            select(RolePermission.role_id, Permission.key)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(RolePermission.role_id.in_(role_ids))
        ):
            permissions_by_role[role_id].add(key)
    grants = tuple(
        ScopeGrant(
            assignment_id=assignment.id,
            role_id=role.id,
            role_name=role.name,
            scope_type=assignment.scope_type,
            customer_id=assignment.customer_id,
            site_id=assignment.site_id,
            permissions=frozenset(permissions_by_role.get(role.id, set())),
        )
        for assignment, role in assignment_rows
    )
    return Principal(user=user, grants=grants)


def get_principal(user: CurrentUser, db: Session = Depends(get_db)) -> Principal:
    return _load_principal(user, db)


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def forbidden(detail: str = "You do not have permission to perform this action") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def require_permission(permission: str):
    def dependency(principal: CurrentPrincipal) -> Principal:
        if principal.user.force_password_change:
            raise forbidden("You must change your password before continuing")
        if not principal.can_anywhere(permission):
            raise forbidden()
        return principal

    return dependency


def require_any_permission(*permissions: str):
    def dependency(principal: CurrentPrincipal) -> Principal:
        if principal.user.force_password_change:
            raise forbidden("You must change your password before continuing")
        if not any(principal.can_anywhere(key) for key in permissions):
            raise forbidden()
        return principal

    return dependency


def require_global(principal: Principal, permission: str) -> None:
    if not principal.can(permission, None, None):
        raise forbidden("This operation requires global access")


def require_scope(
    principal: Principal,
    permission: str,
    customer_id: uuid.UUID,
    site_id: uuid.UUID | None = None,
    *,
    hide_existence: bool = False,
) -> None:
    if principal.can(permission, customer_id, site_id):
        return
    if hide_existence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    raise forbidden()


def scope_condition(
    principal: Principal,
    permission: str,
    customer_column,
    site_column=None,
) -> ColumnElement[bool]:
    """Build an SQL predicate for grants that carry ``permission``."""

    grants = [grant for grant in principal.grants if permission in grant.permissions]
    if any(grant.scope_type == "global" for grant in grants):
        return true()
    conditions: list[ColumnElement[bool]] = []
    customer_ids = {
        grant.customer_id
        for grant in grants
        if grant.scope_type == "customer" and grant.customer_id is not None
    }
    if customer_ids:
        conditions.append(customer_column.in_(customer_ids))
    if site_column is not None:
        site_pairs = {
            (grant.customer_id, grant.site_id)
            for grant in grants
            if grant.scope_type == "site"
            and grant.customer_id is not None
            and grant.site_id is not None
        }
        conditions.extend(
            and_(customer_column == customer_id, site_column == site_id)
            for customer_id, site_id in site_pairs
        )
    else:
        # A site assignment also makes its parent customer visible in customer lists.
        site_customer_ids = {
            grant.customer_id
            for grant in grants
            if grant.scope_type == "site" and grant.customer_id is not None
        }
        if site_customer_ids:
            conditions.append(customer_column.in_(site_customer_ids))
    return or_(*conditions) if conditions else false()


def site_scope_condition(
    principal: Principal,
    permission: str,
    customer_column,
    site_column,
) -> ColumnElement[bool]:
    return scope_condition(principal, permission, customer_column, site_column)


@dataclass(frozen=True, slots=True)
class ActiveContext:
    customer_id: uuid.UUID | None
    site_id: uuid.UUID | None


def get_active_context(
    principal: CurrentPrincipal,
    x_atlas_customer_id: Annotated[uuid.UUID | None, Header()] = None,
    x_atlas_site_id: Annotated[uuid.UUID | None, Header()] = None,
    db: Session = Depends(get_db),
) -> ActiveContext:
    if x_atlas_site_id is not None:
        site = db.get(Site, x_atlas_site_id)
        if site is None:
            raise forbidden("The selected site is no longer available")
        if x_atlas_customer_id is None:
            x_atlas_customer_id = site.customer_id
        elif site.customer_id != x_atlas_customer_id:
            raise forbidden("The selected site does not belong to the selected customer")
    if x_atlas_customer_id is not None and db.get(Customer, x_atlas_customer_id) is None:
        raise forbidden("The selected customer is no longer available")
    if x_atlas_customer_id is not None and not principal.can_access_context(
        x_atlas_customer_id, x_atlas_site_id
    ):
        raise forbidden("The selected customer or site is not available to this user")
    return ActiveContext(x_atlas_customer_id, x_atlas_site_id)


RequestContext = Annotated[ActiveContext, Depends(get_active_context)]


def role_names(principal: Principal) -> list[str]:
    return sorted({grant.role_name for grant in principal.grants})


def grants_with_permission(
    principal: Principal, permission: str
) -> Iterable[ScopeGrant]:
    return (grant for grant in principal.grants if permission in grant.permissions)
