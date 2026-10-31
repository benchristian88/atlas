"""Protect the routine CI boundary and its complete regression configuration."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

import yaml
import pytest

ROOT = Path(__file__).resolve().parents[3]
# Reviewed official release commits whose action.yml declares runs.using=node24.
NODE24_ACTION_PINS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",  # v7.0.1
    "actions/setup-node": "820762786026740c76f36085b0efc47a31fe5020",  # v7.0.0
    "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",  # v7.0.0
}


def workflow(name="ci"):
    # GitHub uses YAML 1.2; BaseLoader keeps the key 'on' intact.
    return yaml.load((ROOT / f".github/workflows/{name}.yml").read_text(), Loader=yaml.BaseLoader)


def runs(job):
    return "\n".join(step.get("run", "") for step in job["steps"])


def test_ci_triggers_required_checks_and_cancellation():
    ci = workflow()
    assert ci["on"] == {"pull_request": {"branches": ["dev", "main"]},
                        "push": {"branches": ["dev", "main"]}, "workflow_dispatch": ""}
    assert ci["concurrency"]["cancel-in-progress"] == "true"
    assert "github.workflow" in ci["concurrency"]["group"]
    assert "github.event.pull_request.number || github.ref" in ci["concurrency"]["group"]
    assert {job["name"] for job in ci["jobs"].values()} == {
        "Backend / PostgreSQL", "Frontend", "Release & Deployment Integrity"}
    assert all(job["runs-on"] == "ubuntu-24.04" and "timeout-minutes" in job for job in ci["jobs"].values())


def test_ci_has_only_read_permissions_pinned_actions_and_no_publication():
    ci, release = workflow(), workflow("release")
    assert ci["permissions"] == {"contents": "read"}
    release_actions = {step["uses"] for job in release["jobs"].values() for step in job["steps"] if "uses" in step}
    for configuration in (ci, release):
        for job in configuration["jobs"].values():
            for step in job["steps"]:
                name, _, pin = step.get("uses", "").partition("@")
                if name in NODE24_ACTION_PINS:
                    assert pin == NODE24_ACTION_PINS[name]
    for job in ci["jobs"].values():
        assert "permissions" not in job and "if" not in job
        for step in job["steps"]:
            assert "continue-on-error" not in step
            if "uses" in step:
                assert re.fullmatch(r"actions/[a-z-]+@[a-f0-9]{40}", step["uses"])
                assert step["uses"] in release_actions
                assert "artifact" not in step["uses"]
                if step["uses"].startswith("actions/checkout@"):
                    assert step["with"]["persist-credentials"] == "false"
                    assert step["with"]["ref"] == "${{ github.sha }}"
            assert "${{" not in step.get("run", "")
            assert "GH_TOKEN" not in step.get("env", {})
        shell = runs(job)
        assert all(command not in shell for command in (
            "publish.py", "gh release", "git tag", "git push", "docker push", "--tag", "|| true", "eval "))
    assert "secrets." not in (ROOT / ".github/workflows/ci.yml").read_text()


def test_backend_enables_every_optional_database_suite_and_rejects_skips():
    job = workflow()["jobs"]["backend"]
    assert job["env"]["PYTHONPATH"] == "${{ github.workspace }}/plugins/sdk:${{ github.workspace }}/plugins/proxmox"
    assert job["env"]["ATLAS_TEST_H3_REDIS_URL"] == "redis://127.0.0.1:6379/0"
    redis = job["services"]["redis"]
    assert redis["image"] == "redis:7.4.6-alpine"
    assert redis["ports"] == ["127.0.0.1:6379:6379"]
    assert '--health-cmd "redis-cli ping"' in redis["options"]
    source = (ROOT / "infra/ci/prepare-postgres.py").read_text()
    tree = ast.parse(source)
    databases = next(ast.literal_eval(node.value) for node in tree.body
                     if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "DATABASES" for target in node.targets))
    required = set()
    for path in (ROOT / "apps/api/tests").glob("test_*.py"):
        required.update(re.findall(r"ATLAS_TEST_[A-Z0-9_]+URL", path.read_text()))
    assert required - {"ATLAS_TEST_H3_REDIS_URL"} == set(databases)
    assert len({name for name, _ in databases.values()}) == len(databases) == 15
    assert sum(migrate for _, migrate in databases.values()) == 5
    assert all(not migrate for key, (_, migrate) in databases.items() if "MIGRATION" in key)
    assert "NOSUPERUSER NOCREATEDB NOCREATEROLE" in source
    shell = runs(job)
    assert "postgres:17-alpine" in shell and "--publish 127.0.0.1:5432:5432" in shell
    assert "POSTGRES_HOST_AUTH_METHOD" not in shell
    assert "--env-file" in shell and "configuration.py --method docker_compose" in shell
    assert "tests ../../plugins/sdk/tests ../../plugins/proxmox/tests" in shell
    assert "assert not skipped" in shell and "assert len(heads) == 1" in shell
    assert "compileall -q" in shell and "apps/worker/worker apps/runtime" in shell
    contract_steps = [step for step in job["steps"] if step.get("run", "").startswith("python -m pytest docs/architecture/integrations/contracts/tests")]
    assert len(contract_steps) == 1
    assert "pip install -e" not in shell and "requirements-dev.txt" not in shell
    dependencies = (ROOT / "infra/ci/install-linux-dependencies.sh").read_text()
    assert "postgresql-client-17" in dependencies and "nginx-1.28.3.tar.gz" in dependencies
    assert "sha256sum -c -" in dependencies and "signed-by=" in dependencies


def local_release_runner():
    spec = importlib.util.spec_from_file_location("ci_local_release", ROOT / "infra/ci/run-local-release-tests.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_root_security_suites_are_mandatory_in_existing_backend_check():
    job = workflow()["jobs"]["backend"]
    ordinary = next(step for step in job["steps"] if step.get("name", "").startswith("Ordinary-user API"))
    privileged = next(step for step in job["steps"] if step.get("name", "").startswith("Root-only local-release"))
    assert "if" not in ordinary and "if" not in privileged and "continue-on-error" not in job
    assert "sudo" not in ordinary["run"] and "assert not skipped" in ordinary["run"]
    runner = local_release_runner()
    ignored = re.findall(r"--ignore=tests/(\w+)\.py", ordinary["run"])
    assert set(ignored) == set(runner.TEST_MODULES) and len(ignored) == 3
    assert runner.MINIMUM_TESTS == 83
    assert "--file apps/api/Dockerfile -t atlas-ci-local-release-api" in privileged["run"]
    assert "build tests" in privileged["run"] and "run --rm tests" in privileged["run"]
    cleanup = next(step for step in job["steps"] if step.get("if") == "always()")
    assert "down --volumes --remove-orphans" in cleanup["run"]
    assert "trap 'rm -f" in cleanup["run"] and "atlas-ci-local-release.env" in cleanup["run"]

    compose = yaml.safe_load((ROOT / "infra/ci/docker-compose.local-release-tests.yml").read_text())
    assert compose["networks"] == {"default": {"internal": True}}
    assert set(compose["services"]) == {"postgres", "tests"}
    tests = compose["services"]["tests"]
    assert tests["user"] == "0:0" and tests["cap_drop"] == ["ALL"]
    assert set(tests["cap_add"]) == {"SETUID", "SETGID"}
    assert tests["security_opt"] == ["no-new-privileges:true"]
    assert tests["depends_on"] == {"postgres": {"condition": "service_healthy"}}
    assert "volumes" not in tests
    assert compose["services"]["postgres"]["volumes"] == ["postgres_data:/var/lib/postgresql/data"]
    for service in compose["services"].values():
        assert not {"ports", "privileged", "network_mode", "pid", "devices"} & service.keys()
    dockerfile = (ROOT / "infra/ci/local-release-tests.Dockerfile").read_text()
    assert "FROM atlas-ci-local-release-api" in dockerfile
    assert "cp -a /app/app/attestation/bin /workspace/apps/api/app/attestation/bin" in dockerfile


@pytest.mark.parametrize("problem", [None, "skipped", "failure", "error", "missing_module", "missing_cases"])
def test_root_security_report_rejects_incomplete_or_nonpassing_execution(tmp_path, problem):
    from xml.etree import ElementTree as ET
    runner = local_release_runner()
    suite = ET.Element("testsuite")
    for index in range(runner.MINIMUM_TESTS):
        module = runner.TEST_MODULES[index % len(runner.TEST_MODULES)]
        if problem == "missing_module":
            module = runner.TEST_MODULES[0]
        case = ET.SubElement(suite, "testcase", classname=f"tests.{module}", name=f"test_{index}")
        if index == 0 and problem in {"skipped", "failure", "error"}:
            ET.SubElement(case, problem)
    if problem == "missing_cases":
        suite.remove(case)
    path = tmp_path / "report.xml"
    ET.ElementTree(suite).write(path)
    if problem is None:
        runner.verify_report(path)
    else:
        with pytest.raises(AssertionError):
            runner.verify_report(path)


def test_backend_cleanup_removes_credentials_and_attempts_both_clusters_on_failure(tmp_path):
    cleanup = next(step for step in workflow()["jobs"]["backend"]["steps"] if step.get("if") == "always()")
    docker = tmp_path / "docker"
    docker.write_text('''#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$RUNNER_TEMP/docker.log"
if [ "$1" = compose ]; then exit 23; fi
''')
    docker.chmod(0o755)
    configurations = [tmp_path / f"atlas-ci-{name}.env" for name in ("postgres", "local-release")]
    for path in configurations:
        path.touch(mode=0o600)
    result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", cleanup["run"]], cwd=ROOT,
                            env={**os.environ, "RUNNER_TEMP": str(tmp_path),
                                 "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"]},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 23  # Cleanup failure remains a failure.
    assert all(not path.exists() for path in configurations)
    commands = (tmp_path / "docker.log").read_text().splitlines()
    assert "down --volumes --remove-orphans" in commands[0]
    assert commands[1:] == ["container inspect atlas-ci-postgres", "rm --force --volumes atlas-ci-postgres"]


def test_release_integrity_reuses_h4_and_builds_without_publication():
    job = workflow()["jobs"]["release-and-deployment-integrity"]
    shared = "bash ../../infra/ci/release-critical.sh"
    assert shared in runs(job) and shared in runs(workflow("release")["jobs"]["build"])
    selector = (ROOT / "infra/ci/release-critical.sh").read_text()
    for path in re.findall(r"(?:tests|\.\./\.\./plugins)/[^\s\\]+", selector):
        assert (ROOT / "apps/api" / path).exists(), path
    for name in ("test_integration_runtime.py", "test_runtime_packaging.py", "test_connector_packages.py", "test_integration_catalogue_api.py"):
        assert f"tests/{name}" in selector
    assert "test_i1_migration_postgres.py" not in selector and "test_connector_lifecycle_postgres.py" not in selector
    shell = runs(job)
    for command in ("release.py metadata", "build --dry-run", "verify --require-committed",
                    "sha256sum -c SHA256SUMS", "compose.py --help", "native.py --help",
                    "upgrade.py", "protected_configuration", "config --quiet", "build api web worker runtime runtime-init connector-bootstrap",
                    "docker-compose.dev.yml", "git diff --check", "actionlint@v1.7.7"):
        assert command in shell
    assert "--worktree" not in shell
    assert all(" up " not in step.get("run", "") for step in job["steps"])
    for configured_job in (job, workflow("release")["jobs"]["build"]):
        assert "build api web worker runtime runtime-init connector-bootstrap" in runs(configured_job)
        assert "python -m pytest docs/architecture/integrations/contracts/tests" in runs(configured_job)


def test_discovery_runtime_installs_only_canonical_sdk_and_exact_lock():
    job = workflow()["jobs"]["backend"]
    step = next(step for step in job["steps"]
                if step.get("name") == "Install isolated pinned Ansible runtime for discovery acceptance")
    commands = step["run"].splitlines()
    runtime_python = '"$RUNNER_TEMP/atlas-ci-runtime/bin/python"'
    assert commands[0] == 'python -I -m venv --clear "$RUNNER_TEMP/atlas-ci-runtime"'
    installs = [command for command in commands if "pip install" in command]
    assert installs == [
        f"{runtime_python} -I -m pip install --no-index --no-deps --require-hashes --find-links vendor/sdk -r vendor/sdk/requirements.txt",
        f"{runtime_python} -I -m pip install --no-deps -r apps/runtime/ansible/requirements.lock",
    ]
    assert f"{runtime_python} -I -m pip check" in commands
    assert 'echo "ATLAS_TEST_RUNTIME_PYTHON=$RUNNER_TEMP/atlas-ci-runtime/bin/python" >> "$GITHUB_ENV"' in commands
    live_test = (ROOT / "apps/api/tests/test_i3_live_runtime.py").read_text()
    assert 'monkeypatch.setattr(jobs.sys, "executable", os.environ["ATLAS_TEST_RUNTIME_PYTHON"])' in live_test


def test_discovery_runtime_rejects_inherited_plugin_metadata_and_stale_packages(tmp_path):
    job = workflow()["jobs"]["backend"]
    step = next(step for step in job["steps"]
                if step.get("name") == "Install isolated pinned Ansible runtime for discovery acceptance")
    commands = step["run"].splitlines()
    environment = {
        **os.environ,
        "RUNNER_TEMP": str(tmp_path),
        "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
        "PYTHONPATH": job["env"]["PYTHONPATH"].replace("${{ github.workspace }}", str(ROOT)),
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PIP_NO_CACHE_DIR": "1",
    }

    def run(command):
        return subprocess.run(["bash", "-c", command], cwd=ROOT, env=environment,
                              capture_output=True, text=True, timeout=30)

    created = run(commands[0])
    assert created.returncode == 0, created.stdout + created.stderr
    check_command = next(command for command in commands if command.endswith(" -m pip check"))
    check_args = [argument.replace("$RUNNER_TEMP", str(tmp_path)) for argument in shlex.split(check_command)]
    isolated_python = check_args[:check_args.index("-m")]
    inspect = subprocess.run(isolated_python + ["-c", (
        "import json, site, sys, sysconfig; "
        "print(json.dumps({'prefix': sys.prefix, 'base_prefix': sys.base_prefix, "
        "'user_site': site.ENABLE_USER_SITE, 'path': sys.path, "
        "'purelib': sysconfig.get_path('purelib')}))"
    )], cwd=ROOT, env=environment, capture_output=True, text=True, check=True, timeout=30)
    state = json.loads(inspect.stdout)
    assert state["prefix"] != state["base_prefix"] and state["user_site"] is False
    assert not set(environment["PYTHONPATH"].split(os.pathsep)) & set(state["path"])
    assert "include-system-site-packages = false" in (tmp_path / "atlas-ci-runtime/pyvenv.cfg").read_text()

    # A reused directory must not retain packages outside the approved lock.
    stale = Path(state["purelib"]) / "atlas_ci_stale_runtime-0.1.dist-info"
    stale.mkdir()
    (stale / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: atlas-ci-stale-runtime\nVersion: 0.1\n"
        "Requires-Dist: atlas-ci-missing-dependency\n")
    assert run(check_command).returncode == 1
    recreated = run(commands[0])
    assert recreated.returncode == 0, recreated.stdout + recreated.stderr
    assert not stale.exists()

    # Reproduce the observed CI failure in the same fresh venv without -I.
    contaminated = run('"$RUNNER_TEMP/atlas-ci-runtime/bin/python" -m pip check')
    assert contaminated.returncode == 1
    assert "atlas-proxmox 0.1.0 requires httpx, which is not installed." in contaminated.stdout
    clean = run(check_command)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert "No broken requirements found." in clean.stdout


def test_frontend_uses_node22_lockfile_tests_and_build():
    ci = workflow()
    assert ci["env"]["NEXT_TELEMETRY_DISABLED"] == "1"
    job = ci["jobs"]["frontend"]
    assert job["defaults"]["run"]["working-directory"] == "apps/web"
    setup = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/setup-node@"))
    assert setup["with"] == {"node-version": "22", "cache": "npm", "cache-dependency-path": "apps/web/package-lock.json"}
    commands = [step["run"] for step in job["steps"] if "run" in step]
    assert commands == ["npm ci", "npm test", "npm run build"]
