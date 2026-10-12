"""One verified Test Connection invocation with bounded private materialisation."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile

from atlas_connector_sdk.configuration import validate_configuration

from .collections import execution_environment

TIMEOUT = 22
CATEGORIES = {"connected", "authentication_failed", "permission_limited", "tls_trust_required", "timeout",
    "source_unavailable", "unsafe_endpoint", "redirect_rejected", "response_too_large", "invalid_source_response",
    "invalid_configuration", "invalid_credentials", "package_unavailable", "runtime_unavailable"}


def safe_capability_diagnostics(value, credentials=()):
    """Generic bounded identifiers only; no source paths, payloads or free text."""
    import re
    if not isinstance(value, list) or len(value) > 16:
        return []
    result = []
    for row in value:
        if (not isinstance(row, dict) or set(row) - {"capability", "state", "privilege", "path_category"}
                or not {"capability", "state", "path_category"} <= set(row)
                or any(not isinstance(item, str) for item in row.values())
                or row["state"] not in {"ready", "permission_limited", "unproven", "source_unavailable"}
                or row["path_category"] not in {"root", "inventory", "topology", "authorization"}
                or any(not isinstance(row[key], str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", row[key])
                       for key in {"capability", "privilege"} & row.keys())
                or any(secret and secret in value for value in row.values() if isinstance(value, str) for secret in credentials)):
            return []
        result.append(dict(row))
    return result


def safe_result(value, credentials=()):
    if not isinstance(value, dict) or type(value.get("success")) is not bool or value.get("category") not in CATEGORIES:
        return {"success": False, "category": "source_unavailable", "source_version": None}
    import re
    source = value.get("source_version")
    if (not isinstance(source, str) or not re.fullmatch(r"[0-9][A-Za-z0-9.+_-]{0,99}", source)
            or any(secret and secret in source for secret in credentials)):
        source = None
    result = {"success": value["success"], "category": value["category"], "source_version": source}
    if value.get("tls") in {"verify", "fingerprint", "insecure"}:
        result["tls"] = value["tls"]
    if type(value.get("permission_limited")) is bool:
        result["permission_limited"] = value["permission_limited"]
    if "capability_diagnostics" in value:
        result["capability_diagnostics"] = safe_capability_diagnostics(value["capability_diagnostics"], credentials)
    return result


def workspace_root():
    root = Path(tempfile.gettempdir()).resolve() / "atlas-runtime-probes"
    if root.is_symlink():
        raise ValueError("unsafe_workspace")
    root.mkdir(mode=0o700, exist_ok=True)
    if root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077:
        raise ValueError("unsafe_workspace")
    return root


def cleanup_stale():
    root = workspace_root()
    for path in root.iterdir():
        if path.name.startswith("probe-") and path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)


def execute(runtime, payload):
    from atlas_runtime.server import read_regular, MAX_FILE
    if not isinstance(payload, dict) or set(payload) != {"reference", "request_id", "config", "credentials"}:
        raise ValueError("invalid_request")
    import uuid
    uuid.UUID(payload["request_id"])
    reference = payload["reference"]
    if runtime.verify_connector(reference)["state"] != "verified":
        return {"success": False, "category": "package_unavailable", "source_version": None}
    directory = runtime.store / reference["connector_id"] / reference["version"] / reference["digest"]
    manifest = json.loads(read_regular(directory / "manifest.json", 256 * 1024))
    if (manifest["source_versions"]["qualification"] == "example"
            or manifest["implementation"]["entry_points"].get("test_connection") != "test_connection"
            or manifest["capabilities"]["test_connection"] is not True):
        raise ValueError("invalid_capability")
    values = payload["credentials"]
    config = validate_configuration(manifest, payload["config"], values)
    if runtime.health()["state"] != "healthy":
        return {"success": False, "category": "runtime_unavailable", "source_version": None}
    with tempfile.TemporaryDirectory(prefix="probe-", dir=workspace_root()) as temporary:
        root = Path(temporary)
        project = root / "project"
        project.mkdir(mode=0o700)
        # Copy only the independently verified package, never a caller path.
        for path in (directory / "contents").rglob("*"):
            relative = path.relative_to(directory / "contents")
            target = project / relative
            if path.is_dir():
                target.mkdir(mode=0o700, parents=True, exist_ok=True)
            else:
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                target.write_bytes(read_regular(path, MAX_FILE))
                target.chmod(0o600)
        if not (project / "test_connection.yml").is_file():
            return {"success": False, "category": "package_unavailable", "source_version": None}
        environment = {**execution_environment(), "PATH": str(Path(sys.executable).parent) + ":/usr/bin:/bin", "HOME": temporary,
            "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
        process = None
        try:
            process = subprocess.Popen([sys.executable, "-m", "atlas_runtime.probe_worker", temporary],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=environment, start_new_session=True)
            process.communicate(json.dumps({"config": config, "credentials": values}).encode(), timeout=TIMEOUT)
            result = json.loads(read_regular(root / "result.json", 8192))
            return safe_result(result, values.values())
        except subprocess.TimeoutExpired:
            return {"success": False, "category": "timeout", "source_version": None}
        except (OSError, ValueError):
            return {"success": False, "category": "source_unavailable", "source_version": None}
        finally:
            if process is not None:
                from atlas_runtime.jobs import stop_process
                stop_process(process)
            # TemporaryDirectory removes inputs, Ansible artifacts and output on
            # every outcome. SIGKILL/reboot remnants are removed at startup.
