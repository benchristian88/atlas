"""Simulated discovery vertical slice for testing the knowledge pipeline."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AssetRelationship,
    DataSource,
    DiscoveryRun,
    EvidenceRecord,
    ReconciliationItem,
)
from app.schemas import SimulatedDiscoveryRequest
from app.services.entity_resolution import (
    AssetResolution,
    normalized_name,
    resolve_asset_identity,
)
from app.services.knowledge_assertions import confirm, record_assertion
from app.services.reconciliation import create_item
from app.utils.json_values import to_json_value


def _payload_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _source(db: Session, payload: SimulatedDiscoveryRequest) -> DataSource:
    if payload.data_source_id is not None:
        source = db.get(DataSource, payload.data_source_id)
        if source is None:
            raise ValueError("Data source not found")
        if source.customer_id != payload.customer_id or source.site_id not in {
            None,
            payload.site_id,
        }:
            raise ValueError("Data source does not match the requested customer and site")
        return source
    source = db.scalar(
        select(DataSource).where(
            DataSource.customer_id == payload.customer_id,
            DataSource.site_id == payload.site_id,
            DataSource.name == "Manual Discovery Simulation",
            DataSource.source_type == "simulated_discovery",
        )
    )
    if source is None:
        source = DataSource(
            customer_id=payload.customer_id,
            site_id=payload.site_id,
            name="Manual Discovery Simulation",
            source_type="simulated_discovery",
            status="active",
            trust_level="test",
            notes="Created automatically by the simulated discovery endpoint.",
        )
        db.add(source)
        db.flush()
    return source


def _manual_source(
    db: Session, customer_id: uuid.UUID, site_id: uuid.UUID | None
) -> DataSource:
    source = db.scalar(
        select(DataSource).where(
            DataSource.customer_id == customer_id,
            DataSource.site_id == site_id,
            DataSource.name == "Atlas Manual Inventory",
            DataSource.source_type == "manual",
        )
    )
    if source is None:
        source = DataSource(
            customer_id=customer_id,
            site_id=site_id,
            name="Atlas Manual Inventory",
            source_type="manual",
            status="active",
            trust_level="declared",
            notes="Represents accepted operational knowledge entered in Atlas.",
        )
        db.add(source)
        db.flush()
    return source


def run_simulation(
    db: Session,
    *,
    payload: SimulatedDiscoveryRequest,
    user_id: uuid.UUID,
) -> tuple[DiscoveryRun, int, int, list[ReconciliationItem]]:
    now = datetime.now(timezone.utc)
    source = _source(db, payload)
    run = DiscoveryRun(
        integration_id=None,
        data_source_id=source.id,
        customer_id=payload.customer_id,
        site_id=payload.site_id,
        status="running",
        started_at=now,
        created_by_user_id=user_id,
        summary={},
    )
    db.add(run)
    db.flush()

    evidence_count = 0
    assertions_created = 0
    items: list[ReconciliationItem] = []
    asset_jobs = []
    run_map: dict[str, AssetResolution] = {}

    def remember(result: tuple[ReconciliationItem, bool]) -> None:
        item, created = result
        if created:
            items.append(item)

    # Pass one records evidence and resolves every asset before relationships.
    for observation in payload.observations:
        external_id = observation.external_id or (
            f"simulated:{observation.asset_type}:{observation.name}"
        )
        raw = to_json_value(observation)
        evidence = EvidenceRecord(
            discovery_run_id=run.id,
            data_source_id=source.id,
            customer_id=payload.customer_id,
            site_id=payload.site_id,
            external_id=external_id,
            entity_kind=observation.entity_kind,
            payload_json=to_json_value(raw),
            payload_hash=_payload_hash(raw),
            observed_at=now,
        )
        db.add(evidence)
        db.flush()
        evidence_count += 1
        if observation.entity_kind != "asset":
            continue

        resolution = resolve_asset_identity(
            db,
            data_source_id=source.id,
            customer_id=payload.customer_id,
            site_id=payload.site_id,
            external_id=external_id,
            name=observation.name,
            asset_type=observation.asset_type,
            hostname=observation.facts.get("hostname"),
            run_map=run_map,
            observed_at=now,
        )
        if resolution.asset is None and resolution.status == "unresolved":
            resolution.status = "pending_asset_acceptance"
        run_map[external_id] = resolution
        asset = resolution.asset
        assertion_by_field = {}
        selected = {
            "asset_type": observation.asset_type,
            "name": observation.name,
            "hostname": observation.facts.get("hostname"),
            "status": observation.facts.get("status"),
        }
        for field, value in selected.items():
            if value is None:
                continue
            assertion, created = record_assertion(
                db,
                customer_id=payload.customer_id,
                site_id=payload.site_id,
                subject_type="asset",
                subject_id=asset.id if asset else None,
                subject_external_id=external_id,
                predicate=field,
                value=value,
                data_source_id=source.id,
                discovery_run_id=run.id,
                evidence_record_id=evidence.id,
                observed_at=now,
            )
            assertion_by_field[field] = assertion
            assertions_created += int(created)

        for interface in observation.interfaces:
            if interface.ip_address is None:
                continue
            _, created = record_assertion(
                db,
                customer_id=payload.customer_id,
                site_id=payload.site_id,
                subject_type="asset",
                subject_id=asset.id if asset else None,
                subject_external_id=external_id,
                predicate=f"interface.{interface.name}.ip_address",
                value={
                    "ip_address": interface.ip_address,
                    "network_name": interface.network_name,
                },
                data_source_id=source.id,
                discovery_run_id=run.id,
                evidence_record_id=evidence.id,
                observed_at=now,
            )
            assertions_created += int(created)

        if asset is None:
            anchor = assertion_by_field.get("name") or assertion_by_field["asset_type"]
            possible_duplicate = resolution.status == "possible_duplicate"
            remember(
                create_item(
                    db,
                    assertion=anchor,
                    category=("possible_duplicate" if possible_duplicate else "newly_discovered"),
                    entity_type="asset",
                    entity_id=None,
                    candidate_external_id=external_id,
                    current_value=(
                        {
                            "possible_matches": [
                                {
                                    "id": candidate.id,
                                    "name": candidate.name,
                                    "asset_type": candidate.asset_type,
                                }
                                for candidate in resolution.candidates
                            ]
                        }
                        if possible_duplicate
                        else None
                    ),
                    observed_value={
                        "name": observation.name,
                        "asset_type": observation.asset_type,
                        "facts": observation.facts,
                        "interfaces": [
                            item.model_dump(mode="json")
                            for item in observation.interfaces
                        ],
                    },
                    recommended_action=(
                        "Link to the intended existing asset"
                        if possible_duplicate
                        else "Create asset or link to an existing asset"
                    ),
                )
            )
        else:
            for field, assertion in assertion_by_field.items():
                current_value = getattr(asset, field, None)
                observed_value = assertion.value_json
                if current_value == observed_value:
                    continue
                if field in {"name", "hostname"} and normalized_name(
                    current_value
                ) == normalized_name(observed_value):
                    continue
                category = "contradiction" if asset.source == "manual" else "changed"
                remember(
                    create_item(
                        db,
                        assertion=assertion,
                        category=category,
                        entity_type="asset",
                        entity_id=asset.id,
                        candidate_external_id=external_id,
                        current_value={"field": field, "value": current_value},
                        observed_value={"field": field, "value": observed_value},
                        recommended_action=f"Update asset {field}",
                    )
                )
        asset_jobs.append((observation, evidence, external_id))

    # Pass two resolves relationship endpoints from durable links and the run map.
    for observation, evidence, external_id in asset_jobs:
        for relationship in observation.relationships:
            source_resolution = run_map[external_id]
            target_resolution = resolve_asset_identity(
                db,
                data_source_id=source.id,
                customer_id=payload.customer_id,
                site_id=payload.site_id,
                external_id=relationship.target_external_id,
                run_map=run_map,
                allow_external_name_hint=True,
                observed_at=now,
            )
            source_asset = source_resolution.asset
            target_asset = target_resolution.asset
            assertion, created = record_assertion(
                db,
                customer_id=payload.customer_id,
                site_id=payload.site_id,
                subject_type="asset",
                subject_id=source_asset.id if source_asset else None,
                subject_external_id=external_id,
                predicate=relationship.relationship_type,
                object_type="asset",
                object_id=target_asset.id if target_asset else None,
                object_external_id=relationship.target_external_id,
                data_source_id=source.id,
                discovery_run_id=run.id,
                evidence_record_id=evidence.id,
                observed_at=now,
            )
            assertions_created += int(created)
            existing_relationship = None
            competing_relationship = None
            if source_asset is not None and target_asset is not None:
                existing_relationship = db.scalar(
                    select(AssetRelationship).where(
                        AssetRelationship.source_asset_id == source_asset.id,
                        AssetRelationship.target_asset_id == target_asset.id,
                        AssetRelationship.relationship_type == relationship.relationship_type,
                    )
                )
                if existing_relationship is None:
                    competing = list(
                        db.scalars(
                            select(AssetRelationship).where(
                                AssetRelationship.source_asset_id == source_asset.id,
                                AssetRelationship.target_asset_id == target_asset.id,
                            )
                        )
                    )
                    if len(competing) == 1:
                        competing_relationship = competing[0]
            observed_value = {
                "source_external_id": external_id,
                "target_external_id": relationship.target_external_id,
                "relationship_type": relationship.relationship_type,
                "resolved_source_asset_id": source_asset.id if source_asset else None,
                "resolved_target_asset_id": target_asset.id if target_asset else None,
                "resolved_source_name": source_asset.name if source_asset else None,
                "resolved_target_name": target_asset.name if target_asset else None,
                "source_resolution_status": source_resolution.status,
                "target_resolution_status": target_resolution.status,
                "blocked_reason": None,
                "current_relationship_id": (
                    existing_relationship.id
                    if existing_relationship
                    else competing_relationship.id
                    if competing_relationship
                    else None
                ),
            }
            unresolved = []
            if source_asset is None:
                unresolved.append(f"source {external_id} ({source_resolution.status})")
            if target_asset is None:
                unresolved.append(
                    f"target {relationship.target_external_id} ({target_resolution.status})"
                )
            if unresolved:
                observed_value["blocked_reason"] = (
                    f"Unresolved relationship endpoint: {', '.join(unresolved)}"
                )
            if existing_relationship is not None:
                confirm(assertion)
                for stale_item in db.scalars(
                    select(ReconciliationItem).where(
                        ReconciliationItem.assertion_id == assertion.id,
                        ReconciliationItem.entity_type == "asset_relationship",
                        ReconciliationItem.status.in_(("open", "deferred")),
                    )
                ):
                    stale_item.status = "accepted"
                    stale_item.entity_id = existing_relationship.id
                    stale_item.decision_reason = (
                        "Existing operational relationship corroborated by discovery"
                    )
                    stale_item.decided_by_user_id = user_id
                    stale_item.decided_at = now
                manual = _manual_source(db, payload.customer_id, payload.site_id)
                declared, declared_created = record_assertion(
                    db,
                    customer_id=payload.customer_id,
                    site_id=payload.site_id,
                    subject_type="asset",
                    subject_id=source_asset.id,
                    predicate=relationship.relationship_type,
                    object_type="asset",
                    object_id=target_asset.id,
                    truth_classification="declared",
                    data_source_id=manual.id,
                    observed_at=existing_relationship.created_at or now,
                )
                confirm(declared)
                assertions_created += int(declared_created)
                continue
            remember(
                create_item(
                    db,
                    assertion=assertion,
                    category=("contradiction" if competing_relationship else "inferred_relationship"),
                    entity_type="asset_relationship",
                    entity_id=None,
                    candidate_external_id=external_id,
                    current_value=(
                        {
                            "relationship_id": competing_relationship.id,
                            "source_asset_id": source_asset.id,
                            "source_name": source_asset.name,
                            "relationship_type": competing_relationship.relationship_type,
                            "target_asset_id": target_asset.id,
                            "target_name": target_asset.name,
                        }
                        if competing_relationship
                        else "No current relationship"
                    ),
                    observed_value=observed_value,
                    recommended_action=(
                        "Resolve relationship endpoints"
                        if unresolved
                        else "Update relationship"
                        if competing_relationship
                        else "Create relationship"
                    ),
                )
            )

    run.status = "completed"
    run.finished_at = datetime.now(timezone.utc)
    run.completed_at = run.finished_at
    run.summary = to_json_value({
        "observations": len(payload.observations),
        "evidence_records_created": evidence_count,
        "assertions_created": assertions_created,
        "reconciliation_items_created": len(items),
    })
    source.last_success_at = run.finished_at
    return run, evidence_count, assertions_created, items
