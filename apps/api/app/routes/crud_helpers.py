import uuid
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import Table, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import BusinessFunction, Service


def not_found(resource: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{resource} not found",
    )


def has_retained_context_reference(
    db: Session, parent: Literal["customer", "site"], parent_id: uuid.UUID
) -> bool:
    # These rows already RESTRICT physical parent deletion. Check them before
    # DELETE's audit SET NULL actions can hit the tombstone immutability trigger.
    # Ordinary reads hide tombstones; this internal existence check must not.
    return any(
        db.scalar(select(model.id).where(
            getattr(model, f"{parent}_id") == parent_id,
            model.deleted_at.is_not(None),
        ).limit(1).execution_options(include_deleted=True)) is not None
        for model in (Service, BusinessFunction)
    )


def _restricts_parent(exc: IntegrityError, parent: Table) -> bool:
    """Recognize only restricting FKs to this parent, never unrelated failures."""
    if getattr(exc.orig, "sqlstate", None) != "23503":
        return False
    diagnostic = getattr(exc.orig, "diag", None)
    return any(
        constraint.referred_table is parent
        and (constraint.ondelete or "NO ACTION").upper() in {"RESTRICT", "NO ACTION"}
        and constraint.name == getattr(diagnostic, "constraint_name", None)
        and table.name == getattr(diagnostic, "table_name", None)
        for table in parent.metadata.tables.values()
        for constraint in table.foreign_key_constraints
    )


def commit(
    db: Session,
    resource: str,
    *,
    parent_dependency: tuple[Table, str] | None = None,
) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        detail = f"{resource} conflicts with an existing record or dependency"
        if parent_dependency and _restricts_parent(exc, parent_dependency[0]):
            detail = parent_dependency[1]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        ) from exc


def flush(db: Session, resource: str) -> None:
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{resource} conflicts with an existing record or dependency",
        ) from exc


def apply_changes(instance: object, changes: dict) -> None:
    for field, value in changes.items():
        setattr(instance, field, value)
