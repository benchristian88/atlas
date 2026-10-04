"""Explicit adapters for every application-key-encrypted field.

Rewrapping runs inside the caller's single database transaction. Adapters may
flush but must not commit: any invalid field rolls back every adapter's writes.
"""
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select

from app.models import UserMfa
from app.services.backup_archive import BackupError


def rewrap_mfa(db, source_key: bytes, target_key: bytes) -> int:
    count = 0
    # Keyset batches bound the identity map even for large installations.
    cursor = None
    while True:
        statement = select(UserMfa).order_by(UserMfa.user_id).limit(200).with_for_update()
        if cursor is not None:
            statement = statement.where(UserMfa.user_id > cursor)
        records = list(db.scalars(statement))
        if not records:
            return count
        for record in records:
            if record.encryption_version != 1:
                raise BackupError("Encrypted application data could not be restored.")
            aad = f"atlas-mfa:v1:{record.user_id}".encode()
            for field in ("secret", "pending"):
                ciphertext = getattr(record, f"{field}_ciphertext")
                nonce = getattr(record, f"{field}_nonce")
                if ciphertext is None and nonce is None:
                    continue
                try:
                    plain = AESGCM(source_key).decrypt(nonce, ciphertext, aad)
                    # H2's semantic payload is an ASCII base32 TOTP seed.
                    import base64
                    if len(base64.b32decode(plain)) != 20:
                        raise ValueError("Invalid seed")
                    fresh_nonce = secrets.token_bytes(12)
                    wrapped = AESGCM(target_key).encrypt(fresh_nonce, plain, aad)
                except (InvalidTag, ValueError, TypeError):
                    raise BackupError("Encrypted application data could not be restored.") from None
                setattr(record, f"{field}_nonce", fresh_nonce)
                setattr(record, f"{field}_ciphertext", wrapped)
                count += 1
            cursor = record.user_id
        db.flush()
        for record in records:
            db.expunge(record)


ENCRYPTED_DATA_ADAPTERS = (rewrap_mfa,)


def rewrap_application_data(db, source_key: bytes, target_key: bytes) -> int:
    if len(source_key) != 32 or len(target_key) != 32:
        raise BackupError("Encrypted application data could not be restored.")
    return sum(adapter(db, source_key, target_key) for adapter in ENCRYPTED_DATA_ADAPTERS)
