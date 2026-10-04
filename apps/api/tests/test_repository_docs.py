"""Public documentation boundaries, licence identity and navigable local targets."""
import hashlib
import json
from pathlib import Path
import re
import tomllib
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).resolve().parents[3]
LINK = re.compile(r"!?\[[^\]\n]*\]\(([^\s)]+)(?:\s+[^)]*)?\)")


def documents():
    return [*ROOT.glob("*.md"), *(ROOT / "docs").rglob("*.md"),
            *(ROOT / ".github").rglob("*.md")]


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
