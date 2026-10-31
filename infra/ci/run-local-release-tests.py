"""Run only the root-dependent suites inside fresh, private CI containers."""
from collections import Counter
import os
from pathlib import Path
import secrets
import subprocess
import sys
from xml.etree import ElementTree

import psycopg
from psycopg import sql
from sqlalchemy import URL

TEST_MODULES = (
    "test_local_release_authority_postgres",
    "test_local_release_recovery",
    "test_local_release_remediation",
)
MINIMUM_TESTS = 83  # All cases previously skipped by ordinary-user CI.


def prepare_database():
    """Only bootstrap can create roles/DBs; tests use a non-superuser owner."""
    bootstrap_password = os.environ.pop("ATLAS_CI_POSTGRES_PASSWORD")
    password = secrets.token_hex(32)
    options = dict(host="postgres", user="atlas_ci_bootstrap", password=bootstrap_password,
                   autocommit=True, connect_timeout=5)
    with psycopg.connect(dbname="postgres", **options) as connection:
        assert int(connection.execute("SHOW server_version_num").fetchone()[0]) // 10000 == 17
        # Refuse reuse: existing role/database is an error, never dropped here.
        connection.execute(sql.SQL(
            "CREATE ROLE atlas_local_release LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}"
        ).format(sql.Literal(password)))
        connection.execute("CREATE DATABASE atlas_local_release OWNER atlas_local_release TEMPLATE template0")
        connection.execute("REVOKE ALL ON DATABASE atlas_local_release FROM PUBLIC")
    with psycopg.connect(dbname="atlas_local_release", **options) as connection:
        # Non-secret cluster identity is required by the genuine enrollment check.
        connection.execute("GRANT EXECUTE ON FUNCTION pg_control_system() TO atlas_local_release")
    url = URL.create("postgresql+psycopg", username="atlas_local_release", password=password,
                     host="postgres", database="atlas_local_release").render_as_string(hide_password=False)
    os.environ.update(DATABASE_URL=url, ATLAS_TEST_DATABASE_URL=url)
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)


def verify_report(path):
    cases = ElementTree.parse(path).findall(".//testcase")
    assert len(cases) >= MINIMUM_TESTS, f"Expected at least {MINIMUM_TESTS} security tests, found {len(cases)}"
    counts = Counter(case.get("classname", "").split(".")[-1] for case in cases)
    assert set(counts) == set(TEST_MODULES), f"Unexpected security suite coverage: {dict(counts)}"
    assert all(len(case) == 0 for case in cases), "Every security test must pass; skips/errors/failures are forbidden"
    for module in TEST_MODULES:
        print(f"{module}: {counts[module]} passed", flush=True)
    print(f"Local-release security gate: {len(cases)} passed, zero skipped", flush=True)


def main():
    assert os.geteuid() == 0 and Path("/.dockerenv").exists(), "Use the disposable CI Docker environment"
    try:
        prepare_database()
    except (KeyError, psycopg.Error, subprocess.CalledProcessError):
        raise SystemExit("Disposable local-release database preparation failed; credentials are not displayed.") from None
    report = Path("/tmp/atlas-ci-local-release.xml")
    subprocess.run([sys.executable, "-m", "pytest", *(f"tests/{module}.py" for module in TEST_MODULES),
                    "-q", "-rs", "--tb=short", f"--junitxml={report}"], check=True)
    verify_report(report)


if __name__ == "__main__":
    main()
