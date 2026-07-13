import uuid
from unittest.mock import Mock

import pytest

from app.auth import verify_password
from scripts.seed_admin import AdminSeedError, seed_admin


def environment(**overrides: str) -> dict[str, str]:
    values = {
        "ATLAS_ADMIN_EMAIL": "ADMIN@example.com",
        "ATLAS_ADMIN_PASSWORD": "correct horse battery staple",
        "ATLAS_ADMIN_DISPLAY_NAME": "Atlas Admin",
    }
    values.update(overrides)
    return values


def test_seed_creates_hashed_admin_without_storing_plaintext() -> None:
    db = Mock()
    db.scalar.return_value = None

    assert seed_admin(db, environment()) is True
    user = db.add.call_args.args[0]
    assert user.email == "admin@example.com"
    assert user.display_name == "Atlas Admin"
    assert user.password_hash != "correct horse battery staple"
    assert verify_password("correct horse battery staple", user.password_hash)


def test_seed_is_idempotent_when_admin_already_exists() -> None:
    db = Mock()
    db.scalar.return_value = uuid.uuid4()

    assert seed_admin(db, environment()) is False
    db.add.assert_not_called()


@pytest.mark.parametrize(
    "missing_variable",
    ["ATLAS_ADMIN_EMAIL", "ATLAS_ADMIN_PASSWORD", "ATLAS_ADMIN_DISPLAY_NAME"],
)
def test_seed_fails_clearly_when_required_variable_is_missing(
    missing_variable: str,
) -> None:
    values = environment()
    values.pop(missing_variable)
    with pytest.raises(AdminSeedError, match=missing_variable):
        seed_admin(Mock(), values)


def test_seed_rejects_short_password_without_echoing_it() -> None:
    password = "too-short"
    with pytest.raises(AdminSeedError) as exc_info:
        seed_admin(Mock(), environment(ATLAS_ADMIN_PASSWORD=password))
    assert password not in str(exc_info.value)
