"""Native local management, with protected file configuration (no shell source)."""
import os
from pathlib import Path
import sys


def main():
    if sys.argv[1:] != ["setup-code", "reset"]:
        raise SystemExit("Usage: manage.py setup-code reset")
    configuration = Path("/etc/atlas/atlas.env")
    for line in configuration.read_text().splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            os.environ[key] = value
    sys.path.insert(0, "/opt/atlas/apps/api")
    from scripts.setup_code import main as reset
    sys.argv = ["setup-code", "reset"]
    reset()


if __name__ == "__main__":
    main()
