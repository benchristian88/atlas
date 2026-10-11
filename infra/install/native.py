"""Install Atlas on a prepared Debian/Ubuntu systemd host, including nginx ingress."""
import argparse
import json
import grp
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import socket
import tempfile
import time
import sys

if __name__ == "__main__":
    # Even help in an extracted package must not create local bytecode directories.
    sys.dont_write_bytecode = True

from configuration import ROOT, build_id, generate_configuration
import native_ingress

DESTINATION = Path("/opt/atlas")
CONFIGURATION = Path("/etc/atlas/atlas.env")
STATE = Path("/var/lib/atlas")
UNITS = Path("/etc/systemd/system")


def run(arguments, **kwargs):
    return subprocess.run(arguments, check=True, **kwargs)


def probe(arguments, **kwargs):
    return subprocess.run(arguments, capture_output=True, text=True, timeout=30, **kwargs)


def host_errors():
    errors = []
    if os.geteuid() != 0:
        errors.append("Run this installer as root.")
    try:
        release = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
        supported = release.get("ID", "").strip('"') in {"debian", "ubuntu"}
    except OSError:
        supported = False
    if not supported or not Path("/run/systemd/system").is_dir():
        errors.append("A Debian/Ubuntu host booted with systemd is required.")
    return errors


def account_errors(*, fresh):
    try:
        account = pwd.getpwnam("atlas")
    except KeyError:
        if not fresh:
            return ["The existing unprivileged atlas service account is required."]
        try:
            grp.getgrnam("atlas")
        except KeyError:
            return []
        return ["An atlas group exists without its service account; resolve this before installation."]
    try:
        group = grp.getgrnam("atlas")
    except KeyError:
        return ["The atlas service account requires its dedicated atlas primary group."]
    if account.pw_uid == 0 or account.pw_gid != group.gr_gid:
        return ["Atlas requires an unprivileged account with the dedicated atlas primary group."]
    return []


