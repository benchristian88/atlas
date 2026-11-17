"""The parent-delete opt-in must not relabel other database failures."""
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import HTTPException
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Customer, Site
from app.routes.crud_helpers import commit


@pytest.mark.parametrize("parent", [Customer, Site])
@pytest.mark.parametrize("failure", ["parent_fk", "other_fk", "other_table", "set_null", "unique", "check", "no_diagnostic", "no_opt_in"])
def test_only_restricting_parent_fk_gets_dependency_explanation(parent, failure):
    target = parent.__table__
    constraint = next(c for c in Customer.metadata.tables["business_functions"].foreign_key_constraints if c.referred_table is target)
    diagnostic = SimpleNamespace(constraint_name=constraint.name, table_name="business_functions")
    sqlstate = "23503"
    if failure == "other_fk": diagnostic.constraint_name = "fk_audit_events_user_id_users"
    if failure == "other_table": diagnostic.table_name = "unrelated_table"
    if failure == "set_null":
        diagnostic.table_name = "audit_events"
        diagnostic.constraint_name = f"fk_audit_events_{'customer' if parent is Customer else 'site'}_id_{target.name}"
    if failure == "unique": sqlstate = "23505"
    if failure == "check": sqlstate = "23514"
    if failure == "no_diagnostic": diagnostic = None
    db = Mock()
    db.commit.side_effect = IntegrityError("not public", {}, SimpleNamespace(sqlstate=sqlstate, diag=diagnostic))
    options = {} if failure == "no_opt_in" else {"parent_dependency": (target, "Safe dependency explanation")}
    with pytest.raises(HTTPException) as error:
        commit(db, parent.__name__, **options)
    assert error.value.status_code == 409
    assert error.value.detail == (
        "Safe dependency explanation" if failure == "parent_fk"
        else f"{parent.__name__} conflicts with an existing record or dependency"
    )
    db.rollback.assert_called_once_with()


def test_parent_delete_does_not_disguise_unexpected_server_failure():
    db = Mock()
    failure = RuntimeError("internal failure")
    db.commit.side_effect = failure
    with pytest.raises(RuntimeError) as error:
        commit(db, "Customer", parent_dependency=(Customer.__table__, "Safe dependency explanation"))
    assert error.value is failure
