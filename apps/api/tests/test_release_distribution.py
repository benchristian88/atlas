import copy
import importlib.util
import io
import os
import json
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tarfile

import pytest
import yaml

from app import release as policy

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("atlas_packager", ROOT / "infra/release/release.py")
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


@pytest.fixture(scope="module")
def packages(tmp_path_factory):
    output = tmp_path_factory.mktemp("h4-release")
    release = packager.build(output, dry_run=True, worktree=True)
    return output, release


def test_metadata_rejects_duplicate_fields(tmp_path):
    path = tmp_path / "release.json"
    path.write_text('{"version":"0.1.0","version":"0.2.0","release_channel":"beta"}')
    with pytest.raises(ValueError, match="Duplicate"): policy.load_metadata(path)


def test_artifact_identity_wins_over_preserved_old_environment(monkeypatch):
    identity = {"version": "0.2.0", "release_channel": "beta", "build_id": "a" * 40, "install_method": "systemd"}
    monkeypatch.setattr(policy, "load_metadata", lambda: identity)
    monkeypatch.setenv("ATLAS_BUILD_ID", "old-build")
    monkeypatch.setenv("ATLAS_INSTALL_METHOD", "development")
    assert policy.build_metadata() == identity


def test_dry_run_and_byte_reproducibility(packages, tmp_path):
    output, release = packages
    other = tmp_path / "repeat"
    packager.build(other, dry_run=True, worktree=True)
    assert {path.name: path.read_bytes() for path in output.iterdir()} == {path.name: path.read_bytes() for path in other.iterdir()}
    assert release["version"] == policy.load_metadata()["version"]
    assert release["source_state"] == "working_tree"
    assert release["current_schema"] == "20261011_0027"
    assert packager.verify(output) == release
    with pytest.raises(ValueError, match="cannot be published"): packager.verify(output, require_committed=True)
    with pytest.raises(ValueError, match="exactly match"): packager.verify(output, tag="v99.0.0")
    with pytest.raises(ValueError, match="requires --dry-run"): packager.build(tmp_path / "unsafe", worktree=True)


def test_package_contents_identity_modes_and_installer_paths(packages, tmp_path):
    output, release = packages
    for artifact in release["artifacts"]:
        path = output / artifact["filename"]
        method = artifact["install_method"]
        assert packager.sha256(path) == artifact["sha256"]
        assert path.stat().st_size == artifact["size"]
        with tarfile.open(path) as archive:
            members = archive.getmembers()
            assert all(member.isfile() and member.uid == member.gid == 0 for member in members)
            assert all(packager.safe_path(member.name) and member.mode in {0o644, 0o755} for member in members)
            assert not any(any(part in packager.FORBIDDEN_PARTS for part in Path(member.name).parts) for member in members)
            archive.extractall(tmp_path / method, filter="data")
        tree = tmp_path / method / artifact["filename"].removesuffix(".tar.gz")
        for name in ("LICENSE", "COMMERCIAL-LICENSING.md", "SECURITY.md", "SUPPORT.md", "THIRD-PARTY-NOTICES.md",
                     "docs/deployment/installation.md", "docs/deployment/mfa.md",
                     "docs/deployment/backup-restore.md", "docs/deployment/releases.md", "docs/deployment/upgrades.md"):
            assert (tree / name).is_file(), name
        assert (tree / "LICENSE").read_bytes() == (ROOT / "LICENSE").read_bytes()
        assert not (tree / "docs/history").exists()
        assert not (tree / "docs/product").exists()
        metadata = policy.load_metadata(tree / "apps/api/app/release.json")
        assert metadata["build_id"] == release["commit_sha"]
        assert metadata["install_method"] == method
        help_result = subprocess.run([sys.executable, str(tree / "infra/install/upgrade.py"), "--help"], check=True, capture_output=True, text=True)
        assert "H3" not in help_result.stdout
        assert "encrypted Atlas backup" in help_result.stdout
        if method == "docker_compose":
            subprocess.run([sys.executable, str(tree / "infra/install/compose.py"), "--help"], check=True, capture_output=True)
            compose = yaml.safe_load((tree / "infra/docker/docker-compose.yml").read_text())
            for service in compose["services"].values():
                if "build" in service:
                    context = (tree / "infra/docker" / service["build"]["context"]).resolve()
                    assert context.is_dir() and (context / service["build"].get("dockerfile", "Dockerfile")).is_file()
            config = tmp_path / "existing.env"
            # Random, ephemeral configuration; no committed fixture credentials.
            config.write_text("ATLAS_INSTALL_METHOD=docker_compose\n" + "".join(f"{key}={secrets.token_hex(32)}\n" for key in ("POSTGRES_PASSWORD", "AUTH_SECRET_KEY", "ATLAS_DATA_ENCRYPTION_KEY")))
            config.chmod(0o600)
            before = config.read_bytes()
            subprocess.run([sys.executable, str(tree / "infra/install/upgrade.py"), "--method", method,
                            "--env-file", str(config), "--validate-only"], check=True, capture_output=True)
            assert config.read_bytes() == before
        else:
            subprocess.run([sys.executable, str(tree / "infra/install/native.py"), "--help"], check=True, capture_output=True)
            for service in ("api", "web", "worker", "runtime"):
                assert (tree / f"infra/systemd/atlas-{service}.service").is_file()
            assert "StateDirectory=atlas" in (tree / "infra/systemd/atlas-api.service").read_text()
            assert (tree / "infra/nginx/native.conf").is_file()
            assert (tree / "infra/install/native_ingress.py").is_file()
        # Package docs must resolve locally or link the omitted source document
        # to the official repository at the exact build commit.
        import re
        from urllib.parse import urlsplit
        for document in (tree / "docs").rglob("*.md"):
            for target in re.findall(r"\]\(([^\s)]+)\)", document.read_text()):
                parsed = urlsplit(target)
                if not parsed.scheme and parsed.path:
                    assert (document.parent / parsed.path).exists(), (document, target)