def preflight(*, fresh=True, values=None):
    """Read-only checks plus a disposable venv probe; no durable Atlas mutation."""
    errors = host_errors() + account_errors(fresh=fresh)
    if sys.version_info < (3, 12):
        errors.append("Python 3.12 or newer is required.")
    required = ("systemctl", "runuser", "useradd", "groupadd", "usermod", "npm", "pg_dump", "pg_restore", "psql")
    available = {name: shutil.which(name) is not None for name in required}
    errors.extend(f"Required prerequisite is missing: {name}" for name, exists in available.items() if not exists)
    if not Path("/usr/bin/env").is_file():
        errors.append("The supported native API unit requires coreutils env at /usr/bin/env.")
    try:
        with tempfile.TemporaryDirectory(prefix="atlas-venv-preflight-") as directory:
            if probe([sys.executable, "-m", "venv", str(Path(directory) / "venv")]).returncode:
                errors.append("Python venv/ensurepip is unavailable; install python3-venv for this interpreter.")
    except (OSError, subprocess.SubprocessError):
        errors.append("Cannot create a disposable Python venv; check python3-venv and temporary storage.")
    try:
        version = probe(["/usr/bin/node", "--version"])
        if version.returncode or int(version.stdout.strip().lstrip("v").split(".")[0]) < 22:
            errors.append("Node.js 22 or newer is required at /usr/bin/node.")
    except (OSError, ValueError, subprocess.SubprocessError):
        errors.append("Node.js 22 or newer is required at /usr/bin/node.")
    if available["npm"]:
        try:
            if probe(["npm", "--version"]).returncode:
                errors.append("npm is unavailable; install npm compatible with Node.js 22+.")
        except (OSError, subprocess.SubprocessError):
            errors.append("npm could not run; check the host Node.js/npm installation.")
    if available["systemctl"]:
        for unit in ("postgresql.service", "redis-server.service"):
            try:
                if probe(["systemctl", "cat", unit]).returncode:
                    errors.append(f"Required service is missing: {unit}; install the host distribution package.")
                elif probe(["systemctl", "is-active", "--quiet", unit]).returncode:
                    errors.append(f"Start {unit} before installation/preflight.")
            except (OSError, subprocess.SubprocessError):
                errors.append(f"Cannot inspect required service: {unit}; check systemd.")
    try:
        native_ingress.safe_path(STATE.parent)
        if STATE.is_symlink():
            errors.append("Atlas state directory must not be a symlink.")
        elif fresh and STATE.exists():
            errors.append(f"Existing Atlas path requires operator review: {STATE}; refusing to overwrite it.")
        elif STATE.exists():
            account = pwd.getpwnam("atlas")
            if not STATE.is_dir() or STATE.stat().st_uid != account.pw_uid or STATE.stat().st_mode & 0o077:
                errors.append("Existing Atlas state must be a private directory owned by the atlas service account.")
        for path in (DESTINATION, CONFIGURATION, *(UNITS / f"atlas-{name}.service" for name in ("api", "web", "worker", "runtime"))):
            native_ingress.safe_path(path)
            parent = next(parent for parent in path.parents if parent.exists())
            if not os.access(parent, os.W_OK):
                errors.append(f"Required installation location is not writable: {parent}")
            if fresh and (path.exists() or path.is_symlink()):
                errors.append(f"Existing Atlas path requires operator review: {path}; refusing to overwrite it.")
        if not fresh and (not DESTINATION.is_dir() or not (DESTINATION / "venv/bin/python").is_file()):
            errors.append("An existing /opt/atlas installation and venv are required.")
        for name in ("apps/api/requirements.txt", "apps/web/package-lock.json", "infra/nginx/native.conf",
                     "infra/systemd/atlas-api.service", "infra/systemd/atlas-web.service", "infra/systemd/atlas-worker.service",
                     "apps/runtime/ansible/requirements.lock", "infra/systemd/atlas-runtime.service", "infra/install/runtime.py"):
            if not (ROOT / name).is_file():
                errors.append(f"Required installation file is missing: {name}")
        native_ingress.check_managed_paths()
        build_id()  # Validate canonical release metadata before account/config creation.
    except (OSError, ValueError, KeyError) as exc:
        errors.append(str(exc))
    ingress = None
    try:
        ingress = native_ingress.settings(values)
        native_ingress.render(ingress)
        listeners = [(ingress["ATLAS_BIND_ADDRESS"], int(ingress["ATLAS_PORT"]))]
        if fresh or not native_ingress.SITE.exists():
            listeners.append(("127.0.0.1", 3001))
        if fresh:
            listeners.append(("127.0.0.1", 8000))
            listeners.append(("127.0.0.1", 8091))
        for address, port in listeners:
            # Existing Atlas listeners belong to the upgrade lifecycle. Validate
            # the new endpoint on first adoption; subsequent upgrades reuse it.
            if not fresh and native_ingress.SITE.exists():
                continue
            if not fresh and address == "127.0.0.1" and port == 3000:
                continue  # The legacy native web unit owns this until stopped.
            with socket.socket() as listener:
                try:
                    listener.bind((address, port))
                except OSError:
                    errors.append(f"Atlas listener is unavailable: {address}:{port}; check the assigned address and port conflicts.")
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
    # Local peer administration, fixed SQL and no inherited PG connection overrides.
    if available["runuser"] and available["psql"] and os.geteuid() == 0:
        try:
            result = probe(["runuser", "-u", "postgres", "--", "psql", "-XAt", "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-c",
                "SELECT current_setting('server_version_num'), EXISTS(SELECT FROM pg_roles WHERE rolname='atlas'), "
                "EXISTS(SELECT FROM pg_database WHERE datname='atlas')"],
                env={**{key: value for key, value in os.environ.items() if not key.startswith("PG")}, "PGCONNECT_TIMEOUT": "5"})
            if result.returncode:
                errors.append("Cannot inspect local PostgreSQL using postgres peer administration; check service/authentication.")
            else:
                server, role, database = result.stdout.strip().split("|")
                major = int(server) // 10000
                if major not in {16, 17}:
                    errors.append("The supported native PostgreSQL server is version 16 or 17.")
                for executable in ("pg_dump", "pg_restore"):
                    if available[executable]:
                        version = re.search(r"\(PostgreSQL\) (\d+)", probe([executable, "--version"]).stdout)
                        if not version or int(version[1]) != major:
                            errors.append(f"{executable} must match the local PostgreSQL server major {major}.")
                if fresh and (role == "t" or database == "t"):
                    errors.append("Atlas PostgreSQL role/database already exists; refusing to replace credentials or data.")
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            errors.append("Cannot verify local PostgreSQL server/client compatibility and Atlas database/role availability.")
    needs_nginx = shutil.which("nginx") is None
    try:
        if needs_nginx:
            if not shutil.which("apt-get"):
                errors.append("nginx is missing and apt-get is unavailable; Debian/Ubuntu package management is required.")
            elif probe(["apt-get", "--simulate", "install", "--no-install-recommends", "nginx"]).returncode:
                errors.append("nginx cannot be installed from configured distribution packages; check apt package indexes/dependencies.")
        else:
            if probe(["nginx", "-t"]).returncode:
                errors.append("Existing nginx configuration fails nginx -t; repair it before Atlas installation/upgrade.")
            if available["systemctl"] and probe(["systemctl", "cat", "nginx.service"]).returncode:
                errors.append("nginx.service is missing; use the supported distribution nginx package.")
    except (OSError, subprocess.SubprocessError):
        errors.append("Cannot verify nginx configuration or distribution package installability.")
    if errors:
        raise ValueError("Atlas preflight failed; no Atlas installation changes made:\n" + "\n".join(f"  - {error}" for error in dict.fromkeys(errors)))
    return ingress, needs_nginx


