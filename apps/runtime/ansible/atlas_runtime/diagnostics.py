"""Discovery diagnostics v1: identifier-only sidecar, independent of AIP.

The descriptor is created and retained by the runtime, never supplied over the
control API. Revalidate after stopping every descendant and before any callback.
"""
import json
import os
import re
import stat

from atlas_connector_sdk.contracts import strict_json

MAX_EVENTS = 8192
MAX_EVENT_BYTES = 768
MAX_TRACE_BYTES = MAX_EVENTS * MAX_EVENT_BYTES
MAX_CONTEXTS = 128
NORMAL = {"sequence", "stage", "result", "reason_code", "object_class", "external_id",
          "parent_external_id", "source_category", "record_count"}
DEBUG = {"field", "encountered_type", "validation_rule", "expected", "action"}
OUTCOMES = {"accepted", "skipped", "warning", "error"}
TOKEN = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./:-]{0,191}")
TYPES = {"null", "boolean", "integer", "number", "string", "array", "object", "unknown"}


def event(value, *, debug=False, secrets=()):
    if (not isinstance(value, dict) or set(value) - (NORMAL | DEBUG if debug else NORMAL)
            or not {"sequence", "stage", "result", "reason_code"} <= value.keys()
            or type(value["sequence"]) is not int or not 1 <= value["sequence"] <= MAX_EVENTS
            or value["result"] not in OUTCOMES
            or type(value.get("record_count", 0)) is not int or not 0 <= value.get("record_count", 0) <= 10000):
        raise ValueError("diagnostic_invalid")
    for key, item in value.items():
        if key in {"sequence", "record_count"}:
            continue
        pattern = IDENTITY if key in {"external_id", "parent_external_id"} else TOKEN
        if (not isinstance(item, str) or not pattern.fullmatch(item)
                or any(secret and secret in item for secret in secrets)
                or "Authorization" in item or re.search(r"password|bearer|private.key|api.token|token.secret|eyJ", item, re.I)):
            raise ValueError("diagnostic_invalid")
    if "encountered_type" in value and value["encountered_type"] not in TYPES:
        raise ValueError("diagnostic_invalid")
    if len(json.dumps(value, separators=(",", ":"), allow_nan=False).encode()) + 1 > MAX_EVENT_BYTES:
        raise ValueError("diagnostic_limit")
    return dict(value)


def report(events, *, debug=False, problems=()):
    counts = {name: 0 for name in ["processed", "accepted", "skipped", "warning", "error"]}
    contexts, reasons = [], {}
    for row in events:
        amount = row.get("record_count", 0)
        counts["processed"] += amount
        counts[row["result"]] += amount if row["result"] in {"accepted", "skipped"} else 1
        if row["result"] in {"warning", "error"}:
            code = row["reason_code"]
            reasons[code] = reasons.get(code, 0) + 1
            if len(contexts) < MAX_CONTEXTS:
                contexts.append({key: item for key, item in row.items() if key in NORMAL})
    for code in sorted(set(problems)):
        counts["error"] += 1
        reasons[code] = reasons.get(code, 0) + 1
    return {"version": 1, "available": bool(events), "counts": counts,
            "reasons": [{"reason_code": code, "count": count} for code, count in sorted(reasons.items())],
            "events": contexts, "contexts_truncated": counts["warning"] + counts["error"] > len(contexts),
            "processing_errors": sorted(set(problems)), "debug_events": events if debug else []}


def read_trace(descriptor, path, identity, *, debug=False, secrets=()):
    events, problems = [], []
    try:
        info, named = os.fstat(descriptor), path.lstat()
        if (not stat.S_ISREG(info.st_mode) or not stat.S_ISREG(named.st_mode)
                or (info.st_dev, info.st_ino) != identity or (named.st_dev, named.st_ino) != identity
                or info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise ValueError("diagnostic_destination_invalid")
        os.lseek(descriptor, 0, os.SEEK_SET)
        with os.fdopen(os.dup(descriptor), "rb") as stream:
            consumed = 0
            while line := stream.readline(MAX_EVENT_BYTES + 1):
                consumed += len(line)
                if consumed > MAX_TRACE_BYTES or len(events) >= MAX_EVENTS or len(line) > MAX_EVENT_BYTES:
                    problems.append("diagnostic_limit")
                    break
                if not line.endswith(b"\n"):
                    problems.append("diagnostic_incomplete")
                    break
                try:
                    row = event(strict_json(line, maximum=MAX_EVENT_BYTES), debug=debug, secrets=secrets)
                    if row["sequence"] != len(events) + 1:
                        raise ValueError("diagnostic_invalid")
                except (ValueError, TypeError, KeyError, RecursionError):
                    problems.append("diagnostic_invalid")
                    break  # Retain the validated prefix only, never offending data.
                events.append(row)
        if events and events[-1]["reason_code"] != "discovery_finished":
            problems.append("diagnostic_incomplete")
        if any(row["reason_code"] == "diagnostic_limit" for row in events):
            problems.append("diagnostic_limit")
    except (OSError, ValueError):
        problems.append("diagnostic_destination_invalid")
    return report(events, debug=debug, problems=problems)