def rewrite_checksums(output):
    names = sorted(path.name for path in output.iterdir() if path.name != "SHA256SUMS")
    (output / "SHA256SUMS").write_text("".join(f"{packager.sha256(output / name)}  {name}\n" for name in names))


@pytest.mark.parametrize("attack", ["traversal", "absolute", "symlink", "hardlink", "duplicate", "env", "database", "git", "mode", "missing-installer", "missing-web-import", "missing-native-ingress", "credential", "wrong-build"])
def test_archive_validation_rejects_attacks_even_with_recomputed_checksums(packages, tmp_path, attack):
    output, original = packages
    target = tmp_path / "release"
    shutil.copytree(output, target)
    artifact_index = 1 if attack == "missing-native-ingress" else 0
    artifact = copy.deepcopy(original["artifacts"][artifact_index])
    path = target / artifact["filename"]
    prefix = artifact["filename"].removesuffix(".tar.gz")
    with tarfile.open(path) as archive:
        members = [(member, archive.extractfile(member).read()) for member in archive]
    name = {"traversal": f"{prefix}/../escape", "absolute": "/escape", "env": f"{prefix}/.env",
            "database": f"{prefix}/local.db", "git": f"{prefix}/.git/config"}.get(attack, f"{prefix}/apps/api/app/unsafe.py")
    if attack == "missing-installer":
        members = [(member, data) for member, data in members if not member.name.endswith("/infra/install/compose.py")]
    elif attack == "missing-web-import":
        members = [(member, data) for member, data in members if not member.name.endswith("/components/updates.js")]
    elif attack == "missing-native-ingress":
        members = [(member, data) for member, data in members if not member.name.endswith("/infra/nginx/native.conf")]
    elif attack == "duplicate":
        members.append(members[0])
    elif attack == "wrong-build":
        for index, (member, data) in enumerate(members):
            if member.name.endswith("/apps/api/app/release.json"):
                metadata = json.loads(data); metadata["build_id"] = "b" * 40
                data = packager.json_bytes(metadata);member.size = len(data);members[index] = member, data
    else:
        member = tarfile.TarInfo(name); data = b"harmless"
        member.mode = 0o777 if attack == "mode" else 0o644
        if attack in {"symlink", "hardlink"}:
            member.type = tarfile.SYMTYPE if attack == "symlink" else tarfile.LNKTYPE
            member.linkname = "../../escape"; data = b""
        if attack == "credential": data = b"ATLAS_DATA_ENCRYPTION_KEY=" + secrets.token_hex(32).encode()
        member.size = len(data); members.append((member, data))
    with tarfile.open(path, "w:gz") as archive:
        for member, data in members: archive.addfile(member, io.BytesIO(data))
    manifest_path = target / f"atlas-release-{original['version']}.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"][artifact_index].update(sha256=packager.sha256(path), size=path.stat().st_size)
    manifest_path.write_bytes(packager.json_bytes(manifest)); rewrite_checksums(target)
    with pytest.raises(ValueError): packager.verify(target)


