"""Confirmed local recovery through the shared backup service; no CLI passphrases."""
import argparse
import getpass
import os
from pathlib import Path
import shutil
import sys

from app.database import engine
from app.services import backup_runtime as runtime
from app.services.backup_archive import BackupError, MAX_ARCHIVE_BYTES
from app.services.backups import BackupJobs


def main():
    parser = argparse.ArgumentParser(description="Atlas encrypted backup and local recovery")
    commands = parser.add_subparsers(dest="action", required=True)
    create = commands.add_parser("create")
    create.add_argument("--output", type=Path, required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("--input", type=Path, required=True)
    recover = commands.add_parser("recover")
    recover.add_argument("--input", type=Path, help="Trusted portable backup if the local rollback is unavailable")
    # Native management follows the existing H1/H2 argv convention.
    arguments = parser.parse_args(sys.argv[1:])
    os.umask(0o077)
    jobs = BackupJobs(engine)
    if arguments.action in {"restore", "recover"}:
        try:
            if input("This replaces Atlas data. Type RESTORE to continue: ").strip() != "RESTORE":
                raise SystemExit("Cancelled.")
        except (EOFError, KeyboardInterrupt):
            raise SystemExit("Cancelled.") from None
    fd = request_fd = None
    job_id = None
    try:
        if arguments.action == "recover":
            marker = runtime.maintenance()
            if marker is None:
                raise BackupError("Atlas does not require local restore recovery.")
            fd = runtime.lock_file("operation.lock", exclusive=True)
            job_id = marker["job_id"]
            if arguments.input:
                passphrase = getpass.getpass("Backup passphrase: ")
                runtime.remove_work(job_id, keep_recovery=True)
                work = runtime.job_directory(job_id)
                source_fd = runtime.private_open(arguments.input, os.O_RDONLY)
                with os.fdopen(source_fd, "rb") as source, (work / "upload.atlasbackup").open("xb") as destination:
                    if os.fstat(source.fileno()).st_size > MAX_ARCHIVE_BYTES:
                        raise BackupError("The archive exceeds the 2 GiB limit.")
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
                jobs.service.restore(job_id, passphrase, {"mode": "local", "actor_email": "local-operator"}, recovery=True)
            else:
                request_fd = runtime.lock_file("requests.lock", exclusive=True, blocking=True)
                jobs.service.rollback(job_id)
            runtime.update_job(job_id, state="complete", message="Atlas data recovered by the local operator.")
        else:
            passphrase = getpass.getpass("Backup passphrase: ")
            if arguments.action == "create" and passphrase != getpass.getpass("Confirm backup passphrase: "):
                raise BackupError("Passphrases do not match.")
            job_id, fd, _ = jobs.reserve(kind="backup" if arguments.action == "create" else "restore",
                                        owner="local-operator", actor_email="local-operator", mode="local")
            work = runtime.job_directory(job_id)
            if arguments.action == "create":
                jobs.service.create(work, passphrase)
                # Exclusive output creation refuses overwrite and symlinks.
                output_fd = os.open(arguments.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                try:
                    with os.fdopen(output_fd, "wb") as destination, (work / "backup.atlasbackup").open("rb") as source:
                        shutil.copyfileobj(source, destination, length=1024 * 1024)
                except BaseException:
                    arguments.output.unlink(missing_ok=True)
                    raise
                jobs.service.audit("backup.created")
            else:
                source_fd = runtime.private_open(arguments.input, os.O_RDONLY)
                with os.fdopen(source_fd, "rb") as source, (work / "upload.atlasbackup").open("xb") as destination:
                    if os.fstat(source.fileno()).st_size > MAX_ARCHIVE_BYTES:
                        raise BackupError("The archive exceeds the 2 GiB limit.")
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
                jobs.service.restore(job_id, passphrase, runtime.job_state(job_id))
            runtime.update_job(job_id, state="complete", message="Local operation completed.")
        print("Atlas local backup operation completed.")
    except (BackupError, OSError) as error:
        message = str(error) if isinstance(error, BackupError) else "Atlas local backup files are unavailable or unsafe."
        raise SystemExit(message) from None
    except Exception:
        raise SystemExit("Atlas local backup operation failed. Check local database, configuration and maintenance state.") from None
    finally:
        try:
            if job_id:
                marker = runtime.maintenance()
                runtime.remove_work(job_id, keep_recovery=marker is not None and marker.get("job_id") == job_id)
        finally:
            if request_fd is not None:
                runtime.unlock(request_fd)
            if fd is not None:
                runtime.unlock(fd)


if __name__ == "__main__":
    main()
