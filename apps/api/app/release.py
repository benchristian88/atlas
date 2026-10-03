"""Artifact-carried application identity; never needs Git at runtime."""
import json
import os
from pathlib import Path

INSTALL_METHODS = {"docker_compose", "systemd", "development"}


def build_metadata() -> dict:
    metadata = json.loads(Path(__file__).with_name("release.json").read_text())
    method = os.getenv("ATLAS_INSTALL_METHOD", "development")
    if method not in INSTALL_METHODS:
        raise RuntimeError("Unsupported ATLAS_INSTALL_METHOD")
    return {
        **metadata,
        "build_id": os.getenv("ATLAS_BUILD_ID") or metadata["build_id"],
        "install_method": method,
    }
