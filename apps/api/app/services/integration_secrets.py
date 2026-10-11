"""Write-only credentials using the existing application key and versioned AAD."""
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import base64
import secrets
import uuid

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import data_encryption_key
from app.models import IntegrationSecret


class SecretProviderError(ValueError):
    def __init__(self):
        super().__init__("Protected Integration credentials are unavailable")


def context(record, key):
    if ":" in key or record.encryption_version != 1:
        raise SecretProviderError()
    return f"atlas-integration-secret:v1:{record.customer_id}:{record.site_id}:{record.integration_id}:{key}:{record.id}".encode()


def encrypt_fields(record, values, key):
    result = {}
    for name, value in values.items():
        nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(key).encrypt(nonce, value.encode("utf-8"), context(record, name))
        result[name] = {"nonce": base64.b64encode(nonce).decode(), "ciphertext": base64.b64encode(ciphertext).decode()}
    return result


def decrypt_fields(record, key, names):
    try:
        if not set(names) <= record.encrypted_fields.keys():
            raise ValueError
        return {name: AESGCM(key).decrypt(base64.b64decode(record.encrypted_fields[name]["nonce"], validate=True),
                    base64.b64decode(record.encrypted_fields[name]["ciphertext"], validate=True), context(record, name)).decode("utf-8") for name in names}
    except (InvalidTag, ValueError, TypeError, KeyError, UnicodeError):
        raise SecretProviderError() from None


@dataclass(repr=False)
class JobSecretLease:
    request_id: uuid.UUID
    expires_at: datetime
    values: dict = field(repr=False)
    revoked: bool = False

    def __repr__(self):
        return "JobSecretLease(redacted)"

    def revoke(self):
        self.values.clear()
        self.revoked = True


class AtlasEncryptedSecretProvider:
    def __init__(self, db):
        self.db = db

    def record(self, integration):
        record = self.db.get(IntegrationSecret, integration.credential_reference) if integration.credential_reference else None
        if record and (record.integration_id, record.customer_id, record.site_id) != (integration.id, integration.customer_id, integration.site_id):
            raise SecretProviderError()
        return record

    def state(self, integration):
        record = self.record(integration)
        return sorted(record.encrypted_fields) if record else []

    def replace(self, integration, values):
        old = self.record(integration)
        record = IntegrationSecret(id=uuid.uuid4(), integration_id=integration.id,
            customer_id=integration.customer_id, site_id=integration.site_id, encryption_version=1)
        try:
            record.encrypted_fields = encrypt_fields(record, values, data_encryption_key())
        except (ValueError, TypeError, RuntimeError):
            raise SecretProviderError() from None
        self.db.add(record)
        self.db.flush()
        integration.credential_reference = record.id
        self.db.flush()
        if old:
            self.db.delete(old)
        self.db.flush()

    create = replace

    def delete(self, integration):
        record = self.record(integration)
        integration.credential_reference = None
        self.db.flush()
        if record:
            self.db.delete(record)
            self.db.flush()

    @contextmanager
    def materialize_for_job(self, integration, request_id, required_fields):
        record = self.record(integration)
        if record is None:
            raise SecretProviderError()
        lease = JobSecretLease(request_id, datetime.now(timezone.utc) + timedelta(seconds=30),
            decrypt_fields(record, data_encryption_key(), required_fields))
        try:
            yield lease
        finally:
            lease.revoke()
