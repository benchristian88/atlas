"""Fresh supported Compose installation, usable from an SSH terminal."""
import argparse
from pathlib import Path
import subprocess

from configuration import ROOT, generate_configuration


def main():
    parser = argparse.ArgumentParser(description="Install Atlas using Docker Compose")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    configuration = args.env_file.resolve()
    try:
        generate_configuration(configuration, "docker_compose")
    except FileExistsError:
        raise SystemExit("Configuration already exists; refusing to overwrite it. Use the documented start/reset commands to resume.") from None
    compose = ["docker", "compose", "--env-file", str(configuration), "-f", str(ROOT / "infra/docker/docker-compose.yml")]
    subprocess.run(compose + ["up", "-d", "--build", "--wait", "--wait-timeout", "300"], check=True)
    subprocess.run(compose + ["exec", "-T", "api", "python", "-m", "scripts.setup_code", "reset"], check=True)


if __name__ == "__main__":
    main()
