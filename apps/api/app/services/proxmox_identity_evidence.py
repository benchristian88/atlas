"""Verify the immutable AIP evidence selected by a Proxmox Identity review."""

from dataclasses import dataclass
from datetime import datetime
import re
import uuid

from sqlalchemy import select

from atlas_connector_sdk.aip import body_hash
from app.models import DiscoveryBatchReceipt, DiscoveryRun, EvidenceRecord, KnowledgeAssertion, RunObservedEntity
from app.services.aip_ingestion import DOMAINS, MAX_BATCHES, MAX_OBSERVATIONS, bound_message
from app.services.proxmox_guest_identity import PRESENCE_PREDICATE, REVIEW_TYPE

UNAVAILABLE_EVIDENCE = "The held evidence could not be verified. Run discovery again to refresh this identity review."


@dataclass
class ReviewedEvidence:
    run: DiscoveryRun
    anchor: EvidenceRecord
    held: list[EvidenceRecord]
    observations: dict
    membership: dict
    receipt_hashes: list[str]
    guest: EvidenceRecord | None


def _scope(row):
    return row.customer_id, row.site_id, row.data_source_id


def reviewed_evidence(db, item, claim, integration):
    """Return verifiable evidence, or leave the legacy review pending for a fresh run."""
    if (claim is None or (claim.subject_type, claim.predicate, claim.subject_external_id) !=
            (REVIEW_TYPE, PRESENCE_PREDICATE, item.candidate_external_id)
            or claim.subject_id is not None or claim.object_id is not None or claim.object_type is not None
            or claim.truth_classification != "observed" or claim.is_accepted or claim.retracted_at
            or (item.status == "open" and (not claim.is_source_current or claim.superseded_by_id))):
        return None
    run = db.get(DiscoveryRun, claim.discovery_run_id) if claim.discovery_run_id else None
    if (run is None or run.status != "completed" or run.completed_at is None or run.completeness_status not in {"complete", "partial"}
            or not re.fullmatch(r"[a-f0-9]{64}", run.finalisation_hash or "")
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
    return ReviewedEvidence(run, anchor, held, observations, membership, [row.body_hash for row in receipts], guest)


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
