"""Canonical wire adapter into Atlas's existing evidence and review lifecycle."""
from datetime import datetime, timezone
import re
from types import SimpleNamespace

from sqlalchemy import select

from atlas_connector_sdk.aip import body_hash, validate_batch
from atlas_connector_sdk.configuration import source_compatibility
from app.models import (DataSource, DiscoveryBatchReceipt, EvidenceRecord, RunObservedEntity,
    EntitySourceLink, AssetType, RelationshipType, KnowledgeAssertion)
from app.schemas import SimulationObservation, SimulationRelationship
from app.services.discovery_observations import record_observed_entity, reconcile_complete_snapshot
from app.services.simulated_discovery import ingest_observations, ingest_technical_observation
from app.services.connector_contracts import SDK_VERSION

MAX_BODY = 1024 * 1024
MAX_BATCHES = 256
MAX_OBSERVATIONS = 5000
MAX_RUN_BYTES = 32 * 1024 * 1024
MAX_FACTS = 20000
DOMAINS = {"assets": "asset", "networks": "network", "interfaces": "asset_interface", "relationships": "relationship"}
INCOMPLETE = {"permission_limited", "source_unavailable", "authentication_failed", "tls_trust_required",
    "source_incompatible", "invalid_source_record", "timeout"}


class IngestionError(ValueError):
    def __init__(self, code, *, fatal=True):
        self.code, self.fatal = code, fatal
        super().__init__(code)


