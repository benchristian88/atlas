"""Operator-run upgrades from a verified release package; never a web action."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess

from configuration import ROOT, add_runtime_configuration


def package_identity(method):
    spec = importlib.util.spec_from_file_location("atlas_release_policy", ROOT / "apps/api/app/release.py")
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    metadata = policy.load_metadata(ROOT / "apps/api/app/release.json")
    identity = json.loads((ROOT / "PACKAGE.json").read_text())
    if (metadata.get("install_method") != method or identity.get("install_method") != method
            or identity.get("version") != metadata["version"]
            or identity.get("commit_sha") != metadata["build_id"]
            or not re.fullmatch(r"[a-f0-9]{40}", metadata["build_id"] or "")):
        raise ValueError("Use the matching verified Atlas release package")
    return metadata


def protected_configuration(path, method):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o027:
            raise ValueError("Configuration must be a protected regular file (0600 or 0640)")
        if method == "systemd" and info.st_uid != 0:
            raise ValueError("Native configuration must remain owned by root")
        values = {}
        for line in stream.read().splitlines():
            if not line or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            if key in values:
                raise ValueError("Duplicate configuration keys require operator review")
            values[key] = value
    for key in ("POSTGRES_PASSWORD", "AUTH_SECRET_KEY", "ATLAS_DATA_ENCRYPTION_KEY"):
        if not values.get(key):
            raise ValueError("Existing production secrets are required; do not regenerate configuration")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", values["ATLAS_DATA_ENCRYPTION_KEY"]):
        raise ValueError("Existing data-encryption key is invalid; refusing to replace it")
    if values.get("ATLAS_INSTALL_METHOD", method) != method:
        raise ValueError("Configuration installation method does not match package")
    return values


def run(arguments, **kwargs):
    return subprocess.run(arguments, check=True, **kwargs)


def docker_upgrade(configuration):
    compose = ["docker", "compose", "--env-file", str(configuration), "-f", str(ROOT / "infra/docker/docker-compose.yml")]
    # Suppress rendered configuration: Compose config can contain credentials.
    run(compose + ["config", "--quiet"])
    # Build before the maintenance window. Writers stop before API migration.
    run(compose + ["build", "api", "web", "worker", "runtime", "runtime-init"])
    run(compose + ["stop", "gateway", "web", "worker", "api"])
    values = protected_configuration(configuration, "docker_compose")
    services = ["gateway", "api", "web", "worker", "postgres", "redis"]
    runtime_enabled = values.get("ATLAS_RUNTIME_ENABLED", "true").lower() not in {"false", "0", "no"}
    if not runtime_enabled:
        run(compose + ["stop", "runtime"])
    run(compose + ["up", "-d", "--wait", "--wait-timeout", "300", *services])
    if runtime_enabled:
        try:
            run(compose + ["up", "-d", "--wait", "--wait-timeout", "60", "runtime"])
        except (OSError, subprocess.SubprocessError):
            print("Local runtime is unavailable; Atlas knowledge services are ready. Inspect the runtime service and Runtime page.")
    run(compose + ["exec", "-T", "api", "python", "-c",
                  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=5).close()"])


def native_upgrade_preflight(values):
    from native import DESTINATION, preflight
    if ROOT == DESTINATION or DESTINATION in ROOT.parents:
        raise ValueError("Extract the new package outside /opt/atlas")
    for name in ("apps", "infra", "vendor", "venv", "runtime-venv"):
        if (DESTINATION / name).is_symlink():
            raise ValueError("Managed installation tree must not be a symlink")
    return preflight(fresh=False, values=values)


def native_upgrade(values, *, prepared=None):
    from native import DESTINATION, build_application, configure_runtime, ensure_nginx, install_units, start_runtime, stop_runtime, wait_for_health
    import native_ingress
    ingress, needs_nginx = prepared if prepared is not None else native_upgrade_preflight(values)
    ensure_nginx(needs_nginx)  # Package failure precedes the maintenance window.
    account = pwd.getpwnam("atlas")
    os.umask(0o022)
    configure_runtime()
    stop_runtime()  # Legacy installations do not yet have this unit.
    run(["systemctl", "stop", "atlas-web", "atlas-worker", "atlas-api"])
    # Only managed application/configuration-free trees are replaced. Database,
    # /etc/atlas, /var/lib/atlas and the existing venv identity stay in place.
    for name in ("apps", "infra", "vendor"):
        destination = DESTINATION / name
        if destination.is_symlink():
            raise ValueError("Managed installation tree must not be a symlink")
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(ROOT / name, destination)
    build_application(account)
    install_units()
    start_runtime(values)
    run(["systemctl", "start", "atlas-api", "atlas-web", "atlas-worker"])
    native_ingress.install(ingress)
    wait_for_health(ingress)
    run(["systemctl", "is-active", "--quiet", "atlas-api", "atlas-web", "atlas-worker"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", choices=["docker_compose", "systemd"], required=True)
    parser.add_argument("--env-file", type=Path, help="Existing protected Docker configuration; never overwritten")
    parser.add_argument("--validate-only", action="store_true", help="Validate package/prerequisites without changes")
    parser.add_argument("--backup-confirmed", action="store_true", help="Confirm an encrypted Atlas backup has been created/downloaded")
    args = parser.parse_args()
    try:
        metadata = package_identity(args.method)
        if args.method == "systemd" and args.env_file:
            raise ValueError("Native upgrades use the existing /etc/atlas/atlas.env")
        configuration = args.env_file or (ROOT / ".env" if args.method == "docker_compose" else Path("/etc/atlas/atlas.env"))
        # Do not resolve a symlink before the O_NOFOLLOW check.
        configuration = Path(os.path.abspath(configuration))
        values = protected_configuration(configuration, args.method)
        prepared = native_upgrade_preflight(values) if args.method == "systemd" else None
        if args.validate_only:
            print(f"Package {metadata['version']} ({args.method}) and protected configuration validated; no changes made.")
            return
        if not args.backup_confirmed:
            raise ValueError("Create/download an encrypted Atlas backup first, then pass --backup-confirmed")
        add_runtime_configuration(configuration, args.method)
        values = protected_configuration(configuration, args.method)
        if args.method == "docker_compose":
            docker_upgrade(configuration)
        else:
            native_upgrade(values, prepared=prepared)
        print(f"Atlas {metadata['version']} upgrade completed. Confirm login, MFA, health and System Settings build identity.")
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    except (OSError, KeyError, subprocess.SubprocessError):
        raise SystemExit("Upgrade could not complete. Check the verified package, protected configuration and service logs. "
                         "No secrets were regenerated. If services stopped, keep the maintenance window closed and use documented backup recovery.") from None


if __name__ == "__main__":
    main()
