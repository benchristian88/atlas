"""Bounded, authenticated local control transport; no execution/domain imports."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit

import aiohttp
from pydantic import BaseModel, ConfigDict, ValidationError

TIMEOUT_SECONDS = 3
MAX_RESPONSE_BYTES = 65536
PROTOCOL = "integration-runtime-v1"
_IDENTITY = re.compile(r"[A-Za-z0-9._+-]{1,128}")
_DIGEST = re.compile(r"[a-f0-9]{64}")


class RuntimeHealth(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    state: str
    runtime_version: str
    protocol_version: str
    baseline_id: str
    baseline_version: str
    baseline_digest: str
    dependency_lock_digest: str
    packaging_mode: str
    ansible_core_version: str | None
    ansible_runner_version: str | None
    diagnostic_code: str | None = None
    dependencies: dict[str, str | None]
    collections: dict


def _approved_baseline() -> dict:
    path = Path(os.getenv("ATLAS_RUNTIME_BASELINE_FILE") or
                Path(__file__).resolve().parents[3] / "runtime/ansible/baseline.json")
    raw = path.read_bytes()
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("Invalid baseline")
    baseline = json.loads(raw)
    return {**baseline, "baseline_digest": hashlib.sha256(raw).hexdigest()}


def _control_secret() -> str:
    # Installation configuration only; no user/API-selected filesystem path.
    path = os.getenv("ATLAS_RUNTIME_CONTROL_SECRET_FILE", "")
    if not path:
        raise ValueError("Runtime authentication unavailable")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o037:
            raise ValueError("Runtime authentication unavailable")
        raw = stream.read(257)
    value = raw.decode("ascii").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", value):
        raise ValueError("Runtime authentication unavailable")
    return value


def _endpoint() -> str:
    value = os.getenv("ATLAS_RUNTIME_URL", "http://127.0.0.1:8091")
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1", "runtime"}
            or parsed.port != 8091 or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ValueError("Only the default local runtime is supported")
    if os.getenv("ATLAS_INSTALL_METHOD") == "systemd" and parsed.hostname == "runtime":
        raise ValueError("Native runtime must use loopback")
    return value.rstrip("/")


async def control_request(operation: str, reference: dict | None = None) -> dict:
    paths = {"health": "/v1/health", "capabilities": "/v1/capabilities", "verify_connector": "/v1/connectors/verify", "test_connection": "/v1/connectors/test-connection",
        "run_discovery": "/v1/discovery/start", "get_job": "/v1/discovery/status", "cancel_job": "/v1/discovery/cancel"}
    if operation not in paths:
        raise ValueError("Operation is unavailable in this release")
    endpoint, secret = _endpoint(), _control_secret()
    timeout = 28 if operation == "test_connection" else TIMEOUT_SECONDS
    async with asyncio.timeout(timeout):
        async with aiohttp.ClientSession(trust_env=False, auto_decompress=False,
                cookie_jar=aiohttp.DummyCookieJar(), timeout=aiohttp.ClientTimeout(total=timeout),
                headers={"Authorization": f"Bearer {secret}", "Accept": "application/json", "Accept-Encoding": "identity"}) as session:
            async with session.request("POST" if reference is not None else "GET", endpoint + paths[operation],
                    json=reference, allow_redirects=False) as response:
                if response.content_type != "application/json":
                    raise ValueError("Runtime control unavailable")
                remaining, chunks = MAX_RESPONSE_BYTES, []
                async for chunk in response.content.iter_chunked(8192):
                    remaining -= len(chunk)
                    if remaining < 0:
                        raise ValueError("Invalid runtime response")
                    chunks.append(chunk)
                payload = json.loads(b"".join(chunks))
                if not isinstance(payload, dict):
                    raise ValueError("Invalid runtime response")
                if response.status != 200:
                    code = payload.get("diagnostic_code")
                    if code in {"runtime_capacity", "conflicting_request", "package_unavailable", "discovery_unavailable"}:
                        raise RuntimeControlError(code)
                    raise ValueError("Runtime control unavailable")
                return payload


class RuntimeControlError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _safe_health(payload: dict, capabilities: dict, baseline: dict) -> dict:
    health = RuntimeHealth.model_validate(payload)
    for field in ("runtime_version", "protocol_version", "baseline_id", "baseline_version", "packaging_mode"):
        if not _IDENTITY.fullmatch(getattr(health, field)):
            raise ValueError("Invalid runtime identity")
    for field in ("baseline_digest", "dependency_lock_digest"):
        if not _DIGEST.fullmatch(getattr(health, field)):
            raise ValueError("Invalid runtime identity")
    for value in (health.ansible_core_version, health.ansible_runner_version):
        if value is not None and not _IDENTITY.fullmatch(value):
            raise ValueError("Invalid dependency identity")
    if health.state not in {"healthy", "incompatible"} or health.packaging_mode not in {"systemd", "docker_compose", "development"}:
        raise ValueError("Invalid runtime state")
    operations = capabilities.get("operations")
    if not isinstance(operations, list) or set(operations) not in ({"health", "capabilities", "verify_connector"}, {"health", "capabilities", "verify_connector", "test_connection"},
            {"health", "capabilities", "verify_connector", "test_connection", "run_discovery", "get_job", "cancel_job"}):
        raise ValueError("Invalid runtime capabilities")
    aip = capabilities.get("aip_versions")
    dependencies = capabilities.get("dependencies")
    collections = capabilities.get("collections")
    if aip != ["1.0"] or not isinstance(dependencies, dict) or collections != {}:
        raise ValueError("Invalid runtime capabilities")
    compatible = (health.protocol_version == PROTOCOL
        and health.baseline_id == baseline["baseline_id"]
        and health.baseline_version == baseline["baseline_version"]
        and health.baseline_digest == baseline["baseline_digest"]
        and health.runtime_version == baseline["runtime_version"]
        and health.dependency_lock_digest == baseline["dependency_lock_digest"]
        and health.dependencies == baseline["dependencies"]
        and health.ansible_core_version == baseline["dependencies"]["ansible-core"]
        and health.ansible_runner_version == baseline["dependencies"]["ansible-runner"]
        and dependencies == health.dependencies
        and health.collections == baseline["collections"])
    # The runtime also checks its actual installed distributions against its lock.
    # Allow-listed return fields prevent arbitrary private response data leaking.
    result = health.model_dump(exclude={"state", "diagnostic_code", "dependencies", "collections"})
    result.update(status="healthy" if compatible and health.state == "healthy" else "incompatible",
        last_error=None if compatible and health.state == "healthy" else "runtime_baseline_mismatch",
        capabilities={"operations": sorted(operations), "aip_versions": aip,
            "dependencies": baseline["dependencies"] if compatible else {}, "collections": {}},
        baseline_version=baseline.get("baseline_version", "1.0.0"))
    capacity = capabilities.get("discovery_capacity")
    if capacity is not None:
        if (not isinstance(capacity, dict) or set(capacity) != {"maximum", "active", "available"}
                or any(type(value) is not int for value in capacity.values())
                or capacity["maximum"] != 4 or not 0 <= capacity["active"] <= 4
                or capacity["available"] != 4 - capacity["active"]):
            raise ValueError("Invalid runtime capacity")
        result["capabilities"]["discovery_capacity"] = capacity
    return result


class LocalIntegrationRuntime:
    async def health(self) -> dict:
        result = dict(status="unavailable", runtime_version=None, protocol_version=None,
            baseline_id=None, baseline_digest=None, dependency_lock_digest=None, packaging_mode=None,
            ansible_core_version=None, ansible_runner_version=None, capabilities={}, last_error="runtime_unavailable")
        if os.getenv("ATLAS_RUNTIME_ENABLED", "true").lower() in {"false", "0", "no"}:
            result.update(status="disabled", last_error=None)
        else:
            try:
                baseline = _approved_baseline()
                async with asyncio.timeout(TIMEOUT_SECONDS):
                    health = await control_request("health")
                    capabilities = await control_request("capabilities")
                result = _safe_health(health, capabilities, baseline)
            except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError,
                    ValidationError, aiohttp.ClientError, TimeoutError):
                # Never reflect endpoint, credential, transport error or stack trace.
                pass
        result["last_checked_at"] = datetime.now(timezone.utc).isoformat()
        return result

    async def verify_connector(self, reference: dict) -> dict:
        try:
            result = await control_request("verify_connector", reference)
            if set(result) - {"state", "connector_id", "version", "digest", "diagnostic_code"}:
                raise ValueError("Invalid connector response")
            if any(result.get(key) != value for key, value in reference.items()):
                raise ValueError("Connector identity mismatch")
            if result.get("state") not in {"verified", "unavailable", "incompatible"}:
                raise ValueError("Invalid connector response")
            return {**reference, "state": result["state"]}
        except (OSError, ValueError, TypeError, UnicodeError, RecursionError, aiohttp.ClientError, TimeoutError):
            return {**reference, "state": "unavailable"}

    async def test_connection(self, reference, config, credentials, request_id):
        try:
            result = await control_request("test_connection", {"reference": reference, "request_id": str(request_id),
                "config": config, "credentials": credentials})
            # Fixed result fields only; never expose runtime/vendor text.
            categories = {"connected", "authentication_failed", "permission_limited", "tls_trust_required", "timeout", "source_unavailable", "unsafe_endpoint", "redirect_rejected", "response_too_large", "invalid_source_response", "invalid_configuration", "invalid_credentials", "package_unavailable", "runtime_unavailable"}
            if type(result.get("success")) is not bool or result.get("category") not in categories:
                raise ValueError
            source = result.get("source_version")
            if not isinstance(source, str) or not re.fullmatch(r"[0-9][A-Za-z0-9.+_-]{0,99}", source) or any(value and value in source for value in credentials.values()):
                source = None
            return {"success": result["success"], "category": result["category"], "source_version": source,
                "tls": result.get("tls") if result.get("tls") in {"verify", "fingerprint", "insecure"} else None,
                "permission_limited": result.get("permission_limited") is True}
        except (OSError, ValueError, TypeError, aiohttp.ClientError, TimeoutError):
            return {"success": False, "category": "runtime_unavailable", "source_version": None}

    async def _job(self, operation, payload):
        import uuid
        try:
            result = await control_request(operation, payload)
            if result == {"state": "unavailable", "diagnostic_code": "job_unavailable"}:
                return result
            if set(result) != {"request_id", "job_id", "state", "accepted_at", "started_at", "finished_at", "diagnostic_code"}:
                raise ValueError
            if result["request_id"] != str(payload["request_id"]) or str(uuid.UUID(result["job_id"])) != result["job_id"]:
                raise ValueError
            if payload.get("job_id") and result["job_id"] != payload["job_id"]:
                raise ValueError
            if result["state"] not in {"queued", "running", "succeeded", "failed", "cancelled"}:
                raise ValueError
            if result["diagnostic_code"] not in {None, "cancelled", "timeout", "invalid_aip", "missing_completion",
                    "callback_unavailable", "callback_rejected", "source_unavailable", "runtime_unavailable"}:
                raise ValueError
            for name in ["accepted_at", "started_at", "finished_at"]:
                if result[name] is not None:
                    if not isinstance(result[name], str) or len(result[name]) > 40:
                        raise ValueError
                    datetime.fromisoformat(result[name])
            return result
        except RuntimeControlError as error:
            return {"state": "unavailable", "diagnostic_code": error.code}
        except (OSError, ValueError, TypeError, KeyError, aiohttp.ClientError, TimeoutError):
            return {"state": "unavailable", "diagnostic_code": "runtime_unavailable"}

    async def run_discovery(self, request):
        return await self._job("run_discovery", request)

    start_discovery = run_discovery

    async def get_job(self, request_id, job_id=None):
        return await self._job("get_job", {"request_id": str(request_id), "job_id": str(job_id) if job_id else None})

    async def cancel_job(self, request_id, job_id=None):
        return await self._job("cancel_job", {"request_id": str(request_id), "job_id": str(job_id) if job_id else None})


runtime = LocalIntegrationRuntime()
