"""Instance-global durable refresh. No executable package or runtime authority."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta
import hashlib
import json
import time
import uuid

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from app.audit import add_audit_event
from app.models import ConnectorCatalogueRevision as Revision, ConnectorCatalogueState as State
from app.services import catalogue_source as source
from app.services.backup_archive import BackupError
from app.services.backup_runtime import maintenance, normal_operation
from app.services.connector_contracts import ConnectorPackageError
from app.services.official_catalogue import parse_official_catalogue
from app.services.official_provenance import TrustProfile
from app.utils.json_values import to_json_value

LEASE_SECONDS = 150
COOLDOWN_SECONDS = 900
CONFLICTS = {"catalogue_rollback", "catalogue_substitution", "historical_identity_changed",
             "withdrawal_reactivated", "channel_changed", "historical_snapshot_mismatch",
             "checkpoint_inconsistent", "bootstrap_policy_rejected"}


def _lock(db):
    # Also serializes first initialization/recovery. Never held during I/O.
    db.execute(text("SET LOCAL lock_timeout = '3s'"))
    db.execute(text("SET LOCAL statement_timeout = '10s'"))
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atlas-official-catalogue'))"))
    db.execute(insert(State).values(id=1).on_conflict_do_nothing())
    return db.scalar(select(State).where(State.id == 1).with_for_update().execution_options(populate_existing=True))


def history_after(document, previous):
    """Pure lifecycle check. Not authentication; suitable for generic unit fixtures."""
    history = dict(previous)
    for entry in document["entries"]:
        manifest = entry["manifest"]
        key = manifest["id"] + "/" + manifest["version"]
        identity = {k: entry[k] for k in ("manifest", "release_tag", "release_asset_id")}
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        old = history.get(key)
        if old:
            source.require(old["digest"] == digest, "historical_identity_changed")
            source.require(not old["withdrawn"] or entry["status"] == "withdrawn", "withdrawal_reactivated")
        history[key] = {"digest": digest, "withdrawn": entry["status"] == "withdrawn"}
    source.require(len(history) <= 10000 and len(json.dumps(history).encode()) <= 2_000_000, "history_capacity_exceeded")
    return history


def transition(document, digest, state):
    sequence = document["sequence"]
    if state.highest_sequence is None:
        source.require(sequence >= source.BOOTSTRAP_SEQUENCE, "bootstrap_policy_rejected")
        if sequence == source.BOOTSTRAP_SEQUENCE:
            source.require(digest == source.BOOTSTRAP_DIGEST, "bootstrap_policy_rejected")
    else:
        source.require(sequence >= state.highest_sequence, "catalogue_rollback")
        if sequence == state.highest_sequence:
            source.require(digest == state.highest_digest, "catalogue_substitution")
            return "unchanged"
    return "accepted"


def recover_checkpoint(db, state):
    """Reconstruct a missing/older checkpoint from retained append-only revisions.

    This cannot detect replacement of the entire database by an older backup.
    Recovery never sets a current-channel confirmation timestamp.
    """
    latest = db.scalar(select(Revision).order_by(Revision.sequence.desc()).limit(1))
    if latest is None:
        source.require(state.highest_sequence is None, "checkpoint_inconsistent")
        return
    if state.highest_sequence == latest.sequence:
        source.require(state.highest_digest == latest.content_digest, "checkpoint_inconsistent")
        return
    source.require(state.highest_sequence is None or state.highest_sequence < latest.sequence, "checkpoint_inconsistent")
    history = {}
    # Recovery is exceptional and bounded; never discard history to fit a limit.
    deadline = time.monotonic() + 20
    with db.scalars(select(Revision).order_by(Revision.sequence).limit(1001)
                    .execution_options(yield_per=1)) as revisions:
        for index, revision in enumerate(revisions):
            source.require(index < 1000 and time.monotonic() < deadline, "history_recovery_limit")
            source.require(hashlib.sha256(revision.original_bytes).hexdigest() == revision.content_digest, "checkpoint_inconsistent")
            history = history_after(parse_official_catalogue(revision.original_bytes).document, history)
    state.highest_sequence, state.highest_digest = latest.sequence, latest.content_digest
    state.identity_history = history
    state.last_confirmed_current_at = None


def claim(db):
    state = _lock(db)
    now = source.utcnow()
    recover_checkpoint(db, state)
    if state.operation_id and state.lease_until > now:
        db.commit()
        return None, "in_progress"
    # Expired ownership recovers immediately; ordinary successive requests obey
    # a durable global cooldown to keep unauthenticated public access viable.
    if not state.operation_id and state.next_attempt_at and state.next_attempt_at > now:
        db.commit()
        return None, "cooldown"
    operation = uuid.uuid4()
    state.operation_id = operation
    state.lease_until = now + timedelta(seconds=LEASE_SECONDS)
    state.last_attempt_at = now
    state.next_attempt_at = now + timedelta(seconds=COOLDOWN_SECONDS)
    db.commit()
    return operation, "claimed"


def _owned(state, operation):
    source.require(state.operation_id == operation and state.lease_until is not None
                   and state.lease_until > source.utcnow(), "refresh_ownership_lost")


def _store_revision(db, state, raw, verification, publication, confirmed_at):
    """Transactional persistence primitive, called ONLY after all trust gates.

    Does not authenticate evidence. Tests exercise this primitive separately
    with explicitly labelled storage fixtures, never synthetic crypto success.
    """
    document = parse_official_catalogue(raw).document
    digest = hashlib.sha256(raw).hexdigest()
    result = transition(document, digest, state)
    history = history_after(document, state.identity_history)
    if result == "accepted":
        db.add(Revision(sequence=document["sequence"], source=source.SOURCE,
            schema_version=document["schema_version"], content_digest=digest, original_bytes=raw,
            generated_at=datetime.fromisoformat(document["generated_at"].replace("Z", "+00:00")),
            verification_evidence=verification, publication_evidence=publication,
            accepted_at=source.utcnow()))
        db.flush()  # satisfy the checkpoint's composite FK in this transaction
        state.highest_sequence, state.highest_digest = document["sequence"], digest
        state.identity_history = history
    state.last_confirmed_current_at = confirmed_at
    state.source_conflict = None
    state.last_error_code = None
    return result


def _promote(db, state, candidate):
    # Reparse original bytes, never a mutable caller-owned document. Match the
    # genuine verifier result again at the persistence boundary.
    evidence = candidate.provenance
    source.require(evidence.profile == TrustProfile.CATALOGUE and evidence.subject_name == "catalogue.json"
                   and evidence.artifact_sha256 == hashlib.sha256(candidate.raw).hexdigest(), "catalogue_evidence_mismatch")
    source.require_publication(candidate)
    return _store_revision(db, state, candidate.raw, to_json_value(asdict(evidence)),
                           candidate.publication, candidate.confirmed_at)


def status(db):
    state = db.get(State, 1, populate_existing=True)
    revision = db.get(Revision, state.highest_sequence) if state and state.highest_sequence else None
    running = bool(state and state.operation_id and state.lease_until > source.utcnow())
    return {
        "source": source.SOURCE, "trusted_remote_available": revision is not None,
        "schema_version": revision.schema_version if revision else None,
        "sequence": revision.sequence if revision else None,
        "content_digest": revision.content_digest if revision else None,
        "generated_at": revision.generated_at if revision else None,
        "accepted_at": revision.accepted_at if revision else None,
        **{key: getattr(state, key) if state else None for key in (
            "last_attempt_at", "last_download_at", "last_authenticity_verified_at",
            "last_confirmed_current_at", "last_error_code", "source_conflict", "next_attempt_at")},
        "refresh_state": "in_progress" if running else "failed" if state and state.last_error_code else "idle",
        "publication_policy": source.POLICY,
    }


def refresh(db, *, actor=None, request=None):
    """Synchronous API thread; lease + restore lock outlive network/verifier work."""
    with normal_operation():
        try:
            operation, result = claim(db)
            if operation is None:
                return {"result": result, "status": status(db)}
        except (SQLAlchemyError, ConnectorPackageError):
            db.rollback()
            return {"result": "failed", "code": "catalogue_state_unavailable"}
        progress = {}
        candidate, error = None, None
        try:
            candidate = asyncio.run(source.retrieve_candidate(progress))
        except ConnectorPackageError as failure:
            error = failure
        except Exception:
            # Transport/library failures must not leak signed URLs, response
            # bodies or subprocess details through logs or API exception text.
            error = source.SourceError("catalogue_refresh_internal_failure")
        try:
            if maintenance() is not None:
                raise BackupError("Restore is draining requests")
            state = _lock(db)
            _owned(state, operation)
            recover_checkpoint(db, state)
            if error is None:
                try:
                    # Record rollback/substitution even if publication is also
                    # insufficient; only genuinely verified candidates reach here.
                    document = parse_official_catalogue(candidate.raw).document
                    transition(document, candidate.provenance.artifact_sha256, state)
                    history_after(document, state.identity_history)
                    result = _promote(db, state, candidate)
                except ConnectorPackageError as failure:
                    error = failure
            for key, stamp in progress.items():
                setattr(state, key, stamp)
            if error is not None:
                result = "failed"
                state.last_error_code = error.code
                if error.code in CONFLICTS:
                    state.source_conflict = error.code
                elif candidate and state.highest_sequence is not None and parse_official_catalogue(candidate.raw).document["sequence"] > state.highest_sequence:
                    state.source_conflict = "newer_candidate_rejected"
                state.next_attempt_at = max(state.next_attempt_at, source.utcnow() + timedelta(seconds=getattr(error, "retry_after", 60)))
            state.operation_id = state.lease_until = None
            add_audit_event(db, action="connector_catalogue.refreshed", target_type="connector_catalogue",
                actor=actor, request=request, success=error is None,
                summary="Official catalogue refresh completed", metadata={"result": result,
                    "code": error.code if error else None, "sequence": state.highest_sequence})
            db.commit()
            return {"result": result, "status": status(db)}
        except ConnectorPackageError as failure:
            db.rollback()
            return {"result": "failed", "code": failure.code, "status": status(db)}
        except SQLAlchemyError:
            # The short claim remains durable and expires. Failed insertion,
            # audit or state update rolls back together, preserving old trust.
            db.rollback()
            return {"result": "failed", "code": "catalogue_persistence_failed"}
