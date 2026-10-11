"""I1 control failure isolation, authorization and non-disclosure regressions."""
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import secrets
import uuid

from fastapi.testclient import TestClient
import pytest

from app.authorization import ActiveContext, get_active_context, get_principal
from app.database import get_db
from app.main import app
from app.services import integration_runtime as transport
from app.services.connector_lifecycle import ConnectorInUse, require_unused
from tests.test_administration import make_principal


class EmptyDB:
    def rollback(self):
        pass

    def scalars(self, _):
        return []

    def execute(self, _):
        return []

    def get(self, *_):
        raise AssertionError("Unauthorized ID must not reach a database lookup")


@pytest.fixture
def client(monkeypatch):
    async def unavailable():
        return {"status": "unavailable", "last_checked_at": "2026-10-11T04:00:00+00:00", "last_error": "runtime_unavailable"}
    monkeypatch.setattr(transport.runtime, "health", unavailable)
    app.dependency_overrides[get_db] = lambda: EmptyDB()
    app.dependency_overrides[get_active_context] = lambda: ActiveContext(None, None)
    with TestClient(app) as instance:
        yield instance
    app.dependency_overrides.clear()


def grant(*keys, scope="global"):
    principal = make_principal(*keys)
    if scope != "global":
        principal = replace(principal, grants=(replace(principal.grants[0], scope_type=scope,
            customer_id=uuid.uuid4(), site_id=uuid.uuid4() if scope == "site" else None),))
    app.dependency_overrides[get_principal] = lambda: principal
    return principal


@pytest.mark.parametrize("path", ["/api/integration-runtime", "/api/installed-connectors", "/api/installed-connectors/hidden"])
def test_ordinary_user_cannot_inspect_global_runtime_or_packages(client, path):
    grant("integrations.view", "integrations.manage")
    assert client.get(path).status_code == 403


@pytest.mark.parametrize("scope", ["customer", "site"])
def test_runtime_permissions_in_scoped_grant_cannot_manage_global_code(client, scope):
    grant("integration_runtime.view", "integration_runtime.manage", scope=scope)
    assert client.get("/api/integration-runtime").status_code == 403
    assert client.get("/api/installed-connectors/hidden").status_code == 403
    response = client.post("/api/integration-catalogue/proxmox/install", json={"version": "1.0.0", "digest": "a" * 64})
    assert response.status_code == 403
    assert client.delete("/api/installed-connectors/hidden").status_code == 403


def test_scoped_integrations_manage_does_not_authorize_package_install(client):
    grant("integrations.view", "integrations.manage", scope="customer")
    response = client.post("/api/integration-catalogue/proxmox/install", json={"version": "1.0.0", "digest": "a" * 64})
    assert response.status_code == 403


def test_offline_bootstrap_real_entries_remain_visible_during_runtime_outage(client, monkeypatch):
    grant("integrations.view", scope="site")
    def forbidden_network(*_args, **_kwargs):
        raise AssertionError("Bootstrap catalogue must not use network")
    monkeypatch.setattr("aiohttp.ClientSession", forbidden_network)
    response = client.get("/api/integration-catalogue")
    assert response.status_code == 200
    entries = response.json()["entries"]
    assert {entry["connector_id"] for entry in entries} == {"proxmox", "docker", "unifi-network"}
    probe = next(entry for entry in entries if entry["connector_id"] == "proxmox")
    assert probe["package_available"] and not probe["supported_actions"] and probe["state"] == "runtime_unavailable"
    assert probe["source_versions"]["qualification"] == "unqualified"
    assert all(not entry["package_available"] for entry in entries if entry["connector_id"] != "proxmox")
    assert "secret" not in response.text.lower()
    assert "/Users/" not in response.text and "/var/lib/" not in response.text
    assert client.get("/api/health").json() == {"status": "ok"}


def test_admin_health_is_safe_normal_unavailable_state(client):
    grant("integration_runtime.view")
    response = client.get("/api/integration-runtime")
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["installed_connector_count"] == 0
    assert response.headers["cache-control"] == "no-store"


def test_missing_package_cannot_activate_example_manifest(client):
    grant("integration_runtime.manage")
    response = client.post("/api/integration-catalogue/proxmox/install", json={"version": "0.0.0-i0", "digest": "a" * 64})
    assert response.status_code == 409
    assert "code" in response.json()["detail"]


def test_package_request_cannot_accept_or_echo_execution_or_sensitive_input(client):
    grant("integration_runtime.manage")
    private = secrets.token_hex(32)
    response = client.post("/api/integration-catalogue/proxmox/install", json={
        "version": "1.0.0", "digest": "a" * 64, "path": "../../escape", "command": "id", "credential": private})
    assert response.status_code == 422
    assert private not in response.text and "../../escape" not in response.text


def test_unknown_catalogue_identity_is_not_filesystem_address(client):
    grant("integrations.view")
    assert client.get("/api/integration-catalogue/unknown").status_code == 404
    assert client.get("/api/integration-catalogue/%2E%2E%5Cescape").status_code == 404


def test_all_live_usage_including_disabled_blocks_uninstall_and_injected_guard():
    with pytest.raises(ConnectorInUse):
        require_unused(object(), "example", usage_counter=lambda *_: 1)
    require_unused(object(), "example", usage_counter=lambda *_: 0)