def ensure_nginx(needs_install):
    if needs_install:
        print("Installing nginx from configured Debian/Ubuntu packages...")
        try:
            run(["apt-get", "install", "--yes", "--no-install-recommends", "nginx"],
                env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"}, capture_output=True, text=True)
        except (OSError, subprocess.SubprocessError):
            raise ValueError("nginx package installation failed; no Atlas files/accounts/database were created. Check apt health and retry.") from None
    try:
        native_ingress.command(["nginx", "-t"])
        native_ingress.command(["systemctl", "cat", "nginx.service"])
    except (OSError, subprocess.SubprocessError):
        raise ValueError("nginx is not ready; check distribution package/service/configuration. No Atlas installation changes made.") from None


def install_sdk(python):
    run([python, "-m", "pip", "install", "--no-index", "--no-deps", "--require-hashes", "--find-links", str(DESTINATION / "vendor/sdk"), "-r", str(DESTINATION / "vendor/sdk/requirements.txt")])


def build_application(account):
    if not (DESTINATION / "venv").exists():
        run([sys.executable, "-m", "venv", str(DESTINATION / "venv")])
    python = str(DESTINATION / "venv/bin/python")
    install_sdk(python)
    run([python, "-m", "pip", "install", "-r", "requirements.txt"], cwd=DESTINATION / "apps/api")
    build_runtime()
    try:
        # The API remains unable to mutate the native root-owned store.
        run([python, "-m", "scripts.stage_integration_bootstrap"], cwd=DESTINATION / "apps/api")
    except (OSError, subprocess.SubprocessError):
        print("Approved Connector staging was unsuccessful; Atlas knowledge services will continue. Inspect the protected package store before activation.")
    environment = {**os.environ, "PATH": "/usr/bin:" + os.environ.get("PATH", "/bin"), "NEXT_PUBLIC_API_URL": "/api"}
    run(["npm", "ci"], cwd=DESTINATION / "apps/web", env=environment)
    run(["npm", "run", "build"], cwd=DESTINATION / "apps/web", env=environment)
    standalone = DESTINATION / "apps/web/.next/standalone"
    shutil.copytree(DESTINATION / "apps/web/public", standalone / "public", dirs_exist_ok=True)
    shutil.copytree(DESTINATION / "apps/web/.next/static", standalone / ".next/static", dirs_exist_ok=True)
    cache = standalone / ".next/cache"
    cache.mkdir(parents=True, exist_ok=True)
    for path in (cache, *cache.rglob("*")):
        os.chown(path, account.pw_uid, account.pw_gid)


def build_runtime():
    """Dependency failure is diagnosed without stopping the knowledge plane."""
    runtime_environment = DESTINATION / "runtime-venv"
    if runtime_environment.is_symlink():
        raise ValueError("Runtime environment must not be a symlink")
    try:
        if not runtime_environment.exists():
            run([sys.executable, "-m", "venv", str(runtime_environment)])
        runtime_python = str(runtime_environment / "bin/python")
        install_sdk(runtime_python)
        run([runtime_python, "-m", "pip", "install", "--no-deps", "-r", "requirements.lock"], cwd=DESTINATION / "apps/runtime/ansible")
        run([runtime_python, "-m", "pip", "check"])
    except (OSError, subprocess.SubprocessError):
        print("Local runtime dependencies could not be prepared; Atlas knowledge services will continue. Inspect runtime-venv and the Runtime page.")


def install_units():
    for unit in ("atlas-api", "atlas-web", "atlas-worker", "atlas-runtime"):
        shutil.copyfile(DESTINATION / f"infra/systemd/{unit}.service", Path(f"/etc/systemd/system/{unit}.service"))
    run(["systemctl", "daemon-reload"])


def configure_runtime():
    from runtime import configure
    configure(CONFIGURATION, STATE.parent / "atlas-connectors")


def configure_worker(values, configuration=None):
    """Root-owned filtered environment; no user/session or publishing secret."""
    import secrets
    configuration = configuration or CONFIGURATION
    path = configuration.parent / "worker.env"
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("Worker configuration must not be a symlink")
    allowed = {"DATABASE_URL", "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD",
        "REDIS_URL", "ATLAS_DATA_ENCRYPTION_KEY", "ATLAS_INSTALL_METHOD", "ATLAS_RUNTIME_ENABLED", "ATLAS_RUNTIME_URL",
        "ATLAS_RUNTIME_CONTROL_SECRET_FILE", "ATLAS_CONNECTOR_STORE_PATH", "ATLAS_RUNTIME_BASELINE_FILE"}
    if any(not isinstance(values[name], str) or any(character in values[name] for character in "\n\r\x00") for name in allowed & values.keys()):
        raise ValueError("Invalid worker environment value")
    content = "".join(f"{name}={values[name]}\n" for name in sorted(allowed & values.keys()))
    temporary = path.parent / ("worker-" + secrets.token_hex(16))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "w") as target:
            target.write(content)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def start_runtime(values):
    try:
        if values.get("ATLAS_RUNTIME_ENABLED", "true").lower() in {"false", "0", "no"}:
            run(["systemctl", "disable", "--now", "atlas-runtime"])
        else:
            # Runtime readiness is a product health state; it cannot block startup
            # of the API/web knowledge plane and has no Requires dependency there.
            run(["systemctl", "enable", "--now", "atlas-runtime"])
    except (OSError, subprocess.SubprocessError):
        print("Local runtime could not start or stop; Atlas knowledge services will continue. Inspect atlas-runtime.service and the Runtime page.")


