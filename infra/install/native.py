"""Supported Debian/Ubuntu systemd installer with preinstalled dependencies."""
import json
import grp
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import time
import sys

from configuration import ROOT, generate_configuration

DESTINATION = Path("/opt/atlas")
CONFIGURATION = Path("/etc/atlas/atlas.env")


def run(arguments, **kwargs):
    return subprocess.run(arguments, check=True, **kwargs)


def main():
    if sys.version_info < (3, 12):
        raise SystemExit("Python 3.12 or newer is required.")
    if os.geteuid() != 0:
        raise SystemExit("Run this installer as root on a supported systemd host.")
    # Application/venv files must be readable by the unprivileged services,
    # even when the invoking root shell has a restrictive umask. Secret file
    # permissions are explicitly enforced by the configuration generator.
    os.umask(0o022)
    if CONFIGURATION.exists() or DESTINATION.exists():
        raise SystemExit("Atlas configuration or installation already exists; refusing to overwrite it.")
    for executable in ("systemctl", "runuser", "python3", "node", "npm"):
        if shutil.which(executable) is None:
            raise SystemExit(f"Required prerequisite is missing: {executable}")
    if not Path("/usr/bin/node").is_file():
        raise SystemExit("The supported native unit requires Node.js at /usr/bin/node.")
    major = int(subprocess.check_output(["node", "--version"], text=True).strip().lstrip("v").split(".")[0])
    if major < 22:
        raise SystemExit("Node.js 22 or newer is required.")
    for unit in ("postgresql.service", "redis-server.service"):
        run(["systemctl", "cat", unit], stdout=subprocess.DEVNULL)
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
    generate_configuration(CONFIGURATION, "systemd")
    os.chown(CONFIGURATION, 0, account.pw_gid)
    os.chmod(CONFIGURATION, 0o640)
    DESTINATION.mkdir(mode=0o755)
    for name in ("apps", "infra"):
        shutil.copytree(ROOT / name, DESTINATION / name,
                        ignore=shutil.ignore_patterns("node_modules", ".next", ".venv", "__pycache__", ".env", ".env.*"))
    run(["python3", "-m", "venv", str(DESTINATION / "venv")])
    python = str(DESTINATION / "venv/bin/python")
    run([python, "-m", "pip", "install", "-r", "requirements.txt"], cwd=DESTINATION / "apps/api")
    run(["npm", "ci"], cwd=DESTINATION / "apps/web")
    run(["npm", "run", "build"], cwd=DESTINATION / "apps/web", env={**os.environ, "NEXT_PUBLIC_API_URL": "/api"})
    standalone = DESTINATION / "apps/web/.next/standalone"
    shutil.copytree(DESTINATION / "apps/web/public", standalone / "public", dirs_exist_ok=True)
    shutil.copytree(DESTINATION / "apps/web/.next/static", standalone / ".next/static", dirs_exist_ok=True)
    cache = standalone / ".next/cache"
    cache.mkdir(parents=True, exist_ok=True)
    for path in (cache, *cache.rglob("*")):
        os.chown(path, account.pw_uid, account.pw_gid)
    run(["systemctl", "enable", "--now", "postgresql.service", "redis-server.service"])
    values = dict(line.split("=", 1) for line in CONFIGURATION.read_text().splitlines() if line and not line.startswith("#"))
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
    for unit in ("atlas-api", "atlas-web", "atlas-worker"):
        shutil.copyfile(DESTINATION / f"infra/systemd/{unit}.service", Path(f"/etc/systemd/system/{unit}.service"))
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "--now", "atlas-api", "atlas-web", "atlas-worker"])
    import urllib.request
    for address in ("http://127.0.0.1:8000/api/health", "http://127.0.0.1:3000/login"):
        for attempt in range(60):
            try:
                urllib.request.urlopen(address, timeout=2).close()
                break
            except OSError:
                if attempt == 59:
                    raise SystemExit("Atlas did not become ready; inspect systemctl status atlas-api atlas-web.") from None
                time.sleep(2)
    run(["systemctl", "is-active", "--quiet", "atlas-api", "atlas-web", "atlas-worker"])
    run(["runuser", "-u", "atlas", "--", python, "-m", "scripts.setup_code", "reset"],
        cwd=DESTINATION / "apps/api", env={**os.environ, **values})


if __name__ == "__main__":
    main()
