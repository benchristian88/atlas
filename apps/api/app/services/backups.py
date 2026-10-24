"""One bounded in-process backup/restore executor, shared by API and local CLI.

Atlas's current worker is idle and has no queue. Passphrases stay only in this
process; jobs are not restartable or serialized into Redis. Target-local locks
and encrypted recovery artifacts survive crashes without becoming backup data.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import logging
import secrets
import shutil
import threading
import time
import uuid

from alembic import command
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

from app.audit import add_audit_event
from app.config import data_encryption_key
from app.models import InstallationState, MfaChallenge, SystemSetting, User, UserMfa
from app.services import backup_runtime as runtime
from app.services.backup_archive import BackupError, decrypt_archive, encrypt_archive, validate_passphrase
from app.services.backup_postgres import PostgresBackup, migration_config, supported_revision
from app.services.encrypted_data import rewrap_application_data
from app.services.installation import installation_state, require_uninitialized

RESTORE_EPOCH_KEY = "auth.restore_epoch"
logger = logging.getLogger("atlas.backup")


def restore_epoch(db: Session) -> str:
    value = db.scalar(select(SystemSetting.value_).where(SystemSetting.key == RESTORE_EPOCH_KEY))
    return str(value) if value is not None else ""


def clear_redis(*, check_only=False):
    import os
    url = os.getenv("REDIS_URL") or ("redis://127.0.0.1:6379/0" if os.getenv("ATLAS_INSTALL_METHOD") == "systemd" else None)
    if url:
        from redis import Redis
        from redis.exceptions import RedisError
        try:
            with Redis.from_url(url, socket_timeout=5, socket_connect_timeout=5) as redis:
                # Supported deployments dedicate the selected Redis database to
                # Atlas; no source Redis data is imported.
                if check_only:
                    redis.ping()
                else:
                    redis.flushdb()
        except (RedisError, ValueError):
            raise BackupError("Atlas transient cache could not be invalidated.") from None


class BackupService:
    def __init__(self, engine):
        self.engine = engine
        self.postgres = PostgresBackup(engine)

    def audit(self, action, *, actor_email=None, success=True, metadata=None):
        with Session(self.engine) as db:
            add_audit_event(db, action=action, target_type="installation",
                            actor_email=actor_email or "local-operator", success=success,
                            metadata=metadata)
            db.commit()

    def create(self, work, passphrase):
        validate_passphrase(passphrase)
        key = data_encryption_key()
        dump = work / "database.dump"
        try:
            metadata = self.postgres.dump(dump)
            encrypt_archive(dump, work / "backup.atlasbackup", passphrase, key, metadata)
        finally:
            dump.unlink(missing_ok=True)

    def preflight(self, work, passphrase):
        key = data_encryption_key()
        major = self.postgres.prerequisites()
        archive = work / "upload.atlasbackup"
        # Decryption and component copying need bounded extra disk headroom.
        if shutil.disk_usage(work).free < archive.stat().st_size * 3 + 64 * 1024**2:
            raise BackupError("Insufficient protected staging space for restore.")
        opened = decrypt_archive(archive, work, passphrase)
        supported_revision(opened.manifest.source_revision)
        if opened.manifest.postgres_major > major:
            raise BackupError("Backup requires a newer PostgreSQL server major version.")
        self.postgres.validate_dump(opened.dump, opened.manifest.source_revision)
        clear_redis(check_only=True)
        return opened, key

    def authorize_current(self, authorization):
        with Session(self.engine) as db:
            if authorization["mode"] == "local":
                # Confirmed local operator already controls the protected
                # deployment configuration, as in H1/H2 management.
                return
            if authorization["mode"] == "fresh":
                state = installation_state(db, lock=True)
                require_uninitialized(db, state)
                if state.setup_generation != authorization["generation"]:
                    raise BackupError("Setup authorization changed. Start again.")
            else:
                from app.routes.users import _has_global_master
                user = db.get(User, uuid.UUID(authorization["owner"]))
                if (user is None or not user.is_active or user.force_password_change
                    or user.session_version != authorization["session_version"]
                    or not _has_global_master(db, user.id)):
                    raise BackupError("Restore authorization changed. Sign in and start again.")

    def post_restore(self, opened, target_key, actor_email):
        config = migration_config()
        with self.engine.begin() as connection:
            actual = connection.scalar(text("SELECT version_num FROM alembic_version"))
            if actual != opened.manifest.source_revision:
                raise BackupError("Backup database schema does not match its manifest.")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            with Session(connection, autoflush=False, expire_on_commit=False) as db:
                from scripts.seed_system import seed_system
                from app.routes.users import _usable_master_count
                seed_system(db)
                if _usable_master_count(db) < 1:
                    raise BackupError("Backup does not contain a usable global Master Administrator.")
                # Detect inconsistent MFA before releasing maintenance.
                invalid = db.scalar(select(User.id).outerjoin(UserMfa, User.id == UserMfa.user_id).where(
                    User.mfa_enabled.is_(True), UserMfa.secret_ciphertext.is_(None)).limit(1))
                if invalid:
                    raise BackupError("Encrypted application data could not be restored.")
                rewrap_application_data(db, opened.source_key, target_key)
                from app.models import DiscoveryRun
                from app.services.discovery_orchestration import fail_run
                for run in db.scalars(select(DiscoveryRun).where(DiscoveryRun.execution_provenance.is_not(None),
                        DiscoveryRun.status.in_(["pending", "running"]))):
                    run.ingestion_generation = None
                    if run.status in {"pending", "running"}:
                        from app.models import Integration
                        fail_run(run, db.get(Integration, run.integration_id), "restore_interrupted")
                db.execute(update(DiscoveryRun).where(DiscoveryRun.execution_provenance.is_not(None))
                    .values(ingestion_generation=None))
                db.execute(update(User).values(session_version=User.session_version + 1))
                # Accepted immutable history survives restore; freshness and an
                # interrupted operation cannot become fresh provider authority.
                from app.models import ConnectorCatalogueState
                db.execute(update(ConnectorCatalogueState).values(
                    last_confirmed_current_at=None, operation_id=None, lease_until=None,
                    next_attempt_at=None))
                db.execute(delete(MfaChallenge))
                # Pending enrollment was rewrapped/authenticated above, then
                # retired as transient security authorization. Active seeds,
                # replay counters and unused recovery verifiers are preserved.
                db.execute(update(UserMfa).values(last_totp_step=func.greatest(UserMfa.last_totp_step, int(time.time()) // 30),
                                                  pending_ciphertext=None, pending_nonce=None,
                                                  pending_id=None, pending_expires_at=None, pending_attempts=0))
                state = installation_state(db, lock=True)
                state.initialized_at = state.initialized_at or datetime.now(timezone.utc)
                state.setup_code_hash = None
                state.setup_generation += 1
                state.failed_attempts = 0
                state.locked_until = None
                epoch = db.scalar(select(SystemSetting).where(SystemSetting.key == RESTORE_EPOCH_KEY))
                if epoch is None:
                    epoch = SystemSetting(key=RESTORE_EPOCH_KEY, sensitive=True,
                                          description="Internal session revocation generation after restore.")
                    db.add(epoch)
                epoch.value_ = str(uuid.uuid4())
                add_audit_event(db, action="restore.completed", target_type="installation",
                                actor_email=actor_email, metadata={
                                    "source_revision": opened.manifest.source_revision,
                                    "target_revision": supported_revision(opened.manifest.source_revision),
                                    "backup_id": str(opened.manifest.backup_id),
                                })
                db.flush()
        self.engine.dispose()

    def restore(self, job_id, passphrase, authorization, *, recovery=False):
        """Preflight → quiesce → encrypted rollback → restore → validate/release."""
        work = runtime.job_directory(job_id)
        opened, target_key = self.preflight(work, passphrase)
        # The passphrase is no longer needed after successful authentication.
        passphrase = None
        # Recovery starts from an already uncertain state. It must never write
        # a "draining" marker that startup could safely auto-clear.
        runtime.set_maintenance(job_id, "recovering" if recovery else "draining")
        request_lock = None
        destructive = False
        recovery_archive = work / "rollback.atlasbackup"
        try:
            request_lock = runtime.lock_file("requests.lock", exclusive=True, blocking=True)
            self.authorize_current(authorization)
            if not recovery:
                from app.models import DiscoveryRun
                with Session(self.engine) as db:
                    active = db.scalar(select(DiscoveryRun.id).where(DiscoveryRun.execution_provenance.is_not(None),
                        DiscoveryRun.dispatch_state != "settled").limit(1))
                    if active:
                        raise BackupError("Cancel active discovery runs and wait for cleanup before restoring.")
            runtime.update_job(job_id, state="restoring", message="Restoring Atlas data…")
            if not recovery:
                self.audit("restore.started", actor_email=authorization["actor_email"], metadata={"mode": authorization["mode"]})
            else:
                logger.info("Confirmed local backup recovery started")
            if not recovery:
                rollback_dump = work / "rollback.dump"
                rollback_metadata = self.postgres.dump(rollback_dump)
                encrypt_archive(rollback_dump, recovery_archive, target_key.hex(), target_key, rollback_metadata)
                rollback_dump.unlink()
            runtime.set_maintenance(job_id, "replacing")
            destructive = True
            self.postgres.replace(opened.dump)
            self.post_restore(opened, target_key, authorization["actor_email"])
            clear_redis()
            runtime.clear_maintenance()
        except BaseException:
            if recovery:
                runtime.set_maintenance(job_id, "recovery_required")
                raise BackupError("Local backup recovery failed; Atlas remains in maintenance mode.") from None
            if destructive:
                try:
                    self.rollback(job_id, authorization["actor_email"])
                except BaseException as rollback_error:
                    runtime.set_maintenance(job_id, "recovery_required")
                    logger.error("Atlas restore rollback failed (%s); local recovery required", type(rollback_error).__name__)
                    try:
                        self.audit("restore.rollback_failed", actor_email=authorization["actor_email"], success=False)
                    except Exception:
                        logger.error("Atlas rollback failure audit unavailable")
                    raise BackupError("Restore failed and Atlas remains in maintenance mode; local recovery is required.") from None
                raise BackupError("Restore failed and the original Atlas data was recovered.") from None
            runtime.clear_maintenance()
            raise
        finally:
            if request_lock is not None:
                runtime.unlock(request_lock)

    def rollback(self, job_id, actor_email="local-operator"):
        work = runtime.job_directory(job_id)
        rollback_work = work / "recovery"
        rollback_work.mkdir(mode=0o700, exist_ok=True)
        key = data_encryption_key()
        restored = decrypt_archive(work / "rollback.atlasbackup", rollback_work, key.hex())
        try:
            self.postgres.replace(restored.dump)
            with self.engine.connect() as connection:
                revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
                if revision != restored.manifest.source_revision:
                    raise BackupError("Local rollback validation failed.")
            clear_redis()
            self.audit("restore.failed", actor_email=actor_email, success=False)
            self.audit("restore.rollback_completed", actor_email=actor_email)
            runtime.clear_maintenance()
        finally:
            shutil.rmtree(rollback_work)


class BackupJobs:
    def __init__(self, engine):
        self.service = BackupService(engine)
        self.pending = {}
        self.mutex = threading.Lock()

    def reserve(self, *, kind, owner, actor_email, session_version=0, mode="existing", generation=0):
        if runtime.maintenance():
            raise BackupError("Atlas is in maintenance mode; local recovery may be required.")
        runtime.cleanup_stale()
        fd = runtime.lock_file("operation.lock", exclusive=True)
        job_id = str(uuid.uuid4())
        status_token = secrets.token_urlsafe(32)
        try:
            path = runtime.new_job_directory(job_id)
            runtime.write_json(path / "status.json", {
                "id": job_id, "kind": kind, "owner": owner, "actor_email": actor_email,
                "session_version": session_version, "mode": mode, "generation": generation,
                "state": "requested", "message": "Waiting for upload…" if kind == "restore" else "Preparing backup…",
                "created_at": time.time(), "expires_at": time.time() + runtime.UPLOAD_SECONDS,
                "status_verifier": hashlib.sha256(status_token.encode()).hexdigest(),
            })
        except BaseException:
            runtime.unlock(fd)
            raise
        return job_id, fd, status_token

    def execute(self, job_id, fd, passphrase, *, restore=False):
        def run():
            state = None
            try:
                state = runtime.job_state(job_id)
                runtime.update_job(job_id, state="preparing", message="Validating backup…" if restore else "Preparing backup…")
                if restore:
                    self.service.restore(job_id, passphrase, state)
                    runtime.update_job(job_id, state="complete", message="Restore completed. Sign in using your restored Atlas account.")
                else:
                    self.service.create(runtime.job_directory(job_id), passphrase)
                    self.service.audit("backup.created", actor_email=state["actor_email"])
                    runtime.update_job(job_id, state="ready", message="Your encrypted backup is ready to download.",
                                       expires_at=time.time() + runtime.DOWNLOAD_SECONDS)
            except Exception as error:
                message = str(error) if isinstance(error, BackupError) else "Atlas could not complete this operation. Check local installation health."
                runtime.update_job(job_id, state="failed", message=message)
                logger.error("Atlas %s failed (%s)", "restore" if restore else "backup", type(error).__name__)
                # Preflight failures intentionally make no database changes,
                # including audit rows. Post-destructive failures are audited
                # in the recovered DB or held fail-closed for local recovery.
                if not restore and state:
                    try:
                        self.service.audit("backup.failed", actor_email=state["actor_email"], success=False)
                    except Exception:
                        logger.error("Atlas backup failure audit unavailable")
            finally:
                try:
                    marker = runtime.maintenance()
                    runtime.remove_work(job_id, keep_archive=runtime.job_state(job_id)["state"] == "ready",
                                        keep_recovery=marker is not None and marker.get("job_id") == job_id)
                finally:
                    runtime.unlock(fd)
        worker = threading.Thread(target=run, name="atlas-" + job_id, daemon=True)
        worker.start()

    def await_upload(self, job_id, fd, passphrase):
        def expire():
            with self.mutex:
                pending = self.pending.pop(job_id, None)
            if pending:
                try:
                    runtime.remove_work(job_id)
                    runtime.update_job(job_id, state="expired", message="Restore upload authorization expired. Start again.")
                finally:
                    runtime.unlock(fd)
        timer = threading.Timer(runtime.UPLOAD_SECONDS, expire)
        timer.daemon = True
        with self.mutex:
            self.pending[job_id] = (fd, passphrase, timer)
        timer.start()

    def claim_upload(self, job_id):
        with self.mutex:
            pending = self.pending.pop(job_id, None)
        if pending is None:
            raise BackupError("Restore upload authorization expired. Start again.")
        fd, passphrase, timer = pending
        timer.cancel()
        try:
            runtime.update_job(job_id, state="uploading", message="Uploading encrypted backup…")
        except BaseException:
            runtime.unlock(fd)
            raise
        return fd, passphrase


_jobs = None


def backup_jobs():
    global _jobs
    if _jobs is None:
        from app.database import engine
        _jobs = BackupJobs(engine)
    return _jobs
