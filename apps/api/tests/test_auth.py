import os
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth import (
    COOKIE_NAME,
    create_session_token,
    decode_session_token,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.main import allowed_origins, app
from app.models import AccessAssignment, AuditEvent, Permission, Role, User


class Result:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def __iter__(self):
        return iter(self.rows)


class AuthDatabase:
    def __init__(self, user: User | None, permissions: set[str] | None = None):
        self.user = user
        self.added = []
        self.commits = 0
        self.role = Role(
            id=uuid.uuid4(),
            name="Master Administrator",
            description="Test role",
            system_defined=True,
            active=True,
            sort_order=10,
        )
        self.assignment = AccessAssignment(
            id=uuid.uuid4(),
            user_id=user.id if user else uuid.uuid4(),
            role_id=self.role.id,
            scope_type="global",
            customer_id=None,
            site_id=None,
        )
        self.permissions = permissions or {"assets.view"}

    def scalar(self, statement):
        if "FROM users" in str(statement):
            return self.user
        return None

    def execute(self, statement):
        sql = str(statement)
        if "FROM access_assignments JOIN roles" in sql:
            return Result([(self.assignment, self.role)] if self.user else [])
        if "FROM role_permissions JOIN permissions" in sql:
            return Result([(self.role.id, key) for key in self.permissions])
        return Result([])

    def add(self, record):
        self.added.append(record)

    def commit(self):
        self.commits += 1

    def refresh(self, record):
        return None


@pytest.fixture(autouse=True)
def auth_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key-with-at-least-32-characters")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("AUTH_SESSION_MINUTES", "30")
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def user() -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=uuid.uuid4(),
        email="admin@example.com",
        display_name="Atlas Admin",
        accent_colour=None,
        password_hash=hash_password("correct horse battery staple"),
        is_active=True,
        force_password_change=False,
        last_login_at=None,
        failed_login_count=0,
        locked_until=None,
        session_version=1,
        auth_provider="local",
        external_subject=None,
        mfa_enabled=False,
        created_at=now,
        updated_at=now,
    )


def client_for(db: AuthDatabase) -> TestClient:
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_passwords_are_argon2_hashed() -> None:
    password_hash = hash_password("a sufficiently long password")
    assert password_hash.startswith("$argon2")
    assert verify_password("a sufficiently long password", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_login_uses_http_only_cookie_without_exposing_token(user: User) -> None:
    db = AuthDatabase(user)
    with client_for(db) as client:
        response = client.post(
            "/api/auth/login",
            json={"email": "ADMIN@example.com", "password": "correct horse battery staple"},
        )
        assert response.status_code == 200
        assert "access_token" not in response.json()
        assert response.json()["user"]["email"] == user.email
        assert response.json()["user"]["accent_colour"] is None
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=lax" in response.headers["set-cookie"]
        assert "Path=/" in response.headers["set-cookie"]
        claims = decode_session_token(client.cookies[COOKIE_NAME])
        assert claims.user_id == user.id
        assert claims.session_version == 1
        assert client.get("/api/auth/me").status_code == 200
    assert any(
        isinstance(item, AuditEvent) and item.event_type == "auth.login_succeeded"
        for item in db.added
    )


def test_unauthenticated_current_user_is_rejected() -> None:
    with client_for(AuthDatabase(None)) as client:
        assert client.get("/api/auth/me").status_code == 401


def test_profile_accent_colour_is_normalised_and_can_be_reset(user: User) -> None:
    with client_for(AuthDatabase(user)) as client:
        assert client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "correct horse battery staple"},
        ).status_code == 200
        updated = client.patch(
            "/api/auth/profile",
            json={"display_name": user.display_name, "accent_colour": "#2563eb"},
        )
        assert updated.status_code == 200
        assert updated.json()["accent_colour"] == "#2563EB"
        assert user.accent_colour == "#2563EB"

        reset = client.patch(
            "/api/auth/profile",
            json={"display_name": user.display_name, "accent_colour": None},
        )
        assert reset.status_code == 200
        assert reset.json()["accent_colour"] is None
        assert user.accent_colour is None


