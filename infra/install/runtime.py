"""Root-operated native runtime setup, without giving it Atlas credentials."""
import grp
import os
from pathlib import Path
import pwd
import re
import secrets
import stat
import subprocess


def run(arguments):
    subprocess.run(arguments, check=True, capture_output=True, text=True)


def configure(configuration: Path, store: Path):
    for name in ("atlas-runtime", "atlas-runtime-control"):
        try:
            grp.getgrnam(name)
        except KeyError:
            run(["groupadd", "--system", name])
    try:
        account = pwd.getpwnam("atlas-runtime")
    except KeyError:
        run(["useradd", "--system", "--gid", "atlas-runtime", "--home-dir", "/nonexistent", "--shell", "/usr/sbin/nologin", "atlas-runtime"])
        account = pwd.getpwnam("atlas-runtime")
    if account.pw_uid == 0 or account.pw_gid != grp.getgrnam("atlas-runtime").gr_gid:
        raise ValueError("Runtime requires its dedicated unprivileged service account")
    run(["usermod", "--append", "--groups", "atlas-runtime-control", "atlas"])
    run(["usermod", "--append", "--groups", "atlas-runtime-control", "atlas-runtime"])
    secret_group = grp.getgrnam("atlas-runtime-control").gr_gid
    secret_directory = configuration.parent.parent / "atlas-runtime"
    for directory, group in ((secret_directory, secret_group), (store, secret_group)):
        if any(parent.is_symlink() for parent in (directory, *directory.parents)):
            raise ValueError("Protected runtime directories must not be symlinks")
        if directory.exists() and (not directory.is_dir() or directory.stat().st_uid != 0 or directory.stat().st_mode & 0o022):
            raise ValueError("Protected runtime directory must remain root-owned and unwritable by services")
        directory.mkdir(mode=0o750, parents=True, exist_ok=True)
        os.chown(directory, 0, group)
        os.chmod(directory, 0o750)
    secret = secret_directory / "control.secret"
    try:
        descriptor = os.open(secret, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
    except FileExistsError:
        descriptor = os.open(secret, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "r") as existing:
            info = os.fstat(existing.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o027
                    or not re.fullmatch(r"[a-f0-9]{96}\n?", existing.read(256))):
                raise ValueError("Existing runtime credential is invalid; refusing to replace it")
    else:
        with os.fdopen(descriptor, "w") as output:
            os.fchmod(output.fileno(), 0o640)
            output.write(secrets.token_hex(48) + "\n")
            output.flush()
            os.fsync(output.fileno())
    os.chown(secret, 0, secret_group)
    os.chmod(secret, 0o640)
