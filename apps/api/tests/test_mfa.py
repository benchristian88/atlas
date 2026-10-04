"""Crypto/configuration contracts independent of a running database."""
import base64
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pyotp
import pytest

from app.config import data_encryption_key
from app.main import app
from app.services import mfa


def test_seed_entropy_encryption_wrong_key_nonce_and_identity(monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_ENCRYPTION_KEY", secrets.token_hex(32))
    seed = pyotp.random_base32(length=32)
    assert len(base64.b32decode(seed)) == 20
    user_id = uuid.uuid4()
    nonce, ciphertext = mfa.encrypt_seed(user_id, seed)
    assert len(nonce) == 12 and seed.encode() not in ciphertext
    assert mfa.decrypt_seed(user_id, nonce, ciphertext) == seed
    second_nonce, second_ciphertext = mfa.encrypt_seed(user_id, seed)
    assert second_nonce != nonce and second_ciphertext != ciphertext
    with pytest.raises(HTTPException):
        mfa.decrypt_seed(uuid.uuid4(), nonce, ciphertext)
    monkeypatch.setenv("ATLAS_DATA_ENCRYPTION_KEY", secrets.token_hex(32))
    with pytest.raises(HTTPException) as failure:
        mfa.decrypt_seed(user_id, nonce, ciphertext)
    assert failure.value.status_code == 503
    assert seed not in failure.value.detail


@pytest.mark.parametrize("value", ["", "short", "g" * 64, "0" * 63, "0" * 65])
def test_production_key_required_and_no_auth_fallback(monkeypatch, value):
    monkeypatch.setenv("ATLAS_INSTALL_METHOD", "docker_compose")
    monkeypatch.setenv("AUTH_SECRET_KEY", secrets.token_hex(48))
    monkeypatch.setenv("ATLAS_DATA_ENCRYPTION_KEY", value)
    with pytest.raises(RuntimeError, match="ATLAS_DATA_ENCRYPTION_KEY"):
        data_encryption_key(required=False)


def test_production_http_startup_fails_closed(monkeypatch):
    monkeypatch.setenv("ATLAS_INSTALL_METHOD", "systemd")
    monkeypatch.delenv("ATLAS_DATA_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ATLAS_DATA_ENCRYPTION_KEY"):
        with TestClient(app):
            pass


def test_development_requires_explicit_key_only_for_mfa(monkeypatch):
    monkeypatch.setenv("ATLAS_INSTALL_METHOD", "development")
    monkeypatch.delenv("ATLAS_DATA_ENCRYPTION_KEY", raising=False)
    assert data_encryption_key(required=False) is None
    with pytest.raises(RuntimeError):
        data_encryption_key()


def test_rfc6238_vector_and_skew_replay(monkeypatch):
    # Public RFC 6238 test vector, not application credential material.
    seed = base64.b32encode(b"12345678901234567890").decode()
    assert pyotp.TOTP(seed, digits=8).at(59) == "94287082"
    current = datetime.fromtimestamp(1_000_000_000, timezone.utc)
    monkeypatch.setattr(mfa, "now", lambda: current)
    step = int(current.timestamp()) // 30
    code = pyotp.TOTP(seed).at(step * 30)
    assert mfa.matching_step(seed, code, None) == step
    assert mfa.matching_step(seed, code, step) is None
    assert mfa.matching_step(seed, pyotp.TOTP(seed).at((step - 1) * 30), step) is None
    assert mfa.matching_step(seed, pyotp.TOTP(seed).at((step + 2) * 30), None) is None
    assert mfa.matching_step(seed, "１２３４５６", None) is None


def test_recovery_verifier_is_one_way_and_account_bound():
    code = secrets.token_hex(20)
    user = uuid.uuid4()
    digest = mfa.recovery_verifier(user, code)
    assert len(digest) == 64 and digest != code
    assert mfa.recovery_verifier(user, code.upper()) == digest
    assert mfa.recovery_verifier(uuid.uuid4(), code) != digest
