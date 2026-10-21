"""Single release-owned verifier distribution contract (also used by packaging).

No environment or caller override can select the executable or roots. Supported
deployments keep this tree root-owned; a development checkout trusts its owner.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat

DISTRIBUTION = Path(__file__).resolve().parent / "attestation"
VERIFIER_VERSION = "2.102.1"
MAX_BINARY_BYTES = 64 * 1024 * 1024
MAX_ROOT_BYTES = 128 * 1024


def platform_key() -> str:
    machine = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine())
    system = platform.system().lower()
    if system not in {"linux", "darwin"} or machine is None:
        raise ValueError("unsupported_verifier_platform")
    return f"{system}-{machine}"


def regular_bytes(path: Path, maximum: int) -> bytes:
    # Refuse links, FIFOs/devices and group/world-writable distribution paths.
    # Sticky /tmp ancestors are permitted for isolated development/CI checkouts.
    if not path.is_absolute():
        raise ValueError("unsafe_distribution_path")
    for parent in (path, *path.parents):
        info = parent.lstat()
        if stat.S_ISLNK(info.st_mode) or (info.st_mode & 0o022 and not (
                parent != path and info.st_uid == 0 and info.st_mode & stat.S_ISVTX)):
            raise ValueError("unsafe_distribution_path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise ValueError("invalid_distribution_file")
        raw = stream.read(maximum + 1)
        if len(raw) > maximum:
            raise ValueError("invalid_distribution_file")
        return raw


def distribution_lock() -> dict:
    try:
        lock = json.loads(regular_bytes(DISTRIBUTION / "distribution.json", 16 * 1024))
    except (ValueError, RecursionError):
        raise ValueError("invalid_verifier_distribution") from None
    if not isinstance(lock, dict) or lock.get("version") != VERIFIER_VERSION:
        raise ValueError("unsupported_verifier_version")
    if (lock.keys() != {"version", "release", "root_id", "root_sha256", "platforms"}
            or lock["release"] != f"https://github.com/cli/cli/releases/tag/v{VERIFIER_VERSION}"
            or not isinstance(lock["root_id"], str)
            or re.fullmatch(r"sigstore-public-good-[0-9]{4}-[0-9]{2}-[0-9]{2}", lock["root_id"]) is None
            or not isinstance(lock["root_sha256"], str)
            or re.fullmatch(r"[a-f0-9]{64}", lock["root_sha256"]) is None
            or not isinstance(lock["platforms"], dict)
            or lock["platforms"].keys() != {"linux-amd64", "linux-arm64", "darwin-amd64", "darwin-arm64"}):
        raise ValueError("invalid_verifier_distribution")
    for key, entry in lock["platforms"].items():
        system, machine = key.split("-")
        upstream = ("macOS" if system == "darwin" else "linux") + "_" + machine
        archive = f"gh_{VERIFIER_VERSION}_{upstream}" + (".zip" if system == "darwin" else ".tar.gz")
        if (not isinstance(entry, dict) or entry.keys() != {"archive", "archive_sha256", "binary_sha256"}
                or entry["archive"] != archive
                or any(not isinstance(entry[name], str) or re.fullmatch(r"[a-f0-9]{64}", entry[name]) is None
                       for name in ("archive_sha256", "binary_sha256"))):
            raise ValueError("invalid_verifier_distribution")
    return lock


def checked_root(lock: dict) -> bytes:
    raw = regular_bytes(DISTRIBUTION / "trusted-root.jsonl", MAX_ROOT_BYTES)
    if hashlib.sha256(raw).hexdigest() != lock["root_sha256"]:
        raise ValueError("invalid_trust_root")
    return raw


def checked_binary(lock: dict) -> Path:
    binary = DISTRIBUTION / "bin/gh"
    raw = regular_bytes(binary, MAX_BINARY_BYTES)
    if hashlib.sha256(raw).hexdigest() != lock["platforms"][platform_key()]["binary_sha256"]:
        raise ValueError("invalid_verifier_digest")
    if not os.access(binary, os.X_OK) or binary.stat().st_mode & 0o222:
        raise ValueError("unsafe_verifier_permissions")
    return binary
