"""H3 crypto/parser/runtime security contracts without a live database."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import struct
import threading
import uuid

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import pytest

from app.audit import _safe_value
from app.services import backup_archive as archive, backup_runtime as runtime
from app.services.backup_archive import BackupError
from app.services.backup_postgres import supported_revision


@pytest.fixture
def bundle(tmp_path):
    dump = tmp_path / "source.dump"
    dump.write_bytes(b"PGDMP" + b"representative database plaintext" * 100)
    key, passphrase = secrets.token_bytes(32), secrets.token_urlsafe(24)
    metadata = dict(backup_id=uuid.uuid4(), created_at=datetime.now(timezone.utc),
                    atlas_version="0.1.0", release_channel="beta", build_id=None,
                    source_install_method="docker_compose", source_revision="20261004_0026", postgres_major=17)
    path = tmp_path / "archive.atlasbackup"
    manifest = archive.encrypt_archive(dump, path, passphrase, key, metadata)
    return dump, path, passphrase, key, manifest


def open_bundle(tmp_path, path, passphrase):
    work = tmp_path / str(uuid.uuid4())
    work.mkdir(mode=0o700)
    return archive.decrypt_archive(path, work, passphrase)


def frame(bundle, manifest=None, raw_json=None, dump_bytes=None):
    dump, _, _, key, original = bundle
    encoded = raw_json if raw_json is not None else json.dumps(manifest or original.model_dump(mode="json")).encode()
    return struct.pack(">I", len(encoded)) + encoded + key + (dump_bytes if dump_bytes is not None else dump.read_bytes())


def seal_frame(tmp_path, bundle, payload):
    _, _, passphrase, _, _ = bundle
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    header = archive.HEADER.pack(archive.MAGIC, 1, 1, 1, 0, 65536, 3, 1, salt, nonce, len(payload))
    encryptor = Cipher(algorithms.AES(archive.derive_key(passphrase, salt)), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(header)
    encrypted = encryptor.update(payload) + encryptor.finalize()
    path = tmp_path / (str(uuid.uuid4()) + ".atlasbackup")
    path.write_bytes(header + encrypted + encryptor.tag)
    return path


def test_format_randomness_confidentiality_roundtrip_and_manifest(bundle, tmp_path):
    dump, path, passphrase, key, manifest = bundle
    second = tmp_path / "second.atlasbackup"
    archive.encrypt_archive(dump, second, passphrase, key, manifest.model_dump(exclude={"components"}))
    first_header, second_header = (archive.HEADER.unpack(p.read_bytes()[:archive.HEADER.size]) for p in (path, second))
    assert first_header[:8] == (b"ATLASBKP", 1, 1, 1, 0, 65536, 3, 1)
    assert first_header[8] != second_header[8] and first_header[9] != second_header[9]
    assert len(first_header[8]) == 16 and len(first_header[9]) == 12
    assert dump.read_bytes() not in path.read_bytes()
    assert key not in path.read_bytes() and key.hex().encode() not in path.read_bytes()
    assert b"source_revision" not in path.read_bytes() and b"docker_compose" not in path.read_bytes()
    opened = open_bundle(tmp_path, path, passphrase)
    assert opened.dump.read_bytes() == dump.read_bytes()
    assert hashlib.sha256(opened.source_key).digest() == hashlib.sha256(key).digest()
    assert opened.manifest == manifest
    assert path.stat().st_mode & 0o777 == 0o600


def test_wrong_passphrase_and_ciphertext_tag_header_tampering(bundle, tmp_path):
    _, path, passphrase, _, _ = bundle
    with pytest.raises(BackupError, match="Incorrect passphrase"):
        open_bundle(tmp_path, path, secrets.token_urlsafe(24))
    for position in (40, archive.HEADER.size + 12, -1):
        data = bytearray(path.read_bytes())
        data[position] ^= 1
        corrupt = tmp_path / str(uuid.uuid4())
        corrupt.write_bytes(data)
        with pytest.raises(BackupError):
            open_bundle(tmp_path, corrupt, passphrase)
    assert not list(tmp_path.glob("*/payload")) and not list(tmp_path.glob("*/database.dump"))


@pytest.mark.parametrize("field,value", [(1, 2), (2, 99), (3, 99), (4, 1), (5, 2**32 - 1), (6, 2**32 - 1), (7, 255), (10, 2**64 - 1)])
def test_untrusted_header_is_bounded_before_kdf(bundle, tmp_path, monkeypatch, field, value):
    _, path, passphrase, _, _ = bundle
    data = path.read_bytes()
    fields = list(archive.HEADER.unpack(data[:archive.HEADER.size]))
    fields[field] = value
    bad = tmp_path / "bad"
    bad.write_bytes(archive.HEADER.pack(*fields) + data[archive.HEADER.size:])
    monkeypatch.setattr(archive, "derive_key", lambda *args: pytest.fail("Untrusted work factors reached the KDF"))
    with pytest.raises(BackupError):
        open_bundle(tmp_path, bad, passphrase)


@pytest.mark.parametrize("data", [b"", b"random binary input", secrets.token_bytes(200), b"ATLASBKP"])
def test_bad_magic_random_and_short_inputs(tmp_path, data):
    path = tmp_path / "bad"
    path.write_bytes(data)
    with pytest.raises(BackupError):
        open_bundle(tmp_path, path, secrets.token_urlsafe(24))


def test_truncation_and_extra_data(bundle, tmp_path):
    _, path, passphrase, _, _ = bundle
    for data in (path.read_bytes()[:-1], path.read_bytes() + b"extra"):
        path.write_bytes(data)
        with pytest.raises(BackupError):
            open_bundle(tmp_path, path, passphrase)


@pytest.mark.parametrize("member", ["../database.dump", "/database.dump", "unexpected", "link", "device", "database.dump/child"])
def test_allowlisted_components_no_paths_links_or_extra_members(bundle, tmp_path, member):
    manifest = bundle[-1].model_dump(mode="json")
    manifest["components"][member] = manifest["components"]["database.dump"]
    path = seal_frame(tmp_path, bundle, frame(bundle, manifest))
    with pytest.raises(BackupError):
        open_bundle(tmp_path, path, bundle[2])


@pytest.mark.parametrize("kind", ["duplicate", "malformed_json", "oversized", "checksum", "key_checksum", "size", "missing", "future_payload", "extra_metadata"])
def test_manifest_hostile_inputs_clean_decrypted_files(bundle, tmp_path, kind):
    manifest = bundle[-1].model_dump(mode="json")
    encoded = None
    if kind == "duplicate":
        encoded = json.dumps(manifest).encode().replace(b'{', b'{"format_version":1,', 1)
    elif kind == "malformed_json":
        encoded = b"not json"
    elif kind == "oversized":
        encoded = b" " * (archive.MAX_MANIFEST_BYTES + 1)
    elif kind == "checksum":
        manifest["components"]["database.dump"]["sha256"] = "0" * 64
    elif kind == "key_checksum":
        manifest["components"]["crypto/data-encryption-material"]["sha256"] = "0" * 64
    elif kind == "size":
        manifest["components"]["database.dump"]["size"] += 1
    elif kind == "missing":
        del manifest["source_revision"]
    elif kind == "future_payload":
        manifest["payload_version"] = 2
    else:
        manifest["symlink"] = "../outside"
    path = seal_frame(tmp_path, bundle, frame(bundle, manifest, encoded))
    with pytest.raises(BackupError):
        open_bundle(tmp_path, path, bundle[2])
    assert not list(tmp_path.glob("*/payload")) and not list(tmp_path.glob("*/database.dump"))


def test_schema_policy_uses_ancestry_and_minimum_h1():
    assert supported_revision("20261004_0025") == supported_revision("20261004_0026")
    for revision in ("future_revision", "20260710_0001", "20261004_9999"):
        with pytest.raises(BackupError):
            supported_revision(revision)


@pytest.fixture
def protected(tmp_path, monkeypatch):
    path = tmp_path / "private"
    monkeypatch.setenv("ATLAS_STATE_DIR", str(path))
    return runtime.state_directory()


def test_private_directories_and_symlink_refusal(protected):
    assert protected.stat().st_mode & 0o777 == 0o700
    (protected / "operation.lock").symlink_to(protected / "outside")
    with pytest.raises(OSError):
        runtime.lock_file("operation.lock", exclusive=True)
    assert not (protected / "outside").exists()


def test_atomic_metadata_replacement_keeps_open_reader_snapshot_safe(protected, monkeypatch):
    path = protected / "metadata.json"
    runtime.write_json(path, {"phase": "before"})
    opened, replaced = threading.Event(), threading.Event()
    original_fstat = os.fstat
    def fstat_after_replacement(fd):
        if threading.current_thread().name.startswith("metadata-reader"):
            opened.set()
            assert replaced.wait(2)
        return original_fstat(fd)
    monkeypatch.setattr(runtime.os, "fstat", fstat_after_replacement)
    with ThreadPoolExecutor(thread_name_prefix="metadata-reader") as pool:
        reader = pool.submit(runtime.read_json, path)
        assert opened.wait(2)
        runtime.write_json(path, {"phase": "after"})
        replaced.set()
        assert reader.result(timeout=2) == {"phase": "before"}
    assert runtime.read_json(path) == {"phase": "after"}
    (protected / "hard-link.json").hardlink_to(path)
    with pytest.raises(BackupError):
        runtime.read_json(path)


def test_operation_lock_and_drain_block_new_mutations(protected):
    fd = runtime.lock_file("operation.lock", exclusive=True)
    with pytest.raises(BackupError):
        runtime.lock_file("operation.lock", exclusive=True)
    runtime.unlock(fd)
    started, drained = threading.Event(), threading.Event()
    def restore():
        runtime.set_maintenance(str(uuid.uuid4()), "draining")
        started.set()
        exclusive = runtime.lock_file("requests.lock", exclusive=True, blocking=True)
        drained.set()
        runtime.unlock(exclusive)
    with ThreadPoolExecutor() as pool:
        with runtime.normal_operation():
            task = pool.submit(restore)
            assert started.wait(2) and not drained.is_set()
            with pytest.raises(BackupError):
                with runtime.normal_operation():
                    pytest.fail("New mutation crossed maintenance")
        task.result(timeout=2)
    assert drained.is_set()
    runtime.clear_maintenance()


def test_audit_redacts_backup_credential_names():
    values = {name: secrets.token_hex(32) for name in ("passphrase", "source_data_key", "derived_key", "password", "encryption_key")}
    assert set(_safe_value(values).values()) == {"[redacted]"}


def test_dump_failure_cleans_plaintext_and_connection_credentials_stay_off_arguments(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from app.services.backups import BackupService
    from app.services.backup_postgres import PostgresBackup
    credential = secrets.token_hex(24)
    engine = create_engine(f"postgresql+psycopg://atlas:{credential}@127.0.0.1:5432/atlas")
    postgres = PostgresBackup(engine)
    assert postgres.environment["PGPASSWORD"] == credential
    assert not any(credential in value for key, value in postgres.environment.items() if key != "PGPASSWORD")
    monkeypatch.setenv("ATLAS_DATA_ENCRYPTION_KEY", secrets.token_hex(32))
    service = BackupService(engine)
    def failed_dump(path):
        path.write_bytes(b"sensitive database content")
        raise BackupError("PostgreSQL backup operation failed.")
    monkeypatch.setattr(service.postgres, "dump", failed_dump)
    with pytest.raises(BackupError):
        service.create(tmp_path, secrets.token_urlsafe(24))
    assert list(tmp_path.iterdir()) == []
    engine.dispose()


def test_stale_cleanup_preserves_only_encrypted_crash_recovery(protected):
    import time
    job_id = str(uuid.uuid4())
    work = runtime.new_job_directory(job_id)
    runtime.write_json(work / "status.json", {"state": "restoring", "created_at": time.time(), "expires_at": 0})
    for name in ("database.dump", "payload", "upload.atlasbackup", "rollback.atlasbackup"):
        (work / name).write_bytes(b"temporary content")
    runtime.set_maintenance(job_id, "replacing")
    runtime.cleanup_stale()
    assert {path.name for path in work.iterdir()} == {"status.json", "rollback.atlasbackup"}
    assert runtime.maintenance()["phase"] == "replacing"
    assert runtime.job_state(job_id)["state"] == "failed"


def test_crashed_pre_destructive_drain_releases_safely(protected):
    import time
    job_id = str(uuid.uuid4())
    work = runtime.new_job_directory(job_id)
    runtime.write_json(work / "status.json", {"state": "preparing", "created_at": time.time(), "expires_at": 0})
    (work / "payload").write_bytes(b"temporary content")
    runtime.set_maintenance(job_id, "draining")
    runtime.cleanup_stale()
    assert runtime.maintenance() is None
    assert {path.name for path in work.iterdir()} == {"status.json"}