def test_checksums_cover_manifest_and_reject_tampering(packages, tmp_path):
    output, release = packages
    target = tmp_path / "release"; shutil.copytree(output, target)
    manifest = target / f"atlas-release-{release['version']}.json"
    manifest.write_bytes(manifest.read_bytes() + b" ")
    with pytest.raises(ValueError, match="checksum"): packager.verify(target)


def documented_checksum_commands():
    guide = (ROOT / "docs/deployment/releases.md").read_text()
    blocks = re.findall(r"```bash\n(.*?)\n```", guide, re.DOTALL)
    selection = next(block for block in blocks if block.startswith("awk -v package="))
    checks = [block for block in blocks if re.match(r"(?:sha256sum|shasum) ", block)]
    assert checks == ["sha256sum -c SHA256SUMS.selected", "shasum -a 256 -c SHA256SUMS.selected"]
    return selection, checks


def selected_release_download(packages, tmp_path, method):
    output, release = packages
    label = packager.METHODS[method]
    archive = f"atlas-{label}-{release['version']}.tar.gz"
    manifest = f"atlas-release-{release['version']}.json"
    for name in (archive, manifest, "SHA256SUMS"):
        shutil.copyfile(output / name, tmp_path / name)
    environment = {**os.environ, "ATLAS_VERSION": release["version"], "ATLAS_PACKAGE": label}
    return archive, manifest, environment


@pytest.mark.parametrize("method", ["docker_compose", "systemd"])
def test_documented_checksums_verify_selected_package_and_manifest_only(packages, tmp_path, method):
    archive, manifest, environment = selected_release_download(packages, tmp_path, method)
    selection, checks = documented_checksum_commands()
    subprocess.run(["bash", "-e", "-c", selection], cwd=tmp_path, env=environment, check=True)
    lines = (tmp_path / "SHA256SUMS.selected").read_text().splitlines()
    assert {line.split("  ")[1] for line in lines} == {archive, manifest}
    for command in checks:
        result = subprocess.run(["bash", "-e", "-c", command], cwd=tmp_path, check=True, capture_output=True, text=True)
        assert f"{archive}: OK" in result.stdout and f"{manifest}: OK" in result.stdout
    assert len(list(tmp_path.glob("*.tar.gz"))) == 1
    installation = (ROOT / "docs/deployment/installation.md").read_text()
    assert installation.count("package, release manifest and `SHA256SUMS`") == 2
    assert "docs/deployment/releases.md#assets-and-validation" in (ROOT / "README.md").read_text()


@pytest.mark.parametrize("method", ["docker_compose", "systemd"])
@pytest.mark.parametrize("defect", ["missing-entry", "duplicate-entry", "missing-package", "missing-manifest", "tampered-package", "tampered-manifest"])
def test_documented_selected_checksums_reject_missing_duplicate_or_tampered_files(packages, tmp_path, method, defect):
    archive, manifest, environment = selected_release_download(packages, tmp_path, method)
    selection, checks = documented_checksum_commands()
    sums = tmp_path / "SHA256SUMS"
    if defect in {"missing-entry", "duplicate-entry"}:
        lines = sums.read_text().splitlines(keepends=True)
        entry = next(line for line in lines if line.endswith(f"  {manifest}\n"))
        sums.write_text("".join(line for line in lines if line != entry) if defect == "missing-entry" else "".join(lines) + entry)
        result = subprocess.run(["bash", "-e", "-c", selection], cwd=tmp_path, env=environment)
        assert result.returncode != 0
        return
    if defect in {"missing-package", "missing-manifest"}:
        (tmp_path / (manifest if defect == "missing-manifest" else archive)).unlink()
    else:
        path = tmp_path / (manifest if defect == "tampered-manifest" else archive)
        path.write_bytes(path.read_bytes() + b"tampered")
    subprocess.run(["bash", "-e", "-c", selection], cwd=tmp_path, env=environment, check=True)
    for command in checks:
        result = subprocess.run(["bash", "-e", "-c", command], cwd=tmp_path, capture_output=True)
        assert result.returncode != 0