def stop_runtime():
    try:
        run(["systemctl", "stop", "atlas-runtime"])
    except (OSError, subprocess.SubprocessError):
        print("Local runtime was unavailable during upgrade; Atlas knowledge services will continue. Inspect atlas-runtime.service after upgrade.")


def wait_for_health(ingress):
    import urllib.request
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = f"http://{ingress['ATLAS_BIND_ADDRESS']}:{ingress['ATLAS_PORT']}"
    for address in (url + "/api/health", url + "/login"):
        for attempt in range(60):
            try:
                opener.open(address, timeout=2).close()
                break
            except OSError:
                if attempt == 59:
                    raise ValueError("Atlas did not become ready; inspect systemctl status nginx atlas-api atlas-web.") from None
                time.sleep(2)


def install(ingress, needs_nginx, *, runtime_enabled=True):
    ensure_nginx(needs_nginx)
    # Application/venv files must be readable by the unprivileged services,
    # even when the invoking root shell has a restrictive umask. Secret file
    # permissions are explicitly enforced by the configuration generator.
    os.umask(0o022)
    try:
        account = pwd.getpwnam("atlas")
    except KeyError:
        run(["useradd", "--system", "--user-group", "--home-dir", "/opt/atlas", "--shell", "/usr/sbin/nologin", "atlas"])
        account = pwd.getpwnam("atlas")
    if account.pw_uid == 0:
        raise SystemExit("Atlas requires an unprivileged service account.")
    try:
        dedicated_group = grp.getgrnam("atlas")
    except KeyError:
        raise SystemExit("The existing Atlas account requires a dedicated atlas group.") from None
    if account.pw_gid != dedicated_group.gr_gid:
        raise SystemExit("The Atlas account must use the dedicated atlas primary group.")
    CONFIGURATION.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    os.chown(CONFIGURATION.parent, 0, account.pw_gid)
    os.chmod(CONFIGURATION.parent, 0o750)
    generate_configuration(CONFIGURATION, "systemd", ingress=ingress, runtime_enabled=runtime_enabled)
    os.chown(CONFIGURATION, 0, account.pw_gid)
    os.chmod(CONFIGURATION, 0o640)
    configure_runtime()
    DESTINATION.mkdir(mode=0o755)
    for name in ("apps", "infra", "vendor"):
        shutil.copytree(ROOT / name, DESTINATION / name,
                        ignore=shutil.ignore_patterns("node_modules", ".next", ".venv", "__pycache__", ".env", ".env.*"))
    build_application(account)
    python = str(DESTINATION / "venv/bin/python")
    run(["systemctl", "enable", "--now", "postgresql.service", "redis-server.service"])
    values = dict(line.split("=", 1) for line in CONFIGURATION.read_text().splitlines() if line and not line.startswith("#"))
    configure_worker(values)
    # Peer-authenticated local provisioning. Password is passed on stdin,
    # never in psql arguments, SQL logs or shell history. Existing DB/role
    # names cause refusal; no existing user data is reinterpreted.
    provision = '''import json,sys
import psycopg
from psycopg import sql
password=json.load(sys.stdin)["password"]
with psycopg.connect("dbname=postgres", autocommit=True) as db:
    if db.execute("SELECT 1 FROM pg_roles WHERE rolname='atlas'").fetchone() or db.execute("SELECT 1 FROM pg_database WHERE datname='atlas'").fetchone():
        sys.exit("Atlas PostgreSQL role/database already exists; refusing to replace credentials.")
    db.execute("SET log_statement = 'none'")
    db.execute("SET log_min_error_statement = 'panic'")
    try:
        db.execute(sql.SQL("CREATE ROLE atlas LOGIN PASSWORD {}").format(sql.Literal(password)))
        db.execute("CREATE DATABASE atlas OWNER atlas")
    except psycopg.Error:
        sys.exit("Atlas database provisioning failed; inspect PostgreSQL service health.")
'''
    run(["runuser", "-u", "postgres", "--", python, "-c", provision],
        input=json.dumps({"password": values["POSTGRES_PASSWORD"]}), text=True, cwd="/tmp")
    install_units()
    start_runtime(values)
    run(["systemctl", "enable", "--now", "atlas-api", "atlas-web", "atlas-worker"])
    native_ingress.install(ingress)
    wait_for_health(ingress)
    run(["systemctl", "is-active", "--quiet", "atlas-api", "atlas-web", "atlas-worker"])
    handoff = run(["runuser", "-u", "atlas", "--", python, "-m", "scripts.setup_code", "reset", "--access-url",
         f"http://{ingress['ATLAS_BIND_ADDRESS']}:{ingress['ATLAS_PORT']}/"],
        cwd=DESTINATION / "apps/api", env={**os.environ, **values, "ATLAS_STATE_DIR": "/var/lib/atlas"}, capture_output=True, text=True)
    # Emit the intended local handoff only after reset commits successfully.
    print("Atlas installed successfully.\n", flush=True)
    print(handoff.stdout, end="")


def main():
    # Parse before even read-only host checks, including --help on non-Linux hosts.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manual-only", action="store_true", help="Install the Atlas knowledge plane with the local runtime disabled")
    args = parser.parse_args()
    try:
        ingress, needs_nginx = preflight()
        if args.manual_only:
            install(ingress, needs_nginx, runtime_enabled=False)
        else:
            install(ingress, needs_nginx)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    except (OSError, subprocess.SubprocessError):
        raise SystemExit("Atlas installation could not complete. Inspect host/service health. Retain generated configuration, "
                         "keys, database and state for operator diagnosis; the installer will not overwrite a partial installation.") from None


if __name__ == "__main__":
    main()