@pytest.mark.parametrize(
    "unsafe_colour",
    ["red", "#FFF", "#11223344", "rgb(1, 2, 3)", "#123456; color:red", "url(x)", "<style>"],
)
def test_profile_rejects_unsafe_accent_colours(user: User, unsafe_colour: str) -> None:
    with client_for(AuthDatabase(user)) as client:
        assert client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "correct horse battery staple"},
        ).status_code == 200
        response = client.patch(
            "/api/auth/profile",
            json={"display_name": user.display_name, "accent_colour": unsafe_colour},
        )
        assert response.status_code == 422
        assert user.accent_colour is None


def test_profile_cannot_target_another_user(user: User) -> None:
    with client_for(AuthDatabase(user)) as client:
        assert client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "correct horse battery staple"},
        ).status_code == 200
        response = client.patch(
            "/api/auth/profile",
            json={
                "display_name": user.display_name,
                "accent_colour": "#2563EB",
                "theme_mode": "dark",
                "user_id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 422
        assert user.accent_colour is None
        assert user.theme_mode is None


def test_unauthenticated_profile_update_is_rejected(user: User) -> None:
    with client_for(AuthDatabase(user)) as client:
        response = client.patch(
            "/api/auth/profile",
            json={"display_name": user.display_name, "accent_colour": "#2563EB", "theme_mode": "dark"},
        )
        assert response.status_code == 401


@pytest.mark.parametrize("mode", ["light", "dark", "system"])
def test_profile_theme_is_independent_and_reloads_after_login(user: User, mode: str) -> None:
    user.accent_colour = "#2563EB"
    db = AuthDatabase(user)
    with client_for(db) as client:
        credentials = {"email": user.email, "password": "correct horse battery staple"}
        assert client.post("/api/auth/login", json=credentials).json()["user"]["theme_mode"] == "system"
        updated = client.patch("/api/auth/profile", json={"display_name": user.display_name, "theme_mode": mode})
        assert updated.status_code == 200
        assert updated.json()["theme_mode"] == mode
        assert updated.json()["accent_colour"] == "#2563EB"
        audit = next(item for item in db.added if isinstance(item, AuditEvent) and item.event_type == "profile.updated")
        assert audit.metadata_["theme_mode"] == {"from": "system", "to": mode}
        # Older clients omitting theme mode must not reset it.
        changed = client.patch("/api/auth/profile", json={"display_name": user.display_name, "accent_colour": None})
        assert changed.json()["theme_mode"] == mode
        assert client.get("/api/auth/me").json()["theme_mode"] == mode
        assert client.post("/api/auth/logout").status_code == 204
        signed_in = client.post("/api/auth/login", json=credentials)
        assert signed_in.json()["user"]["theme_mode"] == mode
        assert signed_in.json()["user"]["accent_colour"] is None


@pytest.mark.parametrize("mode", ["sepia", "DARK", "", None, 1])
def test_profile_rejects_invalid_theme_modes(user: User, mode) -> None:
    with client_for(AuthDatabase(user)) as client:
        client.post("/api/auth/login", json={"email": user.email, "password": "correct horse battery staple"})
        response = client.patch("/api/auth/profile", json={"display_name": user.display_name, "theme_mode": mode})
        assert response.status_code == 422
        assert user.theme_mode is None


@pytest.mark.skipif(not os.getenv("ATLAS_TEST_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")
def test_postgres_profile_preferences_reload_in_new_sessions(user: User) -> None:
    engine = create_engine(os.environ["ATLAS_TEST_DATABASE_URL"])
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as db:
            db.add(user)
            db.commit()

        def override_get_db():
            with Session(connection, join_transaction_mode="create_savepoint") as db:
                yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            with TestClient(app) as client:
                credentials = {"email": "admin@example.com", "password": "correct horse battery staple"}
                assert client.post("/api/auth/login", json=credentials).status_code == 200
                updated = client.patch("/api/auth/profile", json={"display_name": "Theme test", "accent_colour": "#7C3AED", "theme_mode": "light"})
                assert updated.status_code == 200
                assert client.post("/api/auth/logout").status_code == 204
                signed_in = client.post("/api/auth/login", json=credentials).json()["user"]
                assert signed_in["theme_mode"] == "light"
                assert signed_in["accent_colour"] == "#7C3AED"
                assert client.get("/api/auth/me").json()["theme_mode"] == "light"
        finally:
            transaction.rollback()
    engine.dispose()


@pytest.mark.parametrize("password", ["wrong password", "another wrong password"])
def test_invalid_login_is_generic_and_audited(user: User, password: str) -> None:
    db = AuthDatabase(user)
    with client_for(db) as client:
        response = client.post(
            "/api/auth/login", json={"email": user.email, "password": password}
        )
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid email or password"}
        assert COOKIE_NAME not in client.cookies
    assert user.failed_login_count == 1
    event = next(item for item in db.added if isinstance(item, AuditEvent))
    assert event.success is False
    assert password not in str(event.metadata_)


def test_disabled_user_cannot_log_in(user: User) -> None:
    user.is_active = False
    with client_for(AuthDatabase(user)) as client:
        response = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "correct horse battery staple"},
        )
        assert response.status_code == 401


def test_password_change_requires_current_password_and_rotates_sessions(user: User) -> None:
    db = AuthDatabase(user)
    with client_for(db) as client:
        assert client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "correct horse battery staple"},
        ).status_code == 200
        old_cookie = client.cookies[COOKIE_NAME]
        wrong = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "not the current password",
                "new_password": "a completely new password",
                "new_password_confirmation": "a completely new password",
            },
        )
        assert wrong.status_code == 400
        changed = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "correct horse battery staple",
                "new_password": "a completely new password",
                "new_password_confirmation": "a completely new password",
            },
        )
        assert changed.status_code == 200
        assert verify_password("a completely new password", user.password_hash)
        assert user.session_version == 2
        assert client.cookies[COOKIE_NAME] != old_cookie
        assert decode_session_token(client.cookies[COOKIE_NAME]).session_version == 2


