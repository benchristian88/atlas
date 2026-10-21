"""Build/install-time preparation of the pinned verifier, never application startup.

An offline --archive must be the exact reviewed upstream distribution. The
runtime consumes only the fixed resulting path, and rechecks its binary digest.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import os
from pathlib import Path
import tarfile
import tempfile
import urllib.request
import zipfile

from app import attestation_distribution as distribution

MAX_ARCHIVE_BYTES = 32 * 1024 * 1024


def prepare(archive: Path | None = None) -> Path:
    lock = distribution.distribution_lock()
    distribution.checked_root(lock)
    key = distribution.platform_key()
    entry = lock["platforms"][key]
    # Optional operator-staged build input for disconnected installs/upgrades.
    # A present but corrupt cache fails; it never falls back to the network.
    cached = distribution.DISTRIBUTION / "archives" / entry["archive"]
    if archive is None and (cached.exists() or cached.is_symlink()):
        archive = cached
    if archive is not None:
        raw = distribution.regular_bytes(archive.absolute(), MAX_ARCHIVE_BYTES)
    else:
        # Fixed upstream origin; no credentials, proxy configuration or shell.
        url = f"https://github.com/cli/cli/releases/download/v{distribution.VERIFIER_VERSION}/{entry['archive']}"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=30) as response:
            raw = response.read(MAX_ARCHIVE_BYTES + 1)
    if len(raw) > MAX_ARCHIVE_BYTES or hashlib.sha256(raw).hexdigest() != entry["archive_sha256"]:
        raise ValueError("invalid_verifier_archive_digest")
    prefix = entry["archive"].removesuffix(".tar.gz").removesuffix(".zip")
    # Read exactly one regular member; never extract an upstream archive tree.
    if entry["archive"].endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(raw)) as source:
            candidates = [m for m in source.infolist() if m.filename == f"{prefix}/bin/gh"]
            if len(candidates) != 1 or candidates[0].file_size > distribution.MAX_BINARY_BYTES:
                raise ValueError("invalid_verifier_archive")
            with source.open(candidates[0]) as stream:
                binary = stream.read(distribution.MAX_BINARY_BYTES + 1)
    else:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as source:
            candidates = [m for m in source if m.name == f"{prefix}/bin/gh"]
            if len(candidates) != 1 or not candidates[0].isfile() or candidates[0].size > distribution.MAX_BINARY_BYTES:
                raise ValueError("invalid_verifier_archive")
            with source.extractfile(candidates[0]) as stream:
                binary = stream.read(distribution.MAX_BINARY_BYTES + 1)
    if len(binary) > distribution.MAX_BINARY_BYTES or hashlib.sha256(binary).hexdigest() != entry["binary_sha256"]:
        raise ValueError("invalid_verifier_binary_digest")
    target = distribution.DISTRIBUTION / "bin"
    if target.is_symlink():
        raise ValueError("unsafe_distribution_path")
    target.mkdir(mode=0o755, exist_ok=True)
    if not target.is_dir() or target.stat().st_mode & 0o022:
        raise ValueError("unsafe_distribution_path")
    fd, temporary = tempfile.mkstemp(prefix=".gh-", dir=target)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(binary)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), 0o555)
        os.replace(temporary, target / "gh")
    finally:
        Path(temporary).unlink(missing_ok=True)
    (distribution.DISTRIBUTION / "trusted-root.jsonl").chmod(0o444)
    return distribution.checked_binary(lock)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Offline, reviewed platform archive (no download)")
    args = parser.parse_args()
    try:
        prepare(args.archive)
    except (OSError, ValueError, KeyError, tarfile.TarError, zipfile.BadZipFile):
        parser.exit(1, "Pinned attestation verifier preparation failed; no unchecked verifier was accepted.\n")
    print(f"Pinned attestation verifier {distribution.VERIFIER_VERSION} prepared and integrity checked.")


if __name__ == "__main__":
    main()
