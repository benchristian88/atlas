"""Provision the complete H4 regression on a disposable loopback CI cluster.

Creates thirteen isolated databases with a generated non-superuser owner. Eight
migration databases stay empty; five domain/H1/H2/H3 databases are migrated.
Refuses existing CI roles/databases; never drops or overwrites a database.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import time

import psycopg
from psycopg import sql
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "infra/install"))
from upgrade import protected_configuration

DATABASES = {
    "ATLAS_TEST_DATABASE_URL": ("atlas_ci_domain", True),
    "ATLAS_TEST_H1_DATABASE_URL": ("atlas_ci_setup", True),
    "ATLAS_TEST_H2_DATABASE_URL": ("atlas_ci_mfa", True),
    "ATLAS_TEST_H3_SOURCE_URL": ("atlas_ci_backup_source", True),
    "ATLAS_TEST_H3_TARGET_URL": ("atlas_ci_backup_target", True),
    "ATLAS_TEST_MIGRATION_DATABASE_URL": ("atlas_ci_asset_migration", False),
    "ATLAS_TEST_PRESENTATION_MIGRATION_URL": ("atlas_ci_presentation_migration", False),
    "ATLAS_TEST_LAYERS_MIGRATION_URL": ("atlas_ci_layers_migration", False),
    "ATLAS_TEST_POSITIONS_MIGRATION_URL": ("atlas_ci_positions_migration", False),
    "ATLAS_TEST_ROLES_MIGRATION_URL": ("atlas_ci_roles_migration", False),
    "ATLAS_TEST_H1_MIGRATION_URL": ("atlas_ci_h1_migration", False),
    "ATLAS_TEST_H2_MIGRATION_URL": ("atlas_ci_h2_migration", False),
    "ATLAS_TEST_I1_MIGRATION_URL": ("atlas_ci_i1_migration", False),
}


def mask(value):
    if os.getenv("GITHUB_ACTIONS") == "true":
        print(f"::add-mask::{value}", flush=True)


def prepare(configuration, port):
    values = protected_configuration(configuration, "docker_compose")
    for key in ("POSTGRES_PASSWORD", "AUTH_SECRET_KEY", "ATLAS_DATA_ENCRYPTION_KEY"):
        mask(values[key])
    deadline = time.monotonic() + 60
    while True:
        try:
            connection = psycopg.connect(host="127.0.0.1", port=port, dbname="postgres",
                user="atlas_ci_bootstrap", password=values["POSTGRES_PASSWORD"],
                autocommit=True, connect_timeout=2)
            break
        except psycopg.OperationalError:
            if time.monotonic() >= deadline:
                raise ValueError("Disposable CI PostgreSQL did not become ready") from None
            time.sleep(.5)
    password = secrets.token_hex(32)
    mask(password)
    environment = {}
    with connection:
        major = int(connection.execute("SHOW server_version_num").fetchone()[0]) // 10000
        if major != 17:
            raise ValueError("CI regression requires PostgreSQL 17")
        names = [name for name, _ in DATABASES.values()]
        if (connection.execute("SELECT 1 FROM pg_roles WHERE rolname = 'atlas_ci_owner'").fetchone()
                or connection.execute("SELECT 1 FROM pg_database WHERE datname = ANY(%s)", (names,)).fetchone()):
            raise ValueError("CI databases/role already exist; use a fresh disposable cluster")
        connection.execute(sql.SQL("CREATE ROLE atlas_ci_owner LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(sql.Literal(password)))
        for variable, (name, _) in DATABASES.items():
            connection.execute(sql.SQL("CREATE DATABASE {} OWNER atlas_ci_owner TEMPLATE template0").format(sql.Identifier(name)))
            connection.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(name)))
            url = URL.create("postgresql+psycopg", username="atlas_ci_owner", password=password,
                host="127.0.0.1", port=port, database=name).render_as_string(hide_password=False)
            mask(url)
            environment[variable] = url
    for variable, (_, migrate) in DATABASES.items():
        if migrate:
            subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=ROOT / "apps/api", env={**os.environ, "DATABASE_URL": environment[variable]}, check=True)
    environment["DATABASE_URL"] = environment["ATLAS_TEST_DATABASE_URL"]
    return environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="Generated protected docker_compose configuration")
    parser.add_argument("--port", type=int, default=5432, help="Disposable loopback PostgreSQL port")
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--github-env", type=Path, help="Append masked variables to the Actions environment file")
    output.add_argument("--env-file", type=Path, help="Create a protected shell environment file for local checks")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    try:
        environment = prepare(args.config, args.port)
        if args.github_env:
            with args.github_env.open("a") as stream:
                stream.write("".join(f"{key}={value}\n" for key, value in environment.items()))
        else:
            descriptor = os.open(args.env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                stream.write("".join(f"{key}={shlex.quote(value)}\n" for key, value in environment.items()))
    except (OSError, ValueError, psycopg.Error, subprocess.CalledProcessError):
        raise SystemExit("CI database preparation failed; check the disposable cluster, configuration and migration output. Credentials are not displayed.") from None
    print("Prepared all thirteen isolated PostgreSQL test databases; credentials are not displayed.")


if __name__ == "__main__":
    main()
