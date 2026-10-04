"""Bounded PostgreSQL-native snapshot/restore; deployment credentials stay local."""
from datetime import datetime, timezone
import os
import re
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.release import build_metadata
from app.services.backup_archive import BackupError, MAX_ARCHIVE_BYTES

API_ROOT = Path(__file__).resolve().parents[2]
COMMAND_SECONDS = 30 * 60


def migration_config() -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    return config


def supported_revision(revision: str) -> str:
    script = ScriptDirectory.from_config(migration_config())
    head = script.get_current_head()
    # H1 singleton setup/session semantics are the minimum portable state.
    ancestors = [item.revision for item in script.walk_revisions(base="20261004_0025", head=head)]
    if revision not in ancestors:
        raise BackupError("Backup database schema is newer or unsupported by this Atlas version.")
    return head


class PostgresBackup:
    def __init__(self, engine):
        self.engine = engine
        url = make_url(engine.url)
        if url.get_backend_name() != "postgresql":
            raise BackupError("Atlas backup requires PostgreSQL.")
        # Do not inherit PGOPTIONS/PGSERVICE/passwords from the invoking shell.
        self.environment = {key: value for key, value in os.environ.items()
                            if key in {"PATH", "LANG", "LC_ALL", "SYSTEMROOT"}}
        self.environment.update({
            "PGHOST": url.host or "localhost", "PGPORT": str(url.port or 5432),
            "PGUSER": url.username or "atlas", "PGDATABASE": url.database or "atlas",
            "PGPASSWORD": url.password or "", "PGCONNECT_TIMEOUT": "10",
        })
        for key, value in url.query.items():
            if key not in {"sslmode", "sslrootcert", "sslcert", "sslkey", "sslcrl"} or not isinstance(value, str):
                raise BackupError("PostgreSQL backup connection configuration is unsupported.")
            self.environment["PG" + key.upper()] = value

    def run(self, arguments: list[str], *, output: Path | None = None,
            watched: Path | None = None):
        # No shell, connection URI, password or user-submitted argument. Error
        # output can contain source data; it is deliberately not logged/returned.
        try:
            with output.open("xb") if output else open(os.devnull, "wb") as stream:
                if output:
                    output.chmod(0o600)
                process = subprocess.Popen(arguments, env=self.environment,
                                           stdin=subprocess.DEVNULL, stdout=stream,
                                           stderr=subprocess.DEVNULL)
                deadline = time.monotonic() + COMMAND_SECONDS
                try:
                    while process.poll() is None:
                        if time.monotonic() > deadline or (watched and watched.exists() and watched.stat().st_size > MAX_ARCHIVE_BYTES):
                            raise BackupError("PostgreSQL backup operation exceeded its time or size limit.")
                        if output and output.stat().st_size > 1024 * 1024:
                            raise BackupError("PostgreSQL backup metadata exceeds its limit.")
                        time.sleep(0.05)
                    if process.returncode:
                        raise BackupError("PostgreSQL backup operation failed. Check local database health and client compatibility.")
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
        except (OSError, subprocess.SubprocessError):
            raise BackupError("PostgreSQL backup tools are unavailable. Check the local installation.") from None

    def prerequisites(self) -> int:
        for executable in ("pg_dump", "pg_restore"):
            if shutil.which(executable, path=self.environment.get("PATH")) is None:
                raise BackupError("PostgreSQL backup tools are unavailable. Check the local installation.")
        with self.engine.connect() as connection:
            major = int(connection.scalar(text("SHOW server_version_num"))) // 10000
            schema_owner = connection.scalar(text("SELECT pg_get_userbyid(nspowner) = current_user FROM pg_namespace WHERE nspname = 'public'"))
            database_owner = connection.scalar(text("SELECT pg_get_userbyid(datdba) = current_user FROM pg_database WHERE datname = current_database()"))
            can_create_schema = connection.scalar(text("SELECT has_database_privilege(current_user, current_database(), 'CREATE')"))
            if (not schema_owner and not database_owner) or not can_create_schema:
                raise BackupError("The Atlas role must own its database or application schema and be able to recreate that schema.")
        try:
            client_majors = []
            for executable in ("pg_dump", "pg_restore"):
                version = subprocess.run([executable, "--version"], env=self.environment,
                                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                         timeout=10, check=True).stdout.decode("ascii")
                client_majors.append(int(version.split()[2].split(".")[0]))
        except (ValueError, IndexError, OSError, subprocess.SubprocessError):
            raise BackupError("PostgreSQL client version could not be checked.") from None
        if any(client != major for client in client_majors) or major not in {16, 17}:
            raise BackupError("Atlas backup/restore requires PostgreSQL 16 or 17 and client tools matching the target server major version.")
        return major

    def dump(self, destination: Path) -> dict:
        major = self.prerequisites()
        # Metadata and pg_dump refer to the identical exported MVCC snapshot.
        with self.engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
                supported_revision(revision)
                snapshot = connection.scalar(text("SELECT pg_export_snapshot()"))
                self.run(["pg_dump", "--format=custom", "--compress=0", "--no-owner",
                          "--no-privileges", "--snapshot", snapshot, "--file", str(destination)], watched=destination)
        destination.chmod(0o600)
        metadata = build_metadata()
        return {
            "backup_id": uuid.uuid4(), "created_at": datetime.now(timezone.utc),
            "atlas_version": metadata["version"], "release_channel": metadata["release_channel"],
            "build_id": metadata["build_id"], "source_install_method": metadata["install_method"],
            "source_revision": revision, "postgres_major": major,
        }

    def validate_dump(self, dump: Path, revision: str | None = None):
        with dump.open("rb") as stream:
            header = stream.read(12)
        # PostgreSQL custom archive 1.15/1.16 stores compression algorithm in
        # byte 11 (NONE=0). H3 never creates a compressed dump; reject compressed
        # or unknown encodings before pg_restore can expand untrusted data.
        if len(header) < 12 or header[:5] != b"PGDMP" or header[5:7] not in {b"\x01\x0f", b"\x01\x10"} or header[10] != 1 or header[11] != 0:
            raise BackupError("Backup PostgreSQL dump is invalid or unsupported.")
        listing = dump.parent / "dump-list"
        try:
            self.run(["pg_restore", "--list", str(dump)], output=listing)
            content = listing.read_text()
            if "TABLE public alembic_version " not in content or "TABLE public users " not in content:
                raise BackupError("Backup does not contain initialized Atlas state.")
        finally:
            listing.unlink(missing_ok=True)
        if revision is not None:
            revision_data = dump.parent / "dump-revision"
            try:
                self.run(["pg_restore", "--data-only", "--table=alembic_version", "--no-owner",
                          "--no-privileges", "--file=-", str(dump)], output=revision_data)
                rows = re.findall(r"COPY public\.alembic_version \(version_num\) FROM stdin;\n([a-zA-Z0-9_]+)\n\\\.\n", revision_data.read_text())
                if rows != [revision]:
                    raise BackupError("Backup database schema does not match its manifest.")
            finally:
                revision_data.unlink(missing_ok=True)

    def replace(self, dump: Path):
        self.engine.dispose()
        # --clean alone cannot remove tables introduced AFTER an older backup.
        # Reset the owned application schema under quiescence, then use native
        # transactional pg_restore. The encrypted rollback snapshot protects
        # the wider migrate/rewrap workflow; it is not claimed to be atomic.
        with self.engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout = '60s'"))
            connection.execute(text("SET LOCAL statement_timeout = '120s'"))
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
        self.run(["pg_restore", "--format=custom", "--single-transaction", "--exit-on-error",
                  "--clean", "--if-exists", "--no-owner", "--no-privileges",
                  "--dbname", self.environment["PGDATABASE"], str(dump)])
        self.engine.dispose()