def test_workflow_syntax_permissions_publication_guards_and_pins():
    # BaseLoader avoids YAML 1.1 treating the GitHub key 'on' as a boolean.
    workflow = yaml.load((ROOT / ".github/workflows/release.yml").read_text(), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"push", "workflow_dispatch"}
    assert workflow["on"]["push"] == {"tags": ["v*"]}
    assert workflow["permissions"] == {}
    build, publish = workflow["jobs"]["build"], workflow["jobs"]["publish"]
    assert build["permissions"] == {"contents": "read"}
    assert publish["permissions"] == {"contents": "write"}
    assert publish["needs"] == "build"
    assert "github.event_name == 'push'" in publish["if"] and "github.ref_type == 'tag'" in publish["if"]
    assert "benchristian88/atlas" in publish["if"]
    for job in (build, publish):
        for step in job["steps"]:
            if "uses" in step:
                import re
                assert re.fullmatch(r"actions/[a-z-]+@[a-f0-9]{40}", step["uses"])
                if step["uses"].startswith("actions/checkout"):
                    assert step["with"]["persist-credentials"] == "false"
            if "run" in step:
                assert "${{" not in step["run"]
    assert all("GH_TOKEN" not in step.get("env", {}) for step in build["steps"])
    assert all("pip install -e" not in step.get("run", "") and "requirements-dev.txt" not in step.get("run", "") for step in build["steps"])
    assert "GH_TOKEN" in publish["steps"][-1]["env"]
    assert "verify --require-committed" in publish["steps"][-2]["run"]
    build_runs = "\n".join(step.get("run", "") for step in build["steps"])
    assert "metadata --tag" in build_runs and "sha256sum -c SHA256SUMS" in build_runs
    assert "merge-base --is-ancestor HEAD origin/dev" in build_runs
    source = (ROOT / "infra/release/publish.py").read_text()
    assert "--verify-tag" in source and "--draft" in source and "--prerelease" in source
    assert "shell=True" not in source and "eval(" not in source


@pytest.mark.parametrize("missing", ["apps/api/scripts/backup.py", "infra/nginx/native.conf", "infra/install/native_ingress.py"])
def test_build_rejects_malformed_metadata_and_missing_runtime_input(monkeypatch, tmp_path, missing):
    commit, epoch, source = packager.snapshot(ROOT, worktree=True)
    source["apps/api/app/release.json"] = (b'{"version":"bad", "release_channel":"beta"}', 0o644)
    monkeypatch.setattr(packager, "snapshot", lambda *args: (commit, epoch, source))
    with pytest.raises(ValueError, match="SemVer"):
        packager.build(tmp_path / "bad-version", dry_run=True, worktree=True)
    source["apps/api/app/release.json"] = (b'{"version":"0.1.0", "version":"0.2.0", "release_channel":"beta"}', 0o644)
    with pytest.raises(ValueError, match="Duplicate"):
        packager.build(tmp_path / "duplicate", dry_run=True, worktree=True)
    source["apps/api/app/release.json"] = ((ROOT / "apps/api/app/release.json").read_bytes(), 0o644)
    del source[missing]
    with pytest.raises(ValueError, match="missing"):
        packager.build(tmp_path / "missing-input", dry_run=True, worktree=True)


