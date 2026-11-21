"""Verify the immutable AIP evidence selected by a Proxmox Identity review."""

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Literal
import uuid

from sqlalchemy import and_, or_, select

from atlas_connector_sdk.aip import body_hash
from app.models import DiscoveryBatchReceipt, DiscoveryRun, EvidenceRecord, KnowledgeAssertion, RunObservedEntity
from app.services.aip_ingestion import DOMAINS, MAX_BATCHES, MAX_OBSERVATIONS, bound_message
from app.services.proxmox_guest_identity import PRESENCE_PREDICATE, REVIEW_TYPE, observes_guest_at_seal, valid_guest_name

UNAVAILABLE_EVIDENCE = "The held evidence could not be verified. Run discovery again to refresh this identity review."
FINALISATION_HASH = r"[a-f0-9]{64}"


@dataclass
class ReviewedEvidence:
    run: DiscoveryRun
    anchor: EvidenceRecord
    held: list[EvidenceRecord]
    observations: dict
    membership: dict
    receipt_hashes: list[str]
    guest: EvidenceRecord | None
    identity_positive: bool | None


@dataclass(frozen=True)
class EvidenceConflict:
    runs: tuple[tuple[uuid.UUID, str], ...]
    kind: Literal["ambiguous_start", "omission", "newer_positive"]


def _scope(row):
    return row.customer_id, row.site_id, row.data_source_id


def reviewed_evidence(db, item, claim, integration, *, retained=False):
    """Return verifiable evidence, or leave the legacy review pending for a fresh run."""
    if (claim is None or (claim.subject_type, claim.predicate, claim.subject_external_id) !=
            (REVIEW_TYPE, PRESENCE_PREDICATE, item.candidate_external_id)
            or claim.subject_id is not None or claim.object_id is not None or claim.object_type is not None
            or claim.truth_classification != "observed" or claim.is_accepted or claim.retracted_at
            or (item.status == "open" and not retained and (not claim.is_source_current or claim.superseded_by_id))):
        return None
    run = db.get(DiscoveryRun, claim.discovery_run_id) if claim.discovery_run_id else None
    if (run is None or run.status != "completed" or run.completed_at is None or run.completeness_status not in {"complete", "partial"}
            or run.completeness_status == "complete" and not run.is_complete_snapshot
            or not re.fullmatch(FINALISATION_HASH, run.finalisation_hash or "")
            or run.integration_id != integration.id or _scope(run) != _scope(claim)
            or _scope(run) != _scope(integration) or (run.execution_provenance or {}).get("connector_id") != "proxmox"):
        return None
    try:
        provenance = run.execution_provenance
        if (provenance["coverage"]["key"] != run.coverage_key or not isinstance(provenance["object_classes"], list)
                or not isinstance(provenance["mappings"], list)):
            return None
        mapping_keys = set()
        for mapping in provenance["mappings"]:
            key = mapping["kind"], mapping["source_key"]
            if (key in mapping_keys or key[0] not in {"asset", "relationship"} or not isinstance(key[1], str)
                    or not isinstance(mapping["target_key"], (str, type(None)))
                    or not isinstance(mapping["ignored"], bool) or not isinstance(mapping["resolved"], bool)):
                return None
            mapping_keys.add(key)
        value = claim.value_json
        marker = value.get("identity_positive")
        if "identity_positive" in value and not isinstance(marker, bool):
            return None
        ids = value["held_evidence_ids"]
        if not isinstance(ids, list) or not 0 < len(ids) <= MAX_OBSERVATIONS:
            return None
        identifiers = [uuid.UUID(identifier) for identifier in ids]
        if len(set(identifiers)) != len(ids) or claim.evidence_record_id not in identifiers:
            return None
        receipts = list(db.scalars(select(DiscoveryBatchReceipt).where(
            DiscoveryBatchReceipt.discovery_run_id == run.id).order_by(DiscoveryBatchReceipt.sequence)))
        if (not 0 < run.batch_count <= MAX_BATCHES
                or [receipt.sequence for receipt in receipts] != list(range(1, run.batch_count + 1))):
            return None
        observations = {}
        for receipt in receipts:
            payload = receipt.payload_json
            if (body_hash(payload) != receipt.body_hash or payload["message_type"] != "observations"
                    or payload["batch"]["sequence"] != receipt.sequence):
                return None
            bound_message(run, payload)
            observed_at = datetime.fromisoformat(payload["observed_at"].replace("Z", "+00:00"))
            for domain, kind in DOMAINS.items():
                for row in payload[domain]:
                    key = kind, row["external_id"]
                    if key in observations:
                        return None
                    observations[key] = row, observed_at
        if len(observations) != run.observation_count:
            return None
        membership = {(row.entity_type, row.external_id): row for row in db.scalars(select(RunObservedEntity).where(
            RunObservedEntity.discovery_run_id == run.id))}
        records = {row.id: row for row in db.scalars(select(EvidenceRecord).where(EvidenceRecord.id.in_(identifiers)))}
        held = []
        for identifier in identifiers:
            row = records[identifier]
            key = row.entity_kind, row.external_id
            member = membership[key]
            payload, stamp = observations[key]
            if (row.discovery_run_id != run.id or _scope(row) != _scope(run) or _scope(member) != _scope(run)
                    or member.coverage_key != run.coverage_key or member.entity_id is not None
                    or member.evidence_record_id != row.id or member.observed_at != stamp or row.observed_at != stamp
                    or body_hash(payload) != row.payload_hash or payload != row.payload_json
                    or row.entity_kind not in {"asset", "asset_interface", "relationship"}):
                return None
            held.append(row)
        anchor = records[claim.evidence_record_id]
        guest = next((row for row in held if row.entity_kind == "asset"), None)
        expected_anchor = guest or max(held, key=lambda row: (row.observed_at, row.id))
        if (anchor.id != expected_anchor.id or claim.last_observed_at != anchor.observed_at
                or value["guest_observed"] is not (guest is not None)
                or (guest and (anchor.id != guest.id or guest.external_id != item.candidate_external_id
                               or sum(row.entity_kind == "asset" for row in held) != 1))):
            return None
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return ReviewedEvidence(run, anchor, held, observations, membership, [row.body_hash for row in receipts], guest, marker)


