import importlib.util
import json
from pathlib import Path
import secrets
import stat

import pytest

from app.config import database_url
from app.release import build_metadata
from app.services.system_settings import session_minutes, validate_session_minutes

ROOT = Path(__file__).resolve().parents[3]


def configuration_module():
    spec = importlib.util.spec_from_file_location("configuration", ROOT / "infra/install/configuration.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_configuration_secrets_permissions_and_no_overwrite(tmp_path):
    module = configuration_module()
    target = tmp_path / "atlas.env"
    module.generate_configuration(target, "docker_compose")
    content = target.read_text()
    settings = dict(line.split("=", 1) for line in content.splitlines() if line and not line.startswith("#"))
    assert len(settings["POSTGRES_PASSWORD"]) == 64
    assert len(settings["AUTH_SECRET_KEY"]) == 96
    assert settings["POSTGRES_PASSWORD"] not in settings["AUTH_SECRET_KEY"]
    assert settings["AUTH_COOKIE_SECURE"] == "auto"
    assert settings["ATLAS_INSTALL_METHOD"] == "docker_compose"
    assert "DATABASE_URL" not in settings
    assert "AUTH_SESSION_MINUTES" not in content
    assert "ATLAS_BOOTSTRAP" not in content
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        module.generate_configuration(target, "docker_compose")
    assert target.read_text() == content
    other = tmp_path / "native.env"
    module.generate_configuration(other, "systemd")
    assert "ATLAS_INSTALL_METHOD=systemd" in other.read_text()
    assert "AUTH_COOKIE_SECURE=true" in other.read_text()
    assert "ATLAS_BIND_ADDRESS" not in other.read_text()
    assert settings["AUTH_SECRET_KEY"] not in other.read_text()


def test_configuration_refuses_symlink(tmp_path):
    existing = tmp_path / "existing"
    existing.write_text("operator config")
    link = tmp_path / "link"
    link.symlink_to(existing)
    with pytest.raises(FileExistsError):
        configuration_module().generate_configuration(link, "docker_compose")
    assert existing.read_text() == "operator config"


@pytest.mark.parametrize("method", ["docker_compose", "systemd", "development"])
def test_artifact_metadata_without_runtime_git(monkeypatch, method):
    monkeypatch.setenv("ATLAS_INSTALL_METHOD", method)
    monkeypatch.setenv("ATLAS_BUILD_ID", "test-build")
    metadata = build_metadata()
    assert metadata["install_method"] == method
    assert metadata["build_id"] == "test-build"
    assert metadata["version"] == json.loads((ROOT / "apps/api/app/release.json").read_text())["version"]


def test_invalid_install_method_is_rejected(monkeypatch):
    monkeypatch.setenv("ATLAS_INSTALL_METHOD", "manual")
    with pytest.raises(RuntimeError):
        build_metadata()


def test_production_database_requires_credentials_and_escapes_password(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.setenv("ATLAS_INSTALL_METHOD", "systemd")
    with pytest.raises(RuntimeError):
        database_url()
    password = secrets.token_urlsafe(32) + "@:/%"
    monkeypatch.setenv("POSTGRES_PASSWORD", password)
    from sqlalchemy.engine import make_url
    assert make_url(database_url()).password == password


@pytest.mark.parametrize("value", [1, 480, 10080])
def test_session_range(value):
    assert validate_session_minutes(value) == value


@pytest.mark.parametrize("value", [0, 10081, -1, True, "480", 480.0, None])
def test_session_range_rejects_wrong_types_and_bounds(value):
    with pytest.raises(ValueError):
        validate_session_minutes(value)


def test_absent_session_setting_defaults_and_ignores_environment(monkeypatch):
    from unittest.mock import Mock
    db = Mock()
    db.scalar.return_value = None
    monkeypatch.setenv("AUTH_SESSION_MINUTES", "1")
    assert session_minutes(db) == 480


def test_deployment_restart_and_security_contracts():
    import yaml  # Included by the existing uvicorn[standard] dependency.
    compose = yaml.safe_load((ROOT / "infra/docker/docker-compose.yml").read_text())
    services = compose["services"]
    assert set(services) == {"gateway", "api", "web", "worker", "postgres", "redis"}
    assert all(service["restart"] == "unless-stopped" for service in services.values())
    assert "ports" not in services["postgres"]
    assert "ports" not in services["redis"]
    assert "POSTGRES_PASSWORD" not in services["web"].get("environment", {})
    for name in ("api", "web", "worker"):
        unit = (ROOT / f"infra/systemd/atlas-{name}.service").read_text()
        assert "User=atlas" in unit
        assert "Restart=on-failure" in unit
        assert "WantedBy=multi-user.target" in unit
        assert "NoNewPrivileges=true" in unit
