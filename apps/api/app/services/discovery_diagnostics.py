"""Discovery diagnostics v1: identifier-only sidecar, independent of AIP.

The API independently validates the private runtime result before persistence.
No raw sidecar or debug data is part of a normal run response.
"""
import json
import re


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


PROCESSING_ERRORS = {"diagnostic_invalid", "diagnostic_limit", "diagnostic_incomplete", "diagnostic_destination_invalid"}


def validate_report(value, *, debug=False, secrets=()):
    """Fail closed at the second trust boundary; do not persist arbitrary keys."""
    if (not isinstance(value, dict) or set(value) != {"version", "available", "counts", "reasons", "events",
            "contexts_truncated", "processing_errors", "debug_events"}
            or type(value["version"]) is not int or value["version"] != 1
            or type(value["available"]) is not bool or type(value["contexts_truncated"]) is not bool
            or not isinstance(value["counts"], dict)
            or set(value["counts"]) != {"processed", "accepted", "skipped", "warning", "error"}
            or any(type(n) is not int or not 0 <= n <= 100000000 for n in value["counts"].values())
            or not isinstance(value["processing_errors"], list) or len(value["processing_errors"]) > 4
            or any(not isinstance(code, str) or code not in PROCESSING_ERRORS for code in value["processing_errors"])
            or not isinstance(value["events"], list) or len(value["events"]) > MAX_CONTEXTS
            or not isinstance(value["reasons"], list) or len(value["reasons"]) > MAX_EVENTS + 4
            or not isinstance(value["debug_events"], list) or len(value["debug_events"]) > MAX_EVENTS
            or not debug and value["debug_events"]):
        raise ValueError("diagnostic_invalid")
    contexts = [event(row, secrets=secrets) for row in value["events"]]
    trace = [event(row, debug=True, secrets=secrets) for row in value["debug_events"]]
    for rows in [contexts, trace]:
        if any(b["sequence"] <= a["sequence"] for a, b in zip(rows, rows[1:])):
            raise ValueError("diagnostic_invalid")
    for row in value["reasons"]:
        if (not isinstance(row, dict) or set(row) != {"reason_code", "count"}
                or type(row["count"]) is not int or not 1 <= row["count"] <= MAX_EVENTS + 4):
            raise ValueError("diagnostic_invalid")
        event({"sequence": 1, "stage": "diagnostics", "result": "warning", "reason_code": row["reason_code"]}, secrets=secrets)
    if len(json.dumps(value, separators=(",", ":"), allow_nan=False).encode()) > MAX_TRACE_BYTES + 512 * 1024:
        raise ValueError("diagnostic_limit")
    return {**value, "events": contexts, "debug_events": trace}


def persist(db, run, value):
    """One final sanitized snapshot; deletion/expiry cannot rehydrate debug data."""
    from app.models import DiscoveryRunDebugTrace
    safe = validate_report(value, debug=bool(run.debug_enabled))
    if run.diagnostics_summary is not None:
        return
    run.diagnostics_summary = {key: safe[key] for key in ["version", "available", "counts", "reasons",
        "contexts_truncated", "processing_errors"]}
    run.diagnostics_events = safe["events"]
    from datetime import datetime, timezone
    if (run.debug_enabled and run.debug_deleted_at is None and run.debug_expires_at
            and run.debug_expires_at > datetime.now(timezone.utc) and safe["debug_events"]):
        db.add(DiscoveryRunDebugTrace(discovery_run_id=run.id, expires_at=run.debug_expires_at,
            events=safe["debug_events"]))


def purge_expired(db, *, now=None):
    from datetime import datetime, timezone
    from sqlalchemy import delete
    from app.models import DiscoveryRunDebugTrace
    result = db.execute(delete(DiscoveryRunDebugTrace).where(
        DiscoveryRunDebugTrace.expires_at <= (now or datetime.now(timezone.utc))))
    return result.rowcount

