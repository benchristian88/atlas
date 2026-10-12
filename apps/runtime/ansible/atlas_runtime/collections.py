"""Atlas-owned, offline collection installation and installed-content verification.

This module is a packaging tool, never a Connector/control-plane operation.
Collection resolution uses a fixed path independent of HOME and inherited env.
"""
from __future__ import annotations

import hashlib
import gzip
import io
from itertools import islice
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import tarfile

ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS_PATH = ROOT / "collections"
NAME = re.compile(r"[a-z][a-z0-9_]{0,63}\.[a-z][a-z0-9_]{0,63}")
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?")
DIGEST = re.compile(r"[a-f0-9]{64}")


def execution_environment():
    return {"ANSIBLE_COLLECTIONS_PATH": str(COLLECTIONS_PATH),
            "ANSIBLE_COLLECTIONS_SCAN_SYS_PATH": "False"}


def _safe_name(name):
    if (not isinstance(name, str) or not name or "\\" in name
            or PurePosixPath(name).is_absolute()
            or any(part in {"", ".", ".."} for part in name.split("/"))):
        raise ValueError("invalid_collection_file")
    return name


def load_lock(root=ROOT):
    from .server import read_regular, MAX_METADATA
    raw = read_regular(root / "collections.lock.json", MAX_METADATA)
    lock = json.loads(raw)
    if lock.get("schema_version") != 1 or not isinstance(lock.get("collections"), list) or len(lock["collections"]) > 32:
        raise ValueError("invalid_collection_lock")
    names = set()
    for row in lock["collections"]:
        if (not NAME.fullmatch(row["name"]) or not VERSION.fullmatch(row["version"])
                or row["name"] in names or any(not DIGEST.fullmatch(row[key])
                    for key in ("sha256", "manifest_sha256", "files_sha256"))
                or _safe_name(row["archive"]) != PurePosixPath(row["archive"]).name):
            raise ValueError("invalid_collection_lock")
        names.add(row["name"])
    return raw, lock["collections"]


def _file_identities(row, manifest_raw, files_raw):
    if (hashlib.sha256(manifest_raw).hexdigest() != row["manifest_sha256"]
            or hashlib.sha256(files_raw).hexdigest() != row["files_sha256"]):
        raise ValueError("collection_identity_mismatch")
    manifest, files = json.loads(manifest_raw), json.loads(files_raw)
    info = manifest["collection_info"]
    if (f"{info['namespace']}.{info['name']}" != row["name"] or info["version"] != row["version"]
            or manifest["file_manifest_file"]["chksum_sha256"] != row["files_sha256"]):
        raise ValueError("collection_identity_mismatch")
    identities = {"MANIFEST.json": row["manifest_sha256"], "FILES.json": row["files_sha256"]}
    if len(files["files"]) > 256:
        raise ValueError("collection_file_limit")
    for entry in files["files"]:
        if entry["ftype"] == "dir":
            continue
        name = _safe_name(entry["name"])
        if (entry["ftype"] != "file" or name in identities or entry["chksum_type"] != "sha256"
                or not DIGEST.fullmatch(entry["chksum_sha256"])):
            raise ValueError("invalid_collection_manifest")
        identities[name] = entry["chksum_sha256"]
    return identities


def reviewed_archive(row, data):
    """Check bytes and every shipped file before installation or release packaging."""
    from .server import MAX_EXPANDED, MAX_FILE
    if hashlib.sha256(data).hexdigest() != row["sha256"]:
        raise ValueError("collection_archive_mismatch")
    # Galaxy's reviewed archive contains PAX metadata. It is only parsed after
    # the trusted archive digest matches, with a separate expansion bound.
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
        expanded = compressed.read(MAX_EXPANDED + 1)
    if len(expanded) > MAX_EXPANDED:
        raise ValueError("collection_expansion_limit")
    contents = {}
    with tarfile.open(fileobj=io.BytesIO(expanded), mode="r:") as archive:
        def materialise(member, visited):
            if member.name in visited or len(visited) >= 16 or not 0 <= member.size <= MAX_FILE:
                raise ValueError("invalid_collection_link")
            if member.isfile():
                return archive.extractfile(member).read(MAX_FILE + 1)
            if member.issym() or member.islnk():
                # The reviewed archive has internal licence/test links; install
                # their checked bytes as regular files, never filesystem links.
                target = member.linkname if member.islnk() else posixpath.join(posixpath.dirname(member.name), member.linkname)
                target = _safe_name(posixpath.normpath(target))
                return materialise(archive.getmember(target), visited | {member.name})
            raise ValueError("invalid_collection_archive")
        seen = set()
        for count, member in enumerate(archive, 1):
            name = _safe_name(member.name)
            if count > 256 or name in seen or not 0 <= member.size <= MAX_FILE:
                raise ValueError("collection_file_limit")
            seen.add(name)
            if member.isdir():
                continue
            contents[name] = materialise(member, set())
    identities = _file_identities(row, contents["MANIFEST.json"], contents["FILES.json"])
    if set(contents) != set(identities) or any(hashlib.sha256(contents[name]).hexdigest() != digest
                                             for name, digest in identities.items()):
        raise ValueError("collection_contents_mismatch")
    return contents


