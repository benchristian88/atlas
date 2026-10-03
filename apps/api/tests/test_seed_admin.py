"""The retired command must seed definitions only, never environment users."""
from unittest.mock import Mock

from app.models import User
from scripts import seed_system


def test_definition_seed_never_creates_users(monkeypatch):
    db = Mock()
    db.scalar.return_value = None
    for name in ("_ensure_rbac", "_ensure_taxonomy"):
        monkeypatch.setattr(seed_system, name, Mock())
    monkeypatch.setenv("ATLAS_BOOTSTRAP_ADMIN_EMAIL", "obsolete@example.com")
    monkeypatch.setenv("ATLAS_BOOTSTRAP_ADMIN_PASSWORD", "ignored")
    monkeypatch.setenv("ATLAS_ADMIN_PASSWORD", "ignored")
    seed_system.seed_system(db)
    assert not any(isinstance(call.args[0], User) for call in db.add.call_args_list)
    seed_system._ensure_rbac.assert_called_once_with(db)
    seed_system._ensure_taxonomy.assert_called_once_with(db)
