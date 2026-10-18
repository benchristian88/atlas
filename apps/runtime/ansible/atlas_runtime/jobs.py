"""Bounded ephemeral verified jobs. Atlas owns every durable run decision."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

from atlas_connector_sdk.aip import body_hash, validate_batch
from atlas_connector_sdk.configuration import validate_configuration
from atlas_connector_sdk.contracts import strict_json

from .collections import execution_environment
from .diagnostics import read_trace

MAX_JOB_SECONDS = 600
MAX_BATCH_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 32 * 1024 * 1024
MAX_BATCHES = 256
TERMINAL = {"succeeded", "failed", "cancelled"}


def now():
    return datetime.now(timezone.utc).isoformat()


def workspace_root():
    root = Path(tempfile.gettempdir()).resolve() / "atlas-runtime-discovery"
    if root.is_symlink():
        raise ValueError("unsafe_workspace")
    root.mkdir(mode=0o700, exist_ok=True)
    if root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077:
        raise ValueError("unsafe_workspace")
    return root


def cleanup_stale():
    for path in workspace_root().iterdir():
        if path.name.startswith("job-") and path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)


@dataclass(repr=False)
class Job:
    request_id: str
    body_digest: str
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: str = "queued"
    accepted_at: str = field(default_factory=now)
    started_at: str | None = None
    finished_at: str | None = None
    diagnostic_code: str | None = None
    diagnostics: dict | None = field(default=None, repr=False)
    debug_deleted: bool = False
    cancel: threading.Event = field(default_factory=threading.Event)
    process: object = None
    thread: object = None
    deadline: float = 0

    def response(self):
        value = {name: getattr(self, name) for name in ["request_id", "job_id", "state", "accepted_at",
            "started_at", "finished_at", "diagnostic_code"]}
        if self.state in TERMINAL and self.diagnostics is not None:
            value["diagnostics"] = self.diagnostics
        return value


def stop_process(process):
    if process is not None:
        # Ansible worker processes call setsid(). Freeze and collect the bounded
        # descendant tree before killing its root, otherwise orphaned sessions
        # can escape the wrapper's process group. psutil preserves PID identity.
        import psutil
        descendants = []
        try:
            root = psutil.Process(process.pid)
            root.suspend()
            known = {}
            for _ in range(3):
                children = root.children(recursive=True)
                if len(children) > 128:
                    raise ValueError("runtime_process_limit")
                for child in children:
                    try:
                        child.suspend()
                        known[(child.pid, child.create_time())] = child
                    except psutil.NoSuchProcess:
                        pass
            descendants = list(known.values())
            for child in reversed(descendants):
                try: child.kill()
                except psutil.NoSuchProcess: pass
            root.kill()
        except psutil.NoSuchProcess:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=2)
        if descendants:
            psutil.wait_procs(descendants, timeout=.5)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def send_callback(mode, run_id, operation, token, message, cancelled):
    # Deployment-owned routing, no user/Connector URL or proxy authority.
    base = "http://api:8000" if mode == "docker_compose" else "http://127.0.0.1:8000"
    url = f"{base}/api/integration-ingestion/{run_id}/{operation}"
    payload = json.dumps(message, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    if len(payload) > MAX_BATCH_BYTES:
        raise ValueError("invalid_aip")
    opener = build_opener(ProxyHandler({}), NoRedirect())
    for attempt in range(3):
        if cancelled.is_set():
            raise ValueError("cancelled")
        try:
            request = Request(url, data=payload, method="POST", headers={
                "Content-Type": "application/json", "Authorization": "Bearer " + token})
            with opener.open(request, timeout=5) as response:
                if response.status != 200 or response.headers.get_content_type() != "application/json":
                    raise ValueError("callback_rejected")
                if len(response.read(4097)) > 4096:
                    raise ValueError("callback_rejected")
            return
        except ValueError:
            raise
        except Exception as error:
            from urllib.error import HTTPError, URLError
            if isinstance(error, HTTPError) and error.code < 500:
                raise ValueError("callback_rejected") from None
            if not isinstance(error, (HTTPError, URLError, OSError, TimeoutError)) or attempt == 2:
                raise ValueError("callback_unavailable") from None
            cancelled.wait(2 ** attempt)


class Jobs:
    def __init__(self, runtime):
        self.runtime = runtime
        self.lock = threading.RLock()
        self.slots = threading.BoundedSemaphore(4)
        self.by_request = {}

    def start(self, payload):
        from atlas_runtime.server import read_regular
        values = payload.get("credentials") if isinstance(payload, dict) else None
        try:
            if (not isinstance(payload, dict) or set(payload) - {"debug_enabled"} != {"request_id", "run_id", "integration_id",
                    "reference", "config", "credentials", "selected_scopes", "object_classes", "coverage", "ingestion_token", "timeout_seconds"}):
                raise ValueError("invalid_request")
            if type(payload.get("debug_enabled", False)) is not bool:
                raise ValueError("invalid_request")
            for name in ["request_id", "run_id", "integration_id"]:
                if str(uuid.UUID(payload[name])) != payload[name]:
                    raise ValueError("invalid_request")
            if payload["request_id"] != payload["run_id"]:
                raise ValueError("invalid_request")
            if (type(payload["timeout_seconds"]) is not int or not 60 <= payload["timeout_seconds"] <= MAX_JOB_SECONDS
                    or not isinstance(payload["ingestion_token"], str) or not 1 <= len(payload["ingestion_token"]) <= 4096):
                raise ValueError("invalid_request")
            reference = payload["reference"]
            if self.runtime.verify_connector(reference)["state"] != "verified":
                raise ValueError("package_unavailable")
            directory = self.runtime.store / reference["connector_id"] / reference["version"] / reference["digest"]
            manifest = strict_json(read_regular(directory / "manifest.json", 256 * 1024))
            if (manifest["capabilities"]["discover"] != "read_only"
                    or manifest["implementation"]["entry_points"].get("discover") != "discover"
                    or manifest["source_versions"]["qualification"] == "example"
                    or not (directory / "contents/discover.yml").is_file()):
                raise ValueError("discovery_unavailable")
            validate_configuration(manifest, payload["config"], values)
            scopes = {row["key"]: row for row in manifest["discovery_scopes"]}
            selected = payload["selected_scopes"]
            if (not isinstance(selected, list) or not selected or len(selected) > 16
                    or len(set(selected)) != len(selected) or not set(selected) <= scopes.keys()
                    or any(row["required"] and name not in selected for name, row in scopes.items())):
                raise ValueError("invalid_request")
            coverage = payload["coverage"]
            classes = payload["object_classes"]
            declared_classes = {name for key in selected for name in scopes[key]["object_classes"]}
            required_classes = {row["key"] for row in manifest["object_classes"] if row["required"] and row["key"] in declared_classes}
            if (not isinstance(classes, list) or any(not isinstance(name, str) for name in classes)
                    or len(set(classes)) != len(classes) or not set(classes) <= declared_classes or not required_classes <= set(classes)):
                raise ValueError("invalid_request")
            domains = sorted({name for key in selected for name in scopes[key]["domains"]})
            if (not isinstance(coverage, dict) or set(coverage) != {"key", "snapshot_mode", "domains"}
                    or coverage.get("domains") != domains or coverage.get("snapshot_mode") not in {"full", "partial"}
                    or not isinstance(coverage.get("key"), str) or not 1 <= len(coverage["key"]) <= 1024):
                raise ValueError("invalid_request")
            if self.runtime.health()["state"] != "healthy":
                raise ValueError("runtime_unavailable")
            digest = body_hash(payload)
            with self.lock:
                existing = self.by_request.get(payload["request_id"])
                if existing:
                    if existing.body_digest != digest:
                        raise ValueError("conflicting_request")
                    return existing.response()
                # Retain replay authority until well beyond the longest token.
                self.prune()
                if len(self.by_request) >= 128 or not self.slots.acquire(blocking=False):
                    raise ValueError("runtime_capacity")
                job = Job(payload["request_id"], digest, deadline=time.monotonic() + payload["timeout_seconds"])
                self.by_request[job.request_id] = job
                # Copy sensitive material only into this one private invocation.
                invocation = {**payload, "credentials": dict(values)}
                job.thread = threading.Thread(target=self.execute, args=(job, invocation, directory, manifest), daemon=True)
                try:
                    job.thread.start()
                except Exception:
                    self.by_request.pop(job.request_id, None)
                    invocation["credentials"].clear()
                    self.slots.release()
                    raise
                return job.response()
        finally:
            if isinstance(values, dict):
                values.clear()

    def get(self, payload, *, cancel=False):
        if (not isinstance(payload, dict) or set(payload) - {"delete_debug"} != {"request_id", "job_id"}
                or type(payload.get("delete_debug", False)) is not bool):
            raise ValueError("invalid_request")
        str(uuid.UUID(payload["request_id"]))
        if payload["job_id"] is not None:
            str(uuid.UUID(payload["job_id"]))
        with self.lock:
            job = self.by_request.get(payload["request_id"])
            if job is None or payload["job_id"] is not None and job.job_id != payload["job_id"]:
                return {"state": "unavailable", "diagnostic_code": "job_unavailable"}
            if payload.get("delete_debug"):
                job.debug_deleted = True
                if job.diagnostics is not None:
                    job.diagnostics = {**job.diagnostics, "debug_events": []}
            if cancel and job.state not in TERMINAL:
                job.cancel.set()
                # Connector child is killed immediately; execution thread owns
                # bounded reaping/cleanup and publishes terminal state afterward.
                if job.process is not None:
                    stop_process(job.process)
            return job.response()

    def execute(self, job, payload, directory, manifest):
        from atlas_runtime.server import read_regular, MAX_FILE
        code, state = "source_unavailable", "failed"
        trace_fd = None
        try:
            with tempfile.TemporaryDirectory(prefix="job-", dir=workspace_root()) as temporary:
                root = Path(temporary)
                trace_path = root / "diagnostics.ndjson"
                trace_fd = os.open(trace_path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
                info = os.fstat(trace_fd)
                trace_identity = (info.st_dev, info.st_ino)
                def collect_trace():
                    value = read_trace(trace_fd, trace_path, trace_identity,
                        debug=payload.get("debug_enabled", False),
                        secrets=[*payload["credentials"].values(), payload["ingestion_token"], self.runtime._secret])
                    with self.lock:
                        job.diagnostics = {**value, "debug_events": []} if job.debug_deleted else value
                project = root / "project"
                project.mkdir(mode=0o700)
                for path in (directory / "contents").rglob("*"):
                    target = project / path.relative_to(directory / "contents")
                    if path.is_dir():
                        target.mkdir(mode=0o700, parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                        target.write_bytes(read_regular(path, MAX_FILE))
                        target.chmod(0o600)
                if job.cancel.is_set():
                    raise ValueError("cancelled")
                environment = {**execution_environment(), "PATH": str(Path(sys.executable).parent) + ":/usr/bin:/bin", "HOME": temporary,
                    "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
                with self.lock:
                    job.started_at, job.state = now(), "running"
                    job.process = subprocess.Popen([sys.executable, "-m", "atlas_runtime.discovery_worker", temporary],
                        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        env=environment, start_new_session=True)
                try:
                    # The ingestion token remains in this parent; the Connector
                    # produces AIP through a private file and receives no API/control credential.
                    inputs = {name: value for name, value in payload.items() if name not in {"ingestion_token", "request_id"}}
                    job.process.communicate(json.dumps(inputs, allow_nan=False).encode(), timeout=payload["timeout_seconds"] - 30)
                    if job.cancel.is_set():
                        raise ValueError("cancelled")
                    if job.process.returncode != 0:
                        raise ValueError("source_unavailable")
                    stop_process(job.process)
                    job.process = None
                    collect_trace()
                    if job.diagnostics["processing_errors"]:
                        raise ValueError("invalid_diagnostics")
                    raw = read_regular(root / "aip.ndjson", MAX_OUTPUT_BYTES)
                    lines = raw.splitlines()
                    if not 1 <= len(lines) <= MAX_BATCHES + 1:
                        raise ValueError("invalid_aip")
                    completion = None
                    for line in lines:
                        if job.cancel.is_set():
                            raise ValueError("cancelled")
                        if time.monotonic() >= job.deadline:
                            raise ValueError("timeout")
                        message = strict_json(line, maximum=MAX_BATCH_BYTES)
                        validate_batch(message, manifest)
                        def strings(value):
                            if isinstance(value, str):
                                yield value
                            elif isinstance(value, dict):
                                for child in value.values():
                                    yield from strings(child)
                            elif isinstance(value, list):
                                for child in value:
                                    yield from strings(child)
                        if any(secret and secret in value for value in strings(message)
                                for secret in [*payload["credentials"].values(), payload["ingestion_token"]]):
                            raise ValueError("invalid_aip")
                        if (message["run_id"] != payload["run_id"] or message["integration_id"] != payload["integration_id"]
                                or message["coverage"] != payload["coverage"]):
                            raise ValueError("invalid_aip")
                        if message["message_type"] == "completion":
                            if completion is not None:
                                raise ValueError("invalid_aip")
                            completion = message
                        elif completion is not None:
                            raise ValueError("invalid_aip")
                        else:
                            self.callback(job, payload, "batches", message, environment)
                    if completion is None:
                        raise ValueError("missing_completion")
                    if (completion.get("completeness") == "complete" and
                            (job.diagnostics["counts"]["warning"] or job.diagnostics["counts"]["error"])):
                        raise ValueError("invalid_diagnostics")
                    operation = "completion" if completion["status"] == "completed" else "failure"
                    self.callback(job, payload, operation, completion, environment)
                    state, code = ("succeeded", None) if completion["status"] == "completed" else ("failed", "source_unavailable")
                except subprocess.TimeoutExpired:
                    raise ValueError("timeout") from None
                finally:
                    stop_process(job.process)
                    collect_trace()
                    os.close(trace_fd)
                    trace_fd = None
        except ValueError as error:
            allowed = {"cancelled", "timeout", "invalid_aip", "invalid_diagnostics", "missing_completion", "callback_unavailable", "callback_rejected", "source_unavailable"}
            code = str(error) if str(error) in allowed else "invalid_aip"
            state = "cancelled" if job.cancel.is_set() else "failed"
        except (OSError, TypeError, KeyError, subprocess.SubprocessError):
            code, state = "runtime_unavailable", "failed"
        finally:
            if trace_fd is not None:
                os.close(trace_fd)
            payload["credentials"].clear()
            payload.clear()
            with self.lock:
                job.process = None
                job.state = "cancelled" if job.cancel.is_set() else state
                job.diagnostic_code = "cancelled" if job.cancel.is_set() else code
                job.finished_at = now()
            self.slots.release()

    def callback(self, job, payload, operation, message, environment):
        remaining = job.deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("timeout")
        # Isolating transport in a private child also bounds DNS and cancellation.
        with self.lock:
            if job.cancel.is_set():
                raise ValueError("cancelled")
            job.process = subprocess.Popen([sys.executable, "-m", "atlas_runtime.callback_worker"],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=environment, start_new_session=True)
        try:
            job.process.communicate(json.dumps({"mode": self.runtime.packaging_mode, "run_id": payload["run_id"],
                "operation": operation, "token": payload["ingestion_token"], "message": message}, allow_nan=False).encode(),
                timeout=min(20, remaining))
            if job.cancel.is_set():
                raise ValueError("cancelled")
            if job.process.returncode != 0:
                raise ValueError("callback_unavailable")
        except subprocess.TimeoutExpired:
            raise ValueError("callback_unavailable") from None
        finally:
            stop_process(job.process)
            job.process = None

    def capacity(self):
        with self.lock:
            active = sum(job.state not in TERMINAL for job in self.by_request.values())
        return {"maximum": 4, "active": active, "available": 4 - active}

    def prune(self):
        # The existing server lifecycle calls this even when no new run arrives.
        # Transient control results (including debug data) never become a store.
        with self.lock:
            for key, previous in list(self.by_request.items()):
                if previous.finished_at and time.time() - datetime.fromisoformat(previous.finished_at).timestamp() > 1800:
                    del self.by_request[key]

    def shutdown(self):
        with self.lock:
            jobs = list(self.by_request.values())
        for job in jobs:
            if job.state not in TERMINAL:
                self.get({"request_id": job.request_id, "job_id": job.job_id}, cancel=True)
        for job in jobs:
            if job.thread:
                job.thread.join(timeout=6)
