"""Private authenticated I1 health and package-inspection service.

There is deliberately no job, command, playbook, URL or installation operation.
"""
from __future__ import annotations

import hashlib
import gzip
import hmac
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
import threading

ROOT = Path(__file__).resolve().parents[1]
MAX_BODY = 4096
MAX_BUNDLE = 20 * 1024 * 1024
MAX_METADATA = 256 * 1024
MAX_FILES = 256
MAX_FILE = 10 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024
OPERATIONS = ["health", "capabilities", "verify_connector"]
IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
DIGEST = re.compile(r"^[a-f0-9]{64}$")


def read_regular(path: Path, maximum: int) -> bytes:
    """Refuse symlinks in every component and bound regular-file reads."""
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("unsafe_file")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise ValueError("invalid_file")
        value = source.read(maximum + 1)
        if len(value) > maximum:
            raise ValueError("invalid_file")
        return value


def load_secret(path: Path) -> str:
    value = read_regular(path, 256).decode("ascii").strip()
    if not re.fullmatch(r"[a-f0-9]{64,128}", value):
        raise ValueError("invalid_control_configuration")
    return value


def checked_archive(bundle: bytes):
    # tarfile consumes PAX/GNU extension records internally, before yielding a
    # member. Bound gzip expansion and inspect every raw header first.
    with gzip.GzipFile(fileobj=io.BytesIO(bundle)) as compressed:
        expanded = compressed.read(MAX_EXPANDED + MAX_FILES * 2048 + 10241)
    if len(expanded) > MAX_EXPANDED + MAX_FILES * 2048 + 10240:
        raise ValueError("archive_expansion_limit")
    position = count = 0
    while position < len(expanded):
        header = expanded[position:position + 512]
        if len(header) != 512:
            raise ValueError("truncated_archive")
        if not header.strip(b"\0"):
            if expanded[position:].strip(b"\0"):
                raise ValueError("trailing_archive_data")
            break
        entry = tarfile.TarInfo.frombuf(header, "utf-8", "strict")
        count += 1
        if (count > MAX_FILES or entry.size < 0 or entry.size > MAX_FILE
                or entry.type not in {tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE}
                or (entry.isdir() and entry.size != 0)):
            raise ValueError("archive_member_limit")
        position += 512 + ((entry.size + 511) // 512) * 512
        if position > len(expanded):
            raise ValueError("truncated_archive")
    return tarfile.open(fileobj=io.BytesIO(expanded), mode="r:")


class Runtime:
    def __init__(self, secret: str, store: Path, packaging_mode: str):
        self._secret = secret
        self.store = store
        if packaging_mode not in {"docker_compose", "systemd", "development"}:
            raise ValueError("invalid_packaging_mode")
        self.packaging_mode = packaging_mode

    def authenticate(self, authorization: str) -> bool:
        return hmac.compare_digest(authorization.encode("utf-8"), ("Bearer " + self._secret).encode("utf-8"))

    def health(self):
        raw = read_regular(ROOT / "baseline.json", MAX_METADATA)
        baseline = json.loads(raw)
        dependencies = {}
        for name, expected in baseline["dependencies"].items():
            try:
                dependencies[name] = version(name)
            except PackageNotFoundError:
                dependencies[name] = None
        matches = dependencies == baseline["dependencies"]
        matches = matches and hashlib.sha256(read_regular(ROOT / "requirements.lock", MAX_METADATA)).hexdigest() == baseline["dependency_lock_digest"]
        return {
            "state": "healthy" if matches else "incompatible",
            "runtime_version": baseline["runtime_version"],
            "protocol_version": baseline["protocol_version"],
            "baseline_id": baseline["baseline_id"],
            "baseline_version": baseline["baseline_version"],
            "baseline_digest": hashlib.sha256(raw).hexdigest(),
            "dependency_lock_digest": baseline["dependency_lock_digest"],
            "packaging_mode": self.packaging_mode,
            "ansible_core_version": dependencies.get("ansible-core"),
            "ansible_runner_version": dependencies.get("ansible-runner"),
            "diagnostic_code": None if matches else "baseline_dependency_mismatch",
            "dependencies": dependencies,
            "collections": baseline["collections"],
        }

    def capabilities(self):
        return {**self.health(), "operations": OPERATIONS, "aip_versions": ["1.0"]}

    def verify_connector(self, reference):
        if not isinstance(reference, dict) or set(reference) != {"connector_id", "version", "digest"}:
            raise ValueError("invalid_reference")
        if (not isinstance(reference["connector_id"], str) or len(reference["connector_id"]) > 128
                or not IDENTIFIER.fullmatch(reference["connector_id"])
                or not isinstance(reference["version"], str) or len(reference["version"]) > 128
                or not SEMVER.fullmatch(reference["version"])
                or not isinstance(reference["digest"], str) or not DIGEST.fullmatch(reference["digest"])):
            raise ValueError("invalid_reference")
        directory = self.store / reference["connector_id"] / reference["version"] / reference["digest"]
        result = {**reference, "state": "unavailable", "diagnostic_code": "package_unavailable"}
        try:
            bundle = read_regular(directory / "bundle.tar.gz", MAX_BUNDLE)
            manifest = json.loads(read_regular(directory / "manifest.json", MAX_METADATA))
            receipt = json.loads(read_regular(directory / "verification.json", MAX_METADATA))
            if (hashlib.sha256(bundle).hexdigest() != reference["digest"]
                    or manifest.get("id") != reference["connector_id"]
                    or manifest.get("version") != reference["version"]
                    or manifest.get("distribution", {}).get("bundle_digest") != "sha256:" + reference["digest"]
                    or any(receipt.get(key) != value for key, value in reference.items())
                    or receipt.get("verification", {}).get("bundle_digest") != "sha256:" + reference["digest"]
                    or receipt.get("status") != "verified"):
                return {**result, "diagnostic_code": "package_verification_failed"}
            files = receipt.get("files")
            if not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES:
                raise ValueError("invalid_receipt")
            embedded = {}
            total = 0
            members = 0
            domain_manifest = None
            with checked_archive(bundle) as archive:
                for member in archive:
                    parts = PurePosixPath(member.name)
                    members += 1
                    name = member.name.rstrip("/") if member.isdir() else member.name
                    if (not (member.isfile() or member.isdir()) or parts.is_absolute() or "\\" in name
                            or any(part in {"", ".", ".."} for part in name.split("/"))
                            or name in embedded or members > MAX_FILES
                            or (member.isdir() and member.size != 0)
                            or not 0 <= member.size <= MAX_FILE):
                        raise ValueError("unsafe_archive")
                    if member.isdir():
                        continue
                    total += member.size
                    if total > MAX_EXPANDED:
                        raise ValueError("unsafe_archive")
                    content = archive.extractfile(member).read(MAX_FILE + 1)
                    if len(content) != member.size:
                        raise ValueError("unsafe_archive")
                    embedded[member.name] = "sha256:" + hashlib.sha256(content).hexdigest()
                    if member.name == "manifest.json":
                        domain_manifest = json.loads(content)
            if embedded != files or domain_manifest != {key: value for key, value in manifest.items() if key != "distribution"}:
                raise ValueError("changed_manifest")
            seen = set()
            total = 0
            contents = directory / "contents"
            if contents.is_symlink() or not contents.is_dir():
                raise ValueError("unsafe_file")
            entries = 0
            for current, directories, filenames in os.walk(contents, followlinks=False):
                entries += len(directories) + len(filenames)
                if entries > MAX_FILES:
                    raise ValueError("changed_contents")
                for name in directories:
                    if (Path(current) / name).is_symlink():
                        raise ValueError("unsafe_file")
                for name in filenames:
                    path = Path(current) / name
                    name = path.relative_to(contents).as_posix()
                    if name not in files:
                        raise ValueError("changed_contents")
                    content = read_regular(path, MAX_FILE)
                    total += len(content)
                    if total > MAX_EXPANDED or "sha256:" + hashlib.sha256(content).hexdigest() != files[name]:
                        raise ValueError("changed_contents")
                    seen.add(name)
            if seen != set(files):
                raise ValueError("changed_contents")
            # This is inspection only. No caller-selected entry point is executed.
            return {**reference, "state": "verified", "diagnostic_code": None}
        except (OSError, ValueError, TypeError, AttributeError, tarfile.TarError, EOFError):
            return result


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "AtlasRuntime"
    sys_version = ""

    def log_message(self, *_arguments):
        pass  # Never log paths, headers, payloads or control credentials.

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def respond(self, status, payload):
        value = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(value)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(value)
        self.close_connection = True

    def handle_operation(self, method):
        runtime = self.server.runtime
        credentials = self.headers.get_all("Authorization") or []
        if len(credentials) != 1 or not runtime.authenticate(credentials[0]):
            self.respond(401, {"diagnostic_code": "unauthorized"})
            return
        if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length") or []) > 1:
            self.respond(400, {"diagnostic_code": "invalid_request"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 <= size <= MAX_BODY:
                self.respond(413, {"diagnostic_code": "request_too_large"})
                return
            if method == "GET" and size:
                raise ValueError("invalid_request")
            if method == "GET" and self.path == "/v1/health":
                payload = runtime.health()
            elif method == "GET" and self.path == "/v1/capabilities":
                payload = runtime.capabilities()
            elif method == "POST" and self.path == "/v1/connectors/verify":
                if self.headers.get("Content-Type") != "application/json":
                    raise ValueError("invalid_request")
                payload = runtime.verify_connector(json.loads(self.rfile.read(size)))
            else:
                self.respond(404, {"diagnostic_code": "unsupported_operation"})
                return
            self.respond(200, payload)
        except (ValueError, TypeError, UnicodeError):
            self.respond(400, {"diagnostic_code": "invalid_request"})
        except OSError:
            self.respond(503, {"diagnostic_code": "runtime_unavailable"})

    def do_GET(self):
        self.handle_operation("GET")

    def do_POST(self):
        self.handle_operation("POST")


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, address, runtime):
        self.runtime = runtime
        self._slots = threading.BoundedSemaphore(32)
        super().__init__(address, Handler)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


def main():
    mode = os.environ.get("ATLAS_RUNTIME_PACKAGING_MODE", "systemd")
    # Native binding is deliberately independent of inherited host configuration.
    host = "0.0.0.0" if mode == "docker_compose" else "127.0.0.1"
    try:
        secret = load_secret(Path(os.environ["ATLAS_RUNTIME_CONTROL_SECRET_FILE"]))
        runtime = Runtime(secret, Path(os.environ.get("ATLAS_CONNECTOR_STORE_PATH", "/var/lib/atlas-connectors")), mode)
        Server((host, 8091), runtime).serve_forever()
    except (OSError, ValueError, KeyError):
        raise SystemExit("Runtime control configuration is unavailable or invalid") from None


if __name__ == "__main__":
    main()
