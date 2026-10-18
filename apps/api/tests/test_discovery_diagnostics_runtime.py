"""Private sidecar trust boundaries and surviving evidence on terminal paths."""
from copy import deepcopy
import json
import os
from pathlib import Path
import secrets
import subprocess

import pytest

from tests.test_i3_runtime import installed
from atlas_runtime import diagnostics as wire, jobs
from app.services import discovery_diagnostics as core


def event(sequence=1, **extra):
    return {"sequence": sequence, "stage": "guest_interface", "result": "warning",
            "reason_code": "interface_invalid", "object_class": "fixture.guest", "external_id": "guest/1027", **extra}


@pytest.mark.parametrize("attack", ["extra", "body", "type", "result", "sequence", "long", "secret", "header", "debug", "unknown_type"])
def test_both_boundaries_reject_malformed_and_secret_material(attack):
    marker = secrets.token_hex(24)
    row = event()
    if attack == "extra": row["environment"] = {"private": marker}
    elif attack == "body": row["external_id"] = {"body": marker}
    elif attack == "type": row["sequence"] = True
    elif attack == "result": row["result"] = "unknown"
    elif attack == "sequence": row["sequence"] = wire.MAX_EVENTS + 1
    elif attack == "long": row["external_id"] = "a" * 193
    elif attack == "secret": row["external_id"] = "prefix" + marker
    elif attack == "header": row["external_id"] = "Authorization"
    elif attack == "debug": row["field"] = "net0"
    else: row["encountered_type"] = "source_value"
    for contract in [wire, core]:
        with pytest.raises(ValueError): contract.event(row, secrets=[marker])


def test_trace_descriptor_identity_limits_prefix_and_flush(tmp_path):
    path = tmp_path / "diagnostics.ndjson"
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    info = os.fstat(descriptor); identity = (info.st_dev, info.st_ino)
    try:
        os.write(descriptor, (json.dumps(event()) + "\n" + '{"source_body":"untrusted"}\n').encode())
        result = wire.read_trace(descriptor, path, identity)
        assert result["events"] == [event()]
        assert "diagnostic_invalid" in result["processing_errors"]
        assert "untrusted" not in json.dumps(result)
        path.unlink(); path.symlink_to(tmp_path / "elsewhere")
        result = wire.read_trace(descriptor, path, identity)
        assert result["processing_errors"] == ["diagnostic_destination_invalid"]
    finally:
        os.close(descriptor)


@pytest.mark.parametrize("kind", ["size", "count", "partial_line", "duplicate_key"])
def test_bounded_reader_never_returns_unbounded_or_malformed_values(tmp_path, kind):
    path = tmp_path / "diagnostics.ndjson"
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    info = os.fstat(descriptor)
    try:
        if kind == "size": raw = b"x" * (wire.MAX_EVENT_BYTES + 1)
        elif kind == "count": raw = b"".join((json.dumps(event(i)) + "\n").encode() for i in range(1, wire.MAX_EVENTS + 2))
        elif kind == "partial_line": raw = json.dumps(event()).encode()
        else: raw = b'{"sequence":1,"sequence":2}\n'
        os.write(descriptor, raw)
        result = wire.read_trace(descriptor, path, (info.st_dev, info.st_ino))
        assert result["processing_errors"] and len(result["debug_events"]) <= wire.MAX_EVENTS
        core.validate_report(result)
    finally:
        os.close(descriptor)


@pytest.mark.parametrize("outcome", ["partial", "crash", "timeout", "cancelled", "invalid", "symlink", "complete_warning", "missing"])
def test_terminal_jobs_retain_only_sanitized_trace_and_cleanup_workspace(installed, tmp_path, monkeypatch, outcome, capsys):
    runtime, payload = installed
    payload["debug_enabled"] = True
    known = [*payload["credentials"].values(), payload["ingestion_token"], runtime._secret]
    calls = []
    monkeypatch.setattr(jobs, "stop_process", lambda process: None)
    class Process:
        returncode = 0
        def __init__(self, args, **kwargs):
            self.root = Path(args[-1])
            assert all(secret not in json.dumps(args) + json.dumps(kwargs["env"]) for secret in known)
        def communicate(self, raw, timeout):
            source = json.loads(raw)
            assert payload.get("ingestion_token", "absent") not in source
            trace = [event(1, field="net0", encountered_type="string", validation_rule="interface_config")]
            if outcome not in {"crash", "timeout", "cancelled", "missing"}:
                trace.append(event(2, stage="discovery", result="accepted", reason_code="discovery_finished"))
            if outcome == "invalid": trace.append({**event(3), "source_body": known[0]})
            path = self.root / "diagnostics.ndjson"
            path.write_text("".join(json.dumps(row) + "\n" for row in trace))
            if outcome == "symlink":
                path.unlink(); path.symlink_to(tmp_path / "outside")
            if outcome == "crash": self.returncode = 1; return
            if outcome == "timeout": raise subprocess.TimeoutExpired("fixed-child", timeout)
            if outcome == "cancelled": next(iter(runtime.jobs.by_request.values())).cancel.set(); return
            envelope = {"protocol_version": "1.0", "run_id": source["run_id"], "integration_id": source["integration_id"],
                "connector": {"id": source["reference"]["connector_id"], "version": source["reference"]["version"], "bundle_digest": "sha256:" + source["reference"]["digest"]},
                "observed_at": "2026-10-18T00:00:00Z", "coverage": source["coverage"]}
            rows = [{**envelope, "message_type": "observations", "batch": {"sequence": 1}, "assets": [], "networks": [], "interfaces": [], "relationships": []}]
            if outcome != "missing": rows.append({**envelope, "message_type": "completion", "last_sequence": 1, "status": "completed", "completeness": "complete" if outcome == "complete_warning" else "partial"})
            (self.root / "aip.ndjson").write_text("\n".join(json.dumps(row) for row in rows))
            (self.root / "aip.ndjson").chmod(0o600)
    monkeypatch.setattr(jobs.subprocess, "Popen", Process)
    monkeypatch.setattr(runtime.jobs, "callback", lambda job, source, operation, message, env: calls.append(operation))
    accepted = runtime.run_discovery(payload)
    job = runtime.jobs.by_request[accepted["request_id"]]; job.thread.join(5)
    result = runtime.get_job({"request_id": job.request_id, "job_id": job.job_id})
    assert result["state"] == ("succeeded" if outcome == "partial" else "cancelled" if outcome == "cancelled" else "failed")
    diagnostic = result["diagnostics"]
    assert all(secret not in json.dumps(result) + str(capsys.readouterr()) for secret in known)
    assert not list(tmp_path.glob("job-*")) and payload["credentials"] == {}
    if outcome != "symlink":
        assert diagnostic["events"][0]["reason_code"] == "interface_invalid"
        assert diagnostic["debug_events"][0]["field"] == "net0"
    if outcome != "partial": assert "completion" not in calls
    core.validate_report(diagnostic, debug=True)


@pytest.mark.parametrize("extra,value", [("diagnostics_file", "/host/private"), ("debug_enabled", "true"), ("debug", True)])
def test_no_user_supplied_trace_destination_or_coerced_debug(installed, extra, value):
    runtime, payload = installed
    payload[extra] = value
    with pytest.raises(ValueError, match="invalid_request"): runtime.run_discovery(payload)
