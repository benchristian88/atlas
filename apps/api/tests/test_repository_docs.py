"""Public documentation boundaries, licence identity and navigable local targets."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tomllib
from urllib.parse import unquote

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
LINK = re.compile(r"!?\[[^\]\n]*\]\(([^\s)]+)(?:\s+[^)]*)?\)")
EXCLUDED_DIRECTORIES = {"node_modules", ".venv", "venv", "vendor", "generated", "__pycache__"}
# Preserve untouched older Markdown hard breaks and one older EOF blank line.
# These exact-byte snapshots cannot exempt any new or edited document.
LEGACY_WHITESPACE_SNAPSHOTS = {
    "docs/architecture/ui-architecture.md": "11723d96fceab548787e30aa4d0807237fbae3f720ef43dd25d6acbecc26b9ae",
    "docs/history/product-reviews/atlas-product-feature-status-review-reconciled.md": "8b7d90b857561e151469edb46f5e1218188e0c1e3f8a6e69c87ce177bc1042d8",
    "docs/history/product-reviews/atlas-ui-system-review-2026-09.md": "7a4970baabf51d1f4bb20cc230da905c4303cc1bb5ad7bd0a95d94ee461642a1",
}


def documents(root=ROOT):
    # Walk the filesystem, not Git's index: newly created/untracked docs count.
    paths = list(root.glob("*.md"))
    for subtree in ("docs", ".github"):
        for directory, children, files in os.walk(root / subtree):
            children[:] = sorted(set(children) - EXCLUDED_DIRECTORIES)
            paths.extend(Path(directory) / name for name in files if name.endswith(".md"))
    return sorted(paths)


def documentation_whitespace_errors(root=ROOT):
    errors = []
    for path in documents(root):
        name = path.relative_to(root).as_posix()
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() == LEGACY_WHITESPACE_SNAPSHOTS.get(name):
            continue
        for number, line in enumerate(data.splitlines(), 1):
            if line.endswith((b" ", b"\t")):
                errors.append(f"{name}:{number}: trailing whitespace")
        if data and not data.endswith(b"\n"):
            errors.append(f"{name}: missing final newline")
        if data.endswith(b"\n\n"):
            errors.append(f"{name}: blank line at EOF")
    return errors


def test_repository_markdown_whitespace():
    errors = documentation_whitespace_errors()
    assert not errors, errors


@pytest.mark.parametrize("content, expected", [
    (b"Text \n", "1: trailing whitespace"),
    (b"Text\t\n", "1: trailing whitespace"),
    (b"Text\n\n", " blank line at EOF"),
    (b"Text", " missing final newline"),
    (b"```text\nText \n```\n", "2: trailing whitespace"),
])
def test_untracked_markdown_whitespace_is_detected(tmp_path, content, expected):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    path = tmp_path / "docs/new-guide.md"
    path.parent.mkdir()
    path.write_bytes(content)
    # Reproduce the gap: plain diff succeeds while this untracked file is bad.
    subprocess.run(["git", "diff", "--check"], cwd=tmp_path, check=True)
    assert documentation_whitespace_errors(tmp_path) == [f"docs/new-guide.md:{expected}"]


def test_markdown_scan_scope_and_fenced_indentation(tmp_path):
    clean = b"```python\n    print('indented content')\n```\n"
    for name in ("NEW.md", "docs/nested/new.md", ".github/new.md"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(clean)
    for name in EXCLUDED_DIRECTORIES:
        path = tmp_path / "docs" / name / "ignored.md"
        path.parent.mkdir()
        path.write_bytes(b"Ignored bad whitespace \n\n")
    assert len(documents(tmp_path)) == 3
    assert not documentation_whitespace_errors(tmp_path)


def test_legacy_whitespace_allowance_does_not_hide_new_defects(tmp_path):
    name = "docs/architecture/ui-architecture.md"
    path = tmp_path / name
    path.parent.mkdir(parents=True)
    path.write_bytes((ROOT / name).read_bytes())
    assert not documentation_whitespace_errors(tmp_path)
    line = len(path.read_bytes().splitlines()) + 1
    path.write_bytes(path.read_bytes() + b"New defect \n")
    assert f"{name}:{line}: trailing whitespace" in documentation_whitespace_errors(tmp_path)


def test_local_markdown_targets_exist():
    broken = []
    for path in documents():
        for match in LINK.finditer(path.read_text()):
            target = unquote(match[1].split("#", 1)[0])
            if target and ":" not in target and not target.startswith("/"):
                if not (path.parent / target).exists():
                    broken.append((str(path.relative_to(ROOT)), target))
    assert not broken, broken


def test_active_guides_have_product_language_and_closed_code_fences():
    active = [ROOT / "README.md", ROOT / "docs/README.md"]
    for directory in ("admin", "architecture", "deployment", "development", "product", "testing"):
        active.extend((ROOT / "docs" / directory).glob("*.md"))
    for path in active:
        text = path.read_text()
        # Link destinations can name historical records; the reader sees product labels.
        prose = LINK.sub(lambda match: match[0].split("](", 1)[0] + "]", text)
        assert not re.search(r"\b(?:[CH][1-9](?:\.[0-9]+)*|Release [A-F](?:\.[0-9]+)?)\b|\bCodex\b|feature/", prose), path
        fence = None
        for line in text.splitlines():
            match = re.match(r"\s*(`{3,}|~{3,})", line)
            if match:
                if fence is None:
                    fence = match[1]
                elif match[1][0] == fence[0] and len(match[1]) >= len(fence):
                    fence = None
        assert fence is None, path


def test_public_entry_points_do_not_navigate_to_internal_history():
    required = {"LICENSE", "COMMERCIAL-LICENSING.md", "SECURITY.md", "SUPPORT.md",
                "CONTRIBUTING.md", "docs/README.md", "docs/deployment/installation.md",
                "docs/deployment/upgrades.md", "docs/deployment/backup-restore.md"}
    readme = (ROOT / "README.md").read_text()
    targets = {match[1].split("#", 1)[0] for match in LINK.finditer(readme)}
    assert required <= targets
    for path in (ROOT / "README.md", ROOT / "docs/README.md"):
        assert all("history/" not in match[1] and "development-roadmap" not in match[1]
                   for match in LINK.finditer(path.read_text()))


def test_canonical_licence_and_first_party_metadata():
    # Official GNU agpl-3.0.txt downloaded verbatim; no bespoke legal text.
    assert hashlib.sha256((ROOT / "LICENSE").read_bytes()).hexdigest() == (
        "0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0")
    package = json.loads((ROOT / "apps/web/package.json").read_text())
    lock = json.loads((ROOT / "apps/web/package-lock.json").read_text())
    assert package["license"] == lock["packages"][""]["license"] == "AGPL-3.0-only"
    for name in ("sdk", "proxmox"):
        project = tomllib.loads((ROOT / f"plugins/{name}/pyproject.toml").read_text())["project"]
        assert project["license"]["text"] == "AGPL-3.0-only"
    for name in ("api", "web", "worker"):
        dockerfile = (ROOT / f"apps/{name}/Dockerfile").read_text()
        assert 'org.opencontainers.image.licenses="AGPL-3.0-only"' in dockerfile
        assert not re.search(r"(?m)^\+", dockerfile)


def test_issue_templates_collect_diagnostics_without_requesting_secrets():
    for name in ("bug_report", "feature_request"):
        template = yaml.safe_load((ROOT / f".github/ISSUE_TEMPLATE/{name}.yml").read_text())
        assert template["name"] and template["description"]
        assert any(item.get("validations", {}).get("required") for item in template["body"])
    bug = (ROOT / ".github/ISSUE_TEMPLATE/bug_report.yml").read_text()
    for item in ("credentials", "API tokens", "setup codes", "backup files", "private inventory"):
        assert item in bug


def test_security_reporting_uses_github_private_reporting_without_claiming_enablement():
    policy = (ROOT / "SECURITY.md").read_text()
    assert "GitHub Private Vulnerability Reporting" in policy
    assert "Report a vulnerability" in policy
    assert "does not establish that reporting is enabled" in policy
    assert "repository owner must enable" in policy
    assert "Do not publish exploitable details" in policy
    assert "no promised response or disclosure deadline" in policy
    assert "request a private reporting route" not in policy
    assert "mailto:" not in policy
    config = yaml.safe_load((ROOT / ".github/ISSUE_TEMPLATE/config.yml").read_text())
    security = config["contact_links"][0]
    assert security["url"].endswith("/SECURITY.md")
    assert "GitHub Private Vulnerability Reporting" in security["about"]
    for name in ("README.md", "SUPPORT.md", "docs/README.md"):
        assert any(match[1].endswith("SECURITY.md") for match in LINK.finditer((ROOT / name).read_text()))
