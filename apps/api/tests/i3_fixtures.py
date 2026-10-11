"""Test-only trusted executable. Never part of the catalogue or release package."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tarfile

from app.services.connector_catalogue import CataloguePackage
from app.services.connector_verification import BootstrapReleaseVerifier, OfficialBundleVerifier

ROOT = Path(__file__).resolve().parents[3]


def fixture_bundle(tmp_path):
    manifest = json.loads((ROOT / "docs/architecture/integrations/contracts/manifests/proxmox.json").read_text())
    # Schema example is only a template: no vendor endpoint or inventory code.
    raw = json.dumps(manifest).replace("proxmox", "i3-fixture")
    manifest = json.loads(raw)
    manifest["id"], manifest["version"] = "i3-fixture", "1.0.0"
    manifest["licensing"]["licence"] = "AGPL-3.0-only"
    manifest["display"].update(name="I3 test fixture", description="Deterministic test-only execution")
    manifest["source_versions"].update(qualification="qualified", qualified_versions=["8.4.0"])
    manifest["connection_fields"].append({"key": "scenario", "label": "Scenario", "type": "text", "required": False, "secret": False})
    manifest["object_classes"] = [row for row in manifest["object_classes"] if row["key"] in {"i3-fixture.node", "i3-fixture.qemu", "i3-fixture.network", "i3-fixture.interface"}]
    manifest["relationship_classes"][0]["source_object_classes"] = ["i3-fixture.qemu"]
    manifest["discovery_scopes"][0]["object_classes"] = [row["key"] for row in manifest["object_classes"]]
    for fact in manifest["facts"]:
        fact["object_classes"] = ["i3-fixture.qemu"]
    manifest["facts"].append({"key": "i3-fixture.tags", "label": "Tags", "value_type": "string", "class": "configuration", "cardinality": "multi", "object_classes": ["i3-fixture.qemu"]})
    playbook = b'''- hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Deterministic private test output
      ansible.builtin.command:
        argv:
          - "{{ ansible_python_interpreter }}"
          - "{{ playbook_dir }}/emit.py"
          - "{{ atlas_input_file }}"
          - "{{ atlas_aip_file }}"
      no_log: true
'''
    emit = b'''import json,sys,time
from pathlib import Path
inputs=json.loads(Path(sys.argv[1]).read_text())
scenario=inputs["config"].get("scenario","complete")
if scenario=="slow":
 Path(sys.argv[2]).with_name("fixture.pid").write_text(str(__import__("os").getpid()))
 time.sleep(120)
envelope={"protocol_version":"1.0","connector":{"id":inputs["reference"]["connector_id"],"version":inputs["reference"]["version"],"bundle_digest":"sha256:"+inputs["reference"]["digest"]},"run_id":inputs["run_id"],"integration_id":inputs["integration_id"],"observed_at":"2026-10-12T00:00:00Z","source":{"version":"8.4.0"},"coverage":inputs["coverage"]}
messages=[]
for sequence in [1,2]:
 batch={**envelope,"message_type":"observations","batch":{"sequence":sequence},"assets":[],"networks":[],"interfaces":[],"relationships":[]}
 if sequence==1 and scenario!="empty": batch["assets"]=[{"external_id":"node/1","object_class":"i3-fixture.node","name":"Fixture node","status":"active","facts":[]}]
 messages.append(batch)
if scenario!="missing":
 messages.append({**envelope,"message_type":"completion","status":"failed" if scenario=="failed" else "completed","completeness":"failed" if scenario=="failed" else "partial" if scenario=="partial" else "complete","last_sequence":2,**({"errors":[{"code":"source_unavailable"}]} if scenario=="failed" else {})})
if scenario=="malformed": messages[0]["customer_id"]="forbidden"
Path(sys.argv[2]).write_text("\\n".join(json.dumps(row) for row in messages)+"\\n")
'''
    domain = {key: value for key, value in manifest.items() if key != "distribution"}
    files = [("manifest.json", json.dumps(domain).encode()), ("NOTICE", b"Atlas AGPL-3.0-only test infrastructure\n"),
        ("sbom.spdx.json", json.dumps({"spdxVersion": "SPDX-2.3", "dataLicense": "CC0-1.0", "SPDXID": "SPDXRef-DOCUMENT",
            "name": "I3 test-only fixture", "documentNamespace": "https://example.test/i3-test-only/1.0.0",
            "creationInfo": {"creators": ["Organization: Atlas Impact test harness"], "created": "2026-10-12T00:00:00Z"},
            "packages": [{"name": "i3-fixture", "SPDXID": "SPDXRef-Fixture", "versionInfo": "1.0.0", "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False, "licenseDeclared": "AGPL-3.0-only", "licenseConcluded": "NOASSERTION", "copyrightText": "NOASSERTION"}]}).encode()),
        ("discover.yml", playbook), ("emit.py", emit)]
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in files:
            member = tarfile.TarInfo(name); member.size = len(content); member.mode = 0o600
            archive.addfile(member, io.BytesIO(content))
    contents = buffer.getvalue()
    digest = "sha256:" + hashlib.sha256(contents).hexdigest()
    manifest["distribution"]["bundle_digest"] = digest
    path = tmp_path / "test-only.tar.gz"; path.write_bytes(contents)
    package = CataloguePackage(manifest["id"], manifest["version"], digest, manifest, "bootstrap", True, path)
    verifier = OfficialBundleVerifier(BootstrapReleaseVerifier(frozenset({(manifest["id"], manifest["version"], digest)}), "test-only-i3"))
    return package, verifier


def message(run, *, sequence=1, completion=None, assets=True, technical=False):
    provenance = run.execution_provenance
    value = {"protocol_version": "1.0", "connector": {"id": provenance["connector_id"], "version": provenance["connector_version"], "bundle_digest": "sha256:" + provenance["connector_digest"]},
        "run_id": str(run.id), "integration_id": str(run.integration_id), "observed_at": "2026-10-12T00:00:00Z", "source": {"version": "8.4.0"}, "coverage": deepcopy(provenance["coverage"])}
    if completion:
        value.update(message_type="completion", status="completed" if completion in {"complete", "partial"} else completion,
            completeness=completion if completion != "cancelled" else "unknown", last_sequence=sequence)
        if completion == "failed": value["errors"] = [{"code": "source_unavailable"}]
        return value
    value.update(message_type="observations", batch={"sequence": sequence}, assets=[], networks=[], interfaces=[], relationships=[])
    if assets:
        value["assets"] = [{"external_id": "node/1", "object_class": "i3-fixture.node", "name": "Fixture node", "status": "active", "facts": []},
            {"external_id": "vm/1", "object_class": "i3-fixture.qemu", "name": "Fixture VM", "status": "active", "facts": [{"key": "i3-fixture.tags", "value_type": "string", "class": "configuration", "cardinality": "multi", "value": ["a", "b"]}]}]
    if technical:
        value["networks"] = [{"external_id": "network/1", "object_class": "i3-fixture.network", "name": "Fixture LAN", "network_type": "lan", "facts": []}]
        value["interfaces"] = [{"external_id": "interface/1", "object_class": "i3-fixture.interface", "name": "eth0", "asset_external_id": "node/1", "network_external_id": "network/1", "is_primary": False, "facts": []}]
        value["relationships"] = [{"external_id": "runs/1", "relationship_class": "i3-fixture.runs_on", "source": {"kind": "asset", "external_id": "vm/1"}, "target": {"kind": "asset", "external_id": "node/1"}, "truth_classification": "observed", "confidence": 1.0}]
    return value
