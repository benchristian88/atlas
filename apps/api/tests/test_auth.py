import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.auth import COOKIE_NAME, decode_session_token, hash_password, verify_password
from app.database import get_db
from app.main import app
from app.models import User


@pytest.fixture(autouse=True)
def auth_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key-with-at-least-32-characters")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("AUTH_SESSION_MINUTES", "30")


@pytest.fixture
def user() -> User:
    return User(
        id=uuid.uuid4(),
        email="admin@example.com",
        display_name="Atlas Admin",
        password_hash=hash_password("correct horse battery staple"),
    )


def client_with_database_result(result: User | None) -> TestClient:
    db = Mock()
    db.scalar.return_value = result

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_passwords_are_argon2_hashed() -> None:
    password_hash = hash_password("a sufficiently long password")
    assert password_hash.startswith("$argon2")
    assert verify_password("a sufficiently long password", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_login_returns_bearer_token_and_allows_protected_routes(user: User) -> None:
    with client_with_database_result(user) as client:
        response = client.post(
            "/auth/login",
            json={"email": "ADMIN@example.com", "password": "correct horse battery staple"},
        )
        assert response.status_code == 200
        assert response.json()["token_type"] == "bearer"
        access_token = response.json()["access_token"]
        assert response.json()["user"] == {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
        }
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=lax" in response.headers["set-cookie"]
        assert decode_session_token(access_token) == user.id
        assert decode_session_token(client.cookies[COOKIE_NAME]) == user.id

        authorization = {"Authorization": f"Bearer {access_token}"}
        me_response = client.get("/auth/me", headers=authorization)
        assert me_response.status_code == 200
        protected_response = client.get("/protected", headers=authorization)
        assert protected_response.json() == {
            "message": "Authenticated as admin@example.com"
        }
    app.dependency_overrides.clear()


def test_existing_cookie_authentication_remains_supported(user: User) -> None:
    with client_with_database_result(user) as client:
        response = client.post(
            "/auth/login",
            json={"email": user.email, "password": "correct horse battery staple"},
        )
        assert response.status_code == 200
        assert client.get("/auth/me").status_code == 200
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("database_result", "password"),
    [(None, "any password"), ("user", "wrong password")],
)
def test_login_rejects_invalid_credentials(
    database_result: User | str | None, password: str, user: User
) -> None:
    result = user if database_result == "user" else None
    with client_with_database_result(result) as client:
        response = client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": password},
        )
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid email or password"}
        assert COOKIE_NAME not in client.cookies
    app.dependency_overrides.clear()


def test_protected_routes_require_a_valid_session(user: User) -> None:
    with client_with_database_result(user) as client:
        assert client.get("/auth/me").status_code == 401
        assert client.get("/protected").status_code == 401
    app.dependency_overrides.clear()


def test_logout_clears_session_cookie(user: User) -> None:
    with client_with_database_result(user) as client:
        assert client.post(
            "/auth/login",
            json={"email": user.email, "password": "correct horse battery staple"},
        ).status_code == 200
        assert COOKIE_NAME in client.cookies

        response = client.post("/auth/logout")
        assert response.status_code == 204
        assert COOKIE_NAME not in client.cookies
    app.dependency_overrides.clear()


def test_web_origin_can_make_credentialed_requests(user: User) -> None:
    with client_with_database_result(user) as client:
        response = client.options(
            "/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert response.headers["access-control-allow-credentials"] == "true"
        assert "Authorization" in response.headers["access-control-allow-headers"]
    app.dependency_overrides.clear()
