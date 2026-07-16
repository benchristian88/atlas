import uuid
from unittest.mock import Mock

import pytest

from app.auth import verify_password
from app.models import AccessAssignment, Role, User
from scripts import seed_admin as seed_module
from scripts.seed_admin import AdminSeedError, _bootstrap_admin, seed_admin


def environment(**overrides: str) -> dict[str, str]:
    values = {
        "ATLAS_BOOTSTRAP_ADMIN_EMAIL": "ADMIN@example.com",
        "ATLAS_BOOTSTRAP_ADMIN_PASSWORD": "correct horse battery staple",
        "ATLAS_BOOTSTRAP_ADMIN_NAME": "Atlas Admin",
    }
    values.update(overrides)
    return values


class EmptySeedDatabase:
    def __init__(self):
        self.added = []

    def scalar(self, statement):
        return None

    def add(self, record):
        if getattr(record, "id", None) is None and isinstance(record, User):
            record.id = uuid.uuid4()
        self.added.append(record)

    def flush(self):
        return None


def test_bootstrap_creates_hashed_forced_change_master_only_when_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = EmptySeedDatabase()
    master = Role(id=uuid.uuid4(), name="Master Administrator")
    monkeypatch.setattr(seed_module, "_ensure_rbac", lambda _: master)
    monkeypatch.setattr(seed_module, "_ensure_taxonomy", lambda _: None)
    monkeypatch.setattr(seed_module, "_ensure_home_context", lambda _: None)

    assert seed_admin(db, environment()) is True
    user = next(item for item in db.added if isinstance(item, User))
    assignment = next(item for item in db.added if isinstance(item, AccessAssignment))
    assert user.email == "admin@example.com"
    assert user.display_name == "Atlas Admin"
    assert user.force_password_change is True
    assert user.password_hash != "correct horse battery staple"
    assert verify_password("correct horse battery staple", user.password_hash)
    assert assignment.user_id == user.id
    assert assignment.role_id == master.id
    assert assignment.scope_type == "global"


def test_existing_user_prevents_bootstrap_and_environment_password_is_ignored() -> None:
    existing_id = uuid.uuid4()
    db = Mock()
    db.scalar.return_value = existing_id
    hostile = environment(ATLAS_BOOTSTRAP_ADMIN_PASSWORD="replacement password value")
    assert seed_admin(db, hostile) is False
    db.add.assert_not_called()


def test_missing_bootstrap_configuration_is_a_safe_noop() -> None:
    db = Mock()
    db.scalar.return_value = None
    assert seed_admin(db, {}) is False
    db.add.assert_not_called()


@pytest.mark.parametrize(
    "missing_variable",
    [
        "ATLAS_BOOTSTRAP_ADMIN_EMAIL",
        "ATLAS_BOOTSTRAP_ADMIN_PASSWORD",
        "ATLAS_BOOTSTRAP_ADMIN_NAME",
    ],
)
def test_partial_bootstrap_configuration_fails_clearly(missing_variable: str) -> None:
    values = environment()
    values.pop(missing_variable)
    with pytest.raises(AdminSeedError, match=missing_variable):
        _bootstrap_admin(values)


def test_bootstrap_rejects_short_password_without_echoing_it() -> None:
    password = "too-short"
    with pytest.raises(AdminSeedError) as exc_info:
        _bootstrap_admin(environment(ATLAS_BOOTSTRAP_ADMIN_PASSWORD=password))
    assert password not in str(exc_info.value)


def test_legacy_variables_are_one_time_bootstrap_compatible() -> None:
    legacy = {
        "ATLAS_ADMIN_EMAIL": "legacy@example.com",
        "ATLAS_ADMIN_PASSWORD": "correct horse battery staple",
        "ATLAS_ADMIN_DISPLAY_NAME": "Legacy Admin",
    }
    with pytest.warns(RuntimeWarning, match="deprecated"):
        configured = _bootstrap_admin(legacy)
    assert configured.email == "legacy@example.com"
    assert configured.legacy_fallback is True
