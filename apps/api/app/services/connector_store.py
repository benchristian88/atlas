"""Trusted, bounded immutable package staging; DB owns active identity."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tarfile
import uuid

from app.release import Version
from app.services.connector_contracts import ConnectorPackageError, strict_json, validate_manifest
from app.services.connector_verification import BundleVerifier, verify_digest

MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
MAX_EXPANDED_BYTES = 64 * 1024 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_MEMBERS = 256
MAX_PATH_LENGTH = 255


class PackageStoreError(ConnectorPackageError):
    pass


@dataclass(frozen=True)
class StoredPackage:
    connector_id: str
    version: str
    bundle_digest: str
    manifest: dict
    verification: dict

    def safe_metadata(self) -> dict:
        return {"connector_id": self.connector_id, "version": self.version,
                "bundle_digest": self.bundle_digest,
                "manifest_version": self.manifest["manifest_version"],
                "publisher_id": self.manifest["publisher"]["id"],
                "trust_tier": "atlas_official", "verification_status": "verified",
                "verification_evidence": self.verification}


@dataclass(frozen=True)
class QuarantineToken:
    name: str
    connector_id: str
    version: str
    bundle_digest: str


@dataclass(frozen=True)
class ConnectorQuarantineToken:
    name: str
    connector_id: str


def _connector_identity(connector_id: str) -> None:
    if not isinstance(connector_id, str) or len(connector_id) > 100 or not re.fullmatch(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*", connector_id):
        raise PackageStoreError("invalid_package_identity")


def _identity(connector_id: str, version: str, digest: str) -> None:
    _connector_identity(connector_id)
    try:
        Version(version)
    except ValueError:
        raise PackageStoreError("invalid_package_identity") from None
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
        raise PackageStoreError("invalid_package_identity")


def _safe_member(name: str) -> PurePosixPath:
    if (not isinstance(name, str) or not name or len(name) > MAX_PATH_LENGTH
            or "\\" in name or ":" in name or any(ord(char) < 32 for char in name)):
        raise PackageStoreError("unsafe_archive_path")
    pieces = name.rstrip("/").split("/")
    if name.startswith("/") or any(piece in ("", ".", "..") for piece in pieces):
        raise PackageStoreError("unsafe_archive_path")
    if pieces[0] in {"collections", "ansible_collections"}:
        raise PackageStoreError("runtime_owned_collection_path")
    return PurePosixPath(*pieces)


def _without_links(path: Path) -> None:
    # Runtime cannot write these ancestors in supported deployments. Also reject
    # pre-existing links instead of resolving them to a possibly hostile target.
    for part in (path, *path.parents):
        if part.is_symlink():
            raise PackageStoreError("unsafe_store_path")


def _preflight_tar(decoded: bytes) -> None:
    """Check plain USTAR headers before tarfile processes hidden extensions.

    I1 accepts regular files and empty directories only. PAX/GNU extended,
    sparse and special records are outside the deterministic package format;
    rejecting them before parsing also bounds their internal metadata reads.
    """
    offset, count = 0, 0
    while offset < len(decoded):
        header = decoded[offset:offset + tarfile.BLOCKSIZE]
        if len(header) != tarfile.BLOCKSIZE:
            raise PackageStoreError("invalid_archive_header")
        if header == b"\0" * tarfile.BLOCKSIZE:
            return
        try:
            member = tarfile.TarInfo.frombuf(header, "utf-8", "strict")
        except (tarfile.HeaderError, UnicodeError, ValueError):
            raise PackageStoreError("invalid_archive_header") from None
        count += 1
        if count > MAX_MEMBERS:
            raise PackageStoreError("archive_file_limit")
        if member.type not in {tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE}:
            raise PackageStoreError("unsafe_archive_member")
        if member.isdir() and member.size != 0:
            raise PackageStoreError("unsafe_archive_directory")
        if member.size < 0 or member.size > MAX_FILE_BYTES:
            raise PackageStoreError("archive_file_size_limit")
        offset += tarfile.BLOCKSIZE + ((member.size + tarfile.BLOCKSIZE - 1) // tarfile.BLOCKSIZE) * tarfile.BLOCKSIZE
        if offset > len(decoded):
            raise PackageStoreError("invalid_archive_file")


def _read_regular(path: Path, maximum: int) -> bytes:
    _without_links(path)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
                raise PackageStoreError("package_file_invalid")
            raw = stream.read(maximum + 1)
            if len(raw) > maximum:
                raise PackageStoreError("package_file_too_large")
            return raw
    except OSError:
        raise PackageStoreError("package_file_unavailable") from None


def _write(path: Path, raw: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o444)


def _delete_tree(path: Path) -> None:
    _without_links(path)
    if not path.exists():
        return
    # Only the trusted installer makes immutable directories writable for their
    # removal. Runtime mounts/permissions never expose this operation to it.
    for directory, subdirs, _ in os.walk(path, followlinks=False):
        current = Path(directory)
        _without_links(current)
        for subdir in subdirs:
            if (current / subdir).is_symlink():
                raise PackageStoreError("unsafe_store_path")
        current.chmod(0o700)
    shutil.rmtree(path)


class PackageStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        if not self.root.is_absolute():
            raise PackageStoreError("unsafe_store_path")
        _without_links(self.root)

    def _path(self, connector_id: str, version: str, digest: str) -> Path:
        _identity(connector_id, version, digest)
        path = self.root / connector_id / version / digest.removeprefix("sha256:")
        _without_links(path)
        return path

    @contextmanager
    def _lock(self):
        try:
            _without_links(self.root)
            self.root.mkdir(mode=0o755, parents=True, exist_ok=True)
            lock_path = self.root / ".install.lock"
            descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, "a+b") as stream:
                try:
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise PackageStoreError("package_operation_in_progress") from None
                yield
                fcntl.flock(stream, fcntl.LOCK_UN)
        except OSError:
            raise PackageStoreError("protected_store_unavailable") from None

    def install(self, package, verifier: BundleVerifier) -> StoredPackage:
        if not package.package_available or package.archive_path is None:
            raise PackageStoreError("package_not_released")
        _identity(package.connector_id, package.version, package.bundle_digest)
        if package.source == "operator-qualification":
            from app.services.connector_qualification import authorize
            authorize(self.root, package.manifest)
        else:
            validate_manifest(package.manifest, activation=True)
        if (package.manifest["id"] != package.connector_id or package.manifest["version"] != package.version
                or package.manifest["distribution"]["bundle_digest"] != package.bundle_digest):
            raise PackageStoreError("package_identity_mismatch")
        raw = _read_regular(package.archive_path, MAX_ARCHIVE_BYTES)
        # Independently compute the digest even when a verifier is supplied.
        verify_digest(raw, package.bundle_digest)
        evidence = verifier.verify(raw, package).safe_metadata() | {"status": "verified"}
        if package.source == "operator-qualification":
            authorize(self.root, package.manifest, evidence)
        if (evidence.get("bundle_digest") != package.bundle_digest
                or evidence.get("publisher_id") != package.manifest["publisher"]["id"]):
            raise PackageStoreError("verification_identity_mismatch")
        target = self._path(package.connector_id, package.version, package.bundle_digest)
        # Native installers stage immutable approved bytes as root. Activation
        # can verify an existing exact tuple without obtaining filesystem write
        # authority; this does not install missing or unverified packages.
        if target.exists():
            self.verify_connector(package.connector_id, package.version, package.bundle_digest)
            return StoredPackage(package.connector_id, package.version, package.bundle_digest,
                                 package.manifest, evidence)
        with self._lock():
            target = self._path(package.connector_id, package.version, package.bundle_digest)
            if target.exists():
                self.verify_connector(package.connector_id, package.version, package.bundle_digest)
                return StoredPackage(package.connector_id, package.version, package.bundle_digest,
                                     package.manifest, evidence)
            stage = self.root / (".stage-" + uuid.uuid4().hex)
            stage.mkdir(mode=0o700)
            try:
                contents = stage / "contents"
                contents.mkdir(mode=0o700)
                files = self._extract(raw, contents, package.manifest)
                _write(stage / "bundle.tar.gz", raw)
                _write(stage / "manifest.json", _json_bytes(package.manifest))
                metadata = {"connector_id": package.connector_id, "version": package.version,
                            "bundle_digest": package.bundle_digest,
                            "digest": package.bundle_digest.removeprefix("sha256:"),
                            "status": "verified", "verification": evidence,
                            "files": files}
                _write(stage / "verification.json", _json_bytes(metadata))
                for directory, _, _ in os.walk(stage):
                    Path(directory).chmod(0o555)
                _without_links(target.parent)
                target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                # Some supported development filesystems require owner write on
                # the moved directory to update its parent entry. Only the
                # installation authority has write access to the parent store.
                stage.chmod(0o755)
                os.rename(stage, target)
                target.chmod(0o555)
                # The immutable directory rename is the publication point. The
                # database switches active identity only after runtime recheck.
                descriptor = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            except (OSError, ValueError, tarfile.TarError, EOFError) as exc:
                _delete_tree(stage)
                if isinstance(exc, ConnectorPackageError):
                    raise
                raise PackageStoreError("package_install_failed") from None
        return StoredPackage(package.connector_id, package.version, package.bundle_digest,
                             package.manifest, evidence)

    def _extract(self, raw: bytes, contents: Path | None, manifest: dict) -> dict:
        files, seen, expanded, members = {}, set(), 0, 0
        domain = {key: value for key, value in manifest.items() if key != "distribution"}
        embedded = None
        # Bound all decoded tar bytes before tarfile parses headers. Otherwise
        # hidden PAX/long-name headers and non-file records can decompress data
        # outside the per-regular-file accounting below.
        tar_limit = MAX_EXPANDED_BYTES + MAX_MEMBERS * 2048 + 10240
        with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as compressed:
            decoded = compressed.read(tar_limit + 1)
        if len(decoded) > tar_limit:
            raise PackageStoreError("archive_size_limit")
        _preflight_tar(decoded)
        with tarfile.open(fileobj=io.BytesIO(decoded), mode="r:") as archive:
            for member in archive:
                members += 1
                if members > MAX_MEMBERS:
                    raise PackageStoreError("archive_file_limit")
                relative = _safe_member(member.name)
                name = str(relative)
                if name in seen or not (member.isfile() or member.isdir()):
                    raise PackageStoreError("unsafe_archive_member")
                if member.mode & (stat.S_ISUID | stat.S_ISGID):
                    raise PackageStoreError("unsafe_archive_permissions")
                seen.add(name)
                path = contents.joinpath(*relative.parts) if contents is not None else None
                if member.isdir():
                    if member.size != 0:
                        raise PackageStoreError("unsafe_archive_directory")
                    if path is not None:
                        path.mkdir(mode=0o700, parents=True, exist_ok=True)
                    continue
                if member.size < 0 or member.size > MAX_FILE_BYTES:
                    raise PackageStoreError("archive_file_size_limit")
                expanded += member.size
                if expanded > MAX_EXPANDED_BYTES:
                    raise PackageStoreError("archive_size_limit")
                if path is not None:
                    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise PackageStoreError("invalid_archive_file")
                with source:
                    payload = source.read(MAX_FILE_BYTES + 1)
                if len(payload) != member.size:
                    raise PackageStoreError("invalid_archive_file")
                if name == "manifest.json":
                    embedded = strict_json(payload)
                    if embedded != domain:
                        raise PackageStoreError("embedded_manifest_mismatch")
                if path is not None:
                    _write(path, payload)
                files[name] = "sha256:" + hashlib.sha256(payload).hexdigest()
        if embedded is None:
            raise PackageStoreError("embedded_manifest_missing")
        for required in [*manifest["licensing"]["notices"], manifest["licensing"]["sbom"]["path"]]:
            if str(_safe_member(required)) not in files:
                raise PackageStoreError("licence_metadata_missing")
        return dict(sorted(files.items()))

    def verify_connector(self, connector_id: str, version: str, bundle_digest: str) -> dict:
        path = self._path(connector_id, version, bundle_digest)
        raw = _read_regular(path / "bundle.tar.gz", MAX_ARCHIVE_BYTES)
        verify_digest(raw, bundle_digest)
        metadata = strict_json(_read_regular(path / "verification.json", 512 * 1024), maximum=512 * 1024)
        manifest = validate_manifest(strict_json(_read_regular(path / "manifest.json", 256 * 1024)))
        if not isinstance(metadata, dict) or not isinstance(metadata.get("verification"), dict):
            raise PackageStoreError("invalid_installed_metadata")
        if metadata["verification"].get("method") == "operator-qualification":
            from app.services.connector_qualification import authorize
            authorize(self.root, manifest, metadata["verification"])
        else:
            validate_manifest(manifest, activation=True)
        identity = {"connector_id": connector_id, "version": version, "bundle_digest": bundle_digest}
        if (any(metadata.get(key) != value for key, value in identity.items())
                or metadata.get("status") != "verified"
                or manifest["id"] != connector_id or manifest["version"] != version
                or manifest["distribution"]["bundle_digest"] != bundle_digest
                or metadata.get("verification", {}).get("bundle_digest") != bundle_digest):
            raise PackageStoreError("installed_package_mismatch")
        files = metadata.get("files")
        if not isinstance(files, dict) or not files or len(files) > MAX_MEMBERS:
            raise PackageStoreError("invalid_installed_metadata")
        try:
            if self._extract(raw, None, manifest) != files:
                raise PackageStoreError("installed_archive_mismatch")
        except (ValueError, tarfile.TarError, EOFError) as exc:
            if isinstance(exc, ConnectorPackageError):
                raise
            raise PackageStoreError("installed_archive_invalid") from None
        actual, expanded, directories = set(), 0, 0
        contents = path / "contents"
        _without_links(contents)
        for directory, subdirs, filenames in os.walk(contents, followlinks=False):
            directories += 1
            if directories > MAX_MEMBERS:
                raise PackageStoreError("installed_package_limit")
            current = Path(directory)
            _without_links(current)
            for subdir in subdirs:
                _without_links(current / subdir)
            for filename in filenames:
                file_path = current / filename
                relative = file_path.relative_to(contents).as_posix()
                _safe_member(relative)
                payload = _read_regular(file_path, MAX_FILE_BYTES)
                expanded += len(payload)
                if expanded > MAX_EXPANDED_BYTES or len(actual) >= MAX_MEMBERS:
                    raise PackageStoreError("installed_package_limit")
                if files.get(relative) != "sha256:" + hashlib.sha256(payload).hexdigest():
                    raise PackageStoreError("installed_file_changed")
                actual.add(relative)
        if actual != set(files):
            raise PackageStoreError("installed_file_missing")
        return {**identity, "state": "verified", "verification_status": "verified"}

    def remove(self, connector_id: str, version: str, bundle_digest: str) -> None:
        with self._lock():
            path = self._path(connector_id, version, bundle_digest)
            try:
                _delete_tree(path)
            except OSError:
                raise PackageStoreError("package_remove_failed") from None

    def quarantine(self, connector_id: str, version: str, bundle_digest: str) -> QuarantineToken:
        """Remove the active address before DB deletion, with rollback support."""
        with self._lock():
            path = self._path(connector_id, version, bundle_digest)
            name = ".removed-" + uuid.uuid4().hex
            try:
                path.chmod(0o755)
                os.rename(path, self.root / name)
                (self.root / name).chmod(0o555)
            except OSError:
                if path.exists():
                    path.chmod(0o555)
                raise PackageStoreError("package_remove_failed") from None
            return QuarantineToken(name, connector_id, version, bundle_digest)

    def quarantine_connector(self, connector_id: str) -> ConnectorQuarantineToken:
        """Atomically remove every installed version address for one Connector."""
        _connector_identity(connector_id)
        with self._lock():
            path = self.root / connector_id
            _without_links(path)
            name = ".removed-" + uuid.uuid4().hex
            try:
                path.chmod(0o755)
                os.rename(path, self.root / name)
                (self.root / name).chmod(0o555)
            except OSError:
                if path.exists():
                    path.chmod(0o755)
                raise PackageStoreError("package_remove_failed") from None
            return ConnectorQuarantineToken(name, connector_id)

    def _quarantine_path(self, token: QuarantineToken | ConnectorQuarantineToken) -> Path:
        if not isinstance(token, (QuarantineToken, ConnectorQuarantineToken)) or not re.fullmatch(r"\.removed-[a-f0-9]{32}", token.name):
            raise PackageStoreError("invalid_remove_receipt")
        if isinstance(token, ConnectorQuarantineToken):
            _connector_identity(token.connector_id)
        else:
            _identity(token.connector_id, token.version, token.bundle_digest)
        path = self.root / token.name
        _without_links(path)
        return path

    def restore(self, token: QuarantineToken | ConnectorQuarantineToken) -> None:
        with self._lock():
            source = self._quarantine_path(token)
            target = (self.root / token.connector_id if isinstance(token, ConnectorQuarantineToken)
                      else self._path(token.connector_id, token.version, token.bundle_digest))
            _without_links(target)
            if target.exists():
                raise PackageStoreError("package_restore_conflict")
            try:
                source.chmod(0o755)
                os.rename(source, target)
                target.chmod(0o755 if isinstance(token, ConnectorQuarantineToken) else 0o555)
            except OSError:
                raise PackageStoreError("package_restore_failed") from None

    def finish_remove(self, token: QuarantineToken | ConnectorQuarantineToken) -> None:
        with self._lock():
            try:
                _delete_tree(self._quarantine_path(token))
            except OSError:
                raise PackageStoreError("package_remove_failed") from None


def _json_bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")