def installer_module(name):
    sys.path.insert(0, str(ROOT / "infra/install"))
    spec = importlib.util.spec_from_file_location(name, ROOT / f"infra/install/{name}.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_docker_upgrade_stops_writers_after_build_and_preserves_configuration(monkeypatch, tmp_path):
    module = installer_module("upgrade")
    calls = []
    monkeypatch.setattr(module, "run", lambda arguments, **kwargs: calls.append(arguments))
    monkeypatch.setattr(module, "protected_configuration", lambda path, method: {})
    environment = tmp_path / "existing.env"
    environment.write_text("operator configuration"); before = environment.read_bytes()
    module.docker_upgrade(environment)
    tails = [call[6:] for call in calls]
    assert tails[0] == ["config", "--quiet"]
    assert tails[1] == ["build", "api", "web", "worker", "runtime", "runtime-init"]
    assert tails[2] == ["stop", "gateway", "web", "worker", "api"]
    assert "up" in tails[3]
    assert not any("down" in call or "-v" in call for call in calls)
    assert environment.read_bytes() == before


def test_native_upgrade_reuses_install_primitives_and_preserves_state(monkeypatch, tmp_path):
    module = installer_module("upgrade")
    import native
    source, destination = tmp_path / "release", tmp_path / "opt-atlas"
    for root in (source, destination):
        for name in ("apps", "infra"):
            (root / name).mkdir(parents=True);(root / name / "marker").write_text("new" if root == source else "old")
    (destination / "venv").mkdir();(destination / "venv/identity").write_text("preserve")
    configuration = tmp_path / "etc/atlas/atlas.env"
    configuration.parent.mkdir(parents=True)
    values = {key: secrets.token_hex(32) for key in ("POSTGRES_PASSWORD", "AUTH_SECRET_KEY", "ATLAS_DATA_ENCRYPTION_KEY")}
    configuration.write_text("".join(f"{key}={value}\n" for key, value in values.items()) + "AUTH_COOKIE_SECURE=true\n")
    configuration.chmod(0o640)
    original_configuration = configuration.read_bytes()
    state = tmp_path / "var/lib/atlas"
    state.mkdir(parents=True)
    (state / "identity").write_text("preserve state")
    monkeypatch.setattr(module, "ROOT", source)
    monkeypatch.setattr(native, "DESTINATION", destination)
    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(module.pwd, "getpwnam", lambda name: type("Account", (), {"pw_uid": 10001, "pw_gid": 10001})())
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/" + name)
    calls = []
    monkeypatch.setattr(module, "run", lambda args: calls.append(args))
    settings = {"ATLAS_BIND_ADDRESS": "192.0.2.10", "ATLAS_PORT": "3000", "ATLAS_TRUSTED_PROXIES": ""}
    monkeypatch.setattr(module, "native_upgrade_preflight", lambda values: (settings, False))
    monkeypatch.setattr(native, "ensure_nginx", lambda needed: calls.append(["nginx-ready"]))
    monkeypatch.setattr(native, "configure_runtime", lambda: calls.append(["runtime-configured"]))
    monkeypatch.setattr(native, "start_runtime", lambda values: calls.append(["runtime-started"]))
    monkeypatch.setattr(native, "stop_runtime", lambda: calls.append(["runtime-stopped"]))
    import native_ingress
    monkeypatch.setattr(native_ingress, "install", lambda values: calls.append(["ingress", values["ATLAS_PORT"]]))
    monkeypatch.setattr(native, "build_application", lambda account: calls.append(["build", account.pw_uid]))
    monkeypatch.setattr(native, "install_units", lambda: calls.append(["units"]))
    monkeypatch.setattr(native, "wait_for_health", lambda values: calls.append(["health"]))
    previous_umask = module.os.umask(0o022)
    try: module.native_upgrade(values)
    finally: module.os.umask(previous_umask)
    assert calls[0] == ["nginx-ready"]
    assert calls[1] == ["runtime-configured"]
    assert calls[2] == ["runtime-stopped"]
    assert calls[3] == ["systemctl", "stop", "atlas-web", "atlas-worker", "atlas-api"]
    assert calls[4:7] == [["build", 10001], ["units"], ["runtime-started"]]
    assert ["ingress", "3000"] in calls
    assert (destination / "apps/marker").read_text() == "new"
    assert (destination / "venv/identity").read_text() == "preserve"
    assert configuration.read_bytes() == original_configuration
    assert (state / "identity").read_text() == "preserve state"
    assert not any("useradd" in call or "psql" in call or "postgresql.service" in call for call in calls)
