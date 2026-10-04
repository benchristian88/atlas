"""Atlas format v1: fixed authenticated envelope and a tiny, uncompressed frame.

There is no general-purpose archive extraction or attacker-selected filesystem
name. Passphrases remain in memory. Source key material is encrypted in the
portable archive and exists briefly in the private authenticated staging frame.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
import struct
from typing import Literal
import uuid

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from pydantic import BaseModel, ConfigDict, Field, ValidationError

MAGIC = b"ATLASBKP"
FORMAT_VERSION = 1
HEADER = struct.Struct(">8sBBBBIII16s12sQ")
KDF_MEMORY_KIB, KDF_ITERATIONS, KDF_LANES = 65536, 3, 1
CHUNK = 1024 * 1024
MAX_ARCHIVE_BYTES = 2 * 1024**3
MAX_MANIFEST_BYTES = 16 * 1024
TAG_BYTES = 16


class BackupError(Exception):
    """Only fixed, credential-safe messages may cross the service boundary."""


class Component(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    size: int = Field(ge=0, le=MAX_ARCHIVE_BYTES)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    format_version: Literal[1] = 1
    payload_version: Literal[1] = 1
    backup_id: uuid.UUID
    created_at: datetime
    atlas_version: str = Field(min_length=1, max_length=100)
    release_channel: str = Field(min_length=1, max_length=100)
    build_id: str | None = Field(max_length=255)
    source_install_method: Literal["docker_compose", "systemd", "development"]
    source_revision: str = Field(pattern=r"^[a-zA-Z0-9_]{1,64}$")
    postgres_major: int = Field(ge=14, le=100, strict=True)
    data_key_version: Literal[1] = 1
    components: dict[str, Component]


@dataclass(repr=False)
class OpenedBackup:
    manifest: Manifest
    source_key: bytes
    dump: Path


def validate_passphrase(passphrase: str) -> None:
    if not isinstance(passphrase, str) or not 12 <= len(passphrase) <= 1024:
        raise BackupError("Use a backup passphrase of 12–1024 characters.")


def derive_key(passphrase: str, salt: bytes) -> bytes:
    validate_passphrase(passphrase)
    return hash_secret_raw(passphrase.encode("utf-8"), salt,
                           time_cost=KDF_ITERATIONS, memory_cost=KDF_MEMORY_KIB,
                           parallelism=KDF_LANES, hash_len=32, type=Type.ID, version=19)


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def encrypt_archive(dump: Path, destination: Path, passphrase: str,
                    source_key: bytes, metadata: dict) -> Manifest:
    if len(source_key) != 32:
        raise BackupError("Application data encryption is not configured.")
    manifest = Manifest(**metadata, components={
        "database.dump": Component(size=dump.stat().st_size, sha256=digest_file(dump)),
        "crypto/data-encryption-material": Component(size=32, sha256=hashlib.sha256(source_key).hexdigest()),
    })
    encoded = manifest.model_dump_json().encode("utf-8")
    size = 4 + len(encoded) + 32 + dump.stat().st_size
    if len(encoded) > MAX_MANIFEST_BYTES or size + HEADER.size + TAG_BYTES > MAX_ARCHIVE_BYTES:
        raise BackupError("The backup exceeds the 2 GiB archive limit.")
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    envelope = HEADER.pack(MAGIC, 1, 1, 1, 0, KDF_MEMORY_KIB, KDF_ITERATIONS,
                           KDF_LANES, salt, nonce, size)
    encryptor = Cipher(algorithms.AES(derive_key(passphrase, salt)), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(envelope)
    try:
        with destination.open("xb") as output, dump.open("rb") as source:
            destination.chmod(0o600)
            output.write(envelope)
            output.write(encryptor.update(struct.pack(">I", len(encoded)) + encoded + source_key))
            for chunk in iter(lambda: source.read(CHUNK), b""):
                output.write(encryptor.update(chunk))
            output.write(encryptor.finalize())
            output.write(encryptor.tag)
            output.flush()
            os.fsync(output.fileno())
        directory_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return manifest


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def decrypt_archive(archive: Path, work: Path, passphrase: str) -> OpenedBackup:
    """Authenticate completely before returning any usable restore components."""
    payload, dump = work / "payload", work / "database.dump"
    try:
        length = archive.stat().st_size
        if not HEADER.size + TAG_BYTES < length <= MAX_ARCHIVE_BYTES:
            raise BackupError("Incorrect passphrase or invalid backup.")
        with archive.open("rb") as source:
            envelope = source.read(HEADER.size)
            magic, version, kdf, cipher, reserved, memory, iterations, lanes, salt, nonce, size = HEADER.unpack(envelope)
            if magic != MAGIC:
                raise BackupError("Incorrect passphrase or invalid backup.")
            if version != FORMAT_VERSION:
                raise BackupError("Backup format is not supported by this Atlas version.")
            # V1 supports exactly this bounded suite. No attacker-selected work
            # factors, key sizes or algorithms are passed into crypto libraries.
            if (kdf, cipher, reserved, memory, iterations, lanes) != (1, 1, 0, KDF_MEMORY_KIB, KDF_ITERATIONS, KDF_LANES):
                raise BackupError("Backup encryption parameters are not supported.")
            if size < 36 or size + HEADER.size + TAG_BYTES != length:
                raise BackupError("Incorrect passphrase or invalid backup.")
            source.seek(-TAG_BYTES, 2)
            tag = source.read(TAG_BYTES)
            source.seek(HEADER.size)
            decryptor = Cipher(algorithms.AES(derive_key(passphrase, salt)), modes.GCM(nonce, tag)).decryptor()
            decryptor.authenticate_additional_data(envelope)
            with payload.open("xb") as output:
                payload.chmod(0o600)
                remaining = size
                while remaining:
                    chunk = source.read(min(CHUNK, remaining))
                    if not chunk:
                        raise BackupError("Incorrect passphrase or invalid backup.")
                    remaining -= len(chunk)
                    output.write(decryptor.update(chunk))
                output.write(decryptor.finalize())
        with payload.open("rb") as source:
            manifest_size = struct.unpack(">I", source.read(4))[0]
            if not 1 <= manifest_size <= MAX_MANIFEST_BYTES:
                raise BackupError("Backup manifest is invalid.")
            raw = json.loads(source.read(manifest_size), object_pairs_hook=_unique_json)
            manifest = Manifest.model_validate(raw)
            if manifest.created_at.tzinfo is None or set(manifest.components) != {"database.dump", "crypto/data-encryption-material"}:
                raise BackupError("Backup manifest is invalid.")
            key_info = manifest.components["crypto/data-encryption-material"]
            dump_info = manifest.components["database.dump"]
            if key_info.size != 32 or size != 4 + manifest_size + 32 + dump_info.size:
                raise BackupError("Backup component lengths are invalid.")
            key = source.read(32)
            if hashlib.sha256(key).hexdigest() != key_info.sha256:
                raise BackupError("Backup is corrupted.")
            digest = hashlib.sha256()
            with dump.open("xb") as output:
                dump.chmod(0o600)
                for chunk in iter(lambda: source.read(CHUNK), b""):
                    digest.update(chunk)
                    output.write(chunk)
            if digest.hexdigest() != dump_info.sha256:
                raise BackupError("Backup is corrupted.")
        return OpenedBackup(manifest, key, dump)
    except BackupError:
        dump.unlink(missing_ok=True)
        raise
    except (InvalidTag, ValueError, UnicodeError, ValidationError, struct.error, TypeError, KeyError):
        dump.unlink(missing_ok=True)
        raise BackupError("Incorrect passphrase or invalid backup.") from None
    finally:
        payload.unlink(missing_ok=True)
