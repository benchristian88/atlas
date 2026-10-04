"""Canonical release policy shared by runtime and standard-library tooling."""
from __future__ import annotations

from functools import total_ordering
import json
import os
from pathlib import Path
import re

OFFICIAL_REPOSITORY = "benchristian88/atlas"
REPOSITORY_URL = f"https://github.com/{OFFICIAL_REPOSITORY}"
RELEASE_API_URL = f"https://api.github.com/repos/{OFFICIAL_REPOSITORY}/releases"
INSTALL_METHODS = {"docker_compose", "systemd", "development"}
CHANNELS = {"beta", "stable"}
_VERSION = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)


@total_ordering
class Version:
    """SemVer precedence; build identifiers deliberately do not affect order."""

    def __init__(self, value: str):
        if not isinstance(value, str) or len(value) > 64:
            raise ValueError("Version must be a SemVer string of at most 64 characters")
        match = _VERSION.fullmatch(value)
        if not match:
            raise ValueError("Version must follow SemVer (major.minor.patch)")
        self.core = tuple(int(match[i]) for i in (1, 2, 3))
        self.prerelease = tuple(match[4].split(".")) if match[4] else ()
        if any(part.isdecimal() and len(part) > 1 and part.startswith("0") for part in self.prerelease):
            raise ValueError("Numeric prerelease identifiers cannot have leading zeroes")

    def __eq__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return (self.core, self.prerelease) == (other.core, other.prerelease)

    def __lt__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        if self.core != other.core:
            return self.core < other.core
        if not self.prerelease or not other.prerelease:
            return bool(self.prerelease) and not other.prerelease
        for left, right in zip(self.prerelease, other.prerelease):
            if left == right:
                continue
            if left.isdecimal() and right.isdecimal():
                return int(left) < int(right)
            if left.isdecimal() != right.isdecimal():
                return left.isdecimal()
            return left < right
        return len(self.prerelease) < len(other.prerelease)


def validate_metadata(metadata: dict) -> dict:
    if not isinstance(metadata, dict) or set(metadata) - {"version", "release_channel", "build_id", "install_method"}:
        raise ValueError("Invalid canonical release metadata fields")
    version = Version(metadata.get("version"))
    channel = metadata.get("release_channel")
    if not isinstance(channel, str) or channel not in CHANNELS:
        raise ValueError("Release channel must be beta or stable")
    if version.prerelease and (channel != "beta" or not re.fullmatch(r"beta\.(0|[1-9][0-9]*)", ".".join(version.prerelease))):
        raise ValueError("Only beta.<number> prereleases in the beta channel are supported")
    build = metadata.get("build_id")
    if build is not None and (not isinstance(build, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", build)):
        raise ValueError("Invalid build identity")
    method = metadata.get("install_method")
    if method is not None and (not isinstance(method, str) or method not in INSTALL_METHODS):
        raise ValueError("Unsupported artifact installation method")
    return {**metadata, "build_id": build}


def parse_metadata(raw: str | bytes) -> dict:
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate canonical release metadata field")
            result[key] = value
        return result
    return validate_metadata(json.loads(raw, object_pairs_hook=unique_pairs))


def load_metadata(path: Path | None = None) -> dict:
    return parse_metadata((path or Path(__file__).with_name("release.json")).read_text())


def validate_tag(metadata: dict, tag: str) -> None:
    validate_metadata(metadata)
    if tag != f"v{metadata['version']}":
        raise ValueError("Release tag must exactly match canonical metadata: v<version>")


def release_order(version: str, channel: str):
    return Version(version), 1 if channel == "stable" else 0


def build_metadata() -> dict:
    metadata = load_metadata()
    # Packaged identity wins over a stale .env build ID retained during upgrade.
    method = metadata.get("install_method") or os.getenv("ATLAS_INSTALL_METHOD", "development")
    if method not in INSTALL_METHODS:
        raise RuntimeError("Unsupported ATLAS_INSTALL_METHOD")
    return {
        **metadata,
        "build_id": metadata["build_id"] or os.getenv("ATLAS_BUILD_ID") or None,
        "install_method": method,
    }
