"""Installation-local signing; this credential never represents an Atlas user."""
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import secrets
import stat
import uuid

import jwt

from app.services.backup_runtime import state_directory

AUDIENCE = "atlas-integration-ingest"
ISSUER = "atlas-discovery"
MAX_DURATION = 15 * 60


class IngestionAuthenticationError(ValueError):
    def __init__(self):
        super().__init__("Invalid discovery ingestion credential")


def key_path():
    return state_directory() / "discovery-ingestion.secret"


def signing_key():
    """Read an automatically provisioned private file, never an auth/data key."""
    try:
        path = key_path()
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as source:
            info = os.fstat(source.fileno())
            raw = source.read(98)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
                    or not re.fullmatch(rb"[a-f0-9]{96}\n", raw)):
                raise ValueError
        return bytes.fromhex(raw.decode().strip())
    except (OSError, ValueError):
        raise IngestionAuthenticationError() from None


def provision_signing_key():
    """API install/startup only. Existing invalid material is never replaced."""
    path = key_path()
    if path.exists() or path.is_symlink():
        return signing_key()
    temporary = path.parent / ("signing-" + secrets.token_hex(16))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write((secrets.token_hex(48) + "\n").encode())
            target.flush()
            os.fsync(target.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            pass
    finally:
        temporary.unlink(missing_ok=True)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return signing_key()


def mint(run):
    now = datetime.now(timezone.utc)
    if (run.status not in {"pending", "running"} or run.cancellation_requested_at
            or not run.ingestion_generation or not run.deadline_at):
        raise IngestionAuthenticationError()
    expiry = int(run.deadline_at.timestamp())
    if not int(now.timestamp()) < expiry <= int(now.timestamp()) + MAX_DURATION:
        raise IngestionAuthenticationError()
    return jwt.encode({"iss": ISSUER, "aud": AUDIENCE, "run_id": str(run.id),
        "integration_id": str(run.integration_id), "iat": int(now.timestamp()), "exp": expiry,
        "jti": str(run.ingestion_generation)}, signing_key(), algorithm="HS256")


def decode(value):
    try:
        if not isinstance(value, str) or len(value) > 4096:
            raise ValueError
        claims = jwt.decode(value, signing_key(), algorithms=["HS256"], audience=AUDIENCE,
            issuer=ISSUER, options={"require": ["iss", "aud", "run_id", "integration_id", "iat", "exp", "jti"]})
        if set(claims) != {"iss", "aud", "run_id", "integration_id", "iat", "exp", "jti"}:
            raise ValueError
        if (claims["aud"] != AUDIENCE or type(claims["iat"]) is not int or type(claims["exp"]) is not int
                or not 0 < claims["exp"] - claims["iat"] <= MAX_DURATION):
            raise ValueError
        for name in ["run_id", "integration_id", "jti"]:
            if str(uuid.UUID(claims[name])) != claims[name]:
                raise ValueError
        return claims
    except (jwt.PyJWTError, ValueError, TypeError, KeyError, AttributeError):
        raise IngestionAuthenticationError() from None
