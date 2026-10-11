"""Protected, target-local staging and quiescence for the single Atlas runtime.

Kernel locks drain in-flight API requests and serialize UI/local jobs. Durable
maintenance markers survive replacement of PostgreSQL and process crashes. A
crash during destructive work never expires back into normal service.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import time
import uuid

from app.services.backup_archive import BackupError

DOWNLOAD_SECONDS = 15 * 60
UPLOAD_SECONDS = 10 * 60
STATUS_SECONDS = 24 * 60 * 60


def state_directory() -> Path:
    default = Path(__file__).resolve().parents[2] / ".atlas-state"
    path = Path(os.getenv("ATLAS_STATE_DIR", str(default))).absolute()
    # Deployment-owned parent must already exist; never follow a substituted
    # state directory or an arbitrary symlink supplied by a local caller.
    if path.parent.resolve() != path.parent:
        raise BackupError("Atlas backup state directory is unsafe.")
    path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise BackupError("Atlas backup state directory requires private service-account permissions.")
    return path


def private_open(path: Path, flags: int):
    fd = os.open(path, flags | os.O_NOFOLLOW, 0o600)
    info = os.fstat(fd)
    # An atomic metadata replacement can unlink an already-open read inode.
    # That private snapshot remains safe; multiple links remain forbidden.
    allowed_links = {0, 1} if flags & os.O_ACCMODE == os.O_RDONLY else {1}
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink not in allowed_links:
        os.close(fd)
        raise BackupError("Atlas backup staging file is unsafe.")
    return fd


def lock_file(name: str, *, exclusive: bool, blocking: bool = False, read_only: bool = False):
    fd = private_open(state_directory() / name, os.O_RDONLY if read_only else os.O_CREAT | os.O_RDWR)
    try:
        deadline = time.monotonic() + 60
        while True:
            try:
                fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if not blocking or time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)
    except BlockingIOError:
        os.close(fd)
        raise BackupError("Atlas is busy with another backup or restore.") from None
    return fd


def unlock(fd):
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


def read_json(path: Path) -> dict:
    fd = private_open(path, os.O_RDONLY)
    with os.fdopen(fd, "r") as stream:
        value = stream.read(16385)
    if len(value) > 16384:
        raise BackupError("Atlas backup status is unavailable.")
    try:
        result = json.loads(value)
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise BackupError("Atlas backup status is unavailable.") from None


def write_json(path: Path, value: dict):
    temporary = path.parent / ("state-" + secrets.token_hex(16))
    fd = private_open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink():
            raise BackupError("Atlas backup status file is unsafe.")
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def maintenance() -> dict | None:
    path = state_directory() / "maintenance.json"
    try:
        return read_json(path)
    except FileNotFoundError:
        return None


def set_maintenance(job_id: str, phase: str):
    write_json(state_directory() / "maintenance.json", {
        "job_id": str(uuid.UUID(job_id)), "phase": phase,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


def clear_maintenance():
    (state_directory() / "maintenance.json").unlink(missing_ok=True)


@contextmanager
def normal_operation(*, read_only: bool = False):
    # Read the marker both before and after acquiring the shared lock. A
    # restorer writes the marker before waiting for existing requests to drain.
    if maintenance() is not None:
        raise BackupError("Atlas is in maintenance mode. A restore or local recovery is in progress.")
    fd = lock_file("requests.lock", exclusive=False, read_only=read_only)
    try:
        if maintenance() is not None:
            raise BackupError("Atlas is in maintenance mode. A restore or local recovery is in progress.")
        yield
    finally:
        unlock(fd)


def job_directory(job_id: str) -> Path:
    return state_directory() / str(uuid.UUID(job_id))


def new_job_directory(job_id: str) -> Path:
    path = job_directory(job_id)
    path.mkdir(mode=0o700)
    return path


def job_state(job_id: str) -> dict:
    path = job_directory(job_id)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.geteuid():
        raise BackupError("Atlas backup staging directory is unsafe.")
    return read_json(path / "status.json")


def update_job(job_id: str, **changes):
    state = job_state(job_id)
    state.update(changes)
    write_json(job_directory(job_id) / "status.json", state)
    return state


def remove_work(job_id: str, *, keep_archive: bool = False, keep_recovery: bool = False):
    path = job_directory(job_id)
    keep = {"status.json"}
    if keep_archive:
        keep.add("backup.atlasbackup")
    if keep_recovery:
        keep.add("rollback.atlasbackup")
    for child in path.iterdir():
        if child.name in keep:
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def cleanup_stale():
    """Only clean when no process owns the operation lock; keep crash recovery."""
    try:
        fd = lock_file("operation.lock", exclusive=True)
    except BackupError:
        return
    try:
        marker = maintenance()
        if marker and marker.get("phase") == "draining":
            # No destructive action began. Locks vanished with the crashed
            # process, so it is safe to retire an abandoned drain marker.
            clear_maintenance()
            marker = None
        active_recovery = marker.get("job_id") if marker else None
        for child in state_directory().iterdir():
            try:
                job_id = str(uuid.UUID(child.name))
            except ValueError:
                continue
            state = job_state(job_id)
            if job_id == active_recovery:
                remove_work(job_id, keep_recovery=True)
                update_job(job_id, state="failed", message="Atlas remains in maintenance mode; local recovery is required.")
            elif state["state"] in {"requested", "preparing", "uploading", "restoring"}:
                remove_work(job_id)
                update_job(job_id, state="failed", message="The operation was interrupted. Start again.")
            elif state.get("expires_at", 0) < time.time():
                remove_work(job_id)
                if state["state"] == "ready":
                    update_job(job_id, state="expired", message="This backup download has expired.")
                if state["created_at"] + STATUS_SECONDS < time.time():
                    shutil.rmtree(child)
    finally:
        unlock(fd)
