"""H1 security tests require a migrated, disposable PostgreSQL database."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
import secrets
import threading

from fastapi import HTTPException
from fastapi.testclient import TestClient
import jwt
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.auth import COOKIE_NAME, _secret_key, decode_session_token, hash_password
from app.database import get_db
from app.main import app
from app.models import AccessAssignment, AuditEvent, InstallationState, SystemSetting, User
from app.routes.setup import FirstAdministratorRequest
from app.services.installation import SETUP_COOKIE, SETUP_DURATION, create_first_administrator, installation_state, is_initialized, normalize_code, require_setup_authorization, reset_setup_code, verify_setup_code
from app.services.system_settings import SESSION_LIFETIME_KEY

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_H1_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")


@pytest.fixture
def engine():
    engine = create_engine(os.environ["ATLAS_TEST_H1_DATABASE_URL"])
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine, monkeypatch):
    monkeypatch.setenv("AUTH_SECRET_KEY", secrets.token_hex(48))
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()
    app.dependency_overrides.clear()


@pytest.fixture
def client(db):
    def override_db():
        yield db
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client


def admin_payload():
    password = secrets.token_urlsafe(24)
    return {"display_name": "Atlas Administrator", "email": "admin@example.com",
            "password": password, "password_confirmation": password}


def authorize(db, client):
    code = reset_setup_code(db)
    db.commit()
    response = client.post("/api/setup/verify", json={"code": code})
    assert response.status_code == 204
    return code


def initialize(db, client):
    authorize(db, client)
    payload = admin_payload()
    assert client.post("/api/setup/administrator", json=payload).status_code == 204
    return payload


def test_fresh_database_status_and_no_credential_leaks(db, client):
    assert client.get("/api/setup/status").json() == {"state": "UNINITIALISED", "authorized": False}
    code = reset_setup_code(db)
    db.commit()
    state = installation_state(db)
    assert code not in state.setup_code_hash
    assert normalize_code(code) not in state.setup_code_hash
    assert state.setup_code_hash.startswith("$argon2")
    assert len(normalize_code(code)) == 20
    response = client.post("/api/setup/verify", json={"code": code.lower()})
    assert response.status_code == 204
    assert response.content == b""
    assert code not in str(response.headers)
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/api/setup" in cookie
    assert "Max-Age=600" in cookie
    assert client.get("/api/setup/status").json()["authorized"] is True
    assert client.get("/api/auth/me").status_code == 401
    with pytest.raises(HTTPException):
        decode_session_token(client.cookies[SETUP_COOKIE])


def test_invalid_code_generic_throttled_and_validation_redacted(db, client):
    reset_setup_code(db)
    db.commit()
    wrong = secrets.token_urlsafe(24)
    for _ in range(5):
        response = client.post("/api/setup/verify", json={"code": wrong})
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid setup code"}
    assert client.post("/api/setup/verify", json={"code": wrong}).status_code == 429
    too_long = secrets.token_urlsafe(150)
    response = client.post("/api/setup/verify", json={"code": too_long})
    assert response.status_code == 422 and too_long not in response.text
    assert SETUP_COOKIE not in client.cookies


def test_admin_requires_setup_authorization_and_normal_session_is_not_setup(db, client):
    payload = admin_payload()
    assert client.post("/api/setup/administrator", json=payload).status_code == 401
    assert db.scalar(select(func.count()).select_from(User)) == 0
    assert installation_state(db).initialized_at is None


def test_expired_wrong_audience_and_reset_authorizations_refuse(db, client):
    code = authorize(db, client)
    old_token = client.cookies[SETUP_COOKIE]
    claims = jwt.decode(old_token, _secret_key(), algorithms=["HS256"], audience="atlas-setup", issuer="atlas-api")
    assert claims["exp"] - claims["iat"] == 600
    claims["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    expired = jwt.encode(claims, _secret_key(), algorithm="HS256")
    with pytest.raises(HTTPException):
        require_setup_authorization(installation_state(db), expired)
    claims["exp"] = datetime.now(timezone.utc) + SETUP_DURATION
    claims["aud"] = "atlas-web"
    with pytest.raises(HTTPException):
        require_setup_authorization(installation_state(db), jwt.encode(claims, _secret_key(), algorithm="HS256"))
    new_code = reset_setup_code(db)
    db.commit()
    assert client.get("/api/setup/status").json()["authorized"] is False
    assert client.post("/api/setup/administrator", json=admin_payload()).status_code == 401
    assert client.post("/api/setup/verify", json={"code": code}).status_code == 401
    assert client.post("/api/setup/verify", json={"code": new_code}).status_code == 204


@pytest.mark.parametrize("password,confirmation", [("tiny123", "tiny123"), ("a long test password", "another long password")])
def test_password_policy_is_enforced_without_echo(db, client, password, confirmation):
    authorize(db, client)
    payload = admin_payload()
    payload.update(password=password, password_confirmation=confirmation)
    response = client.post("/api/setup/administrator", json=payload)
    assert response.status_code == 422
    assert password not in response.text
    assert installation_state(db).initialized_at is None
    assert db.scalar(select(func.count()).select_from(User)) == 0


def test_first_admin_permissions_login_and_permanent_setup_closure(db, client):
    code = authorize(db, client)
    token = client.cookies[SETUP_COOKIE]
    payload = admin_payload()
    assert client.post("/api/setup/administrator", json=payload).status_code == 204
    assert SETUP_COOKIE not in client.cookies and COOKIE_NAME not in client.cookies
    state = installation_state(db)
    assert state.initialized_at is not None and state.setup_code_hash is None
    assert client.get("/api/setup/status").json() == {"state": "INITIALISED", "authorized": False}
    assert client.post("/api/setup/verify", json={"code": code}).status_code == 409
    client.cookies.set(SETUP_COOKIE, token, path="/api/setup")
    assert client.post("/api/setup/administrator", json=payload).status_code == 409
    with pytest.raises(HTTPException, match="409"):
        reset_setup_code(db)
    login = client.post("/api/auth/login", json={"email": payload["email"], "password": payload["password"]})
    assert login.status_code == 200
    user = login.json()["user"]
    assert "Master Administrator" in user["roles"]
    assert "system_settings.manage" in user["permissions"]
    assert user["assignments"][0]["scope_type"] == "global"
    assert user["force_password_change"] is False
    assert client.get("/api/auth/me").status_code == 200
    audit = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "setup.initialized"))
    assert code not in str(audit.metadata_) and payload["password"] not in str(audit.metadata_)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_legacy_user_closes_setup_even_without_state_backfill(db, client):
    db.add(User(email="legacy@example.com", display_name="Existing", password_hash=hash_password(secrets.token_urlsafe(24))))
    db.commit()
    assert installation_state(db).initialized_at is None
    assert client.get("/api/setup/status").json()["state"] == "INITIALISED"
    with pytest.raises(HTTPException):
        reset_setup_code(db)
    assert client.post("/api/setup/verify", json={"code": secrets.token_urlsafe(24)}).status_code == 409


def test_creation_rollback_keeps_installation_and_code_usable(db, client):
    authorize(db, client)
    token = client.cookies[SETUP_COOKIE]
    db.commit()
    with pytest.raises(RuntimeError):
        with db.begin_nested():
            create_first_administrator(db, FirstAdministratorRequest(**admin_payload()), token)
            raise RuntimeError("Simulated audit/persistence failure before commit")
    db.expire_all()
    assert installation_state(db).initialized_at is None
    assert db.scalar(select(func.count()).select_from(User)) == 0
    assert client.post("/api/setup/administrator", json=admin_payload()).status_code == 204


def test_session_setting_permissions_validation_issuance_and_environment_ignored(db, client, monkeypatch):
    monkeypatch.setenv("AUTH_SESSION_MINUTES", "1")
    assert client.patch(f"/api/system-settings/{SESSION_LIFETIME_KEY}", json={"value": 10}).status_code == 401
    payload = initialize(db, client)
    credentials = {"email": payload["email"], "password": payload["password"]}
    client.post("/api/auth/login", json=credentials)
    token = jwt.decode(client.cookies[COOKIE_NAME], _secret_key(), algorithms=["HS256"], audience="atlas-web")
    assert token["exp"] - token["iat"] == 480 * 60
    for invalid in [0, 10081, "50", True]:
        assert client.patch(f"/api/system-settings/{SESSION_LIFETIME_KEY}", json={"value": invalid}).status_code == 422
    for value in [1, 10080, 37]:
        assert client.patch(f"/api/system-settings/{SESSION_LIFETIME_KEY}", json={"value": value}).status_code == 200
    client.post("/api/auth/login", json=credentials)
    token = jwt.decode(client.cookies[COOKIE_NAME], _secret_key(), algorithms=["HS256"], audience="atlas-web")
    assert token["exp"] - token["iat"] == 37 * 60
    metadata = client.get("/api/system-settings/build-info")
    assert metadata.status_code == 200
    assert set(metadata.json()) == {"version", "release_channel", "build_id", "install_method"}
    replacement = secrets.token_urlsafe(24)
    changed = client.post("/api/auth/change-password", json={
        "current_password": payload["password"], "new_password": replacement,
        "new_password_confirmation": replacement,
    })
    assert changed.status_code == 200
    assert "Max-Age=2220" in changed.headers["set-cookie"]
    token = jwt.decode(client.cookies[COOKIE_NAME], _secret_key(), algorithms=["HS256"], audience="atlas-web")
    assert token["exp"] - token["iat"] == 37 * 60
    user = db.scalar(select(User))
    for assignment in db.scalars(select(AccessAssignment).where(AccessAssignment.user_id == user.id)):
        db.delete(assignment)
    db.commit()
    assert client.patch(f"/api/system-settings/{SESSION_LIFETIME_KEY}", json={"value": 50}).status_code == 403
    assert client.get("/api/system-settings/build-info").status_code == 403


def test_csrf_rejects_cross_origin_setup(db, client):
    code = reset_setup_code(db)
    db.commit()
    assert client.post("/api/setup/verify", headers={"Origin": "https://attacker.example"}, json={"code": code}).status_code == 403


@pytest.mark.parametrize("access_url,local_only", [("http://192.168.50.10:4300", False), ("http://127.0.0.1:3000", True)])
def test_local_reset_command_prints_once_and_refuses_initialized(db, client, monkeypatch, capsys, access_url, local_only):
    from sqlalchemy.orm import sessionmaker
    from scripts import setup_code
    import re
    import sys
    db.commit()
    monkeypatch.setattr(setup_code, "SessionLocal", sessionmaker(bind=db.get_bind(), join_transaction_mode="create_savepoint"))
    monkeypatch.setattr(sys, "argv", ["setup-code", "reset", "--access-url", access_url])
    setup_code.main()
    output = capsys.readouterr().out
    assert access_url in output
    assert ("local-only" in output) is local_only
    assert os.environ["AUTH_SECRET_KEY"] not in output
    matches = re.findall(r"[A-Z2-9]{4}(?:-[A-Z2-9]{4}){4}", output)
    assert len(matches) == 1
    db.expire_all()
    assert client.post("/api/setup/verify", json={"code": matches[0]}).status_code == 204
    assert client.post("/api/setup/administrator", json=admin_payload()).status_code == 204
    with pytest.raises(SystemExit, match="cannot be reset on an initialised instance"):
        setup_code.main()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("scheme,policy,secure", [("http", "auto", False), ("https", "auto", True),
                                                 ("https", "true", True), ("http", "false", False)])
@pytest.mark.parametrize("deployment", ["docker", "native"])
def test_single_origin_setup_login_authenticated_calls_and_cookie_lifecycle(db, monkeypatch, scheme, policy, secure, deployment):
    monkeypatch.setenv("AUTH_COOKIE_SECURE", policy)
    monkeypatch.setenv("CORS_ORIGINS", "")
    app.dependency_overrides[get_db] = lambda: db
    # Matches the private ingress upstream; native explicitly trusts loopback
    # only. The real nginx test exercises the public forwarding boundary.
    upstream = ProxyHeadersMiddleware(app, trusted_hosts="*" if deployment == "docker" else ["127.0.0.1"])
    origin = f"{scheme}://atlas.test:4300"
    with TestClient(upstream, base_url=origin, client=("172.20.0.2" if deployment == "docker" else "127.0.0.1", 1234),
                    headers={"Origin": origin, "X-Forwarded-Proto": scheme}) as browser:
        code = reset_setup_code(db)
        db.commit()
        verify = browser.post("/api/setup/verify", json={"code": code})
        assert verify.status_code == 204
        assert ("Secure" in verify.headers["set-cookie"]) is secure
        assert "HttpOnly" in verify.headers["set-cookie"] and "SameSite=lax" in verify.headers["set-cookie"]
        assert browser.get("/api/setup/status").json()["authorized"] is True
        payload = admin_payload()
        created = browser.post("/api/setup/administrator", json=payload)
        assert created.status_code == 204
        assert ("Secure" in created.headers["set-cookie"]) is secure
        login = browser.post("/api/auth/login", json={"email": payload["email"], "password": payload["password"]})
        assert login.status_code == 200
        assert ("Secure" in login.headers["set-cookie"]) is secure
        assert "access-control-allow-origin" not in login.headers
        assert browser.get("/api/auth/me").status_code == 200
        assert browser.get("/api/context").status_code == 200
        replacement = secrets.token_urlsafe(24)
        changed = browser.post("/api/auth/change-password", json={"current_password": payload["password"],
            "new_password": replacement, "new_password_confirmation": replacement})
        assert changed.status_code == 200
        assert ("Secure" in changed.headers["set-cookie"]) is secure
        assert browser.get("/api/auth/me").status_code == 200
        assert browser.post("/api/auth/login", json={"email": payload["email"], "password": replacement},
                            headers={"Origin": "https://attacker.example"}).status_code == 403
        logout = browser.post("/api/auth/logout")
        assert logout.status_code == 204
        assert ("Secure" in logout.headers["set-cookie"]) is secure
        assert browser.get("/api/auth/me").status_code == 401


def test_secure_cookie_and_expired_authorization_at_api(db, client, monkeypatch):
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    code = reset_setup_code(db)
    db.commit()
    response = client.post("/api/setup/verify", json={"code": code})
    assert "Secure" in response.headers["set-cookie"]
    claims = jwt.decode(client.cookies[SETUP_COOKIE], _secret_key(), algorithms=["HS256"], audience="atlas-setup")
    claims["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    client.cookies.clear()
    client.cookies.set(SETUP_COOKIE, jwt.encode(claims, _secret_key(), algorithm="HS256"), path="/api/setup")
    assert client.post("/api/setup/administrator", json=admin_payload()).status_code == 401


def test_competing_first_admin_requests_create_exactly_one(engine, monkeypatch):
    """Separate real transactions prove PostgreSQL locking, not a mock lock."""
    monkeypatch.setenv("AUTH_SECRET_KEY", secrets.token_hex(48))
    schema = "h1_race_" + secrets.token_hex(8)
    from app.models import Base
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(scoped)
        with Session(scoped) as db:
            db.add(InstallationState(id=1))
            db.commit()
            code = reset_setup_code(db)
            db.commit()
            token = verify_setup_code(db, code)
            db.commit()
        barrier = threading.Barrier(2)
        payload = FirstAdministratorRequest(**admin_payload())
        def create():
            with Session(scoped) as db:
                barrier.wait(timeout=10)
                try:
                    create_first_administrator(db, payload, token)
                    db.commit()
                    return "created"
                except HTTPException as exc:
                    db.rollback()
                    return exc.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(create) for _ in range(2)]
            outcomes = [future.result(timeout=30) for future in futures]
        assert sorted(map(str, outcomes)) == ["409", "created"]
        with Session(scoped) as db:
            assert db.scalar(select(func.count()).select_from(User)) == 1
            assert db.scalar(select(func.count()).select_from(AccessAssignment)) == 1
            assert installation_state(db).setup_code_hash is None
    finally:
        scoped.dispose()
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
