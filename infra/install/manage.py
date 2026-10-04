"""Native local management, with protected file configuration (no shell source)."""
import os
from pathlib import Path
import sys


def main():
    arguments = sys.argv[1:]
    if arguments != ["setup-code", "reset"] and not (len(arguments) == 4 and arguments[:3] == ["mfa", "reset", "--user"]):
        raise SystemExit("Usage: manage.py setup-code reset | mfa reset --user <email>")
    configuration = Path("/etc/atlas/atlas.env")
    for line in configuration.read_text().splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            os.environ[key] = value
    sys.path.insert(0, "/opt/atlas/apps/api")
    if arguments[0] == "mfa":
        from scripts.mfa import main as reset
    else:
        from scripts.setup_code import main as reset
    sys.argv = arguments
    reset()


if __name__ == "__main__":
    main()
