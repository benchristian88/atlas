"""Standard-library production configuration generator, shared by installers."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def build_id() -> str:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unknown"


def generate_configuration(path: Path, method: str) -> None:
    if method not in {"docker_compose", "systemd"}:
        raise ValueError("Unsupported production installation method")
    content = (
        "# Atlas production bootstrap configuration. Keep this file protected.\n"
        f"POSTGRES_PASSWORD={secrets.token_hex(32)}\n"
        f"AUTH_SECRET_KEY={secrets.token_hex(48)}\n"
        "AUTH_COOKIE_SECURE=true\n"
        "CORS_ORIGINS=\n"
        f"ATLAS_INSTALL_METHOD={method}\n"
        f"ATLAS_BUILD_ID={build_id()}\n"
    )
    # Exclusive creation also refuses symlinks and empty existing files.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(content)


def main():
    parser = argparse.ArgumentParser(description="Generate protected Atlas production configuration")
    parser.add_argument("--method", choices=["docker_compose", "systemd"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        generate_configuration(args.output, args.method)
    except FileExistsError:
        raise SystemExit("Configuration already exists; refusing to overwrite it.") from None
    print(f"Protected configuration created at {args.output}. Secrets are not displayed.")


if __name__ == "__main__":
    main()
