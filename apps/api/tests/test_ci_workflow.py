"""Protect the routine CI boundary and its complete regression configuration."""
import ast
from pathlib import Path
import re

import yaml

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


def test_frontend_uses_node22_lockfile_tests_and_build():
    ci = workflow()
    assert ci["env"]["NEXT_TELEMETRY_DISABLED"] == "1"
    job = ci["jobs"]["frontend"]
    assert job["defaults"]["run"]["working-directory"] == "apps/web"
    setup = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/setup-node@"))
    assert setup["with"] == {"node-version": "22", "cache": "npm", "cache-dependency-path": "apps/web/package-lock.json"}
    commands = [step["run"] for step in job["steps"] if "run" in step]
    assert commands == ["npm ci", "npm test", "npm run build"]