def test_logout_invalidates_the_session_generation(user: User) -> None:
    db = AuthDatabase(user)
    with client_for(db) as client:
        assert client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "correct horse battery staple"},
        ).status_code == 200
        response = client.post("/api/auth/logout")
        assert response.status_code == 204
        assert COOKIE_NAME not in client.cookies
    assert user.session_version == 2


def test_session_token_carries_revocation_generation(user: User) -> None:
    token = create_session_token(user)
    claims = decode_session_token(token)
    assert claims.user_id == user.id
    assert claims.session_version == user.session_version


def test_cross_origin_state_change_is_rejected(user: User) -> None:
    with client_for(AuthDatabase(user)) as client:
        response = client.post(
            "/api/auth/login",
            headers={"Origin": "https://attacker.example"},
            json={"email": user.email, "password": "correct horse battery staple"},
        )
        assert response.status_code == 403


def test_same_origin_state_change_is_allowed(user: User) -> None:
    with client_for(AuthDatabase(user)) as client:
        response = client.post(
            "/api/auth/login",
            headers={"Origin": "http://testserver"},
            json={"email": user.email, "password": "correct horse battery staple"},
        )
        assert response.status_code == 200


def test_configured_split_origin_can_send_context_headers(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "  http://web.test/, ,invalid  ")
    assert allowed_origins() == ["http://web.test"]
    cors_app = CORSMiddleware(
        app,
        allow_origins=allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Atlas-Customer-ID", "X-Atlas-Site-ID"],
    )
    with TestClient(cors_app) as client:
        response = client.options(
            "/api/assets",
            headers={
                "Origin": "http://web.test",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": (
                    "x-atlas-customer-id,x-atlas-site-id,content-type"
                ),
            },
        )
        assert response.status_code == 200
        allowed = response.headers["access-control-allow-headers"].lower()
        assert "x-atlas-customer-id" in allowed
        assert "x-atlas-site-id" in allowed


def test_health_and_documentation_use_api_namespace() -> None:
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert client.get("/api/docs").status_code == 200
        assert client.get("/api/openapi.json").status_code == 200
        assert client.get("/health").status_code == 404
        assert client.get("/docs").status_code == 404
        assert client.get("/auth/me").status_code == 404
