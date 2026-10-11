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
    paths = {"health": "/v1/health", "capabilities": "/v1/capabilities", "verify_connector": "/v1/connectors/verify"}
    if operation not in paths:
        raise ValueError("Operation is unavailable in this release")
    endpoint, secret = _endpoint(), _control_secret()
    async with asyncio.timeout(TIMEOUT_SECONDS):
        async with aiohttp.ClientSession(trust_env=False, auto_decompress=False,
                cookie_jar=aiohttp.DummyCookieJar(), timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS),
                headers={"Authorization": f"Bearer {secret}", "Accept": "application/json", "Accept-Encoding": "identity"}) as session:
            async with session.request("POST" if reference is not None else "GET", endpoint + paths[operation],
                    json=reference, allow_redirects=False) as response:
                if response.status != 200 or response.content_type != "application/json":
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
                return payload


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
    if not isinstance(operations, list) or set(operations) != {"health", "capabilities", "verify_connector"}:
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

    async def test_connection(self, *args, **kwargs):
        raise NotImplementedError("Test Connection belongs to the next integration increment")

    async def start_discovery(self, *args, **kwargs):
        raise NotImplementedError("Discovery is unavailable in this release")

    async def get_job(self, *args, **kwargs):
        raise NotImplementedError("Discovery is unavailable in this release")

    async def cancel_job(self, *args, **kwargs):
        raise NotImplementedError("Discovery is unavailable in this release")


runtime = LocalIntegrationRuntime()