def installed_identity(row, path):
    """Report an archive identity only when *all* installed bytes match its lock."""
    from .server import read_regular, MAX_METADATA, MAX_FILE, MAX_EXPANDED
    actual = None
    try:
        manifest_raw = read_regular(path / "MANIFEST.json", MAX_METADATA)
        value = json.loads(manifest_raw)["collection_info"]["version"]
        actual = value if isinstance(value, str) and len(value) <= 128 and VERSION.fullmatch(value) else None
        identities = _file_identities(row, manifest_raw, read_regular(path / "FILES.json", MAX_METADATA))
        seen, total = set(), 0
        # Bounded walk; links and additional code cannot hide behind the manifest.
        entries = 0
        for current, directories, filenames in os.walk(path, followlinks=False):
            entries += len(directories) + len(filenames)
            if entries > 256 or any((Path(current) / name).is_symlink() for name in directories):
                raise ValueError("invalid_collection_tree")
            for name in filenames:
                file = Path(current) / name
                relative = file.relative_to(path).as_posix()
                if relative not in identities:
                    raise ValueError("collection_contents_mismatch")
                data = read_regular(file, MAX_FILE)
                total += len(data)
                if total > MAX_EXPANDED or hashlib.sha256(data).hexdigest() != identities[relative]:
                    raise ValueError("collection_contents_mismatch")
                seen.add(relative)
        if seen != set(identities):
            raise ValueError("collection_contents_mismatch")
        return {"version": actual, "digest": "sha256:" + row["sha256"], "state": "compatible"}
    except (OSError, ValueError, KeyError, TypeError):
        return {"version": actual, "digest": None, "state": "incompatible"}


def health(root=ROOT, path=COLLECTIONS_PATH):
    try:
        raw, rows = load_lock(root)
        identities = {row["name"]: installed_identity(row, path / "ansible_collections" / Path(*row["name"].split(".")))
                      for row in rows}
        registry = path / "ansible_collections"
        if registry.is_symlink():
            return None, identities
        count = 0
        if registry.exists():
            for namespace in islice(registry.iterdir(), 257):
                count += 1
                if count > 256 or namespace.is_symlink() or not namespace.is_dir():
                    return None, identities
                for collection in islice(namespace.iterdir(), 257):
                    count += 1
                    name = namespace.name + "." + collection.name
                    if (count > 256 or collection.is_symlink() or not collection.is_dir()
                            or not NAME.fullmatch(name) or len(identities) >= 32 and name not in identities):
                        return None, identities
                    if name not in identities:
                        identities[name] = {"version": None, "digest": None, "state": "incompatible"}
        return hashlib.sha256(raw).hexdigest(), identities
    except (OSError, ValueError, KeyError, TypeError):
        return None, {}


def install(source, root=ROOT, path=COLLECTIONS_PATH):
    from .server import read_regular, MAX_BUNDLE
    _, rows = load_lock(root)
    for row in rows:
        contents = reviewed_archive(row, read_regular(source / row["archive"], MAX_BUNDLE))
        destination = path / "ansible_collections" / Path(*row["name"].split("."))
        if any(part.is_symlink() for part in (destination, *destination.parents)):
            raise ValueError("invalid_collection_destination")
        if destination.exists():
            if installed_identity(row, destination)["state"] != "compatible":
                raise ValueError("existing_collection_mismatch")
            continue
        # Packaging runs as installation authority; runtime has no write access.
        for name, data in contents.items():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o444)
        for directory in sorted(destination.rglob("*"), reverse=True):
            if directory.is_dir():
                directory.chmod(0o555)
        destination.chmod(0o555)
        if installed_identity(row, destination)["state"] != "compatible":
            raise ValueError("collection_installation_mismatch")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("Expected reviewed archive directory")
    install(Path(sys.argv[1]))
