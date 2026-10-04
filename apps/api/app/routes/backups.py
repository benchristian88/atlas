"""Global-Master export/import and separately scoped restore progress."""
import asyncio
from datetime import datetime, timezone
import hashlib
import hmac
import os
import time
from typing import Annotated
import uuid

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import Field, model_validator
from sqlalchemy.orm import Session

from app.auth import cookie_secure
from app.authorization import Principal, require_global, require_permission
from app.database import get_db
from app.routes.mfa import Credentials
from app.services import backup_runtime as runtime, mfa
from app.services.backup_archive import BackupError, CHUNK, MAX_ARCHIVE_BYTES
from app.services.backups import backup_jobs
from app.services.installation import SETUP_COOKIE, installation_state, require_setup_authorization, require_uninitialized

router = APIRouter(prefix="/system-settings", tags=["backup and restore"])
setup_router = APIRouter(prefix="/setup/restore", tags=["first-run restore"])
status_router = APIRouter(prefix="/restore-status", tags=["restore progress"])
STATUS_COOKIE = "atlas_restore_status"
STATUS_COOKIE_PATH = "/api/restore-status"


class BackupRequest(Credentials):
    passphrase: str = Field(min_length=12, max_length=1024, repr=False)
    passphrase_confirmation: str = Field(min_length=12, max_length=1024, repr=False)

    @model_validator(mode="after")
    def matching_passphrases(self):
        if self.passphrase != self.passphrase_confirmation:
            raise ValueError("Passphrases do not match")
        return self


class RestoreRequest(Credentials):
    passphrase: str = Field(min_length=12, max_length=1024, repr=False)
    acknowledgement: str = Field(pattern="^RESTORE$")


class FreshRestoreRequest(Credentials):
    # No account exists yet; setup authorization is the security boundary.
    current_password: str = Field(default="", max_length=0, repr=False)
    passphrase: str = Field(min_length=12, max_length=1024, repr=False)


def require_master(principal: Principal = Depends(require_permission("system_settings.manage")),
                   db: Session = Depends(get_db)):
    from app.routes.users import _has_global_master
    require_global(principal, "system_settings.manage")
    if not _has_global_master(db, principal.user.id):
        raise HTTPException(403, "A global Master Administrator is required for backup and restore")
    return principal


def public_status(state):
    return {key: state[key] for key in ("id", "kind", "state", "message", "expires_at")}


def owned_job(job_id, principal):
    try:
        state = runtime.job_state(str(job_id))
    except (FileNotFoundError, BackupError):
        raise HTTPException(404, "Backup operation not found") from None
    if state["owner"] != str(principal.user.id) or state["session_version"] != principal.user.session_version:
        raise HTTPException(404, "Backup operation not found")
    return state


def reserve(principal, kind):
    try:
        return backup_jobs().reserve(kind=kind, owner=str(principal.user.id),
                                     actor_email=principal.user.email,
                                     session_version=principal.user.session_version)
    except BackupError as error:
        raise HTTPException(409, str(error)) from None


def reauthenticate(db, principal, payload, request, *, second_factor=False):
    user = mfa.locked_user(db, principal.user.id, principal.user.session_version)
    mfa.reauthenticate(db, user, payload.current_password, request)
    if second_factor and user.mfa_enabled:
        if not payload.code:
            raise HTTPException(400, "Enter a current authenticator or recovery code to restore Atlas")
        mfa.verify_factor(db, user, mfa.state_for(db, user), payload.code, payload.method, request)
    db.commit()


def status_cookie(response, request, token):
    response.set_cookie(STATUS_COOKIE, token, max_age=7200, path=STATUS_COOKIE_PATH,
                        httponly=True, samesite="lax", secure=cookie_secure(request))


def release_reservation(job_id, fd):
    try:
        runtime.update_job(job_id, state="failed", message="Authorization failed. Start again.")
        runtime.remove_work(job_id)
    finally:
        runtime.unlock(fd)


@router.post("/backups", status_code=202)
def create_backup(payload: BackupRequest, request: Request,
                  principal: Principal = Depends(require_master), db: Session = Depends(get_db)):
    job_id, fd, _ = reserve(principal, "backup")
    try:
        reauthenticate(db, principal, payload, request)
        backup_jobs().execute(job_id, fd, payload.passphrase)
    except BaseException:
        release_reservation(job_id, fd)
        raise
    return public_status(runtime.job_state(job_id))


@router.get("/backups/{job_id}")
def backup_status(job_id: uuid.UUID, principal: Principal = Depends(require_master)):
    runtime.cleanup_stale()
    return public_status(owned_job(job_id, principal))