def canonical_size(message):
    import json
    return len(json.dumps(message, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode())


def reject_sensitive_material(db, run, row, message, token):
    """Reject known leased/installation material before durable evidence writes."""
    import os
    from app.services.integration_secrets import AtlasEncryptedSecretProvider
    from app.services.integration_runtime import _control_secret
    from app.services.discovery_tokens import signing_key
    provider = AtlasEncryptedSecretProvider(db)
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from strings(child)
    known = [token, signing_key().hex(), os.getenv("AUTH_SECRET_KEY", ""), os.getenv("ATLAS_DATA_ENCRYPTION_KEY", "")]
    try:
        known.append(_control_secret())
    except (OSError, ValueError):
        pass
    with provider.materialize_for_job(row, run.id, provider.state(row)) as lease:
        known.extend(lease.values.values())
        try:
            for value in strings(message):
                if (any(secret and secret in value for secret in known)
                        or "PRIVATE KEY-----" in value or re.search(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", value)):
                    raise IngestionError("secret_material")
        finally:
            known.clear()


def bound_message(run, message):
    provenance = run.execution_provenance
    if provenance["sdk_version"] != SDK_VERSION:
        raise IngestionError("sdk_version_changed")
    validate_batch(message, provenance["manifest"])
    expected = {"id": provenance["connector_id"], "version": provenance["connector_version"],
        "bundle_digest": "sha256:" + provenance["connector_digest"]}
    if (message["run_id"] != str(run.id) or message["integration_id"] != str(run.integration_id)
            or message["connector"] != expected or message["protocol_version"] != provenance["aip_version"]
            or message["coverage"] != provenance["coverage"]):
        raise IngestionError("invalid_run_binding")
    version = message.get("source", {}).get("version")
    if version is not None and (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+ -]{0,99}", version)
            or source_compatibility(provenance["manifest"], version) == "known_incompatible"):
        raise IngestionError("source_incompatible")


def mappings(db, run):
    from app.services.connector_mappings import mapping_state
    current = {(row["kind"], row["source_key"]): row for row in mapping_state(db, run.execution_provenance["manifest"])}
    result = {}
    for row in run.execution_provenance["mappings"]:
        actual = current.get((row["kind"], row["source_key"]))
        if actual is None or any(actual[name] != row[name] for name in ["target_key", "ignored", "resolved"]):
            raise IngestionError("mapping_unavailable")
        if row["ignored"]:
            result[(row["kind"], row["source_key"])] = None
        elif row["resolved"]:
            model = AssetType if row["kind"] == "asset" else RelationshipType
            target = db.scalar(select(model).where(model.key == row["target_key"], model.active.is_(True)))
            if target is None:
                raise IngestionError("mapping_unavailable")
            result[(row["kind"], row["source_key"])] = target.key
    return result


def accept_batch(db, run, message):
    bound_message(run, message)
    if message["message_type"] != "observations":
        raise IngestionError("invalid_message_type")
    sequence = message["batch"]["sequence"]
    digest = body_hash(message)
    receipt = db.get(DiscoveryBatchReceipt, (run.id, sequence))
    if receipt:
        if receipt.body_hash != digest:
            raise IngestionError("conflicting_receipt")
        return {"sequence": sequence, "accepted": True, "replayed": True}
    if run.status not in {"pending", "running"} or run.cancellation_requested_at:
        raise IngestionError("run_finalised", fatal=False)
    if sequence > MAX_BATCHES or run.batch_count >= MAX_BATCHES:
        raise IngestionError("batch_limit")
    receipts = list(db.scalars(select(DiscoveryBatchReceipt).where(DiscoveryBatchReceipt.discovery_run_id == run.id)))
    if sum(canonical_size(row.payload_json) for row in receipts) + canonical_size(message) > MAX_RUN_BYTES:
        raise IngestionError("run_size_limit")
    if receipts and message.get("source") != receipts[0].payload_json.get("source"):
        raise IngestionError("source_binding_changed")
    total_facts = sum(len(row["facts"]) for batch in [*(receipt.payload_json for receipt in receipts), message]
        for name in ["assets", "networks", "interfaces"] for row in batch[name])
    if total_facts > MAX_FACTS:
        raise IngestionError("fact_limit")
    mapping = mappings(db, run)
    count = sum(len(message[name]) for name in DOMAINS)
    if run.observation_count + count > MAX_OBSERVATIONS:
        raise IngestionError("observation_limit")
    seen = {(row.entity_type, row.external_id) for row in db.scalars(select(RunObservedEntity).where(
        RunObservedEntity.discovery_run_id == run.id))}
    selected = set(run.execution_provenance["object_classes"])
    records = []
    for domain, kind in DOMAINS.items():
        for observation in message[domain]:
            identity = (kind, observation["external_id"])
            if identity in seen:
                raise IngestionError("duplicate_source_identity")
            seen.add(identity)
            if domain != "relationships" and observation["object_class"] not in selected:
                raise IngestionError("observation_outside_scope")
            if kind == "asset" and ("asset", observation["object_class"]) not in mapping:
                raise IngestionError("mapping_unresolved")
            if kind == "relationship" and ("relationship", observation["relationship_class"]) not in mapping:
                raise IngestionError("mapping_unresolved")
            records.append((kind, observation))
    observed_at = datetime.fromisoformat(message["observed_at"].replace("Z", "+00:00"))
    for kind, observation in records:
        evidence = EvidenceRecord(discovery_run_id=run.id, data_source_id=run.data_source_id,
            customer_id=run.customer_id, site_id=run.site_id, external_id=observation["external_id"],
            entity_kind=kind, payload_json=observation, payload_hash=body_hash(observation), observed_at=observed_at)
        db.add(evidence)
        db.flush()
        record_observed_entity(db, run=run, entity_type=kind, external_id=observation["external_id"],
            entity_id=None, evidence_record_id=evidence.id, observed_at=observed_at)
    db.add(DiscoveryBatchReceipt(discovery_run_id=run.id, sequence=sequence, body_hash=digest, payload_json=message))
    run.batch_count += 1
    run.observation_count += count
    run.warning_count += len(message.get("warnings", []))
    run.source_version = message.get("source", {}).get("version")
    db.flush()
    return {"sequence": sequence, "accepted": True, "replayed": False}


def _references(db, run, messages):
    assets = {row["external_id"]: row for message in messages for row in message["assets"]}
    networks = {row["external_id"] for message in messages for row in message["networks"]}
    links = {(row.entity_type, row.external_id): row for row in db.scalars(select(EntitySourceLink).where(
        EntitySourceLink.data_source_id == run.data_source_id, EntitySourceLink.customer_id == run.customer_id,
        EntitySourceLink.site_id == run.site_id))}
    declarations = {row["key"]: row for row in run.execution_provenance["manifest"]["relationship_classes"]}
    for message in messages:
        for row in message["interfaces"]:
            if row["asset_external_id"] not in assets and ("asset", row["asset_external_id"]) not in links:
                raise IngestionError("invalid_interface_binding")
            if row.get("network_external_id") and row["network_external_id"] not in networks and ("network", row["network_external_id"]) not in links:
                raise IngestionError("invalid_interface_binding")
        for row in message["relationships"]:
            declaration = declarations[row["relationship_class"]]
            for side in ["source", "target"]:
                identity = row[side]["external_id"]
                endpoint = assets.get(identity)
                if endpoint is None:
                    link = links.get(("asset", identity))
                    if link is None:
                        raise IngestionError("invalid_relationship_binding")
                    # Use evidence attributed to accepted source knowledge;
                    # staged evidence from a failed run cannot redefine an endpoint.
                    evidence = db.scalar(select(EvidenceRecord).join(KnowledgeAssertion,
                        KnowledgeAssertion.evidence_record_id == EvidenceRecord.id).where(EvidenceRecord.data_source_id == run.data_source_id,
                        EvidenceRecord.customer_id == run.customer_id, EvidenceRecord.site_id == run.site_id,
                        EvidenceRecord.entity_kind == "asset", EvidenceRecord.external_id == identity,
                        KnowledgeAssertion.subject_type == "asset", KnowledgeAssertion.is_accepted.is_(True),
                        KnowledgeAssertion.retracted_at.is_(None))
                        .order_by(EvidenceRecord.observed_at.desc(), EvidenceRecord.created_at.desc(), EvidenceRecord.id).limit(1))
                    endpoint = evidence.payload_json if evidence else {}
                if endpoint.get("object_class") not in declaration[side + "_object_classes"]:
                    raise IngestionError("invalid_relationship_binding")


def finalise(db, run, row, message, *, failure=False):
    bound_message(run, message)
    if message["message_type"] != "completion" or (message["status"] != "completed") != failure:
        raise IngestionError("invalid_message_type")
    digest = body_hash(message)
    if run.finalisation_hash:
        if run.finalisation_hash != digest:
            raise IngestionError("conflicting_completion", fatal=False)
        return {"run_id": str(run.id), "status": run.status, "replayed": True}
    if run.status not in {"pending", "running"} or run.cancellation_requested_at:
        raise IngestionError("run_finalised", fatal=False)
    receipts = list(db.scalars(select(DiscoveryBatchReceipt).where(DiscoveryBatchReceipt.discovery_run_id == run.id)
        .order_by(DiscoveryBatchReceipt.sequence)))
    if [receipt.sequence for receipt in receipts] != list(range(1, message["last_sequence"] + 1)):
        raise IngestionError("incomplete_receipts", fatal=False)
    if not failure and not receipts:
        raise IngestionError("missing_observation_batch")
    messages = [receipt.payload_json for receipt in receipts]
    if messages and any(batch.get("source") != message.get("source") for batch in messages):
        raise IngestionError("source_binding_changed")
    warnings = [warning["code"] for batch in [*messages, message] for warning in batch.get("warnings", [])]
    if message["completeness"] == "complete" and (not run.is_complete_snapshot or any(code in INCOMPLETE for code in warnings)):
        raise IngestionError("incomplete_coverage")
    summary = {"observations": run.observation_count, "evidence_records_created": run.observation_count,
        "assertions_created": 0, "reconciliation_items_created": 0, "warnings": sorted(set(warnings))}
    if not failure:
        _references(db, run, messages)
        mapping = mappings(db, run)
        assets = {}
        facts = {}
        for batch in messages:
            for observation in batch["assets"]:
                target = mapping[("asset", observation["object_class"])]
                if target is None:
                    continue
                assets[observation["external_id"]] = SimulationObservation(external_id=observation["external_id"],
                    asset_type=target, name=observation["name"],
                    facts={key: observation[key] for key in ["hostname", "status"] if key in observation})
                facts[observation["external_id"]] = observation["facts"]
        relationship_rows = []
        evidence = {(record.entity_kind, record.external_id): record for record in db.scalars(select(EvidenceRecord).where(EvidenceRecord.discovery_run_id == run.id))}
        for batch in messages:
            for relationship in batch["relationships"]:
                target = mapping[("relationship", relationship["relationship_class"])]
                if target is None:
                    continue
                source_id = relationship["source"]["external_id"]
                target_id = relationship["target"]["external_id"]
                declaration = next(item for item in run.execution_provenance["manifest"]["relationship_classes"] if item["key"] == relationship["relationship_class"])
                if declaration["direction"] == "target_to_source":
                    source_id, target_id = target_id, source_id
                relationship_rows.append((SimulationRelationship(relationship_type=target,
                    target_external_id=target_id, truth_classification=relationship["truth_classification"],
                    confidence=relationship["confidence"]), evidence[("relationship", relationship["external_id"])], source_id))
        memberships = {(record.entity_type, record.external_id): record for record in db.scalars(select(RunObservedEntity).where(RunObservedEntity.discovery_run_id == run.id))}
        source = db.get(DataSource, run.data_source_id)
        payload = SimpleNamespace(customer_id=run.customer_id, site_id=run.site_id, observations=list(assets.values()))
        _, _, assertions, items = ingest_observations(db, payload=payload, user_id=run.created_by_user_id,
            source=source, run=run, observed_at=datetime.now(timezone.utc), evidence_by_identity=evidence,
            memberships=memberships, namespaced_facts=facts, relationship_observations=relationship_rows)
        summary["assertions_created"] += assertions
        summary["reconciliation_items_created"] += len(items)
        for batch in messages:
            for domain, kind in [("networks", "network"), ("interfaces", "asset_interface")]:
                for observation in batch[domain]:
                    assertions, count, target_id = ingest_technical_observation(db, run=run, source=source,
                        evidence=evidence[(kind, observation["external_id"])], observation=observation,
                        entity_type=kind, user_id=run.created_by_user_id)
                    memberships[(kind, observation["external_id"])].entity_id = target_id
                    summary["assertions_created"] += assertions
                    summary["reconciliation_items_created"] += count
    now = datetime.now(timezone.utc)
    run.status, run.completeness_status = message["status"], message["completeness"]
    run.finished_at = run.completed_at = now
    run.warning_count += len(message.get("warnings", []))
    run.finalisation_hash = digest
    run.source_version = message.get("source", {}).get("version")
    if run.source_version:
        row.source_version = run.source_version
        row.source_compatibility = source_compatibility(run.execution_provenance["manifest"], run.source_version)
    run.error_message = message["errors"][0]["code"] if message.get("errors") else None
    if message["status"] == "cancelled":
        run.cancellation_requested_at = now
        run.ingestion_generation = None
    if not failure:
        db.flush()
        snapshot = reconcile_complete_snapshot(db, run=run, user_id=run.created_by_user_id, observed_at=now)
        summary.update(baseline_run_id=str(snapshot.baseline_run_id) if snapshot.baseline_run_id else None,
            no_longer_observed_count=snapshot.no_longer_observed_count, reobserved_count=snapshot.reobserved_count)
        row.last_success_at = source.last_success_at = now
        row.last_error_code = None
    else:
        row.last_error_code = run.error_message
        db.get(DataSource, run.data_source_id).last_error_at = now
    run.summary = summary
    return {"run_id": str(run.id), "status": run.status, "replayed": False}
