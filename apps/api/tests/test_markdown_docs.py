import uuid
from datetime import datetime, timezone

from atlas_plugin_sdk import (
    NormalizedAsset,
    NormalizedFact,
    NormalizedRelationship,
)

from app.services.markdown_docs import escape_markdown, generate_asset_document


def test_generates_document_from_normalized_data_and_relationships() -> None:
    node = NormalizedAsset(
        external_id="node/pve-01",
        name="pve-01",
        asset_type="hypervisor_node",
        vendor="Proxmox",
        metadata={"status": "online", "tags": ["production", "compute"]},
        facts=(NormalizedFact("maxcpu", 16, "proxmox"),),
    )
    vm = NormalizedAsset(
        external_id="qemu/100",
        name="dc-01",
        asset_type="virtual_machine",
        vendor="Proxmox",
        status="active",
        description="Primary directory server",
        facts=(NormalizedFact("status", "running", "proxmox"),),
    )
    relationship = NormalizedRelationship("qemu/100", "node/pve-01", "runs_on")
    run_id = uuid.uuid4()
    observed_at = datetime(2026, 7, 10, 4, 30, tzinfo=timezone.utc)

    vm_document = generate_asset_document(
        vm,
        {vm.external_id: vm, node.external_id: node},
        (relationship,),
        discovery_run_id=run_id,
        observed_at=observed_at,
    )
    assert vm_document.title == "dc-01 — Asset Documentation"
    assert "# dc\\-01" in vm_document.content_markdown
    assert "| Asset type | Virtual Machine |" in vm_document.content_markdown
    assert "Primary directory server" in vm_document.content_markdown
    assert "| status | running | proxmox |" in vm_document.content_markdown
    assert "| Outgoing | Runs On | pve\\-01 (`node/pve\\-01`) |" in vm_document.content_markdown
    assert str(run_id) in vm_document.content_markdown

    node_document = generate_asset_document(
        node,
        {vm.external_id: vm, node.external_id: node},
        (relationship,),
        discovery_run_id=run_id,
        observed_at=observed_at,
    )
    assert "| Incoming | Runs On | dc\\-01 (`qemu/100`) |" in node_document.content_markdown


def test_vendor_text_is_escaped_and_cannot_inject_markdown_or_html() -> None:
    malicious = "server | bad\n## injected <script>alert(1)</script>"
    asset = NormalizedAsset(
        external_id="node/malicious",
        name=malicious,
        asset_type="server",
        vendor="<b>vendor</b>",
        metadata={"danger|key": "[click](https://example.test)"},
    )
    document = generate_asset_document(
        asset,
        {asset.external_id: asset},
        (),
        discovery_run_id=uuid.uuid4(),
        observed_at=datetime.now(timezone.utc),
    )
    assert "\n## injected" not in document.content_markdown
    assert "<script>" not in document.content_markdown
    assert "&lt;script&gt;" in document.content_markdown
    assert "\\|" in document.content_markdown
    assert "\\[click\\]\\(https://example\\.test\\)" in document.content_markdown


def test_output_is_deterministic_for_unsorted_metadata_and_facts() -> None:
    asset = NormalizedAsset(
        external_id="asset/1",
        name="asset",
        asset_type="server",
        vendor="Vendor",
        metadata={"z": 1, "a": 2},
        facts=(
            NormalizedFact("z", 1, "source"),
            NormalizedFact("a", 2, "source"),
        ),
    )
    document = generate_asset_document(
        asset,
        {asset.external_id: asset},
        (),
        discovery_run_id=uuid.UUID(int=1),
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert document.content_markdown.index("| a | 2 |") < document.content_markdown.index("| z | 1 |")
    assert document.content_markdown.index("| a | 2 | source |") < document.content_markdown.index("| z | 1 | source |")


def test_escape_markdown_collapses_lines() -> None:
    assert escape_markdown("first\nsecond") == "first second"