@router.get("/backups/{job_id}/download")
def download(job_id: uuid.UUID, principal: Principal = Depends(require_master)):
    state = owned_job(job_id, principal)
    if state["state"] != "ready" or state["expires_at"] < time.time():
        runtime.cleanup_stale()
        raise HTTPException(410, "This backup is unavailable or its download has expired")
    path = runtime.job_directory(str(job_id)) / "backup.atlasbackup"
    try:
        fd = runtime.private_open(path, os.O_RDONLY)
        # Atomic claim makes this a single-use download even with parallel GETs.
        claimed = path.with_name("download.atlasbackup")
        os.rename(path, claimed)
    except FileNotFoundError:
        if "fd" in locals():
            os.close(fd)
        raise HTTPException(410, "This backup has already been downloaded") from None
    runtime.update_job(str(job_id), state="expired", message="Backup download claimed. Create another backup if needed.")
    filename = datetime.fromtimestamp(state["created_at"], timezone.utc).strftime("atlas-backup-%Y%m%d-%H%M%S.atlasbackup")

    def stream():
        try:
            with os.fdopen(fd, "rb") as source:
                for chunk in iter(lambda: source.read(CHUNK), b""):
                    yield chunk
        finally:
            claimed.unlink(missing_ok=True)
    return StreamingResponse(stream(), media_type="application/octet-stream", headers={
        "Cache-Control": "no-store", "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Content-Type-Options": "nosniff",
    })


@router.post("/restore/authorize", status_code=202)
def authorize_restore(payload: RestoreRequest, request: Request, response: Response,
                      principal: Principal = Depends(require_master), db: Session = Depends(get_db)):
    job_id, fd, token = reserve(principal, "restore")
    try:
        reauthenticate(db, principal, payload, request, second_factor=True)
        backup_jobs().await_upload(job_id, fd, payload.passphrase)
    except BaseException:
        release_reservation(job_id, fd)
        raise
    status_cookie(response, request, token)
    return public_status(runtime.job_state(job_id))


@setup_router.post("/authorize", status_code=202)
def authorize_fresh_restore(payload: FreshRestoreRequest, request: Request, response: Response,
                            token: Annotated[str | None, Cookie(alias=SETUP_COOKIE)] = None,
                            db: Session = Depends(get_db)):
    state = installation_state(db, lock=True)
    require_uninitialized(db, state)
    require_setup_authorization(state, token)
    generation = state.setup_generation
    db.commit()
    try:
        job_id, fd, status_token = backup_jobs().reserve(kind="restore", owner="setup", actor_email="setup/local-system",
                                                       mode="fresh", generation=generation)
        backup_jobs().await_upload(job_id, fd, payload.passphrase)
    except BackupError as error:
        raise HTTPException(409, str(error)) from None
    status_cookie(response, request, status_token)
    return public_status(runtime.job_state(job_id))


async def receive_upload(job_id: str, request: Request):
    jobs = backup_jobs()
    try:
        fd, passphrase = jobs.claim_upload(job_id)
    except BackupError as error:
        raise HTTPException(410, str(error)) from None
    try:
        length = request.headers.get("content-length")
        if length is not None and (not length.isdecimal() or not 1 <= int(length) <= MAX_ARCHIVE_BYTES):
            raise HTTPException(413, "Upload an Atlas backup no larger than 2 GiB")
        path = runtime.job_directory(job_id) / "upload.atlasbackup"
        count = 0
        async with asyncio.timeout(runtime.UPLOAD_SECONDS):
            with os.fdopen(runtime.private_open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL), "wb") as destination:
                async for chunk in request.stream():
                    count += len(chunk)
                    if count > MAX_ARCHIVE_BYTES:
                        raise HTTPException(413, "Upload an Atlas backup no larger than 2 GiB")
                    destination.write(chunk)
        if not count:
            raise HTTPException(400, "Upload a valid Atlas backup")
        jobs.execute(job_id, fd, passphrase, restore=True)
    except BaseException as error:
        try:
            runtime.remove_work(job_id)
            runtime.update_job(job_id, state="failed", message="Backup upload failed. Start again.")
        finally:
            runtime.unlock(fd)
        if isinstance(error, HTTPException):
            raise
        raise HTTPException(400, "Backup upload failed. Start again.") from None
    return public_status(runtime.job_state(job_id))


@router.put("/restore/{job_id}/upload", status_code=202)
async def existing_upload(job_id: uuid.UUID, request: Request,
                          principal: Principal = Depends(require_master)):
    state = owned_job(job_id, principal)
    if state["kind"] != "restore":
        raise HTTPException(404, "Restore operation not found")
    return await receive_upload(str(job_id), request)


@setup_router.put("/{job_id}/upload", status_code=202)
async def fresh_upload(job_id: uuid.UUID, request: Request,
                       token: Annotated[str | None, Cookie(alias=SETUP_COOKIE)] = None,
                       db: Session = Depends(get_db)):
    state = installation_state(db, lock=True)
    require_uninitialized(db, state)
    require_setup_authorization(state, token)
    try:
        job = runtime.job_state(str(job_id))
    except FileNotFoundError:
        raise HTTPException(404, "Restore operation not found") from None
    if job["owner"] != "setup" or job["generation"] != state.setup_generation:
        raise HTTPException(404, "Restore operation not found")
    db.commit()
    return await receive_upload(str(job_id), request)


@status_router.get("/{job_id}")
def restore_status(job_id: uuid.UUID, token: Annotated[str | None, Cookie(alias=STATUS_COOKIE)] = None):
    # No restored database/session lookup. This cookie reveals only progress of
    # the one authorized restore, never entities, manifest or credentials.
    try:
        state = runtime.job_state(str(job_id))
    except (FileNotFoundError, BackupError):
        raise HTTPException(404, "Restore operation not found") from None
    if (state["kind"] != "restore" or not token or state["created_at"] + 7200 < time.time()
        or not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), state["status_verifier"])):
        raise HTTPException(404, "Restore operation not found")
    return public_status(state)
