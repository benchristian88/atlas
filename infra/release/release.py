"""Deterministic local/CI release construction and independent validation.

This tool cannot publish, tag, push, or execute assets. Official releases use a
clean committed snapshot; --worktree is explicitly a non-publishable dry run.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tarfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/api"))
from app.release import OFFICIAL_REPOSITORY, REPOSITORY_URL, load_metadata, parse_metadata, validate_metadata, validate_tag

METHODS = {"docker_compose": "docker-compose", "systemd": "systemd"}
FORBIDDEN_PARTS = {".git", ".github", ".env", ".venv", "venv", "node_modules", ".next", "__pycache__",
                   ".pytest_cache", "coverage", "tests", "screenshots", ".DS_Store"}
FORBIDDEN_SUFFIXES = {".pyc", ".db", ".sqlite", ".sqlite3", ".dump", ".atlasbackup", ".pem", ".key", ".log"}
MAX_PACKAGE_BYTES = 128 * 1024 * 1024


def git(*args, root=ROOT) -> bytes:
    return subprocess.check_output(["git", *args], cwd=root)


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def safe_path(name: str) -> bool:
    path = PurePosixPath(name)
    return (bool(name) and not path.is_absolute() and "\\" not in name and
            all(part not in {"", ".", ".."} for part in name.split("/")) and
            not any(ord(char) < 32 for char in name))


def permitted_path(name):
    path = PurePosixPath(name)
    return (safe_path(name) and not any(part in FORBIDDEN_PARTS or part.startswith(".env.") for part in path.parts)
            and path.suffix not in FORBIDDEN_SUFFIXES and not any(part.endswith(".egg-info") for part in path.parts))


def included(name, manifest, method):
    return permitted_path(name) and any(name.startswith(rule) if rule.endswith("/") else name == rule
                                       for rule in manifest["common"] + manifest[method])


def snapshot(root, worktree=False):
    commit = git("rev-parse", "HEAD", root=root).decode().strip()
    epoch = int(git("show", "-s", "--format=%ct", commit, root=root))
    if worktree:
        names = git("ls-files", "--cached", "--others", "--exclude-standard", "-z", root=root).decode().split("\0")
        files = {}
        for name in set(names) - {""}:
            if not safe_path(name):
                raise ValueError("Unsafe source path")
            path = root / name
            if not path.exists():
                continue
            if any((root / Path(*Path(name).parts[:index])).is_symlink() for index in range(1, len(Path(name).parts) + 1)) or not path.is_file():
                # Outside-package links can be ignored, but selected links cannot.
                files[name] = (None, 0)
                continue
            files[name] = (path.read_bytes(), 0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644)
        return commit, epoch, files
    if git("status", "--porcelain", root=root).strip():
        raise ValueError("Release build requires a clean committed tree; use --dry-run --worktree for local acceptance")
    with tarfile.open(fileobj=io.BytesIO(git("archive", "--format=tar", commit, root=root))) as archive:
        files = {}
        for member in archive:
            if member.isdir():
                continue
            if not safe_path(member.name):
                raise ValueError("Unsafe tracked path")
            files[member.name] = ((archive.extractfile(member).read() if member.isfile() else None),
                                  0o755 if member.mode & 0o111 else 0o644)
    return commit, epoch, files


def validate_tree(files, method, metadata, commit, manifest):
    required = manifest["required_common"] + manifest[f"required_{method}"]
    if any(name not in files for name in required):
        missing = sorted(set(required) - files.keys())
        raise ValueError(f"Required package files missing: {', '.join(missing)}")
    for name, (data, mode) in files.items():
        if not permitted_path(name) or (name != "PACKAGE.json" and not included(name, manifest, method)):
            raise ValueError("Unreviewed or forbidden package path")
        if data is None or mode not in {0o644, 0o755}:
            raise ValueError("Links/non-regular files or unsafe modes are forbidden")
        if name.endswith((".py", ".js", ".mjs", ".json", ".yml", ".md", ".sh", ".service", ".conf", ".txt")):
            # Reject recognizable secret assignments and private keys; generated
            # expressions in installer source are not literal credential values.
            text = data.decode("utf-8")
            if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", text) or re.search(
                    r"(?m)^\s*(?:POSTGRES_PASSWORD|AUTH_SECRET_KEY|ATLAS_DATA_ENCRYPTION_KEY)\s*=\s*[a-fA-F0-9]{32,}\s*$", text):
                raise ValueError("Credential-like content in release package")
    packaged = parse_metadata(files["apps/api/app/release.json"][0])
    if packaged != {**metadata, "build_id": commit, "install_method": method}:
        raise ValueError("Artifact identity does not match release")
    if method == "docker_compose":
        script = "infra/docker/gateway/15-atlas-trusted-proxies.sh"
        if files[script][1] != 0o755:
            raise ValueError("Gateway entrypoint must be executable")
        for app in ("api", "web", "worker"):
            dockerfile = files[f"apps/{app}/Dockerfile"][0].decode()
            for line in dockerfile.splitlines():
                parts = line.split()
                if not parts or parts[0] != "COPY" or any(part.startswith("--from=") for part in parts):
                    continue
                sources = [part for part in parts[1:-1] if not part.startswith("--")]
                import fnmatch
                for source in sources:
                    prefix = f"apps/{app}/" + source.rstrip("/")
                    if source != "." and not any(fnmatch.fnmatch(name, prefix) or name.startswith(prefix + "/") for name in files):
                        raise ValueError("Docker COPY source missing from package")
    # Local JS/CSS imports are runtime dependencies even if accidentally placed
    # outside an established component tree. Validate them before distribution.
    for name, (data, _) in files.items():
        if name.startswith("apps/web/") and name.endswith((".js", ".mjs")):
            for target in re.findall(r'(?:from\s+|import\s*)["\'](\.[^"\']+)["\']', data.decode()):
                import posixpath
                path = posixpath.normpath(str(PurePosixPath(name).parent / target))
                if not any(candidate in files for candidate in (path, path + ".js", path + ".mjs", path + "/index.js")):
                    raise ValueError(f"Missing frontend import: {name} -> {target}")
    for unit in ("api", "web", "worker") if method == "systemd" else ():
        content = files[f"infra/systemd/atlas-{unit}.service"][0].decode()
        if "User=atlas" not in content or "NoNewPrivileges=true" not in content:
            raise ValueError("Native unit privilege contract missing")
    if not any(name.startswith("apps/web/public/") for name in files):
        raise ValueError("Missing public web assets")


def schema_head(files):
    revisions, parents = set(), set()
    for name, (data, _) in files.items():
        if name.startswith("apps/api/migrations/versions/") and name.endswith(".py"):
            for node in ast.parse(data).body:
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                            value = ast.literal_eval(node.value)
                            if target.id == "revision":
                                revisions.add(value)
                            elif isinstance(value, str):
                                parents.add(value)
    heads = revisions - parents
    if len(heads) != 1:
        raise ValueError("Expected one Alembic head")
    return heads.pop()


def write_archive(path, root_name, files, epoch):
    with path.open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0, compresslevel=9) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                for name in sorted(files):
                    data, mode = files[name]
                    member = tarfile.TarInfo(f"{root_name}/{name}")
                    member.size, member.mode, member.mtime = len(data), mode, epoch
                    member.uid = member.gid = 0
                    member.uname = member.gname = ""
                    archive.addfile(member, io.BytesIO(data))


def package_document_links(files, commit):
    """Keep included docs local; link omitted source docs to the exact commit."""
    import posixpath
    for name, (data, mode) in list(files.items()):
        if not name.endswith(".md"):
            continue
        def replace(match):
            target = match[1]
            parsed = urlsplit(target)
            if parsed.scheme or not parsed.path or parsed.path.startswith("/"):
                return match[0]
            destination = posixpath.normpath(str(PurePosixPath(name).parent / parsed.path))
            if destination in files or not safe_path(destination):
                return match[0]
            kind = "blob" if PurePosixPath(destination).suffix else "tree"
            fragment = "#" + parsed.fragment if parsed.fragment else ""
            return f"]({REPOSITORY_URL}/{kind}/{commit}/{destination}{fragment})"
        files[name] = (re.sub(r"\]\(([^\s)]+)\)", replace, data.decode()).encode(), mode)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build(output: Path, *, root=ROOT, tag=None, dry_run=False, worktree=False):
    if worktree and not dry_run:
        raise ValueError("--worktree requires --dry-run; working-tree assets cannot be published")
    commit, epoch, source = snapshot(root, worktree)
    metadata = parse_metadata(source["apps/api/app/release.json"][0])
    if metadata.get("build_id") is not None or metadata.get("install_method") is not None:
        raise ValueError("Canonical source must not contain artifact build/method identity")
    tag = tag or f"v{metadata['version']}"
    validate_tag(metadata, tag)
    manifest = json.loads(source["infra/release/package-manifest.json"][0])
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Release output directory must be empty")
    artifacts = []
    source_digest = hashlib.sha256()
    selected = {name for method in METHODS for name in source if included(name, manifest, method)}
    for name in sorted(selected):
        data, mode = source[name]
        if data is None:
            raise ValueError("Selected source contains a link/non-regular file")
        source_digest.update(name.encode() + b"\0" + str(mode).encode() + b"\0" + hashlib.sha256(data).digest())
    package_identity = {"version": metadata["version"], "release_channel": metadata["release_channel"],
                        "commit_sha": commit, "source_state": "working_tree" if worktree else "committed",
                        "source_sha256": source_digest.hexdigest(), "tag": tag}
    for method, label in METHODS.items():
        files = {name: source[name] for name in source if included(name, manifest, method)}
        files["apps/api/app/release.json"] = (json_bytes({**metadata, "build_id": commit, "install_method": method}), 0o644)
        files["PACKAGE.json"] = (json_bytes({**package_identity, "install_method": method}), 0o644)
        package_document_links(files, commit)
        validate_tree(files, method, metadata, commit, manifest)
        filename = f"atlas-{label}-{metadata['version']}.tar.gz"
        write_archive(output / filename, f"atlas-{label}-{metadata['version']}", files, epoch)
        artifacts.append({"filename": filename, "install_method": method, "sha256": sha256(output / filename),
                          "size": (output / filename).stat().st_size})
    release = {"schema_version": 1, "product": "Atlas Impact", "repository": OFFICIAL_REPOSITORY,
               **package_identity, "created_at": datetime.fromtimestamp(epoch, timezone.utc).isoformat(),
               "supported_install_methods": sorted(METHODS), "minimum_supported_schema": "20261004_0025",
               "current_schema": schema_head(source), "artifacts": artifacts}
    release_name = f"atlas-release-{metadata['version']}.json"
    (output / release_name).write_bytes(json_bytes(release))
    names = sorted([entry["filename"] for entry in artifacts] + [release_name])
    (output / "SHA256SUMS").write_text("".join(f"{sha256(output / name)}  {name}\n" for name in names))
    verify(output, tag=tag)
    return release


def verify(output: Path, *, tag=None, require_committed=False):
    sums = (output / "SHA256SUMS").read_text().splitlines()
    checksums = {}
    for line in sums:
        match = re.fullmatch(r"([a-f0-9]{64})  ([A-Za-z0-9.+_-]+)", line)
        if not match or match[2] in checksums:
            raise ValueError("Invalid or duplicate checksum entry")
        name = match[2]
        path = output / name
        if path.is_symlink() or not path.is_file() or sha256(path) != match[1]:
            raise ValueError("Artifact checksum verification failed")
        checksums[name] = match[1]
    manifests = [name for name in checksums if re.fullmatch(r"atlas-release-.+\.json", name)]
    if len(manifests) != 1 or len(checksums) != 3:
        raise ValueError("Expected two packages and one release manifest")
    release = json.loads((output / manifests[0]).read_text())
    metadata = validate_metadata({"version": release["version"], "release_channel": release["release_channel"], "build_id": None})
    validate_tag(metadata, release["tag"])
    if tag is not None:
        validate_tag(metadata, tag)
    if (release["schema_version"] != 1 or release["product"] != "Atlas Impact" or release["repository"] != OFFICIAL_REPOSITORY
            or not re.fullmatch(r"[a-f0-9]{40}", release["commit_sha"])):
        raise ValueError("Invalid release identity")
    if (release["source_state"] not in {"committed", "working_tree"}
            or not re.fullmatch(r"[a-f0-9]{64}", release["source_sha256"])
            or release["supported_install_methods"] != sorted(METHODS)
            or release["minimum_supported_schema"] != "20261004_0025"):
        raise ValueError("Invalid release compatibility/source declaration")
    created = datetime.fromisoformat(release["created_at"])
    if created.tzinfo is None:
        raise ValueError("Release creation time must include a timezone")
    if require_committed and release["source_state"] != "committed":
        raise ValueError("Working-tree artifacts cannot be published")
    expected_names = {f"atlas-{label}-{metadata['version']}.tar.gz" for label in METHODS.values()} | {f"atlas-release-{metadata['version']}.json"}
    if set(checksums) != expected_names or {path.name for path in output.iterdir()} != expected_names | {"SHA256SUMS"}:
        raise ValueError("Unexpected release files")
    if len(release["artifacts"]) != 2 or {entry["install_method"] for entry in release["artifacts"]} != set(METHODS):
        raise ValueError("Invalid artifact methods")
    for artifact in release["artifacts"]:
        method = artifact["install_method"]
        filename = f"atlas-{METHODS[method]}-{metadata['version']}.tar.gz"
        if artifact["filename"] != filename or artifact["sha256"] != checksums[filename] or artifact["size"] != (output / filename).stat().st_size:
            raise ValueError("Manifest artifact checksum/size mismatch")
        prefix = filename.removesuffix(".tar.gz")
        files, total = {}, 0
        with tarfile.open(output / filename, "r:gz") as archive:
            for index, member in enumerate(archive):
                if index >= 10000:
                    raise ValueError("Too many archive members")
                if not member.isfile() or not member.name.startswith(prefix + "/") or not safe_path(member.name):
                    raise ValueError("Unsafe archive member/root/type")
                name = member.name[len(prefix) + 1:]
                total += member.size
                if name in files or total > MAX_PACKAGE_BYTES or member.mode not in {0o644, 0o755}:
                    raise ValueError("Duplicate, oversized or unsafe-mode archive member")
                files[name] = (archive.extractfile(member).read(), member.mode)
        manifest = json.loads(files["infra/release/package-manifest.json"][0])
        # The reviewed manifest comes from the checked-out release tooling as well
        # as the package, so a package cannot expand its own path allowlist.
        if manifest != json.loads((ROOT / "infra/release/package-manifest.json").read_text()):
            raise ValueError("Package inclusion policy mismatch")
        validate_tree(files, method, metadata, release["commit_sha"], manifest)
        identity = json.loads(files["PACKAGE.json"][0])
        for key in ("version", "release_channel", "commit_sha", "source_sha256", "source_state", "tag"):
            if identity[key] != release[key]:
                raise ValueError("Package/release identity mismatch")
        if identity["install_method"] != method or schema_head(files) != release["current_schema"]:
            raise ValueError("Package method/schema mismatch")
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["metadata", "build", "verify"])
    parser.add_argument("--output", type=Path, default=ROOT / "dist/release")
    parser.add_argument("--tag")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--worktree", action="store_true")
    parser.add_argument("--require-committed", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "metadata":
            metadata = load_metadata(ROOT / "apps/api/app/release.json")
            if args.tag:
                validate_tag(metadata, args.tag)
            print(json.dumps(metadata, sort_keys=True))
        elif args.action == "build":
            result = build(args.output, tag=args.tag, dry_run=args.dry_run, worktree=args.worktree)
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            verify(args.output, tag=args.tag, require_committed=args.require_committed)
            print("Release packages, identity, manifest and SHA-256 checksums verified.")
    except (ValueError, KeyError, OSError, tarfile.TarError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Release validation failed: {exc}\n")


if __name__ == "__main__":
    main()