def held_observes_guest(evidence, key, binding, bindings):
    """Read sealed eligibility independently of current release prerequisites."""
    if evidence.identity_positive is not None:
        return evidence.identity_positive
    # Pre-existing AIP holds retain their validated receipts and their
    # source binding history. No current accepted assertion proves the seal.
    try:
        return observes_guest_at_seal(evidence.run, key, evidence.held, binding, bindings)
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def newest_evidence_conflict(
    db, reviewed_run, guest_key, guest_class, *, binding, binding_epoch_floor, source_epoch, held_positive,
) -> EvidenceConflict | None:
    """Compare explicit positives and complete omissions using only server start time."""
    run = DiscoveryRun
    provenance = run.execution_provenance
    guest_name = select(EvidenceRecord.payload_json["name"]).join(
        RunObservedEntity, RunObservedEntity.evidence_record_id == EvidenceRecord.id
    ).where(
        RunObservedEntity.discovery_run_id == run.id,
        RunObservedEntity.data_source_id == run.data_source_id,
        RunObservedEntity.customer_id == run.customer_id,
        RunObservedEntity.site_id == run.site_id,
        RunObservedEntity.coverage_key == run.coverage_key,
        RunObservedEntity.entity_type == "asset",
        RunObservedEntity.external_id == guest_key,
        or_(RunObservedEntity.entity_id.is_(None), RunObservedEntity.entity_id == binding.entity_id),
        EvidenceRecord.discovery_run_id == run.id,
        EvidenceRecord.data_source_id == run.data_source_id,
        EvidenceRecord.customer_id == run.customer_id,
        EvidenceRecord.site_id == run.site_id,
        EvidenceRecord.entity_kind == "asset",
        EvidenceRecord.external_id == guest_key,
        EvidenceRecord.payload_json["object_class"].astext == guest_class,
    ).scalar_subquery()
    # Successful holds retain their original claims, even if another run is
    # selected for the preview. Verify dependent-only evidence before using it.
    held_claim = select(KnowledgeAssertion.id).where(
        KnowledgeAssertion.discovery_run_id == run.id,
        KnowledgeAssertion.data_source_id == run.data_source_id,
        KnowledgeAssertion.customer_id == run.customer_id,
        KnowledgeAssertion.site_id == run.site_id,
        KnowledgeAssertion.subject_type == REVIEW_TYPE,
        KnowledgeAssertion.subject_external_id == guest_key,
        KnowledgeAssertion.predicate == PRESENCE_PREDICATE,
        KnowledgeAssertion.retracted_at.is_(None),
    ).limit(1).scalar_subquery()
    complete = and_(run.is_complete_snapshot.is_(True), run.completeness_status == "complete")
    # The UUID stabilizes the token within a tied group. It does not order evidence in time.
    query = select(run.id, run.finalisation_hash, run.started_at, guest_name.label("guest_name"),
                   held_claim.label("held_claim"), complete.label("complete")).where(
        run.id != reviewed_run.id,
        run.integration_id == reviewed_run.integration_id,
        run.data_source_id == reviewed_run.data_source_id,
        run.customer_id == reviewed_run.customer_id,
        run.site_id == reviewed_run.site_id,
        run.coverage_key == reviewed_run.coverage_key,
        run.started_at >= reviewed_run.started_at,
        run.identity_epoch.between(binding_epoch_floor, source_epoch),
        run.status == "completed",
        run.completed_at.is_not(None),
        run.finalisation_hash.regexp_match(f"^{FINALISATION_HASH}$"),
        provenance["connector_id"].astext == "proxmox",
        provenance["coverage"]["key"].astext == reviewed_run.coverage_key,
        provenance["object_classes"].contains([guest_class]),
        or_(complete, and_(run.completeness_status == "partial",
                          or_(guest_name.is_not(None), held_claim.is_not(None)))),
    ).order_by(run.started_at.desc(), run.id)
    latest = None
    with db.execute(query.execution_options(yield_per=16)) as candidates:
        for row in candidates:
            if latest and row.started_at < latest.started_at:
                break
            positive = valid_guest_name(row.guest_name) or (
                row.held_claim is not None and held_positive(row.held_claim)
            )
            if not row.complete and not positive:
                continue
            if latest:
                return EvidenceConflict(((latest.id, latest.finalisation_hash),
                                         (row.id, row.finalisation_hash)), "ambiguous_start")
            latest, latest_positive = row, positive
    if latest is None:
        return None
    kind = "newer_positive" if latest_positive else "omission"
    if latest.started_at == reviewed_run.started_at:
        kind = "ambiguous_start"
    return EvidenceConflict(((latest.id, latest.finalisation_hash),), kind)