def raw_runtime():
    baseline = transport._approved_baseline()
    health = {key: baseline[key] for key in ("runtime_version", "protocol_version", "baseline_id", "baseline_version", "baseline_digest", "dependency_lock_digest", "dependencies", "collections")}
    health.update(state="healthy", packaging_mode="development", ansible_core_version=baseline["dependencies"]["ansible-core"],
        ansible_runner_version=baseline["dependencies"]["ansible-runner"], diagnostic_code=None)
    capabilities = {**health, "operations": ["health", "capabilities", "verify_connector"], "aip_versions": ["1.0"]}
    return health, capabilities


def test_default_client_accepts_only_exact_approved_runtime(monkeypatch):
    health, capabilities = raw_runtime()
    async def request(operation, *_):
        return health if operation == "health" else capabilities
    monkeypatch.setattr(transport, "control_request", request)
    result = asyncio.run(transport.LocalIntegrationRuntime().health())
    assert result["status"] == "healthy"
    health["baseline_digest"] = "b" * 64
    result = asyncio.run(transport.LocalIntegrationRuntime().health())
    assert result["status"] == "incompatible"


def test_unapproved_dependency_map_cannot_claim_healthy(monkeypatch):
    health, capabilities = raw_runtime()
    health["dependencies"] = {**health["dependencies"], "unapproved": "1.0.0"}
    async def request(operation, *_):
        return health if operation == "health" else capabilities
    monkeypatch.setattr(transport, "control_request", request)
    result = asyncio.run(transport.LocalIntegrationRuntime().health())
    assert result["status"] == "incompatible"
    assert "unapproved" not in json.dumps(result)


def test_private_runtime_response_is_never_forwarded_unvalidated(monkeypatch):
    private = secrets.token_hex(32)
    health, capabilities = raw_runtime()
    health["control_secret"] = private
    async def request(operation, *_):
        return health if operation == "health" else capabilities
    monkeypatch.setattr(transport, "control_request", request)
    result = asyncio.run(transport.LocalIntegrationRuntime().health())
    assert result["status"] == "unavailable" and private not in json.dumps(result)


def test_transport_error_never_discloses_credentials_or_endpoint(monkeypatch):
    private = secrets.token_hex(32)
    async def request(*_):
        raise OSError(private + " at /private/runtime/path")
    monkeypatch.setattr(transport, "control_request", request)
    result = asyncio.run(transport.LocalIntegrationRuntime().health())
    assert result["status"] == "unavailable"
    assert private not in json.dumps(result) and "/private/" not in json.dumps(result)


def test_manual_only_opt_out_skips_all_control_calls(monkeypatch):
    monkeypatch.setenv("ATLAS_RUNTIME_ENABLED", "false")
    async def forbidden(*_):
        raise AssertionError("Disabled runtime must not be contacted")
    monkeypatch.setattr(transport, "control_request", forbidden)
    assert asyncio.run(transport.LocalIntegrationRuntime().health())["status"] == "disabled"


@pytest.mark.parametrize("url", ["https://runtime:8091", "http://192.0.2.1:8091", "http://runtime:8091/path", "http://user:password@runtime:8091", "http://runtime:8091/?token=private", "http://runtime:8092"])
def test_no_remote_or_browser_selected_runtime_mode(monkeypatch, url):
    monkeypatch.setenv("ATLAS_RUNTIME_URL", url)
    with pytest.raises(ValueError):
        transport._endpoint()


def test_control_secret_missing_unsafe_permissions_and_symlink_fail_closed(monkeypatch, tmp_path):
    monkeypatch.delenv("ATLAS_RUNTIME_CONTROL_SECRET_FILE", raising=False)
    with pytest.raises(ValueError):
        transport._control_secret()
    path = tmp_path / "control.secret"
    path.write_text(secrets.token_hex(32))
    monkeypatch.setenv("ATLAS_RUNTIME_CONTROL_SECRET_FILE", str(path))
    path.chmod(0o644)
    with pytest.raises(ValueError):
        transport._control_secret()
    path.chmod(0o600)
    assert len(transport._control_secret()) == 64
    link = tmp_path / "link.secret"
    link.symlink_to(path)
    monkeypatch.setenv("ATLAS_RUNTIME_CONTROL_SECRET_FILE", str(link))
    with pytest.raises(OSError):
        transport._control_secret()


def test_later_runtime_operations_are_explicitly_unsupported():
    for name in ("start_discovery", "get_job", "cancel_job"):
        with pytest.raises(NotImplementedError):
            asyncio.run(getattr(transport.LocalIntegrationRuntime(), name)())


@pytest.mark.parametrize("suffix,method", [("/credentials", "put"), ("/credentials", "delete"), ("/test-connection", "post"), ("", "patch")])
def test_i2_non_manager_and_non_runner_cannot_reach_credential_or_probe_lookups(client, suffix, method):
    grant("integrations.view")
    response = client.request(method.upper(), "/api/integrations/" + str(uuid.uuid4()) + suffix, json={})
    assert response.status_code == 403


def test_i2_invalid_credential_payload_never_echoes_values_or_execution_arguments(client):
    grant("integrations.manage")
    value = secrets.token_urlsafe(32)
    response = client.put("/api/integrations/" + str(uuid.uuid4()) + "/credentials", json={"values": {"token_secret": value}, "playbook": "/tmp/forbidden"})
    assert response.status_code == 422
    assert value not in response.text and "/tmp/forbidden" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/api/integration-secrets/" + str(uuid.uuid4())).status_code == 404
