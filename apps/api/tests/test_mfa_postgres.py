"""H2 security acceptance on explicitly supplied disposable PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
import secrets
import sys
import threading
import uuid

from fastapi import HTTPException
from fastapi.testclient import TestClient
import jwt
import pyotp
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
import app.auth as auth_module

from app.auth import COOKIE_NAME, _secret_key, create_session_token, hash_password
from app.database import get_db
from app.main import app
from app.models import AccessAssignment, AuditEvent, Base, MfaChallenge, MfaRecoveryCode, Permission, Role, RolePermission, User, UserMfa
from app.services import mfa
from scripts.seed_system import _ensure_rbac

pytestmark = pytest.mark.skipif(not os.getenv("ATLAS_TEST_H2_DATABASE_URL"), reason="requires disposable migrated PostgreSQL")


@pytest.fixture
def engine():
    engine = create_engine(os.environ["ATLAS_TEST_H2_DATABASE_URL"], hide_parameters=True)
    yield engine
    engine.dispose()


@pytest.fixture
def clock(monkeypatch):
    instant = [datetime.now(timezone.utc)]
    monkeypatch.setattr(mfa, "now", lambda: instant[0])
    class ClockMeta(type):
        def __instancecheck__(cls, value):
            return isinstance(value, datetime)
    class JwtClock(datetime, metaclass=ClockMeta):
        @classmethod
        def now(cls, tz=None):
            return instant[0]
    monkeypatch.setattr(jwt.api_jwt, "datetime", JwtClock)
    monkeypatch.setattr(auth_module, "datetime", JwtClock)
    return instant


@pytest.fixture
def db(engine, monkeypatch, clock):
    monkeypatch.setenv("AUTH_SECRET_KEY", secrets.token_hex(48))
    monkeypatch.setenv("ATLAS_DATA_ENCRYPTION_KEY", secrets.token_hex(32))
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("ATLAS_INSTALL_METHOD", "development")
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint", autoflush=False, expire_on_commit=False) as session:
            yield session
        transaction.rollback()
    app.dependency_overrides.clear()


@pytest.fixture
def user(db):
    password = secrets.token_urlsafe(24)
    master = _ensure_rbac(db)
    user = User(email="h2@example.com", display_name="H2 test", password_hash=hash_password(password),
                mfa_enabled=False, is_active=True, force_password_change=False)
    db.add(user); db.flush()
    db.add(AccessAssignment(user_id=user.id, role_id=master.id, scope_type="global"))
    db.commit()
    return user, password


@pytest.fixture
def client(db, user):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as browser:
        browser.cookies.set(COOKIE_NAME, create_session_token(user[0]), path="/", domain="testserver.local")
        yield browser


def credentials(user, **extra):
    return {"current_password": user[1], **extra}


def enroll(client, user, clock):
    pending = client.post("/api/auth/mfa/enrollment", json=credentials(user))
    assert pending.status_code == 200, pending.status_code
    pending = pending.json()
    response = client.post("/api/auth/mfa/enrollment/confirm", json={
        "enrollment_id": pending["enrollment_id"], "code": pyotp.TOTP(pending["manual_key"]).at(clock[0])})
    assert response.status_code == 200, response.status_code
    return pending, response.json()["recovery_codes"]


def login(client, user):
    return client.post("/api/auth/login", json={"email": user[0].email, "password": user[1]})


def next_code(pending, clock):
    clock[0] += timedelta(seconds=30)
    return pyotp.TOTP(pending["manual_key"]).at(clock[0])


def test_enrollment_reauth_local_uri_confirm_storage_and_status(db, user, client, clock):
    original_cookie = client.cookies[COOKIE_NAME]
    assert client.get("/api/auth/mfa/status").json()["enabled"] is False
    assert client.post("/api/auth/mfa/enrollment", json={"current_password": "wrong"}).status_code == 400
    pending, codes = enroll(client, user, clock)
    assert len(codes) == len(set(codes)) == 12
    assert all(len(code.replace("-", "")) == 24 for code in codes)
    uri = pyotp.parse_uri(pending["otpauth_uri"])
    assert uri.issuer == "Atlas" and uri.name == user[0].email and uri.secret == pending["manual_key"]
    state = db.get(UserMfa, user[0].id)
    assert state.pending_ciphertext is None and state.pending_id is None
    assert pending["manual_key"].encode() not in state.secret_ciphertext
    assert mfa.decrypt_seed(user[0].id, state.secret_nonce, state.secret_ciphertext) == pending["manual_key"]
    assert state.last_totp_step == int(clock[0].timestamp()) // 30
    stored = list(db.scalars(select(MfaRecoveryCode)))
    assert len(stored) == 12 and all(item.verifier not in codes for item in stored)
    status = client.get("/api/auth/mfa/status")
    assert status.json()["recovery_codes_remaining"] == 12
    assert status.headers["cache-control"] == "no-store"
    for path in ["/api/auth/mfa/status", "/api/auth/me", "/api/users"]:
        response = client.get(path)
        assert pending["manual_key"] not in response.text and os.environ["ATLAS_DATA_ENCRYPTION_KEY"] not in response.text
        assert all(code not in response.text for code in codes)
    client.cookies.clear(); client.cookies.set(COOKIE_NAME, original_cookie, path="/", domain="testserver.local")
    assert client.get("/api/auth/me").status_code == 401  # Password-only sessions revoked.


def test_enrollment_authentication_invalid_code_expiry_restart_and_cancel(db, user, client, clock):
    client.cookies.clear()
    assert client.post("/api/auth/mfa/enrollment", json=credentials(user)).status_code == 401
    login(client, user)
    first = client.post("/api/auth/mfa/enrollment", json=credentials(user)).json()
    second = client.post("/api/auth/mfa/enrollment", json=credentials(user)).json()
    assert first["manual_key"] != second["manual_key"]
    assert client.post("/api/auth/mfa/enrollment/confirm", json={"enrollment_id": first["enrollment_id"], "code": pyotp.TOTP(first["manual_key"]).at(clock[0])}).status_code == 409
    assert client.post("/api/auth/mfa/enrollment/confirm", json={"enrollment_id": second["enrollment_id"], "code": "wrong"}).status_code == 400
    assert user[0].mfa_enabled is False
    assert login(client, user).json()["mfa_required"] is False  # Pending never changes login.
    clock[0] += timedelta(minutes=11)
    assert client.post("/api/auth/mfa/enrollment/confirm", json={"enrollment_id": second["enrollment_id"], "code": pyotp.TOTP(second["manual_key"]).at(clock[0])}).status_code == 409
    assert db.get(UserMfa, user[0].id).pending_ciphertext is None
    client.post("/api/auth/mfa/enrollment", json=credentials(user))
    assert client.delete("/api/auth/mfa/enrollment").status_code == 204
    assert db.get(UserMfa, user[0].id).pending_ciphertext is None


def test_confirmation_attempt_bound_and_transaction_rollback(db, user, client, clock):
    pending = client.post("/api/auth/mfa/enrollment", json=credentials(user)).json()
    for _ in range(5):
        assert client.post("/api/auth/mfa/enrollment/confirm", json={"enrollment_id": pending["enrollment_id"], "code": "wrong"}).status_code == 400
    assert db.get(UserMfa, user[0].id).pending_ciphertext is None
    pending = client.post("/api/auth/mfa/enrollment", json=credentials(user)).json()
    code = pyotp.TOTP(pending["manual_key"]).at(clock[0])
    with pytest.raises(RuntimeError):
        with db.begin_nested():
            locked = mfa.locked_user(db, user[0].id)
            mfa.confirm_enrollment(db, locked, uuid.UUID(pending["enrollment_id"]), code)
            db.flush()
            raise RuntimeError("Simulated persistence failure")
    db.expire_all()
    assert db.get(User, user[0].id).mfa_enabled is False
    assert db.scalar(select(func.count()).select_from(MfaRecoveryCode)) == 0
    assert client.post("/api/auth/mfa/enrollment/confirm", json={"enrollment_id": pending["enrollment_id"], "code": code}).status_code == 200


def test_two_stage_login_replay_challenge_purpose_revocation_and_next_step(db, user, client, clock):
    pending, _ = enroll(client, user, clock)
    client.cookies.clear()
    assert login(client, user).json() == {"user": None, "mfa_required": True}
    assert COOKIE_NAME not in client.cookies
    assert client.get("/api/auth/me").status_code == 401
    token = client.cookies[mfa.MFA_COOKIE]
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 401
    assert client.post("/api/auth/mfa/verify", json={"code": pyotp.TOTP(pending["manual_key"]).at(clock[0])}).status_code == 400
    response = client.post("/api/auth/mfa/verify", json={"code": next_code(pending, clock)})
    assert response.status_code == 200 and response.json()["user"]["id"] == str(user[0].id)
    assert mfa.MFA_COOKIE not in client.cookies and client.get("/api/auth/me").status_code == 200
    client.cookies.set(mfa.MFA_COOKIE, token, path=mfa.MFA_COOKIE_PATH, domain="testserver.local")
    assert client.post("/api/auth/mfa/verify", json={"code": next_code(pending, clock)}).status_code == 401
    login(client, user)
    assert client.post("/api/auth/mfa/verify", json={"code": pyotp.TOTP(pending["manual_key"]).at(clock[0] - timedelta(seconds=60))}).status_code == 400
    assert client.post("/api/auth/mfa/verify", json={"code": pyotp.TOTP(pending["manual_key"]).at(clock[0])}).status_code == 200


@pytest.mark.parametrize("expiry", ["database", "token"])
def test_expired_challenge(db, user, client, clock, expiry):
    pending, _ = enroll(client, user, clock)
    login(client, user)
    if expiry == "database":
        clock[0] += timedelta(minutes=6)
    else:
        claims = jwt.decode(client.cookies[mfa.MFA_COOKIE], _secret_key(), algorithms=["HS256"], audience=mfa.MFA_AUDIENCE)
        claims["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        client.cookies.set(mfa.MFA_COOKIE, jwt.encode(claims, _secret_key(), algorithm="HS256"), path=mfa.MFA_COOKIE_PATH, domain="testserver.local")
    assert client.post("/api/auth/mfa/verify", json={"code": next_code(pending, clock)}).status_code == 401
    assert COOKIE_NAME not in client.cookies


def test_recovery_consumption_remaining_single_use_and_audit(db, user, client, clock):
    pending, codes = enroll(client, user, clock)
    login(client, user)
    assert client.post("/api/auth/mfa/verify", json={"code": codes[0].lower().replace("-", " "), "method": "recovery"}).status_code == 200
    assert client.get("/api/auth/mfa/status").json()["recovery_codes_remaining"] == 11
    login(client, user)
    assert client.post("/api/auth/mfa/verify", json={"code": codes[0], "method": "recovery"}).status_code == 400
    assert client.post("/api/auth/mfa/verify", json={"code": codes[1], "method": "recovery"}).status_code == 200
    events = list(db.scalars(select(AuditEvent).where(AuditEvent.event_type.like("auth.mfa%"))))
    assert any(event.event_type == "auth.mfa_recovery_used" for event in events)
    for event in events:
        assert pending["manual_key"] not in str(event.metadata_)
        assert all(code not in str(event.metadata_) for code in codes)


def test_verification_attempt_bounds_and_new_attempt_invalidates_previous(db, user, client, clock):
    enroll(client, user, clock)
    login(client, user)
    old = client.cookies[mfa.MFA_COOKIE]
    login(client, user)
    newest = client.cookies[mfa.MFA_COOKIE]
    client.cookies.set(mfa.MFA_COOKIE, old, path=mfa.MFA_COOKIE_PATH, domain="testserver.local")
    assert client.post("/api/auth/mfa/verify", json={"code": "wrong"}).status_code == 401
    client.cookies.set(mfa.MFA_COOKIE, newest, path=mfa.MFA_COOKIE_PATH, domain="testserver.local")
    for _ in range(5):
        assert client.post("/api/auth/mfa/verify", json={"code": "wrong"}).status_code == 400
    assert client.post("/api/auth/mfa/verify", json={"code": "wrong"}).status_code == 401
    assert login(client, user).status_code == 429
    clock[0] += timedelta(minutes=16)
    assert login(client, user).status_code == 200


def test_regeneration_password_and_totp_only_old_codes_invalid(db, user, client, clock):
    pending, codes = enroll(client, user, clock)
    endpoint = "/api/auth/mfa/recovery-codes"
    assert client.post(endpoint, json={"current_password": "wrong", "code": next_code(pending, clock)}).status_code == 400
    assert client.post(endpoint, json=credentials(user, code=codes[0], method="recovery")).status_code == 400
    assert client.post(endpoint, json=credentials(user, code="wrong")).status_code == 400
    new_codes = client.post(endpoint, json=credentials(user, code=next_code(pending, clock))).json()["recovery_codes"]
    assert len(new_codes) == 12 and set(codes).isdisjoint(new_codes)
    login(client, user)
    assert client.post("/api/auth/mfa/verify", json={"code": codes[1], "method": "recovery"}).status_code == 400
    assert client.post("/api/auth/mfa/verify", json={"code": new_codes[0], "method": "recovery"}).status_code == 200


def test_replace_preserves_existing_factor_and_retires_old_on_confirmation(db, user, client, clock):
    pending, old_codes = enroll(client, user, clock)
    replacement = client.post("/api/auth/mfa/enrollment", json=credentials(user, code=next_code(pending, clock))).json()
    state = db.get(UserMfa, user[0].id)
    assert mfa.decrypt_seed(user[0].id, state.secret_nonce, state.secret_ciphertext) == pending["manual_key"]
    login(client, user)
    assert client.post("/api/auth/mfa/verify", json={"code": next_code(pending, clock)}).status_code == 200
    assert client.post("/api/auth/mfa/enrollment/confirm", json={"enrollment_id": replacement["enrollment_id"], "code": pyotp.TOTP(replacement["manual_key"]).at(clock[0])}).status_code == 200
    assert mfa.decrypt_seed(user[0].id, state.secret_nonce, state.secret_ciphertext) == replacement["manual_key"]
    login(client, user)
    assert client.post("/api/auth/mfa/verify", json={"code": old_codes[0], "method": "recovery"}).status_code == 400
    assert client.post("/api/auth/mfa/verify", json={"code": next_code(pending, clock)}).status_code == 400
    assert client.post("/api/auth/mfa/verify", json={"code": pyotp.TOTP(replacement["manual_key"]).at(clock[0])}).status_code == 200


def test_disable_requires_password_and_factor_cleans_all_and_keeps_current_session(db, user, client, clock):
    pending, codes = enroll(client, user, clock)
    endpoint = "/api/auth/mfa/disable"
    assert client.post(endpoint, json={"current_password": "wrong", "code": codes[0], "method": "recovery"}).status_code == 400
    assert client.post(endpoint, json=credentials(user, code="wrong")).status_code == 400
    assert client.post(endpoint, json=credentials(user, code=codes[0], method="recovery")).status_code == 204
    assert db.get(UserMfa, user[0].id) is None
    assert db.scalar(select(func.count()).select_from(MfaRecoveryCode)) == 0
    assert db.get(MfaChallenge, user[0].id) is None
    assert client.get("/api/auth/me").status_code == 200
    assert login(client, user).json()["mfa_required"] is False


def test_admin_reset_master_only_self_guard_and_sessions(db, user, client, clock):
    pending, _ = enroll(client, user, clock)
    assert client.post(f"/api/users/{user[0].id}/reset-mfa").status_code == 403
    master = _ensure_rbac(db)
    admin = User(email="other@example.com", display_name="Other master", password_hash=hash_password(secrets.token_urlsafe(24)))
    db.add(admin); db.flush()
    assignment = AccessAssignment(user_id=admin.id, role_id=master.id, scope_type="global")
    db.add(assignment); db.commit()
    session = client.cookies[COOKIE_NAME]
    login(client, user)
    challenge = client.cookies[mfa.MFA_COOKIE]
    client.cookies.clear(); client.cookies.set(COOKIE_NAME, create_session_token(admin), path="/", domain="testserver.local")
    listing = client.get("/api/users")
    assert listing.status_code == 200 and any(record["mfa_enabled"] for record in listing.json())
    assert pending["manual_key"] not in listing.text
    # Remove authorization entirely to prove a normal account cannot reset.
    db.delete(assignment); db.commit()
    assert client.post(f"/api/users/{user[0].id}/reset-mfa").status_code == 403
    role = Role(name="H2 delegated editor", system_defined=False, active=True)
    db.add(role); db.flush()
    permission = db.scalar(select(Permission).where(Permission.key == "users.edit"))
    db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    editor_assignment = AccessAssignment(user_id=admin.id, role_id=role.id, scope_type="global")
    db.add(editor_assignment); db.commit()
    # Even globally granted users.edit cannot bypass the protected Master boundary.
    assert client.post(f"/api/users/{user[0].id}/reset-mfa").status_code == 403
    db.add(AccessAssignment(user_id=admin.id, role_id=master.id, scope_type="global")); db.commit()
    assert client.post(f"/api/users/{user[0].id}/reset-mfa").status_code == 200
    client.cookies.clear(); client.cookies.set(COOKIE_NAME, session, path="/", domain="testserver.local")
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set(mfa.MFA_COOKIE, challenge, path=mfa.MFA_COOKIE_PATH, domain="testserver.local")
    assert client.post("/api/auth/mfa/verify", json={"code": next_code(pending, clock)}).status_code == 401
    assert user[0].mfa_enabled is False
    event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "auth.mfa_admin_reset"))
    assert event.user_id == admin.id and event.target_id == user[0].id


def test_local_break_glass_confirmation_reset_password_preserved(db, user, client, clock, monkeypatch, capsys):
    from scripts import mfa as command
    _, codes = enroll(client, user, clock)
    login(client, user)
    original_hash = user[0].password_hash
    monkeypatch.setattr(command, "SessionLocal", sessionmaker(bind=db.get_bind(), join_transaction_mode="create_savepoint", autoflush=False, expire_on_commit=False))
    monkeypatch.setattr(sys, "argv", ["mfa", "reset", "--user", user[0].email.upper()])
    monkeypatch.setattr("builtins.input", lambda _: "no")
    with pytest.raises(SystemExit, match="cancelled"):
        command.main()
    db.expire_all(); assert user[0].mfa_enabled is True
    monkeypatch.setattr("builtins.input", lambda _: "RESET")
    command.main()
    output = capsys.readouterr().out
    assert "Password unchanged" in output and all(code not in output for code in codes)
    db.expire_all()
    assert user[0].password_hash == original_hash and user[0].mfa_enabled is False
    assert db.get(UserMfa, user[0].id) is None and db.get(MfaChallenge, user[0].id) is None
    assert db.scalar(select(func.count()).select_from(MfaRecoveryCode)) == 0
    assert db.scalar(select(AuditEvent).where(AuditEvent.event_type == "auth.mfa_local_reset")) is not None
    assert login(client, user).json()["mfa_required"] is False


def test_password_change_retains_factor_invalidates_pending_and_old_challenges(db, user, client, clock):
    pending, codes = enroll(client, user, clock)
    client.post("/api/auth/mfa/enrollment", json=credentials(user, code=next_code(pending, clock)))
    replacement = secrets.token_urlsafe(24)
    assert client.post("/api/auth/change-password", json={"current_password": user[1], "new_password": replacement, "new_password_confirmation": replacement}).status_code == 200
    assert user[0].mfa_enabled is True and db.get(UserMfa, user[0].id).pending_ciphertext is None
    response = client.post("/api/auth/login", json={"email": user[0].email, "password": replacement})
    assert response.json()["mfa_required"] is True and COOKIE_NAME not in client.cookies
    assert client.post("/api/auth/mfa/verify", json={"code": codes[0], "method": "recovery"}).status_code == 200


def test_user_deletion_cascades_authentication_material(db, user, client, clock):
    enroll(client, user, clock)
    login(client, user)
    user_id = user[0].id
    db.delete(user[0]); db.commit(); db.expire_all()
    assert db.get(UserMfa, user_id) is None
    assert db.get(MfaChallenge, user_id) is None
    assert db.scalar(select(func.count()).select_from(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id)) == 0


def test_validation_origin_and_information_disclosure(db, user, client, clock):
    pending, codes = enroll(client, user, clock)
    for path, data in [("/api/auth/mfa/verify", {"code": codes[0] * 10}),
                       ("/api/auth/mfa/enrollment", {"current_password": user[1], "code": {"raw": codes[0]}}),
                       ("/api/auth/mfa/enrollment/confirm", {"enrollment_id": pending["manual_key"], "code": codes[0]}),
                       ("/api/auth/login", {"email": user[1], "password": codes[0]})]:
        response = client.post(path, json=data)
        assert response.status_code == 422
        assert all(value not in response.text for value in [user[1], codes[0], pending["manual_key"]])
        assert response.headers["cache-control"] == "no-store"
    assert client.post("/api/auth/mfa/disable", headers={"Origin": "https://attacker.example"}, json=credentials(user, code=codes[0], method="recovery")).status_code == 403
    before = client.post("/api/auth/login", json={"email": user[0].email, "password": "wrong"})
    missing = client.post("/api/auth/login", json={"email": "unknown@example.com", "password": "wrong"})
    assert before.status_code == missing.status_code == 401 and before.json() == missing.json()
    assert "mfa" not in before.text.lower()


@pytest.mark.parametrize("scheme,secure", [("http", False), ("https", True)])
def test_mfa_cookie_uses_h1_effective_scheme(db, user, client, clock, monkeypatch, scheme, secure):
    enroll(client, user, clock)
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "auto")
    upstream = ProxyHeadersMiddleware(app, trusted_hosts=["172.20.0.2"])
    with TestClient(upstream, base_url=f"{scheme}://atlas.test", client=("172.20.0.2", 1234)) as browser:
        response = browser.post("/api/auth/login", json={"email": user[0].email, "password": user[1]}, headers={"X-Forwarded-Proto": scheme, "Origin": f"{scheme}://atlas.test"})
        cookie = next(value for value in response.headers.get_list("set-cookie") if value.startswith(mfa.MFA_COOKIE + "="))
        assert ("Secure" in cookie) is secure
        assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/api/auth/mfa" in cookie


@pytest.mark.parametrize("operation", ["confirmation", "totp", "recovery", "challenge"])
def test_real_concurrent_transactions_accept_one(engine, monkeypatch, operation):
    """Separate connections plus row locks prove actual PostgreSQL serialization."""
    monkeypatch.setenv("AUTH_SECRET_KEY", secrets.token_hex(48))
    monkeypatch.setenv("ATLAS_DATA_ENCRYPTION_KEY", secrets.token_hex(32))
    instant = datetime.now(timezone.utc)
    monkeypatch.setattr(mfa, "now", lambda: instant)
    class ClockMeta(type):
        def __instancecheck__(cls, value):
            return isinstance(value, datetime)
    class JwtClock(datetime, metaclass=ClockMeta):
        @classmethod
        def now(cls, tz=None):
            return instant
    monkeypatch.setattr(jwt.api_jwt, "datetime", JwtClock)
    monkeypatch.setattr(auth_module, "datetime", JwtClock)
    schema = "h2_race_" + secrets.token_hex(8)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"}, hide_parameters=True)
    try:
        Base.metadata.create_all(scoped)
        with Session(scoped) as db:
            password = secrets.token_urlsafe(24)
            user = User(email="race@example.com", display_name="Race", password_hash=hash_password(password))
            db.add(user); db.flush()
            user_id = user.id
            pending = mfa.begin_enrollment(db, user, password, None, "totp")
            db.commit()
            code = pyotp.TOTP(pending["manual_key"]).at(instant)
            if operation != "confirmation":
                mfa.locked_user(db, user_id)
                codes = mfa.confirm_enrollment(db, user, pending["enrollment_id"], code)
                db.commit()
                instant += timedelta(seconds=30)
                code = codes[0] if operation == "recovery" else pyotp.TOTP(pending["manual_key"]).at(instant)
                mfa.locked_user(db, user_id)
                challenge = mfa.create_challenge(db, user)
                db.commit()
        barrier = threading.Barrier(2)
        def verify():
            with Session(scoped) as db:
                barrier.wait(timeout=10)
                try:
                    if operation == "challenge":
                        mfa.complete_challenge(db, challenge, code, "totp")
                    else:
                        user = mfa.locked_user(db, user_id)
                        if operation == "confirmation":
                            mfa.confirm_enrollment(db, user, pending["enrollment_id"], code)
                        else:
                            mfa.verify_factor(db, user, mfa.state_for(db, user), code, operation)
                    db.commit()
                    return "accepted"
                except HTTPException as exc:
                    db.rollback()
                    return str(exc.status_code)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = [future.result(timeout=30) for future in [pool.submit(verify), pool.submit(verify)]]
        rejected = {"confirmation": "409", "totp": "400", "recovery": "400", "challenge": "401"}[operation]
        assert sorted(outcomes) == [rejected, "accepted"]
        with Session(scoped) as db:
            assert db.scalar(select(func.count()).select_from(UserMfa)) == 1
            assert db.scalar(select(func.count()).select_from(MfaRecoveryCode)) == 12
            if operation == "recovery":
                assert db.scalar(select(func.count()).select_from(MfaRecoveryCode).where(MfaRecoveryCode.consumed_at.is_not(None))) == 1
            if operation == "challenge":
                assert db.get(MfaChallenge, user_id) is None
    finally:
        scoped.dispose()
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
