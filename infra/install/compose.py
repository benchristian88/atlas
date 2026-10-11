"""Fresh supported Compose installation, usable from an SSH terminal."""
import argparse
from pathlib import Path
import subprocess

from configuration import ROOT, generate_configuration


def main():
    parser = argparse.ArgumentParser(description="Install Atlas using Docker Compose")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--manual-only", action="store_true", help="Install the Atlas knowledge plane without starting the local runtime")
    args = parser.parse_args()
    configuration = args.env_file.resolve()
    try:
        ingress = generate_configuration(configuration, "docker_compose")
    except FileExistsError:
        raise SystemExit("Configuration already exists; refusing to overwrite it. Use the documented start/reset commands to resume.") from None
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    if args.manual_only:
        configuration.write_text(configuration.read_text().replace("ATLAS_RUNTIME_ENABLED=true\n", "ATLAS_RUNTIME_ENABLED=false\n"))
    compose = ["docker", "compose", "--env-file", str(configuration), "-f", str(ROOT / "infra/docker/docker-compose.yml")]
    services = ["gateway", "api", "web", "worker", "postgres", "redis"]
    subprocess.run(compose + ["up", "-d", "--build", "--wait", "--wait-timeout", "300", *services], check=True)
    if not args.manual_only:
        try:
            subprocess.run(compose + ["up", "-d", "--build", "--wait", "--wait-timeout", "60", "runtime"], check=True)
        except (OSError, subprocess.SubprocessError):
            print("Local runtime is unavailable; Atlas knowledge services are ready. Inspect the runtime service and Runtime page.")
    access_url = f"http://{ingress['ATLAS_BIND_ADDRESS']}:{ingress['ATLAS_PORT']}"
    subprocess.run(compose + ["exec", "-T", "api", "python", "-m", "scripts.setup_code", "reset",
                              "--access-url", access_url], check=True)


if __name__ == "__main__":
    main()
