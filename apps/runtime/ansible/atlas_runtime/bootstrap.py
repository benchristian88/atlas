"""One-shot Compose volume provisioner; not a network service."""
import os
from pathlib import Path
import secrets

from .server import load_secret


def provision(secret_directory: Path, store: Path, *, uid=10001, gid=10001):
    for directory in (secret_directory, store):
        if directory.is_symlink():
            raise ValueError("unsafe_volume")
        directory.mkdir(parents=True, exist_ok=True)
        os.chown(directory, uid, gid)
        os.chmod(directory, 0o700 if directory == secret_directory else 0o750)
    path = secret_directory / "control.secret"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    except FileExistsError:
        load_secret(path)  # Upgrade/restart preserves existing valid secret.
    else:
        with os.fdopen(descriptor, "w") as output:
            output.write(secrets.token_hex(48) + "\n")
            output.flush()
            os.fsync(output.fileno())
    os.chown(path, uid, gid)
    os.chmod(path, 0o400)


if __name__ == "__main__":
    try:
        provision(Path("/run/atlas-runtime-control"), Path("/var/lib/atlas-connectors"))
    except (OSError, ValueError):
        raise SystemExit("Cannot provision protected runtime volumes; existing material was preserved") from None