def accepted_endpoint_evidence(db, run, external_id, binding):
    """Proof from accepted scoped source assertions on the exact binding target."""
    return db.execute(select(EvidenceRecord, KnowledgeAssertion).join(KnowledgeAssertion,
        KnowledgeAssertion.evidence_record_id == EvidenceRecord.id).join(DiscoveryRun,
        DiscoveryRun.id == EvidenceRecord.discovery_run_id).where(
        EvidenceRecord.data_source_id == run.data_source_id, EvidenceRecord.customer_id == run.customer_id,
        EvidenceRecord.site_id == run.site_id, EvidenceRecord.entity_kind == "asset",
        EvidenceRecord.external_id == external_id, DiscoveryRun.status == "completed", DiscoveryRun.finalisation_hash.is_not(None),
        DiscoveryRun.data_source_id == run.data_source_id, DiscoveryRun.customer_id == run.customer_id,
        DiscoveryRun.site_id == run.site_id, KnowledgeAssertion.discovery_run_id == DiscoveryRun.id,
        KnowledgeAssertion.subject_type == "asset", KnowledgeAssertion.subject_id == binding.entity_id,
        KnowledgeAssertion.subject_external_id == external_id, KnowledgeAssertion.is_accepted.is_(True),
        KnowledgeAssertion.data_source_id == run.data_source_id, KnowledgeAssertion.customer_id == run.customer_id,
        KnowledgeAssertion.site_id == run.site_id, KnowledgeAssertion.retracted_at.is_(None),
    ).order_by(EvidenceRecord.observed_at.desc(), EvidenceRecord.created_at.desc(), EvidenceRecord.id,
               KnowledgeAssertion.id)).all()
